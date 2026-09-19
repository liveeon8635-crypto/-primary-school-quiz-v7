from sqlalchemy import Integer, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from changying.services.assignments import student_assignment_rows, teacher_assignment_rows


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
