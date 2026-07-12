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

This module also provides the FKM technological size factor K_d,m, which
reduces the tensile strength (and thus stress-based fatigue strength) for
components thicker than the reference test specimen:

    K_d,m = 1                                              for d_eff <= d_eff_N
    K_d,m = (1 - 0.7686 a_dm lg(d_eff / 7.5)) /
            (1 - 0.7686 a_dm lg(d_eff_N / 7.5))            for d_eff > d_eff_N

with lg the base-10 log and d in mm. The 7.5 mm reference is the FKM
standard specimen. This formula is a published relation, verified against
two independent open sources.

The per-material constants a_dm and d_eff_N are NOT embedded here. They are
tabulated only in the copyrighted FKM guideline, which the project rules
forbid copying (the same rule that excludes NIMS, MMPDS, and Boller-Seeger
data tables). The caller supplies them from their own licensed copy of the
guideline. This is deliberate, not an oversight.
"""

from __future__ import annotations

import math

__all__ = [
    "MATERIAL_GROUPS",
    "fkm_roughness_factor",
    "fkm_size_factor",
]

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


#: FKM standard test-specimen diameter in mm.
_D_REF = 7.5


def fkm_size_factor(d_eff: float, *, a_dm: float, d_eff_N: float) -> dict:
    """FKM technological size factor ``K_d,m`` for tensile strength.

    Give the effective diameter ``d_eff`` in mm and the two material
    constants ``a_dm`` and ``d_eff_N`` (mm) from your licensed copy of the
    FKM guideline (tables 3.2.1 and 3.2.2). Those tables are copyrighted and
    are not bundled here, see the module docstring. Returns ``K_d,m``, which
    is 1.0 at or below the reference diameter and decreases above it.

    Multiply a stress-based fatigue strength or tensile strength by
    ``K_d,m``. The formula is a verified published relation, the constants
    are yours.
    """
    if not d_eff > 0:
        raise ValueError(f"d_eff must be positive mm, got {d_eff}")
    if not d_eff_N > 0:
        raise ValueError(f"d_eff_N must be positive mm, got {d_eff_N}")
    if not a_dm >= 0:
        raise ValueError(f"a_dm must be non-negative, got {a_dm}")

    notes: list[str] = [
        "K_d,m multiplies a stress-based fatigue or tensile strength.",
        "a_dm and d_eff_N are caller-supplied from the FKM guideline "
        "tables, which are copyrighted and not bundled.",
    ]
    if d_eff <= d_eff_N:
        k = 1.0
        notes.append(
            f"d_eff {d_eff:g} mm is at or below the reference {d_eff_N:g} mm, "
            "no size reduction."
        )
    else:
        num = 1.0 - 0.7686 * a_dm * math.log10(d_eff / _D_REF)
        den = 1.0 - 0.7686 * a_dm * math.log10(d_eff_N / _D_REF)
        k = num / den
    return {
        "K_dm": float(k),
        "d_eff": float(d_eff),
        "a_dm": float(a_dm),
        "d_eff_N": float(d_eff_N),
        "notes": notes,
    }
