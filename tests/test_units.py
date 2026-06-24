"""Tests for lcf.units: engineering<->true conversions and unit helpers."""

import math

import numpy as np
import pytest

from lcf import units


def test_stress_from_force_scalar():
    # 1000 N over 10 mm^2 = 100 MPa
    assert units.stress_from_force(1000.0, 10.0) == pytest.approx(100.0)


def test_stress_from_force_array():
    out = units.stress_from_force([100.0, 200.0], 10.0)
    np.testing.assert_allclose(out, [10.0, 20.0])


def test_stress_from_force_rejects_nonpositive_area():
    with pytest.raises(ValueError):
        units.stress_from_force(100.0, 0.0)


def test_eng_to_true_strain_known_value():
    # ln(1.01) for 1% engineering strain
    assert units.eng_to_true_strain(0.01) == pytest.approx(math.log(1.01))


def test_eng_to_true_strain_zero():
    assert units.eng_to_true_strain(0.0) == pytest.approx(0.0)


def test_eng_to_true_stress_known_value():
    # sigma_eng=500 MPa at 2% strain -> 500*1.02 = 510 MPa
    assert units.eng_to_true_stress(500.0, 0.02) == pytest.approx(510.0)


def test_true_strain_roundtrip():
    eps_eng = np.array([-0.5, -0.01, 0.0, 0.01, 0.05, 0.2])
    eps_true = units.eng_to_true_strain(eps_eng)
    back = units.true_to_eng_strain(eps_true)
    np.testing.assert_allclose(back, eps_eng, atol=1e-12)


def test_true_stress_roundtrip():
    eps_eng = np.array([0.0, 0.01, 0.05, 0.2])
    sig_eng = np.array([100.0, 300.0, 450.0, 600.0])
    eps_true = units.eng_to_true_strain(eps_eng)
    sig_true = units.eng_to_true_stress(sig_eng, eps_eng)
    back = units.true_to_eng_stress(sig_true, eps_true)
    np.testing.assert_allclose(back, sig_eng, atol=1e-9)


def test_true_strain_rejects_unphysical():
    with pytest.raises(ValueError):
        units.eng_to_true_strain(-1.0)
    with pytest.raises(ValueError):
        units.eng_to_true_stress(100.0, -1.5)


def test_percent_fraction_roundtrip():
    x = np.array([0.001, 0.005, 0.015])
    np.testing.assert_allclose(units.percent_to_fraction(units.fraction_to_percent(x)), x)


def test_pressure_unit_conversions():
    assert units.mpa_to_pa(1.0) == pytest.approx(1.0e6)
    assert units.pa_to_mpa(1.0e6) == pytest.approx(1.0)
    assert units.gpa_to_mpa(208.0) == pytest.approx(208000.0)
    assert units.mpa_to_gpa(208000.0) == pytest.approx(208.0)


def test_energy_convention_mpa_fraction_gives_mjm3():
    """A rectangular loop of 1 MPa x 1 (fraction) encloses area 1 -> 1 MJ/m^3.

    This documents the internal-unit convention (ADR-0002 / units module docstring):
    integrating MPa over dimensionless strain yields MJ/m^3 with no extra factor.
    """
    # closed rectangular path in (strain, stress): width 0.01, height 200 MPa
    strain = np.array([0.0, 0.01, 0.01, 0.0, 0.0])
    stress = np.array([0.0, 0.0, 200.0, 200.0, 0.0])
    # shoelace area
    area = 0.5 * abs(
        np.sum(strain[:-1] * stress[1:] - strain[1:] * stress[:-1])
    )
    assert area == pytest.approx(0.01 * 200.0)  # = 2.0 MJ/m^3
