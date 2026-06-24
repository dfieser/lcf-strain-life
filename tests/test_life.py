"""Tests for lcf.life — model curves and life inversion."""

import numpy as np
import pytest

from lcf import life
from lcf.fits import BasquinFit, CoffinMansonFit, StrainLifeFit


PARAMS = dict(sigma_f=1000.0, b=-0.09, eps_f=0.5, c=-0.6, E=200000.0)


def test_total_is_elastic_plus_plastic():
    tn = np.array([1e2, 1e3, 1e4])
    el = life.elastic_strain_life(tn, PARAMS["sigma_f"], PARAMS["b"], PARAMS["E"])
    pl = life.plastic_strain_life(tn, PARAMS["eps_f"], PARAMS["c"])
    tot = life.total_strain_life(tn, **PARAMS)
    np.testing.assert_allclose(tot, el + pl)


def test_predict_reversals_roundtrip():
    for tn_true in [5e2, 5e3, 5e4, 5e5]:
        eps = life.total_strain_life(tn_true, **PARAMS)
        tn_pred = life.predict_reversals_from_total_strain(eps, **PARAMS)
        assert tn_pred == pytest.approx(tn_true, rel=1e-4)


def test_predict_reversals_basquin_inverse():
    tn_true = 1e4
    sa = PARAMS["sigma_f"] * tn_true**PARAMS["b"]
    assert life.predict_reversals_basquin(sa, PARAMS["sigma_f"], PARAMS["b"]) == pytest.approx(
        tn_true, rel=1e-9
    )


def test_predict_reversals_swt_roundtrip():
    # build a cycle consistent with the model at a known life, zero mean
    tn_true = 2e4
    eps_a = life.total_strain_life(tn_true, **PARAMS)
    sigma_max = PARAMS["sigma_f"] * tn_true**PARAMS["b"]  # zero-mean: sigma_max = sigma_a
    tn = life.predict_reversals_swt(sigma_max, eps_a, **PARAMS)
    assert tn == pytest.approx(tn_true, rel=0.05)


def test_predict_reversals_clamps_high_strain():
    # absurdly high strain -> clamped to lower bracket
    tn = life.predict_reversals_from_total_strain(10.0, bracket=(1.0, 1e12), **PARAMS)
    assert tn == pytest.approx(1.0)


def test_predict_reversals_clamps_low_strain():
    tn = life.predict_reversals_from_total_strain(1e-9, bracket=(1.0, 1e12), **PARAMS)
    assert tn == pytest.approx(1e12)


def test_predict_reversals_basquin_rejects_negative():
    # H4: negative base must raise a clear error, not a TypeError on complex
    with pytest.raises(ValueError, match="positive"):
        life.predict_reversals_basquin(-100.0, 1000.0, -0.09)
    with pytest.raises(ValueError, match="positive"):
        life.predict_reversals_basquin(100.0, -1000.0, -0.09)


def test_predict_reversals_rejects_increasing_curve():
    # H6: degenerate fit with b>0, c>0 -> not invertible -> must raise
    bad = dict(sigma_f=1000.0, b=0.09, eps_f=0.5, c=0.6, E=200000.0)
    with pytest.raises(ValueError, match="decreasing"):
        life.predict_reversals_from_total_strain(0.005, **bad)


def test_predict_reversals_from_fit():
    fit = StrainLifeFit(
        E=200000.0,
        basquin=BasquinFit(sigma_f=1000.0, b=-0.09, r_squared=1.0, n_points=5),
        coffin_manson=CoffinMansonFit(eps_f=0.5, c=-0.6, r_squared=1.0, n_points=5),
        ramberg_osgood=None,
        transition_reversals=1e4,
        consistency=None,
    )
    eps = life.total_strain_life(3e4, **PARAMS)
    assert life.predict_reversals(fit, eps) == pytest.approx(3e4, rel=1e-3)
