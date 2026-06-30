"""Tests for lcf.damage, including Golden C (DLDR) and Golden D (Miner).

See dev/docs/design/IMPLEMENTATION_REFERENCE_PHASE2.md sections 2.1, 2.2, 2.4.
"""

import numpy as np
import pytest

from lcf import damage


# --- Miner ------------------------------------------------------------------
def test_miner_basic_damage():
    r = damage.miner([10, 20], [1000, 5000])
    # 10/1000 + 20/5000 = 0.01 + 0.004 = 0.014
    assert r.damage == pytest.approx(0.014)
    assert r.blocks_to_failure == pytest.approx(1.0 / 0.014)


def test_miner_golden_d_block():
    # Golden D: a block with cumulative damage 0.057 -> about 17.5 blocks
    r = damage.miner([57], [1000])
    assert r.damage == pytest.approx(0.057)
    assert r.blocks_to_failure == pytest.approx(17.5438, rel=1e-3)


def test_miner_d_crit_half():
    r = damage.miner([1], [100], d_crit=0.5)
    assert r.blocks_to_failure == pytest.approx(0.5 / 0.01)


def test_miner_failed_flag():
    assert damage.miner([100], [50]).failed is True
    assert damage.miner([10], [1000]).failed is False


def test_miner_rejects_nonpositive_life():
    with pytest.raises(ValueError):
        damage.miner([1], [0])


# --- DLDR -------------------------------------------------------------------
def test_dldr_golden_c_accumulation():
    # Golden C: phase-I damage per block 0.2134, phase-II 0.1463 -> 11.5 blocks.
    # Feed phase lives that reproduce those per-block phase damages with count 1.
    counts = [1.0]
    n1 = [1.0 / 0.2134]
    n2 = [1.0 / 0.1463]
    r = damage.dldr_from_phase_lives(counts, n1, n2)
    assert r.blocks_to_failure == pytest.approx(4.686 + 6.835, rel=1e-3)
    assert r.blocks_to_failure == pytest.approx(11.52, rel=1e-2)


def test_manson_halford_phase_lives_properties():
    lives = np.array([1e3, 1e4, 1e5])
    n1, n2 = damage.manson_halford_phase_lives(lives)
    assert np.all(n1 > 0) and np.all(n2 > 0)
    assert np.all(n1 < lives) and np.all(n2 <= lives)
    # standard Manson-Halford: longer-life levels spend a larger fraction in
    # Phase I (the reverse of the earlier, incorrect parametric model)
    frac1 = n1 / lives
    assert frac1[2] > frac1[0]


def test_manson_halford_knee_matches_nasa_value():
    # NASA TM-87325: for N_short=1e3, N_long=1e5 the Phase I life is about 111
    n1, _ = damage.manson_halford_phase_lives([1e3, 1e5])
    assert n1[0] == pytest.approx(110.7, rel=1e-2)


def test_dldr_wrapper_runs():
    r = damage.dldr([10, 5], [1e4, 1e5])
    assert r.blocks_to_failure > 0
    assert r.rule == "dldr"


# --- Corten-Dolan -----------------------------------------------------------
def test_corten_dolan_reduces_to_miner():
    # S-N curve N = (sigma/sigma_f)**(1/b'); with d = 1/b' (inverse slope),
    # Corten-Dolan must equal Miner exactly.
    sigma_f, b = 1000.0, -0.1
    stresses = np.array([500.0, 400.0, 300.0])
    counts = np.array([100.0, 200.0, 700.0])
    lives = (stresses / sigma_f) ** (1.0 / b)  # N_f per level
    cd = damage.corten_dolan(counts, stresses, lives, d=-1.0 / b)
    mn = damage.miner(counts, lives)
    assert cd.cycles_to_failure == pytest.approx(mn.cycles_to_failure, rel=1e-9)


def test_corten_dolan_more_damaging_with_higher_exponent():
    stresses = np.array([500.0, 300.0])
    counts = np.array([100.0, 100.0])
    lives = np.array([1e4, 1e5])
    low = damage.corten_dolan(counts, stresses, lives, d=3.0).cycles_to_failure
    high = damage.corten_dolan(counts, stresses, lives, d=8.0).cycles_to_failure
    # a larger exponent makes the lower-stress cycles contribute less damage,
    # so the predicted life increases with d
    assert high > low
