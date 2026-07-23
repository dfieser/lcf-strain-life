"""Tests for lcf.staircase (Dixon-Mood per ISO 12107) and the basis-value
and lack-of-fit additions to lcf.stats.

Golden staircase case: S34MnV steel, R=-1, step 20 MPa, 12 specimens with 7
survivals and 5 fractures. Ekaputra, Dewa, Haryadi and Kim, Open Engineering
10 (2020) 394-400, DOI 10.1515/eng-2020-0048: A=8, B=14, N=5, mean fatigue
strength 282 MPa, standard deviation 10.6 MPa. The variability statistic
(N*B - A^2)/N^2 = 0.24 sits below the 0.3 validity bound, so the published
10.6 MPa is the 0.53*step fallback and the result must carry the warning.
"""

from __future__ import annotations


import numpy as np
import pytest

from lcf import staircase, stats
from lcf.service import LcfService


# S34MnV up-down sequence consistent with the published counts: fractures at
# {300: 3, 280: 2}, survivals at {260: 3, 280: 4}, following the up-down rule
# (survive -> +20 MPa, fracture -> -20 MPa) from a 260 MPa start.
S34MNV_LEVELS = [260, 280, 300, 280, 300, 280, 300, 280, 260, 280, 260, 280]
S34MNV_FAILED = [False, False, True, False, True, False, True, True, False,
                 True, False, False]


@pytest.fixture()
def svc(tmp_path):
    return LcfService(tmp_path / "store")


# --------------------------------------------------------------------------- #
# Dixon-Mood staircase
# --------------------------------------------------------------------------- #
def test_dixon_mood_s34mnv_golden():
    out = staircase.dixon_mood(S34MNV_LEVELS, S34MNV_FAILED)
    assert out.event == "failure"          # 5 fractures < 7 survivals
    assert out.n_events == 5
    assert out.step == pytest.approx(20.0)
    assert out.mean == pytest.approx(282.0)
    assert out.ratio == pytest.approx(0.24)
    assert out.ratio_ok is False
    assert out.std == pytest.approx(10.6)  # 0.53 * 20, the fallback
    assert any("0.3" in n for n in out.notes)


def test_dixon_mood_survival_branch_sign():
    # Mirror case: more failures than survivals, analysis uses survivals and
    # the +1/2 convention. Up-down-consistent sequence, checked by hand:
    # survivals at {240: 2, 260: 1} -> A = 0*2 + 1*1 = 1, B = 1, N = 3,
    # mean = 240 + 20*(1/3 + 0.5) = 256.67.
    levels = [280, 260, 240, 260, 280, 260, 240]
    failed = [True, True, False, False, True, True, False]
    out = staircase.dixon_mood(levels, failed)
    assert out.event == "survival"
    assert out.mean == pytest.approx(240 + 20 * (1 / 3 + 0.5), rel=1e-9)


def test_dixon_mood_reliable_branch_uses_full_formula():
    # Spread the failures over three levels so the statistic clears 0.3:
    # failures at {240: 1, 260: 2, 280: 1} -> A = 4, B = 6, N = 4,
    # ratio = (24 - 16)/16 = 0.5 >= 0.3 -> std = 1.62*20*(0.5 + 0.029).
    # Up-down-consistent from a 260 MPa start, checked by hand.
    levels = [260, 240, 220, 240, 260, 280, 260, 240, 260]
    failed = [True, True, False, False, False, True, True, False, False]
    out = staircase.dixon_mood(levels, failed)
    assert out.event == "failure"
    assert out.ratio == pytest.approx(0.5)
    assert out.ratio_ok is True
    assert out.std == pytest.approx(1.62 * 20 * (0.5 + 0.029), rel=1e-9)


def test_dixon_mood_step_inferred_and_override():
    out = staircase.dixon_mood(S34MNV_LEVELS, S34MNV_FAILED, step=20.0)
    assert out.mean == pytest.approx(282.0)


def test_dixon_mood_refuses_single_outcome():
    with pytest.raises(ValueError, match="both"):
        staircase.dixon_mood([260, 280, 300], [False, False, False])


def test_dixon_mood_refuses_non_uniform_grid():
    with pytest.raises(ValueError, match="step"):
        staircase.dixon_mood([260, 280, 290], [False, True, False])


def test_dixon_mood_length_mismatch():
    with pytest.raises(ValueError, match="length"):
        staircase.dixon_mood([260, 280], [False])


def test_dixon_mood_notes_up_down_violation():
    # A survival followed by a *lower* level breaks the up-down rule. Still
    # analyzed, but flagged.
    levels = [260, 240, 260, 280, 260, 280]
    failed = [False, False, True, False, True, False]
    out = staircase.dixon_mood(levels, failed)
    assert any("up-down" in n for n in out.notes)


