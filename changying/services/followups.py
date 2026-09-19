"""Database-backed follow-up read service extracted from the legacy monolith."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select


class FollowUpService:
    """Read-side student follow-up history with injected legacy ORM models."""

    def __init__(
        self,
        *,
        followup_model: Any,
        followup_log_model: Any,
    ) -> None:
        self.StudentFollowUp = followup_model
        self.StudentFollowUpLog = followup_log_model

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
