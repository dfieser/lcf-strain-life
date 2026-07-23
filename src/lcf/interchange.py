"""Versioned interchange of strain-life data (ADR-0017 P4, extended by ADR 0021).

Three document formats, each a small, versioned, human-diffable JSON object.
The formal JSON Schema artifacts live in ``docs/schemas/`` and are generated
from the pydantic models here, a test guards against drift. The full
field-by-field specification is ``docs/INTERCHANGE.md``.

- ``lcf-strain-life/material@1``: the four strain-life constants, the cyclic
  curve, the unit conventions, and a provenance block. Frozen since v0.1.
- ``lcf-strain-life/test-record@1``: one strain-controlled fatigue test with
  ASTM E606-style metadata, the failure outcome, the half-life response,
  an optional per-cycle table, and a provenance block with the license basis.
- ``lcf-strain-life/collection@1``: a dataset manifest that bundles material
  documents and test records with a compilation license and contributors.

Versioning policy: the version is an integer. Readers refuse unknown schemas,
versions, and unit systems rather than guessing. Within a version, new
optional fields may be added and readers accept unknown fields. Any breaking
change bumps the version.

The pyLife adapter expresses the elastic (Basquin) line in pyLife's
WoehlerCurve conventions (``k_1``, ``ND``, ``SD``, ``TN``, ``TS``). It is
shape-compatible with pyLife's documented pandas conventions and the math
round-trips exactly, but it is not integration-tested against an installed
pyLife. A strain-life curve has no endurance limit, so the knee ``ND`` is a
representation choice recorded in the output.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from . import fits

__all__ = [
    "SCHEMA",
    "RECORD_SCHEMA",
    "COLLECTION_SCHEMA",
    "export_material",
    "import_material",
    "export_test_record",
    "import_test_record",
    "export_collection",
    "import_collection",
    "validate_document",
    "json_schema",
    "to_pylife_woehler",
    "from_pylife_woehler",
    "to_py_fatigue_sn",
]

SCHEMA = "lcf-strain-life/material"
VERSION = 1

_UNITS = {"stress": "MPa", "strain": "fraction", "life": "reversals"}


def export_material(
    *,
    name: str,
    E: float,
    sigma_f: float,
    b: float,
    eps_f: float,
    c: float,
    K_prime: float | None = None,
    n_prime: float | None = None,
    source: str | None = None,
    notes: str | None = None,
) -> dict:
    """Build the versioned material document from strain-life constants."""
    for label, value in (("E", E), ("sigma_f", sigma_f), ("eps_f", eps_f)):
        if not value > 0:
            raise ValueError(f"{label} must be positive, got {value}")
    for label, value in (("b", b), ("c", c)):
        if not value < 0:
            raise ValueError(
                f"{label} must be negative (project convention), got {value}"
            )
    doc = {
        "schema": SCHEMA,
        "version": VERSION,
        "name": name,
        "units": dict(_UNITS),
        "E": float(E),
        "basquin": {"sigma_f": float(sigma_f), "b": float(b)},
        "coffin_manson": {"eps_f": float(eps_f), "c": float(c)},
        "transition_reversals": float(
            fits.transition_reversals(sigma_f, b, eps_f, c, E)
        ),
    }
    if K_prime is not None and n_prime is not None:
        doc["ramberg_osgood"] = {
            "K_prime": float(K_prime), "n_prime": float(n_prime)
        }
    provenance: dict = {}
    if source:
        provenance["source"] = source
    if notes:
        provenance["notes"] = notes
    if provenance:
        doc["provenance"] = provenance
    return doc


def import_material(doc: dict) -> dict:
    """Validate a material document and return the flat constants.

    Returns a dict with ``name``, ``E``, ``sigma_f``, ``b``, ``eps_f``,
    ``c``, and, when present, ``K_prime`` and ``n_prime``. Refuses unknown
    schemas, versions, and unit systems rather than guessing.
    """
    if not isinstance(doc, dict):
        raise ValueError("material document must be a JSON object")
    if doc.get("schema") != SCHEMA:
        raise ValueError(
            f"unknown schema {doc.get('schema')!r}, expected {SCHEMA!r}"
        )
    if doc.get("version") != VERSION:
        raise ValueError(
            f"unsupported version {doc.get('version')!r}, this build reads "
            f"version {VERSION}"
        )
    units = doc.get("units", {})
    if units != _UNITS:
        raise ValueError(
            f"unit system {units!r} is not the internal convention {_UNITS!r}. "
            "Convert the document before importing."
        )
    try:
        out = {
            "name": doc.get("name"),
            "E": float(doc["E"]),
            "sigma_f": float(doc["basquin"]["sigma_f"]),
            "b": float(doc["basquin"]["b"]),
            "eps_f": float(doc["coffin_manson"]["eps_f"]),
            "c": float(doc["coffin_manson"]["c"]),
        }
    except (KeyError, TypeError) as exc:
        raise ValueError(f"material document is missing a required field: {exc}")
    ro = doc.get("ramberg_osgood")
    if ro:
        out["K_prime"] = float(ro["K_prime"])
        out["n_prime"] = float(ro["n_prime"])
    return out


def to_pylife_woehler(
    sigma_f: float, b: float, *, nd_cycles: float = 1.0e6
) -> dict:
    """Express the Basquin line in pyLife WoehlerCurve conventions.

    ``k_1 = -1/b`` and ``SD`` is the Basquin stress amplitude at the knee
    ``ND`` (in cycles). ``TN`` and ``TS`` are 1.0, meaning no scatter is
    encoded. The knee is a representation choice, strain-life implies no
    endurance limit.
    """
    if not b < 0:
        raise ValueError(f"b must be negative, got {b}")
    if not nd_cycles > 0:
        raise ValueError("nd_cycles must be positive")
    sd = sigma_f * (2.0 * nd_cycles) ** b
    return {
        "k_1": -1.0 / b,
        "ND": float(nd_cycles),
        "SD": float(sd),
        "TN": 1.0,
        "TS": 1.0,
        "note": (
            "Basquin line in pyLife WoehlerCurve form, knee ND is a "
            "representation choice, no endurance limit implied. "
            "Shape-compatible, not integration-tested against pyLife."
        ),
    }


def to_py_fatigue_sn(sigma_f: float, b: float) -> dict:
    """Express the Basquin line in py-fatigue SNCurve conventions.

    py-fatigue defines ``log10(N) = intercept - slope * log10(S)``. From
    Basquin in reversals, ``slope = -1/b`` and
    ``intercept = log10(0.5) + slope * log10(sigma_f)`` (the 0.5 converts
    reversals to cycles). No endurance limit is encoded.
    """
    import math

    if not b < 0:
        raise ValueError(f"b must be negative, got {b}")
    slope = -1.0 / b
    intercept = math.log10(0.5) + slope * math.log10(sigma_f)
    return {
        "slope": slope,
        "intercept": intercept,
        "note": (
            "Basquin line in py-fatigue SNCurve form "
            "(log10 N = intercept - slope*log10 S), no endurance limit "
            "encoded."
        ),
    }


def from_pylife_woehler(k_1: float, ND: float, SD: float) -> dict:
    """Recover Basquin constants from pyLife WoehlerCurve values."""
    if not k_1 > 0:
        raise ValueError(f"k_1 must be positive, got {k_1}")
    b = -1.0 / k_1
    sigma_f = SD * (2.0 * ND) ** (-b)
    return {"sigma_f": float(sigma_f), "b": float(b)}


# ---------------------------------------------------------------------------
# Pydantic document models. These define the formats formally. The JSON
# Schema artifacts in docs/schemas/ are generated from them, see
# :func:`json_schema`. The material@1 writer above predates the models and
# stays as the frozen API, the model validates the same documents.
# ---------------------------------------------------------------------------

RECORD_SCHEMA = "lcf-strain-life/test-record"
COLLECTION_SCHEMA = "lcf-strain-life/collection"

_RECORD_UNITS = {
    "stress": "MPa", "strain": "fraction", "life": "reversals",
    "temperature": "C",
}

#: Accepted provenance origins for a test record.
Origin = Literal["own-data", "republished-factual", "digitized", "permissioned"]


class _Block(BaseModel):
    """Base for nested blocks. Unknown fields are accepted and preserved,
    the additive rule of the versioning policy."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class MaterialUnits(BaseModel):
    """The fixed unit convention of material@1."""

    model_config = ConfigDict(extra="forbid")

    stress: Literal["MPa"]
    strain: Literal["fraction"]
    life: Literal["reversals"]


