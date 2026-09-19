from __future__ import annotations

from sqlalchemy import Integer, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from changying.services.followups import FollowUpService


class Base(DeclarativeBase):
    pass


class TestFollowUp(Base):
    __tablename__ = "c2_test_followups"

    id: Mapped[int] = mapped_column(primary_key=True)
    school_id: Mapped[int] = mapped_column(Integer)
    student_id: Mapped[int] = mapped_column(Integer)
    class_id: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(20), default="open")
    updated_at: Mapped[int] = mapped_column(Integer, default=0)


class TestFollowUpLog(Base):
    __tablename__ = "c2_test_followup_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    school_id: Mapped[int] = mapped_column(Integer)
    student_id: Mapped[int] = mapped_column(Integer)
    followup_id: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[int] = mapped_column(Integer, default=0)


def test_student_history_rows_keep_school_student_and_ascending_order():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    service = FollowUpService(
        followup_model=TestFollowUp,
        followup_log_model=TestFollowUpLog,
    )

    with Session(engine) as db:
        db.add_all(
            [
                TestFollowUp(id=3, school_id=10, student_id=100),
                TestFollowUp(id=1, school_id=10, student_id=100),
                TestFollowUp(id=4, school_id=10, student_id=101),
                TestFollowUp(id=5, school_id=20, student_id=100),
            ]
        )
        db.commit()
        rows = service.student_history_rows(db, school_id=10, student_id=100)

    assert [row.id for row in rows] == [1, 3]


def test_student_log_history_rows_keep_school_student_and_ascending_order():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    service = FollowUpService(
        followup_model=TestFollowUp,
        followup_log_model=TestFollowUpLog,
    )

    with Session(engine) as db:
        db.add_all(
            [
                TestFollowUpLog(id=6, school_id=10, student_id=100),
                TestFollowUpLog(id=2, school_id=10, student_id=100),
                TestFollowUpLog(id=7, school_id=10, student_id=101),
                TestFollowUpLog(id=8, school_id=20, student_id=100),
            ]
        )
        db.commit()
        rows = service.student_log_history_rows(
            db, school_id=10, student_id=100
        )

    assert [row.id for row in rows] == [2, 6]


def test_item_log_rows_keep_school_followup_and_created_id_desc_order():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    service = FollowUpService(
        followup_model=TestFollowUp,
        followup_log_model=TestFollowUpLog,
    )

    with Session(engine) as db:
        db.add_all(
            [
                TestFollowUpLog(id=1, school_id=10, student_id=100, followup_id=50, created_at=10),
                TestFollowUpLog(id=2, school_id=10, student_id=100, followup_id=50, created_at=20),
                TestFollowUpLog(id=3, school_id=10, student_id=100, followup_id=50, created_at=20),
                TestFollowUpLog(id=4, school_id=10, student_id=100, followup_id=51, created_at=30),
                TestFollowUpLog(id=5, school_id=20, student_id=100, followup_id=50, created_at=40),
            ]
        )
        db.commit()
        rows = service.item_log_rows(db, school_id=10, followup_id=50)

    assert [row.id for row in rows] == [3, 2, 1]


def test_class_rows_keep_school_class_and_status_updated_id_order():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    service = FollowUpService(
        followup_model=TestFollowUp,
        followup_log_model=TestFollowUpLog,
    )

    with Session(engine) as db:
        db.add_all(
            [
                TestFollowUp(id=1, school_id=10, student_id=100, class_id=7, status="open", updated_at=10),
                TestFollowUp(id=2, school_id=10, student_id=101, class_id=7, status="open", updated_at=20),
                TestFollowUp(id=3, school_id=10, student_id=102, class_id=7, status="done", updated_at=30),
                TestFollowUp(id=4, school_id=10, student_id=103, class_id=8, status="open", updated_at=40),
                TestFollowUp(id=5, school_id=20, student_id=104, class_id=7, status="open", updated_at=50),
                TestFollowUp(id=6, school_id=10, student_id=105, class_id=7, status="open", updated_at=20),
            ]
        )
        db.commit()
        rows = service.class_rows(db, school_id=10, class_id=7)

    assert [row.id for row in rows] == [3, 6, 2, 1]


def test_item_row_keeps_school_class_and_followup_scope():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    service = FollowUpService(
        followup_model=TestFollowUp,
        followup_log_model=TestFollowUpLog,
    )

    with Session(engine) as db:
        db.add_all(
            [
                TestFollowUp(id=1, school_id=10, student_id=100, class_id=7),
                TestFollowUp(id=2, school_id=10, student_id=101, class_id=8),
                TestFollowUp(id=3, school_id=20, student_id=102, class_id=7),
            ]
        )
        db.commit()
        found = service.item_row(db, school_id=10, class_id=7, followup_id=1)
        wrong_class = service.item_row(db, school_id=10, class_id=7, followup_id=2)
        wrong_school = service.item_row(db, school_id=10, class_id=7, followup_id=3)

    assert found is not None and found.id == 1
    assert wrong_class is None
    assert wrong_school is None


def test_followup_service_is_installed_into_legacy_runtime():
    import app_v924 as legacy
    from app import app  # noqa: F401

    service = legacy.followup_service

    assert isinstance(service, FollowUpService)
    assert legacy.followup_student_history_rows.__self__ is service
    assert legacy.followup_student_log_history_rows.__self__ is service
    assert legacy.followup_item_log_rows.__self__ is service
    assert legacy.followup_class_rows.__self__ is service
    assert legacy.followup_item_row.__self__ is service
