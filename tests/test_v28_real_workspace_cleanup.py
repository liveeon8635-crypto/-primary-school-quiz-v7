import re
import subprocess

from changying.web.v1 import v1_html
from changying.web.v28_real_workspace_cleanup import (
    V28_REAL_WORKSPACE_CLEANUP_MARKER,
    patch_v28_real_workspace_cleanup,
)


def test_cleanup_targets_only_real_authenticated_workspaces():
    html = patch_v28_real_workspace_cleanup(v1_html())

    assert V28_REAL_WORKSPACE_CLEANUP_MARKER in html
    assert "return !!t && t!=='demo'" in html
    assert "if(location.pathname!='/v1/history'||!isReal())return" in html
    assert "if(location.pathname!='/v1/transition'||!isReal())return" in html


def test_history_cleanup_waits_for_real_history_panel():
    html = patch_v28_real_workspace_cleanup(v1_html())

    assert "cy-historical-teaching-section" in html
    assert "查询层级" in html
    assert "真实历史" in html
    assert "if(!main||!real)return" in html


def test_transition_cleanup_removes_old_placeholder_sections_and_adds_real_empty_state():
    html = patch_v28_real_workspace_cleanup(v1_html())

    assert "removeSectionByHeading(main,'衔接类型')" in html
    assert "removeSectionByHeading(main,'衔接流程')" in html
    assert "选择学生查看衔接事实" in html
    assert "不会使用演示占位数据替代真实学生记录" in html
    assert "请选择学生" in html


def test_demo_mode_still_keeps_original_demo_content():
    html = patch_v28_real_workspace_cleanup(v1_html())

    # The cleanup is runtime-gated. Demo source content remains available.
    assert "2025—2026（演示）" in html
    assert "结构占位" in html
    assert "t!=='demo'" in html


def test_cleanup_script_is_valid_javascript():
    html = patch_v28_real_workspace_cleanup(v1_html())
    match = re.search(
        rf'<script id="{V28_REAL_WORKSPACE_CLEANUP_MARKER}-script">(?P<script>.*?)</script>',
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


def test_cleanup_patch_is_idempotent():
    once = patch_v28_real_workspace_cleanup(v1_html())
    twice = patch_v28_real_workspace_cleanup(once)

    assert once == twice
    assert twice.count(V28_REAL_WORKSPACE_CLEANUP_MARKER) >= 1


def test_production_v1_installs_cleanup_after_real_panels():
    from app import app  # noqa: F401
    from changying.web import v1 as v1_module

    html = v1_module.v1_html()
    assert V28_REAL_WORKSPACE_CLEANUP_MARKER in html
    assert "cy-historical-teaching-section" in html
    assert "cy-transition-facts" in html
