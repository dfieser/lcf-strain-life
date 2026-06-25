"""Smoke tests for the MCP server: tools/resources register and dispatch."""

import asyncio

import pytest


def test_server_imports_and_names():
    from lcf import mcp_server
    assert mcp_server.mcp.name == "lcf-strain-life"


def test_expected_tools_registered():
    from lcf import mcp_server
    tools = asyncio.run(mcp_server.mcp.list_tools())
    names = {t.name for t in tools}
    expected = {
        "analyze_test_timeseries", "analyze_test_csv", "fit_strain_life",
        "predict_life", "mean_stress_equivalent_stress", "recall_result",
        "list_results",
        # Phase 2
        "count_rainflow", "compute_spectrum_life", "compute_damage",
        "compute_notch_local", "fit_design_curve", "compute_creep_fatigue",
    }
    assert expected <= names


def test_tools_have_descriptions_and_schemas():
    from lcf import mcp_server
    tools = asyncio.run(mcp_server.mcp.list_tools())
    for t in tools:
        assert t.description  # docstring -> description
        assert t.inputSchema  # generated JSON schema


def test_resource_registered():
    from lcf import mcp_server
    templates = asyncio.run(mcp_server.mcp.list_resource_templates())
    uris = {t.uriTemplate for t in templates}
    assert "lcf://results/{key}/{quantity}" in uris


def test_fit_tool_callable_directly(sae1137):
    """The decorated tool function remains directly callable (golden check)."""
    from lcf import mcp_server
    g = sae1137
    res = mcp_server.fit_strain_life(
        list(g.total_strain_amp), list(g.stress_amp), list(g.reversals),
        g.ref["E_nominal"], plastic_strain_amp=list(g.plastic_strain_amp),
        min_plastic_strain=5e-4,
    )
    assert res["coffin_manson"]["c"] == pytest.approx(g.ref["c"], abs=0.04)
