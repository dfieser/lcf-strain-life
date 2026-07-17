"""Tests for the graphical interface: pure logic plus a headless app run.

The core logic in lcf.gui.core is tested directly. The Streamlit layer is
exercised headlessly with streamlit.testing.v1.AppTest, which runs the real
app script without a browser.
"""

from __future__ import annotations

import io
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("streamlit")

import lcf
from lcf.gui import core

APP_PATH = str(Path(__file__).resolve().parents[1] / "src" / "lcf" / "gui" / "app.py")


# --------------------------------------------------------------------------- #
# core: fitting from a table
# --------------------------------------------------------------------------- #
def test_fit_from_table_matches_library_golden(sae1137):
    table = core.example_summary_table()
    fit, warnings = core.fit_from_table(
        table, core.EXAMPLE_E, min_plastic_strain=5e-4
    )
    direct = lcf.fit_strain_life(
        sae1137.total_strain_amp, sae1137.stress_amp, sae1137.reversals,
        sae1137.ref["E_nominal"], min_plastic_strain=5e-4,
    )
    assert fit.basquin.sigma_f == pytest.approx(direct.basquin.sigma_f)
    assert fit.basquin.b == pytest.approx(direct.basquin.b)
    assert fit.coffin_manson.eps_f == pytest.approx(direct.coffin_manson.eps_f)
    assert fit.coffin_manson.c == pytest.approx(direct.coffin_manson.c)
    assert fit.basquin.b < 0 and fit.coffin_manson.c < 0


def test_fit_from_table_needs_two_rows():
    table = core.example_summary_table().head(1)
    with pytest.raises(core.GuiInputError, match="at least 2"):
        core.fit_from_table(table, core.EXAMPLE_E)


def test_fit_from_table_missing_column():
    table = core.example_summary_table().drop(columns=["stress_amp"])
    with pytest.raises(core.GuiInputError, match="stress_amp"):
        core.fit_from_table(table, core.EXAMPLE_E)


def test_fit_from_table_rejects_nonpositive():
    table = core.example_summary_table()
    table.loc[0, "stress_amp"] = -5.0
    with pytest.raises(core.GuiInputError, match="positive"):
        core.fit_from_table(table, core.EXAMPLE_E)


def test_fit_from_table_ignores_incomplete_rows():
    table = pd.concat(
        [core.example_summary_table(),
         pd.DataFrame([{"test": "blank", "total_strain_amp": None,
                        "stress_amp": None, "reversals": None}])],
        ignore_index=True,
    )
    fit, _ = core.fit_from_table(table, core.EXAMPLE_E, min_plastic_strain=5e-4)
    assert np.isfinite(fit.basquin.sigma_f)


def test_fit_from_table_percent_strain_warning():
    table = core.example_summary_table()
    table["total_strain_amp"] = table["total_strain_amp"] * 100.0  # percent
    fit, warnings = core.fit_from_table(table, core.EXAMPLE_E)
    assert any("percent" in w for w in warnings)


def test_fit_from_table_bad_modulus():
    with pytest.raises(core.GuiInputError, match="modulus"):
        core.fit_from_table(core.example_summary_table(), 0.0)


# --------------------------------------------------------------------------- #
# core: prediction
# --------------------------------------------------------------------------- #
@pytest.fixture()
def sae1137_constants(sae1137):
    fit = lcf.fit_strain_life(
        sae1137.total_strain_amp, sae1137.stress_amp, sae1137.reversals,
        sae1137.ref["E_nominal"], min_plastic_strain=5e-4,
    )
    return {
        "sigma_f": fit.basquin.sigma_f, "b": fit.basquin.b,
        "eps_f": fit.coffin_manson.eps_f, "c": fit.coffin_manson.c,
        "E": fit.E,
    }, fit


def test_predict_life_matches_library(sae1137_constants):
    constants, fit = sae1137_constants
    res = core.predict_life(constants, 0.004)
    assert res["reversals"] == pytest.approx(lcf.predict_reversals(fit, 0.004))
    assert res["cycles"] == pytest.approx(res["reversals"] / 2.0)


def test_predict_life_morrow_reduces_life(sae1137_constants):
    constants, _ = sae1137_constants
    base = core.predict_life(constants, 0.004)
    corrected = core.predict_life(
        constants, 0.004, correction="morrow", mean_stress=100.0
    )
    assert corrected["reversals"] < base["reversals"]


