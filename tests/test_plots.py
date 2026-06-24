"""Tests for lcf.plots: figures build and save headless."""

import numpy as np
import pytest
from matplotlib.figure import Figure

from lcf import cycles, fits, metrics, pipeline, plots
from lcf.ingest import from_timeseries
from lcf.models import TestMetadata


@pytest.fixture
def fitted(sae1137):
    g = sae1137
    return fits.fit_strain_life(
        g.total_strain_amp, g.stress_amp, g.reversals, g.ref["E_nominal"],
        plastic_strain_amp=g.plastic_strain_amp, min_plastic_strain=5e-4,
    ), g


def _analyzed(s):
    meta = TestMetadata(name="syn", area=s.area, E=200000.0, already_true=True)
    test = from_timeseries(s.time, s.strain, s.force, metadata=meta)
    rc = cycles.reduce_cycles(test)
    pcm = metrics.per_cycle_metrics(test, rc)
    return test, rc, pcm


def test_strain_life_plot_saves(fitted, tmp_path):
    fit, g = fitted
    fig = plots.plot_strain_life(fit, reversals=g.reversals, total_strain_amp=g.total_strain_amp)
    assert isinstance(fig, Figure)
    p = plots.savefig(fig, tmp_path / "sl.png")
    assert p.exists() and p.stat().st_size > 0


def test_coffin_manson_and_basquin_plots(fitted, tmp_path):
    fit, g = fitted
    f1 = plots.plot_coffin_manson(g.plastic_strain_amp, g.reversals, fit.coffin_manson)
    f2 = plots.plot_basquin(g.stress_amp, g.reversals, fit.basquin)
    assert plots.savefig(f1, tmp_path / "cm.png").stat().st_size > 0
    assert plots.savefig(f2, tmp_path / "bq.png").stat().st_size > 0


def test_cyclic_stress_strain_plot(fitted, tmp_path):
    fit, g = fitted
    assert fit.ramberg_osgood is not None
    fig = plots.plot_cyclic_stress_strain(fit.ramberg_osgood, fit.E, sigma_max=600.0)
    assert plots.savefig(fig, tmp_path / "ro.png").stat().st_size > 0


def test_hysteresis_peak_valley_energy_plots(synthetic_cyclic, tmp_path):
    test, rc, pcm = _analyzed(synthetic_cyclic)
    f1 = plots.plot_hysteresis(test, rc, cycles=[1, rc.half_life_cycle])
    f2 = plots.plot_peak_valley(pcm)
    f3 = plots.plot_energy(pcm)
    for name, f in [("hys", f1), ("pv", f2), ("en", f3)]:
        assert isinstance(f, Figure)
        assert plots.savefig(f, tmp_path / f"{name}.png").stat().st_size > 0
