"""Outlier screening: Grubbs, generalized ESD, and influence diagnostics.

Golden values come from the NIST/SEMATECH e-Handbook of Statistical Methods:

- Grubbs test example, section 1.3.5.17.1 (Tietjen-Moore uniformity data,
  G = 2.4687 with the 245.57 point flagged at the 5 percent level).
- Generalized ESD example, section 1.3.5.17.3 (Rosner's 54-point dataset,
  exactly 3 outliers at the 5 percent level).
"""

from __future__ import annotations

import numpy as np
import pytest

from lcf import stats
from lcf.service import LcfService

# Rosner (1983) example data as tabulated in the NIST handbook, 54 points.
ROSNER_DATA = [
    -0.25, 0.68, 0.94, 1.15, 1.20, 1.26, 1.26, 1.34, 1.38, 1.43, 1.49, 1.49,
    1.55, 1.56, 1.58, 1.65, 1.69, 1.70, 1.76, 1.77, 1.81, 1.91, 1.94, 1.96,
    1.99, 2.06, 2.09, 2.10, 2.14, 2.15, 2.23, 2.24, 2.26, 2.35, 2.37, 2.40,
    2.47, 2.54, 2.62, 2.64, 2.90, 2.92, 2.92, 2.93, 3.21, 3.26, 3.30, 3.59,
    3.68, 4.30, 4.64, 5.34, 5.42, 6.01,
]


# --- Grubbs -------------------------------------------------------------------
def test_grubbs_nist_example():
    values = [199.31, 199.53, 200.19, 200.82, 201.92, 201.95, 202.18, 245.57]
    out = stats.grubbs_test(values, alpha=0.05)
    assert out["statistic"] == pytest.approx(2.4687, abs=1e-3)
    assert out["index"] == 7
    assert out["outlier"] is True


def test_grubbs_clean_sample_not_flagged():
    rng = np.random.default_rng(42)
    values = rng.normal(100.0, 5.0, size=20)
    out = stats.grubbs_test(values, alpha=0.05)
    assert out["outlier"] is False


def test_grubbs_needs_three():
    with pytest.raises(ValueError, match="at least 3"):
        stats.grubbs_test([1.0, 2.0])


# --- generalized ESD ------------------------------------------------------------
def test_generalized_esd_rosner_golden():
    out = stats.generalized_esd(ROSNER_DATA, max_outliers=10, alpha=0.05)
    assert out["outlier_indices"] == [51, 52, 53]
    # the first three step statistics from the NIST worked example
    assert out["steps"][0]["statistic"] == pytest.approx(3.118, abs=2e-3)
    assert out["steps"][1]["statistic"] == pytest.approx(2.942, abs=2e-3)
    assert out["steps"][2]["statistic"] == pytest.approx(3.179, abs=2e-3)


def test_generalized_esd_small_sample_warns():
    out = stats.generalized_esd([1.0, 2.0, 1.5, 1.7, 1.6, 9.0, 1.4, 1.55],
                                max_outliers=1, alpha=0.05)
    assert any("n >= 15" in w for w in out["warnings"])
    assert out["outlier_indices"] == [5]


def test_generalized_esd_guards():
    with pytest.raises(ValueError, match="max_outliers"):
        stats.generalized_esd([1.0, 2.0, 3.0, 4.0], max_outliers=0)
    with pytest.raises(ValueError, match="too few"):
        stats.generalized_esd([1.0, 2.0, 3.0, 4.0], max_outliers=2)


# --- regression diagnostics -------------------------------------------------------
def test_regression_diagnostics_flags_corrupted_point():
    # a clean power law with one corrupted life value
    amps = [0.010, 0.008, 0.006, 0.005, 0.004, 0.003, 0.002, 0.0015]
    lives = [10.0 ** (1.0 - 2.0 * np.log10(a)) for a in amps]
    lives[3] *= 30.0  # corrupt one point
    diag = stats.regression_diagnostics(amps, lives)
    assert 3 in diag["influential_indices"]
    assert len(diag["cooks_distance"]) == len(amps)


# --- service-level flag_outliers ---------------------------------------------------
@pytest.fixture()
def svc(tmp_path):
    return LcfService(tmp_path / "store")


def test_flag_outliers_respects_runouts_and_maps_indices(svc):
    # 16 clean points on a line in log-log space plus one gross outlier,
    # with a runout inserted early to shift the index mapping
    rng = np.random.default_rng(7)
    amps, lives, censored = [], [], []
    for i, a in enumerate(np.geomspace(0.002, 0.02, 17)):
        n = 10.0 ** (0.5 - 1.8 * np.log10(a) + rng.normal(0.0, 0.01))
        amps.append(float(a))
        lives.append(float(n))
        censored.append(False)
    # index 1 is a runout, index 9 is corrupted
    censored[1] = True
    lives[9] *= 100.0
    out = svc.flag_outliers(amps, lives, censored=censored)
    assert out["runout_indices"] == [1]
    assert 9 in out["outlier_indices"]
    assert 1 not in out["outlier_indices"]
    assert out["citations"]


def test_flag_outliers_too_few_points_warns_not_crashes(svc):
    amps = [0.01, 0.005, 0.002]
    lives = [1e3, 1e4, 1e6]
    out = svc.flag_outliers(amps, lives)
    assert out["outlier_indices"] == []
    assert any("too few" in w for w in out["warnings"])


def test_flag_outliers_validates_lengths(svc):
    with pytest.raises(ValueError, match="same length"):
        svc.flag_outliers([0.01, 0.005], [1e3])
    with pytest.raises(ValueError, match="censored"):
        svc.flag_outliers([0.01, 0.005, 0.002], [1e3, 1e4, 1e5], censored=[True])
