"""Pure (non-Streamlit) logic behind the graphical interface.

Everything here is plain Python over the :mod:`lcf` library so it can be unit
tested without a browser. The Streamlit layer in :mod:`lcf.gui.app` only wires
widgets to these functions.
"""

from __future__ import annotations

import io
import json
import tempfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

import lcf
from lcf import datasets, labio
from lcf.models import TestMetadata


class GuiInputError(ValueError):
    """An input problem explained in domain language, safe to show verbatim."""


# --- example dataset ---------------------------------------------------------
# Single source: lcf.datasets. The GUI only names and re-exports it.

EXAMPLE_MATERIAL = "SAE 1137 (example)"
EXAMPLE_E = datasets.SAE1137_E


def example_summary_table() -> pd.DataFrame:
    """Per-test reduced data for the bundled SAE 1137 example."""
    return datasets.sae1137_reduced()


def empty_summary_table() -> pd.DataFrame:
    """An empty fit table with the canonical columns."""
    return pd.DataFrame(
        {
            "test": pd.Series(dtype="object"),
            "total_strain_amp": pd.Series(dtype="float64"),
            "stress_amp": pd.Series(dtype="float64"),
            "reversals": pd.Series(dtype="float64"),
        }
    )


# --- fitting from a reduced-data table --------------------------------------

FIT_COLUMNS = ["total_strain_amp", "stress_amp", "reversals"]


def fit_signature(
    table: pd.DataFrame,
    E: float | None,
    min_plastic_strain: float | None,
    refine_nonlinear: bool,
) -> str:
    """A stable string identifying the inputs of a fit, for staleness checks.

    Two calls return the same string exactly when the fit-relevant inputs (the
    three numeric columns, E, and the two options) are identical. The app uses
    it to tell when a displayed fit no longer matches the edited table and must
    be recomputed, so it never shows constants that disagree with the data.
    """
    present = [c for c in FIT_COLUMNS if c in table.columns]
    sub = table[present].copy()
    for c in present:
        sub[c] = pd.to_numeric(sub[c], errors="coerce")
    records = [
        {c: (None if pd.isna(v) else float(v)) for c, v in zip(present, row)}
        for row in sub.to_numpy().tolist()
    ]
    payload = {
        "data": records,
        "E": None if E is None else float(E),
        "min_plastic_strain": (
            None if min_plastic_strain is None else float(min_plastic_strain)
        ),
        "refine_nonlinear": bool(refine_nonlinear),
    }
    return json.dumps(payload, sort_keys=True)


def fit_from_table(
    table: pd.DataFrame,
    E: float,
    *,
    min_plastic_strain: float | None = None,
    refine_nonlinear: bool = False,
) -> tuple[lcf.StrainLifeFit, list[str]]:
    """Validate a reduced-data table and fit the strain-life models.

    Returns the fit and a list of human-readable warnings. Raises
    :class:`GuiInputError` with a plain-language message on bad input.
    """
    warnings: list[str] = []
    df = table.copy()

    needed = ["total_strain_amp", "stress_amp", "reversals"]
    for col in needed:
        if col not in df.columns:
            raise GuiInputError(f"the data table is missing the '{col}' column")
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=needed)
    if len(df) < 2:
        raise GuiInputError(
            "at least 2 complete rows (strain amplitude, stress amplitude, "
            "reversals) are needed to fit the strain-life models"
        )
    if (df[needed] <= 0).any().any():
        raise GuiInputError(
            "strain amplitude, stress amplitude, and reversals must all be "
            "positive numbers"
        )
    if float(df["total_strain_amp"].max()) > 0.2:
        warnings.append(
            "a strain amplitude above 0.2 was entered: strain must be a "
            "fraction (0.005 = 0.5%), not a percent. Check the values."
        )
    if not np.isfinite(E) or E <= 0:
        raise GuiInputError("the elastic modulus E must be a positive number (MPa)")

    fit = lcf.fit_strain_life(
        df["total_strain_amp"].to_numpy(),
        df["stress_amp"].to_numpy(),
        df["reversals"].to_numpy(),
        float(E),
        min_plastic_strain=min_plastic_strain,
        refine_nonlinear=refine_nonlinear,
    )
    if fit.consistency is not None and not fit.consistency.masing_ok:
        warnings.append(
            "the material departs from Masing behaviour: the independently "
            f"fitted n' = {fit.consistency.n_fitted:.3f} differs from "
            f"b/c = {fit.consistency.n_from_bc:.3f} by "
            f"{fit.consistency.n_rel_diff:.0%}. Both are reported. This is a "
            "property of the data, not an error."
        )
    return fit, warnings


