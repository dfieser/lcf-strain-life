"""Strain-life model fitting — Basquin, Coffin-Manson, Ramberg-Osgood.

Per-branch log-log linear least-squares is the primary fit (ADR-0005), with an
optional nonlinear refinement of the combined total-strain curve. ``K'`` and
``n'`` are fit independently and also derived from ``b/c``; divergence (non-Masing
behavior) is flagged rather than silently forced.

Sign convention: ``b`` and ``c`` are negative. Units: stress/``E`` in MPa.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy import optimize, stats

__all__ = [
    "PowerLawFit",
    "BasquinFit",
    "CoffinMansonFit",
    "RambergOsgoodFit",
    "ConsistencyCheck",
    "StrainLifeFit",
    "power_law_fit",
    "fit_basquin",
    "fit_coffin_manson",
    "fit_ramberg_osgood",
    "transition_reversals",
    "check_consistency",
    "fit_strain_life",
]


@dataclass
class PowerLawFit:
    """Result of ``y = coeff · x**exponent`` fit by log-log linear regression."""

    coeff: float
    exponent: float
    r_squared: float
    n_points: int
    exponent_stderr: float
    coeff_stderr: float


def power_law_fit(x, y) -> PowerLawFit:
    """Fit ``y = coeff · x**exponent`` via OLS on ``log10(y)`` vs ``log10(x)``.

    Only strictly-positive, finite pairs are used (log space). Requires >= 2
    usable points. ``coeff_stderr`` is propagated from the intercept stderr.
    """
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    mask = np.isfinite(x) & np.isfinite(y) & (x > 0) & (y > 0)
    nx = int(mask.sum())
    if nx < 2:
        raise ValueError(f"need >= 2 positive finite points to fit, got {nx}")
    lx = np.log10(x[mask])
    ly = np.log10(y[mask])
    res = stats.linregress(lx, ly)
    coeff = 10.0**res.intercept
    # propagate intercept stderr (base-10): d(10^a)/da = 10^a · ln(10)
    coeff_stderr = coeff * np.log(10.0) * float(res.intercept_stderr)
    return PowerLawFit(
        coeff=float(coeff),
        exponent=float(res.slope),
        r_squared=float(res.rvalue**2),
        n_points=nx,
        exponent_stderr=float(res.stderr),
        coeff_stderr=float(coeff_stderr),
    )


@dataclass
class BasquinFit:
    """Elastic branch: ``Δσ/2 = σ'_f · (2N_f)**b``."""

    sigma_f: float       # fatigue strength coefficient (MPa)
    b: float             # fatigue strength exponent (negative)
    r_squared: float
    n_points: int
    sigma_f_stderr: float = 0.0
    b_stderr: float = 0.0


@dataclass
class CoffinMansonFit:
    """Plastic branch: ``Δε_p/2 = ε'_f · (2N_f)**c``."""

    eps_f: float         # fatigue ductility coefficient
    c: float             # fatigue ductility exponent (negative)
    r_squared: float
    n_points: int
    eps_f_stderr: float = 0.0
    c_stderr: float = 0.0


@dataclass
class RambergOsgoodFit:
    """Cyclic stress-strain: ``Δσ/2 = K' · (Δε_p/2)**n'``."""

    K: float             # cyclic strength coefficient (MPa)
    n: float             # cyclic strain-hardening exponent
    r_squared: float
    n_points: int
    K_stderr: float = 0.0
    n_stderr: float = 0.0


def fit_basquin(stress_amp, reversals) -> BasquinFit:
    """Fit Basquin constants from stress amplitude vs reversals to failure."""
    pl = power_law_fit(reversals, stress_amp)
    return BasquinFit(
        sigma_f=pl.coeff, b=pl.exponent, r_squared=pl.r_squared,
        n_points=pl.n_points, sigma_f_stderr=pl.coeff_stderr, b_stderr=pl.exponent_stderr,
    )


def _plastic_mask(plastic_strain_amp, min_plastic_strain):
    pl = np.asarray(plastic_strain_amp, dtype=np.float64)
    if min_plastic_strain is None:
        return np.ones(pl.shape, dtype=bool)
    return pl >= float(min_plastic_strain)


