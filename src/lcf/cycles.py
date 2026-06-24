"""Cycle reduction — segment a strain-controlled series into ordered cycles.

For constant-amplitude, fully-reversed strain control we segment by **peak-valley
(turning-point) detection on the strain waveform** (ADR-0003). This preserves
cycle order, so per-cycle evolution (hardening/softening, peak/valley drift,
energy per cycle) is retained — the tool's differentiator vs. rainflow-based,
order-discarding libraries.

Outputs an ordered per-cycle table plus the half-life cycle and the
cycles-to-failure ``N_f`` (configurable percent load-drop criterion, ADR-0004).
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from typing import ClassVar

import numpy as np
import pandas as pd

from .ingest import TestRun
from .models import AnalysisParams
from . import schema

__all__ = [
    "find_turning_points",
    "ReducedCycles",
    "reduce_cycles",
    "find_failure_cycle",
]


def find_turning_points(x, *, min_range: float = 0.0) -> np.ndarray:
    """Indices of local extrema (reversals) in ``x``.

    Flats (consecutive equal values) do not count as reversals: the direction is
    forward-filled across them. Endpoints are not returned.

    ``min_range`` applies an amplitude gate (hysteresis filter): small reversal
    pairs whose swing is below ``min_range`` are removed, so sensor noise does not
    fabricate cycles. With ``min_range=0`` no gating is applied. For noisy lab
    data set ``min_range`` to a few times the noise amplitude (ADR-0003; H7).
    """
    x = np.asarray(x, dtype=np.float64)
    if x.size < 3:
        return np.array([], dtype=np.intp)
    dx = np.diff(x)
    sign = np.sign(dx)
    nz = sign != 0
    if not nz.any():
        return np.array([], dtype=np.intp)
    # Forward-fill zero (flat) signs with the most recent nonzero sign.
    idx = np.where(nz, np.arange(sign.size), 0)
    np.maximum.accumulate(idx, out=idx)
    sign_ff = sign[idx]
    # A turning point is where the (filled) slope sign changes.
    tp = (np.where(np.diff(sign_ff) != 0)[0] + 1).astype(np.intp)

    if min_range > 0 and tp.size >= 2:
        tp = _gate_extrema(tp, x[tp], min_range)
    return tp


def _gate_extrema(idx: np.ndarray, vals: np.ndarray, gate: float) -> np.ndarray:
    """Remove alternating-extrema pairs whose swing is below ``gate``.

    Extrema alternate (max, min, ...); removing an adjacent pair merges the two
    same-direction runs around it, preserving alternation. Iterates until no
    sub-gate swing remains (small-cycle elimination).
    """
    keep = list(map(int, idx))
    vlist = list(map(float, vals))
    changed = True
    while changed and len(keep) >= 2:
        changed = False
        for i in range(len(keep) - 1):
            if abs(vlist[i + 1] - vlist[i]) < gate:
                del keep[i : i + 2]
                del vlist[i : i + 2]
                changed = True
                break
    return np.asarray(keep, dtype=np.intp)


@dataclass
class ReducedCycles:
    """Ordered per-cycle reduction of one test."""

    __test__: ClassVar[bool] = False

    table: pd.DataFrame      # one row per cycle (see columns below)
    n_cycles: int
    n_f: int                 # cycles to failure
    half_life_cycle: int     # 1-based cycle index nearest N_f/2
    runout: bool             # True if the failure criterion never triggered
    failure_criterion_pct: float

    #: table columns
    COLUMNS: ClassVar[tuple[str, ...]] = (
        "cycle", "idx_loop_start", "idx_loop_end", "idx_peak", "idx_valley",
        "stress_max", "stress_min", "strain_max", "strain_min",
    )


def find_failure_cycle(
    peak_stress: np.ndarray,
    *,
    pct: float,
    stabilized_value: float | None = None,
) -> tuple[int, bool]:
    """Locate the failure cycle from a per-cycle peak (tensile) stress series.

    Failure = the first cycle **at or after the maximum-load (cyclically hardened)
    cycle** whose peak stress drops below ``(1 - pct/100) * stabilized_value``
    (ADR-0004).

    The stabilized reference defaults to the **maximum** peak stress, which is
    robust to two common artifacts the naive series-midpoint is not (H2/M3):
    acquisition continuing past failure (a low tail cannot lower the max) and the
    initial hardening transient (searching only from the peak-load cycle ignores
    the rising part). A non-positive reference (e.g. an all-compressive or
    sign-flipped column) is rejected.

    Returns ``(n_f, runout)`` — ``n_f`` is a 1-based cycle count; ``runout`` is
    True if the threshold was never crossed (then ``n_f`` is the total cycles).
    """
    peak = np.asarray(peak_stress, dtype=np.float64)
    n = peak.size
    if n == 0:
        return 0, True
    if stabilized_value is None:
        stabilized_value = float(np.nanmax(peak))  # cyclically-hardened peak
    if not (stabilized_value > 0):
        raise ValueError(
            f"stabilized peak tensile stress must be positive, got {stabilized_value}; "
            "check the sign/units of the stress data (peak load should be tensile)."
        )
    threshold = (1.0 - pct / 100.0) * stabilized_value
    start = int(np.nanargmax(peak))  # ignore the initial hardening transient
    below = np.where(peak[start:] < threshold)[0]
    if below.size == 0:
        return n, True
    return int(start + below[0] + 1), False  # 1-based


def reduce_cycles(test: TestRun, params: AnalysisParams | None = None) -> ReducedCycles:
    """Segment a :class:`~lcf.ingest.TestRun` into an ordered per-cycle table.

    Cycles are bounded by consecutive strain **peaks** (each peak->next-peak
    window is one closed loop). Per cycle we record the loop sample-index window
    (for energy integration), the peak/valley sample indices, and the max/min
    true stress and strain within the loop window.
    """
    params = params or AnalysisParams()
    strain = test.data[schema.COL_STRAIN_TRUE].to_numpy()
    stress = test.data[schema.COL_STRESS_TRUE].to_numpy()

    # Amplitude gate for noise rejection: explicit value, else a mild default of
    # 2% of the total strain range (won't remove genuine constant-amplitude loops).
    if params.min_strain_range is not None:
        gate = params.min_strain_range
    else:
        rng = float(np.nanmax(strain) - np.nanmin(strain)) if strain.size else 0.0
        gate = 0.02 * rng

    tp = find_turning_points(strain, min_range=gate)
    if tp.size < 2:
        raise ValueError(
            "could not detect at least two reversals; data does not contain a "
            "complete cycle (or needs pre-filtering / a smaller min_strain_range)."
        )
    if tp.size > strain.size // 4:
        warnings.warn(
            f"detected {tp.size} reversals from {strain.size} samples — implausibly "
            "dense; data may be noisy. Consider setting AnalysisParams.min_strain_range.",
            stacklevel=2,
        )

    # Classify turning points as peaks (local maxima) or valleys (local minima).
    is_peak = strain[tp] >= np.maximum(strain[tp - 1], strain[tp + 1])
    peaks = tp[is_peak]
    valleys = tp[~is_peak]

    # Use consecutive peaks as loop boundaries; fall back to valleys if needed.
    bounds = peaks if peaks.size >= 2 else valleys
    if bounds.size < 2:
        raise ValueError("fewer than two same-type reversals; cannot form a cycle.")

    rows = []
    for k in range(bounds.size - 1):
        i0, i1 = int(bounds[k]), int(bounds[k + 1])
        w = slice(i0, i1 + 1)
        s_win = stress[w]
        e_win = strain[w]
        # peak/valley sample indices within the window (absolute indices)
        idx_peak = i0 + int(np.argmax(s_win))
        idx_valley = i0 + int(np.argmin(s_win))
        rows.append(
            {
                "cycle": k + 1,
                "idx_loop_start": i0,
                "idx_loop_end": i1,
                "idx_peak": idx_peak,
                "idx_valley": idx_valley,
                "stress_max": float(s_win.max()),
                "stress_min": float(s_win.min()),
                "strain_max": float(e_win.max()),
                "strain_min": float(e_win.min()),
            }
        )

    table = pd.DataFrame(rows, columns=list(ReducedCycles.COLUMNS))
    n_cycles = len(table)

    n_f, runout = find_failure_cycle(
        table["stress_max"].to_numpy(), pct=params.failure_criterion_pct
    )
    # half-life cycle nearest N_f/2 (1-based, clamped to available cycles)
    half_life_cycle = max(1, min(n_cycles, int(round(n_f / 2))))

    return ReducedCycles(
        table=table,
        n_cycles=n_cycles,
        n_f=n_f,
        half_life_cycle=half_life_cycle,
        runout=runout,
        failure_criterion_pct=params.failure_criterion_pct,
    )
