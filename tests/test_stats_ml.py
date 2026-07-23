"""Tests for the WK88010-aligned maximum-likelihood statistics layer:
censored fits with uncertainty, the profile-likelihood design bound, the
runout-handling comparison, and the censored nonlinear strain-life fit.

Validation strategy, stated per the honesty rule: the uncensored limits are
checked exactly against closed-form least squares, recovery is checked on
seeded synthetic data at curve level, the profile bound is checked for
consistency against the exact Owen bound on complete samples, and the
censored likelihood machinery is anchored by the exact published
Pascual-Meeker reproduction in test_rfl.py. No published golden value for
the censored linear or censored nonlinear strain-life fits is bundled.
"""

import numpy as np
import pytest

from lcf import datasets, fits, life, stats
from lcf.service import LcfService


@pytest.fixture(scope="module")
def sae1137():
    df = datasets.sae1137_reduced()
    return df.total_strain_amp.to_numpy(), df.stress_amp.to_numpy(), \
        df.reversals.to_numpy()


def synthetic_linear(seed=42, n=24, sigma=0.15, censor_top=0.8):
    rng = np.random.default_rng(seed)
    x = rng.uniform(0.002, 0.01, n)
    y = 2.0 - 2.5 * np.log10(x / 0.005) + rng.normal(0.0, sigma, n)
    life_v = 10.0 ** y
    cens = np.zeros(n, bool)
    limit = 10.0 ** np.quantile(y, censor_top)
    cens[life_v > limit] = True
    life_v[cens] = limit
    return x, life_v, cens


class TestCensoredLinearMl:
    def test_uncensored_limit_equals_ols_exactly(self, sae1137):
        strain, _, rev = sae1137
        ols = stats.fit_log_life(strain, rev)
        ml = stats.fit_log_life_censored(strain, rev, [False] * len(rev))
        assert ml.slope == pytest.approx(ols.slope, abs=1e-6)
        assert ml.intercept == pytest.approx(ols.intercept, abs=1e-6)
        # ML sigma is the OLS s scaled by sqrt((n-2)/n), no bias correction
        n = len(rev)
        assert ml.residual_std == pytest.approx(
            ols.residual_std * np.sqrt((n - 2) / n), rel=1e-6
        )
        assert ml.n_censored == 0

    def test_censored_fit_carries_uncertainty(self):
        x, life_v, cens = synthetic_linear()
        ml = stats.fit_log_life_censored(x, life_v, cens)
        assert ml.n_censored == int(cens.sum())
        assert ml.converged
        assert np.isfinite(ml.loglik)
        assert ml.aic == pytest.approx(6.0 - 2.0 * ml.loglik)
        for se in (ml.se_intercept, ml.se_slope, ml.se_log_sigma):
            assert np.isfinite(se) and se > 0
        assert ml.cov is not None
        assert len(ml.cov) == 3 and len(ml.cov[0]) == 3
        assert isinstance(ml, stats.LogLifeFit)

    def test_lognormal_recovery_on_synthetic(self):
        x, life_v, cens = synthetic_linear(seed=11, n=60, sigma=0.12)
        ml = stats.fit_log_life_censored(x, life_v, cens)
        assert ml.slope == pytest.approx(-2.5, abs=0.35)
        assert ml.residual_std == pytest.approx(0.12, rel=0.35)

    def test_weibull_recovery_on_synthetic(self):
        rng = np.random.default_rng(5)
        n = 120
        x = rng.uniform(0.002, 0.01, n)
        mu = 2.0 - 2.5 * np.log10(x / 0.005)
        y = mu + 0.15 * rng.gumbel(0.0, 1.0, n) * -1.0  # smallest extreme value
        life_v = 10.0 ** y
        cens = np.zeros(n, bool)
        ml = stats.fit_log_life_censored(
            x, life_v, cens, distribution="weibull"
        )
        assert ml.distribution == "weibull"
        assert ml.slope == pytest.approx(-2.5, abs=0.3)
        assert ml.residual_std == pytest.approx(0.15, rel=0.3)

    def test_model_selection_prefers_generating_distribution(self):
        x, life_v, cens = synthetic_linear(seed=42)
        ln = stats.fit_log_life_censored(x, life_v, cens)
        wb = stats.fit_log_life_censored(x, life_v, cens,
                                         distribution="weibull")
        assert ln.aic < wb.aic

    def test_unknown_distribution_rejected(self, sae1137):
        strain, _, rev = sae1137
        with pytest.raises(ValueError, match="distribution"):
            stats.fit_log_life_censored(
                strain, rev, [False] * len(rev), distribution="gamma"
            )

    def test_length_mismatch_rejected(self):
        with pytest.raises(ValueError, match="equal length"):
            stats.fit_log_life_censored([0.01, 0.02], [100, 200], [False])


