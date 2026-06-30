"""High-level orchestration: the full LCF analysis pipeline.

* :func:`analyze_test` runs one test through ingest-already-done -> cycle
  reduction -> per-cycle metrics, and summarizes the stabilized (half-life) and
  peak-hardened states.
* :func:`analyze_material` runs several tests (different strain amplitudes) and
  fits the multi-test strain-life models from their half-life summaries.

This mirrors dev/docs/design/WORKFLOW.md stages 2-4.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar

import pandas as pd

from . import cycles, fits, metrics
from .ingest import TestRun
from .models import AnalysisParams


@dataclass
class TestAnalysis:
    """Per-test analysis result: reduction + metrics + stabilized summary."""

    __test__: ClassVar[bool] = False

    name: str
    reduced: cycles.ReducedCycles
    metrics: metrics.PerCycleMetrics
    summary: dict


@dataclass
class MaterialAnalysis:
    """Multi-test analysis: per-test results + the fitted strain-life model."""

    material: str | None
    tests: list[TestAnalysis]
    summary_table: pd.DataFrame
    fit: fits.StrainLifeFit | None
    notes: list[str] = field(default_factory=list)


def analyze_test(test: TestRun, params: AnalysisParams | None = None) -> TestAnalysis:
    """Reduce one test and compute its per-cycle metrics + stabilized summary."""
    params = params or AnalysisParams()
    reduced = cycles.reduce_cycles(test, params)
    pcm = metrics.per_cycle_metrics(test, reduced)

    hl = pcm.at_half_life()
    ph = pcm.at_peak_hardened()
    summary = {
        "name": test.metadata.name,
        "material": test.metadata.material,
        "E": pcm.E,
        "n_cycles": reduced.n_cycles,
        "n_f": reduced.n_f,
        "reversals": 2 * reduced.n_f,
        "runout": reduced.runout,
        "half_life_cycle": reduced.half_life_cycle,
        # stabilized (half-life) values
        "stress_amp": float(hl["stress_amp"]),
        "mean_stress": float(hl["mean_stress"]),
        "total_strain_amp": float(hl["total_strain_amp"]),
        "elastic_strain_amp": float(hl["elastic_strain_amp"]),
        "plastic_strain_amp": float(hl["plastic_strain_amp"]),
        "r_tc": float(hl["r_tc"]),
        "energy_half_life": float(hl["energy_density"]),
        # peak-hardened values
        "peak_hardened_cycle": pcm.peak_hardened_cycle,
        "energy_peak_hardened": float(ph["energy_density"]),
        "stress_amp_peak_hardened": float(ph["stress_amp"]),
        "failure_criterion_pct": reduced.failure_criterion_pct,
    }
    return TestAnalysis(name=test.metadata.name, reduced=reduced, metrics=pcm, summary=summary)


def build_summary_table(analyses: list[TestAnalysis]) -> pd.DataFrame:
    """One row per test of the half-life quantities needed for strain-life fitting."""
    return pd.DataFrame([a.summary for a in analyses])


def fit_from_summary(
    summary_table: pd.DataFrame, params: AnalysisParams | None = None
) -> tuple[fits.StrainLifeFit | None, list[str]]:
    """Fit strain-life models from a per-test half-life summary table.

    Runout tests (censored life) are excluded from fitting. Returns the fit (or
    None if too few valid tests) and a list of notes about what was excluded.
    """
    params = params or AnalysisParams()
    notes: list[str] = []

    df = summary_table.copy()
    n_runout = int(df["runout"].sum()) if "runout" in df else 0
    if n_runout:
        notes.append(f"excluded {n_runout} run-out test(s) from strain-life fitting")
        df = df[~df["runout"]]

    if len(df) < 2:
        notes.append("fewer than 2 failed tests, cannot fit strain-life models")
        return None, notes

    E = float(df["E"].mean())
    fit = fits.fit_strain_life(
        df["total_strain_amp"].to_numpy(),
        df["stress_amp"].to_numpy(),
        df["reversals"].to_numpy(),
        E,
        plastic_strain_amp=df["plastic_strain_amp"].to_numpy(),
        min_plastic_strain=params.min_plastic_strain,
        refine_nonlinear=params.refine_nonlinear,
    )
    if fit.consistency is not None and not fit.consistency.masing_ok:
        notes.append(
            f"non-Masing: fitted n'={fit.consistency.n_fitted:.3f} vs "
            f"b/c={fit.consistency.n_from_bc:.3f} (rel diff "
            f"{fit.consistency.n_rel_diff:.0%})"
        )
    return fit, notes


def analyze_material(
    tests: list[TestRun],
    params: AnalysisParams | None = None,
    *,
    material: str | None = None,
) -> MaterialAnalysis:
    """Analyze several tests and fit the material's strain-life models."""
    params = params or AnalysisParams()
    analyses = [analyze_test(t, params) for t in tests]
    summary_table = build_summary_table(analyses)
    fit, notes = fit_from_summary(summary_table, params)
    if material is None and tests:
        material = tests[0].metadata.material
    return MaterialAnalysis(
        material=material, tests=analyses, summary_table=summary_table, fit=fit, notes=notes
    )
