from changying.web.v1 import v1_html
from changying.web.v1_student_detail_visibility import (
    V1_STUDENT_DETAIL_VISIBILITY_MARKER,
    patch_v1_student_detail_visibility,
)


def rendered_html() -> str:
    return patch_v1_student_detail_visibility(v1_html())


def test_student_detail_no_longer_silently_truncates_loaded_record_arrays():
    html = rendered_html()

    assert V1_STUDENT_DETAIL_VISIBILITY_MARKER in html
    assert "suggestions.slice(0,4).map" not in html
    assert "assignments.slice(0,6).map" not in html
    assert "weak.slice(0,6).map" not in html
    assert "timeline.slice(0,10).map" not in html
    assert "suggestions.map" in html
    assert "assignments.map" in html
    assert "weak.map" in html
    assert "timeline.map" in html


def test_homepage_preview_remains_compact_while_student_detail_is_complete():
    html = rendered_html()

    assert "people.slice(0,6).map" in html


def test_student_detail_visibility_patch_is_idempotent_and_read_only():
    original = v1_html()
    once = patch_v1_student_detail_visibility(original)
    twice = patch_v1_student_detail_visibility(once)

    assert once == twice
    for verb in ("method:'POST'", 'method:"POST"', "method:'PUT'", "method:'DELETE'"):
        assert once.count(verb) == original.count(verb)


def test_native_student_detail_shows_learning_context_dates_scores_and_real_timeline():
    html = rendered_html()

    assert "const learningTimeline=assignments.map" in html
    assert "title:(x.completed?'完成：':'布置：')" in html
    assert "x.subject||paper.subject" in html
    assert "x.textbook||paper.textbook" in html
    assert "assigned?'布置 '+assigned" in html
    assert "x.dueDate?'截止 '+x.dueDate" in html
    assert "submitted?'提交 '+submitted" in html
    assert "x.score!==null&&x.score!==undefined?'成绩 '+x.score+'分'" in html
    assert "qn?'题量 '+qn+'题'" in html