def test_predict_life_swt_needs_stress_amp(sae1137_constants):
    constants, _ = sae1137_constants
    with pytest.raises(core.GuiInputError, match="stress amplitude"):
        core.predict_life(constants, 0.004, correction="swt", mean_stress=50.0)


def test_predict_life_rejects_bad_amplitude(sae1137_constants):
    constants, _ = sae1137_constants
    with pytest.raises(core.GuiInputError, match="positive"):
        core.predict_life(constants, -1.0)


# --------------------------------------------------------------------------- #
# core: raw-file ingestion
# --------------------------------------------------------------------------- #
def _machine_csv_bytes(synthetic_cyclic) -> bytes:
    buf = io.StringIO()
    buf.write("Time (s),Axial Strain (mm/mm),Axial Force (N)\n")
    for t, e, f in zip(synthetic_cyclic.time, synthetic_cyclic.strain,
                       synthetic_cyclic.force):
        buf.write(f"{t:.6f},{e:.6e},{f:.3f}\n")
    return buf.getvalue().encode()


def test_ingest_raw_file_end_to_end(synthetic_cyclic):
    ing = core.ingest_raw_file(
        "TEST-1.csv", _machine_csv_bytes(synthetic_cyclic),
        name="TEST-1", area=synthetic_cyclic.area, E=200000.0,
    )
    s = ing.analysis.summary
    assert s["n_cycles"] == synthetic_cyclic.n_cycles
    assert s["stress_amp"] == pytest.approx(synthetic_cyclic.stress_amp, rel=0.05)
    row = core.summary_row(ing.analysis)
    assert set(row) == {"test", "total_strain_amp", "stress_amp", "reversals"}


def _machine_csv_stress_bytes(synthetic_cyclic) -> bytes:
    """A machine export carrying a stress column and no force column."""
    buf = io.StringIO()
    buf.write("Time (s),Axial Strain (mm/mm),Axial Stress (MPa)\n")
    for t, e, f in zip(synthetic_cyclic.time, synthetic_cyclic.strain,
                       synthetic_cyclic.force):
        buf.write(f"{t:.6f},{e:.6e},{f / synthetic_cyclic.area:.5f}\n")
    return buf.getvalue().encode()


def test_ingest_raw_file_stress_column_no_force(synthetic_cyclic):
    # regression: a stress-only file normalizes to the canonical role
    # 'stress_eng', which the ingest guard must accept without an area.
    ing = core.ingest_raw_file(
        "STRESS-1.csv", _machine_csv_stress_bytes(synthetic_cyclic),
        name="STRESS-1", area=None, E=200000.0,
    )
    s = ing.analysis.summary
    assert s["stress_amp"] == pytest.approx(synthetic_cyclic.stress_amp, rel=0.05)
    assert "stress_eng" in ing.resolution.get("columns", {})


def test_ingest_raw_file_bad_file_is_domain_error():
    with pytest.raises(core.GuiInputError):
        core.ingest_raw_file(
            "junk.csv", b"this is not a data file at all\n",
            name="junk", area=10.0, E=200000.0,
        )


def test_ingest_raw_file_force_needs_area(synthetic_cyclic):
    with pytest.raises(core.GuiInputError, match="area"):
        core.ingest_raw_file(
            "TEST-1.csv", _machine_csv_bytes(synthetic_cyclic),
            name="TEST-1", area=None, E=200000.0,
        )


# --------------------------------------------------------------------------- #
# core: report and exports
# --------------------------------------------------------------------------- #
def test_report_markdown_contains_constants(sae1137_constants):
    _, fit = sae1137_constants
    md = core.build_report_markdown(
        material="SAE 1137",
        constants=core.constants_frame(fit),
        summary_table=core.example_summary_table(),
        warnings=["a note"],
        source="fitted from test data",
    )
    assert "SAE 1137" in md
    assert "sigma_f" in md
    assert "a note" in md
    assert lcf.__version__ in md


def test_fig_png_bytes(sae1137_constants):
    from lcf import plots

    _, fit = sae1137_constants
    png = core.fig_png_bytes(plots.plot_strain_life(fit))
    assert png[:8] == b"\x89PNG\r\n\x1a\n"


