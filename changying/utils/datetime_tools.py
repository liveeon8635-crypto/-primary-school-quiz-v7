"""School-local date/time helpers shared by the Changying application."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any


SCHOOL_TZ = timezone(timedelta(hours=8))


def due_deadline_utc(value: Any) -> datetime | None:
    """Interpret an assignment deadline and return a naive UTC datetime."""
    text = (value or "").strip()
    if not text:
        return None
    try:
        if len(text) == 10:
            local = datetime.fromisoformat(text).replace(
                hour=23,
                minute=59,
                second=59,
                tzinfo=SCHOOL_TZ,
            )
        else:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
            local = parsed.replace(tzinfo=SCHOOL_TZ) if parsed.tzinfo is None else parsed
        return local.astimezone(timezone.utc).replace(tzinfo=None)
    except Exception:
        return None


def school_local_iso(value: datetime | None) -> str:
    """Serialize a UTC database datetime as school-local ``YYYY-MM-DD HH:MM``."""
    if not value:
        return ""
    aware = value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
    return aware.astimezone(SCHOOL_TZ).strftime("%Y-%m-%d %H:%M")


__all__ = ["SCHOOL_TZ", "due_deadline_utc", "school_local_iso"]
