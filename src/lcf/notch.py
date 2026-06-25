"""Notch effects and the local-strain approach.

Turn a nominal stress at a notch into the local notch stress and strain using
Neuber's rule or Glinka's equivalent strain energy density rule, both solved on
the cyclic Ramberg-Osgood curve fitted in Phase 1. From the local strain
amplitude the strain-life solver gives notch life.

Neuber is the default and tends to overestimate local strain, so it is
conservative. Glinka tends to underestimate, and the measured strain usually
lies between the two (ADR-0010). Validated against the SAE 1005 worked example
(Golden E), see docs/design/IMPLEMENTATION_REFERENCE_PHASE2.md section 2a.5.
"""

from __future__ import annotations

import numpy as np
from scipy import optimize

from .life import predict_reversals_from_total_strain

__all__ = [
    "ramberg_osgood_strain",
    "neuber_local",
    "neuber_local_range",
    "glinka_local",
    "kf_peterson",
    "kf_neuber",
    "notch_sensitivity",
    "notch_local_life",
]


def ramberg_osgood_strain(stress, E: float, K: float, n: float) -> float:
    """Total strain on the cyclic Ramberg-Osgood curve for a given stress."""
    s = float(stress)
    return s / E + (s / K) ** (1.0 / n)


def neuber_local(nominal, Kt: float, E: float, K: float, n: float) -> tuple[float, float]:
    """Local notch stress and strain by Neuber's rule on the cyclic curve.

    Solves ``sigma * (sigma/E + (sigma/K)**(1/n)) = (Kt*nominal)**2 / E`` for the
    local stress, then returns ``(sigma, strain)``. Use stress amplitudes with
    the cyclic K' and n' to get local amplitudes.
    """
    rhs = (Kt * nominal) ** 2 / E
    hi = Kt * abs(nominal) + 1.0  # elastic local stress is an upper bound

    def f(s):
        return s * (s / E + (s / K) ** (1.0 / n)) - rhs

    sigma = float(optimize.brentq(f, 0.0, hi, xtol=1e-10, rtol=1e-12, maxiter=200))
    return sigma, ramberg_osgood_strain(sigma, E, K, n)


def neuber_local_range(delta_nominal, Kt: float, E: float, K: float, n: float) -> tuple[float, float]:
    """Local stress and strain ranges by modified Neuber on the doubled curve.

    Solves ``dsigma * (dsigma/E + 2*(dsigma/(2K))**(1/n)) = (Kt*dS)**2 / E`` for
    the local stress range, then returns ``(dsigma, depsilon)`` using the
    hysteresis (Massing doubled) branch.
    """
    rhs = (Kt * delta_nominal) ** 2 / E
    hi = Kt * abs(delta_nominal) + 1.0

    def f(ds):
        return ds * (ds / E + 2.0 * (ds / (2.0 * K)) ** (1.0 / n)) - rhs

    dsigma = float(optimize.brentq(f, 0.0, hi, xtol=1e-10, rtol=1e-12, maxiter=200))
    deps = dsigma / E + 2.0 * (dsigma / (2.0 * K)) ** (1.0 / n)
    return dsigma, deps


def glinka_local(nominal, Kt: float, E: float, K: float, n: float) -> tuple[float, float]:
    """Local notch stress and strain by the Glinka ESED rule on the cyclic curve.

    Solves ``(Kt*nominal)**2/(2E) = sigma**2/(2E) + (sigma/(n+1))*(sigma/K)**(1/n)``
    for the local stress, then returns ``(sigma, strain)``. Glinka generally
    predicts a lower local strain than Neuber.
    """
    lhs = (Kt * nominal) ** 2 / (2.0 * E)
    hi = Kt * abs(nominal) + 1.0

    def f(s):
        return s**2 / (2.0 * E) + (s / (n + 1.0)) * (s / K) ** (1.0 / n) - lhs

    sigma = float(optimize.brentq(f, 0.0, hi, xtol=1e-10, rtol=1e-12, maxiter=200))
    return sigma, ramberg_osgood_strain(sigma, E, K, n)


def kf_peterson(Kt: float, a: float, r: float) -> float:
    """Fatigue notch factor by Peterson: ``Kf = 1 + (Kt-1)/(1 + a/r)``.

    ``a`` is the Peterson material length and ``r`` the notch radius, same units.
    """
    if r <= 0:
        raise ValueError("notch radius r must be positive")
    return 1.0 + (Kt - 1.0) / (1.0 + a / r)


def kf_neuber(Kt: float, beta: float, r: float) -> float:
    """Fatigue notch factor by Neuber: ``Kf = 1 + (Kt-1)/(1 + sqrt(beta/r))``."""
    if r <= 0:
        raise ValueError("notch radius r must be positive")
    return 1.0 + (Kt - 1.0) / (1.0 + np.sqrt(beta / r))


def notch_sensitivity(Kt: float, Kf: float) -> float:
    """Notch sensitivity ``q = (Kf-1)/(Kt-1)``, between 0 and 1."""
    if Kt == 1.0:
        return 0.0
    return (Kf - 1.0) / (Kt - 1.0)


def notch_local_life(
    nominal_amp,
    Kt: float,
    *,
    E: float,
    K: float,
    n: float,
    sigma_f: float,
    b: float,
    eps_f: float,
    c: float,
    method: str = "neuber",
) -> dict:
    """End-to-end notch life from a nominal stress amplitude.

    Computes the local stress and strain amplitude (Neuber or Glinka), then
    inverts the strain-life curve for reversals to failure. Returns a dict with
    local stress, local strain, reversals, and cycles.
    """
    if method == "neuber":
        sigma, strain = neuber_local(nominal_amp, Kt, E, K, n)
    elif method == "glinka":
        sigma, strain = glinka_local(nominal_amp, Kt, E, K, n)
    else:
        raise ValueError(f"method must be 'neuber' or 'glinka', got {method!r}")
    two_nf = predict_reversals_from_total_strain(strain, sigma_f, b, eps_f, c, E)
    return {
        "local_stress_amp": sigma,
        "local_strain_amp": strain,
        "reversals": two_nf,
        "cycles": two_nf / 2.0,
        "method": method,
    }
