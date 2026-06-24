"""Persistence — the compute / save / recall store (ADR-0007).

A small content-addressed store: a **SQLite** catalog keyed by ``(key, quantity)``
holds scalar/JSON values, an input hash, and paths to large artifacts;
**Parquet** holds per-cycle tables; **PNG** holds plot artifacts on disk. Results
are recomputed only when the input hash changes.

``key`` identifies a test or material (e.g. ``"SAE1137"`` or ``"specimen-3"``);
``quantity`` names the stored result (e.g. ``"per_cycle"``, ``"strain_life_fit"``,
``"summary"``).
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import math
import sqlite3
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

__all__ = ["LcfStore", "hash_inputs", "to_jsonable"]


def to_jsonable(obj: Any) -> Any:
    """Convert dataclasses, pydantic models, and numpy scalars to JSON-able data.

    Non-finite floats (NaN, +/-Inf) are mapped to ``None`` so the result is
    *valid* JSON (RFC 8259 has no NaN/Infinity literals). This matters because
    these values are produced by ordinary use — e.g. a 2-point regression yields
    NaN standard errors — and bare ``NaN`` tokens break strict MCP/JSON clients.
    """
    if obj is None or isinstance(obj, bool) or isinstance(obj, (int, str)):
        return obj
    if isinstance(obj, float):
        return obj if math.isfinite(obj) else None
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        f = float(obj)
        return f if math.isfinite(f) else None
    if isinstance(obj, np.ndarray):
        return [to_jsonable(v) for v in obj.tolist()]
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {k: to_jsonable(v) for k, v in dataclasses.asdict(obj).items()}
    if hasattr(obj, "model_dump"):  # pydantic v2
        return to_jsonable(obj.model_dump(mode="json"))
    if isinstance(obj, dict):
        return {str(k): to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [to_jsonable(v) for v in obj]
    return str(obj)


def dumps(obj: Any, **kwargs) -> str:
    """``json.dumps`` of a sanitized object with NaN/Inf rejected (valid JSON)."""
    return json.dumps(to_jsonable(obj), allow_nan=False, **kwargs)


def hash_inputs(*parts: Any) -> str:
    """SHA-256 over the given parts (bytes used directly; others JSON-encoded)."""
    h = hashlib.sha256()
    for p in parts:
        if isinstance(p, (bytes, bytearray)):
            h.update(bytes(p))
        else:
            h.update(json.dumps(to_jsonable(p), sort_keys=True, allow_nan=False).encode("utf-8"))
    return h.hexdigest()


_SCHEMA = """
CREATE TABLE IF NOT EXISTS results (
    key          TEXT NOT NULL,
    quantity     TEXT NOT NULL,
    input_hash   TEXT,
    value_json   TEXT,
    parquet_path TEXT,
    png_path     TEXT,
    created_at   REAL,
    PRIMARY KEY (key, quantity)
);
"""


class LcfStore:
    """Content-addressed result store backed by SQLite + Parquet + PNG files."""

    def __init__(self, root: str | Path = ".lcfstore"):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.db_path = self.root / "catalog.sqlite"
        with self._conn() as con:
            con.executescript(_SCHEMA)

    def _conn(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.db_path, timeout=30.0)
        con.row_factory = sqlite3.Row
        # WAL + a generous busy timeout avoid "database is locked" when the MCP
        # server runs tools concurrently (M6).
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("PRAGMA busy_timeout=30000")
        return con

    # ----------------------------------------------------------------- save
    def save(
        self,
        key: str,
        quantity: str,
        value: Any = None,
        *,
        input_hash: str | None = None,
        dataframe: pd.DataFrame | None = None,
        png_path: str | Path | None = None,
    ) -> None:
        """Upsert a result. ``dataframe`` is written to Parquet under the store."""
        parquet_path = None
        if dataframe is not None:
            # Hash suffix keeps the filename injective: distinct (key, quantity)
            # never collide after _safe() flattens separators (M4).
            suffix = hashlib.sha256(f"{key}\x00{quantity}".encode()).hexdigest()[:8]
            parquet_path = self.root / f"{_safe(key)}__{_safe(quantity)}__{suffix}.parquet"
            dataframe.to_parquet(parquet_path)
            parquet_path = str(parquet_path)
        value_json = dumps(value) if value is not None else None
        with self._conn() as con:
            con.execute(
                """INSERT INTO results
                   (key, quantity, input_hash, value_json, parquet_path, png_path, created_at)
                   VALUES (?,?,?,?,?,?,?)
                   ON CONFLICT(key, quantity) DO UPDATE SET
                     input_hash=excluded.input_hash,
                     value_json=excluded.value_json,
                     parquet_path=excluded.parquet_path,
                     png_path=excluded.png_path,
                     created_at=excluded.created_at""",
                (key, quantity, input_hash, value_json, parquet_path,
                 str(png_path) if png_path else None, time.time()),
            )

    # --------------------------------------------------------------- recall
    def recall(self, key: str, quantity: str) -> dict | None:
        """Return the stored record (value + paths + hash), or None if absent."""
        with self._conn() as con:
            row = con.execute(
                "SELECT * FROM results WHERE key=? AND quantity=?", (key, quantity)
            ).fetchone()
        if row is None:
            return None
        return {
            "key": row["key"],
            "quantity": row["quantity"],
            "input_hash": row["input_hash"],
            "value": json.loads(row["value_json"]) if row["value_json"] else None,
            "parquet_path": row["parquet_path"],
            "png_path": row["png_path"],
            "created_at": row["created_at"],
        }

    def get_dataframe(self, key: str, quantity: str) -> pd.DataFrame | None:
        """Load the Parquet table for a result, if any."""
        rec = self.recall(key, quantity)
        if rec is None or not rec["parquet_path"]:
            return None
        return pd.read_parquet(rec["parquet_path"])

    def has_fresh(self, key: str, quantity: str, input_hash: str) -> bool:
        """True if a stored result exists with a matching input hash (cache hit)."""
        rec = self.recall(key, quantity)
        return rec is not None and rec["input_hash"] == input_hash

    # ----------------------------------------------------------------- misc
    def list(self, key: str | None = None) -> list[dict]:
        """List stored results (optionally for one key)."""
        with self._conn() as con:
            if key is None:
                rows = con.execute(
                    "SELECT key, quantity, input_hash, created_at FROM results "
                    "ORDER BY key, quantity"
                ).fetchall()
            else:
                rows = con.execute(
                    "SELECT key, quantity, input_hash, created_at FROM results "
                    "WHERE key=? ORDER BY quantity", (key,)
                ).fetchall()
        return [dict(r) for r in rows]

    def delete(self, key: str, quantity: str | None = None) -> int:
        """Delete a result (or all results for a key). Returns rows deleted."""
        with self._conn() as con:
            if quantity is None:
                cur = con.execute("DELETE FROM results WHERE key=?", (key,))
            else:
                cur = con.execute(
                    "DELETE FROM results WHERE key=? AND quantity=?", (key, quantity)
                )
            return cur.rowcount


def _safe(name: str) -> str:
    """Filesystem-safe token from an identifier."""
    return "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in name)
