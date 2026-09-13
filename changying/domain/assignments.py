"""Pure assignment-domain rules extracted from the legacy application."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from changying.utils.datetime_tools import due_deadline_utc


ASSIGNMENT_SUBMISSION_MODES = {"quiz", "media", "mixed"}


def assignment_mode_name(mode: str) -> str:
    return {
        "quiz": "在线答题",
        "media": "拍照/视频",
        "mixed": "在线答题 + 拍照/视频",
    }.get(mode, "在线答题")


def assignment_status(due_date: str, submission: Any = None, now: datetime | None = None) -> dict:
    """Return the legacy assignment completion/deadline status payload."""
    deadline = due_deadline_utc(due_date)
    now = now or datetime.utcnow()
    completed = bool(submission)
    late = bool(completed and deadline and submission.submitted_at > deadline)
    overdue = bool((not completed) and deadline and now > deadline)

    if completed:
        status = "逾期完成" if late else "已完成"
        code = "late_completed" if late else "completed"
    else:
        status = "逾期未交" if overdue else "未完成"
        code = "overdue" if overdue else "pending"

    return {
        "completed": completed,
        "status": status,
        "statusCode": code,
        "late": late,
        "overdue": overdue,
        "deadlinePassed": bool(deadline and now > deadline),
    }


__all__ = ["ASSIGNMENT_SUBMISSION_MODES", "assignment_mode_name", "assignment_status"]