class TestDesignLifeMl:
    def test_bound_orders_and_methods_agree(self):
        x, life_v, cens = synthetic_linear()
        prof = stats.design_life_ml(x, life_v, cens, at_amplitude=0.005)
        wald = stats.design_life_ml(x, life_v, cens, at_amplitude=0.005,
                                    method="wald")
        for r in (prof, wald):
            assert r["design_life"] < r["quantile_life"] < r["median_life"]
        # the two bounds are asymptotically the same quantity
        assert abs(np.log10(prof["design_life"] / wald["design_life"])) < 0.2

    def test_profile_close_to_owen_on_complete_sample(self):
        # On a complete normal sample the Owen bound is exact and the
        # profile bound is asymptotic, they must be close, not equal.
        rng = np.random.default_rng(3)
        x = rng.uniform(0.002, 0.01, 20)
        y = 2.0 - 2.5 * np.log10(x / 0.005) + rng.normal(0, 0.12, 20)
        life_v = 10.0 ** y
        owen_fit = stats.fit_log_life(x, life_v)
        owen = stats.design_life(owen_fit, 0.005,
                                 reliability=0.90, confidence=0.90)
        ml = stats.design_life_ml(x, life_v, [False] * 20,
                                  at_amplitude=0.005)["design_life"]
        assert abs(np.log10(ml / owen)) < 0.1

    def test_higher_reliability_lowers_bound(self):
        x, life_v, cens = synthetic_linear()
        r90 = stats.design_life_ml(x, life_v, cens, at_amplitude=0.005,
                                   reliability=0.90)
        r99 = stats.design_life_ml(x, life_v, cens, at_amplitude=0.005,
                                   reliability=0.99)
        assert r99["design_life"] < r90["design_life"]

    def test_higher_confidence_lowers_bound(self):
        x, life_v, cens = synthetic_linear()
        c90 = stats.design_life_ml(x, life_v, cens, at_amplitude=0.005,
                                   confidence=0.90)
        c99 = stats.design_life_ml(x, life_v, cens, at_amplitude=0.005,
                                   confidence=0.99)
        assert c99["design_life"] < c90["design_life"]

    def test_extrapolation_warning(self):
        x, life_v, cens = synthetic_linear()
        r = stats.design_life_ml(x, life_v, cens, at_amplitude=0.05)
        assert any(w["code"] == "extrapolation" for w in r["warnings"])

    def test_invalid_arguments_rejected(self):
        x, life_v, cens = synthetic_linear()
        with pytest.raises(ValueError, match="method"):
            stats.design_life_ml(x, life_v, cens, at_amplitude=0.005,
                                 method="bayes")
        with pytest.raises(ValueError, match="reliability"):
            stats.design_life_ml(x, life_v, cens, at_amplitude=0.005,
                                 reliability=1.5)


