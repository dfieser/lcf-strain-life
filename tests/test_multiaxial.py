"""Tests for the multiaxial survey stub (lcf.multiaxial)."""

import numpy as np
import pytest

from lcf import multiaxial as mx


def test_fatemi_socie_zero_normal_stress():
    # with no normal stress the parameter equals the shear strain amplitude
    assert mx.fatemi_socie(0.004, 0.0, sigma_y=300.0) == pytest.approx(0.004)


def test_fatemi_socie_tensile_normal_increases_parameter():
    base = mx.fatemi_socie(0.004, 0.0, sigma_y=300.0)
    tensile = mx.fatemi_socie(0.004, 150.0, sigma_y=300.0)
    assert tensile > base


def test_fatemi_socie_requires_positive_yield():
    with pytest.raises(ValueError):
        mx.fatemi_socie(0.004, 100.0, sigma_y=0.0)


def test_brown_miller_combination():
    assert mx.brown_miller(0.004, 0.002, S=0.3) == pytest.approx(0.004 + 0.3 * 0.002)


def test_swt_multiaxial():
    assert mx.swt_multiaxial(400.0, 0.005) == pytest.approx(2.0)


def test_von_mises_uniaxial_returns_axial_strain():
    eps = 0.01
    eq = mx.von_mises_equivalent_strain(eps, -0.5 * eps, -0.5 * eps)
    assert eq == pytest.approx(eps, rel=1e-9)


def test_von_mises_pure_shear():
    # pure shear gamma -> equivalent strain gamma/sqrt(3)
    gamma = 0.01
    eq = mx.von_mises_equivalent_strain(0.0, 0.0, 0.0, gamma_xy=gamma)
    assert eq == pytest.approx(gamma / np.sqrt(3.0), rel=1e-9)


def test_critical_plane_search_finds_max():
    # a parameter peaking at 45 degrees
    res = mx.critical_plane_search(lambda a: np.sin(np.radians(2 * a)))
    assert res["critical_angle"] == pytest.approx(45.0, abs=1.0)
    assert res["max_parameter"] == pytest.approx(1.0, abs=1e-3)
