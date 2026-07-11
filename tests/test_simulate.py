"""Tests for lcf.simulate: Masing hysteresis simulation with material memory
and variable-amplitude strain-life (ADR-0016).

The validation here is internal consistency, per the ADR: constant amplitude
through the engine must reproduce the closed-form solvers exactly, closed
loops must match rainflow counting, and the memory rule must make an
interrupted branch indistinguishable from an uninterrupted one.
"""

from __future__ import annotations

import numpy as np
import pytest
from scipy import optimize

from lcf import counting, life, simulate
from lcf.service import LcfService

E = 200000.0
K = 1650.0     # cyclic strength coefficient, MPa
N_PRIME = 0.15
SIGMA_F = 900.0
B = -0.10
EPS_F = 0.60
C = -0.55


def ro_stress(eps_amp: float) -> float:
    """Independent Ramberg-Osgood inversion for the test's own reference."""
    return float(optimize.brentq(
        lambda s: s / E + (s / K) ** (1.0 / N_PRIME) - eps_amp, 0.0, 10 * K
    ))


# --------------------------------------------------------------------------- #
# hysteresis simulation
# --------------------------------------------------------------------------- #
def test_constant_amplitude_loops_land_on_cyclic_curve():
    amp = 0.008
    history = [amp, -amp] * 4
    sim = simulate.simulate_hysteresis(history, E=E, K_prime=K, n_prime=N_PRIME)
    assert len(sim.loops) == 4
    sigma_a = ro_stress(amp)
    for loop in sim.loops:
        assert loop.count == 1.0
        assert loop.strain_amp == pytest.approx(amp, rel=1e-9)
        assert loop.stress_mean == pytest.approx(0.0, abs=1e-6)
        assert loop.stress_amp == pytest.approx(sigma_a, rel=1e-6)
        assert loop.stress_max == pytest.approx(sigma_a, rel=1e-6)


def test_memory_interruption_is_invisible_afterwards():
    # An inner excursion (down to -0.002, back up to 0.006) must close and
    # leave the outer branch exactly where it would be without it.
    with_pause = simulate.simulate_hysteresis(
        [0.010, -0.002, 0.006, -0.010],
        E=E, K_prime=K, n_prime=N_PRIME, close_residue=False,
    )
    direct = simulate.simulate_hysteresis(
        [0.010, -0.010],
        E=E, K_prime=K, n_prime=N_PRIME, close_residue=False,
    )
    assert with_pause.path[-1][0] == pytest.approx(-0.010)
    assert with_pause.path[-1][1] == pytest.approx(direct.path[-1][1], rel=1e-9)
    # the interruption itself came out as one closed interior loop
    closed = [lp for lp in with_pause.loops if lp.count == 1.0]
    assert len(closed) == 1
    assert closed[0].strain_amp == pytest.approx(0.004, rel=1e-9)
    assert closed[0].strain_mean == pytest.approx(0.002, rel=1e-9)


def test_loops_match_rainflow_counting():
    # Aggregate counts per (range, mean): the counting module represents the
    # boundary cycle of a rotated history as two half cycles while the
    # simulator emits one full loop, the damage content must be identical.
    rng = np.random.default_rng(11)
    history = list(rng.uniform(-0.009, 0.011, size=40))
    sim = simulate.simulate_hysteresis(
        history, E=E, K_prime=K, n_prime=N_PRIME, close_residue=True
    )
    counted = counting.extract_cycles(history, close_residue=True)

    def agg(items):
        out: dict = {}
        for rng_, mean_, count_ in items:
            key = (rng_, mean_)
            out[key] = out.get(key, 0.0) + count_
        return out

    sim_agg = agg((round(2 * lp.strain_amp, 12), round(lp.strain_mean, 12),
                   lp.count) for lp in sim.loops)
    cnt_agg = agg((round(cy.rng, 12), round(cy.mean, 12), cy.count)
                  for cy in counted)
    assert sim_agg == pytest.approx(cnt_agg)


def test_raw_mode_reports_residue_as_half_cycles():
    sim = simulate.simulate_hysteresis(
        [0.002, -0.006, 0.010], E=E, K_prime=K, n_prime=N_PRIME,
        close_residue=False,
    )
    assert all(lp.count == 0.5 for lp in sim.loops)
    assert len(sim.loops) == 2


def test_simulation_refusals():
    with pytest.raises(ValueError, match="turning"):
        simulate.simulate_hysteresis([0.01], E=E, K_prime=K, n_prime=N_PRIME)
    with pytest.raises(ValueError):
        simulate.simulate_hysteresis(
            [0.01, float("nan")], E=E, K_prime=K, n_prime=N_PRIME
        )
    with pytest.raises(ValueError, match="positive"):
        simulate.simulate_hysteresis([0.01, -0.01], E=-1.0, K_prime=K,
                                     n_prime=N_PRIME)


def test_tiny_ranges_on_stiff_material_do_not_break_the_solver():
    # Regression: with a very low n' the plastic term underflows for tiny
    # strain ranges and the elastic-line bracket needs its safety margin.
    # These constants are the Conle SAE10B20 f512 values (in MPa).
    history = [0.010, -0.010, 1.0e-5, -1.0e-5, 0.010, -0.010]
    sim = simulate.simulate_hysteresis(
        history, E=206843.0, K_prime=813.6, n_prime=0.0586
    )
    assert len(sim.loops) >= 2


# --------------------------------------------------------------------------- #
# variable-amplitude life
# --------------------------------------------------------------------------- #
def _va(history, model="swt"):
    return simulate.variable_amplitude_life(
        history, E=E, K_prime=K, n_prime=N_PRIME,
        sigma_f=SIGMA_F, b=B, eps_f=EPS_F, c=C, mean_stress_model=model,
    )


