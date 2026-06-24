"""Mean-stress corrections — Morrow, modified Morrow, SWT, Walker.

Two complementary APIs (ADR-0006, IMPLEMENTATION_REFERENCE §2):

* :func:`equivalent_fully_reversed_stress` — the practical, model-agnostic API:
  convert a cycle ``(σa, σm)`` into the equivalent fully-reversed amplitude
  ``σ_ar`` that produces the same life. All models reduce to ``σa`` when
  ``σm = 0``; Walker with ``γ = 0.5`` reduces exactly to SWT.
* strain-life curve forms — :func:`morrow_strain_life`,
  :func:`modified_morrow_strain_life`, and the SWT parameter curve
  :func:`swt_parameter_curve` — for plotting mean-stress-corrected ε-N curves.

Sign convention: ``b``, ``c`` negative; stresses/``E`` in MPa.
"""

from __future__ import annotations

import numpy as np

from .models import MeanStressModel

__all__ = [
    "walker_gamma_steel",
    "equivalent_fully_reversed_stress",
    "morrow_strain_life",
    "modified_morrow_strain_life",
    "swt_parameter",
    "swt_parameter_curve",
]


def walker_gamma_steel(sigma_u: float) -> float:
    """Estimate the Walker exponent γ for steels from ultimate strength.

    ``γ = 0.8818 − 2.00e-4·σ_u`` (Dowling, Calhoun & Arcari 2009, as in Dowling
    4th ed. Eq. 9.20; σ_u in MPa; widely rounded to 0.883 in secondary sources).
    For 2000/7000-series aluminium, γ ≈ 0.5 (≈ SWT) is recommended instead.
    """
    return 0.8818 - 2.00e-4 * sigma_u


def equivalent_fully_reversed_stress(
    sigma_a,
    mean_stress,
    model: MeanStressModel | str,
    *,
    sigma_f: float | None = None,
    gamma: float | None = None,
):
    """Equivalent fully-reversed stress amplitude ``σ_ar`` for a cycle.

    Parameters
    ----------
    sigma_a : array-like
        Stress amplitude Δσ/2 (MPa).
    mean_stress : array-like
        Mean stress σ_m (MPa). σ_max = σ_a + σ_m.
    model : MeanStressModel | str
        One of ``none``, ``morrow``, ``swt``, ``walker``.
    sigma_f : float, optional
        Fatigue strength coefficient σ'_f (MPa); required for Morrow.
    gamma : float, optional
        Walker exponent γ; required for Walker (γ = 0.5 == SWT).

    Returns
    -------
    σ_ar (MPa). All models give ``σ_ar = σ_a`` when ``σ_m = 0``.
    """
    model = MeanStressModel(model)
    sa = np.asarray(sigma_a, dtype=np.float64)
    sm = np.asarray(mean_stress, dtype=np.float64)
    smax = sa + sm

    if model is MeanStressModel.NONE:
        return sa
    if model is MeanStressModel.MORROW:
        if sigma_f is None:
            raise ValueError("Morrow correction requires sigma_f")
        if np.any(sm >= sigma_f):
            raise ValueError(
                "Morrow correction is undefined for mean stress >= sigma_f "
                f"(sigma_f={sigma_f}); the cycle exceeds the fatigue strength coefficient."
            )
        return sa / (1.0 - sm / sigma_f)
    if model in (MeanStressModel.SWT,):
        # σ_ar = sqrt(σ_max · σ_a), valid for σ_max > 0
        return np.sqrt(np.clip(smax, 0.0, None) * sa)
    if model is MeanStressModel.WALKER:
        if gamma is None:
            raise ValueError("Walker correction requires gamma (use walker_gamma_steel)")
        return np.clip(smax, 0.0, None) ** (1.0 - gamma) * sa**gamma
    if model is MeanStressModel.MODIFIED_MORROW:
        # modified Morrow has no single closed-form σ_ar; use its strain-life form
        raise ValueError(
            "modified_morrow has no equivalent-stress form; use "
            "modified_morrow_strain_life()"
        )
    raise ValueError(f"unsupported model: {model}")  # pragma: no cover


def morrow_strain_life(reversals, *, sigma_f, b, eps_f, c, E, mean_stress):
    """Morrow mean-stress-corrected total strain amplitude vs reversals.

    ``Δε/2 = ((σ'_f − σ_m)/E)·(2N_f)^b + ε'_f·(2N_f)^c``.
    """
    tn = np.asarray(reversals, dtype=np.float64)
    return (sigma_f - mean_stress) / E * tn**b + eps_f * tn**c


def modified_morrow_strain_life(reversals, *, sigma_f, b, eps_f, c, E, mean_stress):
    """Modified Morrow (correction on both terms).

    ``Δε/2 = ((σ'_f − σ_m)/E)·(2N_f)^b + ε'_f·((σ'_f − σ_m)/σ'_f)^(c/b)·(2N_f)^c``.
    """
    tn = np.asarray(reversals, dtype=np.float64)
    factor = (sigma_f - mean_stress) / sigma_f
    if np.any(factor <= 0):
        raise ValueError(
            "modified Morrow is undefined for mean stress >= sigma_f "
            f"(sigma_f={sigma_f}); (sigma_f - mean_stress) must be positive."
        )
    return (sigma_f - mean_stress) / E * tn**b + eps_f * factor ** (c / b) * tn**c


def swt_parameter(sigma_max, strain_amp):
    """SWT damage parameter ``σ_max · ε_a`` for a measured cycle."""
    return np.asarray(sigma_max, dtype=np.float64) * np.asarray(strain_amp, dtype=np.float64)


def swt_parameter_curve(reversals, *, sigma_f, b, eps_f, c, E):
    """SWT parameter as a function of life: ``σ_max·ε_a`` vs ``2N_f``.

    ``σ_max·ε_a = (σ'_f²/E)·(2N_f)^(2b) + σ'_f·ε'_f·(2N_f)^(b+c)``.
    Solve ``swt_parameter(σ_max, ε_a) == swt_parameter_curve(2N_f)`` for life.
    """
    tn = np.asarray(reversals, dtype=np.float64)
    return (sigma_f**2 / E) * tn ** (2 * b) + sigma_f * eps_f * tn ** (b + c)
