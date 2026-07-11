"""Service layer: compute/save/recall operations bound to a store.

This holds the plain-Python logic that the MCP server exposes as tools. Keeping
it MCP-free makes it directly testable and reusable. Each compute operation
returns a compact, JSON-able summary and persists full artifacts (per-cycle
tables, fitted constants) to the :class:`~lcf.store.LcfStore`, following the
compute/save/recall model (ADR-0007, ADR-0008).
"""

from __future__ import annotations

from pathlib import Path

from types import SimpleNamespace

import numpy as np

from . import (
    counting,
    damage,
    estimate,
    fits,
    hightemp,
    labio,
    life,
    multiaxial,
    notch,
    spectrum,
    stats,
)
from .ingest import from_timeseries, read_csv
from .meanstress import equivalent_fully_reversed_stress, walker_gamma_steel
from .models import AnalysisParams, MeanStressModel, TestMetadata
from .pipeline import analyze_test, build_summary_table, fit_from_summary
from .store import LcfStore, hash_inputs, to_jsonable

__all__ = ["LcfService"]


class LcfService:
    """High-level LCF operations with persistence."""

    def __init__(self, store: LcfStore | str | Path = ".lcfstore"):
        self.store = store if isinstance(store, LcfStore) else LcfStore(store)

    # --------------------------------------------------------------- compute
    def analyze_timeseries(
        self,
        name: str,
        time: list[float],
        strain: list[float],
        force: list[float],
        area: float,
        *,
        E: float | None = None,
        R: float = -1.0,
        already_true: bool = False,
        failure_pct: float = 30.0,
        material: str | None = None,
    ) -> dict:
        """Reduce one test from a time series, then persist the per-cycle table and summary."""
        meta = TestMetadata(
            name=name, area=area, E=E, R=R, already_true=already_true, material=material
        )
        test = from_timeseries(time, strain, force, metadata=meta)
        params = AnalysisParams(failure_criterion_pct=failure_pct)
        ta = analyze_test(test, params)

        ihash = hash_inputs(
            list(time), list(strain), list(force), area, E, R, already_true, failure_pct
        )
        self.store.save(name, "per_cycle", {"n_cycles": ta.reduced.n_cycles},
                        dataframe=ta.metrics.table, input_hash=ihash)
        self.store.save(name, "summary", ta.summary, input_hash=ihash)
        return to_jsonable(ta.summary)

    def analyze_csv(
        self,
        name: str,
        csv_path: str,
        area: float,
        *,
        column_map: dict[str, str] | None = None,
        E: float | None = None,
        R: float = -1.0,
        already_true: bool = False,
        failure_pct: float = 30.0,
        material: str | None = None,
        read_csv_kwargs: dict | None = None,
    ) -> dict:
        """Reduce one test from a CSV file, then persist the per-cycle table and summary."""
        meta = TestMetadata(
            name=name, area=area, E=E, R=R, already_true=already_true, material=material
        )
        test = read_csv(csv_path, metadata=meta, column_map=column_map,
                        **(read_csv_kwargs or {}))
        params = AnalysisParams(failure_criterion_pct=failure_pct)
        ta = analyze_test(test, params)
        ihash = hash_inputs(Path(csv_path).read_bytes(), area, E, R, already_true, failure_pct)
        self.store.save(name, "per_cycle", {"n_cycles": ta.reduced.n_cycles},
                        dataframe=ta.metrics.table, input_hash=ihash)
        self.store.save(name, "summary", ta.summary, input_hash=ihash)
        return to_jsonable(ta.summary)

    def analyze_series(
        self,
        directory: str | None = None,
        area: float | None = None,
        *,
        files: list[str] | None = None,
        pattern: str = "*.csv",
        E: float | None = None,
        R: float = -1.0,
        already_true: bool = False,
        failure_pct: float = 30.0,
        material: str | None = None,
        column_map: dict[str, str] | None = None,
        strain_unit: str | None = None,
        force_unit: str | None = None,
        stress_unit: str | None = None,
        min_plastic_strain: float | None = None,
        refine_nonlinear: bool = False,
    ) -> dict:
        """Analyze a full test series of lab exports in one call (ADR-0014, P1).

        Reads every matching file (name = file stem), reduces each test,
        persists each per-cycle table and summary, then fits the strain-life
        models across the series and persists the fit. Per-file failures are
        collected in ``errors`` and do not stop the rest of the series.
        """
        si = labio.read_series(
            directory, files=files, pattern=pattern,
            metadata_defaults={
                "area": area, "E": E, "R": R, "already_true": already_true,
                "material": material,
            },
            column_map=column_map, strain_unit=strain_unit,
            force_unit=force_unit, stress_unit=stress_unit,
        )
        params = AnalysisParams(
            failure_criterion_pct=failure_pct,
            min_plastic_strain=min_plastic_strain,
            refine_nonlinear=refine_nonlinear,
        )

        analyses = []
        kept: list[str] = []
        errors = list(si.errors)
        for path, run in zip(si.paths, si.runs):
            try:
                ta = analyze_test(run, params)
            except Exception as exc:  # noqa: BLE001 - reported per file
                errors.append({"file": path, "error": str(exc)})
                continue
            ihash = hash_inputs(
                Path(path).read_bytes(), area, E, R, already_true, failure_pct
            )
            self.store.save(ta.name, "per_cycle", {"n_cycles": ta.reduced.n_cycles},
                            dataframe=ta.metrics.table, input_hash=ihash)
            self.store.save(ta.name, "summary", ta.summary, input_hash=ihash)
            analyses.append(ta)
            kept.append(path)

        if analyses:
            fit, notes = fit_from_summary(build_summary_table(analyses), params)
        else:
            fit, notes = None, ["no test in the series could be analyzed"]
        fit_json = to_jsonable(fit) if fit is not None else None

        key = material
        if key is None:
            key = Path(directory).name if directory else (
                analyses[0].name if analyses else "series"
            )
        series_hash = hash_inputs(
            [Path(p).name for p in kept], area, E, R, already_true, failure_pct,
            min_plastic_strain, refine_nonlinear,
        )
        if fit_json is not None:
            self.store.save(key, "strain_life_fit", fit_json, input_hash=series_hash)
        result = {
            "material": material,
            "series_key": key,
            "files": kept,
            "n_tests": len(analyses),
            "tests": [a.summary for a in analyses],
            "fit": fit_json,
            "notes": notes,
            "errors": errors,
            "resolutions": si.resolutions,
        }
        self.store.save(
            key, "series_summary",
            {k: result[k] for k in ("material", "files", "n_tests", "notes", "errors")},
            input_hash=series_hash,
        )
        return to_jsonable(result)

    def fit_strain_life(
        self,
        total_strain_amp: list[float],
        stress_amp: list[float],
        reversals: list[float],
        E: float,
        *,
        plastic_strain_amp: list[float] | None = None,
        min_plastic_strain: float | None = None,
        refine_nonlinear: bool = False,
        material: str | None = None,
    ) -> dict:
        """Fit Basquin, Coffin-Manson, and Ramberg-Osgood constants, then persist if named."""
        fit = fits.fit_strain_life(
            total_strain_amp, stress_amp, reversals, E,
            plastic_strain_amp=plastic_strain_amp,
            min_plastic_strain=min_plastic_strain,
            refine_nonlinear=refine_nonlinear,
        )
        result = to_jsonable(fit)
        if material:
            ihash = hash_inputs(
                list(total_strain_amp), list(stress_amp), list(reversals), E,
                min_plastic_strain, refine_nonlinear,
            )
            self.store.save(material, "strain_life_fit", result, input_hash=ihash)
        return result

    def predict_life(
        self, total_strain_amp: float, sigma_f: float, b: float, eps_f: float,
        c: float, E: float,
    ) -> dict:
        """Predict reversals/cycles to failure for a given total strain amplitude."""
        two_nf = life.predict_reversals_from_total_strain(
            total_strain_amp, sigma_f, b, eps_f, c, E
        )
        return to_jsonable({"reversals": two_nf, "cycles": two_nf / 2.0,
                            "total_strain_amp": total_strain_amp})

    def mean_stress_equivalent_stress(
        self, stress_amp: float, mean_stress: float, model: str,
        *, sigma_f: float | None = None, gamma: float | None = None,
        sigma_u: float | None = None,
    ) -> dict:
        """Equivalent fully-reversed stress for a cycle under a mean-stress model.

        For Walker, ``gamma`` may be given directly or estimated from ``sigma_u``
        (steel) via the Dowling relation.
        """
        m = MeanStressModel(model)
        if m is MeanStressModel.WALKER and gamma is None and sigma_u is not None:
            gamma = walker_gamma_steel(sigma_u)
        sar = equivalent_fully_reversed_stress(
            stress_amp, mean_stress, m, sigma_f=sigma_f, gamma=gamma
        )
        return to_jsonable({"equivalent_stress_amp": float(sar), "model": m.value,
                            "gamma": gamma, "stress_amp": stress_amp,
                            "mean_stress": mean_stress})

    # ----------------------------------------------------- phase 2: variable amp
    def count_rainflow(self, name: str, strain_history: list[float], *,
                       close_residue: bool = False,
                       gate: float | None = None) -> dict:
        """Rainflow count a strain history, persist the per-cycle table.

        A non-None ``gate`` first condenses the history with the racetrack
        filter, dropping swings smaller than the gate. Cycle indices always
        refer to the original series.
        """
        if gate is not None:
            idx, vals = counting.racetrack_filter(strain_history, gate)
            df = counting.count_rainflow(vals, close_residue=close_residue)
            df["i_start"] = idx[df["i_start"].to_numpy()]
            df["i_end"] = idx[df["i_end"].to_numpy()]
        else:
            df = counting.count_rainflow(strain_history, close_residue=close_residue)
        ihash = hash_inputs(list(strain_history), close_residue, gate)
        summary = {
            "n_cycles": int(len(df)),
            "total_count": float(df["count"].sum()) if len(df) else 0.0,
            "max_range": float(df["range"].max()) if len(df) else 0.0,
            "gate": gate,
        }
        self.store.save(name, "rainflow", summary, dataframe=df, input_hash=ihash)
        return summary

    def count_level_crossings(self, name: str, series: list[float], *,
                              levels: list[float] | None = None,
                              ref: float = 0.0) -> dict:
        """Level-crossing count (ASTM E1049 5.2), persist the level table."""
        df = counting.count_level_crossings(series, levels=levels, ref=ref)
        ihash = hash_inputs(list(series), list(levels) if levels else None, ref)
        summary = {
            "n_levels": int(len(df)),
            "total_crossings": int(df["count"].sum()),
            "ref": ref,
        }
        self.store.save(name, "level_crossings", summary, dataframe=df,
                        input_hash=ihash)
        return summary

    def count_peaks(self, name: str, series: list[float], *,
                    ref: float = 0.0) -> dict:
        """Peak and valley count (ASTM E1049 5.3), persist the table."""
        df = counting.count_peaks(series, ref=ref)
        ihash = hash_inputs(list(series), ref)
        summary = {
            "n_peaks": int((df["kind"] == "peak").sum()),
            "n_valleys": int((df["kind"] == "valley").sum()),
            "ref": ref,
        }
        self.store.save(name, "peaks", summary, dataframe=df, input_hash=ihash)
        return summary

    def compute_sn_life(self, stress_amp: list[float], *, k: float, sd: float,
                        nd: float, variant: str = "original") -> dict:
        """Allowable cycles per stress amplitude from a Woehler line with knee.

        Infinite lives (below the knee in the original variant) serialize as
        null in JSON.
        """
        lives = damage.sn_curve_life(stress_amp, k=k, sd=sd, nd=nd,
                                     variant=variant)
        return to_jsonable({
            "lives": [float(v) for v in lives],
            "variant": variant,
            "k": k, "sd": sd, "nd": nd,
        })

    def compute_spectrum_life(
        self, strain_history: list[float], stress_history: list[float], *,
        sigma_f: float, b: float, eps_f: float, c: float, E: float,
        mean_stress_method: str = "swt", rule: str = "miner", name: str | None = None,
    ) -> dict:
        """Variable-amplitude life from a strain and stress history."""
        res = spectrum.spectrum_life(
            strain_history, stress_history, sigma_f=sigma_f, b=b, eps_f=eps_f, c=c, E=E,
            mean_stress_method=mean_stress_method, rule=rule,
        )
        out = {
            "damage_per_block": res.damage_per_block,
            "blocks_to_failure": res.blocks_to_failure,
            "cycles_to_failure": res.cycles_to_failure,
            "mean_stress_method": res.mean_stress_method,
            "rule": res.rule,
            "n_cycles": int(len(res.cycles)),
        }
        if name:
            ihash = hash_inputs(list(strain_history), list(stress_history),
                                sigma_f, b, eps_f, c, E, mean_stress_method, rule)
            self.store.save(name, "spectrum_life", out, dataframe=res.cycles, input_hash=ihash)
        return to_jsonable(out)

    def compute_damage(self, counts: list[float], lives: list[float], *,
                       rule: str = "miner", d_crit: float = 1.0,
                       stresses: list[float] | None = None,
                       d_exponent: float | None = None) -> dict:
        """Cumulative damage for a counted block (Miner, DLDR, or Corten-Dolan).

        Corten-Dolan needs the per-level ``stresses`` and the material exponent
        ``d_exponent``.
        """
        if rule == "miner":
            dr = damage.miner(counts, lives, d_crit=d_crit)
        elif rule == "dldr":
            dr = damage.dldr(counts, lives, d_crit=d_crit)
        elif rule == "corten_dolan":
            if stresses is None or d_exponent is None:
                raise ValueError(
                    "corten_dolan requires stresses and d_exponent"
                )
            dr = damage.corten_dolan(counts, stresses, lives, d=d_exponent)
        else:
            raise ValueError("rule must be miner, dldr, or corten_dolan")
        return to_jsonable(dr)

    def compute_notch_local(
        self, nominal_amp: float, Kt: float, *,
        E: float, K: float, n: float, sigma_f: float, b: float, eps_f: float, c: float,
        method: str = "neuber", name: str | None = None,
    ) -> dict:
        """Local notch stress, strain, and life from a nominal stress amplitude."""
        res = notch.notch_local_life(
            nominal_amp, Kt, E=E, K=K, n=n, sigma_f=sigma_f, b=b, eps_f=eps_f, c=c,
            method=method,
        )
        if name:
            self.store.save(name, "notch_local", res,
                            input_hash=hash_inputs(nominal_amp, Kt, E, K, n, method))
        return to_jsonable(res)

    # ----------------------------------------------------- phase 2: statistics
    def fit_design_curve(
        self, amplitude: list[float], life_values: list[float], *,
        reliability: float = 0.90, confidence: float = 0.90,
        censored: list[bool] | None = None, design_amplitude: float | None = None,
        material: str | None = None,
    ) -> dict:
        """Fit a strain-life regression and report design (R-C) values."""
        if censored is not None and any(censored):
            fit = stats.fit_log_life_censored(amplitude, life_values, censored)
        else:
            fit = stats.fit_log_life(amplitude, life_values)
        out = {
            "slope": fit.slope, "intercept": fit.intercept,
            "residual_std": fit.residual_std, "n_points": fit.n_points,
            "r_squared": fit.r_squared,
            "owen_factor": stats.owen_tolerance_factor(fit.n_points, reliability, confidence),
        }
        if design_amplitude is not None:
            out["median_life"] = float(stats.predict_life(fit, design_amplitude))
            out["design_life"] = stats.design_life(
                fit, design_amplitude, reliability=reliability, confidence=confidence
            )
        if material:
            self.store.save(material, "design_curve", out,
                            input_hash=hash_inputs(list(amplitude), list(life_values),
                                                   reliability, confidence))
        return to_jsonable(out)

    def flag_outliers(
        self, amplitude: list[float], life_values: list[float], *,
        censored: list[bool] | None = None,
        alpha: float = 0.05,
        max_outliers: int | None = None,
    ) -> dict:
        """Flag statistical outliers in strain-life data, respecting runouts.

        Runouts (censored points) are suspended tests, not outliers, so they
        are separated first and never tested. The remaining points are fitted
        with the log-log regression, the residuals are screened with the
        generalized ESD test (Rosner 1983, NIST recipe), and influence
        diagnostics (Cook's distance, leverage) are reported. Indices refer to
        the original input order.
        """
        n = len(amplitude)
        if len(life_values) != n:
            raise ValueError("amplitude and life_values must be the same length")
        cens = list(censored) if censored is not None else [False] * n
        if len(cens) != n:
            raise ValueError("censored must match the data length")
        runout_indices = [i for i in range(n) if cens[i]]
        kept = [i for i in range(n) if not cens[i]]
        amp = [amplitude[i] for i in kept]
        lif = [life_values[i] for i in kept]

        fit = stats.fit_log_life(amp, lif)
        x = np.log10(np.asarray(amp, dtype=np.float64))
        y = np.log10(np.asarray(lif, dtype=np.float64))
        residuals = y - (fit.intercept + fit.slope * x)

        warnings: list[str] = []
        outlier_indices: list[int] = []
        steps: list[dict] = []
        k = max_outliers if max_outliers is not None else max(1, len(kept) // 5)
        if len(kept) - k >= 3:
            esd = stats.generalized_esd(residuals, max_outliers=k, alpha=alpha)
            outlier_indices = [kept[j] for j in esd["outlier_indices"]]
            steps = esd["steps"]
            warnings.extend(esd["warnings"])
        else:
            warnings.append(
                "too few uncensored points for the generalized ESD test, "
                "no outlier test was run"
            )

        diag = stats.regression_diagnostics(amp, lif)
        influential = [kept[j] for j in diag["influential_indices"]]
        return to_jsonable({
            "n_points": n,
            "runout_indices": runout_indices,
            "outlier_indices": outlier_indices,
            "influential_indices": influential,
            "esd_steps": steps,
            "cooks_distance": diag["cooks_distance"],
            "leverage": diag["leverage"],
            "studentized_residuals": diag["studentized_residuals"],
            "alpha": alpha,
            "warnings": warnings,
            "citations": [
                "Rosner, Technometrics 25 (1983) 165-172",
                "Grubbs, Technometrics 11 (1969) 1-21",
                "Cook, Technometrics 19 (1977) 15-18",
                "NIST/SEMATECH e-Handbook of Statistical Methods, "
                "sections 1.3.5.17.1 and 1.3.5.17.3",
            ],
        })

    # ----------------------------------------------------- phase 2: high temp
    def compute_creep_fatigue(
        self, cycle_counts: list[float], fatigue_lives: list[float],
        hold_times: list[float], rupture_times: list[float], *,
        envelope: float = 1.0, knee: tuple[float, float] = (0.3, 0.3),
        name: str | None = None,
    ) -> dict:
        """Time-fraction creep-fatigue damage with a D-diagram envelope check."""
        r = hightemp.creep_fatigue_damage(
            cycle_counts, fatigue_lives, hold_times, rupture_times, envelope=envelope
        )
        chk = hightemp.creep_fatigue_envelope_check(r.d_fatigue, r.d_creep, knee=knee)
        out = {**to_jsonable(r), "envelope_check": chk}
        if name:
            self.store.save(name, "creep_fatigue", out,
                            input_hash=hash_inputs(list(cycle_counts), list(hold_times)))
        return to_jsonable(out)

    # ----------------------------------------------------- constant estimation
    def estimate_constants(
        self, method: str, *,
        material_class: str = "steel",
        Su: float | None = None,
        E: float | None = None,
        HB: float | None = None,
        RA: float | None = None,
        material: str | None = None,
    ) -> dict:
        """Estimate strain-life constants from monotonic properties.

        Returns the constants with the citation of the source method and any
        validity warnings. Persists under ``material`` if given.
        """
        est = estimate.estimate_strain_life_constants(
            method, material_class=material_class, Su=Su, E=E, HB=HB, RA=RA
        )
        out = to_jsonable(est)
        if material:
            ihash = hash_inputs(method, material_class, Su, E, HB, RA)
            self.store.save(material, "estimated_constants", out, input_hash=ihash)
        return out

    # ----------------------------------------------------- multiaxial parameters
    def compute_multiaxial_parameter(
        self, parameter: str, *,
        shear_strain_amp: float | None = None,
        normal_strain_amp: float | None = None,
        sigma_n_max: float | None = None,
        sigma_y: float | None = None,
        k: float = 0.3,
        S: float = 1.0,
        eps_x: float | None = None, eps_y: float | None = None,
        eps_z: float | None = None,
        gamma_xy: float = 0.0, gamma_yz: float = 0.0, gamma_zx: float = 0.0,
    ) -> dict:
        """Evaluate one critical-plane damage parameter from known plane quantities.

        ``parameter`` is one of fatemi_socie, brown_miller, swt, von_mises.
        The plane quantities must be supplied by the caller, there is no tensor
        rotating-plane engine yet.
        """
        if parameter == "fatemi_socie":
            if shear_strain_amp is None or sigma_n_max is None or sigma_y is None:
                raise ValueError(
                    "fatemi_socie requires shear_strain_amp, sigma_n_max, sigma_y"
                )
            value = multiaxial.fatemi_socie(
                shear_strain_amp, sigma_n_max, sigma_y=sigma_y, k=k
            )
        elif parameter == "brown_miller":
            if shear_strain_amp is None or normal_strain_amp is None:
                raise ValueError(
                    "brown_miller requires shear_strain_amp and normal_strain_amp"
                )
            value = multiaxial.brown_miller(shear_strain_amp, normal_strain_amp, S=S)
        elif parameter == "swt":
            if sigma_n_max is None or normal_strain_amp is None:
                raise ValueError("swt requires sigma_n_max and normal_strain_amp")
            value = multiaxial.swt_multiaxial(sigma_n_max, normal_strain_amp)
        elif parameter == "von_mises":
            if eps_x is None or eps_y is None or eps_z is None:
                raise ValueError("von_mises requires eps_x, eps_y, eps_z")
            value = multiaxial.von_mises_equivalent_strain(
                eps_x, eps_y, eps_z, gamma_xy, gamma_yz, gamma_zx
            )
        else:
            raise ValueError(
                "parameter must be fatemi_socie, brown_miller, swt, or von_mises"
            )
        return to_jsonable({"parameter": parameter, "value": float(value)})

    def search_critical_plane(
        self, parameter: str, angles: list[float],
        shear_strain_amp: list[float] | None = None, *,
        normal_strain_amp: list[float] | None = None,
        sigma_n_max: list[float] | None = None,
        sigma_y: float | None = None,
        k: float = 0.3,
        S: float = 1.0,
    ) -> dict:
        """Find the plane angle that maximizes a damage parameter.

        The caller supplies per-angle plane quantities as aligned arrays, one
        entry per candidate angle. Returns the critical angle, the maximum
        parameter, and the per-angle values.
        """
        angles_arr = np.asarray(angles, dtype=np.float64)
        n = len(angles_arr)

        def _aligned(name, values):
            if values is None:
                raise ValueError(f"{parameter} requires {name}, one value per angle")
            arr = np.asarray(values, dtype=np.float64)
            if arr.shape != angles_arr.shape:
                raise ValueError(f"{name} must have one value per angle")
            return arr

        if parameter == "fatemi_socie":
            gam = _aligned("shear_strain_amp", shear_strain_amp)
            sn = _aligned("sigma_n_max", sigma_n_max)
            if sigma_y is None:
                raise ValueError("fatemi_socie requires sigma_y")
            values = [
                multiaxial.fatemi_socie(gam[i], sn[i], sigma_y=sigma_y, k=k)
                for i in range(n)
            ]
        elif parameter == "brown_miller":
            gam = _aligned("shear_strain_amp", shear_strain_amp)
            en = _aligned("normal_strain_amp", normal_strain_amp)
            values = [
                multiaxial.brown_miller(gam[i], en[i], S=S) for i in range(n)
            ]
        elif parameter == "swt":
            sn = _aligned("sigma_n_max", sigma_n_max)
            en = _aligned("normal_strain_amp", normal_strain_amp)
            values = [multiaxial.swt_multiaxial(sn[i], en[i]) for i in range(n)]
        else:
            raise ValueError(
                "parameter must be fatemi_socie, brown_miller, or swt"
            )
        res = multiaxial.critical_plane_search(
            lambda a: values[int(np.argmin(np.abs(angles_arr - a)))],
            angles=angles_arr,
        )
        return to_jsonable({
            "parameter": parameter,
            "critical_angle": res["critical_angle"],
            "max_parameter": res["max_parameter"],
            "angles": list(map(float, res["angles"])),
            "values": list(map(float, res["values"])),
        })

    # ----------------------------------------------------- high temp, frequency
    def compute_frequency_modified_life(
        self, plastic_strain_amp: float, eps_f_coeff: float, c: float, *,
        frequency: float, k: float, freq_ref: float = 1.0,
    ) -> dict:
        """Reversals to failure from the frequency-modified Coffin-Manson law."""
        c_f = hightemp.frequency_modified_coefficient(
            eps_f_coeff, frequency=frequency, k=k, freq_ref=freq_ref
        )
        two_nf = hightemp.frequency_modified_reversals(
            plastic_strain_amp, eps_f_coeff, c, frequency=frequency, k=k,
            freq_ref=freq_ref,
        )
        return to_jsonable({
            "reversals": two_nf,
            "cycles": two_nf / 2.0,
            "modified_coefficient": c_f,
            "plastic_strain_amp": plastic_strain_amp,
            "frequency": frequency,
        })

    # --------------------------------------------------------------- plotting
    def render_plot(self, key: str, kind: str) -> dict:
        """Render a stored result as a PNG and register it in the store.

        ``kind`` is one of rainflow_histogram, peak_valley, energy, strain_life.
        The data comes from the store, so run the corresponding compute tool
        first. Returns the PNG path.
        """
        from . import plots  # matplotlib import stays lazy

        if kind == "rainflow_histogram":
            df = self.store.get_dataframe(key, "rainflow")
            if df is None:
                raise ValueError(f"no rainflow table stored for key={key!r}")
            fig = plots.plot_rainflow_histogram(df)
        elif kind in ("peak_valley", "energy"):
            df = self.store.get_dataframe(key, "per_cycle")
            summary = self.store.recall(key, "summary")
            if df is None or summary is None:
                raise ValueError(f"no per-cycle result stored for key={key!r}")
            half_life = summary["value"].get("half_life_cycle")
            shim = SimpleNamespace(table=df, half_life_cycle=half_life)
            fig = plots.plot_peak_valley(shim) if kind == "peak_valley" \
                else plots.plot_energy(shim)
        elif kind == "strain_life":
            rec = self.store.recall(key, "strain_life_fit")
            if rec is None:
                raise ValueError(f"no strain-life fit stored for key={key!r}")
            v = rec["value"]
            shim = SimpleNamespace(
                E=v["E"],
                basquin=SimpleNamespace(**v["basquin"]),
                coffin_manson=SimpleNamespace(**v["coffin_manson"]),
                transition_reversals=v.get("transition_reversals"),
            )
            fig = plots.plot_strain_life(shim)
        else:
            raise ValueError(
                "kind must be rainflow_histogram, peak_valley, energy, "
                "or strain_life"
            )
        png_path = self.store.root / f"{key}__{kind}.png"
        plots.savefig(fig, png_path)
        self.store.save(key, f"plot_{kind}", {"kind": kind}, png_path=png_path)
        return {"key": key, "kind": kind, "png_path": str(png_path)}

    # --------------------------------------------------------------- recall
    def recall(self, key: str, quantity: str) -> dict | None:
        """Recall a stored result by key and quantity."""
        return self.store.recall(key, quantity)

    def list_results(self, key: str | None = None) -> list[dict]:
        """List stored results (optionally for one key)."""
        return self.store.list(key)
