"""Canonical data schema — column names for the normalized per-sample series.

The internal time-series form is a :class:`pandas.DataFrame` with the columns
below. Raw columns (``time``, ``strain``, ``force``) come from the test machine;
the ``*_true`` / ``stress_*`` columns are derived at ingestion (see
:mod:`lcf.ingest`). Naming mirrors the pyLife / py-fatigue ecosystem where it
overlaps (ADR-0001, docs/design/WORKFLOW.md).
"""

from __future__ import annotations

# Raw (as supplied)
COL_TIME = "time"            # s
COL_STRAIN = "strain"        # engineering strain (mm/mm) as supplied
COL_FORCE = "force"          # N

# Derived at ingestion
COL_STRESS_ENG = "stress_eng"    # MPa = force / area
COL_STRAIN_TRUE = "strain_true"  # ln(1 + strain)
COL_STRESS_TRUE = "stress_true"  # stress_eng * (1 + strain)

# Optional
COL_TEMPERATURE = "temperature"  # degC
COL_CYCLE_INDEX = "cycle_index"  # int, assigned by cycle reduction

#: Columns that must be present in a raw input frame.
REQUIRED_RAW = (COL_TIME, COL_STRAIN, COL_FORCE)

#: Columns produced by :func:`lcf.ingest.normalize`.
DERIVED = (COL_STRESS_ENG, COL_STRAIN_TRUE, COL_STRESS_TRUE)

#: All recognized columns, in canonical order.
ALL_COLUMNS = (
    COL_TIME,
    COL_STRAIN,
    COL_FORCE,
    COL_STRESS_ENG,
    COL_STRAIN_TRUE,
    COL_STRESS_TRUE,
    COL_TEMPERATURE,
    COL_CYCLE_INDEX,
)
