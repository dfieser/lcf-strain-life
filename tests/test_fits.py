"""Tests for lcf.fits: including golden-value validation against SAE 1137.

Golden source: Williams, Lee & Rilly, *Int. J. Fatigue* 25 (2003) 427-436
(see tests/conftest.py and dev/docs/design/IMPLEMENTATION_REFERENCE.md §11).
"""

import numpy as np
import pytest

from lcf import fits


# --- power-law primitive ----------------------------------------------------
def test_power_law_fit_recovers_known():
    x = np.array([1.0, 10.0, 100.0, 1000.0])
    y = 5.0 * x**(-0.3)
    pl = fits.power_law_fit(x, y)
    assert pl.coeff == pytest.approx(5.0, rel=1e-6)
    assert pl.exponent == pytest.approx(-0.3, rel=1e-6)
    assert pl.r_squared == pytest.approx(1.0, abs=1e-9)


def test_power_law_filters_nonpositive():
    x = np.array([1.0, 10.0, -5.0, 100.0, np.nan])
    y = np.array([5.0, 2.5, 1.0, 1.25, 1.0])
    pl = fits.power_law_fit(x, y)
    assert pl.n_points == 3  # negative and NaN dropped


def test_power_law_too_few_points():
    with pytest.raises(ValueError):
        fits.power_law_fit([1.0], [2.0])


# --- golden: SAE 1137 -------------------------------------------------------
def test_basquin_golden(sae1137):
    g = sae1137
    bq = fits.fit_basquin(g.stress_amp, g.reversals)
    # elastic branch uses all points, b is a small negative for steel
    assert -0.13 < bq.b < -0.06
    assert 900.0 < bq.sigma_f < 1300.0
    assert bq.r_squared > 0.95


def test_coffin_manson_golden_lcf_regime(sae1137):
    g = sae1137
    # fit plastic branch over the LCF regime (exclude near-runout low-plastic pts)
    cm = fits.fit_coffin_manson(
        g.plastic_strain_amp, g.reversals, min_plastic_strain=5e-4
    )
    assert cm.c == pytest.approx(g.ref["c"], abs=0.03)        # published -0.6207
    assert cm.eps_f == pytest.approx(g.ref["eps_f"], rel=0.15)  # published 1.104
    assert cm.r_squared > 0.99


def test_coffin_manson_allpoints_is_worse(sae1137):
    """Documents the finding: including near-runout points degrades the plastic fit."""
    g = sae1137
    cm_all = fits.fit_coffin_manson(g.plastic_strain_amp, g.reversals)
    cm_lcf = fits.fit_coffin_manson(g.plastic_strain_amp, g.reversals, min_plastic_strain=5e-4)
    assert cm_lcf.r_squared > cm_all.r_squared
    assert abs(cm_lcf.c - g.ref["c"]) < abs(cm_all.c - g.ref["c"])


def test_transition_life_golden(sae1137):
    g = sae1137
    f = fits.fit_strain_life(
        g.total_strain_amp, g.stress_amp, g.reversals, g.ref["E_nominal"],
        plastic_strain_amp=g.plastic_strain_amp, min_plastic_strain=5e-4,
    )
    # published ~22,000 reversals
    assert f.transition_reversals == pytest.approx(g.ref["transition_reversals"], rel=0.25)


def test_full_fit_golden_consistency(sae1137):
    g = sae1137
    f = fits.fit_strain_life(
        g.total_strain_amp, g.stress_amp, g.reversals, g.ref["E_nominal"],
        plastic_strain_amp=g.plastic_strain_amp, min_plastic_strain=5e-4,
    )
    assert f.ramberg_osgood is not None
    assert f.consistency is not None
    # The consistency check is a diagnostic: n_from_bc must equal b/c exactly,
    # and both relative differences must be finite. Whether the dataset is Masing
    # (masing_ok True/False) is an *output*, not an assumption.
    c = f.consistency
    assert c.n_from_bc == pytest.approx(f.basquin.b / f.coffin_manson.c)
    assert np.isfinite(c.n_rel_diff) and np.isfinite(c.K_rel_diff)
    assert isinstance(c.masing_ok, bool)


def test_computed_plastic_matches_published(sae1137):
    """Validate the computed plastic-strain identity Δε_p/2 = Δε_t/2 − Δσ/(2E)."""
    g = sae1137
    computed = g.total_strain_amp - g.stress_amp / g.E  # per-test E
    np.testing.assert_allclose(computed, g.plastic_strain_amp, atol=2e-5)


# --- transition + consistency primitives ------------------------------------
def test_transition_requires_b_ne_c():
    with pytest.raises(ValueError):
        fits.transition_reversals(1000.0, -0.1, 1.0, -0.1, 200000.0)


def test_transition_requires_positive_params():
    # M2: negative sigma_f / eps_f would give a complex result -> must raise
    with pytest.raises(ValueError, match="positive"):
        fits.transition_reversals(-1000.0, -0.1, 1.0, -0.6, 200000.0)
    with pytest.raises(ValueError, match="positive"):
        fits.transition_reversals(1000.0, -0.1, -1.0, -0.6, 200000.0)


def test_consistency_handles_degenerate_c_zero():
    # M1: c == 0 -> undefined b/c, return masing_ok False with NaN, not raise
    bq = fits.BasquinFit(sigma_f=1000.0, b=-0.09, r_squared=1.0, n_points=5)
    cm = fits.CoffinMansonFit(eps_f=0.5, c=0.0, r_squared=1.0, n_points=5)
    ro = fits.RambergOsgoodFit(K=1200.0, n=0.15, r_squared=1.0, n_points=5)
    chk = fits.check_consistency(bq, cm, ro)
    assert chk.masing_ok is False
    assert chk.n_from_bc != chk.n_from_bc  # NaN


def test_coffin_manson_threshold_excludes_too_many():
    # M5: clear error mentioning the threshold
    with pytest.raises(ValueError, match="min_plastic_strain"):
        fits.fit_coffin_manson(
            [1e-5, 2e-5, 3e-5], [1e4, 1e5, 1e6], min_plastic_strain=1e-3
        )


def test_nonlinear_refinement_runs(sae1137):
    g = sae1137
    f = fits.fit_strain_life(
        g.total_strain_amp, g.stress_amp, g.reversals, g.ref["E_nominal"],
        plastic_strain_amp=g.plastic_strain_amp, min_plastic_strain=5e-4,
        refine_nonlinear=True,
    )
    assert "sigma_f" in f.refined and "c" in f.refined
    # refined exponents stay physically negative
    assert f.refined["b"] < 0 and f.refined["c"] < 0
