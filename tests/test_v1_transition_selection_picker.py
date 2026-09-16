"""Regression tests for the V1 transition student picker usability fix.

These tests assert the source-level contract of the injected snippet:
- focus moves into the dialog when it opens
- Escape closes the dialog
- the temporary keydown listener is removed on close (no accumulation)
- focus is restored to the triggering button on close
"""

from __future__ import annotations

from changying.web import v1_transition_selection as mod


SNIPPET = mod._TRANSITION_SELECTION_SNIPPET


def test_picker_focuses_into_dialog_on_open():
    assert "firstFocusable.focus()" in SNIPPET
    assert "data-cy-picker-close" in SNIPPET


def test_picker_escape_closes_dialog():
    assert "e.key==='Escape'" in SNIPPET
    assert "closePicker()" in SNIPPET


def test_picker_removes_temporary_keydown_listener_on_close():
    assert "document.addEventListener('keydown',pickerKeyHandler,true)" in SNIPPET
    assert "document.removeEventListener('keydown',pickerKeyHandler,true)" in SNIPPET
    assert "pickerKeyHandler=null" in SNIPPET


def test_picker_restores_focus_to_trigger_on_close():
    assert "pickerTrigger=trigger||null" in SNIPPET
    assert "trigger.focus()" in SNIPPET
    assert "openStudentPicker(target)" in SNIPPET


def test_patch_is_idempotent_and_marks_html():
    html = "<html><body>V1 预留结构，尚未启用自动分析</body></html>"
    once = mod.patch_v1_transition_selection(html)
    twice = mod.patch_v1_transition_selection(once)
    assert once == twice
    assert mod.V1_TRANSITION_SELECTION_MARKER in once
