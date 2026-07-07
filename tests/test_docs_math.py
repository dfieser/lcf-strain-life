"""Display-math blocks in the shipped docs must survive Markdown rendering.

A ``$$ ... $$`` block whose continuation line begins with ``+``, ``-``, or
``*`` is fragile. Markdown renderers used to view these files, GitHub and the
VS Code preview among them, read that leading character as a list bullet. That
ends the math block early, and the rest of the LaTeX is then processed as
Markdown, so subscripts written with ``_`` turn into emphasis and the equation
renders as garbage. Keep every operator that starts a continuation line at the
end of the previous line instead. This test fails if the fragile pattern comes
back.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent

_BULLET_STARTS = ("+ ", "- ", "* ")


def _fragile_math_lines(text: str) -> list[tuple[int, str]]:
    """Return (line number, line) for each display-math continuation line that
    starts with a Markdown list marker."""
    bad: list[tuple[int, str]] = []
    in_math = False
    for lineno, line in enumerate(text.splitlines(), start=1):
        if in_math and line.lstrip()[:2] in _BULLET_STARTS:
            bad.append((lineno, line))
        if line.count("$$") % 2 == 1:
            in_math = not in_math
    return bad


def test_physics_review_math_is_render_safe():
    path = REPO / "docs" / "PHYSICS_REVIEW.md"
    if not path.exists():  # not present in an installed distribution
        pytest.skip("PHYSICS_REVIEW.md not present, not a repository checkout")
    bad = _fragile_math_lines(path.read_text(encoding="utf-8"))
    assert not bad, (
        "display-math continuation lines start with a Markdown list marker and "
        "will break when rendered: "
        + ", ".join(f"line {n}: {text.strip()!r}" for n, text in bad)
    )
