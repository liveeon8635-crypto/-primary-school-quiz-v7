import re
import subprocess

from changying.web.v1 import v1_html
from changying.web.v1_transition_plan_view import (
    V1_TRANSITION_PLAN_VIEW_MARKER,
    patch_v1_transition_plan_view,
)


def test_transition_plan_view_exposes_existing_persistent_plan_api():
    html = patch_v1_transition_plan_view(v1_html())

    assert V1_TRANSITION_PLAN_VIEW_MARKER in html
    assert "/transition-plans" in html
    assert "教师确认的衔接计划" in html
    assert "确认并保存衔接计划" in html
    assert "关闭计划" in html
    assert "只有教师或管理员可保存/关闭衔接计划" in html
    assert "由教师确认后记录在下方衔接计划中" in html
    assert "未来每一步都引用同一个 student_id" not in html


def test_transition_plan_view_keeps_explicit_human_confirmation():
    html = patch_v1_transition_plan_view(v1_html())

    assert "if(!confirm('确认把这份教师衔接计划写入该学生的连续档案？'))return" in html
    assert "if(!confirm('确认关闭这条衔接计划？关闭后仍保留历史记录。'))return" in html
    assert "session.role==='teacher'||session.role==='admin'" in html
    assert "系统只展示事实与已有证据，不自动生成升学分流或能力结论" in html


def test_transition_plan_view_script_is_valid_javascript():
    html = patch_v1_transition_plan_view(v1_html())
    match = re.search(
        rf'<script id="{V1_TRANSITION_PLAN_VIEW_MARKER}-script">(?P<script>.*?)</script>',
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


def test_transition_plan_view_escapes_persisted_content_before_html_rendering():
    html = patch_v1_transition_plan_view(v1_html())

    assert "esc(plan.transitionType" in html
    assert "items.map(x=>'<li>'+esc(x)+'</li>')" in html
    assert "esc(plan.previousStage)" in html
    assert "esc(plan.nextStageRequirement)" in html
    assert "esc(plan.nextStage)" in html


def test_production_v1_contains_transition_plan_view():
    from app import app  # noqa: F401
    from changying.web import v1 as v1_module

    html = v1_module.v1_html()
    assert V1_TRANSITION_PLAN_VIEW_MARKER in html
    assert "教师确认的衔接计划" in html
    assert "/v1/students/" in html
    assert "/transition-plans" in html



def test_snippet_no_longer_requires_main():
    from changying.web.v1_transition_plan_view import _SNIPPET

    assert "document.querySelector('#screen main');if(!main)return;" not in _SNIPPET
    assert "mountTP" in _SNIPPET
    assert "cy-transition-plan-section" in _SNIPPET