class RecordUnits(BaseModel):
    """The fixed unit convention of test-record@1."""

    model_config = ConfigDict(extra="forbid")

    stress: Literal["MPa"] = "MPa"
    strain: Literal["fraction"] = "fraction"
    life: Literal["reversals"] = "reversals"
    temperature: Literal["C"] = "C"


class MaterialBasquin(_Block):
    sigma_f: float = Field(gt=0, description="Fatigue strength coefficient, MPa.")
    b: float = Field(lt=0, description="Fatigue strength exponent, negative.")


class MaterialCoffinManson(_Block):
    eps_f: float = Field(gt=0, description="Fatigue ductility coefficient.")
    c: float = Field(lt=0, description="Fatigue ductility exponent, negative.")


class MaterialRambergOsgood(_Block):
    K_prime: float = Field(gt=0, description="Cyclic strength coefficient, MPa.")
    n_prime: float = Field(gt=0, description="Cyclic strain hardening exponent.")


class MaterialProvenance(_Block):
    source: str | None = Field(
        default=None, description="Citation for the constants."
    )
    notes: str | None = None


class MaterialDoc(_Block):
    """``lcf-strain-life/material@1``, the constants document."""

    schema_: Literal["lcf-strain-life/material"] = Field(alias="schema")
    version: Literal[1]
    name: str = Field(min_length=1)
    units: MaterialUnits
    E: float = Field(gt=0, description="Elastic modulus, MPa.")
    basquin: MaterialBasquin
    coffin_manson: MaterialCoffinManson
    transition_reversals: float | None = Field(default=None, gt=0)
    ramberg_osgood: MaterialRambergOsgood | None = None
    provenance: MaterialProvenance | None = None


