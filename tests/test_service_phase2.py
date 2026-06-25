"""Tests for the Phase 2 service methods (compute/save/recall)."""

import numpy as np
import pytest

from lcf.service import LcfService

PROPS = dict(sigma_f=1000.0, b=-0.09, eps_f=0.5, c=-0.6, E=200000.0)
ASTM = [-2, 1, -3, 5, -1, 3, -4, 4, -2]


@pytest.fixture
def service(tmp_path):
    return LcfService(tmp_path / "store")


def test_count_rainflow_saves(service):
    summary = service.count_rainflow("hist1", ASTM)
    assert summary["n_cycles"] == 7
    assert summary["total_count"] == pytest.approx(4.0)
    df = service.store.get_dataframe("hist1", "rainflow")
    assert len(df) == 7


def test_spectrum_life(service):
    strain = [0.0, 0.005, -0.005, 0.005, -0.005, 0.0]
    stress = [0.0, 300.0, -300.0, 300.0, -300.0, 0.0]
    out = service.compute_spectrum_life(strain, stress, name="spec1", **PROPS)
    assert out["blocks_to_failure"] > 0
    assert np.isfinite(out["cycles_to_failure"])
    assert service.recall("spec1", "spectrum_life") is not None


def test_compute_damage(service):
    out = service.compute_damage([10, 20], [1000, 5000], rule="miner")
    assert out["damage"] == pytest.approx(0.014)
    assert out["rule"] == "miner"


def test_compute_notch_local(service):
    out = service.compute_notch_local(
        100.0, 2.53, E=207000.0, K=1240.0, n=0.27,
        sigma_f=886.0, b=-0.14, eps_f=0.28, c=-0.5, name="notch1",
    )
    assert out["local_stress_amp"] == pytest.approx(182.0, abs=2.0)
    assert service.recall("notch1", "notch_local") is not None


def test_fit_design_curve(service):
    amp = [0.01, 0.008, 0.006, 0.004, 0.003, 0.002]
    life = [1e4 * (a / 0.002) ** (-2.0) for a in amp]
    out = service.fit_design_curve(amp, life, design_amplitude=0.005, material="M1")
    assert "design_life" in out and out["design_life"] < out["median_life"]
    assert service.recall("M1", "design_curve") is not None


def test_compute_creep_fatigue(service):
    out = service.compute_creep_fatigue([900], [1000], [90], [100], name="cf1")
    assert out["d_total"] == pytest.approx(1.8)
    assert out["failed"] is True
    assert "envelope_check" in out


def test_design_curve_outputs_valid_json(service):
    # a 2-point-ish edge would give NaN stderr; ensure sanitization keeps it JSON-safe
    import json
    from lcf.store import dumps
    amp = [0.01, 0.006, 0.003]
    life = [1e4, 5e4, 2e5]
    out = service.fit_design_curve(amp, life)
    json.loads(dumps(out))  # must not raise
