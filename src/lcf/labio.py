"""Lab-export reading and batch series ingestion (ADR-0014, P1).

Entry points:

* :func:`read_lab_file`:    one delimited lab export -> normalized :class:`TestRun`.
* :func:`preview_lab_file`: how a file would be read, without analyzing it.
* :func:`read_series`:      a directory or file list -> runs plus collected errors.

The reader handles the delimited export shapes that strain-controlled fatigue
labs actually produce (MTS TestSuite and Instron style exports among others):
a preamble block before the header, unit suffixes in the header, percent
strain, kN force, a units row under the header, and semicolon-delimited files
with decimal commas. Column names are resolved through a synonym table.

The reader refuses rather than guesses. Ambiguous or unresolvable headers
raise with the found names, and an unmarked strain column at percent scale
raises and names the ``strain_unit`` override. Explicit ``column_map`` and
unit overrides always win over auto-detection.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from . import schema
from .ingest import TestRun, from_dataframe
from .models import TestMetadata

__all__ = [
    "ColumnResolution",
    "SeriesIngest",
    "preview_lab_file",
    "read_fde_history",
    "read_lab_file",
    "read_series",
]

#: Canonical roles the reader can fill. ``stress_eng`` substitutes for force.
_ROLES = (schema.COL_TIME, schema.COL_STRAIN, schema.COL_FORCE, schema.COL_STRESS_ENG,
          schema.COL_TEMPERATURE)

_SYNONYMS: dict[str, tuple[str, ...]] = {
    schema.COL_TIME: (
        "time", "elapsed time", "running time", "test time", "total time",
        "time stamp", "zeit",
    ),
    schema.COL_STRAIN: (
        "strain", "axial strain", "strain 1", "eng strain", "engineering strain",
        "extensometer strain", "extensometer", "dehnung",
    ),
    schema.COL_FORCE: (
        "force", "load", "axial force", "axial load", "kraft",
    ),
    schema.COL_STRESS_ENG: (
        "stress", "axial stress", "eng stress", "engineering stress", "spannung",
    ),
    schema.COL_TEMPERATURE: ("temperature", "temp"),
}

_STRAIN_FACTORS = {
    "": 1.0, "-": 1.0, "mm/mm": 1.0, "m/m": 1.0, "in/in": 1.0, "fraction": 1.0,
    "%": 0.01, "percent": 0.01, "pct": 0.01,
}
_FORCE_FACTORS = {"": 1.0, "n": 1.0, "kn": 1000.0, "lbf": 4.4482216153}
_STRESS_FACTORS = {
    "": 1.0, "mpa": 1.0, "n/mm^2": 1.0, "n/mm2": 1.0,
    "ksi": 6.894757, "psi": 0.006894757,
}
_TIME_FACTORS = {"": 1.0, "s": 1.0, "sec": 1.0, "seconds": 1.0, "ms": 0.001, "min": 60.0}

_UNIT_FACTORS = {
    schema.COL_TIME: _TIME_FACTORS,
    schema.COL_STRAIN: _STRAIN_FACTORS,
    schema.COL_FORCE: _FORCE_FACTORS,
    schema.COL_STRESS_ENG: _STRESS_FACTORS,
    schema.COL_TEMPERATURE: {"": 1.0, "c": 1.0, "degc": 1.0, "deg c": 1.0},
}

#: Unmarked strain above this magnitude is probably percent (ADR-0014).
_PERCENT_SUSPECT = 0.2

_DELIMITERS = (",", ";", "\t")
_UNIT_RE = re.compile(r"[\(\[]([^)\]]*)[\)\]]\s*$")
_MAX_SCAN_LINES = 200


@dataclass
class ColumnResolution:
    """How a file's header was interpreted."""

    header_row: int                      # 0-based line index of the header
    delimiter: str
    decimal: str
    columns: dict[str, str]              # canonical role -> source column name
    units: dict[str, str]                # canonical role -> unit string found
    conversions: dict[str, float]        # canonical role -> factor applied
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "header_row": self.header_row,
            "delimiter": self.delimiter,
            "decimal": self.decimal,
            "columns": dict(self.columns),
            "units": dict(self.units),
            "conversions": dict(self.conversions),
            "notes": list(self.notes),
        }


