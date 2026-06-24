"""Per-cycle metrics derived from the reduced cycles.

For each cycle: stress amplitude, mean stress, total/elastic/plastic strain
amplitude, tension/compression ratio, and the hysteresis energy density. Plastic
strain amplitude uses the **computed** form ``Δε_p/2 = Δε_t/2 − Δσ/(2E)``
(the practical standard default, ADR-0005, IMPLEMENTATION_REFERENCE §1).

Also provides :func:`estimate_modulus` for when ``E`` is not supplied.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

import numpy as np
import pandas as pd

from . import energy, schema
from .cycles import ReducedCycles
from .ingest import TestRun

__all__ = ["PerCycleMetrics", "per_cycle_metrics", "estimate_modulus"]


@dataclass
class PerCycleMetrics:
    """Per-cycle metric table plus stabilized summaries."""

    __test__: ClassVar[bool] = False

    table: pd.DataFrame      # reduced columns + the metric columns below
    E: float                 # modulus used (MPa)
    half_life_cycle: int
    peak_hardened_cycle: int

    METRIC_COLUMNS: ClassVar[tuple[str, ...]] = (
        "stress_amp", "mean_stress", "total_strain_amp", "elastic_strain_amp",
        "plastic_strain_amp", "r_tc", "energy_density",
    )

    def at_half_life(self) -> pd.Series:
        return self.table.loc[self.table["cycle"] == self.half_life_cycle].iloc[0]

    def at_peak_hardened(self) -> pd.Series:
        return self.table.loc[self.table["cycle"] == self.peak_hardened_cycle].iloc[0]


def estimate_modulus(strain, stress, *, frac: float = 0.25) -> float:
    """Estimate Young's modulus from the initial elastic unloading of one loop.

    Regresses stress on strain over the first ``frac`` of the samples following a
    strain reversal (where the response is elastic), returning ``|slope|`` (MPa).

    Best-effort only, supplying a measured ``E`` is strongly preferred. The fixed
    ``frac`` assumes the window begins at a reversal (true for the loops produced
    by :func:`lcf.cycles.reduce_cycles`) and that the initial segment is elastic.
    A long plastic plateau right after the peak will bias the slope low.
    """
    s = np.asarray(strain, dtype=np.float64)
    y = np.asarray(stress, dtype=np.float64)
    n = s.size
    if n < 4:
        raise ValueError("need at least 4 samples to estimate modulus")
    k = max(2, int(round(frac * n)))
    slope = np.polyfit(s[:k], y[:k], 1)[0]
    return abs(float(slope))


def per_cycle_metrics(
    test: TestRun,
    reduced: ReducedCycles,
    *,
    E: float | None = None,
) -> PerCycleMetrics:
    """Compute per-cycle metrics for a reduced test.

    ``E`` resolution order: explicit argument -> ``test.metadata.E`` -> estimate
    from the largest-amplitude loop's elastic unloading.
    """
    strain = test.data[schema.COL_STRAIN_TRUE].to_numpy()
    stress = test.data[schema.COL_STRESS_TRUE].to_numpy()
    tbl = reduced.table

    if E is None:
        E = test.metadata.E
    if E is None:
        # estimate from the loop with the largest strain amplitude
        amp = (tbl["strain_max"] - tbl["strain_min"]).to_numpy()
        kmax = int(np.argmax(amp))
        i0, i1 = int(tbl["idx_loop_start"].iloc[kmax]), int(tbl["idx_loop_end"].iloc[kmax])
        E = estimate_modulus(strain[i0 : i1 + 1], stress[i0 : i1 + 1])
    if E <= 0:
        raise ValueError(f"Young's modulus must be positive, got {E}")

    stress_max = tbl["stress_max"].to_numpy()
    stress_min = tbl["stress_min"].to_numpy()
    strain_max = tbl["strain_max"].to_numpy()
    strain_min = tbl["strain_min"].to_numpy()

    stress_amp = 0.5 * (stress_max - stress_min)
    mean_stress = 0.5 * (stress_max + stress_min)
    total_strain_amp = 0.5 * (strain_max - strain_min)
    elastic_strain_amp = stress_amp / E
    plastic_strain_amp = total_strain_amp - elastic_strain_amp

    # Tension/compression ratio |σ_max| / |σ_min|. Meaningful for reversed loops
    # (σ_max > 0 > σ_min), NaN when σ_min == 0, and not a true T/C ratio for
    # same-sign (non-reversed) loops. See docs (L5).
    with np.errstate(divide="ignore", invalid="ignore"):
        r_tc = np.abs(stress_max) / np.abs(stress_min)
        r_tc = np.where(np.isfinite(r_tc), r_tc, np.nan)

    # energy density per loop (shoelace over the loop window)
    e_density = np.empty(len(tbl), dtype=np.float64)
    for j, (i0, i1) in enumerate(
        zip(tbl["idx_loop_start"].to_numpy(), tbl["idx_loop_end"].to_numpy())
    ):
        i0, i1 = int(i0), int(i1)
        e_density[j] = energy.loop_area(strain[i0 : i1 + 1], stress[i0 : i1 + 1])

    out = tbl.copy()
    out["stress_amp"] = stress_amp
    out["mean_stress"] = mean_stress
    out["total_strain_amp"] = total_strain_amp
    out["elastic_strain_amp"] = elastic_strain_amp
    out["plastic_strain_amp"] = plastic_strain_amp
    out["r_tc"] = r_tc
    out["energy_density"] = e_density

    peak_hardened_cycle = int(out.loc[out["stress_amp"].idxmax(), "cycle"])

    return PerCycleMetrics(
        table=out,
        E=float(E),
        half_life_cycle=reduced.half_life_cycle,
        peak_hardened_cycle=peak_hardened_cycle,
    )