def test_constant_amplitude_reproduces_closed_form_swt():
    amp = 0.008
    out = _va([amp, -amp])
    sigma_a = ro_stress(amp)
    reversals = life.predict_reversals_swt(
        sigma_a, amp, SIGMA_F, B, EPS_F, C, E
    )
    assert out["blocks_to_failure"] == pytest.approx(reversals / 2.0, rel=1e-6)


def test_constant_amplitude_reproduces_closed_form_uncorrected():
    amp = 0.006
    out = _va([amp, -amp], model="none")
    reversals = life.predict_reversals_from_total_strain(
        amp, SIGMA_F, B, EPS_F, C, E
    )
    assert out["blocks_to_failure"] == pytest.approx(reversals / 2.0, rel=1e-6)


def test_two_level_block_damage_is_miner_sum_without_mean_effect():
    # Under the mean-independent model the combined block's damage is the
    # exact Miner sum of the two constant-amplitude blocks.
    a1, a2 = 0.010, 0.005
    d1 = 1.0 / _va([a1, -a1], model="none")["blocks_to_failure"]
    d2 = 1.0 / _va([a2, -a2], model="none")["blocks_to_failure"]
    combined = _va([a1, -a1, a2, -a2], model="none")
    assert combined["damage_per_block"] == pytest.approx(d1 + d2, rel=1e-9)


def test_sequence_effect_small_loop_carries_mean_stress_under_swt():
    # The engine's point: inside the combined block the small cycle rides on
    # the big loop's branch and picks up a mean stress, so its SWT damage
    # differs from the standalone fully reversed cycle.
    a1, a2 = 0.010, 0.005
    combined = _va([a1, -a1, a2, -a2])
    small = min(combined["loops"], key=lambda g: g["strain_amp"])
    assert small["strain_amp"] == pytest.approx(a2, rel=1e-9)
    assert small["stress_mean"] != pytest.approx(0.0, abs=1e-3)
    d1 = 1.0 / _va([a1, -a1])["blocks_to_failure"]
    d2 = 1.0 / _va([a2, -a2])["blocks_to_failure"]
    assert combined["damage_per_block"] != pytest.approx(d1 + d2, rel=1e-4)


def test_tensile_mean_is_more_damaging_under_swt():
    # 0 to 0.010 cycling: same amplitude 0.005 as fully reversed, tensile mean
    offset = _va([0.010, 0.000])
    reversed_ = _va([0.005, -0.005])
    assert offset["loops"][0]["stress_mean"] > 0.0
    assert offset["blocks_to_failure"] < reversed_["blocks_to_failure"]


def test_compressive_loops_nondamaging_under_swt():
    # cycling entirely in compression: sigma_max < 0, SWT assigns no damage
    out = _va([-0.001, -0.009])
    assert out["damage_per_block"] == 0.0
    assert out["blocks_to_failure"] is None
    assert any("tensile" in n for n in out["notes"])


def test_identical_loops_are_aggregated():
    amp = 0.007
    out = _va([amp, -amp] * 5)
    assert len(out["loops"]) == 1
    assert out["loops"][0]["count"] == 5.0


# --------------------------------------------------------------------------- #
# service exposure and persistence
# --------------------------------------------------------------------------- #
def test_service_simulate_variable_amplitude(tmp_path):
    svc = LcfService(tmp_path / "store")
    out = svc.simulate_variable_amplitude(
        [0.008, -0.008, 0.004, -0.004], E=E, K_prime=K, n_prime=N_PRIME,
        sigma_f=SIGMA_F, b=B, eps_f=EPS_F, c=C, name="VA-demo",
    )
    assert out["n_loops"] == 2
    assert out["blocks_to_failure"] > 0
    assert any("validation status" in n for n in out["notes"])
    assert svc.recall("VA-demo", "va_life") is not None


# --------------------------------------------------------------------------- #
# published-case validation, gated on locally downloaded FD&E data
# --------------------------------------------------------------------------- #
import os

FDE_DIR = os.environ.get("LCF_FDE_DATA_DIR")


@pytest.mark.skipif(
    not FDE_DIR,
    reason="set LCF_FDE_DATA_DIR to a folder holding the FD&E histories "
    "(transmission.txt, bracket.txt, suspension.txt from "
    "fde.uwaterloo.ca, GPL) to run the Conle dataset validation",
)
@pytest.mark.parametrize("name,exp,lo,hi", [
    # experimental blocks from Conle's thesis Table 2 (faconle2.html) and
    # the prediction ratio band measured 2026-07-11. The upper bounds guard
    # against silent regression toward MORE non-conservative predictions.
    ("transmission", [50.0, 38.0], 0.5, 2.0),
    ("bracket", [4.39, 4.63], 0.5, 2.0),
    ("suspension", [50.3, 73.8, 83.8], 0.5, 4.0),
])
def test_conle_sae_dataset_prediction_band(name, exp, lo, hi):
    import math
    from pathlib import Path

    ksi = 6.894757
    vals = []
    for line in (Path(FDE_DIR) / f"{name}.txt").read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            vals.append(float(line.split(":")[0]))
    scale = 0.010 / max(abs(v) for v in vals)
    out = simulate.variable_amplitude_life(
        [v * scale for v in vals],
        E=30000.0 * ksi, K_prime=118.0 * ksi, n_prime=0.0586,
        sigma_f=123.2 * ksi, b=-0.0437, eps_f=2.0907, c=-0.7450,
    )
    geo_mean = math.exp(sum(math.log(v) for v in exp) / len(exp))
    ratio = out["blocks_to_failure"] / geo_mean
    assert lo <= ratio <= hi
