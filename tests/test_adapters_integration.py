"""Integration round-trips against installed pyLife and py-fatigue.

These tests build REAL objects from the target libraries and compare their
life evaluations against our closed-form Basquin inversion. They skip when
the libraries are not installed: pylife and py-fatigue are development-only
test dependencies, deliberately not runtime requirements of this package.
"""

from __future__ import annotations

import math

import pytest

from lcf import interchange

pylife = pytest.importorskip("pylife")
py_fatigue = pytest.importorskip("py_fatigue")

SIGMA_F = 900.0
B = -0.10


def _our_cycles(stress: float) -> float:
    """Basquin inverted for cycles: N = 0.5 * (S/sigma_f)^(1/b)."""
    return 0.5 * (stress / SIGMA_F) ** (1.0 / B)


def test_pylife_woehler_curve_reproduces_basquin():
    import pandas as pd
    import pylife.materiallaws  # noqa: F401 - registers the accessor

    doc = interchange.to_pylife_woehler(SIGMA_F, B, nd_cycles=1e6)
    series = pd.Series({k: doc[k] for k in ("k_1", "ND", "SD", "TN", "TS")})
    wc = series.woehler
    for stress in (300.0, 400.0, 500.0):
        assert float(wc.cycles(stress)) == pytest.approx(
            _our_cycles(stress), rel=1e-9
        )
    # the knee itself: pyLife returns ND at SD
    assert float(wc.cycles(doc["SD"])) == pytest.approx(1e6, rel=1e-9)


def test_py_fatigue_sn_curve_reproduces_basquin():
    from py_fatigue import SNCurve

    doc = interchange.to_py_fatigue_sn(SIGMA_F, B)
    sn = SNCurve(slope=doc["slope"], intercept=doc["intercept"])
    for stress in (300.0, 400.0, 500.0):
        assert float(sn.get_cycles(stress)) == pytest.approx(
            _our_cycles(stress), rel=1e-9
        )


def test_py_fatigue_mapping_math_standalone():
    doc = interchange.to_py_fatigue_sn(SIGMA_F, B)
    # log10 N = intercept - slope*log10 S evaluated by hand
    stress = 350.0
    log_n = doc["intercept"] - doc["slope"] * math.log10(stress)
    assert 10.0 ** log_n == pytest.approx(_our_cycles(stress), rel=1e-12)
