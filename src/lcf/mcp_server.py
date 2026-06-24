"""MCP server exposing the LCF analysis tools (ADR-0008).

Thin wrappers over :class:`lcf.service.LcfService`. Tools are narrow and clearly
named; large per-cycle data is persisted to the store (and recalled on demand)
rather than returned inline. Run with ``lcf-mcp`` or ``python -m lcf``.

The store directory comes from the ``LCF_STORE_DIR`` environment variable
(default ``.lcfstore``).
"""

from __future__ import annotations

import json
import os

from .service import LcfService

try:
    from mcp.server.fastmcp import FastMCP
except ModuleNotFoundError as exc:  # pragma: no cover
    raise SystemExit(
        "The MCP SDK is not installed. Install the optional extra:\n"
        '    pip install "lcf-strain-life[mcp]"'
    ) from exc

mcp = FastMCP("lcf-strain-life")
_service = LcfService(os.environ.get("LCF_STORE_DIR", ".lcfstore"))


@mcp.tool()
def analyze_test_timeseries(
    name: str,
    time: list[float],
    strain: list[float],
    force: list[float],
    area: float,
    E: float | None = None,
    R: float = -1.0,
    already_true: bool = False,
    failure_pct: float = 30.0,
    material: str | None = None,
) -> dict:
    """Reduce one strain-controlled test from a (time, strain, force) series.

    Converts engineering -> true stress/strain (unless already_true), detects
    cycles, computes per-cycle metrics, and returns the stabilized (half-life)
    summary. The full per-cycle table is saved to the store under ``name`` and
    can be recalled with ``recall_result(name, "per_cycle")``.

    Use this for small inline series; for large data use ``analyze_test_csv``.
    """
    return _service.analyze_timeseries(
        name, time, strain, force, area, E=E, R=R, already_true=already_true,
        failure_pct=failure_pct, material=material,
    )


@mcp.tool()
def analyze_test_csv(
    name: str,
    csv_path: str,
    area: float,
    column_map: dict[str, str] | None = None,
    E: float | None = None,
    R: float = -1.0,
    already_true: bool = False,
    failure_pct: float = 30.0,
    material: str | None = None,
) -> dict:
    """Reduce one test from a CSV file (preferred for large series).

    ``column_map`` maps source column names to the canonical ``time``/``strain``/
    ``force`` (e.g. {"Axial Strain": "strain"}). Returns the half-life summary
    and persists the per-cycle table under ``name``.
    """
    return _service.analyze_csv(
        name, csv_path, area, column_map=column_map, E=E, R=R,
        already_true=already_true, failure_pct=failure_pct, material=material,
    )


@mcp.tool()
def fit_strain_life(
    total_strain_amp: list[float],
    stress_amp: list[float],
    reversals: list[float],
    E: float,
    plastic_strain_amp: list[float] | None = None,
    min_plastic_strain: float | None = None,
    refine_nonlinear: bool = False,
    material: str | None = None,
) -> dict:
    """Fit strain-life constants from per-test reduced data.

    Returns Basquin (σ'_f, b), Coffin-Manson (ε'_f, c), Ramberg-Osgood (K', n'),
    the transition life, and a Masing consistency check. ``min_plastic_strain``
    excludes near-runout points from the plastic branch. If ``material`` is
    given, the fit is saved for recall.
    """
    return _service.fit_strain_life(
        total_strain_amp, stress_amp, reversals, E,
        plastic_strain_amp=plastic_strain_amp, min_plastic_strain=min_plastic_strain,
        refine_nonlinear=refine_nonlinear, material=material,
    )


@mcp.tool()
def predict_life(
    total_strain_amp: float, sigma_f: float, b: float, eps_f: float, c: float, E: float
) -> dict:
    """Predict reversals and cycles to failure for a total strain amplitude.

    Inverts the combined Basquin + Coffin-Manson strain-life equation.
    """
    return _service.predict_life(total_strain_amp, sigma_f, b, eps_f, c, E)


@mcp.tool()
def mean_stress_equivalent_stress(
    stress_amp: float,
    mean_stress: float,
    model: str = "swt",
    sigma_f: float | None = None,
    gamma: float | None = None,
    sigma_u: float | None = None,
) -> dict:
    """Equivalent fully-reversed stress amplitude under a mean-stress model.

    ``model`` is one of none, morrow, swt, walker. Morrow needs ``sigma_f``;
    Walker needs ``gamma`` (or ``sigma_u`` to estimate it for steel).
    """
    return _service.mean_stress_equivalent_stress(
        stress_amp, mean_stress, model, sigma_f=sigma_f, gamma=gamma, sigma_u=sigma_u
    )


@mcp.tool()
def recall_result(key: str, quantity: str) -> dict:
    """Recall a previously computed result (e.g. a test summary or a fit).

    ``quantity`` is one of ``summary``, ``per_cycle``, ``strain_life_fit``.
    Returns the stored value plus any artifact paths, or an error message.
    """
    rec = _service.recall(key, quantity)
    if rec is None:
        return {"error": f"no result for key={key!r}, quantity={quantity!r}"}
    return rec


@mcp.tool()
def list_results(key: str | None = None) -> list[dict]:
    """List stored results (optionally filtered to one test/material key)."""
    return _service.list_results(key)


@mcp.resource("lcf://results/{key}/{quantity}")
def result_resource(key: str, quantity: str) -> str:
    """Expose a stored result as a readable resource (JSON)."""
    rec = _service.recall(key, quantity)
    return json.dumps(rec if rec is not None else {"error": "not found"}, indent=2)


def main() -> None:
    """Console entry point: run the stdio MCP server."""
    mcp.run(transport="stdio")


if __name__ == "__main__":  # pragma: no cover
    main()
