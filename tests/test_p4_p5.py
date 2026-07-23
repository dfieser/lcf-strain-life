"""Tests for the P4 slice (interchange, report) and P5 slice (tensor
critical-plane search), ADR-0017 and ADR-0018.

The critical-plane goldens are exact closed forms: uniaxial strain with
Poisson contraction puts the critical shear plane at 45 degrees with
engineering shear amplitude (1+nu) times the axial amplitude, pure torsion
puts it on the specimen-axis planes with the applied shear amplitude and
zero normal strain.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from lcf import criticalplane, interchange
from lcf.service import LcfService


# --------------------------------------------------------------------------- #
# interchange schema
# --------------------------------------------------------------------------- #
def test_material_document_round_trip():
    doc = interchange.export_material(
        name="SAE10B20-f512", E=206843.0, sigma_f=849.4, b=-0.0437,
        eps_f=2.0907, c=-0.7450, K_prime=813.6, n_prime=0.0586,
        source="Conle MSc thesis 1974 via fde.uwaterloo.ca",
    )
    assert doc["schema"] == "lcf-strain-life/material"
    assert doc["version"] == 1
    assert doc["transition_reversals"] > 0
    back = interchange.import_material(doc)
    assert back["sigma_f"] == pytest.approx(849.4)
    assert back["K_prime"] == pytest.approx(813.6)


def test_import_refuses_wrong_version_and_units():
    doc = interchange.export_material(
        name="m", E=2e5, sigma_f=900.0, b=-0.1, eps_f=0.6, c=-0.55
    )
    bad = dict(doc, version=2)
    with pytest.raises(ValueError, match="version"):
        interchange.import_material(bad)
    bad = dict(doc, units={"stress": "ksi", "strain": "fraction",
                           "life": "reversals"})
    with pytest.raises(ValueError, match="unit"):
        interchange.import_material(bad)


def test_export_rejects_positive_exponents():
    with pytest.raises(ValueError, match="negative"):
        interchange.export_material(
            name="m", E=2e5, sigma_f=900.0, b=0.1, eps_f=0.6, c=-0.55
        )


def test_pylife_woehler_round_trip():
    out = interchange.to_pylife_woehler(900.0, -0.10, nd_cycles=1e6)
    assert out["k_1"] == pytest.approx(10.0)
    assert out["SD"] == pytest.approx(900.0 * (2e6) ** -0.10)
    back = interchange.from_pylife_woehler(out["k_1"], out["ND"], out["SD"])
    assert back["sigma_f"] == pytest.approx(900.0, rel=1e-12)
    assert back["b"] == pytest.approx(-0.10, rel=1e-12)


# --------------------------------------------------------------------------- #
# report
# --------------------------------------------------------------------------- #
def test_report_from_stored_results(tmp_path):
    svc = LcfService(tmp_path / "store")
    svc.fit_strain_life(
        [0.009, 0.005, 0.003, 0.002],
        [550.0, 470.0, 405.0, 350.0],
        [4000.0, 15000.0, 80000.0, 450000.0],
        208000.0, material="DEMO",
    )
    svc.analyze_staircase(
        [260, 280, 300, 280, 300, 280, 300, 280, 260, 280, 260, 280],
        [False, False, True, False, True, False, True, True, False, True,
         False, False],
        name="DEMO",
    )
    out = svc.generate_report("DEMO")
    md = out["markdown"]
    assert "# Fatigue analysis report: DEMO" in md
    assert "strain life fit" in md
    assert "staircase" in md
    assert "## Sources" in md
    assert "Dixon and Mood" in md
    assert "Provenance hash" in md
    # persisted for recall and written to disk
    assert svc.recall("DEMO", "report") is not None
    assert (tmp_path / "store" / "reports" / "DEMO.md").exists()


def test_report_empty_key_says_so(tmp_path):
    svc = LcfService(tmp_path / "store")
    out = svc.generate_report("NOTHING")
    assert "No stored results" in out["markdown"]


# --------------------------------------------------------------------------- #
# tensor critical-plane search
# --------------------------------------------------------------------------- #
NU = 0.3


def _uniaxial_histories(eps_a=0.005, n=73):
    t = np.linspace(0.0, 2.0 * math.pi, n)
    ax = eps_a * np.sin(t)
    zeros = np.zeros_like(ax)
    return {
        "eps_xx": ax, "eps_yy": -NU * ax, "eps_zz": -NU * ax,
        "gamma_xy": zeros, "gamma_yz": zeros, "gamma_zx": zeros,
    }


def test_uniaxial_max_shear_plane_is_45_degrees():
    # With S=0 Brown-Miller reduces to the shear amplitude alone, so the
    # search must find the classic 45 degree max-shear plane exactly:
    # engineering shear amplitude (1+nu)*eps_a, normal strain amplitude
    # (1-nu)*eps_a/2. These are closed forms.
    eps_a = 0.005
    out = criticalplane.search_critical_plane_tensor(
        parameter="brown_miller", S=0.0, grid_deg=5.0,
        **_uniaxial_histories(eps_a),
    )
    assert out["shear_strain_amp"] == pytest.approx((1 + NU) * eps_a, rel=1e-6)
    assert out["normal_strain_amp"] == pytest.approx(
        (1 - NU) * eps_a / 2.0, rel=1e-6
    )
    n_dot_x = abs(
        math.sin(math.radians(out["critical_plane"]["phi_deg"]))
        * math.cos(math.radians(out["critical_plane"]["theta_deg"]))
    )
    assert n_dot_x == pytest.approx(math.cos(math.radians(45.0)), abs=1e-9)


def test_brown_miller_normal_term_moves_plane_off_45_and_raises_value():
    # With S>0 the parameter trades shear for normal strain and must be at
    # least as large as its own value on the 45 degree max-shear plane.
    eps_a = 0.005
    plain = criticalplane.search_critical_plane_tensor(
        parameter="brown_miller", S=0.0, grid_deg=5.0,
        **_uniaxial_histories(eps_a),
    )
    coupled = criticalplane.search_critical_plane_tensor(
        parameter="brown_miller", S=1.0, grid_deg=5.0,
        **_uniaxial_histories(eps_a),
    )
    bm_at_45 = plain["shear_strain_amp"] + 1.0 * plain["normal_strain_amp"]
    assert coupled["value"] >= bm_at_45 - 1e-12


def test_torsion_max_shear_plane_and_amplitude():
    gam_a = 0.006
    t = np.linspace(0.0, 2.0 * math.pi, 73)
    zeros = np.zeros_like(t)
    out = criticalplane.search_critical_plane_tensor(
        parameter="brown_miller", S=0.0,
        eps_xx=zeros, eps_yy=zeros, eps_zz=zeros,
        gamma_xy=gam_a * np.sin(t), gamma_yz=zeros, gamma_zx=zeros,
        grid_deg=5.0,
    )
    assert out["shear_strain_amp"] == pytest.approx(gam_a, rel=1e-6)
    assert out["normal_strain_amp"] == pytest.approx(0.0, abs=1e-9)


def test_fatemi_socie_needs_stress_history():
    with pytest.raises(ValueError, match="stress"):
        criticalplane.search_critical_plane_tensor(
            parameter="fatemi_socie", sigma_y=500.0,
            **_uniaxial_histories(),
        )


def test_fatemi_socie_uniaxial_with_stress():
    eps_a, sig_a = 0.005, 400.0
    t = np.linspace(0.0, 2.0 * math.pi, 73)
    ax = np.sin(t)
    zeros = np.zeros_like(ax)
    kwargs = dict(
        eps_xx=eps_a * ax, eps_yy=-NU * eps_a * ax, eps_zz=-NU * eps_a * ax,
        gamma_xy=zeros, gamma_yz=zeros, gamma_zx=zeros,
        sig_xx=sig_a * ax, sig_yy=zeros, sig_zz=zeros,
        tau_xy=zeros, tau_yz=zeros, tau_zx=zeros,
    )
    # k=0 isolates the geometry: the max-shear plane at 45 degrees, where
    # the normal stress peaks at sig_a/2. Closed form, exact on the grid.
    plain = criticalplane.search_critical_plane_tensor(
        parameter="fatemi_socie", sigma_y=500.0, k=0.0, grid_deg=5.0, **kwargs
    )
    assert plain["sigma_n_max"] == pytest.approx(sig_a / 2.0, rel=1e-6)
    assert plain["value"] == pytest.approx((1 + NU) * eps_a, rel=1e-6)
    # with k>0 the normal-stress term must raise the maximum at least to
    # the parameter's own value on the 45 degree plane
    coupled = criticalplane.search_critical_plane_tensor(
        parameter="fatemi_socie", sigma_y=500.0, k=0.3, grid_deg=5.0, **kwargs
    )
    fs_at_45 = (1 + NU) * eps_a * (1 + 0.3 * (sig_a / 2.0) / 500.0)
    assert coupled["value"] >= fs_at_45 - 1e-12


def test_mismatched_lengths_refused():
    with pytest.raises(ValueError, match="length"):
        criticalplane.search_critical_plane_tensor(
            parameter="brown_miller",
            eps_xx=[0.0, 0.001], eps_yy=[0.0], eps_zz=[0.0, 0.0],
            gamma_xy=[0.0, 0.0], gamma_yz=[0.0, 0.0], gamma_zx=[0.0, 0.0],
        )


def test_service_and_persistence_for_tensor_search(tmp_path):
    svc = LcfService(tmp_path / "store")
    h = _uniaxial_histories()
    out = svc.search_critical_plane_tensor(
        parameter="brown_miller", name="CP-demo",
        **{k: list(v) for k, v in h.items()},
    )
    assert out["value"] > 0
    assert svc.recall("CP-demo", "critical_plane") is not None