def fit_coffin_manson(
    plastic_strain_amp, reversals, *, min_plastic_strain: float | None = None
) -> CoffinMansonFit:
    """Fit Coffin-Manson constants from plastic strain amplitude vs reversals.

    The plastic line is only physically meaningful where plastic strain is
    significant (the LCF regime). Near-runout points with plastic strain at
    measurement-noise level corrupt the fit, so pass ``min_plastic_strain`` to
    exclude them (ASTM E739 cautions against fitting outside the valid interval;
    IMPLEMENTATION_REFERENCE §1-2). With no threshold, all points are used.
    """
    pa = np.asarray(plastic_strain_amp, dtype=np.float64)
    rev = np.asarray(reversals, dtype=np.float64)
    m = _plastic_mask(pa, min_plastic_strain)
    if min_plastic_strain is not None and int(m.sum()) < 2:
        raise ValueError(
            f"min_plastic_strain={min_plastic_strain} excluded all but {int(m.sum())} "
            "point(s); lower the threshold (need >= 2 points for the plastic branch)."
        )
    pl = power_law_fit(rev[m], pa[m])
    return CoffinMansonFit(
        eps_f=pl.coeff, c=pl.exponent, r_squared=pl.r_squared,
        n_points=pl.n_points, eps_f_stderr=pl.coeff_stderr, c_stderr=pl.exponent_stderr,
    )


def fit_ramberg_osgood(
    stress_amp, plastic_strain_amp, *, min_plastic_strain: float | None = None
) -> RambergOsgoodFit:
    """Fit Ramberg-Osgood cyclic constants: ``Δσ/2 = K'·(Δε_p/2)**n'``.

    As with Coffin-Manson, ``min_plastic_strain`` excludes elastic-dominated,
    noisy-plastic points.
    """
    sa = np.asarray(stress_amp, dtype=np.float64)
    pa = np.asarray(plastic_strain_amp, dtype=np.float64)
    m = _plastic_mask(pa, min_plastic_strain)
    pl = power_law_fit(pa[m], sa[m])
    return RambergOsgoodFit(
        K=pl.coeff, n=pl.exponent, r_squared=pl.r_squared,
        n_points=pl.n_points, K_stderr=pl.coeff_stderr, n_stderr=pl.exponent_stderr,
    )


def transition_reversals(sigma_f: float, b: float, eps_f: float, c: float, E: float) -> float:
    """Elastic-plastic transition life ``2N_t`` (where Δε_e/2 == Δε_p/2).

    ``2N_t = (ε'_f · E / σ'_f) ** (1 / (b − c))``.
    """
    if b == c:
        raise ValueError("b and c must differ to compute a transition life")
    if not (sigma_f > 0 and eps_f > 0 and E > 0):
        raise ValueError(
            f"transition life requires positive sigma_f, eps_f, E; "
            f"got sigma_f={sigma_f}, eps_f={eps_f}, E={E}"
        )
    return float((eps_f * E / sigma_f) ** (1.0 / (b - c)))


@dataclass
class ConsistencyCheck:
    """Compatibility (Masing) check between fitted and b/c-derived K'/n'."""

    n_fitted: float
    n_from_bc: float          # b/c
    K_fitted: float
    K_from_params: float      # σ'_f / (ε'_f)**(b/c)
    n_rel_diff: float
    K_rel_diff: float
    masing_ok: bool
    tolerance: float


def check_consistency(
    basquin: BasquinFit,
    coffin_manson: CoffinMansonFit,
    ramberg_osgood: RambergOsgoodFit,
    *,
    tolerance: float = 0.15,
) -> ConsistencyCheck:
    """Compare fitted ``K'``/``n'`` to the b/c-derived values (ADR-0005).

    Compatibility predicts ``n' = b/c`` and ``K' = σ'_f / (ε'_f)**(b/c)``.
    ``masing_ok`` is True when both relative differences are within ``tolerance``.
    If the relations are undefined (c == 0, or ε'_f <= 0 so the power is complex),
    the check returns ``masing_ok=False`` with NaN differences rather than raising.
    """
    if coffin_manson.c == 0 or coffin_manson.eps_f <= 0:
        return ConsistencyCheck(
            n_fitted=ramberg_osgood.n, n_from_bc=float("nan"),
            K_fitted=ramberg_osgood.K, K_from_params=float("nan"),
            n_rel_diff=float("nan"), K_rel_diff=float("nan"),
            masing_ok=False, tolerance=tolerance,
        )
    n_from_bc = basquin.b / coffin_manson.c
    K_from_params = basquin.sigma_f / (coffin_manson.eps_f**n_from_bc)
    n_rel = abs(ramberg_osgood.n - n_from_bc) / abs(n_from_bc)
    K_rel = abs(ramberg_osgood.K - K_from_params) / abs(K_from_params)
    return ConsistencyCheck(
        n_fitted=ramberg_osgood.n,
        n_from_bc=n_from_bc,
        K_fitted=ramberg_osgood.K,
        K_from_params=K_from_params,
        n_rel_diff=n_rel,
        K_rel_diff=K_rel,
        masing_ok=bool(n_rel <= tolerance and K_rel <= tolerance),
        tolerance=tolerance,
    )


