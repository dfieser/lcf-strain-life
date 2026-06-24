"""Service layer: compute/save/recall operations bound to a store.

This holds the plain-Python logic that the MCP server exposes as tools. Keeping
it MCP-free makes it directly testable and reusable. Each compute operation
returns a compact, JSON-able summary and persists full artifacts (per-cycle
tables, fitted constants) to the :class:`~lcf.store.LcfStore`, following the
compute/save/recall model (ADR-0007, ADR-0008).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from . import fits, life
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
        return ta.summary

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
        return ta.summary

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
        return {"reversals": two_nf, "cycles": two_nf / 2.0,
                "total_strain_amp": total_strain_amp}

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
        return {"equivalent_stress_amp": float(sar), "model": m.value,
                "gamma": gamma, "stress_amp": stress_amp, "mean_stress": mean_stress}

    # --------------------------------------------------------------- recall
    def recall(self, key: str, quantity: str) -> dict | None:
        """Recall a stored result by key and quantity."""
        return self.store.recall(key, quantity)

    def list_results(self, key: str | None = None) -> list[dict]:
        """List stored results (optionally for one key)."""
        return self.store.list(key)
