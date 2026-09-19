"""Database-backed teaching services extracted from the legacy monolith."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select


class TeachingService:
    """Read-side teaching queries with injected legacy ORM models."""

    def __init__(
        self,
        *,
        adaptive_session_model: Any,
        lesson_model: Any | None = None,
    ) -> None:
        self.TeachingAdaptiveSession = adaptive_session_model
        self.TeachingLesson = lesson_model

    def program_lessons(
        self,
        db,
        *,
        program_id: int,
        school_id: int | None = None,
        subject: str | None = None,
        published_only: bool = False,
    ) -> list[Any]:
        if self.TeachingLesson is None:
            raise RuntimeError("TeachingLesson model is not configured")

        statement = select(self.TeachingLesson).where(
            self.TeachingLesson.program_id == program_id,
        )
        if school_id is not None:
            statement = statement.where(self.TeachingLesson.school_id == school_id)
        if subject:
            statement = statement.where(self.TeachingLesson.subject == subject)
        if published_only:
            statement = statement.where(self.TeachingLesson.published == True)

        return list(
            db.scalars(
                statement.order_by(
                    self.TeachingLesson.subject,
                    self.TeachingLesson.lesson_no,
                )
            ).all()
        )

    def latest_session(
        self,
        db,
        student_id: int,
        program_id: int,
        lesson_id: int | None = None,
        stage: str = "lesson",
        subject: str | None = None,
    ):
        statement = select(self.TeachingAdaptiveSession).where(
            self.TeachingAdaptiveSession.student_id == student_id,
            self.TeachingAdaptiveSession.program_id == program_id,
            self.TeachingAdaptiveSession.stage == stage,
        )
        if lesson_id is not None:
            statement = statement.where(self.TeachingAdaptiveSession.lesson_id == lesson_id)
        else:
            statement = statement.where(
                self.TeachingAdaptiveSession.lesson_id.is_(None),
                self.TeachingAdaptiveSession.subject == subject,
            )
        return db.scalar(statement.order_by(self.TeachingAdaptiveSession.id.desc()).limit(1))


__all__ = ["TeachingService"]
