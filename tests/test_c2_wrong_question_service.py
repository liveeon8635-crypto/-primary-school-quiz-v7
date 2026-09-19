from __future__ import annotations

from sqlalchemy import Integer, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from changying.services.wrong_questions import WrongQuestionService


class Base(DeclarativeBase):
    pass


class TestWrongQuestion(Base):
    __tablename__ = "c2_test_wrong_questions"

    id: Mapped[int] = mapped_column(primary_key=True)
    school_id: Mapped[int] = mapped_column(Integer)
    student_id: Mapped[int] = mapped_column(Integer)
    assignment_id: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20))


def seeded_service():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    service = WrongQuestionService(wrong_question_model=TestWrongQuestion)
    return engine, service


def seed_rows(db):
    db.add_all(
        [
            TestWrongQuestion(id=1, school_id=10, student_id=100, assignment_id=500, status="active"),
            TestWrongQuestion(id=2, school_id=10, student_id=100, assignment_id=500, status="mastered"),
            TestWrongQuestion(id=3, school_id=10, student_id=100, assignment_id=501, status="active"),
            TestWrongQuestion(id=4, school_id=10, student_id=101, assignment_id=500, status="active"),
            TestWrongQuestion(id=5, school_id=20, student_id=100, assignment_id=500, status="active"),
        ]
    )
    db.commit()


def test_assignment_rows_keep_school_student_assignment_and_ascending_order():
    engine, service = seeded_service()
    with Session(engine) as db:
        seed_rows(db)
        rows = service.assignment_rows(
            db, school_id=10, student_id=100, assignment_id=500
        )

    assert [row.id for row in rows] == [1, 2]


def test_teacher_student_rows_keep_optional_status_filter_and_descending_order():
    engine, service = seeded_service()
    with Session(engine) as db:
        seed_rows(db)
        active = service.teacher_student_rows(
            db, school_id=10, student_id=100, status="active"
        )
        all_rows = service.teacher_student_rows(
            db, school_id=10, student_id=100, status="all"
        )

    assert [row.id for row in active] == [3, 1]
    assert [row.id for row in all_rows] == [3, 2, 1]


def test_student_rows_keep_status_then_descending_id_order():
    engine, service = seeded_service()
    with Session(engine) as db:
        seed_rows(db)
        rows = service.student_rows(db, school_id=10, student_id=100)

    assert [(row.status, row.id) for row in rows] == [
        ("active", 3),
        ("active", 1),
        ("mastered", 2),
    ]


def test_wrong_question_service_is_installed_into_legacy_runtime():
    import app_v924 as legacy
    from app import app  # noqa: F401

    service = legacy.wrong_question_service

    assert isinstance(service, WrongQuestionService)
    assert legacy.wrong_question_assignment_rows.__self__ is service
    assert legacy.wrong_question_teacher_student_rows.__self__ is service
    assert legacy.wrong_question_student_rows.__self__ is service