# --------------------------------------------------------------------------- #
# basis values (Owen one-sided tolerance bounds)
# --------------------------------------------------------------------------- #
def test_basis_factors_match_standard_tables():
    # Standard one-sided tolerance factors (Owen): n=10.
    assert stats.owen_tolerance_factor(10, 0.90, 0.95) == pytest.approx(2.355, abs=0.002)
    assert stats.owen_tolerance_factor(10, 0.99, 0.95) == pytest.approx(3.981, abs=0.004)


def test_basis_value_b_and_a():
    b = stats.basis_value(mean=500.0, std=20.0, n=10, basis="B")
    a = stats.basis_value(mean=500.0, std=20.0, n=10, basis="A")
    assert b["reliability"] == 0.90 and b["confidence"] == 0.95
    assert a["reliability"] == 0.99 and a["confidence"] == 0.95
    assert b["value"] == pytest.approx(500.0 - b["k"] * 20.0)
    assert a["value"] < b["value"]          # A-basis is the stricter bound


def test_basis_value_rejects_unknown_basis():
    with pytest.raises(ValueError, match="basis"):
        stats.basis_value(mean=1.0, std=1.0, n=5, basis="C")


def test_basis_value_needs_n_at_least_2():
    with pytest.raises(ValueError, match="n"):
        stats.basis_value(mean=1.0, std=1.0, n=1)


# --------------------------------------------------------------------------- #
# lack-of-fit F test (E739 style, replicates required)
# --------------------------------------------------------------------------- #
def test_lack_of_fit_hand_computed_case():
    # Hand-worked in log10 space via 10** inputs. x = [1,1,2,2,3,3],
    # y = [1.0,1.2, 2.0,2.2, 3.5,3.7]. Level means (1.1, 2.1, 3.6),
    # SS_pure = 0.06 (df 3), regression through the data gives
    # SS_lof = 0.08333 (df 1), F = 4.1667.
    x = [1.0, 1.0, 2.0, 2.0, 3.0, 3.0]
    y = [1.0, 1.2, 2.0, 2.2, 3.5, 3.7]
    out = stats.lack_of_fit([10.0 ** v for v in x], [10.0 ** v for v in y])
    assert out["available"] is True
    assert out["f_statistic"] == pytest.approx(4.1667, rel=1e-3)
    assert out["df_lack_of_fit"] == 1
    assert out["df_pure_error"] == 3
    assert 0.0 < out["p_value"] < 1.0


def test_lack_of_fit_unavailable_without_replicates():
    out = stats.lack_of_fit([0.01, 0.008, 0.006, 0.004], [1e3, 1e4, 1e5, 1e6])
    assert out["available"] is False
    assert "replicate" in out["reason"]


# --------------------------------------------------------------------------- #
# service and persistence
# --------------------------------------------------------------------------- #
def test_service_analyze_staircase_persists(svc):
    out = svc.analyze_staircase(S34MNV_LEVELS, S34MNV_FAILED, name="S34MnV")
    assert out["mean"] == pytest.approx(282.0)
    assert out["std"] == pytest.approx(10.6)
    assert out["ratio_ok"] is False
    assert svc.recall("S34MnV", "staircase") is not None


def test_service_compute_basis_value_from_samples(svc):
    rng = np.random.default_rng(7)
    samples = list(rng.normal(500.0, 20.0, size=12))
    out = svc.compute_basis_value(samples=samples, basis="B")
    m, s = float(np.mean(samples)), float(np.std(samples, ddof=1))
    assert out["value"] == pytest.approx(m - out["k"] * s)
    assert out["n"] == 12


def test_service_compute_basis_value_needs_input(svc):
    with pytest.raises(ValueError, match="samples"):
        svc.compute_basis_value()


def test_fit_design_curve_reports_lack_of_fit(svc):
    amp = [0.010, 0.010, 0.006, 0.006, 0.003, 0.003]
    life = [1.1e3, 1.4e3, 2.2e4, 2.6e4, 8.0e5, 9.6e5]
    out = svc.fit_design_curve(amp, life)
    assert out["lack_of_fit"]["available"] is True
    assert out["lack_of_fit"]["f_statistic"] > 0.0


def test_fit_design_curve_lack_of_fit_censored_declined(svc):
    amp = [0.010, 0.006, 0.003, 0.002]
    life = [1.1e3, 2.2e4, 8.0e5, 5.0e6]
    out = svc.fit_design_curve(amp, life, censored=[False, False, False, True])
    assert out["lack_of_fit"]["available"] is False
