from changying.web.v1 import v1_html
from changying.web import v1_operational
from changying.web.v1_operational import (
    V1_OPERATIONAL_MARKER,
    patch_v1_operational_html,
)


def test_operational_patch_connects_visible_cards_to_native_v1_capabilities():
    html = patch_v1_operational_html(v1_html())

    assert V1_OPERATIONAL_MARKER in html
    assert "/teacher/workbench-summary" in html
    assert "/teacher/classes" in html
    assert "/teacher/students/" in html
    assert "/growth-profile" in html
    # The operational layer itself must remain native/read-only.  The final V1
    # document may now also contain the separate retained-capability center,
    # which intentionally deep-links to mature Classic workflows.
    assert "/classic?legacy=1&page=" not in v1_operational._OPERATIONAL_SNIPPET
    assert ("在 V1 内打开" in html) or ("打开 →" in html)
    assert ("保持 V1 登录态，不再跳转旧系统" in html) or ("在当前页面查看教学信息" in html)
    assert "cy-feature-layer" in html
    assert "今日待办与主动提醒" in html
    assert "家长关联与教学连续性" in html
    assert ("真实历史摘要" in html) or ("历史教学摘要" in html)
    assert "当前档案事实" in html


def test_operational_patch_is_idempotent_and_added_snippet_is_read_only():
    once = patch_v1_operational_html(v1_html())
    twice = patch_v1_operational_html(once)

    assert twice == once
    assert once.count(V1_OPERATIONAL_MARKER) >= 2
    for write_method in ("method:'POST'", 'method:"POST"', "method:'PUT'", "method:'PATCH'", "method:'DELETE'"):
        assert write_method not in v1_operational._OPERATIONAL_SNIPPET


def test_operational_patch_keeps_student_record_as_transition_anchor():
    html = patch_v1_operational_html(v1_html())

    assert "档案 #" in html
    assert "不自动修改年级或班级" in html
    assert (
        "真正改变年级、学校或教学归属仍通过受权限保护的维护流程完成" in html
        or "年级、学校和教学归属不会在此自动变更" in html
    )


def test_operational_patch_removes_fixed_demo_year_from_real_history_view():
    html = patch_v1_operational_html(v1_html())

    assert "2025—2026（演示）" not in html
    assert "按现有档案时间线读取" in html


def test_operational_patch_uses_cache_and_parallel_reads_for_mobile_speed():
    html = patch_v1_operational_html(v1_html())

    assert "const cache=new Map()" in html
    assert "Promise.all" in html
    assert "requestIdleCallback" in html
    assert "cache:'no-store'" in html
