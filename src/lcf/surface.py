"""Surface roughness correction, FKM style (P3 remainder, ADR 0013).

The FKM guideline reduces the polished-specimen fatigue strength for surface
roughness with

    K_R = 1 - a_R * log10(Rz) * log10(2 Rm / Rm_N_min)

where ``Rz`` is the surface roughness in micrometres (DIN 4768), ``Rm`` the
tensile strength in MPa, and ``a_R`` and ``Rm_N_min`` material-group
constants. A polished surface (Rz at or below 1) gives K_R = 1, rougher
surfaces give K_R below 1. Multiply a stress-based fatigue strength (an
endurance limit or a stress-life curve's strength values) by K_R.

Constants per material group, as tabulated in open engineering references
(quadco.engineering, accessed 2026-07-11), original source the FKM
guideline, Rechnerischer Festigkeitsnachweis fuer Maschinenbauteile. The
worked example from the same source, steel with Rm 600 MPa and Rz 100, gives
K_R = 0.79 and is a golden test.

The FKM technological size factor is NOT implemented, its constant tables
were not available from a verifiable open source.
"""

from __future__ import annotations

import math

__all__ = ["MATERIAL_GROUPS", "fkm_roughness_factor"]

#: (a_R, Rm_N_min in MPa) per FKM material group
MATERIAL_GROUPS: dict[str, tuple[float, float]] = {
    "steel": (0.22, 400.0),
    "cast_steel": (0.20, 400.0),
    "nodular_cast_iron": (0.16, 400.0),
    "malleable_cast_iron": (0.12, 350.0),
    "grey_cast_iron": (0.06, 100.0),
    "wrought_aluminium": (0.22, 133.0),
    "cast_aluminium": (0.20, 133.0),
}


def fkm_roughness_factor(
    Rz: float, Rm: float, *, material_group: str = "steel"
) -> dict:
    """FKM roughness factor ``K_R`` for a surface roughness and strength.

    ``Rz`` in micrometres, ``Rm`` in MPa. Returns the factor, the constants
    used, and plain-language notes. ``K_R`` is capped at 1.0, a polished
    surface cannot raise the fatigue strength above the polished-specimen
    value this factor is referenced to.
    """
    group = str(material_group).strip().lower()
    if group not in MATERIAL_GROUPS:
        raise ValueError(
            f"unknown material_group {material_group!r}. "
            f"Supported: {sorted(MATERIAL_GROUPS)}."
        )
    if not Rz > 0:
        raise ValueError(f"Rz must be positive micrometres, got {Rz}")
    if not Rm > 0:
        raise ValueError(f"Rm must be positive MPa, got {Rm}")
    a_r, rm_min = MATERIAL_GROUPS[group]
    notes: list[str] = []
    k_r = 1.0 - a_r * math.log10(Rz) * math.log10(2.0 * Rm / rm_min)
    if k_r > 1.0:
        k_r = 1.0
        notes.append(
            "K_R capped at 1.0, the factor is referenced to the polished "
            "specimen and cannot exceed it."
        )
    if 2.0 * Rm <= rm_min:
        notes.append(
            f"2*Rm is at or below the group minimum {rm_min:g} MPa, the "
            "formula is outside its intended range, treat with care."
        )
    notes.append(
        "multiply a stress-based fatigue strength by K_R. Strain-life "
        "constants are not corrected directly by this factor."
    )
    return {
        "K_R": float(k_r),
        "Rz": float(Rz),
        "Rm": float(Rm),
        "material_group": group,
        "a_R": a_r,
        "Rm_N_min": rm_min,
        "notes": notes,
    }
