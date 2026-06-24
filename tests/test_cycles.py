"""Tests for lcf.cycles — turning-point detection and cycle reduction."""

import numpy as np
import pytest

from lcf import cycles
from lcf.ingest import from_timeseries
from lcf.models import AnalysisParams, TestMetadata


# --- turning points ---------------------------------------------------------
def test_find_turning_points_simple():
    # up, down, up -> two turning points at the peak and the valley
    x = np.array([0.0, 1.0, 2.0, 1.0, 0.0, 1.0, 2.0])
    tp = cycles.find_turning_points(x)
    np.testing.assert_array_equal(tp, [2, 4])


def test_find_turning_points_handles_flats():
    # plateau at the peak should still register a single reversal
    x = np.array([0.0, 1.0, 2.0, 2.0, 2.0, 1.0, 0.0])
    tp = cycles.find_turning_points(x)
    assert tp.size == 1
    assert x[tp[0]] == 2.0


def test_find_turning_points_monotonic_returns_empty():
    assert cycles.find_turning_points(np.arange(10.0)).size == 0


def test_find_turning_points_too_short():
    assert cycles.find_turning_points([1.0, 2.0]).size == 0


# --- cycle reduction --------------------------------------------------------
def test_reduce_cycles_count(synthetic_cyclic):
    s = synthetic_cyclic
    meta = TestMetadata(name="syn", area=s.area, already_true=True)
    test = from_timeseries(s.time, s.strain, s.force, metadata=meta)
    rc = cycles.reduce_cycles(test)
    assert rc.n_cycles == s.n_cycles  # exactly n_cycles closed loops


def test_reduce_cycles_peak_valley_values(synthetic_cyclic):
    s = synthetic_cyclic
    meta = TestMetadata(name="syn", area=s.area, already_true=True)
    test = from_timeseries(s.time, s.strain, s.force, metadata=meta)
    rc = cycles.reduce_cycles(test)
    row = rc.table.iloc[3]  # a mid loop
    assert row["stress_max"] == pytest.approx(s.stress_amp, rel=1e-3)
    assert row["stress_min"] == pytest.approx(-s.stress_amp, rel=1e-3)
    assert row["strain_max"] == pytest.approx(s.eps_amp, rel=1e-3)
    assert row["strain_min"] == pytest.approx(-s.eps_amp, rel=1e-3)


def test_reduce_cycles_constant_amplitude_is_runout(synthetic_cyclic):
    s = synthetic_cyclic
    meta = TestMetadata(name="syn", area=s.area, already_true=True)
    test = from_timeseries(s.time, s.strain, s.force, metadata=meta)
    rc = cycles.reduce_cycles(test)
    # constant amplitude -> peak load never drops -> run-out
    assert rc.runout is True
    assert rc.n_f == rc.n_cycles


def test_reduce_cycles_table_columns(synthetic_cyclic):
    s = synthetic_cyclic
    meta = TestMetadata(name="syn", area=s.area, already_true=True)
    test = from_timeseries(s.time, s.strain, s.force, metadata=meta)
    rc = cycles.reduce_cycles(test)
    assert list(rc.table.columns) == list(cycles.ReducedCycles.COLUMNS)
    assert (rc.table["cycle"].to_numpy() == np.arange(1, rc.n_cycles + 1)).all()


def test_reduce_cycles_raises_on_monotonic():
    meta = TestMetadata(name="ramp", area=10.0, already_true=True)
    t = np.linspace(0, 1, 50)
    test = from_timeseries(t, t * 0.01, t * 1000.0, metadata=meta)
    with pytest.raises(ValueError, match="reversal"):
        cycles.reduce_cycles(test)


# --- failure criterion ------------------------------------------------------
def test_find_failure_cycle_load_drop():
    # hardening to 500, stable, then softening below 30% of 500 = 350
    peak = np.array([400, 450, 500, 500, 480, 420, 360, 349, 300, 200.0])
    n_f, runout = cycles.find_failure_cycle(peak, pct=30.0, stabilized_value=500.0)
    assert runout is False
    assert n_f == 8  # 1-based: first value < 350 is index 7 (349) -> cycle 8


def test_find_failure_cycle_runout():
    peak = np.array([400, 450, 500, 500, 490.0])  # never drops 30%
    n_f, runout = cycles.find_failure_cycle(peak, pct=30.0, stabilized_value=500.0)
    assert runout is True
    assert n_f == 5


def test_find_failure_cycle_uses_half_life_reference():
    # 11 cycles; half-life index = (11-1)//2 = 5 -> value 500
    peak = np.array([400, 450, 480, 490, 495, 500, 495, 480, 400, 340, 300.0])
    n_f, runout = cycles.find_failure_cycle(peak, pct=30.0)  # ref = peak[5] = 500
    # threshold = 350; first below at index 9 (340) -> cycle 10
    assert n_f == 10
    assert runout is False


def test_find_failure_cycle_empty():
    n_f, runout = cycles.find_failure_cycle(np.array([]), pct=30.0)
    assert n_f == 0 and runout is True
