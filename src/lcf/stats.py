"""Statistical analysis of strain-life data, post-E739.

ASTM E739 was withdrawn in 2024 with no superseding standard, so its linearized
regression remains the de facto method and is what this module implements
(ADR-0010). Life is the dependent variable: ``log10(N) = A + B log10(amplitude)``.

Provides the regression fit, confidence and prediction intervals, one-sided
tolerance design curves through the Owen factor, and a maximum-likelihood fit
that handles right-censored runouts instead of deleting them.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import optimize
from scipy import stats as scistats

__all__ = [
    "LogLifeFit",
    "fit_log_life",
    "predict_life",
    "confidence_interval",
    "prediction_interval",
    "owen_tolerance_factor",
    "design_life",
    "fit_log_life_censored",
]


@dataclass
class LogLifeFit:
    """Linear fit of log10(life) on log10(amplitude)."""

    slope: float            # B
    intercept: float        # A
    residual_std: float     # s, residual standard error in log10(life)
    n_points: int
    x_mean: float           # mean of log10(amplitude)
    sxx: float              # sum of squared deviations of log10(amplitude)
    r_squared: float


def _xy(amplitude, life):
    a = np.asarray(amplitude, dtype=np.float64)
    n = np.asarray(life, dtype=np.float64)
    mask = np.isfinite(a) & np.isfinite(n) & (a > 0) & (n > 0)
    if int(mask.sum()) < 3:
        raise ValueError("need at least 3 positive finite points for a regression")
    return np.log10(a[mask]), np.log10(n[mask])


def fit_log_life(amplitude, life) -> LogLifeFit:
    """Fit ``log10(N) = A + B log10(amplitude)`` by ordinary least squares."""
    x, y = _xy(amplitude, life)
    n = x.size
    xbar = float(np.mean(x))
    sxx = float(np.sum((x - xbar) ** 2))
    if sxx == 0:
        raise ValueError(
            "need at least 2 distinct amplitudes to fit a regression, all "
            "amplitudes are equal (Sxx is zero)"
        )
    res = scistats.linregress(x, y)
    yhat = res.intercept + res.slope * x
    sse = float(np.sum((y - yhat) ** 2))
    s = np.sqrt(sse / (n - 2)) if n > 2 else float("nan")
    return LogLifeFit(
        slope=float(res.slope), intercept=float(res.intercept),
        residual_std=float(s), n_points=int(n), x_mean=xbar, sxx=sxx,
        r_squared=float(res.rvalue**2),
    )


def predict_life(fit: LogLifeFit, amplitude):
    """Median (50% reliability) life at a given amplitude."""
    x = np.log10(np.asarray(amplitude, dtype=np.float64))
    return 10.0 ** (fit.intercept + fit.slope * x)


def _band(fit: LogLifeFit, amplitude, confidence, kind):
    x = np.log10(np.asarray(amplitude, dtype=np.float64))
    yhat = fit.intercept + fit.slope * x
    t = scistats.t.ppf(0.5 * (1.0 + confidence), df=fit.n_points - 2)
    var = 1.0 / fit.n_points + (x - fit.x_mean) ** 2 / fit.sxx
    if kind == "prediction":
        var = 1.0 + var
    hw = t * fit.residual_std * np.sqrt(var)
    return 10.0 ** (yhat - hw), 10.0 ** (yhat + hw)


def confidence_interval(fit: LogLifeFit, amplitude, confidence: float = 0.95):
    """Two-sided confidence interval on the mean life line, as (low, high)."""
    return _band(fit, amplitude, confidence, "confidence")


def prediction_interval(fit: LogLifeFit, amplitude, confidence: float = 0.95):
    """Two-sided prediction interval for a single future life, as (low, high)."""
    return _band(fit, amplitude, confidence, "prediction")


def owen_tolerance_factor(n: int, reliability: float = 0.90, confidence: float = 0.90) -> float:
    """One-sided normal tolerance factor k (Owen), via the noncentral t.

    ``k = nct.ppf(confidence, df=n-1, nc=z_p*sqrt(n)) / sqrt(n)`` with
    ``z_p = norm.ppf(reliability)``. This is the standard one-sided tolerance
    factor and matches published tables, for example k(n=10, R90, C95)=2.355.
    """
    if n < 2:
        raise ValueError("need n >= 2 for a tolerance factor")
    z_p = scistats.norm.ppf(reliability)
    nc = z_p * np.sqrt(n)
    return float(scistats.nct.ppf(confidence, df=n - 1, nc=nc) / np.sqrt(n))


def design_life(
    fit: LogLifeFit, amplitude, *, reliability: float = 0.90, confidence: float = 0.90
) -> float:
    """Design (R-C) life at an amplitude: ``mean - k*s`` in log10 life.

    Uses the Owen one-sided tolerance factor for the given reliability and
    confidence, for example R90C90. Returns the lower-bound life.
    """
    x = np.log10(float(amplitude))
    yhat = fit.intercept + fit.slope * x
    k = owen_tolerance_factor(fit.n_points, reliability, confidence)
    return float(10.0 ** (yhat - k * fit.residual_std))


def fit_log_life_censored(amplitude, life, censored) -> LogLifeFit:
    """Maximum-likelihood fit with right-censored (runout) observations.

    Observed lives contribute the normal density of log10(N) about the line,
    runouts contribute the survival probability that the true life exceeds the
    observed value. Runouts are never deleted. Returns a :class:`LogLifeFit`
    whose ``residual_std`` is the MLE sigma.
    """
    a = np.asarray(amplitude, dtype=np.float64)
    n = np.asarray(life, dtype=np.float64)
    cens = np.asarray(censored, dtype=bool)
    ok = np.isfinite(a) & np.isfinite(n) & (a > 0) & (n > 0)
    a, n, cens = a[ok], n[ok], cens[ok]
    x = np.log10(a)
    y = np.log10(n)
    if x.size < 3:
        raise ValueError("need at least 3 points for a censored regression")

    # seed from OLS on the observed (non-censored) points
    seed = fit_log_life(a[~cens], n[~cens]) if (~cens).sum() >= 3 else None
    p0 = (
        [seed.intercept, seed.slope, np.log(max(seed.residual_std, 1e-3))]
        if seed else [float(np.mean(y)), 0.0, np.log(0.1)]
    )

    def nll(p):
        b0, b1, log_sigma = p
        sigma = np.exp(log_sigma)
        mu = b0 + b1 * x
        z = (y - mu) / sigma
        ll = np.where(
            cens,
            scistats.norm.logsf(z),                 # P(true life > observed)
            scistats.norm.logpdf(z) - np.log(sigma),
        )
        return -float(np.sum(ll))

    res = optimize.minimize(nll, p0, method="Nelder-Mead",
                            options={"xatol": 1e-8, "fatol": 1e-8, "maxiter": 5000})
    if not np.all(np.isfinite(res.x)) or not np.isfinite(nll(res.x)):
        raise ValueError(f"censored MLE failed to produce a finite fit: {res.message}")
    b0, b1, log_sigma = res.x
    xbar = float(np.mean(x))
    sxx = float(np.sum((x - xbar) ** 2))
    return LogLifeFit(
        slope=float(b1), intercept=float(b0), residual_std=float(np.exp(log_sigma)),
        n_points=int(x.size), x_mean=xbar, sxx=sxx, r_squared=float("nan"),
    )