# --------------------------------------------------------------------------- #
# launcher: first-run credentials bootstrap
# --------------------------------------------------------------------------- #
def test_credentials_bootstrap_writes_once(tmp_path, monkeypatch):
    import lcf.gui as gui

    monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))
    cred = tmp_path / ".streamlit" / "credentials.toml"

    gui.ensure_streamlit_credentials()
    assert cred.exists()
    assert 'email = ""' in cred.read_text(encoding="utf-8")

    # an existing file, for example a real user's, is never overwritten
    cred.write_text("[general]\nemail = \"someone@lab.example\"\n", encoding="utf-8")
    gui.ensure_streamlit_credentials()
    assert "someone@lab.example" in cred.read_text(encoding="utf-8")


def test_should_bootstrap_credentials_frozen_only(monkeypatch):
    # finding 6: pip installs must not silently write the user's global
    # ~/.streamlit; only the frozen desktop build bootstraps credentials.
    import sys

    import lcf.gui as gui

    monkeypatch.delattr(sys, "frozen", raising=False)
    assert gui.should_bootstrap_credentials() is False
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    assert gui.should_bootstrap_credentials() is True


# --------------------------------------------------------------------------- #
# core helpers behind the review fixes
# --------------------------------------------------------------------------- #
def test_fit_signature_stable_and_sensitive():
    # finding 1: the signature must change when any fit-relevant input changes,
    # so the app can drop a stale fit.
    tbl = core.example_summary_table()
    base = core.fit_signature(tbl, 208000.0, 5e-4, False)
    assert base == core.fit_signature(tbl.copy(), 208000.0, 5e-4, False)

    changed_data = tbl.copy()
    changed_data.loc[0, "stress_amp"] = 999.0
    assert core.fit_signature(changed_data, 208000.0, 5e-4, False) != base
    assert core.fit_signature(tbl, 210000.0, 5e-4, False) != base
    assert core.fit_signature(tbl, 208000.0, 1e-3, False) != base
    assert core.fit_signature(tbl, 208000.0, 5e-4, True) != base
    # a non-fit column (test name) must not affect the signature
    renamed = tbl.copy()
    renamed.loc[0, "test"] = "renamed"
    assert core.fit_signature(renamed, 208000.0, 5e-4, False) == base


def test_analyze_uploads_reports_batch_outcome(synthetic_cyclic):
    # finding 3: the batch result must reflect this batch, not a running total.
    good = _machine_csv_bytes(synthetic_cyclic)
    files = [("good.csv", good), ("bad.csv", b"not a data file\n")]
    ok, errors = core.analyze_uploads(
        files, area=synthetic_cyclic.area, E=200000.0,
    )
    assert len(ok) == 1 and ok[0].filename == "good.csv"
    assert len(errors) == 1 and errors[0][0] == "bad.csv"

    # all-bad batch yields zero successes, so the app shows no false success
    none_ok, all_err = core.analyze_uploads(
        [("bad.csv", b"junk\n")], area=1.0, E=1.0,
    )
    assert none_ok == [] and len(all_err) == 1


def test_drop_test_row():
    # finding 4: removing a test must drop exactly its row.
    tbl = core.example_summary_table()
    n = len(tbl)
    out = core.drop_test_row(tbl, "SAE1137-3")
    assert len(out) == n - 1
    assert "SAE1137-3" not in set(out["test"])
    # dropping a non-existent name is a no-op, and a table without a test
    # column is returned unchanged
    assert len(core.drop_test_row(tbl, "nope")) == n
    assert core.drop_test_row(pd.DataFrame({"x": [1]}), "a").equals(pd.DataFrame({"x": [1]}))


def test_select_source_prefers_and_falls_back():
    # finding 2: an explicit preference must win, with sane fallbacks.
    assert core.select_source(True, True, "estimate") == "estimate"
    assert core.select_source(True, True, "fit") == "fit"
    assert core.select_source(True, True, None) == "fit"
    assert core.select_source(False, True, "fit") == "estimate"   # prefer missing
    assert core.select_source(True, False, "estimate") == "fit"   # prefer missing
    assert core.select_source(False, False, None) is None


