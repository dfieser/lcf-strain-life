"""Hysteresis-loop energy: closed-loop area by the shoelace formula.

The plastic strain energy density dissipated per cycle is the area enclosed by
one stress-strain loop, ``∮ σ dε``. We compute it with the **shoelace polygon
formula** on the ordered loop vertices (ADR / IMPLEMENTATION_REFERENCE §6): it is
robust to the non-monotonic, self-intersecting paths that ``trapezoid`` mishandle,
and needs no sorting (points must stay in acquisition order).

With stress in MPa and strain dimensionless (the internal convention), the area
is in **MJ/m³** directly (see :mod:`lcf.units`).
"""

from __future__ import annotations

import numpy as np

__all__ = ["loop_area", "shoelace_area"]


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