class TestControl(_Block):
    """How the test was driven."""

    control_mode: Literal["strain", "stress"] = "strain"
    strain_amplitude: float | None = Field(
        default=None, gt=0, description="Controlled true strain amplitude."
    )
    stress_amplitude: float | None = Field(
        default=None, gt=0, description="Controlled true stress amplitude, MPa."
    )
    strain_ratio: float | None = Field(
        default=None, description="R ratio of the controlled strain."
    )
    stress_ratio: float | None = None
    frequency_hz: float | None = Field(default=None, gt=0)
    strain_rate: float | None = Field(
        default=None, gt=0, description="Strain rate, per second."
    )
    temperature_C: float | None = None
    environment: str | None = Field(
        default=None, description="For example lab air, vacuum, 3.5% NaCl."
    )
    waveform: str | None = Field(
        default=None, description="For example triangular, sinusoidal."
    )

    @model_validator(mode="after")
    def _mode_needs_amplitude(self) -> "TestControl":
        if self.control_mode == "strain" and self.strain_amplitude is None:
            raise ValueError("strain control requires strain_amplitude")
        if self.control_mode == "stress" and self.stress_amplitude is None:
            raise ValueError("stress control requires stress_amplitude")
        return self


class Specimen(_Block):
    """ASTM E606-style specimen description, all optional."""

    geometry: str | None = Field(
        default=None, description="For example uniform gauge, hourglass."
    )
    gauge_diameter_mm: float | None = Field(default=None, gt=0)
    gauge_length_mm: float | None = Field(default=None, gt=0)
    surface_finish: str | None = None
    orientation: str | None = Field(
        default=None, description="Sampling orientation, for example L, LT."
    )


class HalfLifeResponse(_Block):
    """Reduced stabilized response, by convention at half life."""

    stress_amplitude: float | None = Field(default=None, gt=0)
    mean_stress: float | None = None
    elastic_strain_amplitude: float | None = Field(default=None, gt=0)
    plastic_strain_amplitude: float | None = Field(default=None, ge=0)
    at_life_fraction: float | None = Field(
        default=None, gt=0, le=1,
        description="Life fraction the values were read at, 0.5 is half life.",
    )


class PerCycleTable(_Block):
    """Optional per-cycle evolution table, the raw-data differentiator."""

    columns: list[str] = Field(min_length=1)
    rows: list[list[float]]
    units: dict[str, str] | None = Field(
        default=None, description="Unit per column when not the fixed set."
    )

    @model_validator(mode="after")
    def _rectangular(self) -> "PerCycleTable":
        if len(set(self.columns)) != len(self.columns):
            raise ValueError("per_cycle columns must be unique")
        width = len(self.columns)
        for i, row in enumerate(self.rows):
            if len(row) != width:
                raise ValueError(
                    f"per_cycle row {i} has {len(row)} values, "
                    f"expected {width}"
                )
        return self


class Failure(_Block):
    """The test outcome."""

    reversals_to_failure: float = Field(
        gt=0, description="2Nf, or the suspension point when runout is true."
    )
    runout: bool = Field(
        default=False,
        description="True when the test was suspended without failure.",
    )
    criterion: str | None = Field(
        default=None, description="For example 30% load drop, separation."
    )


