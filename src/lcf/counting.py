"""Rainflow cycle counting for variable-amplitude histories (ASTM E1049-85).

This is an in-house three-point rainflow counter, the Downing and Socie form
embodied in ASTM E1049. It preserves the original sample indices of every
counted cycle, which is what lets the rest of the toolkit recover per-cycle
stress and strain evolution rather than just a histogram (ADR-0011).

The counter operates on one signal, usually the strain history. To get a mean
stress per cycle, map the returned ``i_start`` and ``i_end`` indices into the
paired stress signal with :func:`mean_stress_per_cycle`.

Residue handling follows E1049: leftover reversals are reported as half cycles.
Set ``close_residue=True`` for the common repeat-history closure, which counts
the residue against a repeat of itself so the largest range closes as a full
cycle.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass

import numpy as np
import pandas as pd

__all__ = ["reversals", "extract_cycles", "count_rainflow", "mean_stress_per_cycle"]


@dataclass
class Cycle:
    """One counted cycle with indices into the original series."""

    rng: float          # range
    mean: float         # mean of the two turning values
    count: float        # 1.0 full cycle, 0.5 half cycle
    i_start: int        # index of the first turning point
    i_end: int          # index of the second turning point


def _reduce_points(points):
    """Reduce ``(index, value)`` points to alternating turning points.

    Collapses consecutive equal values and drops points that are not direction
    changes. The first and last surviving points are kept because they bound the
    sequence. Original indices are preserved.
    """
    collapsed = []
    for p in points:
        if collapsed and p[1] == collapsed[-1][1]:
            continue
        collapsed.append((int(p[0]), float(p[1])))
    if len(collapsed) <= 2:
        return collapsed
    out = [collapsed[0]]
    for k in range(1, len(collapsed) - 1):
        a, b, c = collapsed[k - 1][1], collapsed[k][1], collapsed[k + 1][1]
        if (b - a) * (c - b) < 0:
            out.append(collapsed[k])
    out.append(collapsed[-1])
    return out


def reversals(series):
    """Yield ``(index, value)`` turning points of ``series``, including the ends.

    Consecutive equal values are collapsed so flats do not create spurious
    reversals. The first and last retained points are always yielded, because
    they bound the history for counting.
    """
    x = np.asarray(series, dtype=np.float64)
    if x.size == 0:
        return
    if not np.all(np.isfinite(x)):
        raise ValueError("series contains NaN or inf, clean the data before counting")
    for p in _reduce_points([(i, x[i]) for i in range(x.size)]):
        yield p


def _three_point(points):
    """Run the E1049 three-point algorithm over a list of (index, value) points.

    Returns the list of counted :class:`Cycle` plus the residual stack of points
    that did not close.
    """
    stack: deque = deque()
    cycles: list[Cycle] = []
    for p in points:
        stack.append(p)
        while len(stack) >= 3:
            (i0, x0) = stack[-3]
            (i1, x1) = stack[-2]
            (i2, x2) = stack[-1]
            X = abs(x2 - x1)
            Y = abs(x1 - x0)
            if X < Y:
                break
            if len(stack) == 3:
                # Y contains the start, count it as a half cycle and drop the oldest
                cycles.append(Cycle(Y, 0.5 * (x0 + x1), 0.5, i0, i1))
                stack.popleft()
            else:
                # Y is a closed interior loop, count a full cycle, remove its two
                # middle points and keep the enclosing path (material memory)
                cycles.append(Cycle(Y, 0.5 * (x0 + x1), 1.0, i0, i1))
                stack.remove(stack[-3])
                stack.remove(stack[-2])
    return cycles, list(stack)


def extract_cycles(series, *, close_residue: bool = False) -> list[Cycle]:
    """Count rainflow cycles in ``series`` (ASTM E1049 three-point).

    With ``close_residue=False`` the history is counted once and any unclosed
    reversals are reported as half cycles, which reproduces the ASTM E1049 worked
    example. With ``close_residue=True`` the reversal sequence is rotated to begin
    and end at the global maximum before counting, the standard treatment for a
    repeating history, so every reversal closes into a full cycle.
    """
    pts = list(reversals(series))

    if close_residue and len(pts) > 2:
        vals = [v for _, v in pts]
        kmax = int(np.argmax(vals))
        rotated = _reduce_points(pts[kmax:] + pts[:kmax] + [pts[kmax]])
        cycles, residue = _three_point(rotated)
    else:
        cycles, residue = _three_point(pts)

    # report any leftover reversals as half cycles
    for i in range(len(residue) - 1):
        i0, x0 = residue[i]
        i1, x1 = residue[i + 1]
        cycles.append(Cycle(abs(x1 - x0), 0.5 * (x0 + x1), 0.5, i0, i1))
    return cycles


def count_rainflow(series, *, close_residue: bool = False) -> pd.DataFrame:
    """Rainflow count as a tidy DataFrame, ready for damage accumulation.

    Columns: ``range``, ``amplitude`` (range/2), ``mean``, ``count``,
    ``i_start``, ``i_end``, ``peak`` (max of the two turning values), and
    ``valley`` (min of the two turning values).
    """
    cycles = extract_cycles(series, close_residue=close_residue)
    x = np.asarray(series, dtype=np.float64)
    rows = []
    for c in cycles:
        v0, v1 = x[c.i_start], x[c.i_end]
        rows.append(
            {
                "range": c.rng,
                "amplitude": 0.5 * c.rng,
                "mean": c.mean,
                "count": c.count,
                "i_start": int(c.i_start),
                "i_end": int(c.i_end),
                "peak": float(max(v0, v1)),
                "valley": float(min(v0, v1)),
            }
        )
    cols = ["range", "amplitude", "mean", "count", "i_start", "i_end", "peak", "valley"]
    return pd.DataFrame(rows, columns=cols)


def mean_stress_per_cycle(cycles: pd.DataFrame, stress) -> np.ndarray:
    """Mean stress for each counted cycle from a paired stress signal.

    Uses the stress values at the cycle turning-point indices, so the strain
    history can be counted while the stress history supplies the mean. Returns an
    array aligned with the rows of ``cycles``.
    """
    s = np.asarray(stress, dtype=np.float64)
    i0 = cycles["i_start"].to_numpy()
    i1 = cycles["i_end"].to_numpy()
    return 0.5 * (s[i0] + s[i1])
