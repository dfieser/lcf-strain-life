"""Validated data models: test metadata, analysis parameters, and enums.

Pydantic models are used for everything that crosses the MCP boundary (so inputs
are validated and outputs serialize to JSON schema). Numerical result containers
that wrap arrays/DataFrames live with their producing modules and use dataclasses.
"""

from __future__ import annotations

from enum import Enum
from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class MeanStressModel(str, Enum):
    """Mean-stress correction selector (ADR-0006)."""

    NONE = "none"
    MORROW = "morrow"
    MODIFIED_MORROW = "modified_morrow"
    SWT = "swt"
    WALKER = "walker"


class SpecimenMetadata(BaseModel):
    """Specimen and test-condition metadata per the ASTM E606/E606M-21
    reporting requirements (ADR-0014).

    Every field is optional. Dimensions are in mm, the strain rate is per
    second. This records what the lab reports about the specimen and the
    test setup, it does not affect the numerical analysis.
    """

    model_config = ConfigDict(extra="forbid")

    specimen_id: str | None = Field(None, description="Specimen identifier as machined.")
    geometry: str | None = Field(
        None, description="Specimen geometry, for example round or flat."
    )
    diameter_mm: float | None = Field(None, gt=0, description="Gauge diameter for round specimens (mm).")
    width_mm: float | None = Field(None, gt=0, description="Gauge width for flat specimens (mm).")
    thickness_mm: float | None = Field(None, gt=0, description="Gauge thickness for flat specimens (mm).")
    surface_finish: str | None = Field(None, description="Surface preparation, for example longitudinal polish.")
    control_mode: Literal["strain", "stress"] | None = Field(
        None, description="Test control mode. Strain control is the E606 norm."
    )
    waveform: str | None = Field(None, description="Command waveform, for example triangle or sine.")
    strain_rate: float | None = Field(None, gt=0, description="Strain rate (1/s).")
    environment: str | None = Field(None, description="Test environment, for example lab air.")
    machine: str | None = Field(None, description="Test frame or controller identification.")
    extensometer: str | None = Field(None, description="Extensometer model and gauge length class.")
    lab: str | None = Field(None, description="Laboratory that ran the test.")
    operator: str | None = Field(None, description="Operator identification.")
    test_date: str | None = Field(None, description="Test date, ISO-8601.")
    standard: str | None = Field(
        None, description="Governing test standard, for example ASTM E606/E606M-21."
    )
    notes: str | None = Field(None, description="Free-form remarks.")


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
    # Optional Phase 2 fields. All default to None so the Phase 1 uniaxial path
    # is unchanged when they are omitted.
    temperature: float | None = Field(None, description="Test temperature in degC.")
    Kt: float | None = Field(None, gt=0, description="Elastic stress concentration factor.")
    Kf: float | None = Field(None, gt=0, description="Fatigue notch factor.")
    frequency: float | None = Field(None, gt=0, description="Cyclic frequency, cycles per unit time.")
    hold_time: float | None = Field(None, ge=0, description="Hold time per cycle for creep-fatigue.")
    specimen: SpecimenMetadata | None = Field(
        None, description="ASTM E606 specimen and test-condition reporting metadata."
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
        None, description="Walker exponent gamma. If None and the Walker model is used, it "
        "is estimated or fit from data."
    )
    min_plastic_strain: float | None = Field(
        None, ge=0,
        description="Minimum plastic strain amplitude for a test to enter the plastic "
        "(Coffin-Manson) and cyclic (Ramberg-Osgood) fits, excluding near-runout points "
        "whose plastic strain is at measurement-noise level (ADR-0005).",
    )
    min_strain_range: float | None = Field(
        None, ge=0,
        description="Amplitude gate for turning-point detection: reversals with a strain "
        "swing below this are treated as noise and removed. If None, a mild default of 2% "
        "of the total strain range is used (ADR-0003).",
    )

    @model_validator(mode="after")
    def _check(self) -> "AnalysisParams":
        if not (0.0 < self.failure_criterion_pct < 100.0):
            raise ValueError("failure_criterion_pct must be in (0, 100)")
        return self
