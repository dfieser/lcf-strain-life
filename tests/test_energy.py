"""Tests for lcf.energy: loop area and the Halford-Morrow energy-life model."""

import numpy as np
import pytest

from lcf import energy


def _masing_loop(stress_range, E, K, n, npts=4000):
    """Dense polygon of a Masing hysteresis loop from the cyclic constants."""
    sa = stress_range / 2.0
    ea = sa / E + (sa / K) ** (1.0 / n)
    dsig = np.linspace(0.0, stress_range, npts)
    deps = dsig / E + 2.0 * (dsig / (2.0 * K)) ** (1.0 / n)
    up_x, up_y = -ea + deps, -sa + dsig
    dn_x, dn_y = ea - deps, sa - dsig
    return np.concatenate([up_x, dn_x]), np.concatenate([up_y, dn_y])


def test_shoelace_rectangle():
    # unit-ish rectangle: width 0.01 (strain) x height 200 (stress) = 2.0
    x = np.array([0.0, 0.01, 0.01, 0.0])
    y = np.array([0.0, 0.0, 200.0, 200.0])
    assert energy.loop_area(x, y) == pytest.approx(2.0)


def test_shoelace_sign_direction_independent():
    x = np.array([0.0, 0.01, 0.01, 0.0])
    y = np.array([0.0, 0.0, 200.0, 200.0])
    a_cw = energy.shoelace_area(x, y)
    a_ccw = energy.shoelace_area(x[::-1], y[::-1])
    assert a_cw == pytest.approx(-a_ccw)
    assert energy.loop_area(x, y) == pytest.approx(abs(a_cw))


def test_ellipse_area_matches_analytic():
    eps_a, sig_a, delta = 0.01, 400.0, 0.35
    t = np.linspace(0.0, 2.0 * np.pi, 2000, endpoint=False)
    x = eps_a * np.cos(t)
    y = sig_a * np.cos(t - delta)
    expected = np.pi * eps_a * sig_a * np.sin(delta)
    assert energy.loop_area(x, y) == pytest.approx(expected, rel=1e-4)


def test_degenerate_returns_zero():
    assert energy.loop_area([0.0, 1.0], [0.0, 1.0]) == 0.0  # < 3 points
    # collinear points enclose no area
    assert energy.loop_area([0.0, 1.0, 2.0], [0.0, 2.0, 4.0]) == pytest.approx(0.0)


def test_shape_mismatch_raises():
    with pytest.raises(ValueError):
        energy.shoelace_area([0.0, 1.0], [0.0, 1.0, 2.0])


# ---------------------------------------------- Halford-Morrow energy-life


@pytest.mark.parametrize("n_prime", [0.162, 0.2996, 0.2502])
def test_masing_energy_matches_numeric_loop_area(n_prime):
    """Eq. 3 of Zhang 2013 is exact for a Masing loop.

    The n' values are the three temperatures of Zhang, Zuo, and Liu, FFEMS
    36 (2013) 623-630. The closed-loop area integrates the plastic work, so
    the shoelace area of a dense Masing loop must match the closed form.
    """
    E, K = 73000.0, 600.0
    stress_range = 300.0
    x, y = _masing_loop(stress_range, E, K, n_prime)
    numeric = energy.loop_area(x, y)
    plastic_range = 2.0 * (stress_range / (2.0 * K)) ** (1.0 / n_prime)
    closed_form = energy.masing_plastic_energy(
        stress_range, plastic_range, n_prime
    )
    assert numeric == pytest.approx(closed_form, rel=5e-3)


def test_fit_energy_life_round_trip():
    """Exact power-law data recovers the Zhang Table 5 constants at 200 C."""
    W_f, beta = 5.96, -0.40
    rev = np.array([2e2, 1e3, 5e3, 2e4, 1e5])
    dwp = W_f * rev**beta
    fit = energy.fit_energy_life(dwp, rev)
    assert fit.W_f == pytest.approx(W_f, rel=1e-6)
    assert fit.beta == pytest.approx(beta, rel=1e-6)
    assert fit.r_squared == pytest.approx(1.0)
    assert fit.n_points == 5


def test_predict_life_energy_inverts_the_relation():
    W_f, beta = 18.94, -0.46   # Zhang Table 5, 400 C
    two_nf = 4.0e3
    dwp = W_f * two_nf**beta
    assert energy.predict_life_energy(dwp, W_f, beta) == pytest.approx(two_nf)


def test_energy_life_guards():
    with pytest.raises(ValueError):
        energy.predict_life_energy(0.0, 5.96, -0.4)
    with pytest.raises(ValueError):
        energy.predict_life_energy(1.0, -1.0, -0.4)
    with pytest.raises(ValueError):
        energy.predict_life_energy(1.0, 5.96, 0.4)
    with pytest.raises(ValueError):
        energy.masing_plastic_energy(-1.0, 0.01, 0.2)
    with pytest.raises(ValueError):
        energy.masing_plastic_energy(300.0, 0.01, 1.2)
