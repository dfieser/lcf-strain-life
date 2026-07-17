"""Streamlit app: a guided, no-code interface over the lcf library.

Run with ``lcf-gui`` (installed with the ``gui`` extra) or directly with
``streamlit run src/lcf/gui/app.py``. All computation happens locally in this
process. Nothing is sent anywhere.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

import lcf
from lcf import plots
from lcf.gui import core

st.set_page_config(page_title="LCF Strain-Life", layout="wide")

STEPS = [
    "Start",
    "1 · Analyze raw test files",
    "2 · Fit strain-life constants",
    "3 · Predict life",
    "4 · Estimate constants (no test data)",
    "5 · Report & export",
]


def _init_state() -> None:
    ss = st.session_state
    ss.setdefault("fit_table", core.empty_summary_table())
    ss.setdefault("fit_E", 200000.0)
    # fit options are mirrored into session_state so switching sidebar steps
    # does not reset them and spuriously invalidate a still-valid fit
    ss.setdefault("fit_minp", 5e-4)
    ss.setdefault("fit_refine", False)
    ss.setdefault("fit", None)                # lcf.StrainLifeFit
    ss.setdefault("fit_warnings", [])
    ss.setdefault("fit_data", None)           # DataFrame actually used in the fit
    ss.setdefault("material", "my material")
    ss.setdefault("ingested", {})             # filename -> core.IngestedTest
    ss.setdefault("estimated", None)          # lcf.EstimatedConstants
    ss.setdefault("estimated_E", None)


def _clear_fit() -> None:
    """Drop the current fit and everything derived from it."""
    ss = st.session_state
    ss.fit = None
    ss.fit_data = None
    ss.fit_warnings = []
    ss.pop("fit_signature", None)


def _have_fit() -> bool:
    return st.session_state.fit is not None


def _have_estimate() -> bool:
    return st.session_state.estimated is not None and bool(st.session_state.estimated_E)


def _active_constants(prefer: str | None = None) -> tuple[dict, str] | None:
    """The constants to predict with, honoring an explicit source preference.

    ``prefer`` is ``fit``, ``estimate``, or None. Falls back to the fit, then
    the estimate, so a user with both can choose either one.
    """
    ss = st.session_state
    source = core.select_source(_have_fit(), _have_estimate(), prefer)
    if source == "fit":
        f: lcf.StrainLifeFit = ss.fit
        return (
            {
                "sigma_f": f.basquin.sigma_f, "b": f.basquin.b,
                "eps_f": f.coffin_manson.eps_f, "c": f.coffin_manson.c,
                "E": f.E,
            },
            "fitted from test data (step 2)",
        )
    if source == "estimate":
        e = ss.estimated
        return (
            {"sigma_f": e.sigma_f, "b": e.b, "eps_f": e.eps_f, "c": e.c,
             "E": ss.estimated_E},
            f"estimated with the {e.method} method (step 4)",
        )
    return None


# --- pages -------------------------------------------------------------------

def page_start() -> None:
    st.title("LCF Strain-Life")
    st.write(
        "Low cycle fatigue strain-life analysis without writing code. "
        "Everything runs locally on this computer. Your data does not leave it."
    )
    st.markdown(
        """
**How to use it**

1. **Analyze raw test files**: upload the delimited exports from the test
   machine (time, strain, force). Each file is reduced to per-cycle metrics
   and a half-life summary, with hysteresis and hardening/softening plots.
2. **Fit strain-life constants**: the reduced tests (or numbers you type in)
   are fitted to the Basquin, Coffin-Manson, and Ramberg-Osgood models.
3. **Predict life**: reversals to failure at any strain amplitude, with
   optional Morrow or Smith-Watson-Topper mean-stress correction.
4. **Estimate constants**: no fatigue tests? Estimate the constants from
   tensile properties or hardness with five published methods.
5. **Report & export**: download the plots (PNG), tables (CSV), and a
   markdown report.

