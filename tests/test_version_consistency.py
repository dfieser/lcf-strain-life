"""The version has one source of truth and nothing may drift from it.

The source is ``__version__`` in ``src/lcf/__init__.py``. pyproject.toml reads
it at build time through hatch dynamic versioning, and the release script
syncs CITATION.cff. These tests fail CI if anyone reintroduces a second copy.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

import lcf

REPO = Path(__file__).resolve().parent.parent


def _repo_file(name: str) -> str | None:
    path = REPO / name
    if not path.exists():  # not present in an installed distribution
        return None
    return path.read_text(encoding="utf-8")


def test_version_is_semver():
    assert re.fullmatch(r"\d+\.\d+\.\d+", lcf.__version__)


def test_citation_file_matches_package_version():
    cff = _repo_file("CITATION.cff")
    if cff is None:
        pytest.skip("CITATION.cff not present, not a repository checkout")
    m = re.search(r"(?m)^version: (.+)$", cff)
    assert m, "CITATION.cff has no version field"
    assert m.group(1).strip() == lcf.__version__


def test_pyproject_has_no_second_version_copy():
    py = _repo_file("pyproject.toml")
    if py is None:
        pytest.skip("pyproject.toml not present, not a repository checkout")
    assert 'dynamic = ["version"]' in py
    assert re.search(r"(?m)^version = ", py) is None
    assert 'path = "src/lcf/__init__.py"' in py


def test_changelog_mentions_current_version():
    log = _repo_file("CHANGELOG.md")
    if log is None:
        pytest.skip("CHANGELOG.md not present, not a repository checkout")
    assert f"## [{lcf.__version__}]" in log, (
        "CHANGELOG.md has no section for the current version, the release "
        "script creates it"
    )
