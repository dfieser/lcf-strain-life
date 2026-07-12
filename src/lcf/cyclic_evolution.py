"""Cycle-dependent mean stress relaxation and ratcheting (ADR 0020).

Two phenomena that the stabilized-cycle analysis elsewhere in the toolkit
does not model:

* Mean stress relaxation, strain-controlled asymmetric cycling. A nonzero
  mean stress decays toward zero as plastic strain accumulates. The standard
  empirical form is a power law in cycle count,

      sigma_m(N) = sigma_m1 * N ** b_r,

  with ``sigma_m1`` the first-cycle mean stress and ``b_r <= 0`` a material
  relaxation exponent, the slope of log(sigma_m) against log(N).

* Ratcheting, stress-controlled asymmetric cycling. Plastic strain
  accumulates cycle by cycle in the direction of the mean stress. The
  accumulated ratcheting strain follows an empirical power law,

      eps_r(N) = C * N ** p,

  and its life interaction is a ductility-exhaustion penalty on the
  Coffin-Manson plastic term,

      delta_eps_p / 2 = (eps_f' - eps_r) * (2 N_f) ** c.

Provenance and status. These forms were reconstructed from collaborator
notes (Hugh Shortt, 2026-07-08) whose inline equations were lost in
transfer, and they match the standard published forms cited below. They are
labeled reconstructed and carry a note that the exact formulation is pending
the collaborator's confirmation. Every function is validated by internal
consistency and by fitter-recovery of known constants, there is no published
worked-example golden.

References: Jhansale and Topper 1973 (ASTM STP 519), Morrow and Sinclair
1958 (ASTM STP 237) for relaxation. Xia, Kujawski and Ellyin 1996 (Int. J.
Fatigue 18:335) and Kapoor 1994 (Fatigue Fract. Eng. Mater. Struct. 17:201)
for ratcheting and its damage interaction.
"""

from __future__ import annotations

import numpy as np

__all__ = [
    "mean_stress_relaxation",
    "fit_relaxation_exponent",
    "ratcheting_strain",
    "fit_ratcheting",
    "ratcheting_penalized_life",
]

_RECON_NOTE = (
    "reconstructed from collaborator notes (2026-07-08), matches the "
    "standard published form, pending confirmation the formulation is the "
    "intended one"
)


def mean_stress_relaxation(sigma_m1: float, N, b_r: float) -> np.ndarray:
    """Relaxed mean stress at cycle ``N``: ``sigma_m1 * N ** b_r``.

    ``sigma_m1`` is the first-cycle mean stress (MPa), ``b_r`` the relaxation
    exponent (<= 0, more negative relaxes faster). ``N`` is a cycle count or
    array of counts (>= 1). Returns the mean stress at each ``N``.
    """
    n = np.asarray(N, dtype=np.float64)
    if np.any(n < 1):
        raise ValueError("cycle count N must be >= 1 (cycle 1 is the first)")
    if b_r > 0:
        raise ValueError(
            f"relaxation exponent b_r must be <= 0, got {b_r}. A positive "
            "exponent would grow the mean stress, not relax it."
        )
    return sigma_m1 * n ** b_r


