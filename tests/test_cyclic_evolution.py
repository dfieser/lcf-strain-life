"""Tests for lcf.cyclic_evolution: mean stress relaxation and ratcheting.

These are reconstructed forms (collaborator notes 2026-07-08) matching the
standard published power laws. Validation is internal consistency plus
fitter-recovery of known constants, there is no published-worked-example
golden and the results say so.
"""

from __future__ import annotations

import numpy as np
import pytest

from lcf import cyclic_evolution as ce
from lcf.service import LcfService


# --------------------------------------------------------------------------- #
# mean stress relaxation
# --------------------------------------------------------------------------- #
def test_relaxation_decays_toward_zero():
    N = np.array([1.0, 10.0, 100.0, 1000.0])
    s = ce.mean_stress_relaxation(120.0, N, -0.1)
    assert s[0] == pytest.approx(120.0)
    assert np.all(np.diff(s) < 0)          # monotonically relaxing
    assert s[-1] < s[0]


def test_relaxation_preserves_sign_and_first_cycle():
    s = ce.mean_stress_relaxation(-80.0, [1.0, 50.0], -0.2)
    assert s[0] == pytest.approx(-80.0)
    assert s[1] > s[0]                      # magnitude shrinks toward zero


def test_relaxation_refusals():
    with pytest.raises(ValueError, match="N must be"):
        ce.mean_stress_relaxation(100.0, [0.5], -0.1)
    with pytest.raises(ValueError, match="b_r must be"):
        ce.mean_stress_relaxation(100.0, [1.0], 0.1)


def test_fit_relaxation_recovers_exponent():
    N = np.array([1.0, 5.0, 20.0, 100.0, 500.0])
    true_b, true_s1 = -0.15, 140.0
    s = true_s1 * N ** true_b
    out = ce.fit_relaxation_exponent(N, s)
    assert out["b_r"] == pytest.approx(true_b, rel=1e-6)
    assert out["sigma_m1"] == pytest.approx(true_s1, rel=1e-6)
    assert out["r_squared"] == pytest.approx(1.0, abs=1e-9)
    assert any("reconstructed" in n for n in out["notes"])


def test_fit_relaxation_negative_mean_sign():
    N = np.array([1.0, 10.0, 100.0, 1000.0])
    s = -90.0 * N ** -0.12
    out = ce.fit_relaxation_exponent(N, s)
    assert out["sigma_m1"] < 0
    assert out["b_r"] == pytest.approx(-0.12, rel=1e-6)


def test_fit_relaxation_mixed_sign_refused():
    with pytest.raises(ValueError, match="share one sign"):
        ce.fit_relaxation_exponent([1.0, 2.0, 3.0], [10.0, -5.0, 3.0])


# --------------------------------------------------------------------------- #
# ratcheting
# --------------------------------------------------------------------------- #
def test_ratcheting_grows_monotonically():
    N = np.array([1.0, 10.0, 100.0])
    e = ce.ratcheting_strain(N, 1e-4, 0.5)
    assert np.all(np.diff(e) > 0)
    assert e[0] == pytest.approx(1e-4)


def test_fit_ratcheting_recovers_constants():
    N = np.array([1.0, 5.0, 25.0, 125.0, 625.0])
    true_C, true_p = 2.5e-4, 0.42
    e = true_C * N ** true_p
    out = ce.fit_ratcheting(N, e)
    assert out["C"] == pytest.approx(true_C, rel=1e-6)
    assert out["p"] == pytest.approx(true_p, rel=1e-6)
    assert out["r_squared"] == pytest.approx(1.0, abs=1e-9)


def test_ratcheting_refusals():
    with pytest.raises(ValueError, match="C must be"):
        ce.ratcheting_strain([1.0], -1.0, 0.5)
    with pytest.raises(ValueError, match="at least 3"):
        ce.fit_ratcheting([1.0, 2.0], [1e-4, 2e-4])


# --------------------------------------------------------------------------- #
# ratcheting-penalized life
# --------------------------------------------------------------------------- #
def test_ratcheting_penalty_shortens_life():
    base = ce.ratcheting_penalized_life(0.005, 0.0, eps_f=0.6, c=-0.6)
    penalized = ce.ratcheting_penalized_life(0.005, 0.2, eps_f=0.6, c=-0.6)
    assert penalized["reversals"] < base["reversals"]
    assert penalized["eps_f_effective"] == pytest.approx(0.4)


def test_ratcheting_penalty_matches_coffin_manson_at_zero():
    # with eps_r = 0 the penalized life is the plain Coffin-Manson inverse
    out = ce.ratcheting_penalized_life(0.005, 0.0, eps_f=0.6, c=-0.6)
    two_nf = (0.005 / 0.6) ** (1.0 / -0.6)
    assert out["reversals"] == pytest.approx(two_nf, rel=1e-9)


def test_ratcheting_exhausted_ductility_fails_immediately():
    out = ce.ratcheting_penalized_life(0.005, 0.7, eps_f=0.6, c=-0.6)
    assert out["cycles"] == 0.5
    assert any("consumed the fatigue ductility" in n for n in out["notes"])


# --------------------------------------------------------------------------- #
# service exposure
# --------------------------------------------------------------------------- #
def test_service_relaxation_and_ratcheting(tmp_path):
    svc = LcfService(tmp_path / "store")
    r = svc.fit_mean_stress_relaxation(
        [1.0, 10.0, 100.0, 1000.0],
        [140.0 * n ** -0.15 for n in (1.0, 10.0, 100.0, 1000.0)],
    )
    assert r["b_r"] == pytest.approx(-0.15, rel=1e-6)

    rt = svc.fit_ratcheting_law(
        [1.0, 10.0, 100.0, 1000.0],
        [2e-4 * n ** 0.4 for n in (1.0, 10.0, 100.0, 1000.0)],
    )
    assert rt["p"] == pytest.approx(0.4, rel=1e-6)

    life = svc.ratcheting_penalized_life(0.005, 0.2, eps_f=0.6, c=-0.6)
    assert life["reversals"] > 0
