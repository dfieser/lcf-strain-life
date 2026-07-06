"""Strain-life constant estimation from monotonic properties.

Golden values are hand-computed from the published formulas:

- Medians: Meggiolaro and Castro, Int. J. Fatigue 26 (2004) 463-476.
- Uniform Material Law: Baeumel and Seeger, 1990.
- Universal slopes: Manson, 1965.
- Modified universal slopes: Muralidharan and Manson, 1988.
- Hardness method: Roessle and Fatemi, Int. J. Fatigue 22 (2000) 495-511.
"""

from __future__ import annotations

import math

import pytest

from lcf import estimate
from lcf.service import LcfService


# --- medians method -----------------------------------------------------------
def test_medians_steel():
    est = estimate.estimate_medians("steel", 500.0)
    assert est.sigma_f == pytest.approx(750.0)
    assert est.b == pytest.approx(-0.09)
    assert est.eps_f == pytest.approx(0.45)
    assert est.c == pytest.approx(-0.59)
    assert est.n == pytest.approx(0.15)
    assert est.warnings == []
    assert "Meggiolaro" in est.citation


def test_medians_aluminum():
    est = estimate.estimate_medians("aluminum", 300.0)
    assert est.sigma_f == pytest.approx(570.0)
    assert est.b == pytest.approx(-0.11)
    assert est.eps_f == pytest.approx(0.28)
    assert est.c == pytest.approx(-0.66)


def test_medians_small_sample_classes_warn():
    for cls in ("titanium", "cast_iron", "nickel"):
        est = estimate.estimate_medians(cls, 900.0)
        assert any("small sample" in w for w in est.warnings)


def test_medians_rejects_unknown_class_and_bad_su():
    with pytest.raises(ValueError, match="material_class"):
        estimate.estimate_medians("wood", 500.0)
    with pytest.raises(ValueError, match="Su"):
        estimate.estimate_medians("steel", -1.0)


# --- uniform material law ------------------------------------------------------
def test_uml_steel_low_strength():
    # Su/E = 0.0025 <= 0.003, so psi = 1
    est = estimate.estimate_uniform_material_law("steel", 500.0, 200000.0)
    assert est.sigma_f == pytest.approx(750.0)
    assert est.b == pytest.approx(-0.087)
    assert est.eps_f == pytest.approx(0.59)
    assert est.c == pytest.approx(-0.58)
    assert est.K == pytest.approx(825.0)
    assert est.n == pytest.approx(0.15)


def test_uml_steel_high_strength_psi():
    # Su/E = 0.005, psi = 1.375 - 125*0.005 = 0.75
    est = estimate.estimate_uniform_material_law("steel", 1000.0, 200000.0)
    assert est.eps_f == pytest.approx(0.59 * 0.75)


def test_uml_steel_invalid_near_2200():
    # Su/E = 0.011, psi = 0, the law is invalid
    with pytest.raises(ValueError, match="2.2 GPa"):
        estimate.estimate_uniform_material_law("steel", 2200.0, 200000.0)


def test_uml_aluminum_titanium():
    est = estimate.estimate_uniform_material_law("aluminum_titanium", 300.0, 71000.0)
    assert est.sigma_f == pytest.approx(501.0)
    assert est.b == pytest.approx(-0.095)
    assert est.eps_f == pytest.approx(0.35)
    assert est.c == pytest.approx(-0.69)
    assert est.K is None


# --- universal slopes -----------------------------------------------------------
def test_universal_slopes():
    est = estimate.estimate_universal_slopes(500.0, 200000.0, 0.5)
    assert est.sigma_f == pytest.approx(950.0)
    assert est.b == pytest.approx(-0.12)
    assert est.eps_f == pytest.approx(0.76 * math.log(2.0) ** 0.6)
    assert est.c == pytest.approx(-0.6)
    assert est.warnings  # carries the accuracy caveat


def test_universal_slopes_rejects_bad_ra():
    for ra in (0.0, 1.0, -0.2, 1.5):
        with pytest.raises(ValueError, match="RA"):
            estimate.estimate_universal_slopes(500.0, 200000.0, ra)


# --- modified universal slopes ---------------------------------------------------
def test_modified_universal_slopes():
    est = estimate.estimate_modified_universal_slopes(500.0, 200000.0, 0.5)
    # hand-computed: 0.623 * 200000 * 0.0025**0.832 = 852.5 MPa (about)
    assert est.sigma_f == pytest.approx(0.623 * 200000.0 * 0.0025**0.832)
    assert est.sigma_f == pytest.approx(852.0, rel=0.01)
    expected_eps = 0.0196 * 0.0025**-0.53 * math.log(2.0) ** 0.155
    assert est.eps_f == pytest.approx(expected_eps)
    assert est.eps_f == pytest.approx(0.443, rel=0.01)
    assert est.b == pytest.approx(-0.09)
    assert est.c == pytest.approx(-0.56)


# --- hardness method -------------------------------------------------------------
def test_hardness_method_golden():
    est = estimate.estimate_hardness_method(200.0, 200000.0)
    assert est.sigma_f == pytest.approx(4.25 * 200.0 + 225.0)
    assert est.eps_f == pytest.approx(
        (0.32 * 200.0**2 - 487.0 * 200.0 + 191000.0) / 200000.0
    )
    assert est.eps_f == pytest.approx(0.532)
    assert est.b == pytest.approx(-0.09)
    assert est.c == pytest.approx(-0.56)


def test_hardness_out_of_range_warns():
    est = estimate.estimate_hardness_method(120.0, 200000.0)
    assert any("150 to 700" in w for w in est.warnings)


# --- dispatcher and service ------------------------------------------------------
def test_dispatcher_routes_and_validates():
    est = estimate.estimate_strain_life_constants(
        "medians", material_class="steel", Su=500.0
    )
    assert est.method == "medians"
    with pytest.raises(ValueError, match="requires Su"):
        estimate.estimate_strain_life_constants("medians")
    with pytest.raises(ValueError, match="method must be"):
        estimate.estimate_strain_life_constants("ong", Su=500.0)


def test_service_estimate_saves_and_returns_citation(tmp_path):
    svc = LcfService(tmp_path / "store")
    out = svc.estimate_constants(
        "uniform_material_law", material_class="steel", Su=500.0, E=200000.0,
        material="mat-x",
    )
    assert out["citation"].startswith("Baeumel")
    assert out["sigma_f"] == pytest.approx(750.0)
    rec = svc.recall("mat-x", "estimated_constants")
    assert rec is not None
    assert rec["value"]["eps_f"] == pytest.approx(0.59)


def test_estimates_feed_life_prediction(tmp_path):
    # the estimated constants must plug straight into the life solver
    from lcf import predict_reversals_from_total_strain

    est = estimate.estimate_medians("steel", 500.0)
    two_nf = predict_reversals_from_total_strain(
        0.004, est.sigma_f, est.b, est.eps_f, est.c, 200000.0
    )
    assert two_nf > 0 and math.isfinite(two_nf)
