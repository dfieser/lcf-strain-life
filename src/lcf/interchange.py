"""Versioned interchange of strain-life material data (ADR-0017, P4).

The document format is ``lcf-strain-life/material@1``: a small, versioned,
human-diffable JSON object carrying the four strain-life constants, the
cyclic curve, the unit conventions, and a provenance block. There is no de
facto standard for exchanging strain-life constants between tools, this
schema is documented so others can adopt or adapt it.

The pyLife adapter expresses the elastic (Basquin) line in pyLife's
WoehlerCurve conventions (``k_1``, ``ND``, ``SD``, ``TN``, ``TS``). It is
shape-compatible with pyLife's documented pandas conventions and the math
round-trips exactly, but it is not integration-tested against an installed
pyLife. A strain-life curve has no endurance limit, so the knee ``ND`` is a
representation choice recorded in the output.
"""

from __future__ import annotations

from . import fits

__all__ = [
    "SCHEMA",
    "export_material",
    "import_material",
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
