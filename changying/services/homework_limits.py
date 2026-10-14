"""Usage limits for the student side of the homework assistant.

Counted straight from ``ai_usage_logs`` (feature prefix ``homework_help_``) and ``help_requests``,
so no extra table is needed. Two values are meant to be tuned in production without a code change:

    HOMEWORK_STUDENT_DAILY_LIMIT   help requests per student per school day   (default 8)
    HOMEWORK_SCHOOL_HOURLY_LIMIT   student-side model calls per school per hour (default 300)

and one more protects the single web instance:

    HOMEWORK_AI_CONCURRENCY        student model calls running at the same time (default 8)

Every limit answers 429 with a friendly message that points at asking the teacher.
"""

from __future__ import annotations

import os
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, Iterator

from fastapi import HTTPException
from sqlalchemy import func, select

STUDENT_FEATURE_PREFIX = "homework_help_"
DEFAULT_STUDENT_DAILY_LIMIT = 8
DEFAULT_SCHOOL_HOURLY_LIMIT = 300
DEFAULT_CONCURRENCY = 8
CALLS_PER_REQUEST = 3  # recognise + explain + one re-check
PER_MINUTE_HELP_REQUESTS = 2
PER_MINUTE_CALLS = 6
SCHOOL_TZ = timezone(timedelta(hours=8))  # same school day as the rest of the app

TOO_BUSY = "现在使用的同学比较多，请稍等几秒再试，或者直接点“求助老师”。"
TODAY_DONE = "你今天的求助次数用完了，明天再来，或者直接问老师。"


def _env_int(name: str, default: int, low: int, high: int) -> int:
    try:
        value = int(os.getenv(name, "") or default)
    except ValueError:
        value = default
    return max(low, min(value, high))


def student_daily_limit() -> int:
    return _env_int("HOMEWORK_STUDENT_DAILY_LIMIT", DEFAULT_STUDENT_DAILY_LIMIT, 1, 100)


def school_hourly_limit() -> int:
    return _env_int("HOMEWORK_SCHOOL_HOURLY_LIMIT", DEFAULT_SCHOOL_HOURLY_LIMIT, 10, 5000)


def concurrency_limit() -> int:
    return _env_int("HOMEWORK_AI_CONCURRENCY", DEFAULT_CONCURRENCY, 1, 64)


def school_day_start_utc(now: datetime | None = None) -> datetime:
    """Start of the current school day (UTC+8 midnight) as the naive UTC the database stores."""
    local = (now or datetime.now(timezone.utc)).astimezone(SCHOOL_TZ)
    midnight = local.replace(hour=0, minute=0, second=0, microsecond=0)
    return midnight.astimezone(timezone.utc).replace(tzinfo=None)


def require_student_ai(implementation: Any, db: Any, user: Any) -> None:
    """The school must have switched AI on and allowed student content to be sent."""
    config = implementation.ai_config_for(db, user.school_id, False)
    if not config or not config.enabled or not config.allow_student_data:
        raise HTTPException(403, "学校管理员还没有开启这个功能，请先问老师")


def _count_calls(implementation: Any, db: Any, *, user_id: int | None, school_id: int, since: datetime) -> int:
    log = implementation.AIUsageLog
    query = select(func.count()).select_from(log).where(
        log.school_id == school_id,
        log.created_at >= since,
        log.feature.like(STUDENT_FEATURE_PREFIX + "%"),
    )
    if user_id is not None:
        query = query.where(log.user_id == user_id)
    return int(db.scalar(query) or 0)


def check_student_call(implementation: Any, db: Any, user: Any) -> None:
    """Called before every student-side model call (recognise, explain)."""
    now = datetime.utcnow()
    if _count_calls(implementation, db, user_id=user.id, school_id=user.school_id, since=now - timedelta(minutes=1)) >= PER_MINUTE_CALLS:
        raise HTTPException(429, "操作太快了，请过一分钟再试")
    if (
        _count_calls(implementation, db, user_id=user.id, school_id=user.school_id, since=school_day_start_utc())
        >= student_daily_limit() * CALLS_PER_REQUEST
    ):
        raise HTTPException(429, TODAY_DONE)
    if _count_calls(implementation, db, user_id=None, school_id=user.school_id, since=now - timedelta(hours=1)) >= school_hourly_limit():
        raise HTTPException(429, TOO_BUSY)


def check_new_help_request(db: Any, table: Any, user: Any) -> None:
    """Called when a student confirms a question (one help request)."""
    now = datetime.utcnow()
    base = select(func.count()).select_from(table).where(table.c.student_id == user.id)
    if int(db.scalar(base.where(table.c.created_at >= now - timedelta(minutes=1))) or 0) >= PER_MINUTE_HELP_REQUESTS:
        raise HTTPException(429, "操作太快了，请过一分钟再试")
    if int(db.scalar(base.where(table.c.created_at >= school_day_start_utc())) or 0) >= student_daily_limit():
        raise HTTPException(429, TODAY_DONE)


_slots_lock = threading.Lock()
_slots_in_use = 0


@contextmanager
def ai_slot() -> Iterator[None]:
    """Non-blocking concurrency gate: a busy class gets a polite 429 instead of piling up threads."""
    global _slots_in_use
    with _slots_lock:
        if _slots_in_use >= concurrency_limit():
            raise HTTPException(429, TOO_BUSY)
        _slots_in_use += 1
    try:
        yield
    finally:
        with _slots_lock:
            _slots_in_use -= 1


def slots_in_use() -> int:
    with _slots_lock:
        return _slots_in_use


__all__ = [
    "STUDENT_FEATURE_PREFIX",
    "ai_slot",
    "check_new_help_request",
    "check_student_call",
    "concurrency_limit",
    "require_student_ai",
    "school_day_start_utc",
    "school_hourly_limit",
    "slots_in_use",
    "student_daily_limit",
]
