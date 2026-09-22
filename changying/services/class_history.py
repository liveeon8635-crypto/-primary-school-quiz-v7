"""Read-only class membership history for one continuous student record."""

from __future__ import annotations

from typing import Any


class ClassHistoryService:
    def __init__(
        self,
        *,
        history_model: Any,
        class_model: Any,
        select_fn: Any,
        local_iso: Any,
    ) -> None:
        self.History = history_model
        self.SchoolClass = class_model
        self.select = select_fn
        self.local_iso = local_iso

    def rows(self, db: Any, student_id: int, school_id: int) -> list[dict[str, Any]]:
        histories = db.scalars(
            self.select(self.History)
            .where(
                self.History.student_id == student_id,
                self.History.school_id == school_id,
            )
            .order_by(self.History.joined_at.desc(), self.History.id.desc())
        ).all()
        reason_names = {
            "transfer": "调班",
            "graduate": "毕业归档",
            "restore": "恢复入班",
            "": "在读",
        }
        result = []
        for history in histories:
            school_class = db.get(self.SchoolClass, history.class_id)
            result.append(
                {
                    "id": history.id,
                    "classID": history.class_id,
                    "className": (
                        school_class.name
                        if school_class is not None
                        else f"班级#{history.class_id}"
                    ),
                    "grade": school_class.grade if school_class is not None else None,
                    "joinedAt": self.local_iso(history.joined_at),
                    "leftAt": self.local_iso(history.left_at) if history.left_at else None,
                    "leaveReason": history.leave_reason,
                    "leaveReasonName": reason_names.get(
                        history.leave_reason, history.leave_reason or "在读"
                    ),
                    "current": history.left_at is None,
                }
            )
        return result


__all__ = ["ClassHistoryService"]
