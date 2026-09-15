import inspect

from changying.web.v1 import v1_html
from changying.web.v1_data_quality import patch_v1_html
from changying.web.v1_fast_path import V1_FAST_PATH_MARKER, _teacher_roster
from changying.web.v1_membership_reliability import (
    V1_MEMBERSHIP_RELIABILITY_MARKER,
    patch_v1_membership_reliability,
)
from changying.web.v1_membership_visibility import patch_v1_membership_visibility


def before_reliability() -> str:
    return patch_v1_membership_visibility(patch_v1_html(v1_html()))


def rendered_html() -> str:
    return patch_v1_membership_reliability(before_reliability())


def test_membership_read_failures_are_never_presented_as_confirmed_empty_data():
    html = rendered_html()

    assert V1_MEMBERSHIP_RELIABILITY_MARKER in html
    assert "当前学生统计可能不完整" in html
    assert "不代表这些教学归属没有学生" in html
    if V1_FAST_PATH_MARKER in html:
        # Aggregate roster reads are all-or-nothing at the HTTP boundary, so
        # per-class browser failures no longer exist. The final closure handles
        # top-level aggregate failures visibly instead.
        assert "/teacher/v1-roster" in html
        assert "学生列表读取失败：" in html
        assert "工作台读取失败：" in html
    else:
        assert "students:[],failed:true" in html
        assert "classRows.filter(item=>item.failed)" in html
        assert "window.__cyV1PeopleLoadWarnings=[]" in html


def test_partial_read_warning_renders_after_workspace_student_or_history_loads():
    html = rendered_html()

    assert "['/v1/workspace','/v1/student','/v1/history'].includes(path)" in html
    assert 'id="cy-v1-membership-warning"' in html
    assert "failures.slice(0,5)" in html
    assert "new MutationObserver(schedule)" in html
    assert "window.addEventListener('popstate',schedule)" in html


def test_reliability_keeps_complete_visible_membership_scope():
    html = rendered_html()

    assert "classes.slice(0,30)" not in html
    if V1_FAST_PATH_MARKER in html:
        source = inspect.getsource(_teacher_roster)
        assert "SchoolClass.teacher_id == user.id" in source
        assert "ClassStudent.class_id.in_(class_ids)" in source
        assert "if student.active is False" in source
        assert "key = str(student.id)" in source
    else:
        assert "for(let i=0;i<classes.length;i+=8)" in html
        assert "classes.slice(i,i+8).map" in html
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
