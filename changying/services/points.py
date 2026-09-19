"""Database-backed points services extracted from the legacy monolith."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select


class PointService:
    """Read-side point aggregation with injected legacy ORM models."""

    def __init__(self, *, point_ledger_model: Any) -> None:
        self.PointLedger = point_ledger_model

    def summary(self, db, student_id: int, school_id: int) -> dict[str, int]:
        rows = db.execute(
            select(
                self.PointLedger.category,
                self.PointLedger.points,
                self.PointLedger.source,
            ).where(
                self.PointLedger.student_id == student_id,
                self.PointLedger.school_id == school_id,
            )
        ).all()

        raw = sum(int(points or 0) for _, points, _ in rows)
        earned = sum(
            int(points or 0)
            for _, points, source in rows
            if (points or 0) > 0 and source in ("classroom", "adjustment")
        )
        activity = sum(
            int(points or 0)
            for category, points, source in rows
            if category == "activity"
            and source in ("classroom", "adjustment", "reversal")
        )
        discipline = sum(
            int(points or 0)
            for category, points, source in rows
            if category == "discipline"
            and source in ("classroom", "adjustment", "reversal")
        )
        reward_flow = sum(
            int(points or 0)
            for _, points, source in rows
            if source in ("redemption", "refund")
        )
        redeemed = max(0, -reward_flow)

        return {
            "balance": raw,
            "available": max(raw, 0),
            "earned": earned,
            "activity": activity,
            "discipline": discipline,
            "redeemed": redeemed,
        }


__all__ = ["PointService"]
