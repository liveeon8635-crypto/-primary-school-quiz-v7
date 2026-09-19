"""Database-backed wrong-question read service extracted from the legacy monolith."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select


class WrongQuestionService:
    """Read-side wrong-question queries with injected legacy ORM models."""

    def __init__(self, *, wrong_question_model: Any) -> None:
        self.WrongQuestionRecord = wrong_question_model

    def assignment_rows(
        self,
        db,
        *,
        school_id: int,
        student_id: int,
        assignment_id: int,
    ) -> list[Any]:
        return list(
            db.scalars(
                select(self.WrongQuestionRecord)
                .where(
                    self.WrongQuestionRecord.school_id == school_id,
                    self.WrongQuestionRecord.student_id == student_id,
                    self.WrongQuestionRecord.assignment_id == assignment_id,
                )
                .order_by(self.WrongQuestionRecord.id)
            ).all()
        )

    def teacher_student_rows(
        self,
        db,
        *,
        school_id: int,
        student_id: int,
        status: str | None = None,
    ) -> list[Any]:
        query = select(self.WrongQuestionRecord).where(
            self.WrongQuestionRecord.school_id == school_id,
            self.WrongQuestionRecord.student_id == student_id,
        )
        if status in ("active", "mastered"):
            query = query.where(self.WrongQuestionRecord.status == status)
        return list(
            db.scalars(query.order_by(self.WrongQuestionRecord.id.desc())).all()
        )

    def student_rows(
        self,
        db,
        *,
        school_id: int,
        student_id: int,
    ) -> list[Any]:
        return list(
            db.scalars(
                select(self.WrongQuestionRecord)
                .where(
                    self.WrongQuestionRecord.school_id == school_id,
                    self.WrongQuestionRecord.student_id == student_id,
                )
                .order_by(
                    self.WrongQuestionRecord.status,
                    self.WrongQuestionRecord.id.desc(),
                )
            ).all()
        )
