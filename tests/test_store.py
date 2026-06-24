"""Tests for lcf.store — SQLite/Parquet/PNG persistence and hashing."""

import numpy as np
import pandas as pd
import pytest

from lcf.store import LcfStore, hash_inputs, to_jsonable


def test_save_and_recall_scalar(tmp_path):
    s = LcfStore(tmp_path / "store")
    s.save("T1", "summary", {"stress_amp": 553.0, "c": -0.62}, input_hash="abc")
    rec = s.recall("T1", "summary")
    assert rec["value"]["stress_amp"] == 553.0
    assert rec["input_hash"] == "abc"


def test_recall_missing_returns_none(tmp_path):
    s = LcfStore(tmp_path / "store")
    assert s.recall("nope", "nope") is None


def test_dataframe_roundtrip(tmp_path):
    s = LcfStore(tmp_path / "store")
    df = pd.DataFrame({"cycle": [1, 2, 3], "stress_max": [400.0, 410.0, 405.0]})
    s.save("T1", "per_cycle", {"n": 3}, dataframe=df, input_hash="h1")
    back = s.get_dataframe("T1", "per_cycle")
    pd.testing.assert_frame_equal(back, df)


def test_upsert_overwrites(tmp_path):
    s = LcfStore(tmp_path / "store")
    s.save("T1", "summary", {"v": 1}, input_hash="h1")
    s.save("T1", "summary", {"v": 2}, input_hash="h2")
    rec = s.recall("T1", "summary")
    assert rec["value"]["v"] == 2 and rec["input_hash"] == "h2"
    assert len(s.list("T1")) == 1  # still a single row


def test_has_fresh_cache(tmp_path):
    s = LcfStore(tmp_path / "store")
    s.save("T1", "fit", {"c": -0.6}, input_hash="hABC")
    assert s.has_fresh("T1", "fit", "hABC") is True
    assert s.has_fresh("T1", "fit", "different") is False
    assert s.has_fresh("T1", "missing", "hABC") is False


def test_list_and_delete(tmp_path):
    s = LcfStore(tmp_path / "store")
    s.save("T1", "summary", {"v": 1})
    s.save("T1", "fit", {"v": 2})
    s.save("T2", "summary", {"v": 3})
    assert len(s.list()) == 3
    assert len(s.list("T1")) == 2
    assert s.delete("T1", "fit") == 1
    assert len(s.list("T1")) == 1
    assert s.delete("T2") == 1
    assert len(s.list("T2")) == 0


def test_persistence_across_instances(tmp_path):
    root = tmp_path / "store"
    LcfStore(root).save("T1", "summary", {"v": 42}, input_hash="h")
    # new instance, same root
    assert LcfStore(root).recall("T1", "summary")["value"]["v"] == 42


# --- hashing ----------------------------------------------------------------
def test_hash_deterministic_and_order_independent_for_dict():
    h1 = hash_inputs(b"rawdata", {"pct": 30.0, "model": "swt"})
    h2 = hash_inputs(b"rawdata", {"model": "swt", "pct": 30.0})  # key order swapped
    assert h1 == h2


def test_hash_changes_with_inputs():
    base = hash_inputs(b"rawdata", {"pct": 30.0})
    assert base != hash_inputs(b"rawdata2", {"pct": 30.0})
    assert base != hash_inputs(b"rawdata", {"pct": 25.0})


def test_to_jsonable_handles_numpy():
    out = to_jsonable({"a": np.float64(1.5), "b": np.int64(3), "c": np.array([1.0, 2.0])})
    assert out == {"a": 1.5, "b": 3, "c": [1.0, 2.0]}
    assert isinstance(out["a"], float) and isinstance(out["b"], int)