@dataclass
class SeriesIngest:
    """Result of a batch read: the runs that loaded and the files that did not."""

    runs: list[TestRun]
    paths: list[str]                     # source path per run, parallel to runs
    resolutions: list[dict]              # per run, ColumnResolution.to_dict()
    errors: list[dict]                   # {"file": path, "error": message}


def _split_header(raw: str) -> tuple[str, str]:
    """Normalize one header cell into (base name, unit string)."""
    txt = str(raw).strip().strip('"').strip()
    unit = ""
    m = _UNIT_RE.search(txt)
    if m:
        unit = m.group(1).strip().lower()
        txt = txt[: m.start()].strip()
    base = re.sub(r"[\s_]+", " ", txt).strip().lower()
    return base, unit


def _resolve_headers(
    headers: list[str], column_map: dict[str, str] | None
) -> tuple[dict[str, str], dict[str, str], list[str]]:
    """Map raw headers to canonical roles.

    Returns (columns, units, ambiguities): canonical role -> source name,
    canonical role -> unit string, and a list of ambiguity messages.
    """
    column_map = column_map or {}
    columns: dict[str, str] = {}
    units: dict[str, str] = {}
    ambiguous: list[str] = []
    candidates: dict[str, list[str]] = {role: [] for role in _ROLES}

    for raw in headers:
        base, unit = _split_header(raw)
        mapped = column_map.get(str(raw).strip())
        if mapped is not None:
            role = schema.COL_STRESS_ENG if mapped == "stress" else mapped
            if role in _ROLES:
                candidates[role].append(raw)
                units[role] = unit
            continue
        for role, names in _SYNONYMS.items():
            if base in names:
                candidates[role].append(raw)
                if len(candidates[role]) == 1:
                    units[role] = unit
                break

    for role, found in candidates.items():
        if len(found) == 1:
            columns[role] = str(found[0])
        elif len(found) > 1:
            ambiguous.append(
                f"{role}: {found}"
            )
    return columns, units, ambiguous


def _sniff(text_lines: list[str], column_map: dict[str, str] | None):
    """Find (header_row, delimiter, columns, units, ambiguities).

    The header is the first line that resolves at least two canonical roles
    under some delimiter. Preamble lines (titles, ``key: value`` pairs, blank
    lines) do not resolve two roles and are skipped naturally.
    """
    best = None
    for i, line in enumerate(text_lines):
        if not line.strip():
            continue
        for delim in _DELIMITERS:
            tokens = [t for t in line.rstrip("\r\n").split(delim)]
            if len(tokens) < 2:
                continue
            columns, units, ambiguous = _resolve_headers(tokens, column_map)
            score = len(columns) + len(ambiguous)
            if score >= 2:
                cand = (i, delim, columns, units, ambiguous, score, len(tokens))
                if best is None or (cand[0] == best[0] and (cand[5], cand[6]) > (best[5], best[6])):
                    best = cand
        if best is not None and best[0] == i:
            return best[:5]
    return None


