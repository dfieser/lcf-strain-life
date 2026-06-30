"""Tests for lcf.ingest and lcf.models."""

import math

import numpy as np
import pandas as pd
import pytest

from lcf import schema
from lcf.ingest import TestRun, from_timeseries, normalize, read_csv
from lcf.models import AnalysisParams, MeanStressModel, TestMetadata


def test_from_timeseries_basic(synthetic_cyclic):
    s = synthetic_cyclic
    meta = TestMetadata(name="syn", area=s.area, E=200000.0)
    t = from_timeseries(s.time, s.strain, s.force, metadata=meta)
    assert isinstance(t, TestRun)
    assert len(t) == len(s.time)
    # derived columns present
    for col in schema.DERIVED:
        assert col in t.data.columns


def test_normalize_eng_to_true_values():
    df = pd.DataFrame({"time": [0.0, 1.0], "strain": [0.0, 0.02], "force": [0.0, 5000.0]})
    meta = TestMetadata(name="t", area=10.0)  # 5000 N / 10 mm^2 = 500 MPa eng
    out = normalize(df, meta)
    assert out[schema.COL_STRESS_ENG].iloc[1] == pytest.approx(500.0)
    assert out[schema.COL_STRAIN_TRUE].iloc[1] == pytest.approx(math.log(1.02))
    assert out[schema.COL_STRESS_TRUE].iloc[1] == pytest.approx(500.0 * 1.02)


def test_already_true_skips_conversion():
    df = pd.DataFrame({"time": [0.0, 1.0], "strain": [0.0, 0.02], "force": [0.0, 5000.0]})
    meta = TestMetadata(name="t", area=10.0, already_true=True)
    out = normalize(df, meta)
    # strain_true == strain, stress_true == stress_eng (no conversion)
    assert out[schema.COL_STRAIN_TRUE].iloc[1] == pytest.approx(0.02)
    assert out[schema.COL_STRESS_TRUE].iloc[1] == pytest.approx(500.0)


def test_missing_column_raises():
    df = pd.DataFrame({"time": [0.0], "strain": [0.0]})  # no force
    meta = TestMetadata(name="t", area=10.0)
    with pytest.raises(ValueError, match="missing required column"):
        normalize(df, meta)


def test_missing_area_raises_when_force_based():
    df = pd.DataFrame({"time": [0.0], "strain": [0.0], "force": [0.0]})
    meta = TestMetadata(name="t")  # no area
    with pytest.raises(ValueError, match="area is required"):
        normalize(df, meta)


def test_stress_eng_column_bypasses_area():
    df = pd.DataFrame(
        {"time": [0.0, 1.0], "strain": [0.0, 0.01], "force": [0.0, 0.0],
         "stress_eng": [0.0, 300.0]}
    )
    meta = TestMetadata(name="t")  # no area, but stress_eng provided
    out = normalize(df, meta)
    assert out[schema.COL_STRESS_TRUE].iloc[1] == pytest.approx(300.0 * 1.01)


def test_unequal_length_raises():
    meta = TestMetadata(name="t", area=10.0)
    with pytest.raises(ValueError, match="equal length"):
        from_timeseries([0.0, 1.0], [0.0], [0.0, 1.0], metadata=meta)


def test_read_csv_with_column_map(tmp_path):
    p = tmp_path / "raw.csv"
    p.write_text("Time (s),Axial Strain,Axial Force\n0,0,0\n1,0.01,5000\n")
    meta = TestMetadata(name="t", area=10.0)
    t = read_csv(
        p, metadata=meta,
        column_map={"Time (s)": "time", "Axial Strain": "strain", "Axial Force": "force"},
    )
    assert t.data[schema.COL_STRESS_ENG].iloc[1] == pytest.approx(500.0)


def test_read_csv_with_machine_header_block(tmp_path):
    # mirrors a real machine export: a metadata header block, then columns, then data
    p = tmp_path / "machine.csv"
    p.write_text(
        "# Test machine export\n"
        "# Specimen: S1, area 10 mm^2\n"
        "# Control: axial strain\n"
        "Time (s),Axial Strain (mm/mm),Axial Force (N)\n"
        "0,0,0\n"
        "1,0.02,5000\n"
        "2,0,0\n"
    )
    meta = TestMetadata(name="S1", area=10.0)
    t = read_csv(
        p, metadata=meta,
        column_map={"Time (s)": "time", "Axial Strain (mm/mm)": "strain",
                    "Axial Force (N)": "force"},
        skiprows=3,
    )
    assert len(t) == 3
    assert t.data[schema.COL_STRESS_ENG].iloc[1] == pytest.approx(500.0)
    assert t.data[schema.COL_STRESS_TRUE].iloc[1] == pytest.approx(500.0 * 1.02)


# --- model validation -------------------------------------------------------
def test_metadata_rejects_bad_area():
    with pytest.raises(Exception):
        TestMetadata(name="t", area=-1.0)


def test_metadata_forbids_extra_fields():
    with pytest.raises(Exception):
        TestMetadata(name="t", area=10.0, bogus=123)


def test_analysis_params_defaults():
    p = AnalysisParams()
    assert p.failure_criterion_pct == 30.0
    assert p.mean_stress_model is MeanStressModel.SWT


def test_analysis_params_rejects_bad_pct():
    with pytest.raises(Exception):
        AnalysisParams(failure_criterion_pct=150.0)


# --- input validation (M1/L1) ----------------------------------------------
def test_normalize_rejects_nan():
    df = pd.DataFrame({"time": [0.0, 1.0, 2.0], "strain": [0.0, np.nan, 0.01],
                       "force": [0.0, 100.0, 200.0]})
    meta = TestMetadata(name="t", area=10.0)
    with pytest.raises(ValueError, match="NaN"):
        normalize(df, meta)


def test_normalize_nan_bypass_with_validate_false():
    df = pd.DataFrame({"time": [0.0, 1.0], "strain": [0.0, np.nan],
                       "force": [0.0, 100.0]})
    meta = TestMetadata(name="t", area=10.0)
    out = normalize(df, meta, validate=False)  # should not raise
    assert np.isnan(out[schema.COL_STRAIN_TRUE].iloc[1])


def test_normalize_warns_on_nonmonotonic_time():
    import warnings as _w
    df = pd.DataFrame({"time": [0.0, 2.0, 1.0], "strain": [0.0, 0.01, 0.02],
                       "force": [0.0, 100.0, 200.0]})
    meta = TestMetadata(name="t", area=10.0)
    with _w.catch_warnings(record=True) as w:
        _w.simplefilter("always")
        normalize(df, meta)
        assert any("monoton" in str(x.message) for x in w)