class TestCompareRunoutHandling:
    def test_three_treatments_reported(self):
        x, life_v, cens = synthetic_linear()
        cmp = stats.compare_runout_handling(x, life_v, cens,
                                            at_amplitude=0.005)
        for key in ("naive", "ml_owen", "ml_profile"):
            assert "design_life" in cmp[key]
        assert set(cmp["design_life_ratio"]) == {
            "ml_owen_over_naive", "ml_profile_over_naive"
        }
        assert cmp["n_censored"] == int(cens.sum())

    def test_naive_unavailable_with_two_observed(self):
        x = [0.002, 0.004, 0.006, 0.008, 0.01]
        life_v = [1e6, 1e5, 1e4, 5e3, 2e3]
        cens = [True, True, True, False, False]
        cmp = stats.compare_runout_handling(x, life_v, cens,
                                            at_amplitude=0.005)
        assert "design_life" not in cmp["naive"]
        assert "unavailable" in cmp["naive"]["note"]


class TestCensoredStrainLife:
    def test_curve_level_recovery_with_censoring(self):
        rng = np.random.default_rng(7)
        sf, b, ef, c, sig = 900.0, -0.09, 0.8, -0.6, 0.08
        E = 200000.0
        strain = rng.uniform(0.0015, 0.012, 30)
        mu = np.array([
            np.log10(life.predict_reversals_from_total_strain(
                e, sf, b, ef, c, E))
            for e in strain
        ])
        rev = 10.0 ** (mu + rng.normal(0, sig, 30))
        cens = rev > 5.0e5
        rev[cens] = 5.0e5
        fit = stats.fit_strain_life_censored(strain, rev, cens, E=E)
        assert fit.converged
        assert fit.b < 0 and fit.c < 0
        assert fit.n_censored == int(cens.sum())
        assert fit.sigma_log10_life == pytest.approx(sig, rel=0.5)
        grid = np.array([0.002, 0.003, 0.005, 0.008, 0.011])
        for eps in grid:
            got = np.log10(life.predict_reversals_from_total_strain(
                eps, fit.sigma_f, fit.b, fit.eps_f, fit.c, E))
            want = np.log10(life.predict_reversals_from_total_strain(
                eps, sf, b, ef, c, E))
            assert got == pytest.approx(want, abs=0.05)

    def test_matches_refined_least_squares_uncensored(self, sae1137):
        strain, stress, rev = sae1137
        E = datasets.SAE1137_E
        ml = stats.fit_strain_life_censored(strain, rev, E=E,
                                            stress_amp=stress)
        ls = fits.fit_strain_life(strain, stress, rev, E,
                                  min_plastic_strain=5e-4,
                                  refine_nonlinear=True)
        r = ls.refined
        for eps in strain:
            a = np.log10(life.predict_reversals_from_total_strain(
                eps, ml.sigma_f, ml.b, ml.eps_f, ml.c, E))
            b_ = np.log10(life.predict_reversals_from_total_strain(
                eps, r["sigma_f"], r["b"], r["eps_f"], r["c"], E))
            assert a == pytest.approx(b_, abs=0.15)

    def test_heuristic_seed_agrees_with_stress_seed(self, sae1137):
        strain, stress, rev = sae1137
        E = datasets.SAE1137_E
        with_stress = stats.fit_strain_life_censored(
            strain, rev, E=E, stress_amp=stress)
        without = stats.fit_strain_life_censored(strain, rev, E=E)
        assert without.loglik == pytest.approx(with_stress.loglik, abs=0.05)

    def test_fit_reports_weak_elastic_branch(self, sae1137):
        # Six points cannot pin four correlated constants. On SAE 1137 the
        # optimum sits at a collapsed elastic exponent, b near zero, and
        # the uncertainty report must expose the weakness: some constant
        # has a standard error at least as large as its estimate, or a
        # standard error is not finite.
        strain, stress, rev = sae1137
        fit = stats.fit_strain_life_censored(
            strain, rev, E=datasets.SAE1137_E, stress_amp=stress)
        ses = [fit.se_sigma_f, fit.se_b, fit.se_eps_f, fit.se_c]
        vals = [fit.sigma_f, fit.b, fit.eps_f, fit.c]
        assert any(
            not np.isfinite(s) or s > abs(v) for s, v in zip(ses, vals)
        )

    def test_input_validation(self):
        with pytest.raises(ValueError, match="at least 5"):
            stats.fit_strain_life_censored(
                [0.01, 0.008, 0.006, 0.004], [1e3, 1e4, 1e5, 1e6],
                E=200000.0)
        with pytest.raises(ValueError, match="uncensored"):
            stats.fit_strain_life_censored(
                [0.01, 0.008, 0.006, 0.004, 0.002],
                [1e3, 1e4, 1e5, 1e6, 1e7],
                [True, True, True, False, False], E=200000.0)
        with pytest.raises(ValueError, match="equal length"):
            stats.fit_strain_life_censored(
                [0.01, 0.008], [1e3, 1e4], [False], E=200000.0)

    def test_censoring_beats_treating_runouts_as_failures(self):
        # Treating suspensions as failures biases life down, the censored
        # fit must sit above that at the runout end.
        rng = np.random.default_rng(19)
        sf, b, ef, c, sig = 1000.0, -0.1, 0.6, -0.55, 0.1
        E = 195000.0
        strain = np.geomspace(0.0018, 0.01, 24)
        mu = np.array([
            np.log10(life.predict_reversals_from_total_strain(
                e, sf, b, ef, c, E))
            for e in strain
        ])
        rev = 10.0 ** (mu + rng.normal(0, sig, 24))
        cens = rev > 2.0e5
        rev[cens] = 2.0e5
        censored_fit = stats.fit_strain_life_censored(strain, rev, cens, E=E)
        naive_fit = stats.fit_strain_life_censored(
            strain, rev, np.zeros(24, bool), E=E)
        eps_low = 0.002
        life_cens = life.predict_reversals_from_total_strain(
            eps_low, censored_fit.sigma_f, censored_fit.b,
            censored_fit.eps_f, censored_fit.c, E)
        life_naive = life.predict_reversals_from_total_strain(
            eps_low, naive_fit.sigma_f, naive_fit.b,
            naive_fit.eps_f, naive_fit.c, E)
        assert life_cens > life_naive


