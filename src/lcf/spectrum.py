"""Spectrum life: the end-to-end variable-amplitude chain.

Ties the Phase 2 pieces together. A strain history and a paired stress history
go in. Rainflow counts the strain, each counted cycle gets a mean-stress
correction and a life from the strain-life curve, and the chosen damage rule
returns blocks and cycles to failure (research sections 1.4 and 2).

Mean-stress methods for the per-cycle life: ``none``, ``morrow``, and ``swt``.
SWT is the default for variable amplitude.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from . import counting, damage, life

__all__ = ["SpectrumResult", "spectrum_life"]


@dataclass
class SpectrumResult:
    """Result of a spectrum life calculation."""

    cycles: pd.DataFrame        # per-cycle table with amplitude, mean, N_f, damage
    damage_per_block: float
    blocks_to_failure: float
    cycles_to_failure: float
    mean_stress_method: str
    rule: str


def _per_cycle_life(amp, sigma_max, sigma_m, *, method, sigma_f, b, eps_f, c, E):
    if method == "none":
        return life.predict_reversals_from_total_strain(amp, sigma_f, b, eps_f, c, E)
    if method == "swt":
        return life.predict_reversals_swt(sigma_max, amp, sigma_f, b, eps_f, c, E)
    if method == "morrow":
        return life.predict_reversals_morrow(amp, sigma_m, sigma_f, b, eps_f, c, E)
    raise ValueError(f"mean_stress_method must be none, morrow, or swt, got {method!r}")


def spectrum_life(
    strain_history,
    stress_history,
    *,
    sigma_f: float,
    b: float,
    eps_f: float,
    c: float,
    E: float,
    mean_stress_method: str = "swt",
    rule: str = "miner",
    close_residue: bool = False,
    d_crit: float = 1.0,
) -> SpectrumResult:
    """Predict life under a variable-amplitude strain history.

    Parameters mirror the strain-life constants from Phase 1. ``strain_history``
    and ``stress_history`` must be aligned sample arrays. Returns a
    :class:`SpectrumResult` whose ``cycles`` table carries the per-cycle
    amplitude, mean stress, reversals to failure, and damage.
    """
    strain = np.asarray(strain_history, dtype=np.float64)
    stress = np.asarray(stress_history, dtype=np.float64)
    if strain.shape != stress.shape:
        raise ValueError("strain_history and stress_history must have equal length")

    cyc = counting.count_rainflow(strain, close_residue=close_residue)
    if len(cyc) == 0:
        raise ValueError("no cycles counted; history has no complete reversal")

    i0 = cyc["i_start"].to_numpy()
    i1 = cyc["i_end"].to_numpy()
    s0 = stress[i0]
    s1 = stress[i1]
    sigma_max = np.maximum(s0, s1)
    sigma_m = 0.5 * (s0 + s1)
    amp = cyc["amplitude"].to_numpy()  # strain amplitude per cycle

    nf = np.array([
        _per_cycle_life(a, smax, sm, method=mean_stress_method,
                        sigma_f=sigma_f, b=b, eps_f=eps_f, c=c, E=E)
        for a, smax, sm in zip(amp, sigma_max, sigma_m)
    ])

    counts = cyc["count"].to_numpy()
    if rule == "miner":
        dr = damage.miner(counts, nf, d_crit=d_crit)
    elif rule == "dldr":
        dr = damage.dldr(counts, nf, d_crit=d_crit)
    else:
        raise ValueError(f"rule must be miner or dldr, got {rule!r}")

    out = cyc.copy()
    out["sigma_max"] = sigma_max
    out["mean_stress"] = sigma_m
    out["reversals_to_failure"] = nf
    out["damage"] = counts / nf
    return SpectrumResult(
        cycles=out,
        damage_per_block=dr.damage,
        blocks_to_failure=dr.blocks_to_failure,
        cycles_to_failure=dr.cycles_to_failure,
        mean_stress_method=mean_stress_method,
        rule=rule,
    )
