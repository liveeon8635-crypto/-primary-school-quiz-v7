from __future__ import annotations

from sqlalchemy import Integer, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

import app_v924 as legacy
from app import app  # noqa: F401
from changying.services.teaching import TeachingService


class Base(DeclarativeBase):
    pass


class TestTeachingAdaptiveSession(Base):
    __tablename__ = "c2_test_teaching_adaptive_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    program_id: Mapped[int] = mapped_column(Integer)
    lesson_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    student_id: Mapped[int] = mapped_column(Integer)
    stage: Mapped[str] = mapped_column(String(20))
    subject: Mapped[str] = mapped_column(String(20))


def test_latest_session_preserves_lesson_scope_and_latest_id_order():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    service = TeachingService(adaptive_session_model=TestTeachingAdaptiveSession)

    with Session(engine) as db:
        db.add_all(
            [
                TestTeachingAdaptiveSession(id=1, program_id=10, lesson_id=20, student_id=100, stage="lesson", subject="数学"),
                TestTeachingAdaptiveSession(id=3, program_id=10, lesson_id=20, student_id=100, stage="lesson", subject="数学"),
                TestTeachingAdaptiveSession(id=4, program_id=10, lesson_id=21, student_id=100, stage="lesson", subject="数学"),
                TestTeachingAdaptiveSession(id=5, program_id=10, lesson_id=20, student_id=101, stage="lesson", subject="数学"),
                TestTeachingAdaptiveSession(id=6, program_id=11, lesson_id=20, student_id=100, stage="lesson", subject="数学"),
            ]
        )
        db.commit()

        row = service.latest_session(db, 100, 10, 20, "lesson", "数学")

    assert row is not None
    assert row.id == 3


def test_latest_session_preserves_stage_subject_scope_when_lesson_is_none():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    service = TeachingService(adaptive_session_model=TestTeachingAdaptiveSession)

    with Session(engine) as db:
        db.add_all(
            [
                TestTeachingAdaptiveSession(id=1, program_id=10, lesson_id=None, student_id=100, stage="unit", subject="数学"),
                TestTeachingAdaptiveSession(id=3, program_id=10, lesson_id=None, student_id=100, stage="unit", subject="数学"),
                TestTeachingAdaptiveSession(id=4, program_id=10, lesson_id=20, student_id=100, stage="unit", subject="数学"),
                TestTeachingAdaptiveSession(id=5, program_id=10, lesson_id=None, student_id=100, stage="unit", subject="语文"),
                TestTeachingAdaptiveSession(id=6, program_id=10, lesson_id=None, student_id=100, stage="term", subject="数学"),
            ]
        )
        db.commit()

        row = service.latest_session(db, 100, 10, None, "unit", "数学")

    assert row is not None
    assert row.id == 3


def test_teaching_service_is_installed_into_legacy_runtime():
    service = legacy.teaching_service

    assert isinstance(service, TeachingService)
    assert legacy.latest_teaching_session.__self__ is service
