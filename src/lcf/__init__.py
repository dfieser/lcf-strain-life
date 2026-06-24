"""lcf — material-agnostic Low Cycle Fatigue (LCF) strain-life analysis.

Core library for reducing strain-controlled fatigue test data and fitting the
standard strain-life models (Basquin, Coffin-Manson, Ramberg-Osgood) plus
mean-stress corrections. All analysis uses *true* stress/strain; the fatigue
exponents ``b`` and ``c`` are negative.

See ``docs/`` for the equations, workflow, and design decisions (ADRs).

The ``lcf.plots`` and ``lcf.mcp_server`` modules are intentionally not imported
here so that importing :mod:`lcf` does not pull in matplotlib / the MCP SDK.
"""

from __future__ import annotations

__version__ = "0.1.0"

from .cycles import (
    ReducedCycles,
    find_failure_cycle,
    find_turning_points,
    reduce_cycles,
)
from .energy import loop_area, shoelace_area
from .fits import (
    BasquinFit,
    CoffinMansonFit,
    ConsistencyCheck,
    RambergOsgoodFit,
    StrainLifeFit,
    check_consistency,
    fit_basquin,
    fit_coffin_manson,
    fit_ramberg_osgood,
    fit_strain_life,
    transition_reversals,
)
from .ingest import TestRun, from_dataframe, from_timeseries, read_csv
from .life import (
    elastic_strain_life,
    plastic_strain_life,
    predict_reversals,
    predict_reversals_from_total_strain,
    total_strain_life,
)
from .meanstress import (
    equivalent_fully_reversed_stress,
    modified_morrow_strain_life,
    morrow_strain_life,
    swt_parameter,
    walker_gamma_steel,
)
from .metrics import PerCycleMetrics, estimate_modulus, per_cycle_metrics
from .models import AnalysisParams, MeanStressModel, TestMetadata
from .pipeline import (
    MaterialAnalysis,
    TestAnalysis,
    analyze_material,
    analyze_test,
    fit_from_summary,
)

__all__ = [
    "__version__",
    # models
    "TestMetadata", "AnalysisParams", "MeanStressModel",
    # ingestion
    "TestRun", "from_timeseries", "from_dataframe", "read_csv",
    # cycles
    "reduce_cycles", "ReducedCycles", "find_turning_points", "find_failure_cycle",
    # metrics / energy
    "per_cycle_metrics", "PerCycleMetrics", "estimate_modulus",
    "loop_area", "shoelace_area",
    # fits
    "fit_strain_life", "fit_basquin", "fit_coffin_manson", "fit_ramberg_osgood",
    "StrainLifeFit", "BasquinFit", "CoffinMansonFit", "RambergOsgoodFit",
    "ConsistencyCheck", "transition_reversals", "check_consistency",
    # mean stress
    "equivalent_fully_reversed_stress", "walker_gamma_steel",
    "morrow_strain_life", "modified_morrow_strain_life", "swt_parameter",
    # life
    "total_strain_life", "elastic_strain_life", "plastic_strain_life",
    "predict_reversals", "predict_reversals_from_total_strain",
    # pipeline
    "analyze_test", "analyze_material", "fit_from_summary",
    "TestAnalysis", "MaterialAnalysis",
]