**Conventions**: stress and modulus in MPa. Strain is a fraction
(0.005 = 0.5 %), not a percent. All analysis uses true stress and strain,
and the exponents *b* and *c* are negative.
        """
    )
    if st.button("Load the SAE 1137 example dataset"):
        st.session_state.fit_table = core.example_summary_table()
        st.session_state.fit_E = core.EXAMPLE_E
        st.session_state.material = core.EXAMPLE_MATERIAL
        st.success(
            "Example loaded: published SAE 1137 reduced data. "
            "Continue with step 2 · Fit strain-life constants."
        )


def page_ingest() -> None:
    st.header("Analyze raw test files")
    st.write(
        "Upload one delimited export per test (CSV/TXT/DAT with time, strain, "
        "and force or stress columns). The delimiter, header row, and units "
        "(percent strain, kN force, ksi stress) are detected automatically."
    )
    with st.expander("Test parameters (applied to each uploaded file)", expanded=True):
        c1, c2, c3, c4 = st.columns(4)
        area = c1.number_input(
            "Cross-sectional area (mm²)", min_value=0.0, value=50.0,
            help="Gauge-section area, used to convert force to stress. "
                 "Not needed if the file already has a stress column.",
        )
        E_in = c2.number_input(
            "Elastic modulus E (MPa)", min_value=0.0, value=200000.0,
            help="Measured modulus. If 0, it is estimated from the loop data "
                 "(supplying a measured value is strongly preferred).",
        )
        R = c3.number_input(
            "Strain ratio R", value=-1.0,
            help="ε_min/ε_max of the command waveform. Fully reversed is -1.",
        )
        fail_pct = c4.number_input(
            "Failure criterion (% load drop)", min_value=1.0, max_value=90.0,
            value=50.0,
            help="Cycles to failure N_f is where the peak load drops this "
                 "percentage from the stabilized value (ASTM E606 practice).",
        )
        already_true = st.checkbox(
            "Strain/stress in the files are already true values",
            value=False,
            help="Leave off for normal engineering strain/stress exports. The "
                 "engineering-to-true conversion is applied at ingestion.",
        )

    uploads = st.file_uploader(
        "Test files", accept_multiple_files=True,
        type=["csv", "txt", "dat", "tsv", "asc"],
    )
    if uploads and st.button("Analyze uploaded files", type="primary"):
        files = [(up.name, up.getvalue()) for up in uploads]
        ok, errors = core.analyze_uploads(
            files,
            area=area or None,
            E=E_in or None,
            R=R,
            material=st.session_state.material,
            already_true=already_true,
            failure_criterion_pct=fail_pct,
        )
        for _fname, msg in errors:
            st.error(msg)
        for ing in ok:
            st.session_state.ingested[ing.filename] = ing
            row = core.summary_row(ing.analysis)
            st.session_state.fit_table = pd.concat(
                [core.drop_test_row(st.session_state.fit_table, row["test"]),
                 pd.DataFrame([row])],
                ignore_index=True,
            )
        if ok:
            st.success(
                f"{len(ok)} of {len(files)} file(s) analyzed. The half-life "
                "summaries were added to the fit table in step 2."
            )
        elif errors:
            st.warning("No files could be analyzed. See the errors above.")

    # Removal is deferred to after the loop so we do not mutate the dict while
    # iterating it, then a rerun redraws the reduced set.
    to_remove: tuple[str, str] | None = None
    for fname, ing in list(st.session_state.ingested.items()):
        s = ing.analysis.summary
        with st.expander(f"{fname}: {s['n_cycles']} cycles, N_f = {s['n_f']}"):
            st.caption(
                f"Read as: delimiter '{ing.resolution.get('delimiter')}', "
                f"columns {ing.resolution.get('columns')}, "
                f"units {ing.resolution.get('units') or 'as-is'}."
            )
            for note in ing.resolution.get("notes", []):
                st.warning(note)
            half = {
                "cycles detected": s["n_cycles"],
                "cycles to failure N_f": s["n_f"],
                "half-life cycle": s["half_life_cycle"],
                "stress amplitude (MPa)": round(s["stress_amp"], 1),
                "total strain amplitude": round(s["total_strain_amp"], 6),
                "plastic strain amplitude": round(s["plastic_strain_amp"], 6),
                "mean stress (MPa)": round(s["mean_stress"], 1),
                "energy density at half-life (MJ/m³)": round(s["energy_half_life"], 3),
                "E used (MPa)": round(s["E"], 0),
                "run-out (no failure)": s["runout"],
            }
            st.table(pd.DataFrame(half.items(), columns=["quantity", "value"]))
            p1, p2, p3 = st.columns(3)
            with p1:
                st.pyplot(plots.plot_hysteresis(ing.run, ing.analysis.reduced))
            with p2:
                st.pyplot(plots.plot_peak_valley(ing.analysis.metrics))
            with p3:
                st.pyplot(plots.plot_energy(ing.analysis.metrics))
            if st.button("Remove this test", key=f"remove_{fname}"):
                to_remove = (fname, s["name"])

    if to_remove is not None:
        fname, test_name = to_remove
        st.session_state.ingested.pop(fname, None)
        st.session_state.fit_table = core.drop_test_row(
            st.session_state.fit_table, test_name
        )
        st.rerun()


def page_fit() -> None:
    st.header("Fit strain-life constants")
    st.write(
        "One row per test: the half-life total strain amplitude (fraction), "
        "stress amplitude (MPa), and reversals to failure 2N_f. Rows arrive "
        "here automatically from step 1, or type/paste them directly. "
        "At least two rows are needed, more amplitudes give a better fit."
    )
    st.session_state.material = st.text_input(
        "Material name", value=st.session_state.material
    )
    edited = st.data_editor(
        st.session_state.fit_table,
        num_rows="dynamic",
        width="stretch",
        column_config={
            "test": st.column_config.TextColumn("Test", help="Test/specimen name"),
            "total_strain_amp": st.column_config.NumberColumn(
                "Total strain amplitude Δε/2", format="%.6f",
                help="Fraction, not percent: 0.005 means 0.5 %",
            ),
            "stress_amp": st.column_config.NumberColumn(
                "Stress amplitude Δσ/2 (MPa)", format="%.1f",
                help="Half-life (stabilized) stress amplitude",
            ),
            "reversals": st.column_config.NumberColumn(
                "Reversals to failure 2N_f", format="%.0f",
                help="Twice the cycles to failure",
            ),
        },
        key="fit_editor",
    )
    st.session_state.fit_table = edited

    with st.expander("Fit options"):
        c1, c2 = st.columns(2)
        E = c1.number_input(
            "Elastic modulus E (MPa)", min_value=1.0,
            value=float(st.session_state.fit_E),
            help="Used to split total strain into elastic and plastic parts.",
        )
        st.session_state.fit_E = E
        minp = c2.number_input(
            "Exclude points with plastic strain below", min_value=0.0,
            value=float(st.session_state.fit_minp), format="%.5f",
            help="Near-runout points whose plastic strain is at measurement-"
                 "noise level distort the Coffin-Manson fit. 0 disables.",
        )
        st.session_state.fit_minp = minp
        refine = st.checkbox(
            "Nonlinear refinement of the combined curve",
            value=bool(st.session_state.fit_refine),
            help="Refines the four constants with a nonlinear fit of the "
                 "total-strain curve, seeded by the standard log-log fits.",
        )
        st.session_state.fit_refine = refine

    if st.button("Fit the strain-life models", type="primary"):
        try:
            fit, warns = core.fit_from_table(
                edited, st.session_state.fit_E,
                min_plastic_strain=minp or None,
                refine_nonlinear=refine,
            )
        except core.GuiInputError as exc:
            st.error(str(exc))
        else:
            st.session_state.fit = fit
            st.session_state.fit_warnings = warns
            st.session_state.fit_signature = core.fit_signature(
                edited, st.session_state.fit_E, minp or None, refine
            )
            df = edited.copy()
            for col in ("total_strain_amp", "stress_amp", "reversals"):
                df[col] = pd.to_numeric(df[col], errors="coerce")
            st.session_state.fit_data = df.dropna(
                subset=["total_strain_amp", "stress_amp", "reversals"]
            )

    # Invalidate a shown fit if the table or options changed since it was made,
    # so the displayed constants and plots never disagree with the data above.
    current_sig = core.fit_signature(
        edited, st.session_state.fit_E, minp or None, refine
    )
    if (
        st.session_state.fit is not None
        and st.session_state.get("fit_signature") != current_sig
    ):
        _clear_fit()
        st.info(
            "The data or fit options changed since the last fit. Click Fit the "
            "strain-life models to recompute the constants."
        )

    fit: lcf.StrainLifeFit | None = st.session_state.fit
    if fit is not None:
        if st.button("Clear fit"):
            _clear_fit()
            st.rerun()
        for w in st.session_state.fit_warnings:
            st.warning(w)
        st.subheader("Fitted constants")
        st.dataframe(
            core.constants_frame(fit).style.format({"value": core.format_value}),
            width="stretch", hide_index=True,
        )
        data = st.session_state.fit_data
        p1, p2 = st.columns(2)
        with p1:
            st.pyplot(plots.plot_strain_life(
                fit,
                reversals=data["reversals"],
                total_strain_amp=data["total_strain_amp"],
            ))
        with p2:
            if fit.ramberg_osgood is not None:
                st.pyplot(plots.plot_cyclic_stress_strain(
                    fit.ramberg_osgood, fit.E,
                    sigma_max=float(data["stress_amp"].max()) * 1.2,
                ))
            else:
                st.info(
                    "No Ramberg-Osgood curve: fewer than two points with "
                    "usable plastic strain."
                )
        st.caption(
            "Continue with step 3 · Predict life, or step 5 · Report & export."
        )


def page_predict() -> None:
    st.header("Predict life")
    prefer = None
    if _have_fit() and _have_estimate():
        prefer = st.radio(
            "Use constants from",
            ["fit", "estimate"],
            format_func={
                "fit": "Fit from test data (step 2)",
                "estimate": "Estimate from properties (step 4)",
            }.get,
            horizontal=True,
        )
    active = _active_constants(prefer)
    if active is None:
        st.info(
            "No constants yet. Fit them from test data (step 2) or estimate "
            "them from tensile properties (step 4) first."
        )
        return
    constants, source = active
    st.caption(f"Using constants {source}.")

    c1, c2 = st.columns(2)
    amp = c1.number_input(
        "Total strain amplitude Δε/2", min_value=0.0, value=0.004,
        format="%.6f", help="Fraction, not percent: 0.004 means 0.4 %",
    )
    corr = c2.selectbox(
        "Mean-stress correction",
        ["none", "morrow", "swt"],
        format_func={
            "none": "None (fully reversed)",
            "morrow": "Morrow",
            "swt": "Smith-Watson-Topper",
        }.get,
        help="Apply a correction when the cycle carries a tensile mean stress.",
    )
    mean = 0.0
    samp = None
    if corr in ("morrow", "swt"):
        mean = st.number_input("Mean stress σ_m (MPa)", value=0.0)
    if corr == "swt":
        samp = st.number_input(
            "Stress amplitude σ_a (MPa)", min_value=0.0, value=0.0,
            help="Needed to form the peak stress σ_max = σ_a + σ_m of the cycle.",
        )

    if st.button("Predict", type="primary"):
        try:
            res = core.predict_life(
                constants, amp, correction=corr, mean_stress=mean,
                stress_amp=samp,
            )
        except core.GuiInputError as exc:
            st.error(str(exc))
        else:
            st.session_state.last_prediction = res
            m1, m2 = st.columns(2)
            m1.metric("Reversals to failure 2N_f", f"{res['reversals']:,.0f}")
            m2.metric("Cycles to failure N_f", f"{res['cycles']:,.0f}")


def page_estimate() -> None:
    st.header("Estimate constants without fatigue data")
    st.write(
        "Five published methods estimate the strain-life constants from "
        "tensile properties or hardness. Estimates are a starting point, not "
        "a substitute for testing. Each method's validity caveats are shown."
    )
    method = st.selectbox(
        "Method",
        list(lcf.ESTIMATION_METHODS),
        format_func={
            "medians": "Medians (Meggiolaro-Castro 2004): needs Su",
            "uniform_material_law": "Uniform Material Law (Baeumel-Seeger 1990): needs Su, E",
            "universal_slopes": "Universal Slopes (Manson 1965): needs Su, E, RA",
            "modified_universal_slopes": "Modified Universal Slopes (Muralidharan-Manson 1988): needs Su, E, RA",
            "hardness": "Hardness method (Roessle-Fatemi 2000): needs HB, E",
        }.get,
    )
    c1, c2, c3, c4 = st.columns(4)
    Su = c1.number_input("Ultimate strength Su (MPa)", min_value=0.0, value=500.0)
    E = c2.number_input("Elastic modulus E (MPa)", min_value=0.0, value=200000.0)
    RA = c3.number_input(
        "Reduction in area RA", min_value=0.0, max_value=1.0, value=0.5,
        help="Fraction, e.g. 0.5 for 50 %",
    )
    HB = c4.number_input("Brinell hardness HB", min_value=0.0, value=150.0)
    if method == "medians":
        mat_class = st.selectbox(
            "Material class",
            ["steel", "aluminum", "titanium", "cast_iron", "nickel"],
        )
    elif method == "uniform_material_law":
        mat_class = st.selectbox("Material class", ["steel", "aluminum_titanium"])
    else:
        mat_class = "steel"

    if st.button("Estimate", type="primary"):
        try:
            # Pass the raw field values, not `x or None`. A deliberately entered
            # 0 is an invalid boundary, not a missing field, and the estimator's
            # own validation gives the precise message (for example RA out of
            # range) instead of a misleading "requires RA".
            est = lcf.estimate_strain_life_constants(
                method, material_class=mat_class,
                Su=Su, E=E, HB=HB, RA=RA,
            )
        except ValueError as exc:
            st.error(str(exc))
        else:
            st.session_state.estimated = est
            # Prediction needs a positive modulus. A zero here means no usable
            # E, so store None and the predict page will say so.
            st.session_state.estimated_E = E if E > 0 else None

    est = st.session_state.estimated
    if est is not None:
        for w in est.warnings:
            st.warning(w)
        st.subheader("Estimated constants")
        st.dataframe(
            core.estimated_constants_frame(est).style.format({"value": core.format_value}),
            width="stretch", hide_index=True,
        )
        st.caption(f"Source: {est.citation}")
        if st.session_state.fit is None:
            st.caption("These constants are now available in step 3 · Predict life.")
        else:
            st.caption(
                "Both a fit (step 2) and this estimate are available. On step 3 · "
                "Predict life you can choose which one to use."
            )


def page_report() -> None:
    st.header("Report & export")
    fit: lcf.StrainLifeFit | None = st.session_state.fit
    est = st.session_state.estimated
    if fit is None and est is None:
        st.info("Nothing to export yet: fit (step 2) or estimate (step 4) first.")
        return

    material = st.session_state.material
    if fit is not None:
        constants = core.constants_frame(fit)
        source = "fitted from test data"
        summary = st.session_state.fit_data
        warnings = list(st.session_state.fit_warnings)
    else:
        constants = core.estimated_constants_frame(est)
        source = f"estimated ({est.method}), {est.citation}"
        summary = None
        warnings = list(est.warnings)

    md = core.build_report_markdown(
        material=material, constants=constants, summary_table=summary,
        warnings=warnings, source=source,
    )
    st.download_button(
        "Download report (markdown)", md,
        file_name=f"{material}-strain-life-report.md".replace(" ", "_"),
    )
    st.download_button(
        "Download constants (CSV)",
        constants.to_csv(index=False),
        file_name=f"{material}-constants.csv".replace(" ", "_"),
    )
    if summary is not None and len(summary):
        st.download_button(
            "Download per-test table (CSV)",
            summary.to_csv(index=False),
            file_name=f"{material}-tests.csv".replace(" ", "_"),
        )
    if fit is not None:
        data = st.session_state.fit_data
        fig = plots.plot_strain_life(
            fit, reversals=data["reversals"],
            total_strain_amp=data["total_strain_amp"],
        )
        st.download_button(
            "Download strain-life plot (PNG)", core.fig_png_bytes(fig),
            file_name=f"{material}-strain-life.png".replace(" ", "_"),
        )
    st.divider()
    st.subheader("Report preview")
    st.markdown(md)


# --- shell -------------------------------------------------------------------

def main() -> None:
    _init_state()
    with st.sidebar:
        st.markdown("### LCF Strain-Life")
        step = st.radio("Workflow", STEPS, label_visibility="collapsed")
        st.caption(
            f"lcf-strain-life {lcf.__version__}: runs locally, "
            "no data leaves this computer."
        )
    {
        STEPS[0]: page_start,
        STEPS[1]: page_ingest,
        STEPS[2]: page_fit,
        STEPS[3]: page_predict,
        STEPS[4]: page_estimate,
        STEPS[5]: page_report,
    }[step]()


main()
