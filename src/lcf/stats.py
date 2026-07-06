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
    "grubbs_test",
    "generalized_esd",
    "regression_diagnostics",
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


def grubbs_test(values, *, alpha: float = 0.05) -> dict:
    """Two-sided Grubbs test for a single outlier in a normal sample.

    Grubbs, Technometrics 11 (1969) 1-21, with the critical value in the form
    given by the NIST/SEMATECH e-Handbook, section 1.3.5.17.1. Returns the
    statistic, the critical value, the index of the most extreme point, and
    whether it is flagged at the given significance level.
    """
    x = np.asarray(values, dtype=np.float64)
    if x.size < 3:
        raise ValueError("the Grubbs test needs at least 3 values")
    if not np.all(np.isfinite(x)):
        raise ValueError("values must be finite")
    n = x.size
    s = float(np.std(x, ddof=1))
    if s == 0:
        return {"statistic": 0.0, "critical": float("nan"),
                "index": 0, "outlier": False}
    dev = np.abs(x - float(np.mean(x)))
    idx = int(np.argmax(dev))
    g = float(dev[idx] / s)
    t = scistats.t.ppf(1.0 - alpha / (2.0 * n), n - 2)
    crit = float((n - 1) / np.sqrt(n) * np.sqrt(t**2 / (n - 2 + t**2)))
    return {"statistic": g, "critical": crit, "index": idx,
            "outlier": bool(g > crit)}


def generalized_esd(values, *, max_outliers: int, alpha: float = 0.05) -> dict:
    """Generalized extreme studentized deviate test for up to k outliers.

    Rosner, Technometrics 25 (1983) 165-172, following the NIST/SEMATECH
    e-Handbook recipe, section 1.3.5.17.3. Returns the indices of the flagged
    outliers (possibly empty) and the per-step statistics. The approximation
    is intended for roughly n >= 15, smaller samples get a warning entry.
    """
    x = np.asarray(values, dtype=np.float64)
    if not np.all(np.isfinite(x)):
        raise ValueError("values must be finite")
    n = x.size
    if max_outliers < 1:
        raise ValueError("max_outliers must be at least 1")
    if n - max_outliers < 3:
        raise ValueError("too few values for the requested max_outliers")
    warnings = []
    if n < 15:
        warnings.append(
            "the generalized ESD approximation is intended for n >= 15, "
            "interpret small-sample results with caution"
        )
    remaining = list(range(n))
    steps = []
    removed: list[int] = []
    for i in range(1, max_outliers + 1):
        sub = x[remaining]
        s = float(np.std(sub, ddof=1))
        if s == 0:
            break
        dev = np.abs(sub - float(np.mean(sub)))
        j = int(np.argmax(dev))
        r_i = float(dev[j] / s)
        n_i = len(remaining)
        p = 1.0 - alpha / (2.0 * n_i)
        t = scistats.t.ppf(p, n_i - 2)
        lam = float((n_i - 1) * t / np.sqrt((n_i - 2 + t**2) * n_i))
        steps.append({"step": i, "statistic": r_i, "critical": lam,
                      "index": remaining[j]})
        removed.append(remaining[j])
        remaining.pop(j)
    n_out = 0
    for st in steps:
        if st["statistic"] > st["critical"]:
            n_out = st["step"]
    return {"outlier_indices": sorted(removed[:n_out]), "steps": steps,
            "warnings": warnings}


def regression_diagnostics(amplitude, life, *, alpha: float = 0.05) -> dict:
    """Influence diagnostics for the log-log life regression.

    Computes leverage, internally and externally studentized residuals, and
    Cook's distance (Cook, Technometrics 19 (1977) 15-18) for each point of
    the ``log10(N) = A + B log10(amplitude)`` fit. A point is flagged when its
    externally studentized residual exceeds the Bonferroni-corrected t
    critical value (the standard mean-shift outlier test in regression), or
    when Cook's distance exceeds 4/n, a common screening threshold.
    """
    x, y = _xy(amplitude, life)
    fit = fit_log_life(amplitude, life)
    n = x.size
    yhat = fit.intercept + fit.slope * x
    e = y - yhat
    h = 1.0 / n + (x - fit.x_mean) ** 2 / fit.sxx
    s = fit.residual_std
    with np.errstate(divide="ignore", invalid="ignore"):
        student = e / (s * np.sqrt(1.0 - h))
        # externally studentized (delete-one) residuals, p = 2 parameters
        ext = student * np.sqrt(
            np.maximum(n - 3.0, 1e-12) / np.maximum(n - 2.0 - student**2, 1e-12)
        )
        cooks = e**2 / (2.0 * s**2) * h / (1.0 - h) ** 2
    cooks_thresh = 4.0 / n
    t_crit = float(scistats.t.ppf(1.0 - alpha / (2.0 * n), max(n - 3, 1)))
    flagged = [
        int(i) for i in range(n)
        if (np.isfinite(cooks[i]) and cooks[i] > cooks_thresh)
        or (np.isfinite(ext[i]) and abs(ext[i]) > t_crit)
    ]
    return {
        "leverage": [float(v) for v in h],
        "studentized_residuals": [float(v) for v in student],
        "external_studentized_residuals": [float(v) for v in ext],
        "cooks_distance": [float(v) for v in cooks],
        "cooks_threshold": cooks_thresh,
        "t_critical": t_crit,
        "influential_indices": flagged,
    }


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
