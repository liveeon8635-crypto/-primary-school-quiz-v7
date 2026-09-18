"""Regression tests for V1 mobile student-detail clarity.

These tests exercise the presentation-only visibility patch that removes
silent truncation caps from the already-fetched continuous student record on
the V1 student detail page.  They assert the patch is idempotent, that it
removes the detail caps, and that it leaves unrelated markup untouched.
"""

from __future__ import annotations

from changying.web.v1 import v1_html
from changying.web.v1_student_detail_visibility import (
    STUDENT_DETAIL_MOBILE_CSS_MARKER,
    V1_STUDENT_DETAIL_VISIBILITY_MARKER,
    patch_v1_student_detail_visibility,
)


_DETAIL_HTML = """
<html><body>
<section class="card student-head"><div class="student-meta"><span class="tag">监护人 ${s.parents?.length??'—'}</span></div></section>
<div class="card"><h2>需要关注 / 下一步教学</h2><div class="list" style="margin-top:12px">{suggestions.slice(0,4).map(renderSuggestion)}</div></div>
<div class="card"><h2>作业情况</h2><div class="list" style="margin-top:12px">{assignments.slice(0,6).map(renderAssignment)}</div></div>
<div class="card"><h2>薄弱内容 / 错题</h2><div class="list" style="margin-top:12px">{weak.slice(0,6).map(renderWeak)}</div></div>
<section><h2>历史时间线</h2><p>换班、换老师或升年级后仍保留在同一档案</p><div class="card"><div class="timeline">{timeline.slice(0,10).map(renderEvent)}</div></div></section>
</body></html>



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
    assert "家庭关联 · 监护人 ${s.parents?.length??'—'}" in patched
    assert "成长档案时间线" in patched
    assert "按时间倒序展示 · 最新记录在前" in patched
    assert "<h2>历史时间线</h2>" not in patched


def test_patch_is_idempotent() -> None:
    once = patch_v1_student_detail_visibility(_DETAIL_HTML)
    twice = patch_v1_student_detail_visibility(once)

    assert once == twice
    assert once.count(V1_STUDENT_DETAIL_VISIBILITY_MARKER) == 1
    assert once.count(STUDENT_DETAIL_MOBILE_CSS_MARKER) == 1


def test_patch_adds_mobile_long_record_overflow_guards() -> None:
    patched = patch_v1_student_detail_visibility(_DETAIL_HTML)

    assert "@media (max-width:640px)" in patched
    assert "#suggestions,#assignments,#weak,#timeline{min-width:0;max-width:100%;overflow-x:auto;" in patched
    assert "#suggestions>*,#assignments>*,#weak>*,#timeline>*{min-width:0;overflow-wrap:anywhere}" in patched
    assert 'id="suggestions"' in patched
    assert 'id="assignments"' in patched
    assert 'id="weak"' in patched
    assert 'id="timeline"' in patched
    assert patched.count(STUDENT_DETAIL_MOBILE_CSS_MARKER) == 1


def test_patch_preserves_unrelated_markup() -> None:
    patched = patch_v1_student_detail_visibility(_DETAIL_HTML)

    assert '<div id="suggestions" class="list"' in patched
    assert '<div id="timeline" class="timeline"' in patched
    assert "</body>" in patched


def test_mobile_overflow_guards_bind_to_real_v1_student_detail_dom() -> None:
    patched = patch_v1_student_detail_visibility(v1_html())

    for target_id in ("suggestions", "assignments", "weak", "timeline"):
        assert f'id="{target_id}"' in patched

    assert "suggestions.slice(0,4).map" not in patched
    assert "assignments.slice(0,6).map" not in patched
    assert "weak.slice(0,6).map" not in patched
    assert "timeline.slice(0,10).map" not in patched
