"""Random fatigue limit model, Pascual-Meeker normal-normal form.

The model: with stress amplitude ``s``, the specimen fatigue limit ``gamma``
varies unit to unit, ``V = log(gamma) ~ Normal(mu_gamma, sigma_gamma)``, and
given ``V`` the log life is

    W = log(N) | V  ~  Normal( beta0 + beta1 * log(s - gamma), sigma )

defined for ``s > gamma``. A specimen whose fatigue limit is at or above the
test stress never fails. Runouts are right-censored observations. The
marginal likelihood integrates over ``V`` (Gauss-Legendre quadrature), and
the five parameters are found by maximum likelihood.

Validation status, stated plainly: the fitter reproduces the published
Pascual and Meeker (Technometrics 41, 1999, 277-290) normal-normal fit of
the laminate-panel dataset exactly, log-likelihood -86.221 and parameters
matching their Table 1 to the digit (tests/test_rfl.py, data from the
public SMRD.data R package). The marginal likelihood is also cross-checked
against brute-force integration and the fitter recovers known parameters
from simulated data.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy import optimize
from scipy import stats as scistats

__all__ = ["RflFit", "rfl_loglik", "fit_rfl", "simulate_rfl"]

_NODES = 96  # Gauss-Legendre nodes for the marginal integral over V. The
             # laminate-panel fit is identical from 64 nodes up, 96 keeps a
             # margin for arbitrary user data while halving the fit time.


@dataclass
class RflFit:
    """Maximum-likelihood estimates of the random fatigue limit model."""

    beta0: float
    beta1: float
    sigma: float                 # sd of log life given V
    mu_gamma: float              # mean of log fatigue limit
    sigma_gamma: float           # sd of log fatigue limit
    log_likelihood: float
    n_failures: int
    n_runouts: int
    converged: bool
    notes: list[str] = field(default_factory=list)


def _quad_nodes(x: float, mu_g: float, sig_g: float, n: int = _NODES):
    """Gauss-Legendre nodes and weights on the effective support of V below x."""
    lo = mu_g - 10.0 * sig_g
    hi = min(x - 1e-12, mu_g + 10.0 * sig_g)
    if hi <= lo:
        return None, None  # essentially all fatigue limits sit above s
    z, w = np.polynomial.legendre.leggauss(n)
    v = 0.5 * (hi - lo) * z + 0.5 * (hi + lo)
    return v, 0.5 * (hi - lo) * w


_SQRT2PI = float(np.sqrt(2.0 * np.pi))
_SQRT2 = float(np.sqrt(2.0))


def _npdf(z):
    return np.exp(-0.5 * z * z) / _SQRT2PI


def _nsf(z):
    from scipy.special import erfc

    return 0.5 * erfc(z / _SQRT2)


def rfl_loglik(theta, stress, log_life, censored) -> float:
    """Marginal log likelihood of the normal-normal RFL model.

    ``theta`` is (beta0, beta1, log sigma, mu_gamma, log sigma_gamma).
    ``log_life`` uses natural logs. Runouts contribute their survival
    probability, including the probability that the fatigue limit is at or
    above the stress level. Vectorized per unique stress level.
    """
    b0, b1, ls, mg, lsg = theta
    sig, sig_g = np.exp(ls), np.exp(lsg)
    s_arr = np.asarray(stress, dtype=np.float64)
    w_arr = np.asarray(log_life, dtype=np.float64)
    c_arr = np.asarray(censored, dtype=bool)
    total = 0.0
    for s in np.unique(s_arr):
        at = s_arr == s
        x = np.log(s)
        v, wt = _quad_nodes(x, mg, sig_g)
        p_above = float(_nsf((x - mg) / sig_g))
        if v is None:
            # every specimen's limit is above s: failure impossible
            if np.any(at & ~c_arr):
                return -np.inf
            continue  # runouts here have probability ~1, log(1) = 0
        mu_w = b0 + b1 * np.log(s - np.exp(v))            # (nodes,)
        weight = wt * _npdf((v - mg) / sig_g) / sig_g     # (nodes,)
        z = (w_arr[at][:, None] - mu_w[None, :]) / sig    # (obs, nodes)
        like = np.where(
            c_arr[at],
            (weight[None, :] * _nsf(z)).sum(axis=1) + p_above,
            (weight[None, :] * _npdf(z)).sum(axis=1) / sig,
        )
        if not np.all(like > 0):
            return -np.inf
        total += float(np.log(like).sum())
    return total


def fit_rfl(
    stress,
    life,
    censored=None,
    *,
    life_is_log: bool = False,
) -> RflFit:
    """Fit the random fatigue limit model by maximum likelihood.

    ``stress`` are amplitudes (MPa or any consistent unit), ``life`` the
    lives (cycles or reversals, be consistent), ``censored`` flags runouts.
    Starting values come from a plain log-log regression plus a fatigue
    limit slightly below the lowest stress, then Nelder-Mead maximizes the
    marginal likelihood.
    """
    s = np.asarray(stress, dtype=np.float64)
    n_arr = np.asarray(life, dtype=np.float64)
    cen = (np.zeros(s.size, dtype=bool) if censored is None
           else np.asarray(censored, dtype=bool))
    if s.size != n_arr.size or s.size != cen.size:
        raise ValueError("stress, life, and censored must have equal length")
    if s.size < 10:
        raise ValueError(
            f"need at least 10 observations to fit 5 parameters, got {s.size}"
        )
    if not np.all(s > 0) or not np.all(n_arr > 0):
        raise ValueError("stress and life must be positive")
    if int((~cen).sum()) < 6:
        raise ValueError("need at least 6 failures for a meaningful fit")
    w = n_arr if life_is_log else np.log(n_arr)

    # starting values: fatigue limit below the lowest stress, then a
    # log-log regression of the failures against log(s - gamma0)
    gamma0 = 0.8 * float(s.min())
    xs = np.log(s[~cen] - gamma0)
    ws = w[~cen]
    b1_0, b0_0 = np.polyfit(xs, ws, 1)
    resid = ws - (b0_0 + b1_0 * xs)
    theta0 = np.array([
        b0_0, b1_0, np.log(max(resid.std(), 1e-2)),
        np.log(gamma0), np.log(0.1),
    ])

    def nll(theta):
        return -rfl_loglik(theta, s, w, cen)

    res = optimize.minimize(
        nll, theta0, method="Nelder-Mead",
        options={"maxiter": 4000, "xatol": 1e-6, "fatol": 1e-8},
    )
    res = optimize.minimize(
        nll, res.x, method="Nelder-Mead",
        options={"maxiter": 4000, "xatol": 1e-8, "fatol": 1e-10},
    )
    b0, b1, ls, mg, lsg = res.x
    notes = [
        "normal-normal random fatigue limit model, Pascual and Meeker, "
        "Technometrics 41 (1999) 277-290",
        "validated by exact reproduction of the published laminate-panel "
        "fit (log-likelihood -86.221) plus likelihood cross-check and "
        "simulated parameter recovery",
    ]
    if not res.success:
        notes.append(f"optimizer did not report convergence: {res.message}")
    return RflFit(
        beta0=float(b0), beta1=float(b1), sigma=float(np.exp(ls)),
        mu_gamma=float(mg), sigma_gamma=float(np.exp(lsg)),
        log_likelihood=float(-res.fun),
        n_failures=int((~cen).sum()), n_runouts=int(cen.sum()),
        converged=bool(res.success), notes=notes,
    )


def simulate_rfl(
    stress_levels,
    n_per_level: int,
    *,
    beta0: float,
    beta1: float,
    sigma: float,
    mu_gamma: float,
    sigma_gamma: float,
    censor_time: float,
    rng=None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Simulate an RFL test campaign, returning (stress, life, censored).

    Specimens whose fatigue limit is at or above their stress level, and
    failures beyond ``censor_time``, are censored at ``censor_time``.
    """
    rng = np.random.default_rng(rng)
    s_out, n_out, c_out = [], [], []
    for s in stress_levels:
        v = rng.normal(mu_gamma, sigma_gamma, size=n_per_level)
        for vi in v:
            gamma = np.exp(vi)
            if gamma >= s:
                s_out.append(s); n_out.append(censor_time); c_out.append(True)
                continue
            w = rng.normal(beta0 + beta1 * np.log(s - gamma), sigma)
            n = np.exp(w)
            if n >= censor_time:
                s_out.append(s); n_out.append(censor_time); c_out.append(True)
            else:
                s_out.append(s); n_out.append(n); c_out.append(False)
    return np.asarray(s_out), np.asarray(n_out), np.asarray(c_out)
