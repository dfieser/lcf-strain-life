"""Tests for lcf.meanstress: Morrow, modified Morrow, SWT, Walker."""

import numpy as np
import pytest

from lcf import meanstress as ms


# --- equivalent fully-reversed stress: reductions ---------------------------
@pytest.mark.parametrize("model", ["none", "morrow", "swt", "walker"])
def test_zero_mean_reduces_to_amplitude(model):
    sa = np.array([200.0, 300.0, 450.0])
    kw = {}
    if model == "morrow":
        kw["sigma_f"] = 1000.0
    if model == "walker":
        kw["gamma"] = 0.6
    sar = ms.equivalent_fully_reversed_stress(sa, 0.0, model, **kw)
    np.testing.assert_allclose(sar, sa, rtol=1e-12)


def test_walker_half_equals_swt():
    sa, sm = 300.0, 150.0
    swt = ms.equivalent_fully_reversed_stress(sa, sm, "swt")
    walker = ms.equivalent_fully_reversed_stress(sa, sm, "walker", gamma=0.5)
    assert walker == pytest.approx(swt)


def test_swt_is_geometric_mean():
    sa, sm = 300.0, 100.0
    smax = sa + sm
    sar = ms.equivalent_fully_reversed_stress(sa, sm, "swt")
    assert sar == pytest.approx(np.sqrt(smax * sa))


def test_morrow_tensile_mean_increases_equivalent():
    sa = 300.0
    sar_tension = ms.equivalent_fully_reversed_stress(sa, 100.0, "morrow", sigma_f=1000.0)
    sar_compression = ms.equivalent_fully_reversed_stress(sa, -100.0, "morrow", sigma_f=1000.0)
    # tensile mean -> larger equivalent amplitude -> more damaging
    assert sar_tension > sa > sar_compression


def test_morrow_requires_sigma_f():
    with pytest.raises(ValueError, match="sigma_f"):
        ms.equivalent_fully_reversed_stress(300.0, 100.0, "morrow")


def test_walker_requires_gamma():
    with pytest.raises(ValueError, match="gamma"):
        ms.equivalent_fully_reversed_stress(300.0, 100.0, "walker")


def test_modified_morrow_has_no_equivalent_stress():
    with pytest.raises(ValueError, match="modified_morrow"):
        ms.equivalent_fully_reversed_stress(300.0, 100.0, "modified_morrow")


def test_morrow_raises_when_mean_exceeds_sigma_f():
    # H3: sigma_m >= sigma_f -> inf/negative, must raise instead
    with pytest.raises(ValueError, match="sigma_f"):
        ms.equivalent_fully_reversed_stress(100.0, 1000.0, "morrow", sigma_f=1000.0)
    with pytest.raises(ValueError, match="sigma_f"):
        ms.equivalent_fully_reversed_stress(100.0, 1200.0, "morrow", sigma_f=1000.0)


def test_modified_morrow_raises_when_mean_exceeds_sigma_f():
    # H5: factor <= 0 -> complex result, must raise instead
    with pytest.raises(ValueError, match="sigma_f"):
        ms.modified_morrow_strain_life(
            [1e3], sigma_f=1000.0, b=-0.09, eps_f=0.5, c=-0.6, E=2e5, mean_stress=1200.0
        )


# --- Walker gamma -----------------------------------------------------------
def test_walker_gamma_steel():
    # Dowling et al. 2009 / Dowling 4th ed. Eq. 9.20: gamma = 0.8818 - 2.00e-4 * sigma_u
    assert ms.walker_gamma_steel(600.0) == pytest.approx(0.8818 - 0.12)
    assert ms.walker_gamma_steel(0.0) == pytest.approx(0.8818)


# --- strain-life curve forms ------------------------------------------------
def test_morrow_strain_life_reduces_to_base_at_zero_mean():
    params = dict(sigma_f=1000.0, b=-0.09, eps_f=0.5, c=-0.6, E=200000.0)
    tn = np.array([1e2, 1e3, 1e4, 1e5])
    base = (params["sigma_f"] / params["E"]) * tn ** params["b"] + params["eps_f"] * tn ** params["c"]
    morrow = ms.morrow_strain_life(tn, mean_stress=0.0, **params)
    np.testing.assert_allclose(morrow, base, rtol=1e-12)


def test_morrow_tensile_mean_lowers_strain_life_curve():
    params = dict(sigma_f=1000.0, b=-0.09, eps_f=0.5, c=-0.6, E=200000.0)
    tn = np.array([1e3, 1e4, 1e5])
    base = ms.morrow_strain_life(tn, mean_stress=0.0, **params)
    tensile = ms.morrow_strain_life(tn, mean_stress=150.0, **params)
    # tensile mean reduces the allowable strain amplitude at a given life
    assert np.all(tensile < base)


def test_modified_morrow_reduces_at_zero_mean():
    params = dict(sigma_f=1000.0, b=-0.09, eps_f=0.5, c=-0.6, E=200000.0)
    tn = np.array([1e3, 1e4, 1e5])
    base = (params["sigma_f"] / params["E"]) * tn ** params["b"] + params["eps_f"] * tn ** params["c"]
    mm = ms.modified_morrow_strain_life(tn, mean_stress=0.0, **params)
    np.testing.assert_allclose(mm, base, rtol=1e-12)


def test_swt_parameter_curve_positive_and_decreasing():
    params = dict(sigma_f=1000.0, b=-0.09, eps_f=0.5, c=-0.6, E=200000.0)
    tn = np.array([1e2, 1e3, 1e4, 1e5, 1e6])
    p = ms.swt_parameter_curve(tn, **params)
    assert np.all(p > 0)
    assert np.all(np.diff(p) < 0)  # damage parameter decreases with life


def test_swt_parameter_value():
    assert ms.swt_parameter(500.0, 0.01) == pytest.approx(5.0)
