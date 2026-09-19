"""Database-backed points services extracted from the legacy monolith."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select


class PointService:
    """Read-side point aggregation with injected legacy ORM models."""

    def __init__(self, *, point_ledger_model: Any) -> None:
        self.PointLedger = point_ledger_model

    def balance(self, db, student_id: int, school_id: int) -> int:
        return int(
            db.scalar(
                select(func.coalesce(func.sum(self.PointLedger.points), 0)).where(
                    self.PointLedger.student_id == student_id,
                    self.PointLedger.school_id == school_id,
                )
            )
            or 0
        )

    def window_summary(self, db, student_id: int, school_id: int, start_utc, end_utc) -> dict[str, int]:
        rows = db.scalars(
            select(self.PointLedger).where(
                self.PointLedger.school_id == school_id,
                self.PointLedger.student_id == student_id,
                self.PointLedger.created_at >= start_utc,
                self.PointLedger.created_at < end_utc,
                self.PointLedger.source.in_(("classroom", "adjustment", "reversal")),
            )
        ).all()

        earned = sum(
            int(row.points or 0)
            for row in rows
            if (row.points or 0) > 0 and row.source in ("classroom", "adjustment")
        )
        return {
            "earned": earned,
            "net": sum(int(row.points or 0) for row in rows),
            "activity": sum(int(row.points or 0) for row in rows if row.category == "activity"),
            "discipline": sum(int(row.points or 0) for row in rows if row.category == "discipline"),
            "records": len(rows),
        }

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
