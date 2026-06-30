"""Tests for lcf.notch, including Golden E (SAE 1005 notched plate).

See dev/docs/design/IMPLEMENTATION_REFERENCE_PHASE2.md section 2a.5.
"""

import pytest

from lcf import notch

# SAE 1005 verified constants (Golden E)
SAE1005 = dict(E=207000.0, K=1240.0, n=0.27, sigma_f=886.0, b=-0.14, eps_f=0.28, c=-0.5)
KT = 2.53


def test_neuber_local_golden_e():
    sigma, strain = notch.neuber_local(100.0, KT, SAE1005["E"], SAE1005["K"], SAE1005["n"])
    assert sigma == pytest.approx(182.0, abs=1.0)
    assert strain == pytest.approx(0.00170, abs=2e-5)


def test_notch_local_life_golden_e():
    res = notch.notch_local_life(100.0, KT, **SAE1005, method="neuber")
    assert res["reversals"] == pytest.approx(1.08e5, rel=0.05)
    assert res["cycles"] == pytest.approx(res["reversals"] / 2.0)


def test_glinka_lower_strain_than_neuber():
    _, e_neuber = notch.neuber_local(100.0, KT, SAE1005["E"], SAE1005["K"], SAE1005["n"])
    _, e_glinka = notch.glinka_local(100.0, KT, SAE1005["E"], SAE1005["K"], SAE1005["n"])
    assert e_glinka < e_neuber


def test_glinka_predicts_longer_life():
    neu = notch.notch_local_life(100.0, KT, **SAE1005, method="neuber")
    gli = notch.notch_local_life(100.0, KT, **SAE1005, method="glinka")
    assert gli["reversals"] > neu["reversals"]  # less strain -> longer life


def test_neuber_range_is_double_the_amplitude():
    s, e = notch.neuber_local(100.0, KT, SAE1005["E"], SAE1005["K"], SAE1005["n"])
    ds, de = notch.neuber_local_range(200.0, KT, SAE1005["E"], SAE1005["K"], SAE1005["n"])
    assert ds == pytest.approx(2.0 * s, rel=1e-6)
    assert de == pytest.approx(2.0 * e, rel=1e-6)


def test_kf_peterson():
    assert notch.kf_peterson(3.0, 0.1, 0.5) == pytest.approx(1.0 + 2.0 / 1.2)


def test_kf_neuber():
    assert notch.kf_neuber(3.0, 0.25, 0.25) == pytest.approx(2.0)


def test_notch_sensitivity():
    assert notch.notch_sensitivity(3.0, 2.0) == pytest.approx(0.5)
    assert notch.notch_sensitivity(1.0, 1.0) == 0.0  # no concentration


def test_unknown_method_raises():
    with pytest.raises(ValueError, match="neuber"):
        notch.notch_local_life(100.0, KT, **SAE1005, method="bogus")


def test_neuber_elastic_limit():
    # at low nominal stress the response is elastic, so local stress approaches
    # Kt times nominal and local strain approaches stress over modulus
    sigma, strain = notch.neuber_local(5.0, KT, SAE1005["E"], SAE1005["K"], SAE1005["n"])
    assert sigma == pytest.approx(KT * 5.0, rel=1e-3)
    assert strain == pytest.approx(sigma / SAE1005["E"], rel=1e-3)
