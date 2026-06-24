"""Life prediction — evaluate strain-life models and invert them for life.

Forward model curves (strain amplitude given life) and inverse solvers (life
given a strain amplitude or an SWT cycle). Lives are expressed in **reversals**
``2N_f``; divide by two for cycles.
"""

from __future__ import annotations

import numpy as np
from scipy import optimize

from .fits import StrainLifeFit
from .meanstress import swt_parameter

__all__ = [
    "elastic_strain_life",
    "plastic_strain_life",
    "total_strain_life",
    "predict_reversals_from_total_strain",
    "predict_reversals_basquin",
    "predict_reversals_swt",
    "predict_reversals",
]


def elastic_strain_life(reversals, sigma_f, b, E):
    """Basquin elastic strain amplitude: ``(σ'_f/E)·(2N_f)^b``."""
    tn = np.asarray(reversals, dtype=np.float64)
    return (sigma_f / E) * tn**b


def plastic_strain_life(reversals, eps_f, c):
    """Coffin-Manson plastic strain amplitude: ``ε'_f·(2N_f)^c``."""
    tn = np.asarray(reversals, dtype=np.float64)
    return eps_f * tn**c


def total_strain_life(reversals, sigma_f, b, eps_f, c, E):
    """Total strain amplitude: elastic + plastic."""
    return elastic_strain_life(reversals, sigma_f, b, E) + plastic_strain_life(reversals, eps_f, c)


def _solve_decreasing(func, target, bracket):
    """Solve ``func(x) == target`` for a strictly decreasing positive ``func``."""
    lo, hi = bracket
    f_lo = func(lo) - target
    f_hi = func(hi) - target
    if f_lo < 0:  # target above the curve max (life shorter than lo) -> clamp
        return lo
    if f_hi > 0:  # target below the curve min (life longer than hi) -> clamp
        return hi
    return float(optimize.brentq(lambda x: func(x) - target, lo, hi, xtol=1e-6, rtol=1e-10))


def predict_reversals_from_total_strain(
    total_strain_amp, sigma_f, b, eps_f, c, E, *, bracket=(1.0, 1e12)
) -> float:
    """Reversals to failure ``2N_f`` for a given total strain amplitude.

    Inverts the combined strain-life equation by bracketed root finding (the
    curve is monotonically decreasing in life). Results are clamped to the
    bracket when the target lies outside the curve's range.
    """
    return _solve_decreasing(
        lambda tn: total_strain_life(tn, sigma_f, b, eps_f, c, E),
        float(total_strain_amp), bracket,
    )


def predict_reversals_basquin(stress_amp, sigma_f, b) -> float:
    """Reversals from stress amplitude via inverted Basquin: ``(σa/σ'_f)^(1/b)``."""
    return float((stress_amp / sigma_f) ** (1.0 / b))


def predict_reversals_swt(
    sigma_max, strain_amp, sigma_f, b, eps_f, c, E, *, bracket=(1.0, 1e12)
) -> float:
    """Reversals from an SWT cycle by solving ``σ_max·ε_a = SWT_curve(2N_f)``."""
    target = float(swt_parameter(sigma_max, strain_amp))
    return _solve_decreasing(
        lambda tn: (sigma_f**2 / E) * tn ** (2 * b) + sigma_f * eps_f * tn ** (b + c),
        target, bracket,
    )


def predict_reversals(fit: StrainLifeFit, total_strain_amp: float) -> float:
    """Convenience: predict reversals from a fitted model and a strain amplitude."""
    return predict_reversals_from_total_strain(
        total_strain_amp,
        fit.basquin.sigma_f, fit.basquin.b,
        fit.coffin_manson.eps_f, fit.coffin_manson.c, fit.E,
    )