class RecordProvenance(_Block):
    """Where the record came from and on what basis it is shared."""

    source: str = Field(
        min_length=1, description="Citation or origin of the data. Required."
    )
    license: str | None = Field(
        default=None,
        description="SPDX id when the contributor licenses own data.",
    )
    origin: Origin | None = Field(
        default=None,
        description="own-data, republished-factual, digitized, permissioned.",
    )
    notes: str | None = None


class TestRecordDoc(_Block):
    """``lcf-strain-life/test-record@1``, one strain-controlled fatigue test."""

    schema_: Literal["lcf-strain-life/test-record"] = Field(alias="schema")
    version: Literal[1]
    record_id: str = Field(min_length=1)
    material: str = Field(min_length=1)
    condition: str | None = Field(
        default=None, description="Heat treatment or material condition."
    )
    units: RecordUnits
    test: TestControl
    specimen: Specimen | None = None
    response: HalfLifeResponse | None = None
    failure: Failure
    per_cycle: PerCycleTable | None = None
    provenance: RecordProvenance


class Contributor(_Block):
    name: str = Field(min_length=1)
    orcid: str | None = None


class CollectionDoc(_Block):
    """``lcf-strain-life/collection@1``, a dataset manifest."""

    schema_: Literal["lcf-strain-life/collection"] = Field(alias="schema")
    version: Literal[1]
    name: str = Field(min_length=1)
    description: str | None = None
    license: str = Field(
        min_length=1,
        description="SPDX id of the compilation, per-record basis may differ.",
    )
    created: str | None = Field(
        default=None, pattern=r"^\d{4}-\d{2}-\d{2}$",
        description="ISO date the collection was assembled.",
    )
    doi: str | None = None
    homepage: str | None = None
    contributors: list[Contributor] | None = None
    materials: list[MaterialDoc] = Field(default_factory=list)
    records: list[TestRecordDoc] = Field(default_factory=list)

    @model_validator(mode="after")
    def _non_empty_and_unique(self) -> "CollectionDoc":
        if not self.materials and not self.records:
            raise ValueError(
                "a collection needs at least one material or test record"
            )
        seen: set[str] = set()
        for rec in self.records:
            if rec.record_id in seen:
                raise ValueError(f"duplicate record_id {rec.record_id!r}")
            seen.add(rec.record_id)
        return self


_MODELS: dict[str, type[_Block]] = {
    SCHEMA: MaterialDoc,
    RECORD_SCHEMA: TestRecordDoc,
    COLLECTION_SCHEMA: CollectionDoc,
}

_KINDS = {
    SCHEMA: "material",
    RECORD_SCHEMA: "test-record",
    COLLECTION_SCHEMA: "collection",
}


def export_test_record(
    *,
    record_id: str,
    material: str,
    reversals_to_failure: float,
    source: str,
    strain_amplitude: float | None = None,
    stress_amplitude: float | None = None,
    control_mode: str = "strain",
    runout: bool = False,
    criterion: str | None = None,
    condition: str | None = None,
    license: str | None = None,
    origin: str | None = None,
    notes: str | None = None,
    test: dict | None = None,
    specimen: dict | None = None,
    response: dict | None = None,
    per_cycle: dict | None = None,
) -> dict:
    """Build a validated ``test-record@1`` document.

    The common fields are keyword arguments. Less common control fields go in
    ``test``, which is merged over the keyword values. ``specimen``,
    ``response``, and ``per_cycle`` are optional blocks passed as dicts.
    ``source`` is required, a record without provenance is not accepted.
    """
    control: dict = {
        "control_mode": control_mode,
        "strain_amplitude": strain_amplitude,
        "stress_amplitude": stress_amplitude,
    }
    control.update(test or {})
    doc: dict = {
        "schema": RECORD_SCHEMA,
        "version": 1,
        "record_id": record_id,
        "material": material,
        "condition": condition,
        "units": dict(_RECORD_UNITS),
        "test": {k: v for k, v in control.items() if v is not None},
        "specimen": specimen,
        "response": response,
        "failure": {
            "reversals_to_failure": reversals_to_failure,
            "runout": runout,
            "criterion": criterion,
        },
        "per_cycle": per_cycle,
        "provenance": {
            "source": source, "license": license,
            "origin": origin, "notes": notes,
        },
    }
    model = TestRecordDoc.model_validate(doc)
    return model.model_dump(by_alias=True, exclude_none=True)


