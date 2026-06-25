"""Tests for lcf.spectrum, the variable-amplitude life chain."""

import numpy as np
import pytest

from lcf import life, spectrum

PROPS = dict(sigma_f=1000.0, b=-0.09, eps_f=0.5, c=-0.6, E=200000.0)


def _constant_amplitude(eps_a, sigma_a, n_cycles):
    # fully reversed, n_cycles full loops, strain and stress in phase
    pts = []
    spts = []
    for _ in range(n_cycles):
        pts += [eps_a, -eps_a]
        spts += [sigma_a, -sigma_a]
    pts = [0.0] + pts
    spts = [0.0] + spts
    return np.array(pts), np.array(spts)


def test_spectrum_constant_amplitude_matches_single_cycle():
    eps_a, sigma_a, n = 0.005, 300.0, 6
    strain, stress = _constant_amplitude(eps_a, sigma_a, n)
    res = spectrum.spectrum_life(strain, stress, mean_stress_method="none", **PROPS)
    # the full cycles (amplitude eps_a) share the single-cycle solver's life.
    # The leading 0->peak ramp is one half cycle at half amplitude, as expected.
    nf_single = life.predict_reversals_from_total_strain(eps_a, **PROPS)
    full = res.cycles[np.isclose(res.cycles["amplitude"], eps_a)]
    assert len(full) >= 1
    assert np.allclose(full["reversals_to_failure"], nf_single, rtol=1e-6)


def test_spectrum_returns_finite_life():
    eps_a, sigma_a, n = 0.005, 300.0, 6
    strain, stress = _constant_amplitude(eps_a, sigma_a, n)
    res = spectrum.spectrum_life(strain, stress, **PROPS)
    assert res.blocks_to_failure > 0 and np.isfinite(res.blocks_to_failure)
    assert res.damage_per_block > 0


def test_tensile_mean_shortens_life():
    # add a tensile mean to the stress while keeping strain amplitude the same
    eps_a, n = 0.004, 5
    strain, _ = _constant_amplitude(eps_a, 0.0, n)
    # stress oscillates about a positive mean of 100 MPa
    stress = np.zeros_like(strain)
    sa = 350.0
    for i in range(1, len(strain)):
        stress[i] = 100.0 + (sa if strain[i] > 0 else -sa)
    res_none = spectrum.spectrum_life(strain, stress, mean_stress_method="none", **PROPS)
    res_swt = spectrum.spectrum_life(strain, stress, mean_stress_method="swt", **PROPS)
    res_morrow = spectrum.spectrum_life(strain, stress, mean_stress_method="morrow", **PROPS)
    # mean-stress corrections reduce life relative to ignoring the mean
    assert res_swt.cycles_to_failure < res_none.cycles_to_failure
    assert res_morrow.cycles_to_failure < res_none.cycles_to_failure


def test_spectrum_dldr_rule_runs():
    strain, stress = _constant_amplitude(0.005, 300.0, 6)
    res = spectrum.spectrum_life(strain, stress, rule="dldr", **PROPS)
    assert res.rule == "dldr"
    assert res.blocks_to_failure > 0


def test_spectrum_rejects_mismatched_lengths():
    with pytest.raises(ValueError):
        spectrum.spectrum_life([0.0, 0.01, -0.01], [0.0, 100.0], **PROPS)


def test_spectrum_unknown_method():
    strain, stress = _constant_amplitude(0.005, 300.0, 3)
    with pytest.raises(ValueError, match="mean_stress_method"):
        spectrum.spectrum_life(strain, stress, mean_stress_method="bogus", **PROPS)
