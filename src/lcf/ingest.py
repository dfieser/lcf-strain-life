"""Ingestion and normalization: raw test data -> true stress/strain series.

Entry points:

* :func:`from_timeseries`: build a :class:`Test` from arrays ``(time, strain, force)``.
* :func:`from_dataframe`:  build a :class:`Test` from a raw DataFrame.
* :func:`read_csv`:        read a delimited file (with optional column mapping).

All paths run :func:`normalize`, which adds the derived true-stress/true-strain
columns (ADR-0002). If ``metadata.already_true`` is set, the supplied values are
treated as true and the conversion is skipped (no double conversion).
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

import numpy as np
import pandas as pd

from . import schema, units
from .models import TestMetadata


@dataclass
class TestRun:
    """One ingested, normalized test: metadata + per-sample true stress/strain series."""

    __test__: ClassVar[bool] = False  # not a pytest test class

    metadata: TestMetadata
    data: pd.DataFrame  # contains at least strain_true, stress_true

    def __len__(self) -> int:  # number of samples
        return len(self.data)

    @property
    def strain_true(self) -> pd.Series:
        return self.data[schema.COL_STRAIN_TRUE]

    @property
    def stress_true(self) -> pd.Series:
        return self.data[schema.COL_STRESS_TRUE]


def normalize(df: pd.DataFrame, metadata: TestMetadata, *, validate: bool = True) -> pd.DataFrame:
    """Return a copy of ``df`` with derived stress/strain columns added.

    Required raw columns: ``time``, ``strain``, and ``force`` or ``stress_eng``
    (see :mod:`lcf.schema`).

    Stress precedence: if a ``stress_eng`` column is present it is used as-is and
    ``area`` is not required. Otherwise stress is derived as ``force / area``.
    If ``metadata.already_true`` is True, the (engineering-named) strain and stress
    are taken to be *true* values directly and the eng->true conversion is skipped.

    With ``validate=True`` (default), NaN values in the required columns raise, and
    non-monotonic ``time`` emits a warning.
    """
    has_stress = schema.COL_STRESS_ENG in df.columns
    missing = [c for c in (schema.COL_TIME, schema.COL_STRAIN) if c not in df.columns]
    if schema.COL_FORCE not in df.columns and not has_stress:
        missing.append(f"{schema.COL_FORCE} (or {schema.COL_STRESS_ENG})")
    if missing:
        raise ValueError(
            f"raw data missing required column(s): {missing}. "
            f"Expected {schema.REQUIRED_RAW} or stress_eng in place of force."
        )

    required_present = [schema.COL_TIME, schema.COL_STRAIN,
                        schema.COL_STRESS_ENG if has_stress else schema.COL_FORCE]
    if validate:
        nan_cols = [c for c in required_present if df[c].isna().any()]
        if nan_cols:
            raise ValueError(
                f"raw data contains NaN in column(s) {nan_cols}. Clean or drop those "
                "rows with df.dropna() before ingestion, or pass validate=False."
            )
        t = df[schema.COL_TIME].to_numpy()
        if t.size > 1 and np.any(np.diff(t) < 0):
            warnings.warn(
                "time column is not monotonically non-decreasing. Cycle ordering may "
                "be affected.",
                stacklevel=2,
            )

    out = df.copy()

    # Force -> engineering stress (needs area), unless stress already provided.
    if schema.COL_STRESS_ENG not in out.columns:
        if metadata.area is None:
            raise ValueError(
                "metadata.area is required to derive stress from force "
                "(or supply a 'stress_eng' column directly)."
            )
        out[schema.COL_STRESS_ENG] = units.stress_from_force(
            out[schema.COL_FORCE].to_numpy(), metadata.area
        )

    strain_eng = out[schema.COL_STRAIN].to_numpy()
    stress_eng = out[schema.COL_STRESS_ENG].to_numpy()

    if metadata.already_true:
        out[schema.COL_STRAIN_TRUE] = strain_eng
        out[schema.COL_STRESS_TRUE] = stress_eng
    else:
        out[schema.COL_STRAIN_TRUE] = units.eng_to_true_strain(strain_eng)
        out[schema.COL_STRESS_TRUE] = units.eng_to_true_stress(stress_eng, strain_eng)

    return out


def from_dataframe(df: pd.DataFrame, metadata: TestMetadata) -> TestRun:
    """Build a normalized :class:`TestRun` from a raw DataFrame."""
    return TestRun(metadata=metadata, data=normalize(df, metadata))


def from_timeseries(time, strain, force, *, metadata: TestMetadata) -> TestRun:
    """Build a normalized :class:`TestRun` from parallel ``(time, strain, force)`` arrays.

    Mirrors the py-fatigue ``CycleCount.from_timeseries`` constructor shape
    (ADR-0001), adapted to strain-controlled ``(time, strain, force)`` input.
    """
    t = np.asarray(time, dtype="float64")
    e = np.asarray(strain, dtype="float64")
    f = np.asarray(force, dtype="float64")
    if not (t.shape == e.shape == f.shape):
        raise ValueError(
            f"time, strain, force must have equal length. Got {t.shape}, {e.shape}, {f.shape}"
        )
    df = pd.DataFrame(
        {schema.COL_TIME: t, schema.COL_STRAIN: e, schema.COL_FORCE: f}
    )
    return from_dataframe(df, metadata)


def read_csv(
    path: str | Path,
    *,
    metadata: TestMetadata,
    column_map: dict[str, str] | None = None,
    **read_csv_kwargs,
) -> TestRun:
    """Read a delimited file into a normalized :class:`TestRun`.

    Parameters
    ----------
    path : str | Path
        File to read.
    metadata : TestMetadata
        Test scalars (area, E, ...).
    column_map : dict, optional
        Maps source column names -> canonical names (``time``/``strain``/``force``).
        Example: ``{"Time (s)": "time", "Axial Strain": "strain", "Axial Force": "force"}``.
    **read_csv_kwargs
        Passed through to :func:`pandas.read_csv` (e.g. ``sep``, ``skiprows``,
        ``comment``) to handle machine-specific header blocks.
    """
    df = pd.read_csv(path, **read_csv_kwargs)
    if column_map:
        df = df.rename(columns=column_map)
    return from_dataframe(df, metadata)
