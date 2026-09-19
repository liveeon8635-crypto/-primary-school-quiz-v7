from sqlalchemy import Integer, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from changying.services.assignments import teacher_assignment_rows


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
