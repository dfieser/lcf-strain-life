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


def find_turning_points(x) -> np.ndarray:
    """Indices of local extrema (reversals) in ``x``.

    Flats (consecutive equal values) do not count as reversals: the direction is
    forward-filled across them. Endpoints are not returned. Robust to noise only
    to the extent the signal is already turning-point-reducible; pre-filter noisy
    lab data first (see docs/design/IMPLEMENTATION_REFERENCE.md §3).
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
    changes = np.where(np.diff(sign_ff) != 0)[0] + 1
    return changes.astype(np.intp)


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

    Failure = first cycle whose peak stress has dropped below
    ``(1 - pct/100) * stabilized_value`` (ADR-0004). If ``stabilized_value`` is
    None, the half-life peak stress is used as the stabilized reference.

    Returns ``(n_f, runout)`` where ``n_f`` is a 1-based cycle count and
    ``runout`` is True if the threshold was never crossed (then ``n_f`` is the
    total number of cycles).
    """
    peak = np.asarray(peak_stress, dtype=np.float64)
    n = peak.size
    if n == 0:
        return 0, True
    if stabilized_value is None:
        stabilized_value = float(peak[(n - 1) // 2])  # half-life reference
    threshold = (1.0 - pct / 100.0) * stabilized_value
    below = np.where(peak < threshold)[0]
    if below.size == 0:
        return n, True
    return int(below[0] + 1), False  # 1-based


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

    tp = find_turning_points(strain)
    if tp.size < 2:
        raise ValueError(
            "could not detect at least two reversals; data does not contain a "
            "complete cycle (or needs pre-filtering)."
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
