from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

from changying.domain.assignments import assignment_mode_name, assignment_status


def test_assignment_mode_names_preserve_legacy_labels():
    assert assignment_mode_name("quiz") == "在线答题"
    assert assignment_mode_name("media") == "拍照/视频"
    assert assignment_mode_name("mixed") == "在线答题 + 拍照/视频"
    assert assignment_mode_name("unknown") == "在线答题"


def test_pending_and_overdue_assignment_statuses():
    pending = assignment_status("2026-09-14", now=datetime(2026, 9, 14, 15, 0, 0))
    assert pending == {
        "completed": False,
        "status": "未完成",
        "statusCode": "pending",
        "late": False,
        "overdue": False,
        "deadlinePassed": False,
    }

    overdue = assignment_status("2026-09-14", now=datetime(2026, 9, 14, 16, 0, 0))
    assert overdue["status"] == "逾期未交"
    assert overdue["statusCode"] == "overdue"
    assert overdue["overdue"] is True
    assert overdue["deadlinePassed"] is True


def test_completed_and_late_completed_assignment_statuses():
    on_time = SimpleNamespace(submitted_at=datetime(2026, 9, 14, 15, 0, 0))
    result = assignment_status("2026-09-14", on_time, now=datetime(2026, 9, 14, 16, 0, 0))
    assert result["completed"] is True
    assert result["status"] == "已完成"
    assert result["statusCode"] == "completed"
    assert result["late"] is False
    assert result["deadlinePassed"] is True

    late = SimpleNamespace(submitted_at=datetime(2026, 9, 14, 16, 0, 0))
    result = assignment_status("2026-09-14", late, now=datetime(2026, 9, 14, 16, 30, 0))
    assert result["status"] == "逾期完成"
    assert result["statusCode"] == "late_completed"
    assert result["late"] is True


def test_production_loader_installs_assignment_domain_rules():
    import app_v924 as legacy
    import changying.production  # noqa: F401
    from changying.domain.assignments import ASSIGNMENT_SUBMISSION_MODES

    assert legacy.ASSIGNMENT_SUBMISSION_MODES is ASSIGNMENT_SUBMISSION_MODES
    assert legacy.assignment_mode_name is assignment_mode_name
    assert legacy.assignment_status is assignment_status
