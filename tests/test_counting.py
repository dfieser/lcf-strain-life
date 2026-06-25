"""Tests for lcf.counting, rainflow against the ASTM E1049 worked example.

Golden A and Golden B both use the sequence [-2, 1, -3, 5, -1, 3, -4, 4, -2],
the ASTM E1049 example. Golden B (Tom Irvine / vibrationdata) gives the exact
path cycles and binned totals used here as the regression baseline. See
docs/design/IMPLEMENTATION_REFERENCE_PHASE2.md section 1.5.
"""

from collections import Counter

import numpy as np
import pytest

from lcf import counting

ASTM = [-2, 1, -3, 5, -1, 3, -4, 4, -2]


def test_reversals_basic():
    rev = list(counting.reversals([0, 1, 0, 2, 0]))
    vals = [v for _, v in rev]
    assert vals == [0, 1, 0, 2, 0]  # all are turning points here


def test_reversals_collapses_flats():
    rev = list(counting.reversals([0, 2, 2, 2, 0]))
    vals = [v for _, v in rev]
    assert vals == [0, 2, 0]


def test_golden_b_astm_cycles():
    df = counting.count_rainflow(ASTM)
    got = sorted((round(r["range"], 3), r["count"], round(r["mean"], 3))
                 for _, r in df.iterrows())
    expected = sorted([
        (3.0, 0.5, -0.5),
        (4.0, 0.5, -1.0),
        (4.0, 1.0, 1.0),
        (8.0, 0.5, 1.0),
        (9.0, 0.5, 0.5),
        (8.0, 0.5, 0.0),
        (6.0, 0.5, 1.0),
    ])
    assert got == expected


def test_golden_b_binned_totals():
    df = counting.count_rainflow(ASTM)
    binned = Counter()
    for _, r in df.iterrows():
        binned[round(r["range"], 3)] += r["count"]
    assert binned == {3.0: 0.5, 4.0: 1.5, 6.0: 0.5, 8.0: 1.0, 9.0: 0.5}
    assert df["count"].sum() == pytest.approx(4.0)


def test_index_preservation_full_cycle():
    df = counting.count_rainflow(ASTM)
    full = df[df["count"] == 1.0].iloc[0]  # the E-F full cycle, range 4 mean 1
    assert (int(full["i_start"]), int(full["i_end"])) == (4, 5)
    assert ASTM[4] == -1 and ASTM[5] == 3


def test_amplitude_is_half_range():
    df = counting.count_rainflow(ASTM)
    np.testing.assert_allclose(df["amplitude"], df["range"] / 2.0)


def test_mean_stress_per_cycle():
    # strain drives counting, a paired stress signal supplies the mean
    strain = [0.0, 0.01, -0.01, 0.008, -0.008]
    stress = [0.0, 400.0, -380.0, 350.0, -360.0]
    df = counting.count_rainflow(strain)
    sm = counting.mean_stress_per_cycle(df, stress)
    assert sm.shape[0] == len(df)
    # each entry is the average stress at the two turning indices
    i0 = df["i_start"].to_numpy()
    i1 = df["i_end"].to_numpy()
    np.testing.assert_allclose(sm, 0.5 * (np.array(stress)[i0] + np.array(stress)[i1]))


def test_close_residue_repeats_history():
    closed = counting.count_rainflow(ASTM, close_residue=True)
    # the repeated history conserves the total and closes the largest range
    assert closed["count"].sum() == pytest.approx(4.0)
    big = closed[closed["range"] == closed["range"].max()]
    assert big["count"].sum() == pytest.approx(1.0)


def test_monotonic_is_one_half_cycle():
    df = counting.count_rainflow([0.0, 1.0, 2.0, 3.0])
    assert len(df) == 1
    assert df.iloc[0]["count"] == 0.5
    assert df.iloc[0]["range"] == pytest.approx(3.0)


def test_empty_and_single():
    assert len(counting.count_rainflow([])) == 0
    assert len(counting.count_rainflow([5.0])) == 0