def constants_frame(fit: lcf.StrainLifeFit) -> pd.DataFrame:
    """The fitted constants as a small display/CSV table (units in the name)."""
    rows = [
        ("sigma_f' (MPa)", fit.basquin.sigma_f, "Basquin fatigue strength coefficient"),
        ("b", fit.basquin.b, "Basquin fatigue strength exponent"),
        ("eps_f'", fit.coffin_manson.eps_f, "Coffin-Manson fatigue ductility coefficient"),
        ("c", fit.coffin_manson.c, "Coffin-Manson fatigue ductility exponent"),
        ("E (MPa)", fit.E, "Elastic modulus used for the fit"),
        ("2N_t (reversals)", fit.transition_reversals, "Elastic/plastic transition life"),
    ]
    if fit.ramberg_osgood is not None:
        rows.insert(4, ("K' (MPa)", fit.ramberg_osgood.K, "Cyclic strength coefficient"))
        rows.insert(5, ("n'", fit.ramberg_osgood.n, "Cyclic strain hardening exponent"))
    return pd.DataFrame(rows, columns=["constant", "value", "meaning"])


def estimated_constants_frame(est: "lcf.EstimatedConstants") -> pd.DataFrame:
    """Estimated constants as a display/CSV table."""
    rows = [
        ("sigma_f' (MPa)", est.sigma_f, "Fatigue strength coefficient"),
        ("b", est.b, "Fatigue strength exponent"),
        ("eps_f'", est.eps_f, "Fatigue ductility coefficient"),
        ("c", est.c, "Fatigue ductility exponent"),
    ]
    if est.K is not None:
        rows.append(("K' (MPa)", est.K, "Cyclic strength coefficient"))
    if est.n is not None:
        rows.append(("n'", est.n, "Cyclic strain hardening exponent"))
    return pd.DataFrame(rows, columns=["constant", "value", "meaning"])


# --- raw-file ingestion ------------------------------------------------------

@dataclass
class IngestedTest:
    """One uploaded raw file, ingested and analyzed."""

    filename: str
    run: lcf.TestRun
    analysis: "lcf.TestAnalysis"
    resolution: dict  # how the file's header/units were interpreted


def ingest_raw_file(
    filename: str,
    data: bytes,
    *,
    name: str,
    area: float | None,
    E: float | None,
    R: float = -1.0,
    material: str | None = None,
    already_true: bool = False,
    failure_criterion_pct: float = 50.0,
) -> IngestedTest:
    """Ingest one uploaded lab export and run the single-test analysis.

    The bytes are written to a temporary file so the lab-file reader can
    sniff the delimiter, header row, and units exactly as it does for a file
    on disk. Raises :class:`GuiInputError` with a plain-language message when
    the file cannot be read.
    """
    suffix = Path(filename).suffix or ".csv"
    tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    try:
        tmp.write(data)
        tmp.close()
        try:
            resolution = labio.preview_lab_file(tmp.name)
        except Exception as exc:
            raise GuiInputError(
                f"'{filename}' could not be read as a delimited lab export: {exc}"
            ) from exc
        # The lab reader normalizes a stress column to the canonical role
        # "stress_eng" (see lcf.schema.COL_STRESS_ENG), not "stress".
        cols = resolution.get("columns", {})
        has_stress = "stress_eng" in cols
        if "strain" not in cols:
            raise GuiInputError(
                f"no strain column was recognized in '{filename}'. Columns "
                f"found: {resolution.get('columns')}. Rename the strain column "
                "(e.g. to 'strain') or export with a standard header."
            )
        if "force" not in cols and not has_stress:
            raise GuiInputError(
                f"no force or stress column was recognized in '{filename}'. "
                "The file needs a force (N/kN) or stress (MPa) column."
            )
        if "force" in cols and not has_stress and (area is None or area <= 0):
            raise GuiInputError(
                f"'{filename}' has a force column, so the specimen "
                "cross-sectional area (mm²) is required to compute stress."
            )
        metadata = TestMetadata(
            name=name, area=area, E=E, R=R, material=material,
            already_true=already_true,
        )
        try:
            run = labio.read_lab_file(tmp.name, metadata=metadata)
        except Exception as exc:
            raise GuiInputError(f"'{filename}' could not be ingested: {exc}") from exc
        try:
            params = lcf.AnalysisParams(failure_criterion_pct=failure_criterion_pct)
            analysis = lcf.analyze_test(run, params)
        except Exception as exc:
            raise GuiInputError(
                f"the analysis of '{filename}' failed: {exc}. Check that the "
                "file holds a continuous strain-controlled time series."
            ) from exc
        return IngestedTest(
            filename=filename, run=run, analysis=analysis, resolution=resolution
        )
    finally:
        Path(tmp.name).unlink(missing_ok=True)