def import_test_record(doc: dict) -> TestRecordDoc:
    """Validate a test-record document, return the typed model.

    Raises ``ValueError`` on any mismatch, never guesses. Use
    ``.model_dump(by_alias=True)`` to get a plain dict back.
    """
    _check_header(doc, RECORD_SCHEMA)
    return TestRecordDoc.model_validate(doc)


def export_collection(
    *,
    name: str,
    license: str,
    description: str | None = None,
    created: str | None = None,
    doi: str | None = None,
    homepage: str | None = None,
    contributors: list[dict] | None = None,
    materials: list[dict] | None = None,
    records: list[dict] | None = None,
) -> dict:
    """Build a validated ``collection@1`` document from member documents.

    Every member document is validated. ``created`` is an ISO date string
    supplied by the caller, nothing is auto-stamped, exports stay
    reproducible.
    """
    doc: dict = {
        "schema": COLLECTION_SCHEMA,
        "version": 1,
        "name": name,
        "description": description,
        "license": license,
        "created": created,
        "doi": doi,
        "homepage": homepage,
        "contributors": contributors,
        "materials": materials or [],
        "records": records or [],
    }
    model = CollectionDoc.model_validate(doc)
    return model.model_dump(by_alias=True, exclude_none=True)


def import_collection(doc: dict) -> CollectionDoc:
    """Validate a collection document, return the typed model."""
    _check_header(doc, COLLECTION_SCHEMA)
    return CollectionDoc.model_validate(doc)


def _check_header(doc: dict, expected_schema: str) -> None:
    if not isinstance(doc, dict):
        raise ValueError("document must be a JSON object")
    if doc.get("schema") != expected_schema:
        raise ValueError(
            f"unknown schema {doc.get('schema')!r}, expected "
            f"{expected_schema!r}"
        )
    if doc.get("version") != VERSION:
        raise ValueError(
            f"unsupported version {doc.get('version')!r}, this build reads "
            f"version {VERSION}"
        )


def validate_document(doc: object) -> dict:
    """Validate any interchange document, returning a structured verdict.

    Dispatches on the ``schema`` key across all three formats. Returns a dict
    with ``valid``, ``schema``, ``version``, ``kind``, and a list of
    human-readable ``errors``. Never raises on invalid content and never
    repairs a document.
    """
    if not isinstance(doc, dict):
        return {
            "valid": False, "schema": None, "version": None, "kind": None,
            "errors": ["document must be a JSON object"],
        }
    schema = doc.get("schema")
    version = doc.get("version")
    errors: list[str] = []
    out: dict[str, Any] = {
        "valid": False,
        "schema": schema,
        "version": version,
        "kind": _KINDS.get(schema) if isinstance(schema, str) else None,
        "errors": errors,
    }
    if schema not in _MODELS:
        errors.append(
            f"unknown schema {schema!r}, known schemas: "
            + ", ".join(sorted(_MODELS))
        )
        return out
    if version != VERSION:
        errors.append(
            f"unsupported version {version!r}, this build reads version "
            f"{VERSION}"
        )
        return out
    try:
        _MODELS[schema].model_validate(doc)
    except ValueError as exc:
        errors.extend(_validation_messages(exc))
        return out
    out["valid"] = True
    return out


def _validation_messages(exc: ValueError) -> list[str]:
    """Flatten a pydantic ValidationError into readable dotted-path lines."""
    errors = getattr(exc, "errors", None)
    if errors is None:
        return [str(exc)]
    out: list[str] = []
    for err in errors():
        loc = ".".join(str(part) for part in err.get("loc", ()))
        msg = err.get("msg", "invalid")
        out.append(f"{loc}: {msg}" if loc else msg)
    return out


def json_schema(kind: str) -> dict:
    """Generate the JSON Schema for ``material``, ``test-record``, or
    ``collection``.

    The checked-in artifacts in ``docs/schemas/`` are exactly these outputs,
    a test regenerates and compares them so they cannot drift.
    """
    by_kind = {v: k for k, v in _KINDS.items()}
    if kind not in by_kind:
        raise ValueError(
            f"unknown kind {kind!r}, use one of {sorted(by_kind)}"
        )
    model = _MODELS[by_kind[kind]]
    schema = model.model_json_schema(by_alias=True)
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = (
        "https://dfieser.github.io/lcf-strain-life/docs/schemas/"
        f"{kind}.v1.schema.json"
    )
    schema["title"] = f"{by_kind[kind]}@{VERSION}"
    return schema
