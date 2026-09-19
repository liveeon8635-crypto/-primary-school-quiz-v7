"""Database-backed teaching services extracted from the legacy monolith."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select


class TeachingService:
    """Read-side teaching queries with injected legacy ORM models."""

    def __init__(self, *, adaptive_session_model: Any) -> None:
        self.TeachingAdaptiveSession = adaptive_session_model

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
