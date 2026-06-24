"""Tests for lcf.energy: shoelace loop area."""

import numpy as np
import pytest

from lcf import energy


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
