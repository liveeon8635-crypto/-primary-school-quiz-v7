from changying.web.v1 import v1_html
from changying.web.v1_fast_path import V1_FAST_PATH_MARKER
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
    assert "studentProfiles(10)" not in html
    assert "x.students.slice(0,8).map" not in html
    assert "links=[...document.querySelectorAll('a[data-student]')].slice(0,10)" not in html
    assert "rows.slice(0,12).map" not in html


def test_history_reads_all_currently_visible_students_without_browser_n_plus_one():
    html = rendered_html()

    if V1_FAST_PATH_MARKER in html:
        assert "readJson('/teacher/v1-profiles')" in html
        assert (
            "一次读取当前可见学生的连续档案摘要" in html
            or "汇总当前可见学生的历史教学与时间线记录。" in html
        )
        assert "readJson('/teacher/students/'+student.id+'/growth-profile')" not in html
    else:
        assert "const students=await visibleStudents();if(!students.length)return;" in html
        assert "mapBatches(students,6" in html
        assert "从全部当前可见学生的班级历史与时间线分批读取" in html
    assert (
        "已读取 ${esc(records.length)} 名当前可见学生" in html
        or "共 ${esc(records.length)} 名学生有可查看的连续档案摘要。" in html
    )


def test_full_visibility_keeps_protected_read_api_boundary():
    html = rendered_html()

    # After the V1 fast-path is installed, the browser uses authenticated
    # aggregate GETs instead of issuing one request per class/student.  The
    # older bounded readers remain the fallback contract when that later patch
    # is not installed.
    if V1_FAST_PATH_MARKER in html:
        for endpoint in (
            "/teacher/v1-roster",
            "/teacher/v1-bootstrap",
            "/teacher/v1-profiles",
        ):
            assert endpoint in html
        assert "api('/teacher/classes/'+c.id+'/students')" not in html
        assert "readJson('/teacher/classes/'+c.id+'/students')" not in html
    else:
        assert "mapBatches(use,8" in html
        assert "mapBatches(students,6" in html
        assert "readJson('/teacher/classes')" in html
        assert "readJson('/teacher/students/'+s.id+'/growth-profile')" in html
