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


def test_find_turning_points_amplitude_gate_rejects_noise():
    # large reversal at the ends, tiny noise blip in the middle
    x = np.array([0.0, 1.0, 0.98, 1.0, 2.0, 0.0])  # mid blip swing ~0.02
    raw = cycles.find_turning_points(x)
    gated = cycles.find_turning_points(x, min_range=0.1)
    assert raw.size > gated.size  # gate removes the small blip pair


def test_find_turning_points_gate_keeps_real_cycles():
    t = np.linspace(0, 6 * np.pi, 600)
    x = np.sin(t)  # amplitude 1
    gated = cycles.find_turning_points(x, min_range=0.05)  # gate << 2*amplitude
    raw = cycles.find_turning_points(x)
    assert gated.size == raw.size  # genuine reversals survive


def test_reduce_cycles_default_gate_keeps_clean_count(synthetic_cyclic):
    s = synthetic_cyclic
    meta = TestMetadata(name="syn", area=s.area, already_true=True)
    test = from_timeseries(s.time, s.strain, s.force, metadata=meta)
    rc = cycles.reduce_cycles(test)  # default 2%-of-range gate
    assert rc.n_cycles == s.n_cycles  # default gate doesn't drop real loops


def test_reduce_cycles_warns_on_noisy_data():
    import warnings as _w
    # noisy monotonic ramp -> many spurious reversals without a strong gate
    t = np.linspace(0, 1, 400)
    rng = np.linspace(0, 0.01, 400) + 2e-4 * np.sin(np.linspace(0, 800, 400))
    meta = TestMetadata(name="noisy", area=10.0, already_true=True)
    test = from_timeseries(t, rng, rng * 1e5, metadata=meta)
    params = AnalysisParams(min_strain_range=0.0)  # disable gate to expose noise
    with _w.catch_warnings(record=True) as w:
        _w.simplefilter("always")
        try:
            cycles.reduce_cycles(test, params)
        except ValueError:
            pass
        assert any("implausibly dense" in str(x.message) for x in w)


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


def test_find_failure_cycle_uses_max_reference():
    # default reference is the max (cyclically hardened) peak = 500
    peak = np.array([400, 450, 480, 490, 495, 500, 495, 480, 400, 340, 300.0])
    n_f, runout = cycles.find_failure_cycle(peak, pct=30.0)  # ref = max = 500
    # threshold = 350; first below (after the peak) at index 9 (340) -> cycle 10
    assert n_f == 10
    assert runout is False


def test_find_failure_cycle_robust_to_post_failure_tail():
    """H2: acquisition continuing past failure must not bias the reference."""
    # hardens to 500, fails ~cycle 8, then logs collapsed values for many cycles
    pre = [400, 450, 500, 500, 480, 420, 360, 349, 300]
    tail = [120] * 30  # long post-failure recording
    peak = np.array(pre + tail, dtype=float)
    n_f, runout = cycles.find_failure_cycle(peak, pct=30.0)  # default max ref
    assert runout is False
    assert n_f == 8  # not pulled later by the tail


def test_find_failure_cycle_rejects_nonpositive_reference():
    """M3: an all-compressive / sign-flipped peak series is rejected."""
    with pytest.raises(ValueError, match="positive"):
        cycles.find_failure_cycle(np.array([-100.0, -200.0, -300.0]), pct=30.0)


def test_find_failure_cycle_empty():
    n_f, runout = cycles.find_failure_cycle(np.array([]), pct=30.0)
    assert n_f == 0 and runout is True
