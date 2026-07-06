"""Service and MCP exposure of capabilities added after Phase 2.

Covers the multiaxial parameter evaluation, the array-based critical-plane
search, the frequency-modified Coffin-Manson tool, the Corten-Dolan damage
rule at the service boundary, and PNG plot rendering from stored results.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from lcf import damage, hightemp, multiaxial
from lcf.service import LcfService


@pytest.fixture()
def svc(tmp_path):
    return LcfService(tmp_path / "store")


# --- multiaxial parameter evaluation -----------------------------------------
def test_multiaxial_parameter_matches_library(svc):
    expected = multiaxial.fatemi_socie(0.004, 300.0, sigma_y=500.0, k=0.3)
    out = svc.compute_multiaxial_parameter(
        "fatemi_socie", shear_strain_amp=0.004, sigma_n_max=300.0, sigma_y=500.0
    )
    assert out["value"] == pytest.approx(expected)

    expected = multiaxial.brown_miller(0.004, 0.002, S=1.0)
    out = svc.compute_multiaxial_parameter(
        "brown_miller", shear_strain_amp=0.004, normal_strain_amp=0.002
    )
    assert out["value"] == pytest.approx(expected)

    expected = multiaxial.swt_multiaxial(400.0, 0.003)
    out = svc.compute_multiaxial_parameter(
        "swt", sigma_n_max=400.0, normal_strain_amp=0.003
    )
    assert out["value"] == pytest.approx(expected)


def test_multiaxial_von_mises_uniaxial_recovery(svc):
    # uniaxial strain with incompressible transverse strains returns eps
    out = svc.compute_multiaxial_parameter(
        "von_mises", eps_x=0.004, eps_y=-0.002, eps_z=-0.002
    )
    assert out["value"] == pytest.approx(0.004)


def test_multiaxial_parameter_missing_inputs_raise(svc):
    with pytest.raises(ValueError, match="fatemi_socie requires"):
        svc.compute_multiaxial_parameter("fatemi_socie", shear_strain_amp=0.004)
    with pytest.raises(ValueError, match="parameter must be"):
        svc.compute_multiaxial_parameter("dang_van")


# --- critical-plane search from arrays ---------------------------------------
def test_search_critical_plane_finds_max(svc):
    angles = list(np.arange(0.0, 180.0, 15.0))
    # peak shear strain at 45 degrees
    gamma = [0.004 * math.sin(math.radians(2 * a)) for a in angles]
    sn = [100.0] * len(angles)
    out = svc.search_critical_plane(
        "fatemi_socie", angles, gamma, sigma_n_max=sn, sigma_y=500.0
    )
    assert out["critical_angle"] == pytest.approx(45.0)
    assert out["max_parameter"] == pytest.approx(
        multiaxial.fatemi_socie(0.004, 100.0, sigma_y=500.0, k=0.3), rel=1e-6
    )
    assert len(out["values"]) == len(angles)


def test_search_critical_plane_misaligned_raises(svc):
    with pytest.raises(ValueError, match="one value per angle"):
        svc.search_critical_plane(
            "brown_miller", [0.0, 45.0, 90.0], [0.004, 0.003],
            normal_strain_amp=[0.001, 0.001, 0.001],
        )


# --- frequency-modified Coffin-Manson ----------------------------------------
def test_frequency_modified_life_round_trip(svc):
    out = svc.compute_frequency_modified_life(
        0.002, 0.5, -0.6, frequency=0.1, k=0.7
    )
    # invert back through the library form
    back = hightemp.frequency_modified_plastic_strain(
        out["reversals"], 0.5, -0.6, frequency=0.1, k=0.7
    )
    assert back == pytest.approx(0.002, rel=1e-9)
    # at the reference frequency the coefficient is unchanged
    ref = svc.compute_frequency_modified_life(0.002, 0.5, -0.6, frequency=1.0, k=0.7)
    assert ref["modified_coefficient"] == pytest.approx(0.5)


# --- Corten-Dolan through the service ----------------------------------------
def test_compute_damage_corten_dolan_matches_library(svc):
    counts = [100.0, 400.0]
    stresses = [500.0, 300.0]
    lives = [1e4, 1e6]
    expected = damage.corten_dolan(counts, stresses, lives, d=4.8)
    out = svc.compute_damage(counts, lives, rule="corten_dolan",
                             stresses=stresses, d_exponent=4.8)
    assert out["cycles_to_failure"] == pytest.approx(expected.cycles_to_failure)


def test_compute_damage_corten_dolan_requires_inputs(svc):
    with pytest.raises(ValueError, match="corten_dolan requires"):
        svc.compute_damage([1.0], [1e5], rule="corten_dolan")
    with pytest.raises(ValueError, match="rule must be"):
        svc.compute_damage([1.0], [1e5], rule="haibach")


# --- plot rendering from stored results --------------------------------------
def test_render_plot_rainflow(svc, tmp_path):
    svc.count_rainflow("t1", [-2.0, 1.0, -3.0, 5.0, -1.0, 3.0, -4.0, 4.0, -2.0])
    out = svc.render_plot("t1", "rainflow_histogram")
    from pathlib import Path
    assert Path(out["png_path"]).exists()
    rec = svc.recall("t1", "plot_rainflow_histogram")
    assert rec is not None and rec["png_path"] == out["png_path"]


def test_render_plot_per_cycle_kinds(svc):
    # ten triangular cycles, engineering input
    n_cycles = 10
    time, strain, force = [], [], []
    t = 0.0
    for _ in range(n_cycles):
        for s in (0.0, 0.01, 0.0, -0.01):
            time.append(t)
            strain.append(s)
            force.append(s * 3e5)
            t += 0.25
    svc.analyze_timeseries("t2", time, strain, force, area=10.0, E=200000.0,
                           already_true=True)
    from pathlib import Path
    for kind in ("peak_valley", "energy"):
        out = svc.render_plot("t2", kind)
        assert Path(out["png_path"]).exists()


def test_render_plot_strain_life(svc):
    svc.fit_strain_life(
        total_strain_amp=[0.009, 0.007, 0.005, 0.003, 0.002],
        stress_amp=[553.0, 522.0, 464.0, 405.0, 350.0],
        reversals=[4234.0, 7398.0, 14768.0, 77104.0, 437498.0],
        E=208000.0,
        material="m1",
    )
    out = svc.render_plot("m1", "strain_life")
    from pathlib import Path
    assert Path(out["png_path"]).exists()


def test_render_plot_missing_data_raises(svc):
    with pytest.raises(ValueError, match="no rainflow table"):
        svc.render_plot("nope", "rainflow_histogram")
    with pytest.raises(ValueError, match="kind must be"):
        svc.render_plot("nope", "pie_chart")
