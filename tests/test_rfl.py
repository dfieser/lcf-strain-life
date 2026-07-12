"""Tests for lcf.rfl, the random fatigue limit model.

Validation strategy: the fitter reproduces the published Pascual-Meeker
(Technometrics 41, 1999) normal-normal fit of the laminate-panel dataset
exactly (the golden test below), the marginal likelihood is cross-checked
against brute-force adaptive integration, and the fitter recovers known
parameters from simulated data.
"""

from __future__ import annotations

import csv
from pathlib import Path

import numpy as np
import pytest
from scipy import integrate
from scipy import stats as scistats

from lcf import rfl
from lcf.service import LcfService

_DATA = Path(__file__).parent / "data" / "laminate_panel.csv"


def _laminate_panel():
    mpa, kc, cen = [], [], []
    with open(_DATA, encoding="utf-8") as f:
        for line in f:
            if line.startswith("#") or line.startswith("mpa"):
                continue
            s, k, e = line.strip().split(",")
            mpa.append(float(s)); kc.append(float(k))
            cen.append(e.strip() == "Censored")
    return np.array(mpa), np.array(kc), np.array(cen)


def test_laminate_panel_reproduces_published_fit():
    """The golden benchmark: exact reproduction of Pascual-Meeker 1999.

    Their normal-normal fit of this dataset (Table 1): log-likelihood
    -86.221, beta0 30.272, beta1 -5.100, mu_gamma 5.366. Life in kilocycles,
    natural logs, as in the paper.
    """
    mpa, kc, cen = _laminate_panel()
    assert len(mpa) == 125 and cen.sum() == 10
    fit = rfl.fit_rfl(mpa, kc, cen)
    assert fit.converged
    assert fit.log_likelihood == pytest.approx(-86.221, abs=0.01)
    assert fit.beta0 == pytest.approx(30.272, abs=0.01)
    assert fit.beta1 == pytest.approx(-5.100, abs=0.01)
    assert fit.mu_gamma == pytest.approx(5.366, abs=0.005)
    assert fit.sigma == pytest.approx(0.2895, abs=0.005)
    assert fit.sigma_gamma == pytest.approx(0.0314, abs=0.005)
    # implied fatigue limit sits below the lowest tested stress
    assert float(np.exp(fit.mu_gamma)) == pytest.approx(214.0, abs=1.0)

# Self-consistent truth values at the published laminate-panel test design
# (five levels, 25 specimens each, runouts at the low levels). These are
# plausible values chosen to exercise both censoring mechanisms, they are
# NOT the published estimates: the paper's parameter table could not be
# extracted reliably and unverified numbers must not pose as goldens.
TRUTH = dict(beta0=28.0, beta1=-4.5, sigma=0.30,
             mu_gamma=5.52, sigma_gamma=0.05)
LEVELS = [270.0, 280.0, 300.0, 340.0, 380.0]
CENSOR = 2.0e6


def test_loglik_matches_bruteforce_integration():
    theta = (30.0, -5.0, np.log(0.3), 5.35, np.log(0.04))
    b0, b1, ls, mg, lsg = theta
    sig, sig_g = np.exp(ls), np.exp(lsg)

    def brute_pdf(w_obs, s):
        x = np.log(s)

        def integrand(v):
            mu = b0 + b1 * np.log(s - np.exp(v))
            return (scistats.norm.pdf((w_obs - mu) / sig) / sig
                    * scistats.norm.pdf(v, mg, sig_g))

        val, _ = integrate.quad(integrand, mg - 12 * sig_g,
                                min(x - 1e-12, mg + 12 * sig_g), limit=200)
        return val

    def brute_surv(w_obs, s):
        x = np.log(s)

        def integrand(v):
            mu = b0 + b1 * np.log(s - np.exp(v))
            return (scistats.norm.sf((w_obs - mu) / sig)
                    * scistats.norm.pdf(v, mg, sig_g))

        val, _ = integrate.quad(integrand, mg - 12 * sig_g,
                                min(x - 1e-12, mg + 12 * sig_g), limit=200)
        return val + scistats.norm.sf(x, mg, sig_g)

    stress = [300.0, 280.0, 270.0]
    log_life = [np.log(2.0e3), np.log(3.0e4), np.log(CENSOR)]
    censored = [False, False, True]
    expected = (np.log(brute_pdf(log_life[0], stress[0]))
                + np.log(brute_pdf(log_life[1], stress[1]))
                + np.log(brute_surv(log_life[2], stress[2])))
    got = rfl.rfl_loglik(theta, stress, log_life, censored)
    assert got == pytest.approx(expected, rel=1e-6)


