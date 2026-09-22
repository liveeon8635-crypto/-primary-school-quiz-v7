"""Database-backed transition-plan service extracted from the V1 route layer."""

from __future__ import annotations

from datetime import datetime
from typing import Any


class TransitionPlanService:
    """Persistence operations for teacher-confirmed transition plans.

    The service deliberately owns only the existing transition-plan table. It does
    not change student grade/class membership, points, evidence or mastery.
    """

    def __init__(self, *, table: Any, select_fn: Any, audit_log_model: Any) -> None:
        self.table = table
        self.select = select_fn
        self.AuditLog = audit_log_model

    def list_rows(self, db, *, school_id: int, student_id: int) -> list[Any]:
        return list(db.execute(
            self.select(self.table).where(
                self.table.c.school_id == school_id,
                self.table.c.student_id == student_id,
            ).order_by(self.table.c.created_at.desc(), self.table.c.id.desc())
        ).all())

    def row(self, db, *, school_id: int, student_id: int, plan_id: int) -> Any | None:
        return db.execute(self.select(self.table).where(
            self.table.c.id == plan_id,
            self.table.c.school_id == school_id,
            self.table.c.student_id == student_id,
        )).first()

    def create(self, db, *, school_id: int, student_id: int, teacher_id: int, values: dict[str, Any]) -> Any:
        result = db.execute(self.table.insert().values(**values))
        plan_id = int(result.inserted_primary_key[0])
        db.add(self.AuditLog(
            school_id=school_id,
            user_id=teacher_id,
            action="student.transition_plan.create",
            detail=f"student={student_id}:plan={plan_id}",
        ))
        db.commit()
        return self.row(db, school_id=school_id, student_id=student_id, plan_id=plan_id)

    def close(self, db, *, school_id: int, student_id: int, teacher_id: int, plan_id: int, now: datetime | None = None) -> Any | None:
        row = self.row(db, school_id=school_id, student_id=student_id, plan_id=plan_id)
        if row is None:
            return None
        if row._mapping["status"] != "closed":
            now = now or datetime.utcnow()
            db.execute(self.table.update().where(self.table.c.id == plan_id).values(
                status="closed", closed_at=now, updated_at=now,
            ))
            db.add(self.AuditLog(
                school_id=school_id,
                user_id=teacher_id,
                action="student.transition_plan.close",
                detail=f"student={student_id}:plan={plan_id}",
            ))
            db.commit()
        return self.row(db, school_id=school_id, student_id=student_id, plan_id=plan_id)


__all__ = ["TransitionPlanService"]
