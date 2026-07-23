"""Tests for the test-record@1 and collection@1 interchange formats,
the validate_document dispatcher, the JSON Schema artifacts, and the
lcf-validate command line entry."""

import json
from pathlib import Path

import pytest

from lcf import interchange, validate_cli
from lcf.service import LcfService

SCHEMAS_DIR = Path(__file__).resolve().parents[1] / "docs" / "schemas"


def make_record(**overrides):
    kwargs = dict(
        record_id="SAE1137-1",
        material="SAE 1137",
        strain_amplitude=0.009,
        reversals_to_failure=4234.0,
        source="Williams, Lee, Rilly, Int J Fatigue 25 (2003) 427-436",
        origin="republished-factual",
        response={"stress_amplitude": 553.0, "at_life_fraction": 0.5},
    )
    kwargs.update(overrides)
    return interchange.export_test_record(**kwargs)


def make_collection(**overrides):
    kwargs = dict(
        name="example collection",
        license="CC-BY-4.0",
        created="2026-07-23",
        records=[make_record()],
    )
    kwargs.update(overrides)
    return interchange.export_collection(**kwargs)


class TestTestRecord:
    def test_round_trip(self):
        doc = make_record()
        rec = interchange.import_test_record(doc)
        assert rec.record_id == "SAE1137-1"
        assert rec.material == "SAE 1137"
        assert rec.test.control_mode == "strain"
        assert rec.test.strain_amplitude == pytest.approx(0.009)
        assert rec.failure.reversals_to_failure == pytest.approx(4234.0)
        assert rec.failure.runout is False
        assert rec.response is not None
        assert rec.response.stress_amplitude == pytest.approx(553.0)
        assert rec.provenance.origin == "republished-factual"
        again = rec.model_dump(by_alias=True, exclude_none=True)
        assert again == doc

    def test_strain_control_needs_strain_amplitude(self):
        with pytest.raises(ValueError, match="strain_amplitude"):
            make_record(strain_amplitude=None)

    def test_stress_control_mode(self):
        doc = make_record(
            control_mode="stress", strain_amplitude=None,
            stress_amplitude=300.0,
        )
        rec = interchange.import_test_record(doc)
        assert rec.test.control_mode == "stress"
        assert rec.test.stress_amplitude == pytest.approx(300.0)

    def test_runout_record(self):
        doc = make_record(runout=True, reversals_to_failure=2.0e6)
        rec = interchange.import_test_record(doc)
        assert rec.failure.runout is True

    def test_source_is_required(self):
        doc = make_record()
        del doc["provenance"]["source"]
        result = interchange.validate_document(doc)
        assert not result["valid"]
        assert any("provenance.source" in e for e in result["errors"])

    def test_extra_control_fields_via_test_block(self):
        doc = make_record(test={"temperature_C": 550.0, "environment": "lab air"})
        rec = interchange.import_test_record(doc)
        assert rec.test.temperature_C == pytest.approx(550.0)
        assert rec.test.environment == "lab air"

    def test_per_cycle_table(self):
        doc = make_record(per_cycle={
            "columns": ["cycle", "stress_amplitude", "mean_stress"],
            "rows": [[1, 560.0, 12.0], [10, 553.0, 8.0]],
        })
        rec = interchange.import_test_record(doc)
        assert rec.per_cycle is not None
        assert len(rec.per_cycle.rows) == 2

    def test_per_cycle_ragged_rows_rejected(self):
        with pytest.raises(ValueError, match="row 1"):
            make_record(per_cycle={
                "columns": ["cycle", "stress_amplitude"],
                "rows": [[1, 560.0], [10]],
            })

    def test_per_cycle_duplicate_columns_rejected(self):
        with pytest.raises(ValueError, match="unique"):
            make_record(per_cycle={
                "columns": ["cycle", "cycle"], "rows": [[1, 2]],
            })

    def test_unknown_origin_rejected(self):
        with pytest.raises(ValueError):
            make_record(origin="scraped")

    def test_wrong_schema_refused(self):
        doc = make_record()
        doc["schema"] = "somebody-else/format"
        with pytest.raises(ValueError, match="unknown schema"):
            interchange.import_test_record(doc)

    def test_wrong_version_refused(self):
        doc = make_record()
        doc["version"] = 2
        with pytest.raises(ValueError, match="unsupported version"):
            interchange.import_test_record(doc)


class TestCollection:
    def test_round_trip_with_materials_and_records(self):
        mat = interchange.export_material(
            name="SAE 1005", E=207000.0, sigma_f=886.0, b=-0.14,
            eps_f=0.28, c=-0.5, K_prime=1240.0, n_prime=0.27,
            source="Lee, Pan, Hathaway, Barkey 2005",
        )
        doc = make_collection(materials=[mat])
        col = interchange.import_collection(doc)
        assert col.name == "example collection"
        assert col.license == "CC-BY-4.0"
        assert len(col.materials) == 1
        assert len(col.records) == 1
        assert col.materials[0].basquin.b == pytest.approx(-0.14)

    def test_empty_collection_rejected(self):
        with pytest.raises(ValueError, match="at least one"):
            make_collection(records=[])

    def test_duplicate_record_ids_rejected(self):
        with pytest.raises(ValueError, match="duplicate record_id"):
            make_collection(records=[make_record(), make_record()])

    def test_invalid_member_record_surfaces_path(self):
        doc = make_collection()
        doc["records"][0]["failure"]["reversals_to_failure"] = -5.0
        result = interchange.validate_document(doc)
        assert not result["valid"]
        assert any("records.0.failure" in e for e in result["errors"])

    def test_created_must_be_iso_date(self):
        with pytest.raises(ValueError):
            make_collection(created="23 July 2026")


