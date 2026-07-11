"""Tests for lcf.labio: lab-export reading, E606 metadata, and batch series.

The reader fixtures imitate the delimited export shapes of common lab
software (MTS TestSuite and Instron style headers, preamble blocks, percent
strain, kN force) without claiming byte-exact vendor formats, per ADR-0014.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from lcf import labio, pipeline, schema
from lcf.ingest import from_timeseries
from lcf.models import SpecimenMetadata, TestMetadata


# --------------------------------------------------------------------------- #
# fixture helpers
# --------------------------------------------------------------------------- #
def _decayed_force(s, onset_frac=0.7, factor=0.4):
    """Force array that drops to ``factor`` of nominal after ``onset_frac``."""
    force = s.force.copy()
    onset = s.time >= onset_frac * s.time[-1]
    force[onset] *= factor
    return force


def _write_mts_flavor(path, s, force=None):
    """MTS TestSuite flavored export: preamble block, percent strain, kN force."""
    force = s.force if force is None else force
    lines = [
        "MTS TestSuite TW Elite",
        "Test Name: LCF demo",
        "Specimen: S-01",
        "",
        "Time (s),Axial Force (kN),Axial Strain (%)",
    ]
    for t, f, e in zip(s.time, force, s.strain):
        lines.append(f"{t:.6f},{f / 1000.0:.8f},{e * 100.0:.8f}")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _write_instron_flavor(path, s):
    """Instron flavored export: tab separated, mm/mm strain, N force."""
    lines = ["Time\tStrain 1 (mm/mm)\tLoad (N)"]
    for t, e, f in zip(s.time, s.strain, s.force):
        lines.append(f"{t:.6f}\t{e:.8f}\t{f:.6f}")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _meta(s, name="t", **kw):
    kw.setdefault("area", s.area)
    kw.setdefault("E", 200000.0)
    kw.setdefault("already_true", True)
    return TestMetadata(name=name, **kw)


# --------------------------------------------------------------------------- #
# column resolution and unit conversion
# --------------------------------------------------------------------------- #
def test_read_mts_flavor_converts_percent_and_kn(tmp_path, synthetic_cyclic):
    s = synthetic_cyclic
    path = _write_mts_flavor(tmp_path / "s01.csv", s)
    run = labio.read_lab_file(path, metadata=_meta(s))
    ref = from_timeseries(s.time, s.strain, s.force, metadata=_meta(s))
    np.testing.assert_allclose(
        run.data[schema.COL_STRAIN].to_numpy(), ref.data[schema.COL_STRAIN].to_numpy(),
        rtol=1e-6, atol=1e-9,
    )
    np.testing.assert_allclose(
        run.data[schema.COL_STRESS_TRUE].to_numpy(),
        ref.data[schema.COL_STRESS_TRUE].to_numpy(), rtol=1e-6, atol=1e-3,
    )


def test_read_instron_flavor_tab_separated(tmp_path, synthetic_cyclic):
    s = synthetic_cyclic
    path = _write_instron_flavor(tmp_path / "s02.txt", s)
    run = labio.read_lab_file(path, metadata=_meta(s))
    assert len(run) == len(s.time)
    np.testing.assert_allclose(
        run.data[schema.COL_STRAIN].to_numpy(), s.strain, rtol=1e-6, atol=1e-8
    )


def test_read_plain_canonical_headers(tmp_path, synthetic_cyclic):
    s = synthetic_cyclic
    lines = ["time,strain,force"]
    for t, e, f in zip(s.time, s.strain, s.force):
        lines.append(f"{t},{e},{f}")
    path = tmp_path / "plain.csv"
    path.write_text("\n".join(lines), encoding="utf-8")
    run = labio.read_lab_file(path, metadata=_meta(s))
    assert len(run) == len(s.time)


def test_stress_column_needs_no_area(tmp_path, synthetic_cyclic):
    s = synthetic_cyclic
    stress = s.force / s.area
    lines = ["Time (s),Axial Strain (%),Axial Stress (MPa)"]
    for t, e, sig in zip(s.time, s.strain, stress):
        lines.append(f"{t},{e * 100.0},{sig}")
    path = tmp_path / "stress.csv"
    path.write_text("\n".join(lines), encoding="utf-8")
    meta = TestMetadata(name="t", E=200000.0, already_true=True)  # no area
    run = labio.read_lab_file(path, metadata=meta)
    np.testing.assert_allclose(
        run.data[schema.COL_STRESS_ENG].to_numpy(), stress, rtol=1e-6
    )


def test_ksi_stress_converts_to_mpa(tmp_path):
    lines = ["Time (s),Strain (%),Stress (ksi)", "0.0,0.0,0.0", "1.0,0.5,10.0"]
    path = tmp_path / "ksi.csv"
    path.write_text("\n".join(lines), encoding="utf-8")
    meta = TestMetadata(name="t", already_true=True)
    run = labio.read_lab_file(path, metadata=meta)
    assert run.data[schema.COL_STRESS_ENG].iloc[1] == pytest.approx(68.94757, rel=1e-4)


def test_unit_row_under_header_is_dropped(tmp_path):
    lines = [
        "Time,Strain,Force",
        "s,mm/mm,N",
        "0.0,0.0,0.0",
        "1.0,0.001,100.0",
    ]
    path = tmp_path / "unitrow.csv"
    path.write_text("\n".join(lines), encoding="utf-8")
    run = labio.read_lab_file(path, metadata=TestMetadata(name="t", area=10.0))
    assert len(run) == 2
    assert run.data[schema.COL_FORCE].iloc[1] == pytest.approx(100.0)


def test_semicolon_decimal_comma(tmp_path):
    lines = ["Zeit (s);Kraft (kN);Dehnung (%)", "0,0;0,0;0,0", "1,0;5,0;1,0"]
    path = tmp_path / "de.csv"
    path.write_text("\n".join(lines), encoding="utf-8")
    run = labio.read_lab_file(path, metadata=TestMetadata(name="t", area=50.0))
    assert run.data[schema.COL_FORCE].iloc[1] == pytest.approx(5000.0)
    assert run.data[schema.COL_STRAIN].iloc[1] == pytest.approx(0.01)


# --------------------------------------------------------------------------- #
# refusal guards
# --------------------------------------------------------------------------- #
def test_unmarked_percent_scale_strain_refuses(tmp_path):
    lines = ["time,strain,force", "0.0,0.0,0.0", "1.0,1.0,100.0"]
    path = tmp_path / "pct.csv"
    path.write_text("\n".join(lines), encoding="utf-8")
    with pytest.raises(ValueError, match="strain_unit"):
        labio.read_lab_file(path, metadata=TestMetadata(name="t", area=10.0))


def test_strain_unit_override_accepts_percent(tmp_path):
    lines = ["time,strain,force", "0.0,0.0,0.0", "1.0,1.0,100.0"]
    path = tmp_path / "pct2.csv"
    path.write_text("\n".join(lines), encoding="utf-8")
    run = labio.read_lab_file(
        path, metadata=TestMetadata(name="t", area=10.0), strain_unit="percent"
    )
    assert run.data[schema.COL_STRAIN].iloc[1] == pytest.approx(0.01)


def test_unresolvable_headers_error_lists_found(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("alpha,beta,gamma\n1,2,3\n", encoding="utf-8")
    with pytest.raises(ValueError, match="alpha"):
        labio.read_lab_file(path, metadata=TestMetadata(name="t", area=10.0))


def test_ambiguous_strain_columns_refuse(tmp_path):
    lines = ["Time (s),Axial Strain (%),Strain 1 (%),Force (N)", "0,0,0,0", "1,1,1,9"]
    path = tmp_path / "ambig.csv"
    path.write_text("\n".join(lines), encoding="utf-8")
    with pytest.raises(ValueError, match="column_map"):
        labio.read_lab_file(path, metadata=TestMetadata(name="t", area=10.0))


def test_explicit_column_map_override(tmp_path, synthetic_cyclic):
    s = synthetic_cyclic
    lines = ["c1,c2,c3"]
    for t, e, f in zip(s.time, s.strain, s.force):
        lines.append(f"{t},{e},{f}")
    path = tmp_path / "odd.csv"
    path.write_text("\n".join(lines), encoding="utf-8")
    run = labio.read_lab_file(
        path, metadata=_meta(s),
        column_map={"c1": "time", "c2": "strain", "c3": "force"},
    )
    assert len(run) == len(s.time)


# --------------------------------------------------------------------------- #
# FD&E history format
# --------------------------------------------------------------------------- #
FDE_SAMPLE = """#This is a test history
#  Copyright (C) 1999  Fatigue Design & Evaluation Comm. of SAE
#BEGIN DATA
 -999
  -41
 -112   :   1500
  333