def test_md_table_escapes_pipe():
    # finding 5: a user test name containing '|' must not break the table.
    import re

    df = pd.DataFrame({"test": ["A|B"], "value": [1.0]})
    md = core._md_table(df)
    assert "A\\|B" in md
    # the data row must have the same number of *unescaped* pipes (column
    # delimiters) as the header, so the '|' in the value does not inject a column
    def delimiters(line):
        return len(re.findall(r"(?<!\\)\|", line))

    lines = [ln for ln in md.splitlines() if ln.startswith("|")]
    assert delimiters(lines[2]) == delimiters(lines[0])


def test_format_value_nonfinite():
    # finding 8: non-finite constants read plainly, never nan/inf.
    assert core.format_value(float("inf")) == "not finite"
    assert core.format_value(float("nan")) == "not finite"
    assert core.format_value(np.float64(np.inf)) == "not finite"
    assert core.format_value(1234.5) == "1234.5"
    assert core.format_value("text") == "text"


def test_report_flags_nonfinite_constants():
    # finding 8: a degenerate fit's non-finite constant is flagged in the report.
    constants = pd.DataFrame(
        {"constant": ["b", "2N_t (reversals)"],
         "value": [-0.09, float("inf")],
         "meaning": ["exp", "transition"]},
    )
    md = core.build_report_markdown(
        material="M", constants=constants, summary_table=None,
        warnings=[], source="fitted",
    )
    assert "not finite" in md
    assert "degenerate fit" in md


def test_estimate_zero_ra_gives_specific_error():
    # finding 7: a deliberately-zero RA must raise the RA-range error, not a
    # misleading "requires RA". This is the library behavior the app relies on
    # by passing raw field values instead of `RA or None`.
    with pytest.raises(ValueError, match="RA must be a fraction"):
        lcf.estimate_strain_life_constants(
            "universal_slopes", material_class="steel",
            Su=500.0, E=200000.0, HB=150.0, RA=0.0,
        )


# --------------------------------------------------------------------------- #
# the app itself, headless
# --------------------------------------------------------------------------- #
def _app(default_timeout: float = 30.0):
    from streamlit.testing.v1 import AppTest

    return AppTest.from_file(APP_PATH, default_timeout=default_timeout)


def test_app_start_page_runs():
    at = _app().run()
    assert not at.exception
    assert "LCF Strain-Life" in at.title[0].value


def test_app_all_pages_render():
    at = _app().run()
    steps = at.sidebar.radio[0].options
    for step in steps:
        at.sidebar.radio[0].set_value(step)
        at.run()
        assert not at.exception, f"page '{step}' raised"


def test_app_example_fit_flow():
    at = _app().run()
    # load the example dataset on the start page
    at.button[0].click()
    at.run()
    assert at.session_state["material"] == core.EXAMPLE_MATERIAL
    # go to the fit page and fit
    at.sidebar.radio[0].set_value(at.sidebar.radio[0].options[2])
    at.run()
    fit_buttons = [b for b in at.button if "Fit the strain-life" in b.label]
    assert fit_buttons, "fit button not found"
    fit_buttons[0].click()
    at.run()
    assert not at.exception
    fit = at.session_state["fit"]
    assert fit is not None
    # golden check against the direct library fit of the same data
    direct = lcf.fit_strain_life(
        core.example_summary_table()["total_strain_amp"],
        core.example_summary_table()["stress_amp"],
        core.example_summary_table()["reversals"],
        core.EXAMPLE_E, min_plastic_strain=5e-4,
    )
    assert fit.basquin.b == pytest.approx(direct.basquin.b)
    assert fit.coffin_manson.c == pytest.approx(direct.coffin_manson.c)


def test_app_predict_after_fit():
    at = _app().run()
    at.button[0].click()
    at.run()
    at.sidebar.radio[0].set_value(at.sidebar.radio[0].options[2])
    at.run()
    [b for b in at.button if "Fit the strain-life" in b.label][0].click()
    at.run()
    at.sidebar.radio[0].set_value(at.sidebar.radio[0].options[3])
    at.run()
    assert not at.exception
    predict_buttons = [b for b in at.button if b.label == "Predict"]
    assert predict_buttons, "predict button not found"
    predict_buttons[0].click()
    at.run()
    assert not at.exception
    res = at.session_state["last_prediction"]
    assert res["reversals"] > 0