def fit_relaxation_exponent(cycles, mean_stresses) -> dict:
    """Fit the relaxation power law to measured (cycle, mean stress) data.

    Returns ``sigma_m1`` (the fitted first-cycle mean stress), ``b_r``, the
    coefficient of determination, and notes. Mean stresses must share one
    sign, the log-log fit is on their magnitude.
    """
    n = np.asarray(cycles, dtype=np.float64)
    s = np.asarray(mean_stresses, dtype=np.float64)
    if n.shape != s.shape:
        raise ValueError("cycles and mean_stresses must have equal length")
    if n.size < 3:
        raise ValueError("need at least 3 points to fit the relaxation law")
    if np.any(n < 1):
        raise ValueError("cycle counts must be >= 1")
    if not (np.all(s > 0) or np.all(s < 0)):
        raise ValueError(
            "mean stresses must share one sign, relaxation is fit on the "
            "magnitude and the sign is preserved"
        )
    sign = 1.0 if s[0] > 0 else -1.0
    logn = np.log10(n)
    logs = np.log10(np.abs(s))
    b_r, log_s1 = np.polyfit(logn, logs, 1)
    pred = log_s1 + b_r * logn
    ss_res = float(np.sum((logs - pred) ** 2))
    ss_tot = float(np.sum((logs - logs.mean()) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 1.0
    notes = [_RECON_NOTE]
    if b_r > 0:
        notes.append(
            "fitted exponent is positive, the data grow rather than relax, "
            "check the input"
        )
    return {
        "sigma_m1": float(sign * 10.0 ** log_s1),
        "b_r": float(b_r),
        "r_squared": float(r2),
        "n_points": int(n.size),
        "notes": notes,
    }


def ratcheting_strain(N, C: float, p: float) -> np.ndarray:
    """Accumulated ratcheting strain at cycle ``N``: ``C * N ** p``.

    ``C`` is the ratcheting coefficient (strain at N=1), ``p`` the ratcheting
    exponent (> 0). ``N`` is a cycle count or array (>= 1).
    """
    n = np.asarray(N, dtype=np.float64)
    if np.any(n < 1):
        raise ValueError("cycle count N must be >= 1")
    if C < 0:
        raise ValueError(f"ratcheting coefficient C must be >= 0, got {C}")
    return C * n ** p


def fit_ratcheting(cycles, ratchet_strains) -> dict:
    """Fit the ratcheting power law ``eps_r = C * N ** p`` to data.

    Returns ``C``, ``p``, the coefficient of determination, and notes.
    """
    n = np.asarray(cycles, dtype=np.float64)
    e = np.asarray(ratchet_strains, dtype=np.float64)
    if n.shape != e.shape:
        raise ValueError("cycles and ratchet_strains must have equal length")
    if n.size < 3:
        raise ValueError("need at least 3 points to fit the ratcheting law")
    if np.any(n < 1) or np.any(e <= 0):
        raise ValueError("cycle counts must be >= 1 and strains must be > 0")
    logn = np.log10(n)
    loge = np.log10(e)
    p, log_c = np.polyfit(logn, loge, 1)
    pred = log_c + p * logn
    ss_res = float(np.sum((loge - pred) ** 2))
    ss_tot = float(np.sum((loge - loge.mean()) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 1.0
    notes = [_RECON_NOTE]
    if p < 0:
        notes.append("fitted exponent is negative, ratcheting should grow "
                     "with cycles, check the input")
    return {
        "C": float(10.0 ** log_c),
        "p": float(p),
        "r_squared": float(r2),
        "n_points": int(n.size),
        "notes": notes,
    }


def ratcheting_penalized_life(
    plastic_strain_amp: float,
    eps_r: float,
    *,
    eps_f: float,
    c: float,
    bracket: tuple[float, float] = (1.0, 1e12),
) -> dict:
    """Reversals to failure with the ratcheting ductility-exhaustion penalty.

    Solves ``plastic_strain_amp = (eps_f - eps_r) * (2 N_f) ** c`` for the
    reversals, the Coffin-Manson plastic line with the fatigue ductility
    reduced by the accumulated ratcheting strain ``eps_r``. Returns the
    reversals, the cycles, the penalized ductility, and notes.
    """
    eps_f_eff = eps_f - eps_r
    notes = [_RECON_NOTE]
    if eps_f_eff <= 0:
        notes.append(
            f"ratcheting strain {eps_r:g} has consumed the fatigue ductility "
            f"{eps_f:g}, the material is predicted to fail immediately"
        )
        return {"reversals": 1.0, "cycles": 0.5,
                "eps_f_effective": float(eps_f_eff), "notes": notes}
    if plastic_strain_amp <= 0:
        raise ValueError("plastic_strain_amp must be positive")
    # (2Nf)^c = plastic_strain_amp / eps_f_eff, c < 0
    two_nf = (plastic_strain_amp / eps_f_eff) ** (1.0 / c)
    two_nf = float(np.clip(two_nf, *bracket))
    return {
        "reversals": two_nf,
        "cycles": two_nf / 2.0,
        "eps_f_effective": float(eps_f_eff),
        "notes": notes,
    }
