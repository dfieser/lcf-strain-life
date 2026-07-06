"""lcf: material-agnostic Low Cycle Fatigue (LCF) strain-life analysis.

Core library for reducing strain-controlled fatigue test data and fitting the
standard strain-life models (Basquin, Coffin-Manson, Ramberg-Osgood) plus
mean-stress corrections. All analysis uses *true* stress/strain. The fatigue
exponents ``b`` and ``c`` are negative.

See ``docs/`` for the equations, workflow, and design decisions (ADRs).

The ``lcf.plots`` and ``lcf.mcp_server`` modules are intentionally not imported
here so that importing :mod:`lcf` does not pull in matplotlib / the MCP SDK.
"""

from __future__ import annotations

__version__ = "0.1.1"

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

# Phase 2: variable amplitude, damage, notch, statistics, high temperature
from .counting import (
    count_level_crossings,
    count_peaks,
    count_rainflow,
    extract_cycles,
    mean_stress_per_cycle,
    racetrack_filter,
)
from .damage import (
    DamageResult,
    corten_dolan,
    dldr,
    manson_halford_phase_lives,
    miner,
    sn_curve_life,
)
from .notch import (
    glinka_local,
    kf_neuber,
    kf_peterson,
    neuber_local,
    notch_local_life,
    notch_sensitivity,
)
from .stats import (
    LogLifeFit,
    confidence_interval,
    design_life,
    fit_log_life,
    fit_log_life_censored,
    generalized_esd,
    grubbs_test,
    owen_tolerance_factor,
    prediction_interval,
    regression_diagnostics,
)
from .hightemp import (
    CreepFatigueResult,
    creep_fatigue_damage,
    creep_fatigue_envelope_check,
    frequency_modified_plastic_strain,
    interpolate_constants,
)
from .multiaxial import (
    brown_miller,
    critical_plane_search,
    fatemi_socie,
    swt_multiaxial,
    von_mises_equivalent_strain,
)
from .spectrum import SpectrumResult, spectrum_life

from .citations import CITATIONS, get_citations

# Phase 3: estimation of strain-life constants from monotonic properties
from .estimate import (
    ESTIMATION_METHODS,
    EstimatedConstants,
    estimate_hardness_method,
    estimate_medians,
    estimate_modified_universal_slopes,
    estimate_strain_life_constants,
    estimate_uniform_material_law,
    estimate_universal_slopes,
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
    # phase 2: counting / damage
    "count_rainflow", "extract_cycles", "mean_stress_per_cycle",
    "count_level_crossings", "count_peaks", "racetrack_filter",
    "miner", "dldr", "corten_dolan", "manson_halford_phase_lives", "DamageResult",
    "sn_curve_life",
    # phase 2: notch
    "neuber_local", "glinka_local", "notch_local_life",
    "kf_peterson", "kf_neuber", "notch_sensitivity",
    # phase 2: statistics
    "fit_log_life", "fit_log_life_censored", "design_life", "owen_tolerance_factor",
    "confidence_interval", "prediction_interval", "LogLifeFit",
    "grubbs_test", "generalized_esd", "regression_diagnostics",
    # phase 2: high temperature
    "creep_fatigue_damage", "creep_fatigue_envelope_check",
    "frequency_modified_plastic_strain", "interpolate_constants", "CreepFatigueResult",
    # phase 2: multiaxial survey
    "fatemi_socie", "brown_miller", "swt_multiaxial",
    "von_mises_equivalent_strain", "critical_plane_search",
    # phase 2: spectrum life
    "spectrum_life", "SpectrumResult",
    # phase 3: constant estimation
    "estimate_strain_life_constants", "estimate_medians",
    "estimate_uniform_material_law", "estimate_universal_slopes",
    "estimate_modified_universal_slopes", "estimate_hardness_method",
    "EstimatedConstants", "ESTIMATION_METHODS",
    # provenance
    "CITATIONS", "get_citations",
]
