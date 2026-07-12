"""Tests for lcf.surface, the FKM roughness factor.

Golden case from the published worked example (quadco.engineering, FKM
method): steel, Rm 600 MPa, Rz 100 micrometres -> K_R = 0.79.
"""

from __future__ import annotations

import math

import pytest

from lcf import surface
from lcf.service import LcfService


def test_worked_example_steel_600mpa_rz100():
    out = surface.fkm_roughness_factor(100.0, 600.0, material_group="steel")
    assert out["K_R"] == pytest.approx(0.79, abs=0.005)
    assert out["K_R"] == pytest.approx(1 - 0.22 * 2.0 * 0.47712125, rel=1e-6)


def test_polished_surface_caps_at_one():
    out = surface.fkm_roughness_factor(0.5, 600.0)
    assert out["K_R"] == 1.0
    assert any("capped" in n for n in out["notes"])


def test_rougher_and_stronger_reduce_more():
    base = surface.fkm_roughness_factor(25.0, 500.0)["K_R"]
    rougher = surface.fkm_roughness_factor(100.0, 500.0)["K_R"]
    stronger = surface.fkm_roughness_factor(25.0, 1000.0)["K_R"]
    assert rougher < base
    assert stronger < base


def test_all_material_groups_compute():
    for group in surface.MATERIAL_GROUPS:
        out = surface.fkm_roughness_factor(50.0, 500.0, material_group=group)
        assert 0.0 < out["K_R"] <= 1.0


def test_grey_cast_iron_least_sensitive():
    steel = surface.fkm_roughness_factor(100.0, 600.0, material_group="steel")
    gg = surface.fkm_roughness_factor(100.0, 600.0,
                                      material_group="grey_cast_iron")
    assert gg["K_R"] > steel["K_R"]


def test_refusals():
    with pytest.raises(ValueError, match="material_group"):
        surface.fkm_roughness_factor(50.0, 500.0, material_group="unobtainium")
    with pytest.raises(ValueError, match="Rz"):
        surface.fkm_roughness_factor(0.0, 500.0)
    with pytest.raises(ValueError, match="Rm"):
        surface.fkm_roughness_factor(50.0, -1.0)


def test_service_exposure(tmp_path):
    svc = LcfService(tmp_path / "store")
    out = svc.compute_roughness_factor(100.0, 600.0)
    assert out["K_R"] == pytest.approx(0.79, abs=0.005)


# --------------------------------------------------------------------------- #
# FKM technological size factor (formula only, caller supplies constants)
# --------------------------------------------------------------------------- #
def test_size_factor_unity_at_and_below_reference():
    at = surface.fkm_size_factor(40.0, a_dm=0.15, d_eff_N=40.0)
    below = surface.fkm_size_factor(20.0, a_dm=0.15, d_eff_N=40.0)
    assert at["K_dm"] == 1.0
    assert below["K_dm"] == 1.0
    assert any("reference" in n for n in below["notes"])


def test_size_factor_decreases_above_reference():
    small = surface.fkm_size_factor(50.0, a_dm=0.15, d_eff_N=40.0)
    large = surface.fkm_size_factor(200.0, a_dm=0.15, d_eff_N=40.0)
    assert small["K_dm"] < 1.0
    assert large["K_dm"] < small["K_dm"]


def test_size_factor_formula_matches_closed_form():
    a, dn, d = 0.15, 40.0, 120.0
    out = surface.fkm_size_factor(d, a_dm=a, d_eff_N=dn)
    num = 1 - 0.7686 * a * math.log10(d / 7.5)
    den = 1 - 0.7686 * a * math.log10(dn / 7.5)
    assert out["K_dm"] == pytest.approx(num / den, rel=1e-12)


def test_size_factor_stamps_caller_supplied_note():
    out = surface.fkm_size_factor(80.0, a_dm=0.3, d_eff_N=100.0)
    assert any("caller-supplied" in n for n in out["notes"])


def test_size_factor_refusals():
    with pytest.raises(ValueError, match="d_eff must be positive"):
        surface.fkm_size_factor(0.0, a_dm=0.15, d_eff_N=40.0)
    with pytest.raises(ValueError, match="d_eff_N must be positive"):
        surface.fkm_size_factor(80.0, a_dm=0.15, d_eff_N=0.0)
    with pytest.raises(ValueError, match="a_dm must be non-negative"):
        surface.fkm_size_factor(80.0, a_dm=-0.1, d_eff_N=40.0)


def test_size_factor_service_exposure(tmp_path):
    from lcf.service import LcfService

    svc = LcfService(tmp_path / "store")
    out = svc.compute_size_factor(120.0, a_dm=0.3, d_eff_N=100.0)
    assert 0.0 < out["K_dm"] < 1.0
