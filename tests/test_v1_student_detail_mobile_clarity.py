"""Regression tests for V1 mobile student-detail clarity.

These tests exercise the presentation-only visibility patch that removes
silent truncation caps from the already-fetched continuous student record on
the V1 student detail page.  They assert the patch is idempotent, that it
removes the detail caps, and that it leaves unrelated markup untouched.
"""

from __future__ import annotations

from changying.web.v1_student_detail_visibility import (
    V1_STUDENT_DETAIL_VISIBILITY_MARKER,
    patch_v1_student_detail_visibility,
)


_DETAIL_HTML = """
<html><body>
<div id="suggestions">{suggestions.slice(0,4).map(renderSuggestion)}</div>
<div id="assignments">{assignments.slice(0,6).map(renderAssignment)}</div>
<div id="weak">{weak.slice(0,6).map(renderWeak)}</div>
<div id="timeline">{timeline.slice(0,10).map(renderEvent)}</div>
</body></html>
"""


def test_patch_removes_detail_caps() -> None:
    patched = patch_v1_student_detail_visibility(_DETAIL_HTML)

    assert "suggestions.slice(0,4).map" not in patched
    assert "assignments.slice(0,6).map" not in patched
    assert "weak.slice(0,6).map" not in patched
    assert "timeline.slice(0,10).map" not in patched

    assert "suggestions.map" in patched
    assert "assignments.map" in patched
    assert "weak.map" in patched
    assert "timeline.map" in patched


def test_patch_is_idempotent() -> None:
    once = patch_v1_student_detail_visibility(_DETAIL_HTML)
    twice = patch_v1_student_detail_visibility(once)

    assert once == twice
    assert once.count(V1_STUDENT_DETAIL_VISIBILITY_MARKER) == 1


def test_patch_preserves_unrelated_markup() -> None:
    patched = patch_v1_student_detail_visibility(_DETAIL_HTML)

    assert "<div id=\"suggestions\">" in patched
    assert "<div id=\"timeline\">" in patched
    assert "</body>" in patched