"""


def test_read_fde_history_from_text_and_file(tmp_path):
    vals = labio.read_fde_history(FDE_SAMPLE)
    assert vals == [-999.0, -41.0, -112.0, 333.0]
    p = tmp_path / "h.txt"
    p.write_text(FDE_SAMPLE, encoding="utf-8")
    assert labio.read_fde_history(p) == vals


def test_read_fde_history_refuses_garbage():
    with pytest.raises(ValueError, match="line 2"):
        labio.read_fde_history("#ok\nnot a number\n")
    with pytest.raises(ValueError, match="no data"):
        labio.read_fde_history("#only comments\n#here\n")


# --------------------------------------------------------------------------- #
# preview
# --------------------------------------------------------------------------- #
def test_preview_reports_resolution(tmp_path, synthetic_cyclic):
    s = synthetic_cyclic
    path = _write_mts_flavor(tmp_path / "p.csv", s)
    info = labio.preview_lab_file(path)
    assert info["header_row"] == 4
    assert info["delimiter"] == ","
    assert info["columns"]["strain"] == "Axial Strain (%)"
    assert info["units"]["strain"] == "%"
    assert info["n_rows"] == len(s.time)


# --------------------------------------------------------------------------- #
# E606 specimen metadata
# --------------------------------------------------------------------------- #
def test_specimen_metadata_roundtrip_and_summary():
    spec = SpecimenMetadata(
        specimen_id="S-01", geometry="round", diameter_mm=6.35,
        control_mode="strain", strain_rate=0.004, environment="lab air",
        machine="MTS 810", extensometer="632.13F-20", standard="ASTM E606/E606M-21",
    )
    meta = TestMetadata(name="t", area=31.67, E=200000.0, specimen=spec)
    assert meta.specimen.diameter_mm == pytest.approx(6.35)

    s_time = np.linspace(0.0, 2.0, 1441)
    strain = 0.01 * np.sin(2 * math.pi * s_time)
    force = 400.0 * 31.67 * np.sin(2 * math.pi * s_time - 0.3)
    run = from_timeseries(s_time, strain, force, metadata=meta)
    ta = pipeline.analyze_test(run)
    assert ta.summary["specimen"]["specimen_id"] == "S-01"
    assert ta.summary["R"] == pytest.approx(-1.0)


def test_specimen_metadata_forbids_unknown_fields():
    with pytest.raises(Exception):
        SpecimenMetadata(bogus_field=1.0)


# --------------------------------------------------------------------------- #
# batch series
# --------------------------------------------------------------------------- #
def test_read_series_collects_errors(tmp_path, make_synthetic):
    d = tmp_path / "series"
    d.mkdir()
    _write_mts_flavor(d / "t1.csv", make_synthetic(eps_amp=0.010))
    _write_mts_flavor(d / "t2.csv", make_synthetic(eps_amp=0.006))
    (d / "broken.csv").write_text("not,a,lab\nfile,x,y\n", encoding="utf-8")
    out = labio.read_series(
        str(d), metadata_defaults={"area": 50.0, "E": 200000.0, "already_true": True}
    )
    assert sorted(r.metadata.name for r in out.runs) == ["t1", "t2"]
    assert len(out.errors) == 1
    assert "broken.csv" in out.errors[0]["file"]


def test_analyze_series_one_call(tmp_path, make_synthetic):
    d = tmp_path / "series"
    d.mkdir()
    cases = [
        ("t1", make_synthetic(n_cycles=10, eps_amp=0.012, stress_amp=430.0), 0.4),
        ("t2", make_synthetic(n_cycles=16, eps_amp=0.008, stress_amp=400.0), 0.6),
        ("t3", make_synthetic(n_cycles=24, eps_amp=0.005, stress_amp=370.0), 0.8),
    ]
    for name, s, onset in cases:
        _write_mts_flavor(d / f"{name}.csv", s, force=_decayed_force(s, onset))

    from lcf.service import LcfService

    svc = LcfService(tmp_path / "store")
    out = svc.analyze_series(
        str(d), area=50.0, E=200000.0, already_true=True, material="SYN"
    )
    assert out["errors"] == []
    assert len(out["tests"]) == 3
    assert all(not t["runout"] for t in out["tests"])
    lives = [t["n_f"] for t in out["tests"]]
    assert len(set(lives)) == 3
    assert out["fit"] is not None
    assert "basquin" in out["fit"]
    # per-test summaries and the series fit are persisted for recall
    assert svc.recall("t1", "summary") is not None
    assert svc.recall("SYN", "strain_life_fit") is not None


def test_read_series_bad_unit_override_fails_fast(tmp_path, make_synthetic):
    d = tmp_path / "series"
    d.mkdir()
    _write_mts_flavor(d / "t1.csv", make_synthetic(eps_amp=0.010))
    with pytest.raises(ValueError, match="not supported"):
        labio.read_series(
            str(d), metadata_defaults={"area": 50.0}, strain_unit="per cent"
        )


def test_analyze_series_all_runout_reports_note(tmp_path, make_synthetic):
    d = tmp_path / "series"
    d.mkdir()
    _write_mts_flavor(d / "t1.csv", make_synthetic(eps_amp=0.010))
    _write_mts_flavor(d / "t2.csv", make_synthetic(eps_amp=0.006))

    from lcf.service import LcfService

    svc = LcfService(tmp_path / "store")
    out = svc.analyze_series(
        str(d), area=50.0, E=200000.0, already_true=True, material="SYN"
    )
    assert out["fit"] is None
    assert any("run-out" in n for n in out["notes"])
