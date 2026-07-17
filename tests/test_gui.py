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