@dataclass
class StrainLifeFit:
    """Full strain-life fit result."""

    E: float
    basquin: BasquinFit
    coffin_manson: CoffinMansonFit
    ramberg_osgood: RambergOsgoodFit | None
    transition_reversals: float
    consistency: ConsistencyCheck | None
    refined: dict = field(default_factory=dict)  # optional nonlinear-refined constants


def _total_strain_model(two_nf, sigma_f, b, eps_f, c, E):
    return (sigma_f / E) * two_nf**b + eps_f * two_nf**c


def fit_strain_life(
    total_strain_amp,
    stress_amp,
    reversals,
    E: float,
    *,
    plastic_strain_amp=None,
    min_plastic_strain: float | None = None,
    refine_nonlinear: bool = False,
) -> StrainLifeFit:
    """Fit the complete strain-life model from per-test reduced data.

    Parameters
    ----------
    total_strain_amp, stress_amp, reversals : array-like
        Per-test total strain amplitude, half-life stress amplitude, and
        reversals to failure ``2N_f``.
    E : float
        Young's modulus (MPa).
    plastic_strain_amp : array-like, optional
        If omitted, computed as ``Δε_t/2 − Δσ/(2E)`` (the standard default).
    min_plastic_strain : float, optional
        Minimum plastic strain amplitude for a point to enter the *plastic*
        (Coffin-Manson) and cyclic (Ramberg-Osgood) fits. The *elastic* (Basquin)
        fit always uses all points. Use this to exclude near-runout points whose
        plastic strain is at measurement-noise level (ADR-0005).
    refine_nonlinear : bool
        If True, refine ``σ'_f, b, ε'_f, c`` with a nonlinear fit of the combined
        total-strain curve, seeded by the linear fits (ADR-0005).
    """
    total_strain_amp = np.asarray(total_strain_amp, dtype=np.float64)
    stress_amp = np.asarray(stress_amp, dtype=np.float64)
    reversals = np.asarray(reversals, dtype=np.float64)
    if plastic_strain_amp is None:
        plastic_strain_amp = total_strain_amp - stress_amp / E
    else:
        plastic_strain_amp = np.asarray(plastic_strain_amp, dtype=np.float64)

    basquin = fit_basquin(stress_amp, reversals)  # elastic branch: all points
    coffin_manson = fit_coffin_manson(
        plastic_strain_amp, reversals, min_plastic_strain=min_plastic_strain
    )

    # Ramberg-Osgood needs >= 2 positive plastic points; skip gracefully otherwise.
    ro: RambergOsgoodFit | None
    consistency: ConsistencyCheck | None
    try:
        ro = fit_ramberg_osgood(
            stress_amp, plastic_strain_amp, min_plastic_strain=min_plastic_strain
        )
        consistency = check_consistency(basquin, coffin_manson, ro)
    except ValueError:
        ro = None
        consistency = None

    trans = transition_reversals(basquin.sigma_f, basquin.b, coffin_manson.eps_f,
                                 coffin_manson.c, E)

    refined: dict = {}
    if refine_nonlinear:
        try:
            p0 = [basquin.sigma_f, basquin.b, coffin_manson.eps_f, coffin_manson.c]
            popt, pcov = optimize.curve_fit(
                lambda tn, sf, bb, ef, cc: _total_strain_model(tn, sf, bb, ef, cc, E),
                reversals, total_strain_amp, p0=p0, maxfev=10000,
            )
            perr = np.sqrt(np.diag(pcov))
            refined = {
                "sigma_f": float(popt[0]), "b": float(popt[1]),
                "eps_f": float(popt[2]), "c": float(popt[3]),
                "stderr": [float(v) for v in perr],
            }
        except Exception as exc:  # pragma: no cover - refinement is best-effort
            refined = {"error": str(exc)}

    return StrainLifeFit(
        E=float(E),
        basquin=basquin,
        coffin_manson=coffin_manson,
        ramberg_osgood=ro,
        transition_reversals=trans,
        consistency=consistency,
        refined=refined,
    )
