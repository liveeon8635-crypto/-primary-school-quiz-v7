from sqlalchemy import Integer, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from changying.services.assignments import AssignmentService, student_assignment_rows, teacher_assignment_rows


class Base(DeclarativeBase):
    pass


class TestClass(Base):
    __tablename__ = "c2_test_classes"

    id: Mapped[int] = mapped_column(primary_key=True)
    school_id: Mapped[int] = mapped_column(Integer)
    teacher_id: Mapped[int] = mapped_column(Integer)


class TestAssignment(Base):
    __tablename__ = "c2_test_assignments"

    id: Mapped[int] = mapped_column(primary_key=True)
    school_id: Mapped[int] = mapped_column(Integer)
    class_id: Mapped[int] = mapped_column(Integer)
    paper_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    title: Mapped[str] = mapped_column(String(80))


class TestRecipient(Base):
    __tablename__ = "c2_test_assignment_recipients"

    id: Mapped[int] = mapped_column(primary_key=True)
    school_id: Mapped[int] = mapped_column(Integer)
    assignment_id: Mapped[int] = mapped_column(Integer)
    student_id: Mapped[int] = mapped_column(Integer)


def test_teacher_assignment_rows_keeps_school_teacher_filter_and_desc_order():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)

    with Session(engine) as db:
        db.add_all(
            [
                TestClass(id=1, school_id=10, teacher_id=100),
                TestClass(id=2, school_id=10, teacher_id=200),
                TestClass(id=3, school_id=20, teacher_id=100),
                TestAssignment(id=1, school_id=10, class_id=1, title="older"),
                TestAssignment(id=4, school_id=10, class_id=1, title="newer"),
                TestAssignment(id=5, school_id=10, class_id=2, title="other teacher"),
                TestAssignment(id=6, school_id=20, class_id=3, title="other school"),
            ]
        )
        db.commit()

        rows = teacher_assignment_rows(
            db,
            assignment_model=TestAssignment,
            class_model=TestClass,
            school_id=10,
            teacher_id=100,
        )

    assert [row.id for row in rows] == [4, 1]


def test_student_assignment_rows_keeps_recipient_school_and_desc_order():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)

    with Session(engine) as db:
        db.add_all(
            [
                TestAssignment(id=10, school_id=10, class_id=1, title="older"),
                TestAssignment(id=12, school_id=10, class_id=1, title="newer"),
                TestAssignment(id=13, school_id=10, class_id=1, title="other student"),
                TestAssignment(id=14, school_id=20, class_id=1, title="other school"),
                TestRecipient(id=1, school_id=10, assignment_id=10, student_id=300),
                TestRecipient(id=2, school_id=10, assignment_id=12, student_id=300),
                TestRecipient(id=3, school_id=10, assignment_id=13, student_id=301),
                TestRecipient(id=4, school_id=20, assignment_id=14, student_id=300),
            ]
        )
        db.commit()

        rows = student_assignment_rows(
            db,
            assignment_model=TestAssignment,
            assignment_recipient_model=TestRecipient,
            school_id=10,
            student_id=300,
        )

    assert [row.id for row in rows] == [12, 10]


def test_student_assignment_for_requires_matching_recipient_and_school():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)

    service = AssignmentService(
        assignment_submission_setting_model=object,
        submission_model=object,
        homework_media_submit_model=object,
        homework_media_model=object,
        user_model=object,
        assignment_recipient_model=TestRecipient,
        assignment_model=TestAssignment,
        class_model=TestClass,
        valid_submission_modes={"quiz", "media", "mixed"},
        assignment_mode_name=lambda mode: mode,
        school_local_iso=lambda value: str(value),
        due_deadline_utc=lambda value: None,
    )

    with Session(engine) as db:
        db.add_all(
            [
                TestAssignment(id=20, school_id=10, class_id=1, title="allowed"),
                TestAssignment(id=21, school_id=10, class_id=1, title="not addressed"),
                TestAssignment(id=22, school_id=20, class_id=1, title="other school"),
                TestRecipient(id=20, school_id=10, assignment_id=20, student_id=300),
                TestRecipient(id=21, school_id=20, assignment_id=22, student_id=300),
            ]
        )
        db.commit()

        allowed = service.student_assignment_for(db, 10, 300, 20)
        wrong_student = service.student_assignment_for(db, 10, 301, 20)
        not_addressed = service.student_assignment_for(db, 10, 300, 21)
        other_school = service.student_assignment_for(db, 10, 300, 22)

    assert allowed is not None and allowed.id == 20
    assert wrong_student is None
    assert not_addressed is None
    assert other_school is None


def test_student_assignment_for_paper_requires_matching_student_and_school():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)

    service = AssignmentService(
        assignment_submission_setting_model=object,
        submission_model=object,
        homework_media_submit_model=object,
        homework_media_model=object,
        user_model=object,
        assignment_recipient_model=TestRecipient,
        assignment_model=TestAssignment,
        class_model=TestClass,
        valid_submission_modes={"quiz", "media", "mixed"},
        assignment_mode_name=lambda mode: mode,
        school_local_iso=lambda value: str(value),
        due_deadline_utc=lambda value: None,
    )

    with Session(engine) as db:
        db.add_all(
            [
                TestAssignment(id=30, school_id=10, class_id=1, paper_id=900, title="allowed paper"),
                TestAssignment(id=31, school_id=10, class_id=1, paper_id=901, title="other paper"),
                TestAssignment(id=32, school_id=20, class_id=1, paper_id=900, title="other school"),
                TestRecipient(id=30, school_id=10, assignment_id=30, student_id=300),
                TestRecipient(id=31, school_id=10, assignment_id=31, student_id=301),
                TestRecipient(id=32, school_id=20, assignment_id=32, student_id=300),
            ]
        )
        db.commit()

        allowed = service.student_assignment_for_paper(db, 10, 300, 900)
        wrong_student = service.student_assignment_for_paper(db, 10, 301, 900)
        wrong_paper = service.student_assignment_for_paper(db, 10, 300, 901)
        other_school = service.student_assignment_for_paper(db, 10, 300, 900)

    assert allowed is not None and allowed.id == 30
    assert wrong_student is None
    assert wrong_paper is None
    assert other_school is not None and other_school.school_id == 10
