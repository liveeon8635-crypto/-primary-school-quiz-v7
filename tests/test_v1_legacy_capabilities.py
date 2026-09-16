import subprocess
import sys
import textwrap

from changying.web.v1_legacy_capabilities import (
    V1_LEGACY_CAPABILITIES_MARKER,
    _LEGACY_CAPABILITIES_SNIPPET,
)


def run_isolated(code: str) -> None:
    result = subprocess.run(
        [sys.executable, "-c", textwrap.dedent(code)],
        text=True,
        capture_output=True,
        timeout=45,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_final_v1_html_includes_unified_capability_center():
    run_isolated(
        """
        from fastapi.testclient import TestClient
        from app import app

        html = TestClient(app).get('/v1/workspace').text
        assert 'changying_v1_legacy_capabilities_v1' in html
        assert '完整功能中心' in html
        assert '同一数据 · 不丢功能' in html
        assert '/classic?legacy=1&page=' in html
        """
    )


def test_teacher_retained_capabilities_cover_legacy_core_menu():
    for page, label in (
        ("classes", "班级学生"),
        ("classPoints", "课堂积分"),
        ("ai", "AI 助手"),
        ("teaching", "定制教学"),
        ("resources", "教材教案"),
        ("catalog", "教材题库"),
        ("papers", "组卷作业"),
        ("analytics", "学情分析"),
        ("audit", "操作记录"),
        ("leaderboard", "排行榜"),
        ("account", "我的"),
    ):
        assert f"['{page}','{label}'" in _LEGACY_CAPABILITIES_SNIPPET


def test_student_parent_and_admin_capabilities_are_retained():
    for page in (
        "syncLearning",
        "rewards",
        "assignments",
        "wrongbook",
        "practice",
        "progress",
        "childLearning",
        "childRewards",
        "childProgress",
        "childAssignments",
        "subscription",
        "users",
        "pointsAdmin",
        "imports",
        "adminAudit",
        "system",
    ):
        assert f"['{page}'" in _LEGACY_CAPABILITIES_SNIPPET


def test_unification_does_not_pull_unrelated_commercial_operator_surface_into_v1():
    assert V1_LEGACY_CAPABILITIES_MARKER in _LEGACY_CAPABILITIES_SNIPPET
    for forbidden in (
        "operator/",
        "commercial/plans",
        "便利店",
        "健身",
        "AI 工作台",
    ):
        assert forbidden not in _LEGACY_CAPABILITIES_SNIPPET


def test_capability_links_keep_existing_classic_permission_boundary():
    assert "'/classic?legacy=1&page='" in _LEGACY_CAPABILITIES_SNIPPET
    assert "requestedDeepPage" not in _LEGACY_CAPABILITIES_SNIPPET
    assert "method:'POST'" not in _LEGACY_CAPABILITIES_SNIPPET
    assert 'method:"POST"' not in _LEGACY_CAPABILITIES_SNIPPET