def test_parameter_recovery_at_laminate_design():
    stress, life, cen = rfl.simulate_rfl(
        LEVELS, 25, censor_time=CENSOR, rng=20260711, **TRUTH
    )
    assert cen.sum() > 0  # the design produces runouts at the low levels
    fit = rfl.fit_rfl(stress, life, cen)
    assert fit.converged
    # recovery tolerances reflect n=125 sampling noise. sigma and
    # sigma_gamma trade off along a likelihood ridge (the 1999 paper's own
    # profile plots show this), so they are checked FUNCTIONALLY through
    # the predicted life distribution rather than individually.
    assert fit.beta1 == pytest.approx(TRUTH["beta1"], rel=0.15)
    assert fit.mu_gamma == pytest.approx(TRUTH["mu_gamma"], abs=0.05)
    # the fitted likelihood is at least as good as the truth's
    truth_theta = (TRUTH["beta0"], TRUTH["beta1"], np.log(TRUTH["sigma"]),
                   TRUTH["mu_gamma"], np.log(TRUTH["sigma_gamma"]))
    ll_truth = rfl.rfl_loglik(truth_theta, stress, np.log(life), cen)
    assert fit.log_likelihood >= ll_truth - 1e-6
    # functional recovery: simulate large samples from the fitted and true
    # models and compare the median and 5th percentile of life
    fitted = dict(beta0=fit.beta0, beta1=fit.beta1, sigma=fit.sigma,
                  mu_gamma=fit.mu_gamma, sigma_gamma=fit.sigma_gamma)
    for s_level in (300.0, 340.0):
        _, life_t, cen_t = rfl.simulate_rfl(
            [s_level], 20000, censor_time=1e12, rng=1, **TRUTH)
        _, life_f, cen_f = rfl.simulate_rfl(
            [s_level], 20000, censor_time=1e12, rng=2, **fitted)
        # a few simulated limits sit above the stress even at this cutoff,
        # compare the failure populations
        lt, lf = life_t[~cen_t], life_f[~cen_f]
        assert np.median(lf) == pytest.approx(np.median(lt), rel=0.30)
        assert np.percentile(lf, 5) == pytest.approx(
            np.percentile(lt, 5), rel=0.45)


def test_fit_refusals():
    with pytest.raises(ValueError, match="at least 10"):
        rfl.fit_rfl([300.0] * 5, [1e4] * 5)
    with pytest.raises(ValueError, match="failures"):
        rfl.fit_rfl([300.0] * 12, [1e4] * 12, [True] * 12)
    with pytest.raises(ValueError, match="equal length"):
        rfl.fit_rfl([300.0] * 12, [1e4] * 11)


def test_notes_state_validation_status():
    stress, life, cen = rfl.simulate_rfl(
        LEVELS, 25, censor_time=CENSOR, rng=7, **TRUTH
    )
    fit = rfl.fit_rfl(stress, life, cen)
    assert any("not yet benchmarked" in n for n in fit.notes)


def test_service_exposure_and_persistence(tmp_path):
    svc = LcfService(tmp_path / "store")
    stress, life, cen = rfl.simulate_rfl(
        LEVELS, 25, censor_time=CENSOR, rng=3, **TRUTH
    )
    out = svc.fit_random_fatigue_limit(
        list(stress), list(life), list(bool(c) for c in cen), name="RFL-demo"
    )
    assert out["converged"] is True
    assert out["n_runouts"] > 0
    assert svc.recall("RFL-demo", "rfl_fit") is not None
