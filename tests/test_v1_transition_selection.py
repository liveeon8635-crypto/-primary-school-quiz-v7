from changying.web.v1 import v1_html
from changying.web.v1_transition_selection import (
    V1_TRANSITION_SELECTION_MARKER,
    _TRANSITION_SELECTION_SNIPPET,
    patch_v1_transition_selection,
)


def test_transition_types_are_real_selectable_controls():
    html = patch_v1_transition_selection(v1_html())

    assert V1_TRANSITION_SELECTION_MARKER in html
    assert "cy-transition-selected" in html
    assert "aria-pressed" in html
    assert "sessionStorage.setItem" in html
    assert "e.stopImmediatePropagation()" in html
    assert "请选择一个衔接类型" in html


def test_transition_selection_keeps_persistence_boundary_honest():
    html = patch_v1_transition_selection(v1_html())

    assert "当前选择仅保存在本次浏览会话，尚未写入学生档案" in html
    assert "当前仅保存在本次浏览会话，不写入学生档案" in html
    for method in ("POST", "PUT", "PATCH", "DELETE"):
        assert f"method:'{method}'" not in _TRANSITION_SELECTION_SNIPPET
        assert f'method:"{method}"' not in _TRANSITION_SELECTION_SNIPPET


def test_transition_observer_cannot_watch_its_own_nested_note_mutations():
    # PR #66 originally observed the whole screen subtree. showChoice() inserts and
    # rewrites a note inside that subtree, which re-triggered MutationObserver and
    # could keep the mobile main thread in a render loop on /v1/transition.
    assert "observer.observe(root,{childList:true});" in _TRANSITION_SELECTION_SNIPPET
    assert "subtree:true" not in _TRANSITION_SELECTION_SNIPPET
    assert "if(note.textContent!==text)note.textContent=text" in _TRANSITION_SELECTION_SNIPPET


def test_transition_selection_patch_is_idempotent():
    once = patch_v1_transition_selection(v1_html())
    twice = patch_v1_transition_selection(once)

    assert once == twice
