"""Validated data models: test metadata, analysis parameters, and enums.

Pydantic models are used for everything that crosses the MCP boundary (so inputs
are validated and outputs serialize to JSON schema). Numerical result containers
that wrap arrays/DataFrames live with their producing modules and use dataclasses.
"""

from __future__ import annotations

from enum import Enum
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field, model_validator


class MeanStressModel(str, Enum):
    """Mean-stress correction selector (ADR-0006)."""

    NONE = "none"
    MORROW = "morrow"
    MODIFIED_MORROW = "modified_morrow"
    SWT = "swt"
    WALKER = "walker"


class TestMetadata(BaseModel):
    """Scalar metadata describing one strain-controlled fatigue test.

    Units follow the internal convention (ADR-0002): area in mm², ``E`` in MPa,
    gauge length in mm. ``R`` is the strain ratio (−1 for fully reversed).
    """

    model_config = ConfigDict(extra="forbid")

    __test__: ClassVar[bool] = False  # not a pytest test class

    name: str = Field(..., description="Unique test/specimen identifier.")
    area: float | None = Field(
        None, gt=0, description="Original cross-sectional area A0 (mm²). Required to "
        "derive stress from force."
    )
    E: float | None = Field(
        None, gt=0, description="Young's modulus (MPa). If omitted, may be estimated "
        "from the elastic slope."
    )
    R: float = Field(-1.0, description="Strain ratio ε_min/ε_max (−1 = fully reversed).")
    gauge_length: float | None = Field(None, gt=0, description="Gauge length L0 (mm).")
    material: str | None = Field(None, description="Material name (groups tests for fitting).")
    units: str = Field("MPa", description="Stress unit of the source data.")
    timestamp: str | None = Field(None, description="ISO-8601 acquisition timestamp.")
    already_true: bool = Field(
        False,
        description="True if the supplied strain/stress are already true (skip "
        "engineering→true conversion).",
    )


class AnalysisParams(BaseModel):
    """Parameters that govern data reduction and fitting (hashed for caching)."""

    model_config = ConfigDict(extra="forbid")

    failure_criterion_pct: float = Field(
        30.0, gt=0, lt=100,
        description="Percent load-drop from the stabilized (half-life) peak load "
        "that defines failure / N_f (ADR-0004).",
    )
    mean_stress_model: MeanStressModel = Field(
        MeanStressModel.SWT, description="Mean-stress correction to apply (ADR-0006)."
    )
    refine_nonlinear: bool = Field(
        False,
        description="If true, refine strain-life constants with a nonlinear fit on the "
        "combined total-strain curve, seeded by the per-branch linear fit (ADR-0005).",
    )
    walker_gamma: float | None = Field(
        None, description="Walker exponent γ; if None and the Walker model is used, it "
        "is estimated or fit from data."
    )

    @model_validator(mode="after")
    def _check(self) -> "AnalysisParams":
        if not (0.0 < self.failure_criterion_pct < 100.0):
            raise ValueError("failure_criterion_pct must be in (0, 100)")
        return self
