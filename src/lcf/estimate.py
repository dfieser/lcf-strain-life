"""Strain-life constant estimation from monotonic properties.

When no strain-controlled test data exists, these methods estimate the four
strain-life constants (sigma_f', b, eps_f', c) from tensile properties or
hardness. Every method is published and citable, and every result carries its
citation, its validity warnings, and nothing that the source did not publish.

Methods and sources:

- Medians method: Meggiolaro and Castro, Int. J. Fatigue 26 (2004) 463-476.
  Median constants from an 845-metal database (724 steels, 81 aluminum,
  15 titanium alloys). Their evaluation found it the best average predictor,
  so it is the recommended default.
- Uniform Material Law: Baeumel and Seeger, Materials Data for Cyclic
  Loading, Supplement 1, Elsevier, 1990.
- Universal slopes: Manson, Experimental Mechanics 5 (1965) 193-226.
- Modified universal slopes: Muralidharan and Manson, J. Eng. Mater.
  Technol. 110 (1988) 55-58. Steels only.
- Hardness method: Roessle and Fatemi, Int. J. Fatigue 22 (2000) 495-511.
  Steels only, from Brinell hardness and modulus.

Units follow the package convention: stress and modulus in MPa, strains as
fractions. The exponents b and c are negative. Estimates are starting points
for screening, not substitutes for test data, and the accuracy caveats
reported by the sources are repeated in the per-method warnings.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

__all__ = [
    "EstimatedConstants",
    "estimate_medians",
    "estimate_uniform_material_law",
    "estimate_universal_slopes",
    "estimate_modified_universal_slopes",
    "estimate_hardness_method",
    "estimate_strain_life_constants",
    "ESTIMATION_METHODS",
]

_CITATIONS = {
    "medians": (
        "Meggiolaro and Castro, Int. J. Fatigue 26 (2004) 463-476"
    ),
    "uniform_material_law": (
        "Baeumel and Seeger, Materials Data for Cyclic Loading, "
        "Supplement 1, Elsevier, 1990"
    ),
    "universal_slopes": (
        "Manson, Experimental Mechanics 5 (1965) 193-226"
    ),
    "modified_universal_slopes": (
        "Muralidharan and Manson, J. Eng. Mater. Technol. 110 (1988) 55-58"
    ),
    "hardness": (
        "Roessle and Fatemi, Int. J. Fatigue 22 (2000) 495-511"
    ),
}

ESTIMATION_METHODS = tuple(_CITATIONS)


@dataclass
class EstimatedConstants:
    """Estimated strain-life constants with provenance.

    ``K`` and ``n`` (cyclic strength coefficient and exponent) are filled only
    when the source method publishes them. ``warnings`` repeats the validity
    caveats of the source that apply to the given inputs.
    """

    method: str
    material_class: str
    sigma_f: float
    b: float
    eps_f: float
    c: float
    citation: str
    K: float | None = None
    n: float | None = None
    warnings: list[str] = field(default_factory=list)


def _require_positive(**values: float) -> None:
    for name, v in values.items():
        if v is None or not math.isfinite(v) or v <= 0:
            raise ValueError(f"{name} must be a positive finite number")


def _require_ra(RA: float) -> None:
    if RA is None or not (0.0 < RA < 1.0):
        raise ValueError("RA must be a fraction between 0 and 1, exclusive")


def estimate_medians(material_class: str, Su: float) -> EstimatedConstants:
    """Meggiolaro-Castro medians method (2004), the recommended default.

    ``material_class`` is steel or aluminum. The paper also reports medians
    for titanium, cast iron, and nickel alloys from small samples, exposed
    here with an explicit small-sample warning.
    """
    _require_positive(Su=Su)
    table = {
        # class: (sigma_f/Su, eps_f, b, c, n_prime, small_sample)
        "steel": (1.5, 0.45, -0.09, -0.59, 0.15, False),
        "aluminum": (1.9, 0.28, -0.11, -0.66, 0.09, False),
        "titanium": (1.9, 0.50, -0.10, -0.69, None, True),
        "cast_iron": (1.2, 0.04, -0.08, -0.52, None, True),
        "nickel": (1.4, 0.15, -0.08, -0.59, None, True),
    }
    if material_class not in table:
        raise ValueError(
            "material_class must be one of " + ", ".join(sorted(table))
        )
    ratio, eps_f, b, c, n_prime, small = table[material_class]
    warns = []
    if small:
        warns.append(
            f"the {material_class} medians come from a small sample in the "
            "source and should be used with caution"
        )
    return EstimatedConstants(
        method="medians",
        material_class=material_class,
        sigma_f=ratio * Su,
        b=b,
        eps_f=eps_f,
        c=c,
        n=n_prime,
        citation=_CITATIONS["medians"],
        warnings=warns,
    )


def estimate_uniform_material_law(
    material_class: str, Su: float, E: float
) -> EstimatedConstants:
    """Baeumel-Seeger Uniform Material Law (1990).

    ``material_class`` is steel (unalloyed and low-alloy) or aluminum_titanium.
    For steel the ductility correction is psi = 1 for Su/E <= 0.003, otherwise
    psi = 1.375 - 125 Su/E. The law loses validity as Su approaches 2.2 GPa,
    where psi reaches zero, and this function refuses non-positive psi.
    """
    _require_positive(Su=Su, E=E)
    warns: list[str] = []
    if material_class == "steel":
        ratio = Su / E
        psi = 1.0 if ratio <= 0.003 else 1.375 - 125.0 * ratio
        if psi <= 0.0:
            raise ValueError(
                "the Uniform Material Law is not valid here, the ductility "
                "correction psi is non-positive because Su/E is too high "
                "(the law fails as Su approaches 2.2 GPa for steel)"
            )
        if psi < 0.5:
            warns.append(
                "Su/E is high and the ductility correction psi is below 0.5, "
                "the estimate degrades as Su approaches 2.2 GPa"
            )
        return EstimatedConstants(
            method="uniform_material_law",
            material_class="steel",
            sigma_f=1.50 * Su,
            b=-0.087,
            eps_f=0.59 * psi,
            c=-0.58,
            K=1.65 * Su,
            n=0.15,
            citation=_CITATIONS["uniform_material_law"],
            warnings=warns,
        )
    if material_class == "aluminum_titanium":
        return EstimatedConstants(
            method="uniform_material_law",
            material_class="aluminum_titanium",
            sigma_f=1.67 * Su,
            b=-0.095,
            eps_f=0.35,
            c=-0.69,
            citation=_CITATIONS["uniform_material_law"],
            warnings=warns,
        )
    raise ValueError("material_class must be steel or aluminum_titanium")


def estimate_universal_slopes(Su: float, E: float, RA: float) -> EstimatedConstants:
    """Manson's original universal slopes method (1965), any metal.

    ``RA`` is the reduction in area as a fraction. Later evaluations found the
    method non-conservative at short lives and conservative at long lives for
    steels (Meggiolaro and Castro, 2004), so the newer methods are preferred.
    """
    _require_positive(Su=Su, E=E)
    _require_ra(RA)
    true_fracture_ductility = math.log(1.0 / (1.0 - RA))
    return EstimatedConstants(
        method="universal_slopes",
        material_class="any_metal",
        sigma_f=1.9 * Su,
        b=-0.12,
        eps_f=0.76 * true_fracture_ductility**0.6,
        c=-0.6,
        citation=_CITATIONS["universal_slopes"],
        warnings=[
            "later evaluations found this method non-conservative at short "
            "lives and conservative at long lives for steels, prefer the "
            "medians or uniform material law methods"
        ],
    )


def estimate_modified_universal_slopes(
    Su: float, E: float, RA: float
) -> EstimatedConstants:
    """Muralidharan-Manson modified universal slopes (1988), steels only.

    The source derived the correlation for steels. Applying it to aluminum or
    titanium is unsupported, their exponents differ significantly
    (Meggiolaro and Castro, 2004), so this function is steel-specific.
    """
    _require_positive(Su=Su, E=E)
    _require_ra(RA)
    ratio = Su / E
    true_fracture_ductility = math.log(1.0 / (1.0 - RA))
    return EstimatedConstants(
        method="modified_universal_slopes",
        material_class="steel",
        sigma_f=0.623 * E * ratio**0.832,
        b=-0.09,
        eps_f=0.0196 * ratio**-0.53 * true_fracture_ductility**0.155,
        c=-0.56,
        citation=_CITATIONS["modified_universal_slopes"],
    )


def estimate_hardness_method(HB: float, E: float) -> EstimatedConstants:
    """Roessle-Fatemi hardness method (2000), steels only.

    Needs only Brinell hardness and modulus. The source correlation covers
    steels with hardness roughly 150 to 700 HB, values outside that range get
    a warning. The source notes the sigma_f' offset overestimates strength at
    low hardness and that the ductility correlation is statistically weak.
    """
    _require_positive(HB=HB, E=E)
    warns: list[str] = []
    if not (150.0 <= HB <= 700.0):
        warns.append(
            "HB is outside the 150 to 700 range of the source correlation"
        )
    eps_f = (0.32 * HB**2 - 487.0 * HB + 191000.0) / E
    if eps_f <= 0:
        raise ValueError(
            "the hardness correlation gives a non-positive fatigue ductility "
            "coefficient for these inputs"
        )
    warns.append(
        "the source reports the ductility correlation is statistically weak, "
        "treat eps_f as a rough estimate"
    )
    return EstimatedConstants(
        method="hardness",
        material_class="steel",
        sigma_f=4.25 * HB + 225.0,
        b=-0.09,
        eps_f=eps_f,
        c=-0.56,
        citation=_CITATIONS["hardness"],
        warnings=warns,
    )


def estimate_strain_life_constants(
    method: str,
    *,
    material_class: str = "steel",
    Su: float | None = None,
    E: float | None = None,
    HB: float | None = None,
    RA: float | None = None,
) -> EstimatedConstants:
    """Dispatch to one estimation method by name.

    ``method`` is one of medians, uniform_material_law, universal_slopes,
    modified_universal_slopes, hardness. Each method needs a subset of the
    inputs: medians needs Su, uniform_material_law needs Su and E,
    universal_slopes and modified_universal_slopes need Su, E, and RA,
    hardness needs HB and E.
    """
    if method == "medians":
        if Su is None:
            raise ValueError("medians requires Su")
        return estimate_medians(material_class, Su)
    if method == "uniform_material_law":
        if Su is None or E is None:
            raise ValueError("uniform_material_law requires Su and E")
        return estimate_uniform_material_law(material_class, Su, E)
    if method == "universal_slopes":
        if Su is None or E is None or RA is None:
            raise ValueError("universal_slopes requires Su, E, and RA")
        return estimate_universal_slopes(Su, E, RA)
    if method == "modified_universal_slopes":
        if Su is None or E is None or RA is None:
            raise ValueError(
                "modified_universal_slopes requires Su, E, and RA"
            )
        return estimate_modified_universal_slopes(Su, E, RA)
    if method == "hardness":
        if HB is None or E is None:
            raise ValueError("hardness requires HB and E")
        return estimate_hardness_method(HB, E)
    raise ValueError("method must be one of " + ", ".join(ESTIMATION_METHODS))
