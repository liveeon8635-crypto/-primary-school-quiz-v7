"""Database-backed teaching services extracted from the legacy monolith."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select


class TeachingService:
    """Read-side teaching queries with injected legacy ORM models."""

    def __init__(
        self,
        *,
        adaptive_session_model: Any,
        lesson_model: Any | None = None,
        question_model: Any | None = None,
    ) -> None:
        self.TeachingAdaptiveSession = adaptive_session_model
        self.TeachingLesson = lesson_model
        self.TeachingQuestion = question_model

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

    def question_counts(self, db, program) -> dict[str, dict[str, dict[str, int]]]:
        if self.TeachingQuestion is None:
            raise RuntimeError("TeachingQuestion model is not configured")
        rows = db.execute(
            select(
                self.TeachingQuestion.stage,
                self.TeachingQuestion.subject,
                self.TeachingQuestion.level,
                func.count(),
            )
            .where(
                self.TeachingQuestion.program_id == program.id,
                self.TeachingQuestion.school_id == program.school_id,
                self.TeachingQuestion.active == True,
            )
            .group_by(
                self.TeachingQuestion.stage,
                self.TeachingQuestion.subject,
                self.TeachingQuestion.level,
            )
        ).all()
        counts = {}
        for stage, subject, level, count in rows:
            counts.setdefault(stage, {}).setdefault(subject, {})[level] = int(count or 0)
        return counts

    def questions_for_level(
        self,
        db,
        program,
        level,
        lesson=None,
        stage="lesson",
        subject=None,
    ) -> list[Any]:
        if self.TeachingQuestion is None:
            raise RuntimeError("TeachingQuestion model is not configured")
        statement = select(self.TeachingQuestion).where(
            self.TeachingQuestion.school_id == program.school_id,
            self.TeachingQuestion.program_id == program.id,
            self.TeachingQuestion.active == True,
            self.TeachingQuestion.level == level,
        )
        if lesson is not None:
            statement = statement.where(
                self.TeachingQuestion.lesson_id == lesson.id,
                self.TeachingQuestion.stage == "lesson",
                self.TeachingQuestion.subject == lesson.subject,
            )
        else:
            statement = statement.where(
                self.TeachingQuestion.lesson_id.is_(None),
                self.TeachingQuestion.stage == stage,
                self.TeachingQuestion.subject == subject,
            )
        return db.scalars(statement.order_by(self.TeachingQuestion.id)).all()

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
