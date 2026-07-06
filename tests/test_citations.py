"""The citation registry: every method maps to a published source."""

from __future__ import annotations

from lcf import citations


def test_every_entry_has_method_and_citation():
    assert citations.CITATIONS, "registry must not be empty"
    for key, entry in citations.CITATIONS.items():
        assert entry.get("method"), key
        assert entry.get("citation"), key


def test_filter_matches_key_method_and_citation_text():
    assert "rainflow" in citations.get_citations("rainflow")
    # matches method text
    assert citations.get_citations("mean-stress")
    # matches citation text
    assert citations.get_citations("Technometrics")
    # no match returns empty, not an error
    assert citations.get_citations("zzz-no-such-topic") == {}


def test_registry_covers_the_new_features():
    for key in (
        "estimate_medians", "estimate_uniform_material_law",
        "estimate_universal_slopes", "estimate_modified_universal_slopes",
        "estimate_hardness", "generalized_esd", "grubbs_test",
        "racetrack_filter", "level_crossing_counting", "peak_counting",
        "sn_knee_haibach", "fatemi_socie", "brown_miller",
        "frequency_modified_coffin_manson", "corten_dolan",
    ):
        assert key in citations.CITATIONS, key


def test_withdrawn_standard_is_labeled():
    entry = citations.CITATIONS["log_life_regression"]
    assert "withdrawn" in entry["citation"].lower()