class TestServiceIntegration:
    @pytest.fixture
    def svc(self, tmp_path):
        return LcfService(store=str(tmp_path / "store"))

    def test_design_curve_censored_carries_ml_block(self, svc):
        x, life_v, cens = synthetic_linear()
        out = svc.fit_design_curve(
            list(x), list(life_v), censored=[bool(v) for v in cens],
            design_amplitude=0.005,
        )
        assert out["ml"]["n_censored"] == int(cens.sum())
        assert np.isfinite(out["ml"]["standard_errors"]["slope"])
        assert out["ml_design_life"] < out["median_life"]
        assert out["ml"]["design_method"] == "profile"
        assert any(w["code"] == "owen_with_censoring"
                   for w in out["warnings"])

    def test_design_curve_uncensored_unchanged_shape(self, svc, sae1137):
        strain, _, rev = sae1137
        out = svc.fit_design_curve(
            list(strain), list(rev), design_amplitude=0.005)
        assert "ml" not in out
        assert "ml_design_life" not in out
        assert out["design_life"] < out["median_life"]

    def test_design_curve_distribution_ignored_warning(self, svc, sae1137):
        strain, _, rev = sae1137
        out = svc.fit_design_curve(
            list(strain), list(rev), distribution="weibull")
        assert any(w["code"] == "distribution_ignored"
                   for w in out["warnings"])

    def test_fit_strain_life_ml_service(self, svc, sae1137):
        strain, stress, rev = sae1137
        out = svc.fit_strain_life_ml(
            list(strain), list(rev), E=datasets.SAE1137_E,
            stress_amp=list(stress), name="sae1137-ml",
        )
        assert out["b"] < 0 and out["c"] < 0
        assert out["n_points"] == 6
        assert "sigma_log10_life" in out
        assert any(w["code"] == "weak_identifiability"
                   for w in out["warnings"])
        recalled = svc.recall("sae1137-ml", "strain_life_ml")
        assert recalled is not None
        assert recalled["value"]["sigma_f"] == pytest.approx(out["sigma_f"])
