"""Racetrack filter, level-crossing and peak counting, and S-N knee variants.

The level-crossing and peak counters follow the conventions of ASTM E1049-85
sections 5.2 and 5.3. The test cases here are hand-derived, small enough to
verify by inspection.
"""

from __future__ import annotations

import numpy as np
import pytest

from lcf import counting, damage
from lcf.service import LcfService


# --- racetrack filter -----------------------------------------------------------
def test_racetrack_keeps_large_reversals_drops_small():
    # large square wave with a small ripple riding on it
    series = [0.0, 10.0, 9.5, 10.5, -10.0, -9.4, -10.2, 10.0, 0.0]
    idx, vals = counting.racetrack_filter(series, gate=2.0)
    # the ripples (1.0 and 0.8 swings) disappear, the big reversals stay
    assert np.all(np.abs(np.diff(vals))[1:-1] >= 2.0)
    assert vals.max() >= 10.0 and vals.min() <= -10.0
    # indices refer to the original series
    assert all(series[int(i)] == pytest.approx(v) for i, v in zip(idx, vals))


def test_racetrack_zero_gate_is_turning_points():
    series = [0.0, 1.0, -1.0, 2.0, -2.0]
    idx, vals = counting.racetrack_filter(series, gate=0.0)
    pts = list(counting.reversals(series))
    assert list(idx) == [p[0] for p in pts]


def test_racetrack_negative_gate_rejected():
    with pytest.raises(ValueError, match="gate"):
        counting.racetrack_filter([0.0, 1.0], gate=-1.0)


# --- level crossing --------------------------------------------------------------
def test_level_crossings_hand_case():
    # signal: 0 -> 3 -> -1 -> 2 -> -2 -> 1
    series = [0.0, 3.0, -1.0, 2.0, -2.0, 1.0]
    df = counting.count_level_crossings(
        series, levels=[-1.5, -0.5, 0.5, 1.5, 2.5], ref=0.0
    )
    counts = dict(zip(df["level"], df["count"]))
    # positive-slope crossings: level 0.5 crossed by 0->3, -1->2, -2->1
    assert counts[0.5] == 3
    # level 1.5 crossed upward by 0->3 and -1->2
    assert counts[1.5] == 2
    # level 2.5 crossed upward only by 0->3
    assert counts[2.5] == 1
    # negative-slope crossings below ref: level -0.5 crossed by 3->-1 and 2->-2
    assert counts[-0.5] == 2
    # level -1.5 crossed downward only by 2->-2
    assert counts[-1.5] == 1


def test_level_crossings_rejects_nan():
    with pytest.raises(ValueError, match="NaN"):
        counting.count_level_crossings([0.0, float("nan"), 1.0])


# --- peak counting ----------------------------------------------------------------
def test_peak_count_hand_case():
    series = [0.0, 3.0, -1.0, 2.0, -2.0, 1.0, 0.0]
    df = counting.count_peaks(series, ref=0.0)
    peaks = df[df["kind"] == "peak"]["value"].tolist()
    valleys = df[df["kind"] == "valley"]["value"].tolist()
    assert sorted(peaks) == [1.0, 2.0, 3.0]
    assert sorted(valleys) == [-2.0, -1.0]


# --- S-N curve knee variants -------------------------------------------------------
def test_sn_life_above_knee_all_variants_agree():
    for variant in ("original", "elementary", "haibach"):
        lives = damage.sn_curve_life([200.0], k=5.0, sd=100.0, nd=1e6,
                                     variant=variant)
        assert lives[0] == pytest.approx(1e6 * 2.0**-5.0)


def test_sn_life_below_knee_variants():
    s = [50.0]  # half the knee stress
    orig = damage.sn_curve_life(s, k=5.0, sd=100.0, nd=1e6, variant="original")
    elem = damage.sn_curve_life(s, k=5.0, sd=100.0, nd=1e6, variant="elementary")
    haib = damage.sn_curve_life(s, k=5.0, sd=100.0, nd=1e6, variant="haibach")
    assert np.isinf(orig[0])
    assert elem[0] == pytest.approx(1e6 * 0.5**-5.0)          # 3.2e7
    assert haib[0] == pytest.approx(1e6 * 0.5**-9.0)          # 5.12e8
    # haibach lies between original (infinite) and elementary (shortest)
    assert elem[0] < haib[0] < orig[0]


def test_sn_life_validates():
    with pytest.raises(ValueError, match="variant"):
        damage.sn_curve_life([50.0], k=5.0, sd=100.0, nd=1e6, variant="fkm")
    with pytest.raises(ValueError, match="positive"):
        damage.sn_curve_life([50.0], k=-1.0, sd=100.0, nd=1e6)


# --- service integration -------------------------------------------------------------
@pytest.fixture()
def svc(tmp_path):
    return LcfService(tmp_path / "store")


def test_service_rainflow_gate_prefilter(svc):
    # the E1049 example sequence with a small ripple inserted
    series = [-2.0, 1.0, 0.8, 1.1, -3.0, 5.0, -1.0, 3.0, -4.0, 4.0, -2.0]
    plain = svc.count_rainflow("g0", series)
    gated = svc.count_rainflow("g1", series, gate=1.0)
    assert gated["n_cycles"] < plain["n_cycles"]
    assert gated["max_range"] == pytest.approx(plain["max_range"])
    # gated indices still point into the original series
    df = svc.store.get_dataframe("g1", "rainflow")
    assert df["i_end"].max() <= len(series) - 1


def test_service_level_and_peak_counts_persist(svc):
    series = [0.0, 3.0, -1.0, 2.0, -2.0, 1.0, 0.0]
    lc = svc.count_level_crossings("h", series, levels=[0.5], ref=0.0)
    assert lc["total_crossings"] == 3
    pk = svc.count_peaks("h", series, ref=0.0)
    assert pk["n_peaks"] == 3 and pk["n_valleys"] == 2
    assert svc.store.get_dataframe("h", "level_crossings") is not None
    assert svc.store.get_dataframe("h", "peaks") is not None


def test_service_sn_life_json_safe_inf(svc):
    out = svc.compute_sn_life([200.0, 50.0], k=5.0, sd=100.0, nd=1e6,
                              variant="original")
    # infinite life below the knee must serialize as null, not Infinity
    assert out["lives"][1] is None
    from lcf.store import dumps
    dumps(out)  # must not raise