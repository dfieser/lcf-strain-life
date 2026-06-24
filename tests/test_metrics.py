"""Tests for lcf.metrics — per-cycle metrics and modulus estimation."""

import numpy as np
import pytest

from lcf import cycles, metrics
from lcf.ingest import from_timeseries
from lcf.models import TestMetadata


def _reduce(s):
    meta = TestMetadata(name="syn", area=s.area, E=200000.0, already_true=True)
    test = from_timeseries(s.time, s.strain, s.force, metadata=meta)
    return test, cycles.reduce_cycles(test)


def test_per_cycle_metric_values(synthetic_cyclic):
    s = synthetic_cyclic
    test, rc = _reduce(s)
    pcm = metrics.per_cycle_metrics(test, rc, E=200000.0)
    row = pcm.table.iloc[3]
    assert row["stress_amp"] == pytest.approx(s.stress_amp, rel=1e-3)
    assert row["mean_stress"] == pytest.approx(0.0, abs=1e-2)
    assert row["total_strain_amp"] == pytest.approx(s.eps_amp, rel=1e-3)
    assert row["elastic_strain_amp"] == pytest.approx(s.stress_amp / 200000.0, rel=1e-3)
    assert row["r_tc"] == pytest.approx(1.0, rel=1e-3)


def test_plastic_strain_amp_identity(synthetic_cyclic):
    s = synthetic_cyclic
    test, rc = _reduce(s)
    pcm = metrics.per_cycle_metrics(test, rc, E=200000.0)
    row = pcm.table.iloc[3]
    # Δε_p/2 = Δε_t/2 − Δσ/(2E)
    expected = row["total_strain_amp"] - row["stress_amp"] / 200000.0
    assert row["plastic_strain_amp"] == pytest.approx(expected)


def test_energy_density_matches_analytic(synthetic_cyclic):
    s = synthetic_cyclic
    test, rc = _reduce(s)
    pcm = metrics.per_cycle_metrics(test, rc, E=200000.0)
    # a mid cycle's loop area should match the analytic ellipse area
    mid = pcm.table.iloc[3]["energy_density"]
    assert mid == pytest.approx(s.energy_per_cycle, rel=1e-3)


def test_metric_columns_present(synthetic_cyclic):
    s = synthetic_cyclic
    test, rc = _reduce(s)
    pcm = metrics.per_cycle_metrics(test, rc, E=200000.0)
    for c in metrics.PerCycleMetrics.METRIC_COLUMNS:
        assert c in pcm.table.columns


def test_E_resolution_from_metadata(synthetic_cyclic):
    s = synthetic_cyclic
    meta = TestMetadata(name="syn", area=s.area, E=190000.0, already_true=True)
    test = from_timeseries(s.time, s.strain, s.force, metadata=meta)
    rc = cycles.reduce_cycles(test)
    pcm = metrics.per_cycle_metrics(test, rc)  # no explicit E
    assert pcm.E == pytest.approx(190000.0)


def test_estimate_modulus_linear_segment():
    E = 205000.0
    strain = np.linspace(0.01, -0.01, 100)  # unloading branch
    stress = E * strain                       # pure elastic
    assert metrics.estimate_modulus(strain, stress) == pytest.approx(E, rel=1e-6)


def test_estimate_modulus_used_when_no_E(synthetic_cyclic):
    s = synthetic_cyclic
    meta = TestMetadata(name="syn", area=s.area, already_true=True)  # no E
    test = from_timeseries(s.time, s.strain, s.force, metadata=meta)
    rc = cycles.reduce_cycles(test)
    pcm = metrics.per_cycle_metrics(test, rc)  # must estimate
    assert pcm.E > 0


def test_half_life_and_peak_hardened_cycles(synthetic_cyclic):
    s = synthetic_cyclic
    test, rc = _reduce(s)
    pcm = metrics.per_cycle_metrics(test, rc, E=200000.0)
    assert 1 <= pcm.half_life_cycle <= pcm.table["cycle"].max()
    assert 1 <= pcm.peak_hardened_cycle <= pcm.table["cycle"].max()
