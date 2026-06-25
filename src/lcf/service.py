"""Service layer: compute/save/recall operations bound to a store.

This holds the plain-Python logic that the MCP server exposes as tools. Keeping
it MCP-free makes it directly testable and reusable. Each compute operation
returns a compact, JSON-able summary and persists full artifacts (per-cycle
tables, fitted constants) to the :class:`~lcf.store.LcfStore`, following the
compute/save/recall model (ADR-0007, ADR-0008).
"""

from __future__ import annotations

from pathlib import Path

from . import counting, damage, fits, hightemp, life, notch, spectrum, stats
from .ingest import from_timeseries, read_csv
from .meanstress import equivalent_fully_reversed_stress, walker_gamma_steel
from .models import AnalysisParams, MeanStressModel, TestMetadata
from .pipeline import analyze_test
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
                       close_residue: bool = False) -> dict:
        """Rainflow count a strain history, persist the per-cycle table."""
        df = counting.count_rainflow(strain_history, close_residue=close_residue)
        ihash = hash_inputs(list(strain_history), close_residue)
        summary = {
            "n_cycles": int(len(df)),
            "total_count": float(df["count"].sum()) if len(df) else 0.0,
            "max_range": float(df["range"].max()) if len(df) else 0.0,
        }
        self.store.save(name, "rainflow", summary, dataframe=df, input_hash=ihash)
        return summary

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
                       rule: str = "miner", d_crit: float = 1.0) -> dict:
        """Cumulative damage for a counted block (Miner or DLDR)."""
        if rule == "miner":
            dr = damage.miner(counts, lives, d_crit=d_crit)
        elif rule == "dldr":
            dr = damage.dldr(counts, lives, d_crit=d_crit)
        else:
            raise ValueError("rule must be miner or dldr")
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

    # --------------------------------------------------------------- recall
    def recall(self, key: str, quantity: str) -> dict | None:
        """Recall a stored result by key and quantity."""
        return self.store.recall(key, quantity)

    def list_results(self, key: str | None = None) -> list[dict]:
        """List stored results (optionally for one key)."""
        return self.store.list(key)
