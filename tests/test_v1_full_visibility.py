from changying.web.v1 import v1_html
from changying.web.v1_full_visibility import (
    V1_FULL_VISIBILITY_MARKER,
    patch_v1_full_visibility,
)
from changying.web.v1_operational import patch_v1_operational_html
from changying.web.v1_school_facts import patch_v1_school_facts


def rendered_html() -> str:
    html = patch_v1_operational_html(v1_html())
    html = patch_v1_school_facts(html)
    return patch_v1_full_visibility(html)


def test_full_visibility_removes_demo_scale_caps_from_detail_panels():
    html = rendered_html()

    assert V1_FULL_VISIBILITY_MARKER in html
    assert "async function mapBatches(items,size,fn)" in html
    assert "studentProfiles(10)" not in html
    assert "x.students.slice(0,8).map" not in html
    assert "links=[...document.querySelectorAll('a[data-student]')].slice(0,10)" not in html
    assert "rows.slice(0,12).map" not in html


def test_history_reads_all_currently_visible_students_in_bounded_batches():
    html = rendered_html()

    assert "const students=await visibleStudents();if(!students.length)return;" in html
    assert "mapBatches(students,6" in html
    assert "从全部当前可见学生的班级历史与时间线分批读取" in html
    assert "已读取 ${esc(records.length)} 名当前可见学生" in html


def test_full_visibility_keeps_protected_read_api_boundary():
    html = rendered_html()

    for endpoint in (
        "/teacher/classes",
        "/teacher/classes/",
        "/teacher/students/",
        "/teacher/workbench-summary",
    ):
        assert endpoint in html

    # The V1 base shell legitimately POSTs to /login.  Scope this regression
    # test to the full-visibility behavior itself: it must keep using the
    # existing protected readers and bounded GET-style read helpers.
    assert "mapBatches(use,8" in html
    assert "mapBatches(students,6" in html
    assert "readJson('/teacher/classes')" in html
    assert "readJson('/teacher/students/'+s.id+'/growth-profile')" in html