class TestValidateDocument:
    def test_material_from_frozen_writer_validates(self):
        mat = interchange.export_material(
            name="X", E=200000.0, sigma_f=900.0, b=-0.1, eps_f=0.5, c=-0.6,
        )
        result = interchange.validate_document(mat)
        assert result["valid"]
        assert result["kind"] == "material"

    def test_unknown_schema_reported(self):
        result = interchange.validate_document({"schema": "nope", "version": 1})
        assert not result["valid"]
        assert result["kind"] is None
        assert "known schemas" in result["errors"][0]

    def test_non_dict_reported(self):
        result = interchange.validate_document([1, 2, 3])
        assert not result["valid"]

    def test_wrong_units_reported(self):
        mat = interchange.export_material(
            name="X", E=200000.0, sigma_f=900.0, b=-0.1, eps_f=0.5, c=-0.6,
        )
        mat["units"]["stress"] = "ksi"
        result = interchange.validate_document(mat)
        assert not result["valid"]
        assert any("units" in e for e in result["errors"])


class TestSchemaArtifacts:
    @pytest.mark.parametrize("kind", validate_cli.KINDS)
    def test_checked_in_schema_matches_generated(self, kind):
        path = SCHEMAS_DIR / f"{kind}.v1.schema.json"
        assert path.exists(), (
            f"missing schema artifact {path}, regenerate with "
            "lcf-validate --write-schemas docs/schemas"
        )
        on_disk = json.loads(path.read_text(encoding="utf-8"))
        assert on_disk == interchange.json_schema(kind), (
            f"{path.name} drifted from the pydantic model, regenerate with "
            "lcf-validate --write-schemas docs/schemas"
        )

    def test_unknown_kind_raises(self):
        with pytest.raises(ValueError, match="unknown kind"):
            interchange.json_schema("nope")


class TestCli:
    def test_valid_file_exits_zero(self, tmp_path, capsys):
        f = tmp_path / "rec.json"
        f.write_text(json.dumps(make_record()), encoding="utf-8")
        assert validate_cli.main([str(f)]) == 0
        assert "ok" in capsys.readouterr().out

    def test_invalid_file_exits_one(self, tmp_path, capsys):
        doc = make_record()
        doc["version"] = 99
        f = tmp_path / "bad.json"
        f.write_text(json.dumps(doc), encoding="utf-8")
        assert validate_cli.main([str(f)]) == 1
        assert "FAIL" in capsys.readouterr().out

    def test_unreadable_file_exits_one(self, tmp_path, capsys):
        f = tmp_path / "broken.json"
        f.write_text("{not json", encoding="utf-8")
        assert validate_cli.main([str(f)]) == 1
        assert "cannot read JSON" in capsys.readouterr().out

    def test_write_schemas(self, tmp_path):
        assert validate_cli.main(["--write-schemas", str(tmp_path)]) == 0
        for kind in validate_cli.KINDS:
            assert (tmp_path / f"{kind}.v1.schema.json").exists()


class TestServiceExposure:
    @pytest.fixture
    def svc(self, tmp_path):
        return LcfService(store=str(tmp_path / "store"))

    def test_validate_interchange(self, svc):
        result = svc.validate_interchange(make_record())
        assert result["valid"]
        assert result["kind"] == "test-record"

    def test_summarize_collection(self, svc):
        records = [
            make_record(),
            make_record(record_id="SAE1137-2", strain_amplitude=0.002,
                        reversals_to_failure=437498.0),
            make_record(record_id="RUNOUT-1", strain_amplitude=0.0015,
                        reversals_to_failure=1.0e7, runout=True),
        ]
        summary = svc.summarize_collection(make_collection(records=records))
        assert summary["valid"]
        assert summary["record_count"] == 3
        assert summary["records_by_material"] == {"SAE 1137": 3}
        assert summary["runout_count"] == 1
        assert summary["strain_amplitude_range"]["min"] == pytest.approx(0.0015)
        assert summary["reversals_range"]["max"] == pytest.approx(1.0e7)

    def test_summarize_rejects_non_collection(self, svc):
        summary = svc.summarize_collection(make_record())
        assert summary["valid"] is False
        assert any("not a collection" in e for e in summary["errors"])

    def test_summarize_reports_invalid(self, svc):
        doc = make_collection()
        doc["license"] = ""
        summary = svc.summarize_collection(doc)
        assert summary["valid"] is False
        assert summary["errors"]
