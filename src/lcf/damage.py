"""Cumulative damage accumulation under variable-amplitude loading.

Palmgren-Miner is the default and the validated primary rule (ADR-0010). The
Double Linear Damage Rule (Manson-Halford) and Corten-Dolan are sequence and
load-level sensitive alternatives.

Lives passed in here are per-counted-cycle reversals or cycles to failure. Apply
any mean-stress correction upstream when computing those lives, so this module
only sums damage (research section 2.3).

Validation status, stated honestly:
- Miner: validated against a published block example (Golden D).
- DLDR accumulation: validated against a published two-phase example (Golden C).
- Manson-Halford phase-life split: a documented parametric knee model, property
  tested only. The damage answer comes from the validated accumulation.
- Corten-Dolan: tested by its exact reduction to Miner when the exponent equals
  the inverse S-N slope.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

__all__ = [
    "DamageResult",
    "miner",
    "manson_halford_phase_lives",
    "dldr_from_phase_lives",
    "dldr",
    "corten_dolan",
    "sn_curve_life",
]


@dataclass
class DamageResult:
    """Outcome of a damage calculation for one loading block."""

    damage: float               # damage accumulated by one application of the block
    blocks_to_failure: float    # d_crit / damage (block repetitions to failure)
    cycles_to_failure: float    # blocks_to_failure * cycles per block
    failed: bool                # damage >= d_crit for a single block
    rule: str
    d_crit: float


def _arrays(counts, lives):
    n = np.asarray(counts, dtype=np.float64)
    nf = np.asarray(lives, dtype=np.float64)
    if n.shape != nf.shape:
        raise ValueError(f"counts and lives must have equal shape, got {n.shape}, {nf.shape}")
    if np.any(nf <= 0):
        raise ValueError("all lives must be positive")
    return n, nf


def miner(counts, lives, *, d_crit: float = 1.0) -> DamageResult:
    """Palmgren-Miner linear damage for one loading block.

    ``damage`` is the sum of cycle-count over life for the block. The block is
    assumed to repeat, so ``blocks_to_failure`` is ``d_crit / damage``. The
    critical sum defaults to 1.0. Codes use other values, for example 0.5 for
    out-of-phase loading under IIW and Eurocode 3.
    """
    n, nf = _arrays(counts, lives)
    damage = float(np.sum(n / nf))
    blocks = d_crit / damage if damage > 0 else float("inf")
    return DamageResult(
        damage=damage,
        blocks_to_failure=blocks,
        cycles_to_failure=blocks * float(np.sum(n)),
        failed=damage >= d_crit,
        rule="miner",
        d_crit=d_crit,
    )


def manson_halford_phase_lives(lives, *, knee_coeff: float = 0.35, exponent: float = 0.25):
    """Split each life into Phase I and Phase II for the Double Linear Damage Rule.

    Uses the Manson-Halford knee, where the Phase I fraction of a level is
    ``f_I = knee_coeff * (N_f/N_long)**exponent`` referenced to the longest life
    in the spectrum, so longer-life levels spend proportionally more of their
    life in Phase I. With the standard constants 0.35 and 0.25 the shortest level
    in an N_short to N_long spectrum gets a Phase I life of
    ``N_short * 0.35 * (N_short/N_long)**0.25``, which reproduces the published
    Manson-Halford table value. Returns ``(phase1_lives, phase2_lives)``.
    """
    nf = np.asarray(lives, dtype=np.float64)
    if np.any(nf <= 0):
        raise ValueError("all lives must be positive")
    n_long = float(np.max(nf))
    f_one = np.clip(knee_coeff * (nf / n_long) ** exponent, 1e-12, 1.0)
    phase1 = nf * f_one
    phase2 = nf - phase1
    phase2 = np.where(phase2 <= 0, nf * 1e-9, phase2)
    return phase1, phase2


def dldr_from_phase_lives(counts, phase1_lives, phase2_lives, *, d_crit: float = 1.0) -> DamageResult:
    """Double Linear Damage Rule accumulation from explicit phase lives.

    Phase I runs until its linear damage sum reaches ``d_crit``, then Phase II
    runs until its sum reaches ``d_crit``, when failure occurs. Blocks to failure
    is the sum of the two phase contributions. This is the validated DLDR core.
    """
    n, n1 = _arrays(counts, phase1_lives)
    _, n2 = _arrays(counts, phase2_lives)
    d1 = float(np.sum(n / n1))
    d2 = float(np.sum(n / n2))
    if d1 <= 0 or d2 <= 0:
        raise ValueError("phase damages must be positive")
    blocks = d_crit / d1 + d_crit / d2
    return DamageResult(
        damage=1.0 / blocks if blocks > 0 else float("inf"),
        blocks_to_failure=blocks,
        cycles_to_failure=blocks * float(np.sum(n)),
        failed=False,
        rule="dldr",
        d_crit=d_crit,
    )


def dldr(counts, lives, *, exponent: float = 0.25, d_crit: float = 1.0) -> DamageResult:
    """Double Linear Damage Rule using the Manson-Halford knee split.

    Convenience wrapper: split lives into phases with
    :func:`manson_halford_phase_lives`, then accumulate with
    :func:`dldr_from_phase_lives`.
    """
    n1, n2 = manson_halford_phase_lives(lives, exponent=exponent)
    return dldr_from_phase_lives(counts, n1, n2, d_crit=d_crit)


def sn_curve_life(stress_amp, *, k: float, sd: float, nd: float,
                  variant: str = "original"):
    """Allowable cycles from a one-slope Woehler line with a knee at (SD, ND).

    Above the knee stress ``sd`` the line is ``N = nd * (s / sd) ** -k``. Below
    it the treatment follows the named Miner variant:

    - original: infinite life below the knee (Miner, J. Appl. Mech. 12 (1945)
      A159-A164, with the fatigue limit taken literally).
    - elementary: the slope ``k`` continues below the knee, the conservative
      elementary variant.
    - haibach: the line continues with the flatter fictitious slope
      ``2k - 1`` below the knee (Haibach, 1970, described in Haibach,
      Betriebsfestigkeit, Springer, 3rd ed., 2006).

    Returns an array of cycles to failure aligned with ``stress_amp``. These
    lives feed :func:`miner` for spectrum damage of stress-based collectives.
    """
    if k <= 0 or sd <= 0 or nd <= 0:
        raise ValueError("k, sd, and nd must be positive")
    s = np.asarray(stress_amp, dtype=np.float64)
    if np.any(s < 0) or not np.all(np.isfinite(s)):
        raise ValueError("stress amplitudes must be finite and non-negative")
    with np.errstate(divide="ignore"):
        above = nd * (s / sd) ** -k
        if variant == "original":
            below = np.full_like(s, np.inf)
        elif variant == "elementary":
            below = nd * (s / sd) ** -k
        elif variant == "haibach":
            below = nd * (s / sd) ** -(2.0 * k - 1.0)
        else:
            raise ValueError("variant must be original, elementary, or haibach")
    out = np.where(s >= sd, above, below)
    return out


def corten_dolan(counts, stresses, lives, *, d: float) -> DamageResult:
    """Corten-Dolan cumulative damage for one loading block.

    Cycles to failure is ``N_f,1 / sum(alpha_i (sigma_i/sigma_1)**d)`` where
    ``sigma_1`` is the maximum stress in the block, ``N_f,1`` its life, and
    ``alpha_i`` the cycle fractions. The exponent ``d`` controls sequence and
    level sensitivity. When ``d`` equals the inverse S-N slope the rule reduces
    exactly to Miner.
    """
    n, nf = _arrays(counts, lives)
    s = np.asarray(stresses, dtype=np.float64)
    if s.shape != n.shape:
        raise ValueError("stresses must match counts shape")
    if np.any(s <= 0):
        raise ValueError("Corten-Dolan requires positive stresses")
    k = int(np.argmax(s))
    sigma_1 = s[k]
    nf_1 = nf[k]
    alpha = n / np.sum(n)
    denom = float(np.sum(alpha * (s / sigma_1) ** d))
    cycles_to_failure = nf_1 / denom if denom > 0 else float("inf")
    blocks = cycles_to_failure / float(np.sum(n))
    return DamageResult(
        damage=1.0 / blocks if blocks > 0 else float("inf"),
        blocks_to_failure=blocks,
        cycles_to_failure=cycles_to_failure,
        failed=False,
        rule="corten_dolan",
        d_crit=1.0,
    )