def summary_row(a: "lcf.TestAnalysis") -> dict:
    """The half-life quantities of one analyzed test, as a fit-table row."""
    s = a.summary
    return {
        "test": s["name"],
        "total_strain_amp": s["total_strain_amp"],
        "stress_amp": s["stress_amp"],
        "reversals": float(s["reversals"]),
    }


def analyze_uploads(
    files: list[tuple[str, bytes]],
    *,
    area: float | None,
    E: float | None,
    R: float = -1.0,
    material: str | None = None,
    already_true: bool = False,
    failure_criterion_pct: float = 50.0,
) -> tuple[list[IngestedTest], list[tuple[str, str]]]:
    """Analyze a batch of uploaded files, reporting the true per-batch outcome.

    ``files`` is a list of ``(filename, data_bytes)``. Each file is ingested
    independently. Returns ``(successes, errors)`` where ``errors`` is a list of
    ``(filename, message)``, so the caller can report how many files in *this*
    batch actually analyzed instead of a running total.
    """
    ok: list[IngestedTest] = []
    errors: list[tuple[str, str]] = []
    for filename, data in files:
        name = filename.rsplit(".", 1)[0]
        try:
            ing = ingest_raw_file(
                filename, data, name=name, area=area, E=E, R=R,
                material=material, already_true=already_true,
                failure_criterion_pct=failure_criterion_pct,
            )
        except GuiInputError as exc:
            errors.append((filename, str(exc)))
            continue
        ok.append(ing)
    return ok, errors


def drop_test_row(table: pd.DataFrame, test_name: str) -> pd.DataFrame:
    """Return the fit table without the row whose ``test`` equals test_name."""
    if "test" not in table.columns:
        return table
    return table[table["test"] != test_name].reset_index(drop=True)


# --- prediction --------------------------------------------------------------

def select_source(
    have_fit: bool, have_estimate: bool, prefer: str | None = None
) -> str | None:
    """Choose which constants source to predict with.

    Honors an explicit ``prefer`` of ``fit`` or ``estimate`` when that source is
    available, otherwise falls back to the fit, then the estimate, then None.
    This lets a user with both a fit and an estimate pick either one, instead of
    the fit permanently shadowing the estimate.
    """
    if prefer == "estimate" and have_estimate:
        return "estimate"
    if prefer == "fit" and have_fit:
        return "fit"
    if have_fit:
        return "fit"
    if have_estimate:
        return "estimate"
    return None


