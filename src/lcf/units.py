"""Unit conventions and engineering<->true stress/strain conversions.

Internal convention (see ADR-0002):

* **stress** in **MPa**
* **strain** dimensionless (fraction, *not* percent)
* **modulus** ``E`` in **MPa**

A consequence worth stating explicitly: with stress in MPa and strain a fraction,
a hysteresis-loop area ``∮ σ dε`` comes out directly in **MJ/m³**
(``1 MPa × 1 = 1e6 J/m³ = 1 MJ/m³``). No extra factor is needed. If a caller
instead works in GPa and percent, the raw product is 10× MJ/m³, hence everything
here normalizes to MPa + fraction first.

All functions accept scalars or array-likes and return ``float`` or
``numpy.ndarray`` accordingly.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import ArrayLike, NDArray

__all__ = [
    "stress_from_force",
    "eng_to_true_strain",
    "eng_to_true_stress",
    "true_to_eng_strain",
    "true_to_eng_stress",
    "fraction_to_percent",
    "percent_to_fraction",
    "mpa_to_pa",
    "pa_to_mpa",
    "gpa_to_mpa",
    "mpa_to_gpa",
]


def _as_float_array(x: ArrayLike) -> NDArray[np.float64] | np.float64:
    """Return ``x`` as a float array. A 0-d input stays 0-d, callers handle scalars."""
    arr = np.asarray(x, dtype=np.float64)
    return arr


# --------------------------------------------------------------------------- #
# Force -> stress
# --------------------------------------------------------------------------- #
def stress_from_force(force: ArrayLike, area: float) -> NDArray[np.float64]:
    """Engineering stress from force and original cross-sectional area.

    Parameters
    ----------
    force : array-like
        Load (N).
    area : float
        Original cross-sectional area A0 (mm²). Using N and mm² yields MPa
        directly (``1 N/mm² = 1 MPa``).

    Returns
    -------
    Engineering stress (MPa).
    """
    if area <= 0:
        raise ValueError(f"area must be positive, got {area}")
    return _as_float_array(force) / area


# --------------------------------------------------------------------------- #
# Engineering -> true
# --------------------------------------------------------------------------- #
def eng_to_true_strain(eps_eng: ArrayLike) -> NDArray[np.float64]:
    """True strain from engineering strain: ``ε_true = ln(1 + ε_eng)``.

    Uses ``log1p`` for accuracy near zero. Valid up to necking.
    """
    eps = _as_float_array(eps_eng)
    if np.any(eps <= -1.0):
        raise ValueError("engineering strain <= -100% is non-physical (1 + ε must be > 0)")
    return np.log1p(eps)


def eng_to_true_stress(sigma_eng: ArrayLike, eps_eng: ArrayLike) -> NDArray[np.float64]:
    """True stress from engineering stress and strain: ``σ_true = σ_eng·(1 + ε_eng)``.

    Assumes constant volume (incompressible plastic flow); valid up to necking.
    """
    sig = _as_float_array(sigma_eng)
    eps = _as_float_array(eps_eng)
    if np.any(eps <= -1.0):
        raise ValueError("engineering strain <= -100% is non-physical (1 + ε must be > 0)")
    return sig * (1.0 + eps)


# --------------------------------------------------------------------------- #
# True -> engineering (inverse, for completeness / round-tripping)
# --------------------------------------------------------------------------- #
def true_to_eng_strain(eps_true: ArrayLike) -> NDArray[np.float64]:
    """Engineering strain from true strain: ``ε_eng = exp(ε_true) − 1``."""
    return np.expm1(_as_float_array(eps_true))


def true_to_eng_stress(sigma_true: ArrayLike, eps_true: ArrayLike) -> NDArray[np.float64]:
    """Engineering stress from true stress and *true* strain.

    ``σ_eng = σ_true / (1 + ε_eng) = σ_true · exp(−ε_true)``.
    """
    sig = _as_float_array(sigma_true)
    return sig * np.exp(-_as_float_array(eps_true))


# --------------------------------------------------------------------------- #
# Simple scalar unit conversions
# --------------------------------------------------------------------------- #
def fraction_to_percent(x: ArrayLike) -> NDArray[np.float64]:
    """Strain fraction -> percent."""
    return _as_float_array(x) * 100.0


def percent_to_fraction(x: ArrayLike) -> NDArray[np.float64]:
    """Strain percent -> fraction."""
    return _as_float_array(x) / 100.0


def mpa_to_pa(x: ArrayLike) -> NDArray[np.float64]:
    return _as_float_array(x) * 1.0e6


def pa_to_mpa(x: ArrayLike) -> NDArray[np.float64]:
    return _as_float_array(x) / 1.0e6


def gpa_to_mpa(x: ArrayLike) -> NDArray[np.float64]:
    return _as_float_array(x) * 1.0e3


def mpa_to_gpa(x: ArrayLike) -> NDArray[np.float64]:
    return _as_float_array(x) / 1.0e3
