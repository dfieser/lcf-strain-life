"""Regression tests for the Phase 2 critical-review fixes.

Each test pins a bug found in the adversarial audit so it cannot return.
"""

import asyncio
import json

import numpy as np
import pytest

from lcf import counting, damage, hightemp, meanstress, notch, stats
from lcf.models import MeanStressModel


# --- JSON safety at the MCP boundary (CRITICAL) -----------------------------
def test_all_mcp_tools_return_valid_json(tmp_path, monkeypatch):
    """Dispatch each tool through FastMCP and strict-parse the text result.

    Strict parsing rejects bare NaN and Infinity, so this catches non-finite
    leaks that the internal dumps helper would otherwise mask.
    """
    monkeypatch.setenv("LCF_STORE_DIR", str(tmp_path / "store"))
    import importlib

    from lcf import mcp_server
    importlib.reload(mcp_server)

    def strict(text):
        return json.loads(text, parse_constant=lambda c: (_ for _ in ()).throw(
            ValueError(f"non-finite token {c}")))

    calls = {
        # pulsating-tension test: valley stress 0 makes r_tc NaN, which must
        # serialize as null. E is supplied so no modulus estimation is needed.
        "analyze_test_timeseries": dict(
            name="t",
            time=list(range(9)),
            strain=[0, 0.01, 0, 0.01, 0, 0.01, 0, 0.01, 0],
            force=[0, 3000, 0, 3000, 0, 3000, 0, 3000, 0],
            area=10.0, E=200000.0, already_true=True,
        ),
        # Walker with a compressive cycle, a non-finite-prone path
        "mean_stress_equivalent_stress": dict(
            stress_amp=100.0, mean_stress=-100.0, model="swt"),
        "predict_life": dict(total_strain_amp=10.0, sigma_f=1000.0, b=-0.09,
                             eps_f=0.5, c=-0.6, E=200000.0),
        "compute_damage": dict(counts=[1], lives=[1e9]),
    }
    for name, args in calls.items():
        result = asyncio.run(mcp_server.mcp.call_tool(name, args))
        # FastMCP returns (content, structured) or a content list across versions
        content = result[0] if isinstance(result, tuple) else result
        text = content[0].text
        strict(text)  # must not raise


# --- counting NaN guard (HIGH) ----------------------------------------------
def test_rainflow_rejects_nan():
    with pytest.raises(ValueError, match="NaN"):
        counting.count_rainflow([1.0, 5.0, float("nan"), 9.0, 2.0])


# --- stats degenerate guards (MEDIUM) ---------------------------------------
def test_fit_log_life_rejects_equal_amplitudes():
    with pytest.raises(ValueError, match="distinct"):
        stats.fit_log_life([0.01, 0.01, 0.01, 0.01], [1e5, 2e5, 1.5e5, 3e5])


def test_censored_mle_all_censored_raises_or_finite():
    # all-censored is pathological; must not silently return junk
    try:
        fit = stats.fit_log_life_censored([0.01, 0.006, 0.003], [1e5, 1e5, 1e5],
                                          [True, True, True])
    except ValueError:
        return
    assert np.isfinite(fit.slope)


# --- hightemp validation (MEDIUM) -------------------------------------------
def test_interpolate_rejects_nonpositive_coefficient():
    with pytest.raises(ValueError, match="positive"):
        hightemp.interpolate_constants({"T": [20, 400], "sigma_f": [1000, -5]}, 200)


def test_interpolate_rejects_duplicate_temperatures():
    with pytest.raises(ValueError, match="distinct"):
        hightemp.interpolate_constants({"T": [20, 20, 400], "E": [1, 2, 3]}, 100)


# --- damage validation (MEDIUM) ---------------------------------------------
def test_corten_dolan_rejects_negative_stress():
    with pytest.raises(ValueError, match="positive"):
        damage.corten_dolan([1, 1], [-100, 200], [1e4, 1e5], d=2.5)


# --- meanstress Walker guard ------------------------------------------------
def test_walker_rejects_gamma_above_one():
    with pytest.raises(ValueError, match="gamma"):
        meanstress.equivalent_fully_reversed_stress(
            100.0, -100.0, MeanStressModel.WALKER, gamma=1.5)


# --- notch Kf guard ---------------------------------------------------------
def test_kf_rejects_zero_radius():
    with pytest.raises(ValueError, match="radius"):
        notch.kf_peterson(3.0, 0.1, 0.0)
    with pytest.raises(ValueError, match="radius"):
        notch.kf_neuber(3.0, 0.25, 0.0)