def _load(
    path: str | Path,
    *,
    column_map: dict[str, str] | None = None,
    delimiter: str | None = None,
    decimal: str | None = None,
    strain_unit: str | None = None,
    force_unit: str | None = None,
    stress_unit: str | None = None,
    strict: bool = True,
) -> tuple[pd.DataFrame, ColumnResolution]:
    """Parse one delimited lab export into a canonical raw DataFrame."""
    path = Path(path)
    with open(path, encoding="utf-8-sig", errors="replace") as fh:
        head = [next(fh, "") for _ in range(_MAX_SCAN_LINES)]

    sniffed = _sniff(head, column_map)
    if sniffed is None:
        first = ", ".join(repr(t.strip()) for t in head[0].rstrip("\r\n").split(",")) if head else ""
        raise ValueError(
            f"{path.name}: could not locate a header row. No line resolves two or "
            f"more of time/strain/force/stress through the known column names. "
            f"First line: {first}. Pass column_map to name the columns explicitly."
        )
    header_row, delim, columns, units, ambiguous = sniffed
    if delimiter is not None:
        delim = delimiter
    if ambiguous:
        raise ValueError(
            f"{path.name}: ambiguous column resolution, {'; '.join(ambiguous)}. "
            "Pass column_map to pick the intended columns."
        )

    have_force = schema.COL_FORCE in columns
    have_stress = schema.COL_STRESS_ENG in columns
    missing = [r for r in (schema.COL_TIME, schema.COL_STRAIN) if r not in columns]
    if not have_force and not have_stress:
        missing.append("force or stress")
    if missing:
        raise ValueError(
            f"{path.name}: could not resolve required column(s) {missing} from the "
            f"header {head[header_row].strip()!r}. Pass column_map."
        )

    if decimal is None:
        decimal = "."
        if delim == ";":
            sample = "\n".join(head[header_row + 1: header_row + 5])
            if re.search(r"\d,\d", sample) and not re.search(r"\d\.\d", sample):
                decimal = ","

    df = pd.read_csv(
        path, sep=delim, skiprows=header_row, decimal=decimal,
        encoding="utf-8-sig", skip_blank_lines=True, engine="python",
    )
    df.columns = [str(c).strip() for c in df.columns]

    notes: list[str] = []
    rename = {src: role for role, src in columns.items()}
    df = df.rename(columns={k.strip(): v for k, v in rename.items()})
    keep = [r for r in _ROLES if r in df.columns]
    df = df[keep]

    for col in keep:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    required_cols = [schema.COL_TIME, schema.COL_STRAIN,
                     schema.COL_STRESS_ENG if (have_stress and not have_force) else schema.COL_FORCE]
    all_nan = df[required_cols].isna().all(axis=1)
    leading = 0
    while leading < len(df) and all_nan.iloc[leading]:
        leading += 1
    trailing = 0
    while trailing < len(df) - leading and all_nan.iloc[len(df) - 1 - trailing]:
        trailing += 1
    if leading or trailing:
        df = df.iloc[leading: len(df) - trailing].reset_index(drop=True)
        notes.append(
            f"dropped {leading + trailing} non-numeric row(s) (units row or blank tail)"
        )

    overrides = {
        schema.COL_STRAIN: strain_unit,
        schema.COL_FORCE: force_unit,
        schema.COL_STRESS_ENG: stress_unit,
    }
    conversions: dict[str, float] = {}
    for role in keep:
        factors = _UNIT_FACTORS[role]
        override = overrides.get(role)
        unit = (override if override is not None else units.get(role, "")).strip().lower()
        if unit not in factors:
            raise ValueError(
                f"{path.name}: unit {unit!r} on column {columns.get(role, role)!r} is not "
                f"supported for {role}. Supported: {sorted(u for u in factors if u)}."
            )
        factor = factors[unit]
        if factor != 1.0:
            df[role] = df[role] * factor
            notes.append(f"{role}: converted {unit!r} by factor {factor:g}")
        conversions[role] = factor
        if override is not None:
            units[role] = unit

    unmarked = not units.get(schema.COL_STRAIN, "") and overrides[schema.COL_STRAIN] is None
    if unmarked and len(df):
        max_abs = float(df[schema.COL_STRAIN].abs().max())
        if max_abs > _PERCENT_SUSPECT:
            msg = (
                f"{path.name}: strain column {columns[schema.COL_STRAIN]!r} carries no "
                f"unit and reaches {max_abs:g}, which is probably percent, not a "
                f"fraction. Pass strain_unit='percent' to convert, or "
                f"strain_unit='fraction' to keep the values as they are."
            )
            if strict:
                raise ValueError(msg)
            notes.append(msg)

    resolution = ColumnResolution(
        header_row=header_row, delimiter=delim, decimal=decimal,
        columns={r: columns[r] for r in columns}, units={r: units.get(r, "") for r in columns},
        conversions=conversions, notes=notes,
    )
    return df, resolution


def read_lab_file(
    path: str | Path,
    *,
    metadata: TestMetadata,
    column_map: dict[str, str] | None = None,
    delimiter: str | None = None,
    decimal: str | None = None,
    strain_unit: str | None = None,
    force_unit: str | None = None,
    stress_unit: str | None = None,
) -> TestRun:
    """Read one delimited lab export into a normalized :class:`TestRun`.

    Auto-detects the delimiter and the header row, resolves columns through
    the synonym table, and converts units declared in header suffixes
    (percent strain, kN force, ksi stress). ``column_map`` maps source column
    names to ``time``/``strain``/``force``/``stress`` and overrides the
    synonyms. The unit overrides win over header suffixes.
    """
    df, _ = _load(
        path, column_map=column_map, delimiter=delimiter, decimal=decimal,
        strain_unit=strain_unit, force_unit=force_unit, stress_unit=stress_unit,
        strict=True,
    )
    return from_dataframe(df, metadata)


