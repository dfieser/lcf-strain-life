"""Hysteresis-loop energy: loop area, and the energy-based life relation.

The plastic strain energy density dissipated per cycle is the area enclosed by
one stress-strain loop, ``∮ σ dε``. We compute it with the **shoelace polygon
formula** on the ordered loop vertices (ADR / IMPLEMENTATION_REFERENCE §6): it is
robust to the non-monotonic, self-intersecting paths that ``trapezoid`` mishandle,
and needs no sorting (points must stay in acquisition order).

With stress in MPa and strain dimensionless (the internal convention), the area
is in **MJ/m³** directly (see :mod:`lcf.units`).

The module also implements the **Halford-Morrow energy-based life relation**
and the Masing-loop plastic energy estimate:

    ΔW_p = W'_f (2N_f)^β                       (energy-life power law)
    ΔW_p = ((1 - n') / (1 + n')) Δσ Δε_p       (Masing-loop estimate)

Sources: Morrow, ASTM STP 378 (1965) 45-87, and Halford, J. Materials 1
(1966) 3-18. Implemented as applied to high-temperature low cycle fatigue by
Zhang, Zuo, and Liu, Fatigue Fract. Eng. Mater. Struct. 36 (2013) 623-630,
their Eqs. (2) and (3). The energy criterion is useful at high temperature,
where strength and ductility shift in opposite directions and a strain-only
correlation misses the stress effect. Sign convention: ``β`` is negative,
like ``b`` and ``c``. Units: ``W'_f`` and ``ΔW_p`` in MJ/m³ (numerically
equal to MPa when stress is MPa and strain a fraction).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .fits import power_law_fit

__all__ = [
    "loop_area",
    "shoelace_area",
    "EnergyLifeFit",
    "fit_energy_life",
    "predict_life_energy",
    "masing_plastic_energy",
]


def shoelace_area(x, y) -> float:
    """Signed polygon area of the (possibly open) path ``(x, y)``.

    The path is implicitly closed (last vertex connected back to the first).
    A positive sign means counter-clockwise traversal.
    """
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    if x.shape != y.shape:
        raise ValueError("x and y must have the same shape")
    if x.size < 3:
        return 0.0
    # close the polygon
    x_c = np.append(x, x[0])
    y_c = np.append(y, y[0])
    return 0.5 * float(np.sum(x_c[:-1] * y_c[1:] - x_c[1:] * y_c[:-1]))


def loop_area(strain, stress) -> float:
    """Enclosed area of one stress-strain hysteresis loop (MJ/m³).

    Absolute value of the shoelace area, so the result is independent of loop
    traversal direction. ``strain`` and ``stress`` must be the ordered samples of
    one closed loop (e.g. peak -> valley -> peak).
    """
    return abs(shoelace_area(strain, stress))


@dataclass
class EnergyLifeFit:
    """Halford-Morrow energy-life fit: ``ΔW_p = W'_f · (2N_f)**β``."""

    W_f: float           # energy-life coefficient (MJ/m³)
    beta: float          # energy-life exponent (negative)
    r_squared: float
    n_points: int
    W_f_stderr: float = 0.0
    beta_stderr: float = 0.0


def fit_energy_life(plastic_energy_per_cycle, reversals) -> EnergyLifeFit:
    """Fit the Halford-Morrow relation from per-cycle plastic energy vs life.

    ``plastic_energy_per_cycle`` is the stabilized plastic strain energy per
    cycle of each test in MJ/m³, for example the half-life hysteresis energy
    from the per-cycle reduction, or the Masing estimate from
    :func:`masing_plastic_energy`. ``reversals`` is ``2N_f`` per test. The
    fit is log-log least squares, the same primary method as the strain-life
    branches. Source: Zhang, Zuo, and Liu, FFEMS 36 (2013) 623-630, Eq. (2).
    """
    pl = power_law_fit(reversals, plastic_energy_per_cycle)
    return EnergyLifeFit(
        W_f=pl.coeff, beta=pl.exponent, r_squared=pl.r_squared,
        n_points=pl.n_points, W_f_stderr=pl.coeff_stderr,
        beta_stderr=pl.exponent_stderr,
    )


def predict_life_energy(
    plastic_energy_per_cycle: float, W_f: float, beta: float
) -> float:
    """Reversals to failure ``2N_f`` from the Halford-Morrow relation.

    Inverts ``ΔW_p = W'_f (2N_f)**β`` for a stabilized plastic strain energy
    per cycle in MJ/m³. ``beta`` must be negative and both energies positive.
    """
    if plastic_energy_per_cycle <= 0.0:
        raise ValueError("plastic_energy_per_cycle must be positive")
    if W_f <= 0.0:
        raise ValueError("W_f must be positive")
    if beta >= 0.0:
        raise ValueError("beta must be negative, like b and c")
    return float((plastic_energy_per_cycle / W_f) ** (1.0 / beta))


def masing_plastic_energy(
    stress_range: float, plastic_strain_range: float, n_prime: float
) -> float:
    """Plastic strain energy per cycle of a Masing loop (MJ/m³).

    ``ΔW_p = ((1 - n') / (1 + n')) · Δσ · Δε_p`` with the total stress range
    ``Δσ`` in MPa, the total plastic strain range ``Δε_p`` as a fraction, and
    the cyclic strain-hardening exponent ``n'`` from
    ``Δσ/2 = K'·(Δε_p/2)**n'``. Exact for a material with Masing behavior,
    an estimate otherwise. The fit's Masing consistency check reports how far
    the material departs. Source: Zhang, Zuo, and Liu, FFEMS 36 (2013)
    623-630, Eq. (3), after Morrow, ASTM STP 378 (1965).
    """
    if stress_range < 0.0 or plastic_strain_range < 0.0:
        raise ValueError("stress_range and plastic_strain_range must be >= 0")
    if not 0.0 < n_prime < 1.0:
        raise ValueError("n_prime must be between 0 and 1")
    factor = (1.0 - n_prime) / (1.0 + n_prime)
    return float(factor * stress_range * plastic_strain_range)
