from changying.web.v1 import v1_html
from changying.web.v1_data_quality import patch_v1_html
from changying.web.v1_membership_reliability import (
    V1_MEMBERSHIP_RELIABILITY_MARKER,
    patch_v1_membership_reliability,
)
from changying.web.v1_membership_visibility import patch_v1_membership_visibility


def before_reliability() -> str:
    return patch_v1_membership_visibility(patch_v1_html(v1_html()))


def rendered_html() -> str:
    return patch_v1_membership_reliability(before_reliability())


def test_partial_membership_reads_are_flagged_instead_of_silently_empty():
    html = rendered_html()

    assert V1_MEMBERSHIP_RELIABILITY_MARKER in html
    assert "students:[],failed:true" in html
    assert "classRows.filter(item=>item.failed)" in html
    assert "peopleLoadWarnings=[]" in html
    assert "当前学生统计可能不完整" in html
    assert "不代表这些教学归属没有学生" in html


def test_partial_read_warning_is_shown_on_workspace_and_student_index():
    html = rendered_html()

    assert html.count("${peopleLoadWarningHtml()}${duplicateAuditHtml(people)}") == 2
    assert "peopleLoadWarnings.slice(0,5)" in html


def test_reliability_patch_keeps_bounded_full_visibility_reads():
    html = rendered_html()

    assert "for(let i=0;i<classes.length;i+=8)" in html
    assert "classes.slice(i,i+8).map" in html
    assert "classes.slice(0,30)" not in html
    assert "if(x.active===false)continue" in html
    assert "const key=String(x.id)" in html


def test_reliability_patch_adds_no_new_write_methods():
    original = before_reliability()
    patched = rendered_html()

    for verb in ("method:'POST'", 'method:"POST"', "method:'PUT'", "method:'DELETE'", "method:'PATCH'"):
        assert patched.count(verb) == original.count(verb)


def test_reliability_patch_is_idempotent():
    once = rendered_html()
    twice = patch_v1_membership_reliability(once)

    assert twice == once
