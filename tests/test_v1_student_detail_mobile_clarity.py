from changying.web.v1 import v1_html
from changying.web.v1_student_detail_mobile_clarity import (
    V1_STUDENT_DETAIL_MOBILE_CLARITY_MARKER,
    patch_v1_student_detail_mobile_clarity,
)


def rendered_html() -> str:
    return patch_v1_student_detail_mobile_clarity(v1_html())


def test_family_association_is_labeled_for_mobile_readability():
    html = rendered_html()

    assert V1_STUDENT_DETAIL_MOBILE_CLARITY_MARKER in html
    assert "data-cy-family-link" in html
    assert "家庭关联 · 监护人" in html


def test_growth_record_timeline_has_explicit_mobile_section_label():
    html = rendered_html()

    assert "成长档案 · 历史时间线" in html
    assert "手机端按时间倒序阅读" in html


def test_mobile_clarity_patch_is_idempotent_and_read_only():
    original = v1_html()
    once = patch_v1_student_detail_mobile_clarity(original)
    twice = patch_v1_student_detail_mobile_clarity(once)

    assert once == twice
    for verb in ("method:'POST'", 'method:"POST"', "method:'PUT'", "method:'DELETE'"):
        assert once.count(verb) == original.count(verb)
