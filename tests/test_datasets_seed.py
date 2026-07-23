"""Tests for the seed open-data collection: schema validity, agreement with
the bundled SAE 1137 dataset, and drift protection for the checked-in
artifact."""

import json
from pathlib import Path

import pytest

from lcf import datasets, interchange
from lcf.service import LcfService

ARTIFACT = (
    Path(__file__).resolve().parents[1] / "docs" / "data"
    / "seed_collection.json"
)


@pytest.fixture(scope="module")
def seed():
    return datasets.seed_collection()


def test_seed_is_a_valid_collection(seed):
    result = interchange.validate_document(seed)
    assert result["valid"], result["errors"]
    assert result["kind"] == "collection"


def test_seed_matches_bundled_sae1137(seed):
    df = datasets.sae1137_reduced()
    records = {r["record_id"]: r for r in seed["records"]}
    assert len(records) == len(df)
    for row in df.itertuples():
        rec = records[row.test]
        assert rec["material"] == "SAE 1137"
        assert rec["test"]["strain_amplitude"] == pytest.approx(
            row.total_strain_amp
        )
        assert rec["response"]["stress_amplitude"] == pytest.approx(
            row.stress_amp
        )
        assert rec["failure"]["reversals_to_failure"] == pytest.approx(
            row.reversals
        )
        assert rec["provenance"]["source"] == datasets.SAE1137_CITATION
        assert rec["provenance"]["origin"] == "republished-factual"


def test_seed_material_constants_are_the_published_sets(seed):
    by_name = {m["name"]: m for m in seed["materials"]}
    assert set(by_name) == {"SAE 1005", "Man-Ten", "RQC-100"}
    sae1005 = by_name["SAE 1005"]
    assert sae1005["E"] == pytest.approx(207000.0)
    assert sae1005["basquin"]["sigma_f"] == pytest.approx(886.0)
    assert sae1005["basquin"]["b"] == pytest.approx(-0.14)
    assert sae1005["coffin_manson"]["eps_f"] == pytest.approx(0.28)
    assert sae1005["coffin_manson"]["c"] == pytest.approx(-0.5)
    assert sae1005["ramberg_osgood"]["K_prime"] == pytest.approx(1240.0)
    assert sae1005["ramberg_osgood"]["n_prime"] == pytest.approx(0.27)
    manten = by_name["Man-Ten"]
    assert manten["basquin"]["sigma_f"] == pytest.approx(915.0)
    assert manten["ramberg_osgood"]["K_prime"] == pytest.approx(1200.6)
    rqc = by_name["RQC-100"]
    assert rqc["basquin"]["sigma_f"] == pytest.approx(1160.0)
    assert rqc["coffin_manson"]["eps_f"] == pytest.approx(1.06)


def test_every_seed_entry_carries_provenance(seed):
    for mat in seed["materials"]:
        assert mat["provenance"]["source"]
    for rec in seed["records"]:
        assert rec["provenance"]["source"]


def test_checked_in_artifact_matches_builder(seed):
    assert ARTIFACT.exists(), (
        f"missing {ARTIFACT}, regenerate from datasets.seed_collection()"
    )
    on_disk = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    assert on_disk == seed, (
        "docs/data/seed_collection.json drifted from "
        "datasets.seed_collection(), regenerate it"
    )


def test_summary_through_service(tmp_path, seed):
    svc = LcfService(store=str(tmp_path / "store"))
    summary = svc.summarize_collection(seed)
    assert summary["valid"]
    assert summary["record_count"] == 6
    assert summary["material_count"] == 3
    assert summary["records_by_material"] == {"SAE 1137": 6}
    assert summary["runout_count"] == 0
    assert summary["license"] == "CC-BY-4.0"
    assert summary["contributors"] == ["David Fieser", "Hugh Shortt"]


def test_seed_fits_close_to_golden_constants(seed):
    """The seed records must carry enough information to reproduce a
    strain-life fit. Fitting the six records reproduces the golden SAE 1137
    reduction within loose tolerances, the golden values themselves live in
    the test suite's independent copy."""
    from lcf import fits

    strain = [r["test"]["strain_amplitude"] for r in seed["records"]]
    stress = [r["response"]["stress_amplitude"] for r in seed["records"]]
    rev = [r["failure"]["reversals_to_failure"] for r in seed["records"]]
    elastic = [s / datasets.SAE1137_E for s in stress]
    plastic = [t - e for t, e in zip(strain, elastic)]
    # Williams et al. drop plastic strain amplitudes below 5e-4, the same
    # threshold the golden reduction uses.
    cm = fits.fit_coffin_manson(plastic, rev, min_plastic_strain=5e-4)
    assert cm.c == pytest.approx(-0.62, abs=0.05)
    assert cm.eps_f == pytest.approx(1.1, rel=0.25)