def test_app_estimate_flow():
    at = _app().run()
    at.sidebar.radio[0].set_value(at.sidebar.radio[0].options[4])
    at.run()
    est_buttons = [b for b in at.button if b.label == "Estimate"]
    assert est_buttons, "estimate button not found"
    est_buttons[0].click()
    at.run()
    assert not at.exception
    est = at.session_state["estimated"]
    assert est is not None
    # medians method for steel at Su=500: sigma_f' = 1.5*Su
    assert est.sigma_f == pytest.approx(750.0)


def test_app_report_page_after_fit():
    at = _app().run()
    at.button[0].click()
    at.run()
    at.sidebar.radio[0].set_value(at.sidebar.radio[0].options[2])
    at.run()
    [b for b in at.button if "Fit the strain-life" in b.label][0].click()
    at.run()
    at.sidebar.radio[0].set_value(at.sidebar.radio[0].options[5])
    at.run()
    assert not at.exception
    assert at.markdown, "report preview should render markdown"


def _load_example_and_fit(at):
    at.button[0].click()  # load example on the start page
    at.run()
    at.sidebar.radio[0].set_value(at.sidebar.radio[0].options[2])  # fit page
    at.run()
    [b for b in at.button if "Fit the strain-life" in b.label][0].click()
    at.run()
    return at


def test_app_clear_fit_button():
    # finding 1/2: a clear-fit control exists and actually drops the fit.
    at = _load_example_and_fit(_app().run())
    assert at.session_state["fit"] is not None
    clear = [b for b in at.button if b.label == "Clear fit"]
    assert clear, "Clear fit button not found"
    clear[0].click()
    at.run()
    assert at.session_state["fit"] is None


def test_app_stale_fit_invalidated_on_option_change():
    # finding 1: changing E after a fit invalidates the shown fit instead of
    # leaving mismatched constants on screen.
    at = _load_example_and_fit(_app().run())
    assert at.session_state["fit"] is not None
    e_inputs = [n for n in at.number_input if "Elastic modulus" in n.label]
    assert e_inputs, "fit-page E input not found"
    e_inputs[0].set_value(e_inputs[0].value + 1000.0)
    at.run()
    assert at.session_state["fit"] is None, "stale fit was not invalidated"


def test_app_fit_survives_navigation_with_nondefault_options():
    # regression: a non-default min-plastic-strain must persist across page
    # switches so the staleness check does not wrongly drop a valid fit.
    at = _app().run()
    at.button[0].click()  # load example
    at.run()
    at.sidebar.radio[0].set_value(at.sidebar.radio[0].options[2])  # fit page
    at.run()
    minp = [n for n in at.number_input if "plastic strain below" in n.label]
    assert minp, "min-plastic-strain input not found"
    minp[0].set_value(1e-3)
    at.run()
    [b for b in at.button if "Fit the strain-life" in b.label][0].click()
    at.run()
    assert at.session_state["fit"] is not None
    # leave the fit page and come back; the fit must still be there
    at.sidebar.radio[0].set_value(at.sidebar.radio[0].options[3])  # predict
    at.run()
    at.sidebar.radio[0].set_value(at.sidebar.radio[0].options[2])  # back to fit
    at.run()
    assert at.session_state["fit"] is not None, "valid fit was spuriously cleared"


def test_app_predict_source_radio_allows_estimate():
    # finding 2: with both a fit and an estimate, the user can predict from the
    # estimate, not only the fit.
    at = _load_example_and_fit(_app().run())
    at.sidebar.radio[0].set_value(at.sidebar.radio[0].options[4])  # estimate page
    at.run()
    [b for b in at.button if b.label == "Estimate"][0].click()
    at.run()
    assert at.session_state["estimated"] is not None
    at.sidebar.radio[0].set_value(at.sidebar.radio[0].options[3])  # predict page
    at.run()
    source = [r for r in at.radio if "Use constants from" in (r.label or "")]
    assert source, "source radio not shown when both fit and estimate exist"
    source[0].set_value("estimate")
    at.run()
    [b for b in at.button if b.label == "Predict"][0].click()
    at.run()
    assert not at.exception
    assert at.session_state["last_prediction"]["reversals"] > 0
