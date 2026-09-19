"""Database-backed points services extracted from the legacy monolith."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select


class PointService:
    """Read-side point aggregation with injected legacy ORM models."""

    def __init__(
        self,
        *,
        point_ledger_model: Any,
        school_class_model: Any | None = None,
        user_model: Any | None = None,
        point_rule_model: Any | None = None,
        school_local_iso_fn: Any | None = None,
    ) -> None:
        self.PointLedger = point_ledger_model
        self.SchoolClass = school_class_model
        self.User = user_model
        self.PointRule = point_rule_model
        self.school_local_iso = school_local_iso_fn

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

    def ledger_json(self, db, row) -> dict[str, Any]:
        if self.User is None or self.PointRule is None or self.school_local_iso is None:
            raise RuntimeError("user_model, point_rule_model and school_local_iso_fn are required for ledger serialization")
        student = db.get(self.User, row.student_id)
        actor = db.get(self.User, row.actor_id) if row.actor_id else None
        rule = db.get(self.PointRule, row.rule_id) if row.rule_id else None
        return {
            "id": row.id,
            "studentID": row.student_id,
            "studentName": student.name if student else "",
            "classID": row.class_id,
            "actorName": actor.name if actor else "系统",
            "ruleName": rule.name if rule else "",
            "category": row.category,
            "points": row.points,
            "reason": row.reason,
            "note": row.note,
            "source": row.source,
            "relatedID": row.related_id,
            "reversed": bool(row.reversed),
            "createdAt": self.school_local_iso(row.created_at),
        }

    def recent_rows(
        self,
        db,
        *,
        school_id: int,
        teacher_id: int | None = None,
        class_id: int | None = None,
        limit: int = 40,
    ) -> list[Any]:
        limit = max(1, min(int(limit or 40), 200))
        statement = select(self.PointLedger).where(
            self.PointLedger.school_id == school_id,
            self.PointLedger.source.in_(("classroom", "reversal", "adjustment")),
        )
        if class_id is not None:
            statement = statement.where(self.PointLedger.class_id == class_id)
        elif teacher_id is not None:
            if self.SchoolClass is None:
                raise RuntimeError("school_class_model is required for teacher filtering")
            own_class_ids = select(self.SchoolClass.id).where(
                self.SchoolClass.school_id == school_id,
                self.SchoolClass.teacher_id == teacher_id,
            )
            statement = statement.where(self.PointLedger.class_id.in_(own_class_ids))
        return list(
            db.scalars(
                statement.order_by(self.PointLedger.id.desc()).limit(limit)
            ).all()
        )

    def metric_value(self, db, *, student_id: int, school_id: int, cutoff, metric: str) -> tuple[int, str]:
        rows = db.scalars(
            select(self.PointLedger).where(
                self.PointLedger.school_id == school_id,
                self.PointLedger.student_id == student_id,
                self.PointLedger.created_at >= cutoff,
                self.PointLedger.source.in_(("classroom", "adjustment", "reversal")),
            )
        ).all()

        metric = (metric or "net").strip().lower()
        if metric == "issued":
            value = sum(
                int(row.points or 0)
                for row in rows
                if (row.points or 0) > 0 and row.source in ("classroom", "adjustment")
            )
        elif metric == "activity":
            value = sum(int(row.points or 0) for row in rows if row.category == "activity")
        elif metric == "discipline":
            value = sum(int(row.points or 0) for row in rows if row.category == "discipline")
        else:
            metric = "net"
            value = sum(int(row.points or 0) for row in rows)
        return int(value), metric

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
