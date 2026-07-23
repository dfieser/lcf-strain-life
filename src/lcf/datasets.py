"""Bundled example datasets, published and citable.

One module holds the example data used by the README, the examples, and the
graphical interface, so the numbers exist in exactly one place. The test
suite keeps its own copy on purpose: a golden reference must stay independent
of the code it validates.

This module also builds the seed open-data collection,
:func:`seed_collection`. The checked-in artifact
``docs/data/seed_collection.json`` is exactly that output, a test guards
against drift. The seed is a schema-reference dataset of published, citable
strain-life data. It demonstrates the interchange formats, it is not yet a
database at publishable scale.
"""

from __future__ import annotations

import pandas as pd

SAE1137_CITATION = (
    "Williams, C.R., Lee, Y.-L., Rilly, J.T., 'A practical method for "
    "statistical analysis of strain-life fatigue data', International "
    "Journal of Fatigue 25 (2003) 427-436"
)

SAE1137_E = 208000.0
"""Nominal elastic modulus for the SAE 1137 example (MPa)."""

_SAE1137: dict[str, list] = {
    "test": [f"SAE1137-{i}" for i in range(1, 7)],
    "total_strain_amp": [0.00900, 0.00700, 0.00500, 0.00300, 0.00200, 0.00175],
    "stress_amp": [553.0, 522.0, 464.0, 405.0, 350.0, 319.0],
    "reversals": [4234.0, 7398.0, 14768.0, 77104.0, 437498.0, 3327958.0],
}


def sae1137_reduced() -> pd.DataFrame:
    """Published SAE 1137 per-test reduced strain-life data.

    One row per test: half-life total strain amplitude (fraction), stress
    amplitude (MPa), and reversals to failure 2N_f. Source:
    :data:`SAE1137_CITATION`.
    """
    return pd.DataFrame(_SAE1137)


SAE1005_CITATION = (
    "Lee, Y.-L., Pan, J., Hathaway, R., Barkey, M., 'Fatigue Testing and "
    "Analysis: Theory and Practice', Elsevier Butterworth-Heinemann, 2005, "
    "chapter 5 worked notched-plate example"
)

KEYHOLE_CITATION = (
    "SAE Fatigue Design and Evaluation committee keyhole program material "
    "constants as documented on the eFatigue SAE keyhole benchmark page, "
    "archived at web.archive.org/web/20251215150910/https://www.efatigue.com"
    "/benchmarks/SAE_keyhole/SAE_keyhole.html"
)

WU2024_CITATION = (
    "Wu, Zhang, Paraschivoiu, Materials 17 (2024) 4521, CC BY 4.0, "
    "cyclic curve constants K' and n'"
)

#: Verified published constant sets bundled as material documents.
#: Values live here in exactly one place, the seed collection reads them.
SEED_MATERIALS: tuple[dict, ...] = (
    {
        "name": "SAE 1005",
        "E": 207000.0, "sigma_f": 886.0, "b": -0.14,
        "eps_f": 0.28, "c": -0.5,
        "K_prime": 1240.0, "n_prime": 0.27,
        "source": SAE1005_CITATION,
        "notes": (
            "Constants transcribed verbatim from the cited text. Factual "
            "values re-tabulated with attribution."
        ),
    },
    {
        "name": "Man-Ten",
        "E": 203000.0, "sigma_f": 915.0, "b": -0.095,
        "eps_f": 0.26, "c": -0.47,
        "K_prime": 1200.6, "n_prime": 0.2,
        "source": KEYHOLE_CITATION,
        "notes": (
            "Strain-life constants from the SAE committee benchmark page. "
            "K' and n' from " + WU2024_CITATION + ". Factual values "
            "re-tabulated with attribution."
        ),
    },
    {
        "name": "RQC-100",
        "E": 203000.0, "sigma_f": 1160.0, "b": -0.075,
        "eps_f": 1.06, "c": -0.75,
        "K_prime": 1131.6, "n_prime": 0.1,
        "source": KEYHOLE_CITATION,
        "notes": (
            "Strain-life constants from the SAE committee benchmark page. "
            "K' and n' from " + WU2024_CITATION + ". Factual values "
            "re-tabulated with attribution."
        ),
    },
)

_SEED_CONTRIBUTORS = (
    {"name": "David Fieser", "orcid": "https://orcid.org/0009-0007-5754-4331"},
    {"name": "Hugh Shortt", "orcid": "https://orcid.org/0000-0001-8015-3733"},
)

_SEED_CREATED = "2026-07-23"


def seed_collection() -> dict:
    """Build the seed open-data collection as a ``collection@1`` document.

    Six SAE 1137 strain-controlled tests as test records, Williams, Lee,
    Rilly 2003, plus three verified published constant sets as material
    documents. Every value is factual data re-tabulated from the cited
    source. The compilation, the selection, arrangement, and metadata, is
    licensed CC-BY-4.0. The record data keep their cited provenance.
    """
    from . import interchange

    records = []
    for test_id, strain, stress, rev in zip(
        _SAE1137["test"], _SAE1137["total_strain_amp"],
        _SAE1137["stress_amp"], _SAE1137["reversals"],
    ):
        records.append(interchange.export_test_record(
            record_id=test_id,
            material="SAE 1137",
            strain_amplitude=strain,
            reversals_to_failure=rev,
            source=SAE1137_CITATION,
            origin="republished-factual",
            response={"stress_amplitude": stress, "at_life_fraction": 0.5},
            notes=(
                "Half-life values as tabulated in the cited source, "
                f"elastic modulus {SAE1137_E:g} MPa."
            ),
        ))
    materials = [
        interchange.export_material(
            name=m["name"], E=m["E"], sigma_f=m["sigma_f"], b=m["b"],
            eps_f=m["eps_f"], c=m["c"], K_prime=m["K_prime"],
            n_prime=m["n_prime"], source=m["source"], notes=m["notes"],
        )
        for m in SEED_MATERIALS
    ]
    return interchange.export_collection(
        name="lcf-strain-life seed collection",
        description=(
            "A small schema-reference dataset of published, citable "
            "strain-life data. It demonstrates the lcf-strain-life "
            "interchange formats and seeds the open strain-life data "
            "effort. It is not yet a database at publishable scale."
        ),
        license="CC-BY-4.0",
        created=_SEED_CREATED,
        homepage="https://github.com/dfieser/lcf-strain-life",
        contributors=list(_SEED_CONTRIBUTORS),
        materials=materials,
        records=records,
    )
