"""Tests for lcf.pipeline — per-test and multi-test orchestration."""

import numpy as np
import pandas as pd
import pytest

from lcf import pipeline
from lcf.ingest import from_timeseries
from lcf.models import AnalysisParams, TestMetadata


def _make_test(s, name="syn"):
    meta = TestMetadata(name=name, area=s.area, E=200000.0, already_true=True, material="SYN")
    return from_timeseries(s.time, s.strain, s.force, metadata=meta)


def test_analyze_test_summary(synthetic_cyclic):
    s = synthetic_cyclic
    ta = pipeline.analyze_test(_make_test(s))
    sm = ta.summary
    assert sm["stress_amp"] == pytest.approx(s.stress_amp, rel=1e-3)
    assert sm["total_strain_amp"] == pytest.approx(s.eps_amp, rel=1e-3)
    assert sm["mean_stress"] == pytest.approx(0.0, abs=1e-2)
    assert sm["energy_half_life"] == pytest.approx(s.energy_per_cycle, rel=1e-3)
    assert sm["runout"] is True
    assert sm["n_f"] == s.n_cycles


def test_analyze_material_runout_no_fit(make_synthetic):
    # two constant-amplitude (runout) tests -> no strain-life fit, with a note
    tests = [
        _make_test(make_synthetic(eps_amp=0.010, stress_amp=400.0), "t1"),
        _make_test(make_synthetic(eps_amp=0.006, stress_amp=350.0), "t2"),
    ]
    ma = pipeline.analyze_material(tests, material="SYN")
    assert ma.fit is None
    assert any("run-out" in n for n in ma.notes)
    assert len(ma.tests) == 2
    assert list(ma.summary_table["name"]) == ["t1", "t2"]


def test_fit_from_summary_golden(sae1137):
    """The multi-test fit path reproduces the SAE 1137 golden constants."""
    g = sae1137
    runout = np.array([False, False, False, False, False, True])  # longest life = runout
    summary = pd.DataFrame(
        {
            "total_strain_amp": g.total_strain_amp,
            "stress_amp": g.stress_amp,
            "plastic_strain_amp": g.plastic_strain_amp,
            "reversals": g.reversals,
            "E": g.E,
            "runout": runout,
        }
    )
    params = AnalysisParams(min_plastic_strain=5e-4)
    fit, notes = pipeline.fit_from_summary(summary, params)
    assert fit is not None
    assert fit.coffin_manson.c == pytest.approx(g.ref["c"], abs=0.04)
    assert fit.coffin_manson.eps_f == pytest.approx(g.ref["eps_f"], rel=0.2)
    assert any("run-out" in n for n in notes)


def test_fit_from_summary_too_few():
    summary = pd.DataFrame(
        {
            "total_strain_amp": [0.009],
            "stress_amp": [553.0],
            "plastic_strain_amp": [0.006],
            "reversals": [4234.0],
            "E": [208000.0],
            "runout": [False],
        }
    )
    fit, notes = pipeline.fit_from_summary(summary)
    assert fit is None
    assert any("fewer than 2" in n for n in notes)
