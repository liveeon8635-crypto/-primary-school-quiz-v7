"""Database-backed points services extracted from the legacy monolith."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select


POINT_EARNING_SOURCES = (
    "classroom",
    "adjustment",
    "learning_submission",
    "learning_grading",
    "homework_practice",
    "math_star_map",
    "math_exam_sprint",
    "english_star_map",
    "english_exam_sprint",
    "chinese_star_map",
    "chinese_exam_sprint",
)
POINT_NET_SOURCES = POINT_EARNING_SOURCES + ("reversal",)
LEARNING_POINT_SOURCES = (
    "learning_submission",
    "learning_grading",
    "homework_practice",
    "math_star_map",
    "math_exam_sprint",
    "english_star_map",
    "english_exam_sprint",
    "chinese_star_map",
    "chinese_exam_sprint",
)


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

    def class_window_summary(
        self,
        db,
        *,
        school_id: int,
        class_id: int,
        start_utc,
        end_utc,
    ) -> dict[str, Any]:
        rows = db.scalars(
            select(self.PointLedger).where(
                self.PointLedger.school_id == school_id,
                self.PointLedger.class_id == class_id,
                self.PointLedger.created_at >= start_utc,
                self.PointLedger.created_at < end_utc,
                self.PointLedger.source.in_(POINT_NET_SOURCES),
            ).order_by(self.PointLedger.id.desc())
        ).all()

        by_student: dict[int, dict[str, int]] = {}
        for row in rows:
            item = by_student.setdefault(
                row.student_id,
                {"studentID": row.student_id, "net": 0, "activity": 0, "discipline": 0, "learning": 0, "records": 0},
            )
            points = int(row.points or 0)
            item["net"] += points
            item["records"] += 1
            if row.category == "activity":
                item["activity"] += points
            if row.category == "discipline":
                item["discipline"] += points
            if row.category == "learning":
                item["learning"] += points

        return {
            "recordCount": len(rows),
            "studentCount": len(by_student),
            "activity": sum(int(row.points or 0) for row in rows if row.category == "activity"),
            "discipline": sum(int(row.points or 0) for row in rows if row.category == "discipline"),
            "learning": sum(int(row.points or 0) for row in rows if row.category == "learning"),
            "net": sum(int(row.points or 0) for row in rows),
            "students": list(by_student.values()),
        }

    def class_window_categories(
        self,
        db,
        *,
        school_id: int,
        class_id: int,
        start_utc,
        end_utc,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        rows = db.scalars(
            select(self.PointLedger).where(
                self.PointLedger.school_id == school_id,
                self.PointLedger.class_id == class_id,
                self.PointLedger.created_at >= start_utc,
                self.PointLedger.created_at < end_utc,
                self.PointLedger.source.in_(POINT_NET_SOURCES),
            )
        ).all()

        categories: dict[str, dict[str, Any]] = {}
        for row in rows:
            key = row.reason or ("课堂活动" if row.category == "activity" else "守纪情况")
            item = categories.setdefault(
                key,
                {"reason": key, "category": row.category, "count": 0, "points": 0},
            )
            item["count"] += 1
            item["points"] += int(row.points or 0)

        result = sorted(
            categories.values(),
            key=lambda item: (abs(item["points"]), item["count"]),
            reverse=True,
        )
        if limit is not None:
            result = result[: max(0, int(limit))]
        return result

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

    def rule_json(self, row) -> dict[str, Any]:
        return {
            "id": row.id,
            "name": row.name,
            "category": row.category,
            "points": row.points,
            "active": bool(row.active),
            "requireNote": bool(row.require_note),
            "sortOrder": row.sort_order,
        }

    def class_rule_json(self, row) -> dict[str, Any]:
        return {
            **self.rule_json(row),
            "scope": "class",
            "classID": row.class_id,
        }

    def inherited_rule_json(self, row) -> dict[str, Any]:
        return {
            **self.rule_json(row),
            "scope": "school",
            "inherited": True,
        }

    def school_period_summary(
        self,
        db,
        *,
        school_id: int,
        cutoff,
    ) -> dict[str, int]:
        rows = db.scalars(
            select(self.PointLedger).where(
                self.PointLedger.school_id == school_id,
                self.PointLedger.created_at >= cutoff,
                self.PointLedger.source.in_(POINT_NET_SOURCES),
            )
        ).all()

        return {
            "earned": sum(
                int(row.points or 0)
                for row in rows
                if (row.points or 0) > 0 and row.source in POINT_EARNING_SOURCES
            ),
            "activity": sum(int(row.points or 0) for row in rows if row.category == "activity"),
            "discipline": sum(int(row.points or 0) for row in rows if row.category == "discipline"),
            "learning": sum(int(row.points or 0) for row in rows if row.category == "learning"),
        }

    def period_summary(
        self,
        db,
        *,
        student_id: int,
        school_id: int,
        cutoff,
        reason_limit: int = 5,
    ) -> dict[str, Any]:
        rows = db.scalars(
            select(self.PointLedger).where(
                self.PointLedger.school_id == school_id,
                self.PointLedger.student_id == student_id,
                self.PointLedger.created_at >= cutoff,
                self.PointLedger.source.in_(POINT_NET_SOURCES),
            ).order_by(self.PointLedger.id.desc())
        ).all()

        earned = sum(
            int(row.points or 0)
            for row in rows
            if (row.points or 0) > 0 and row.source in POINT_EARNING_SOURCES
        )
        reasons: dict[str, dict[str, int | str]] = {}
        for row in rows:
            key = row.reason or "积分记录"
            item = reasons.setdefault(key, {"reason": key, "count": 0, "points": 0})
            item["count"] = int(item["count"]) + 1
            item["points"] = int(item["points"]) + int(row.points or 0)
        top_reasons = sorted(
            reasons.values(),
            key=lambda item: (abs(int(item["points"])), int(item["count"])),
            reverse=True,
        )[: max(0, int(reason_limit))]

        return {
            "earned": earned,
            "net": sum(int(row.points or 0) for row in rows),
            "activity": sum(int(row.points or 0) for row in rows if row.category == "activity"),
            "discipline": sum(int(row.points or 0) for row in rows if row.category == "discipline"),
            "learning": sum(int(row.points or 0) for row in rows if row.category == "learning"),
            "topReasons": top_reasons,
        }

    def school_history_rows(
        self,
        db,
        *,
        school_id: int,
        descending: bool = True,
    ) -> list[Any]:
        ordering = self.PointLedger.id.desc() if descending else self.PointLedger.id
        return list(
            db.scalars(
                select(self.PointLedger)
                .where(self.PointLedger.school_id == school_id)
                .order_by(ordering)
            ).all()
        )

    def student_history_rows(
        self,
        db,
        *,
        student_id: int,
        school_id: int,
    ) -> list[Any]:
        return list(
            db.scalars(
                select(self.PointLedger)
                .where(
                    self.PointLedger.school_id == school_id,
                    self.PointLedger.student_id == student_id,
                )
                .order_by(self.PointLedger.id)
            ).all()
        )

    def student_recent_rows(
        self,
        db,
        *,
        student_id: int,
        school_id: int,
        limit: int,
        class_id: int | None = None,
        order_by_created_at: bool = False,
        id_tiebreak: bool = False,
    ) -> list[Any]:
        limit = max(1, int(limit))
        statement = select(self.PointLedger).where(
            self.PointLedger.school_id == school_id,
            self.PointLedger.student_id == student_id,
        )
        if class_id is not None:
            statement = statement.where(self.PointLedger.class_id == class_id)
        if order_by_created_at:
            ordering = [self.PointLedger.created_at.desc()]
            if id_tiebreak:
                ordering.append(self.PointLedger.id.desc())
            statement = statement.order_by(*ordering)
        else:
            statement = statement.order_by(self.PointLedger.id.desc())
        return list(db.scalars(statement.limit(limit)).all())

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
            self.PointLedger.source.in_(POINT_NET_SOURCES),
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
                self.PointLedger.source.in_(POINT_NET_SOURCES),
            )
        ).all()

        metric = (metric or "net").strip().lower()
        if metric == "issued":
            value = sum(
                int(row.points or 0)
                for row in rows
                if (row.points or 0) > 0 and row.source in POINT_EARNING_SOURCES
            )
        elif metric == "activity":
            value = sum(int(row.points or 0) for row in rows if row.category == "activity")
        elif metric == "discipline":
            value = sum(int(row.points or 0) for row in rows if row.category == "discipline")
        elif metric == "learning":
            value = sum(int(row.points or 0) for row in rows if row.category == "learning")
        else:
            metric = "net"
            value = sum(int(row.points or 0) for row in rows)
        return int(value), metric

    def window_series(
        self,
        db,
        *,
        student_id: int,
        school_id: int,
        windows,
    ) -> list[dict[str, int]]:
        windows = list(windows)
        if not windows:
            return []
        first_utc = min(start_utc for start_utc, _ in windows)
        final_utc = max(end_utc for _, end_utc in windows)
        rows = db.scalars(
            select(self.PointLedger).where(
                self.PointLedger.school_id == school_id,
                self.PointLedger.student_id == student_id,
                self.PointLedger.created_at >= first_utc,
                self.PointLedger.created_at < final_utc,
                self.PointLedger.source.in_(POINT_NET_SOURCES),
            ).order_by(self.PointLedger.created_at)
        ).all()

        result: list[dict[str, int]] = []
        for start_utc, end_utc in windows:
            current = [row for row in rows if start_utc <= row.created_at < end_utc]
            result.append(
                {
                    "earned": sum(
                        int(row.points or 0)
                        for row in current
                        if (row.points or 0) > 0 and row.source in POINT_EARNING_SOURCES
                    ),
                    "net": sum(int(row.points or 0) for row in current),
                    "activity": sum(int(row.points or 0) for row in current if row.category == "activity"),
                    "discipline": sum(int(row.points or 0) for row in current if row.category == "discipline"),
                    "learning": sum(int(row.points or 0) for row in current if row.category == "learning"),
                }
            )
        return result

    def window_summary(self, db, student_id: int, school_id: int, start_utc, end_utc) -> dict[str, int]:
        rows = db.scalars(
            select(self.PointLedger).where(
                self.PointLedger.school_id == school_id,
                self.PointLedger.student_id == student_id,
                self.PointLedger.created_at >= start_utc,
                self.PointLedger.created_at < end_utc,
                self.PointLedger.source.in_(POINT_NET_SOURCES),
            )
        ).all()

        earned = sum(
            int(row.points or 0)
            for row in rows
            if (row.points or 0) > 0 and row.source in POINT_EARNING_SOURCES
        )
        return {
            "earned": earned,
            "net": sum(int(row.points or 0) for row in rows),
            "activity": sum(int(row.points or 0) for row in rows if row.category == "activity"),
            "discipline": sum(int(row.points or 0) for row in rows if row.category == "discipline"),
            "learning": sum(int(row.points or 0) for row in rows if row.category == "learning"),
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
            if (points or 0) > 0 and source in POINT_EARNING_SOURCES
        )
        activity = sum(
            int(points or 0)
            for category, points, source in rows
            if category == "activity"
            and source in POINT_NET_SOURCES
        )
        discipline = sum(
            int(points or 0)
            for category, points, source in rows
            if category == "discipline"
            and source in POINT_NET_SOURCES
        )
        learning = sum(
            int(points or 0)
            for category, points, source in rows
            if category == "learning"
            and source in POINT_NET_SOURCES
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
            "learning": learning,
            "redeemed": redeemed,
        }


__all__ = ["LEARNING_POINT_SOURCES", "POINT_EARNING_SOURCES", "POINT_NET_SOURCES", "PointService"]
