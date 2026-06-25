"""Tests for lcf.stats, including Golden G (Williams, Lee, Rilly SAE 1137).

See docs/design/IMPLEMENTATION_REFERENCE_PHASE2.md section 3.5.
"""

import numpy as np
import pytest

from lcf import stats


# --- Owen tolerance factor (validated against standard tables) --------------
def test_owen_factor_table_values():
    # standard one-sided normal tolerance factors
    assert stats.owen_tolerance_factor(10, 0.90, 0.95) == pytest.approx(2.355, abs=2e-3)
    assert stats.owen_tolerance_factor(20, 0.90, 0.95) == pytest.approx(1.926, abs=2e-3)


def test_owen_factor_increases_with_reliability():
    assert stats.owen_tolerance_factor(15, 0.95, 0.90) > stats.owen_tolerance_factor(15, 0.90, 0.90)


def test_owen_factor_decreases_with_n():
    assert stats.owen_tolerance_factor(50, 0.90, 0.90) < stats.owen_tolerance_factor(8, 0.90, 0.90)


def test_golden_g_williams_reduction_formula():
    # Williams, Lee, Rilly report K=2.608, s=0.03011, n=8, R50=23,700 reversals,
    # R90C90=22,300. Their design value is the mean reduced by K*s/sqrt(n) in
    # log10 life. Validate that construction reproduces the published R90C90.
    K, s, n, r50 = 2.608, 0.03011, 8, 23700.0
    r90c90 = r50 * 10.0 ** (-K * s / np.sqrt(n))
    assert r90c90 == pytest.approx(22300.0, rel=0.01)


# --- regression -------------------------------------------------------------
def _synthetic():
    # perfect power law life = 1e12 * amp**(-3), with mild scatter-free data
    amp = np.array([0.01, 0.007, 0.005, 0.003, 0.002, 0.0015])
    life = 1e6 * (amp / 0.01) ** (-3.0)
    return amp, life


def test_fit_log_life_recovers_slope():
    amp, life = _synthetic()
    fit = stats.fit_log_life(amp, life)
    assert fit.slope == pytest.approx(-3.0, rel=1e-6)
    assert fit.r_squared == pytest.approx(1.0, abs=1e-9)


def test_predict_life_roundtrip():
    amp, life = _synthetic()
    fit = stats.fit_log_life(amp, life)
    np.testing.assert_allclose(stats.predict_life(fit, amp), life, rtol=1e-6)


def test_prediction_interval_wider_than_confidence():
    amp = np.array([0.01, 0.008, 0.006, 0.004, 0.003, 0.002])
    life = 1e6 * (amp / 0.01) ** (-3.0) * np.array([1.1, 0.9, 1.2, 0.8, 1.05, 0.95])
    fit = stats.fit_log_life(amp, life)
    clo, chi = stats.confidence_interval(fit, 0.005)
    plo, phi = stats.prediction_interval(fit, 0.005)
    assert plo < clo and phi > chi  # prediction band is wider


def test_design_life_below_median():
    amp = np.array([0.01, 0.008, 0.006, 0.004, 0.003, 0.002])
    life = 1e6 * (amp / 0.01) ** (-3.0) * np.array([1.1, 0.9, 1.2, 0.8, 1.05, 0.95])
    fit = stats.fit_log_life(amp, life)
    assert stats.design_life(fit, 0.005) < stats.predict_life(fit, 0.005)


# --- censored MLE -----------------------------------------------------------
def test_censored_mle_matches_ols_without_censoring():
    amp = np.array([0.01, 0.008, 0.006, 0.004, 0.003, 0.002])
    life = 1e6 * (amp / 0.01) ** (-3.0) * np.array([1.1, 0.9, 1.2, 0.8, 1.05, 0.95])
    ols = stats.fit_log_life(amp, life)
    mle = stats.fit_log_life_censored(amp, life, [False] * len(amp))
    assert mle.slope == pytest.approx(ols.slope, rel=1e-2)
    assert mle.intercept == pytest.approx(ols.intercept, rel=1e-2)


def test_censored_runout_raises_predicted_life():
    amp = np.array([0.01, 0.008, 0.006, 0.004, 0.003, 0.002])
    life = 1e6 * (amp / 0.01) ** (-3.0)
    # treat the longest-life point as a runout (true life exceeds observed)
    cens = [False, False, False, False, False, True]
    as_failure = stats.fit_log_life_censored(amp, life, [False] * 6)
    with_runout = stats.fit_log_life_censored(amp, life, cens)
    # censoring the runout should not lower the predicted life at that amplitude
    assert stats.predict_life(with_runout, 0.002) >= stats.predict_life(as_failure, 0.002) * 0.999
