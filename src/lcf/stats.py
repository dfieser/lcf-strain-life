"""Statistical analysis of strain-life data, post-E739.

ASTM E739 was withdrawn in 2024 with no superseding standard. Its linearized
regression remains the de facto method and is implemented here (ADR-0010).
Life is the dependent variable: ``log10(N) = A + B log10(amplitude)``.

The module also implements the modern maximum-likelihood layer the ASTM
replacement effort points to, work item WK88010 and its technical basis,
Meeker, Escobar, Pascual et al., arXiv:2212.04550: censored fits that treat
runouts by likelihood instead of deletion, lognormal or Weibull life
scatter, observed-information standard errors, profile-likelihood design
bounds (Venzon and Moolgavkar 1988), a quantified comparison against the
delete-runouts legacy, and a censored nonlinear fit of the full strain-life
curve, which the linearized E739 method could not represent.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy import optimize
from scipy import stats as scistats

from . import fits as _fits
from . import life as _life

__all__ = [
    "LogLifeFit",
    "MlLogLifeFit",
    "MlStrainLifeFit",
    "fit_log_life",
    "predict_life",
    "confidence_interval",
    "prediction_interval",
    "owen_tolerance_factor",
    "basis_value",
    "design_life",
    "design_life_ml",
    "compare_runout_handling",
    "lack_of_fit",
    "fit_log_life_censored",
    "fit_strain_life_censored",
    "grubbs_test",
    "generalized_esd",
    "regression_diagnostics",
]

#: Reliability/confidence pairs for the MMPDS-style basis values.
BASIS_LEVELS = {"A": (0.99, 0.95), "B": (0.90, 0.95)}


@dataclass
class LogLifeFit:
    """Linear fit of log10(life) on log10(amplitude).

    ``amp_min``/``amp_max`` record the amplitude interval the fit actually
    used, so callers can flag predictions outside it. E739's own caveat is
    that the curve should not be extrapolated outside the interval of
    testing. NaN when the fit was built without that information.
    """

    slope: float            # B
    intercept: float        # A
    residual_std: float     # s, residual standard error in log10(life)
    n_points: int
    x_mean: float           # mean of log10(amplitude)
    sxx: float              # sum of squared deviations of log10(amplitude)
    r_squared: float
    amp_min: float = float("nan")
    amp_max: float = float("nan")


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
        amp_min=float(10.0 ** x.min()), amp_max=float(10.0 ** x.max()),
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
            n_out = int(st["step"])
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


def basis_value(*, mean: float, std: float, n: int, basis: str = "B") -> dict:
    """A- or B-basis value: the one-sided lower tolerance bound ``mean - k*std``.

    Following MMPDS practice, the B-basis is the 95 percent confidence lower
    bound on the 10th percentile (90 percent reliability) and the A-basis on
    the 1st percentile (99 percent reliability). ``k`` is the exact Owen
    one-sided tolerance factor from the noncentral t. Assumes the property is
    normally distributed in the analyzed units, fit and check the sample
    before relying on the bound.
    """
    key = str(basis).strip().upper()
    if key not in BASIS_LEVELS:
        raise ValueError(
            f"unknown basis {basis!r}. Use 'A' (99% reliability, 95% "
            "confidence) or 'B' (90% reliability, 95% confidence), or call "
            "owen_tolerance_factor directly for other levels."
        )
    if n < 2:
        raise ValueError("need n >= 2 samples for a basis value")
    reliability, confidence = BASIS_LEVELS[key]
    k = owen_tolerance_factor(int(n), reliability, confidence)
    return {
        "basis": key,
        "reliability": reliability,
        "confidence": confidence,
        "n": int(n),
        "mean": float(mean),
        "std": float(std),
        "k": k,
        "value": float(mean) - k * float(std),
    }


def lack_of_fit(amplitude, life) -> dict:
    """ASTM E739-style lack-of-fit F test for the linearized life regression.

    Requires replicate tests: at least one amplitude level tested more than
    once, and at least three distinct levels. Partitions the residual sum of
    squares into pure error (within replicate levels) and lack of fit
    (between the level means and the regression line), in log10 space with
    life as the dependent variable. A significant F says the straight line
    does not represent the data, whatever the r squared says.
    """
    x, y = _xy(amplitude, life)
    levels, inverse = np.unique(x, return_inverse=True)
    m = int(levels.size)
    n = int(x.size)
    if m < 3:
        return {"available": False,
                "reason": "need at least 3 distinct amplitude levels"}
    if n <= m:
        return {"available": False,
                "reason": "need replicate tests (a repeated amplitude level) "
                          "to separate pure error from lack of fit"}

    fit = fit_log_life(10.0 ** x, 10.0 ** y)
    y_hat = fit.intercept + fit.slope * x
    level_means = np.array([y[inverse == j].mean() for j in range(m)])
    ss_pure = float(np.sum((y - level_means[inverse]) ** 2))
    ss_lof = float(np.sum((level_means[inverse] - y_hat) ** 2))
    df_lof = m - 2
    df_pure = n - m
    if ss_pure <= 0.0:
        return {"available": False,
                "reason": "replicates are identical, pure error is zero"}
    f_stat = (ss_lof / df_lof) / (ss_pure / df_pure)
    p = float(scistats.f.sf(f_stat, df_lof, df_pure))
    return {
        "available": True,
        "f_statistic": float(f_stat),
        "df_lack_of_fit": int(df_lof),
        "df_pure_error": int(df_pure),
        "ss_lack_of_fit": ss_lof,
        "ss_pure_error": ss_pure,
        "p_value": p,
        "linear_ok_at_5pct": bool(p >= 0.05),
    }


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


@dataclass
class MlLogLifeFit(LogLifeFit):
    """Censored maximum-likelihood fit with uncertainty information.

    Extends :class:`LogLifeFit`. ``distribution`` is ``lognormal``, normal
    scatter of log10 life, or ``weibull``, smallest-extreme-value scatter of
    log10 life, which is a Weibull life distribution. ``residual_std`` is the
    ML scale parameter of the chosen distribution. Standard errors come from
    the observed information, the inverse Hessian of the negative log
    likelihood at the optimum, and are NaN when that matrix is not
    invertible. ``cov`` orders the parameters (intercept, slope, log sigma).
    """

    distribution: str = "lognormal"
    n_censored: int = 0
    loglik: float = float("nan")
    aic: float = float("nan")
    converged: bool = False
    se_intercept: float = float("nan")
    se_slope: float = float("nan")
    se_log_sigma: float = float("nan")
    cov: list[list[float]] | None = field(default=None, repr=False)


def _dist_funcs(distribution: str):
    """logpdf, logsf, and ppf of the standardized life-scatter distribution."""
    if distribution == "lognormal":
        d = scistats.norm
    elif distribution == "weibull":
        # smallest extreme value on log life is a Weibull life distribution
        d = scistats.gumbel_l
    else:
        raise ValueError(
            f"unknown distribution {distribution!r}, use 'lognormal' or "
            "'weibull'"
        )
    return d.logpdf, d.logsf, d.ppf


def _censored_xy(amplitude, life, censored):
    a = np.asarray(amplitude, dtype=np.float64)
    n = np.asarray(life, dtype=np.float64)
    cens = np.asarray(censored, dtype=bool)
    if not (a.shape == n.shape == cens.shape):
        raise ValueError("amplitude, life, and censored must have equal length")
    ok = np.isfinite(a) & np.isfinite(n) & (a > 0) & (n > 0)
    a, n, cens = a[ok], n[ok], cens[ok]
    if a.size < 3:
        raise ValueError("need at least 3 points for a censored regression")
    return a, np.log10(a), np.log10(n), cens


def _censored_nll(x, y, cens, logpdf, logsf):
    def nll(p):
        b0, b1, log_sigma = p
        sigma = np.exp(log_sigma)
        z = (y - (b0 + b1 * x)) / sigma
        ll = np.where(cens, logsf(z), logpdf(z) - np.log(sigma))
        return -float(np.sum(ll))

    return nll


def _num_hessian(f, x, *, rel_step: float = 1e-4):
    """Central-difference Hessian, None when any entry is not finite."""
    x = np.asarray(x, dtype=np.float64)
    k = x.size
    h = rel_step * np.maximum(np.abs(x), 1.0)
    hess = np.empty((k, k))
    for i in range(k):
        for j in range(i, k):
            ei = np.zeros(k)
            ej = np.zeros(k)
            ei[i] = h[i]
            ej[j] = h[j]
            val = (
                f(x + ei + ej) - f(x + ei - ej)
                - f(x - ei + ej) + f(x - ei - ej)
            ) / (4.0 * h[i] * h[j])
            hess[i, j] = hess[j, i] = val
    if not np.all(np.isfinite(hess)):
        return None
    return hess


def _cov_and_ses(nll, theta):
    """Observed-information covariance and standard errors, NaN on failure."""
    k = len(theta)
    ses = np.full(k, np.nan)
    hess = _num_hessian(nll, theta)
    cov = None
    if hess is not None:
        try:
            cov = np.linalg.inv(hess)
        except np.linalg.LinAlgError:
            cov = None
    if cov is not None:
        diag = np.diagonal(cov)
        with np.errstate(invalid="ignore"):
            ses = np.where(diag > 0, np.sqrt(np.abs(diag)), np.nan)
        if not np.all(np.isfinite(np.asarray(cov))):
            cov = None
    return cov, ses


def fit_log_life_censored(
    amplitude, life, censored, *, distribution: str = "lognormal"
) -> MlLogLifeFit:
    """Maximum-likelihood fit with right-censored (runout) observations.

    Observed lives contribute the density of log10(N) about the line,
    runouts contribute the survival probability that the true life exceeds
    the observed value. Runouts are never deleted. ``distribution`` selects
    the life scatter model: ``lognormal`` (default) or ``weibull``. Returns
    a :class:`MlLogLifeFit` whose ``residual_std`` is the ML scale and which
    carries observed-information standard errors, the log likelihood, and
    AIC. Method per Meeker, Escobar, Pascual et al., arXiv:2212.04550, the
    technical basis of ASTM work item WK88010.
    """
    logpdf, logsf, _ = _dist_funcs(distribution)
    a, x, y, cens = _censored_xy(amplitude, life, censored)

    # seed from OLS on the observed (non-censored) points
    seed = fit_log_life(a[~cens], 10.0 ** y[~cens]) if (~cens).sum() >= 3 else None
    p0 = (
        [seed.intercept, seed.slope, np.log(max(seed.residual_std, 1e-3))]
        if seed else [float(np.mean(y)), 0.0, np.log(0.1)]
    )

    nll = _censored_nll(x, y, cens, logpdf, logsf)
    res = optimize.minimize(nll, p0, method="Nelder-Mead",
                            options={"xatol": 1e-8, "fatol": 1e-8, "maxiter": 5000})
    if not np.all(np.isfinite(res.x)) or not np.isfinite(nll(res.x)):
        raise ValueError(f"censored MLE failed to produce a finite fit: {res.message}")
    b0, b1, log_sigma = res.x
    xbar = float(np.mean(x))
    sxx = float(np.sum((x - xbar) ** 2))
    min_nll = float(nll(res.x))
    cov, ses = _cov_and_ses(nll, res.x)
    return MlLogLifeFit(
        slope=float(b1), intercept=float(b0), residual_std=float(np.exp(log_sigma)),
        n_points=int(x.size), x_mean=xbar, sxx=sxx, r_squared=float("nan"),
        amp_min=float(a.min()), amp_max=float(a.max()),
        distribution=distribution, n_censored=int(cens.sum()),
        loglik=-min_nll, aic=2.0 * 3 + 2.0 * min_nll,
        converged=bool(res.success),
        se_intercept=float(ses[0]), se_slope=float(ses[1]),
        se_log_sigma=float(ses[2]),
        cov=None if cov is None else [[float(v) for v in row] for row in cov],
    )


def design_life_ml(
    amplitude, life, censored, *,
    at_amplitude: float,
    reliability: float = 0.90,
    confidence: float = 0.90,
    distribution: str = "lognormal",
    method: str = "profile",
) -> dict:
    """One-sided lower confidence bound on the life quantile, censored ML.

    The modern replacement for the Owen tolerance factor when runouts are
    present. The Owen factor assumes a complete normal sample, maximum
    likelihood with censoring does not. The bound is on the ``reliability``
    quantile of life at ``at_amplitude``, at the given one-sided
    ``confidence``. ``method`` is ``profile`` (default), inverting the
    likelihood ratio per Venzon and Moolgavkar 1988, or ``wald``, the delta
    method on the observed information. Profile bounds keep their meaning at
    small samples where Wald intervals go symmetric and optimistic. Aligned
    with the framework of Meeker, Escobar, Pascual et al., arXiv:2212.04550,
    behind ASTM work item WK88010.
    """
    if method not in ("profile", "wald"):
        raise ValueError(f"unknown method {method!r}, use 'profile' or 'wald'")
    if not 0.0 < reliability < 1.0:
        raise ValueError("reliability must be in (0, 1)")
    if not 0.0 < confidence < 1.0:
        raise ValueError("confidence must be in (0, 1)")
    fit = fit_log_life_censored(
        amplitude, life, censored, distribution=distribution
    )
    logpdf, logsf, ppf = _dist_funcs(distribution)
    _, x, y, cens = _censored_xy(amplitude, life, censored)
    nll = _censored_nll(x, y, cens, logpdf, logsf)

    x0 = float(np.log10(at_amplitude))
    z_p = float(ppf(1.0 - reliability))
    z_50 = float(ppf(0.5))
    sigma = fit.residual_std
    q_hat = fit.intercept + fit.slope * x0 + z_p * sigma
    median = fit.intercept + fit.slope * x0 + z_50 * sigma
    nll_hat = -fit.loglik
    z_conf = float(scistats.norm.ppf(confidence))

    se_q = float("nan")
    if fit.cov is not None:
        grad = np.array([1.0, x0, z_p * sigma])
        var_q = float(grad @ np.asarray(fit.cov) @ grad)
        if var_q > 0:
            se_q = float(np.sqrt(var_q))

    warnings: list[dict] = []
    if np.isfinite(fit.amp_min) and not (
        fit.amp_min <= at_amplitude <= fit.amp_max
    ):
        warnings.append({
            "code": "extrapolation",
            "message": (
                f"at_amplitude {at_amplitude:g} lies outside the fitted "
                f"amplitude interval [{fit.amp_min:g}, {fit.amp_max:g}], "
                "treat the bound as unreliable."
            ),
        })

    if method == "wald":
        if not np.isfinite(se_q):
            raise ValueError(
                "Wald bound unavailable, the observed information matrix "
                "is not invertible. Use method='profile'."
            )
        q_low = q_hat - z_conf * se_q
    else:
        def profile_nll(q: float) -> float:
            def inner(p2):
                b1, log_sigma = p2
                s = np.exp(log_sigma)
                b0 = q - b1 * x0 - z_p * s
                return nll((b0, b1, log_sigma))

            r = optimize.minimize(
                inner, [fit.slope, np.log(max(sigma, 1e-8))],
                method="Nelder-Mead",
                options={"xatol": 1e-9, "fatol": 1e-9, "maxiter": 4000},
            )
            return float(r.fun)

        target = nll_hat + 0.5 * z_conf**2

        def g(q: float) -> float:
            return profile_nll(q) - target

        step = se_q if np.isfinite(se_q) and se_q > 0 else max(sigma, 0.05)
        lo = q_hat - z_conf * step
        expansions = 0
        while g(lo) < 0.0 and expansions < 60:
            lo -= step
            expansions += 1
        if g(lo) < 0.0:
            raise ValueError(
                "profile likelihood bound did not bracket, the likelihood "
                "is too flat. Check the data or use method='wald'."
            )
        q_low = float(optimize.brentq(g, lo, q_hat, xtol=1e-8))

    return {
        "design_life": float(10.0 ** q_low),
        "quantile_life": float(10.0 ** q_hat),
        "median_life": float(10.0 ** median),
        "reliability": reliability,
        "confidence": confidence,
        "method": method,
        "distribution": distribution,
        "se_quantile_log10": se_q,
        "n_points": fit.n_points,
        "n_censored": fit.n_censored,
        "converged": fit.converged,
        "warnings": warnings,
    }


def compare_runout_handling(
    amplitude, life, censored, *,
    at_amplitude: float,
    reliability: float = 0.90,
    confidence: float = 0.90,
) -> dict:
    """Quantify what deleting runouts does to the design curve.

    Fits the same data three ways and evaluates each at ``at_amplitude``:
    ``naive``, runouts deleted, OLS with the Owen tolerance factor, the
    legacy practice. ``ml_owen``, censored lognormal ML with the Owen factor
    applied to the ML sigma, an approximation because the factor assumes a
    complete sample. ``ml_profile``, censored ML with the
    profile-likelihood bound, the modern method. The ``design_life_ratio``
    entries divide the alternatives by the naive value, whether deletion was
    optimistic or pessimistic depends on the data, the point is that the
    difference is quantified instead of hidden.
    """
    a = np.asarray(amplitude, dtype=np.float64)
    n = np.asarray(life, dtype=np.float64)
    cens = np.asarray(censored, dtype=bool)
    out: dict = {
        "at_amplitude": float(at_amplitude),
        "reliability": reliability,
        "confidence": confidence,
        "n_points": int(a.size),
        "n_censored": int(cens.sum()),
    }

    if (~cens).sum() >= 3:
        naive_fit = fit_log_life(a[~cens], n[~cens])
        out["naive"] = {
            "note": "runouts deleted, OLS, Owen factor, legacy practice",
            "median_life": float(predict_life(naive_fit, at_amplitude)),
            "sigma_log10": naive_fit.residual_std,
            "design_life": design_life(
                naive_fit, at_amplitude,
                reliability=reliability, confidence=confidence,
            ),
        }
    else:
        out["naive"] = {
            "note": "unavailable, fewer than 3 uncensored points",
        }

    ml_fit = fit_log_life_censored(a, n, cens)
    k = owen_tolerance_factor(ml_fit.n_points, reliability, confidence)
    x0 = float(np.log10(at_amplitude))
    mu = ml_fit.intercept + ml_fit.slope * x0
    out["ml_owen"] = {
        "note": (
            "censored ML, Owen factor on the ML sigma, approximate, the "
            "factor assumes a complete sample"
        ),
        "median_life": float(10.0 ** mu),
        "sigma_log10": ml_fit.residual_std,
        "design_life": float(10.0 ** (mu - k * ml_fit.residual_std)),
    }

    ml = design_life_ml(
        a, n, cens, at_amplitude=at_amplitude,
        reliability=reliability, confidence=confidence,
    )
    out["ml_profile"] = {
        "note": "censored ML, profile-likelihood bound, modern method",
        "median_life": ml["median_life"],
        "sigma_log10": ml_fit.residual_std,
        "design_life": ml["design_life"],
    }

    naive_design = out["naive"].get("design_life")
    if naive_design:
        out["design_life_ratio"] = {
            "ml_owen_over_naive": out["ml_owen"]["design_life"] / naive_design,
            "ml_profile_over_naive": ml["design_life"] / naive_design,
        }
    out["warnings"] = ml["warnings"]
    return out


@dataclass
class MlStrainLifeFit:
    """Censored nonlinear ML fit of the full total strain-life curve.

    Constants follow the project conventions, b and c negative,
    ``sigma_log10_life`` is the lognormal scatter of log10 life about the
    curve. Standard errors come from the observed information with the delta
    method back to natural units, NaN when unavailable.
    """

    sigma_f: float
    b: float
    eps_f: float
    c: float
    E: float
    sigma_log10_life: float
    transition_reversals: float
    n_points: int
    n_censored: int
    loglik: float
    aic: float
    converged: bool
    se_sigma_f: float = float("nan")
    se_b: float = float("nan")
    se_eps_f: float = float("nan")
    se_c: float = float("nan")
    se_sigma_log10_life: float = float("nan")
    strain_min: float = float("nan")
    strain_max: float = float("nan")


def _strain_life_mu(strain, sigma_f, b, eps_f, c, E):
    """log10 of the curve life at each strain amplitude, clamped bracket."""
    out = np.empty(strain.size)
    for i, eps in enumerate(strain):
        out[i] = np.log10(_life.predict_reversals_from_total_strain(
            float(eps), sigma_f, b, eps_f, c, E,
        ))
    return out


def fit_strain_life_censored(
    total_strain_amp, reversals, censored=None, *,
    E: float,
    stress_amp=None,
    max_iter: int = 20000,
) -> MlStrainLifeFit:
    """Censored maximum-likelihood fit of the full strain-life curve.

    Fits ``sigma_f, b, eps_f, c`` and the lognormal scatter of log10 life
    directly on the combined curve, with runouts contributing survival
    probability. ASTM E739 restricted itself to linearized fits and could
    not represent the combined curve or runouts, the ASTM replacement work
    item WK88010 names nonlinear regression and censored data as the point
    of the rewrite, method per Meeker, Escobar, Pascual et al.,
    arXiv:2212.04550. Lognormal life scatter only.

    ``stress_amp`` is optional and used only to seed the optimizer through
    the standard linear fits. Without it the seed is heuristic. The sign
    conventions are enforced by parametrization, the fitted b and c are
    always negative. Needs at least 5 points and at least 3 uncensored.

    Identifiability caveat, stated because it is intrinsic to the model:
    the four constants of the combined curve are strongly correlated when
    fitted from total strain alone, especially the elastic pair, and their
    standard errors can exceed the estimates. The fitted curve itself is
    well determined inside the tested strain range. Treat the constants as
    curve parameters, and read the standard errors before quoting any of
    them individually. Branch-wise linear fits from separated elastic and
    plastic strains remain the method of choice when stress amplitudes are
    available, this fit is for censored data and direct curve inference.
    """
    strain = np.asarray(total_strain_amp, dtype=np.float64)
    rev = np.asarray(reversals, dtype=np.float64)
    cens = (np.zeros(strain.shape, dtype=bool) if censored is None
            else np.asarray(censored, dtype=bool))
    if not (strain.shape == rev.shape == cens.shape):
        raise ValueError(
            "total_strain_amp, reversals, and censored must have equal length"
        )
    ok = np.isfinite(strain) & np.isfinite(rev) & (strain > 0) & (rev > 0)
    strain, rev, cens = strain[ok], rev[ok], cens[ok]
    if strain.size < 5:
        raise ValueError(
            "need at least 5 points for the 5-parameter censored curve fit"
        )
    if (~cens).sum() < 3:
        raise ValueError("need at least 3 uncensored points")
    y = np.log10(rev)

    # Seed constants: proper linear fits when stress amplitudes are given,
    # otherwise a heuristic from the log-log OLS line with textbook-range
    # starting exponents.
    if stress_amp is not None:
        s = np.asarray(stress_amp, dtype=np.float64)[ok]
        base = _fits.fit_strain_life(
            strain[~cens], s[~cens], rev[~cens], E,
        )
        seed = (base.basquin.sigma_f, base.basquin.b,
                base.coffin_manson.eps_f, base.coffin_manson.c)
    else:
        ols = fit_log_life(strain[~cens], rev[~cens])

        def eps_at(two_n: float) -> float:
            return 10.0 ** ((np.log10(two_n) - ols.intercept) / ols.slope)

        b0, c0 = -0.09, -0.6
        seed = (
            E * eps_at(1.0e6) * (1.0e6) ** (-b0),
            b0,
            eps_at(1.0e2) * (1.0e2) ** (-c0),
            c0,
        )

    def decode(theta):
        t = np.clip(theta, -40.0, 40.0)
        return (float(np.exp(t[0])), float(-np.exp(t[1])),
                float(np.exp(t[2])), float(-np.exp(t[3])),
                float(np.exp(t[4])))

    mu_seed = _strain_life_mu(strain, seed[0], seed[1], seed[2], seed[3], E)
    resid = (y - mu_seed)[~cens]
    sigma0 = max(float(np.std(resid)) if resid.size else 0.1, 1e-3)
    theta0 = np.array([
        np.log(seed[0]), np.log(-seed[1]),
        np.log(seed[2]), np.log(-seed[3]), np.log(sigma0),
    ])

    def nll(theta):
        sigma_f, b, eps_f, c, sigma = decode(theta)
        try:
            mu = _strain_life_mu(strain, sigma_f, b, eps_f, c, E)
        except ValueError:
            return 1.0e10
        z = (y - mu) / sigma
        ll = np.where(
            cens,
            scistats.norm.logsf(z),
            scistats.norm.logpdf(z) - np.log(sigma),
        )
        total = float(np.sum(ll))
        return -total if np.isfinite(total) else 1.0e10

    res = optimize.minimize(
        nll, theta0, method="Nelder-Mead",
        options={"xatol": 1e-8, "fatol": 1e-8, "maxiter": max_iter,
                 "maxfev": max_iter},
    )
    if not np.all(np.isfinite(res.x)) or nll(res.x) >= 1.0e10:
        raise ValueError(
            f"censored strain-life MLE failed to converge: {res.message}"
        )
    sigma_f, b, eps_f, c, sigma = decode(res.x)
    min_nll = float(nll(res.x))
    cov, ses = _cov_and_ses(nll, res.x)
    # delta method from log parametrization back to natural units
    se_nat = [
        sigma_f * ses[0], abs(b) * ses[1], eps_f * ses[2],
        abs(c) * ses[3], sigma * ses[4],
    ]
    return MlStrainLifeFit(
        sigma_f=sigma_f, b=b, eps_f=eps_f, c=c, E=float(E),
        sigma_log10_life=sigma,
        transition_reversals=float(
            _fits.transition_reversals(sigma_f, b, eps_f, c, E)
        ),
        n_points=int(strain.size), n_censored=int(cens.sum()),
        loglik=-min_nll, aic=2.0 * 5 + 2.0 * min_nll,
        converged=bool(res.success),
        se_sigma_f=float(se_nat[0]), se_b=float(se_nat[1]),
        se_eps_f=float(se_nat[2]), se_c=float(se_nat[3]),
        se_sigma_log10_life=float(se_nat[4]),
        strain_min=float(strain.min()), strain_max=float(strain.max()),
    )