def predict_life(
    constants: dict,
    total_strain_amp: float,
    *,
    correction: str = "none",
    mean_stress: float = 0.0,
    stress_amp: float | None = None,
) -> dict:
    """Predict reversals/cycles to failure for one strain amplitude.

    ``constants`` needs sigma_f, b, eps_f, c, E. ``correction`` is ``none``,
    ``morrow`` (uses ``mean_stress``), or ``swt`` (uses ``stress_amp`` and
    ``mean_stress`` to form the peak stress).
    """
    if not np.isfinite(total_strain_amp) or total_strain_amp <= 0:
        raise GuiInputError("the strain amplitude must be a positive number")
    sf, b = constants["sigma_f"], constants["b"]
    ef, c = constants["eps_f"], constants["c"]
    E = constants["E"]
    try:
        if correction == "none":
            two_nf = lcf.predict_reversals_from_total_strain(
                total_strain_amp, sf, b, ef, c, E
            )
        elif correction == "morrow":
            from lcf.life import predict_reversals_morrow

            two_nf = predict_reversals_morrow(
                total_strain_amp, mean_stress, sf, b, ef, c, E
            )
        elif correction == "swt":
            from lcf.life import predict_reversals_swt

            if stress_amp is None or stress_amp <= 0:
                raise GuiInputError(
                    "the SWT correction needs the stress amplitude of the "
                    "cycle (MPa) to form the peak stress"
                )
            two_nf = predict_reversals_swt(
                stress_amp + mean_stress, total_strain_amp, sf, b, ef, c, E
            )
        else:
            raise GuiInputError(f"unknown mean-stress correction '{correction}'")
    except GuiInputError:
        raise
    except Exception as exc:
        raise GuiInputError(
            f"no life could be solved for this amplitude: {exc}. The amplitude "
            "may be outside the range where the fitted curve is decreasing."
        ) from exc
    return {"reversals": float(two_nf), "cycles": float(two_nf) / 2.0}


# --- exports -----------------------------------------------------------------

def fig_png_bytes(fig) -> bytes:
    """Render a matplotlib Figure to PNG bytes for download."""
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    return buf.getvalue()


def format_value(v) -> str:
    """Format one cell value for display. Non-finite numbers read plainly.

    A degenerate fit can produce an infinite or NaN constant. Rendering it as a
    bare ``inf`` or ``nan`` reads like a software bug, so it is shown as
    ``not finite`` instead, both on screen and in exports.
    """
    if isinstance(v, bool):
        return str(v)
    if isinstance(v, (int, float, np.integer, np.floating)):
        f = float(v)
        return f"{f:.6g}" if np.isfinite(f) else "not finite"
    return str(v)


def _md_escape(text: str) -> str:
    """Escape characters that would break a markdown table cell."""
    return text.replace("\\", "\\\\").replace("|", "\\|").replace("\n", " ")


def _md_table(df: pd.DataFrame) -> str:
    """A GitHub pipe table, without the optional tabulate dependency."""
    cols = [_md_escape(str(c)) for c in df.columns]
    lines = ["| " + " | ".join(cols) + " |",
             "| " + " | ".join("---" for _ in cols) + " |"]
    for _, row in df.iterrows():
        cells = [_md_escape(format_value(row[c])) for c in df.columns]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def _has_nonfinite(df: pd.DataFrame) -> bool:
    """True if the frame's ``value`` column holds any non-finite number."""
    if "value" not in df.columns:
        return False
    vals = pd.to_numeric(df["value"], errors="coerce").to_numpy(dtype=float)
    return bool((~np.isfinite(vals)).any())


def build_report_markdown(
    *,
    material: str,
    constants: pd.DataFrame,
    summary_table: pd.DataFrame | None,
    warnings: list[str],
    source: str,
) -> str:
    """A small self-contained markdown report of the fitted constants."""
    lines = [
        f"# Strain-life analysis report: {material}",
        "",
        f"Produced with lcf-strain-life {lcf.__version__} (graphical interface).",
        f"Constants source: {source}.",
        "Conventions: true stress/strain, stress in MPa, strain as a fraction, "
        "exponents b and c negative.",
        "",
        "## Fitted constants",
        "",
        _md_table(constants),
        "",
    ]
    if summary_table is not None and len(summary_table):
        lines += [
            "## Per-test reduced data (half-life)",
            "",
            _md_table(summary_table),
            "",
        ]
    notes = list(warnings)
    if _has_nonfinite(constants):
        notes.append(
            "One or more constants above are not finite, which indicates a "
            "degenerate fit (too few points, or points too close to collinear). "
            "Treat these results as unreliable."
        )
    if notes:
        lines += ["## Notes", ""]
        lines += [f"- {w}" for w in notes]
        lines += [""]
    return "\n".join(lines)