def preview_lab_file(
    path: str | Path,
    *,
    column_map: dict[str, str] | None = None,
    delimiter: str | None = None,
    decimal: str | None = None,
) -> dict:
    """Report how a lab export would be read, without analyzing it.

    Returns the header row, delimiter, resolved columns with their units and
    conversion factors, the parsed row count, and any notes. A percent-suspect
    strain column is reported as a note here instead of raising.
    """
    df, resolution = _load(
        path, column_map=column_map, delimiter=delimiter, decimal=decimal, strict=False
    )
    out = resolution.to_dict()
    out["file"] = str(path)
    out["n_rows"] = int(len(df))
    return out


def read_fde_history(source: str | Path) -> list[float]:
    """Read an SAE FD and E committee load-history file into a value list.

    The format, as published at fde.uwaterloo.ca: ``#`` comment lines
    (including the GPL license header), one value per line, with occasional
    progress markers of the form ``-112 : 1500`` whose part before the colon
    is the value. ``source`` is a file path, or the file's text content when
    it contains newlines (so a runtime download can be passed directly).
    The license header of the file itself is not altered by reading it,
    redistribute the files under their own terms.
    """
    text = str(source)
    if "\n" not in text:
        text = Path(source).read_text(encoding="utf-8", errors="replace")
    values: list[float] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        token = line.split(":")[0].strip()
        try:
            values.append(float(token))
        except ValueError:
            raise ValueError(
                f"line {lineno} is not a value or marker: {line!r}. "
                "Expected the FD&E format: # comments, one value per line, "
                "optional 'value : index' markers."
            )
    if not values:
        raise ValueError("no data values found, is this an FD&E history file?")
    return values


def read_series(
    directory: str | Path | None = None,
    *,
    files: list[str | Path] | None = None,
    pattern: str = "*.csv",
    metadata_defaults: dict | None = None,
    per_test_metadata: dict[str, dict] | None = None,
    column_map: dict[str, str] | None = None,
    delimiter: str | None = None,
    decimal: str | None = None,
    strain_unit: str | None = None,
    force_unit: str | None = None,
    stress_unit: str | None = None,
) -> SeriesIngest:
    """Read every export of a test series, collecting failures per file.

    ``directory`` is globbed with ``pattern`` (sorted), ``files`` adds explicit
    paths. Each test's name defaults to its file stem. ``metadata_defaults``
    seeds every :class:`TestMetadata`, ``per_test_metadata`` overrides fields
    per file stem. One unreadable file lands in ``errors`` and does not stop
    the rest of the series.
    """
    for role, override in ((schema.COL_STRAIN, strain_unit),
                           (schema.COL_FORCE, force_unit),
                           (schema.COL_STRESS_ENG, stress_unit)):
        factors = _UNIT_FACTORS[role]
        if override is not None and override.strip().lower() not in factors:
            raise ValueError(
                f"unit override {override!r} is not supported for {role}. "
                f"Supported: {sorted(u for u in factors if u)}."
            )

    paths: list[Path] = []
    if directory is not None:
        paths.extend(sorted(Path(directory).glob(pattern)))
    if files:
        paths.extend(Path(f) for f in files)
    if not paths:
        raise ValueError(
            f"no input files found (directory={directory!r}, pattern={pattern!r}, "
            f"files={files!r})"
        )

    defaults = dict(metadata_defaults or {})
    overrides = per_test_metadata or {}
    runs: list[TestRun] = []
    kept_paths: list[str] = []
    resolutions: list[dict] = []
    errors: list[dict] = []
    for p in paths:
        try:
            fields = dict(defaults)
            fields.update(overrides.get(p.stem, {}))
            fields.setdefault("name", p.stem)
            meta = TestMetadata(**fields)
            df, resolution = _load(
                p, column_map=column_map, delimiter=delimiter, decimal=decimal,
                strain_unit=strain_unit, force_unit=force_unit,
                stress_unit=stress_unit, strict=True,
            )
            runs.append(from_dataframe(df, meta))
            kept_paths.append(str(p))
            resolutions.append({"file": str(p), **resolution.to_dict()})
        except Exception as exc:  # noqa: BLE001 - reported, not swallowed
            errors.append({"file": str(p), "error": str(exc)})
    return SeriesIngest(runs=runs, paths=kept_paths, resolutions=resolutions, errors=errors)
