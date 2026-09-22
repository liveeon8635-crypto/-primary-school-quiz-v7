import re
import subprocess

from changying.web.v1 import v1_html
from changying.web.v1_historical_teaching_view import (
    V1_HISTORICAL_TEACHING_VIEW_MARKER,
    patch_v1_historical_teaching_view,
)


def test_historical_teaching_view_is_read_only_and_role_safe():
    html = patch_v1_historical_teaching_view(v1_html())
    assert V1_HISTORICAL_TEACHING_VIEW_MARKER in html
    assert "/v1/teacher/history/students" in html
    assert "/v1/teacher/history/classrooms" in html
    assert "互动课堂历史" in html
    assert "查看课堂过程" in html
    assert "课堂复盘/讲义" in html
    assert "teacher-owned-assignment-recipient-snapshots" not in html
    assert "teacher-owned-completed-classroom-sessions" not in html
    assert "学生离班后的新档案内容" in html
    assert "sessionStorage.getItem('v717Token')" in html
    assert "localStorage.getItem('v717Token')" in html

    marker = f'<script id="{V1_HISTORICAL_TEACHING_VIEW_MARKER}-script">'
    fragment = html[html.index(marker):html.index("</script>", html.index(marker))]
    for verb in ("method:'POST'", "method:'PUT'", "method:'PATCH'", "method:'DELETE'"):
        assert verb not in fragment


def test_historical_teaching_view_script_is_valid_javascript():
    html = patch_v1_historical_teaching_view(v1_html())
    match = re.search(
        rf'<script id="{V1_HISTORICAL_TEACHING_VIEW_MARKER}-script">(?P<script>.*?)</script>',
        html,
        re.S,
    )
    assert match
    result = subprocess.run(
        ["node", "--check", "-"],
        input=match.group("script"),
        text=True,
        capture_output=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_historical_teaching_view_patch_is_idempotent():
    original = v1_html()
    once = patch_v1_historical_teaching_view(original)
    twice = patch_v1_historical_teaching_view(once)
    assert once == twice
    assert twice.count(V1_HISTORICAL_TEACHING_VIEW_MARKER) >= 1


def test_production_v1_contains_historical_teaching_view():
    from app import app  # noqa: F401
    from changying.web import v1 as v1_module

    html = v1_module.v1_html()
    assert V1_HISTORICAL_TEACHING_VIEW_MARKER in html
    assert "真实历史教学记录" in html
    assert "互动课堂历史" in html
    assert "/v1/teacher/history/students" in html
    assert "/v1/teacher/history/classrooms" in html
