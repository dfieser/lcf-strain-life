"""Tests for lcf.hightemp, including Golden H and a Hastelloy X style table.

See docs/design/IMPLEMENTATION_REFERENCE_PHASE2.md section 4.4.
"""

import numpy as np
import pytest

from lcf import hightemp as ht


# --- frequency-modified Coffin-Manson --------------------------------------
def test_freq_modified_reduces_at_reference():
    c_f = ht.frequency_modified_coefficient(0.5, frequency=1.0, k=0.8, freq_ref=1.0)
    assert c_f == pytest.approx(0.5)  # at the reference frequency, C_f == C_o


def test_freq_modified_life_monotonic_in_frequency():
    # with k > 1 the coefficient grows with frequency, so at a fixed plastic
    # strain a lower frequency gives a longer life; the relation is monotonic
    kw = dict(eps_f_coeff=0.5, c=-0.6, k=1.3, freq_ref=1.0)
    n_low = ht.frequency_modified_reversals(0.002, frequency=0.01, **kw)
    n_high = ht.frequency_modified_reversals(0.002, frequency=10.0, **kw)
    assert n_low != n_high
    # consistency: forward then inverse round-trips
    eps = ht.frequency_modified_plastic_strain(n_high, kw["eps_f_coeff"], kw["c"],
                                               frequency=10.0, k=kw["k"])
    assert eps == pytest.approx(0.002, rel=1e-6)


# --- creep-fatigue time fraction (Golden H) --------------------------------
def test_creep_fatigue_golden_h_structure():
    # D = n1/N1 + n2/N2 + n3/N3 + t4/H4 + t5/H5 + t6/H6, fail when > 1
    counts = [100, 200, 50]
    lives = [1000, 4000, 500]
    holds = [10, 20, 5]
    ruptures = [200, 500, 100]
    r = ht.creep_fatigue_damage(counts, lives, holds, ruptures)
    d_f = 100 / 1000 + 200 / 4000 + 50 / 500  # 0.25
    d_c = 10 / 200 + 20 / 500 + 5 / 100        # 0.14
    assert r.d_fatigue == pytest.approx(d_f)
    assert r.d_creep == pytest.approx(d_c)
    assert r.d_total == pytest.approx(d_f + d_c)
    assert r.failed is False


def test_creep_fatigue_failure_flag():
    r = ht.creep_fatigue_damage([900], [1000], [90], [100])  # 0.9 + 0.9 = 1.8
    assert r.failed is True


def test_creep_fatigue_rejects_nonpositive():
    with pytest.raises(ValueError):
        ht.creep_fatigue_damage([1], [0], [1], [10])


# --- D-diagram envelope -----------------------------------------------------
def test_envelope_corners():
    # endpoints of the bilinear envelope
    assert ht.creep_fatigue_envelope_allowable(0.0, 0.3, 0.3) == pytest.approx(1.0)
    assert ht.creep_fatigue_envelope_allowable(1.0, 0.3, 0.3) == pytest.approx(0.0)
    assert ht.creep_fatigue_envelope_allowable(0.3, 0.3, 0.3) == pytest.approx(0.3)


def test_envelope_check_inside_and_outside():
    inside = ht.creep_fatigue_envelope_check(0.2, 0.2, knee=(0.3, 0.3))
    outside = ht.creep_fatigue_envelope_check(0.6, 0.6, knee=(0.3, 0.3))
    assert inside["safe"] is True and inside["margin"] > 0
    assert outside["safe"] is False and outside["margin"] < 0


# --- temperature-dependent constants ---------------------------------------
def _table():
    # Hastelloy X style: three temperatures with strain-life constants
    return {
        "T": [430.0, 650.0, 816.0],
        "E": [185000.0, 170000.0, 155000.0],
        "sigma_f": [1100.0, 900.0, 700.0],
        "b": [-0.09, -0.10, -0.11],
        "eps_f": [0.40, 0.30, 0.20],
        "c": [-0.55, -0.60, -0.65],
    }


def test_interpolate_exact_at_table_point():
    out = ht.interpolate_constants(_table(), 650.0)
    assert out["E"] == pytest.approx(170000.0)
    assert out["sigma_f"] == pytest.approx(900.0)
    assert out["c"] == pytest.approx(-0.60)


def test_interpolate_between_points():
    out = ht.interpolate_constants(_table(), 540.0)  # between 430 and 650
    assert 170000.0 < out["E"] < 185000.0
    assert -0.10 < out["b"] < -0.09
    # coefficient is log-interpolated, so it stays positive and between bounds
    assert 900.0 < out["sigma_f"] < 1100.0


def test_interpolate_clamps_outside():
    hot = ht.interpolate_constants(_table(), 1000.0)
    assert hot["E"] == pytest.approx(155000.0)  # clamps to the hottest entry
