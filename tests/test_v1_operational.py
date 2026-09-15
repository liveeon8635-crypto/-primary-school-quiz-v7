from changying.web.v1 import v1_html
from changying.web.v1_operational import (
    V1_OPERATIONAL_MARKER,
    patch_v1_operational_html,
)


def test_operational_patch_connects_visible_cards_to_real_capabilities():
    html = patch_v1_operational_html(v1_html())

    assert V1_OPERATIONAL_MARKER in html
    assert "/teacher/workbench-summary" in html
    assert "/teacher/students/" in html
    assert "/growth-profile" in html
    assert "/classic?legacy=1&page=" in html
    assert "点击进入可用功能" in html
    assert "今日待办与主动提醒" in html
    assert "家长关联与教学连续性" in html
    assert "真实历史摘要" in html
    assert "当前档案事实" in html


def test_operational_patch_is_idempotent_and_does_not_add_write_requests():
    once = patch_v1_operational_html(v1_html())
    twice = patch_v1_operational_html(once)

    assert twice == once
    assert once.count(V1_OPERATIONAL_MARKER) >= 2
    for write_method in ("method:'POST'", 'method:"POST"', "method:'PUT'", "method:'PATCH'", "method:'DELETE'"):
        assert write_method not in once


def test_operational_patch_keeps_student_record_as_transition_anchor():
    html = patch_v1_operational_html(v1_html())

    assert "档案 #" in html
    assert "不自动修改年级或班级" in html
    assert "真正改变年级、学校或教学归属仍沿用受权限保护的原系统操作" in html
