"""Tests for lcf.service: compute/save/recall orchestration."""

import numpy as np
import pytest

from lcf.service import LcfService


@pytest.fixture
def service(tmp_path):
    return LcfService(tmp_path / "store")


def test_analyze_timeseries_saves_and_summarizes(service, synthetic_cyclic):
    s = synthetic_cyclic
    summary = service.analyze_timeseries(
        "spec-1", list(s.time), list(s.strain), list(s.force), s.area,
        E=200000.0, already_true=True,
    )
    assert summary["stress_amp"] == pytest.approx(s.stress_amp, rel=1e-3)
    # per-cycle table and summary persisted and recallable
    assert service.recall("spec-1", "summary")["value"]["n_cycles"] == s.n_cycles
    df = service.store.get_dataframe("spec-1", "per_cycle")
    assert len(df) == s.n_cycles


def test_analyze_timeseries_cache_hash_stable(service, synthetic_cyclic):
    s = synthetic_cyclic
    args = ("spec-1", list(s.time), list(s.strain), list(s.force), s.area)
    service.analyze_timeseries(*args, E=200000.0, already_true=True)
    h1 = service.recall("spec-1", "summary")["input_hash"]
    service.analyze_timeseries(*args, E=200000.0, already_true=True)
    h2 = service.recall("spec-1", "summary")["input_hash"]
    assert h1 == h2  # identical inputs -> identical hash (cache would hit)


def test_fit_strain_life_golden_and_saved(service, sae1137):
    g = sae1137
    res = service.fit_strain_life(
        list(g.total_strain_amp), list(g.stress_amp), list(g.reversals),
        g.ref["E_nominal"], plastic_strain_amp=list(g.plastic_strain_amp),
        min_plastic_strain=5e-4, material="SAE1137",
    )
    assert res["coffin_manson"]["c"] == pytest.approx(g.ref["c"], abs=0.04)
    assert service.recall("SAE1137", "strain_life_fit") is not None


def test_predict_life(service):
    out = service.predict_life(0.01, sigma_f=1000.0, b=-0.09, eps_f=0.5, c=-0.6, E=200000.0)
    assert out["reversals"] > 0
    assert out["cycles"] == pytest.approx(out["reversals"] / 2.0)


def test_mean_stress_swt(service):
    out = service.mean_stress_equivalent_stress(300.0, 100.0, "swt")
    assert out["equivalent_stress_amp"] == pytest.approx(np.sqrt(400.0 * 300.0))


def test_mean_stress_walker_from_sigma_u(service):
    out = service.mean_stress_equivalent_stress(
        300.0, 100.0, "walker", sigma_u=600.0
    )
    assert out["gamma"] == pytest.approx(0.8818 - 2.00e-4 * 600.0)


def test_list_results(service):
    service.predict_life(0.01, 1000.0, -0.09, 0.5, -0.6, 200000.0)  # no save
    service.fit_strain_life([0.009, 0.005], [553, 464], [4234, 14768], 208000.0,
                            material="M1")
    assert any(r["key"] == "M1" for r in service.list_results())


def test_energy_life_fit_persists_and_predicts(service):
    # exact Halford-Morrow data from the Zhang 2013 Table 5 constants, 350 C
    W_f, beta = 9.30, -0.43
    rev = [3e2, 2e3, 1e4, 8e4]
    dwp = [W_f * r**beta for r in rev]
    out = service.fit_energy_life(dwp, rev, material="AlSi12")
    assert out["W_f"] == pytest.approx(W_f, rel=1e-6)
    assert out["beta"] == pytest.approx(beta, rel=1e-6)
    saved = service.recall("AlSi12", "energy_life_fit")["value"]
    assert saved["W_f"] == pytest.approx(W_f, rel=1e-6)
    pred = service.predict_life_energy(dwp[2], W_f, beta)
    assert pred["reversals"] == pytest.approx(rev[2], rel=1e-9)
    assert pred["cycles"] == pytest.approx(rev[2] / 2.0, rel=1e-9)


def test_estimate_plastic_energy_masing(service):
    out = service.estimate_plastic_energy_masing(300.0, 0.004, 0.162)
    expected = (1.0 - 0.162) / (1.0 + 0.162) * 300.0 * 0.004
    assert out["plastic_energy_per_cycle"] == pytest.approx(expected)
    assert "Masing" in out["note"]
