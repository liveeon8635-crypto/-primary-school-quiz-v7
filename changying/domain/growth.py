"""Pure time-window and trend rules used by growth/points analysis."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from changying.utils.datetime_tools import SCHOOL_TZ


def period_cutoff_utc(days: int = 7, now: datetime | None = None) -> tuple[datetime, int]:
    days = max(1, min(int(days or 7), 90))
    local_now = now or datetime.now(SCHOOL_TZ)
    if local_now.tzinfo is None:
        local_now = local_now.replace(tzinfo=SCHOOL_TZ)
    else:
        local_now = local_now.astimezone(SCHOOL_TZ)
    cutoff = local_now - timedelta(days=days)
    return cutoff.astimezone(timezone.utc).replace(tzinfo=None), days


def auto_period_window(period: str, now: datetime | None = None) -> tuple[datetime, str, str]:
    local_now = now or datetime.now(SCHOOL_TZ)
    if local_now.tzinfo is None:
        local_now = local_now.replace(tzinfo=SCHOOL_TZ)
    else:
        local_now = local_now.astimezone(SCHOOL_TZ)
    period = (period or "weekly").strip().lower()
    if period == "monthly":
        start = local_now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        key = local_now.strftime("%Y-%m")
    else:
        period = "weekly"
        start = (local_now - timedelta(days=local_now.weekday())).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        iso = local_now.isocalendar()
        key = f"{iso.year}-W{iso.week:02d}"
    return start.astimezone(timezone.utc).replace(tzinfo=None), key, period


def calendar_week_window_utc(
    offset_weeks: int = 0,
    now: datetime | None = None,
) -> tuple[datetime, datetime, str, str]:
    local_now = now or datetime.now(SCHOOL_TZ)
    if local_now.tzinfo is None:
        local_now = local_now.replace(tzinfo=SCHOOL_TZ)
    else:
        local_now = local_now.astimezone(SCHOOL_TZ)
    start = (
        local_now - timedelta(days=local_now.weekday()) + timedelta(weeks=offset_weeks)
    ).replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=7)
    return (
        start.astimezone(timezone.utc).replace(tzinfo=None),
        end.astimezone(timezone.utc).replace(tzinfo=None),
        start.date().isoformat(),
        (end - timedelta(days=1)).date().isoformat(),
    )


def day_window_utc(
    offset_days: int = 0,
    now: datetime | None = None,
) -> tuple[datetime, datetime, str]:
    local_now = now or datetime.now(SCHOOL_TZ)
    if local_now.tzinfo is None:
        local_now = local_now.replace(tzinfo=SCHOOL_TZ)
    else:
        local_now = local_now.astimezone(SCHOOL_TZ)
    local_now += timedelta(days=offset_days)
    start = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    return (
        start.astimezone(timezone.utc).replace(tzinfo=None),
        end.astimezone(timezone.utc).replace(tzinfo=None),
        start.date().isoformat(),
    )


def progress_streak_from_trend(trend: list[dict]) -> int:
    if len(trend) < 2:
        return 0
    streak = 0
    for index in range(len(trend) - 1, 0, -1):
        if int(trend[index].get("net", 0)) > int(trend[index - 1].get("net", 0)):
            streak += 1
        else:
            break
    return streak


def discipline_streak_from_trend(trend: list[dict]) -> int:
    streak = 0
    for item in reversed(trend):
        if int(item.get("discipline", 0)) < 0:
            streak += 1
        else:
            break
    return streak


__all__ = [
    "auto_period_window",
    "calendar_week_window_utc",
    "day_window_utc",
    "discipline_streak_from_trend",
    "period_cutoff_utc",
    "progress_streak_from_trend",
]
