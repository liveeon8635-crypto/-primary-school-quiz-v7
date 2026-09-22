from __future__ import annotations

from sqlalchemy import Boolean, Integer, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column
from types import SimpleNamespace

import app_v924 as legacy
from app import app  # noqa: F401
from changying.services.teaching import TeachingService


class Base(DeclarativeBase):
    pass


class TestTeachingLesson(Base):
    __tablename__ = "c2_test_teaching_lessons"

    id: Mapped[int] = mapped_column(primary_key=True)
    program_id: Mapped[int] = mapped_column(Integer)
    school_id: Mapped[int] = mapped_column(Integer)
    subject: Mapped[str] = mapped_column(String(20))
    lesson_no: Mapped[int] = mapped_column(Integer)
    published: Mapped[bool] = mapped_column(Boolean)


class TestTeachingQuestion(Base):
    __tablename__ = "c2_test_teaching_questions"

    id: Mapped[int] = mapped_column(primary_key=True)
    program_id: Mapped[int] = mapped_column(Integer)
    school_id: Mapped[int] = mapped_column(Integer)
    lesson_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    stage: Mapped[str] = mapped_column(String(20))
    subject: Mapped[str] = mapped_column(String(20))
    level: Mapped[str] = mapped_column(String(2))
    active: Mapped[bool] = mapped_column(Boolean)


class TestTeachingAdaptiveSession(Base):
    __tablename__ = "c2_test_teaching_adaptive_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    program_id: Mapped[int] = mapped_column(Integer)
    lesson_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    student_id: Mapped[int] = mapped_column(Integer)
    stage: Mapped[str] = mapped_column(String(20))
    subject: Mapped[str] = mapped_column(String(20))


def test_program_lessons_preserves_scope_filters_and_subject_lesson_order():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    service = TeachingService(
        adaptive_session_model=TestTeachingAdaptiveSession,
        lesson_model=TestTeachingLesson,
    )

    with Session(engine) as db:
        db.add_all(
            [
                TestTeachingLesson(id=1, program_id=10, school_id=100, subject="数学", lesson_no=2, published=True),
                TestTeachingLesson(id=2, program_id=10, school_id=100, subject="数学", lesson_no=1, published=False),
                TestTeachingLesson(id=3, program_id=10, school_id=100, subject="语文", lesson_no=1, published=True),
                TestTeachingLesson(id=4, program_id=10, school_id=200, subject="数学", lesson_no=0, published=True),
                TestTeachingLesson(id=5, program_id=11, school_id=100, subject="数学", lesson_no=1, published=True),
            ]
        )
        db.commit()

        teacher_rows = service.program_lessons(
            db, program_id=10, school_id=100, subject="数学"
        )
        published_rows = service.program_lessons(
            db, program_id=10, school_id=100, published_only=True
        )

    assert [row.id for row in teacher_rows] == [2, 1]
    assert [row.id for row in published_rows] == [1, 3]


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
    assert legacy.teaching_program_lessons.__self__ is service
    assert legacy.teaching_question_counts.__self__ is service
    assert legacy.teaching_questions_for_level.__self__ is service


def test_question_counts_and_level_selection_preserve_school_lesson_and_stage_scope():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    service = TeachingService(
        adaptive_session_model=TestTeachingAdaptiveSession,
        lesson_model=TestTeachingLesson,
        question_model=TestTeachingQuestion,
    )
    program = SimpleNamespace(id=10, school_id=100)
    lesson = SimpleNamespace(id=20, subject="数学")
    with Session(engine) as db:
        db.add_all([
            TestTeachingQuestion(id=1, program_id=10, school_id=100, lesson_id=20, stage="lesson", subject="数学", level="C", active=True),
            TestTeachingQuestion(id=3, program_id=10, school_id=100, lesson_id=20, stage="lesson", subject="数学", level="C", active=True),
            TestTeachingQuestion(id=4, program_id=10, school_id=100, lesson_id=None, stage="unit", subject="数学", level="C", active=True),
            TestTeachingQuestion(id=5, program_id=10, school_id=100, lesson_id=20, stage="lesson", subject="数学", level="B", active=True),
            TestTeachingQuestion(id=6, program_id=10, school_id=100, lesson_id=20, stage="lesson", subject="数学", level="C", active=False),
            TestTeachingQuestion(id=7, program_id=10, school_id=200, lesson_id=20, stage="lesson", subject="数学", level="C", active=True),
            TestTeachingQuestion(id=8, program_id=11, school_id=100, lesson_id=20, stage="lesson", subject="数学", level="C", active=True),
        ])
        db.commit()
        counts = service.question_counts(db, program)
        lesson_rows = service.questions_for_level(db, program, "C", lesson)
        unit_rows = service.questions_for_level(db, program, "C", None, "unit", "数学")
    assert counts == {"lesson": {"数学": {"B": 1, "C": 2}}, "unit": {"数学": {"C": 1}}}
    assert [row.id for row in lesson_rows] == [1, 3]
    assert [row.id for row in unit_rows] == [4]
