"""Database-backed follow-up read service extracted from the legacy monolith."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select


class FollowUpService:
    """Read-side student follow-up history with injected legacy ORM models."""

    def __init__(
        self,
        *,
        followup_model: Any,
        followup_log_model: Any,
        class_todo_model: Any | None = None,
    ) -> None:
        self.StudentFollowUp = followup_model
        self.StudentFollowUpLog = followup_log_model
        self.ClassTodo = class_todo_model

    def student_history_rows(
        self,
        db,
        *,
        school_id: int,
        student_id: int,
    ) -> list[Any]:
        return list(
            db.scalars(
                select(self.StudentFollowUp)
                .where(
                    self.StudentFollowUp.school_id == school_id,
                    self.StudentFollowUp.student_id == student_id,
                )
                .order_by(self.StudentFollowUp.id)
            ).all()
        )

    def student_log_history_rows(
        self,
        db,
        *,
        school_id: int,
        student_id: int,
    ) -> list[Any]:
        return list(
            db.scalars(
                select(self.StudentFollowUpLog)
                .where(
                    self.StudentFollowUpLog.school_id == school_id,
                    self.StudentFollowUpLog.student_id == student_id,
                )
                .order_by(self.StudentFollowUpLog.id)
            ).all()
        )

    def item_log_rows(
        self,
        db,
        *,
        school_id: int,
        followup_id: int,
    ) -> list[Any]:
        return list(
            db.scalars(
                select(self.StudentFollowUpLog)
                .where(
                    self.StudentFollowUpLog.school_id == school_id,
                    self.StudentFollowUpLog.followup_id == followup_id,
                )
                .order_by(
                    self.StudentFollowUpLog.created_at.desc(),
                    self.StudentFollowUpLog.id.desc(),
                )
            ).all()
        )

    def class_rows(
        self,
        db,
        *,
        school_id: int,
        class_id: int,
    ) -> list[Any]:
        return list(
            db.scalars(
                select(self.StudentFollowUp)
                .where(
                    self.StudentFollowUp.school_id == school_id,
                    self.StudentFollowUp.class_id == class_id,
                )
                .order_by(
                    self.StudentFollowUp.status,
                    self.StudentFollowUp.updated_at.desc(),
                    self.StudentFollowUp.id.desc(),
                )
            ).all()
        )

    def item_row(
        self,
        db,
        *,
        school_id: int,
        class_id: int,
        followup_id: int,
    ) -> Any | None:
        return db.scalar(
            select(self.StudentFollowUp).where(
                self.StudentFollowUp.id == followup_id,
                self.StudentFollowUp.class_id == class_id,
                self.StudentFollowUp.school_id == school_id,
            )
        )

    def parent_contact_rows(
        self,
        db,
        *,
        school_id: int,
        student_id: int,
    ) -> list[Any]:
        return list(
            db.scalars(
                select(self.StudentFollowUpLog)
                .join(
                    self.StudentFollowUp,
                    self.StudentFollowUp.id == self.StudentFollowUpLog.followup_id,
                )
                .where(
                    self.StudentFollowUpLog.school_id == school_id,
                    self.StudentFollowUpLog.student_id == student_id,
                    self.StudentFollowUpLog.log_type == "parent_contact",
                )
                .order_by(
                    self.StudentFollowUpLog.created_at.desc(),
                    self.StudentFollowUpLog.id.desc(),
                )
                .limit(50)
            ).all()
        )

    def class_parent_contact_rows(
        self,
        db,
        *,
        school_id: int,
        class_id: int,
    ) -> list[Any]:
        return list(
            db.scalars(
                select(self.StudentFollowUpLog)
                .join(
                    self.StudentFollowUp,
                    self.StudentFollowUp.id == self.StudentFollowUpLog.followup_id,
                )
                .where(
                    self.StudentFollowUp.school_id == school_id,
                    self.StudentFollowUp.class_id == class_id,
                    self.StudentFollowUpLog.log_type == "parent_contact",
                )
                .order_by(self.StudentFollowUpLog.created_at.desc())
            ).all()
        )

    def timeline_rows(
        self,
        db,
        *,
        school_id: int,
        student_id: int,
        class_id: int | None = None,
        limit: int = 20,
    ) -> list[Any]:
        query = select(self.StudentFollowUp).where(
            self.StudentFollowUp.school_id == school_id,
            self.StudentFollowUp.student_id == student_id,
        )
        if class_id:
            query = query.where(self.StudentFollowUp.class_id == class_id)
        return list(
            db.scalars(
                query.order_by(self.StudentFollowUp.created_at.desc()).limit(limit)
            ).all()
        )

    def timeline_log_rows(
        self,
        db,
        *,
        school_id: int,
        followup_ids: list[int],
        limit: int = 40,
    ) -> list[Any]:
        if not followup_ids:
            return []
        return list(
            db.scalars(
                select(self.StudentFollowUpLog)
                .where(
                    self.StudentFollowUpLog.followup_id.in_(followup_ids),
                    self.StudentFollowUpLog.school_id == school_id,
                )
                .order_by(self.StudentFollowUpLog.created_at.desc())
                .limit(limit)
            ).all()
        )


    def class_todo_rows(
        self,
        db,
        *,
        school_id: int,
        class_id: int,
    ) -> list[Any]:
        if self.ClassTodo is None:
            raise RuntimeError("class_todo_model is not configured")
        return list(
            db.scalars(
                select(self.ClassTodo)
                .where(
                    self.ClassTodo.school_id == school_id,
                    self.ClassTodo.class_id == class_id,
                )
                .order_by(
                    self.ClassTodo.status,
                    self.ClassTodo.created_at.desc(),
                    self.ClassTodo.id.desc(),
                )
            ).all()
        )

    def class_parent_contact_count(
        self,
        db,
        *,
        school_id: int,
        class_id: int,
    ) -> int:
        return int(
            db.scalar(
                select(func.count())
                .select_from(self.StudentFollowUpLog)
                .join(
                    self.StudentFollowUp,
                    self.StudentFollowUp.id == self.StudentFollowUpLog.followup_id,
                )
                .where(
                    self.StudentFollowUp.school_id == school_id,
                    self.StudentFollowUp.class_id == class_id,
                    self.StudentFollowUpLog.log_type == "parent_contact",
                )
            )
            or 0
        )
