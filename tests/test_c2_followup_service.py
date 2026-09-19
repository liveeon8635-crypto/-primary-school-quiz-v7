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
    created_at: Mapped[int] = mapped_column(Integer, default=0)


class TestFollowUpLog(Base):
    __tablename__ = "c2_test_followup_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    school_id: Mapped[int] = mapped_column(Integer)
    student_id: Mapped[int] = mapped_column(Integer)
    followup_id: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[int] = mapped_column(Integer, default=0)
    log_type: Mapped[str] = mapped_column(String(40), default="note")


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
        row = service.item_row(db, school_id=10, class_id=7, followup_id=1)
        wrong_class = service.item_row(db, school_id=10, class_id=7, followup_id=2)
        wrong_school = service.item_row(db, school_id=10, class_id=7, followup_id=3)

    assert row is not None and row.id == 1
    assert wrong_class is None
    assert wrong_school is None


def test_parent_contact_rows_keep_join_scope_type_order_and_limit_contract():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    service = FollowUpService(
        followup_model=TestFollowUp,
        followup_log_model=TestFollowUpLog,
    )

    with Session(engine) as db:
        db.add_all(
            [
                TestFollowUp(id=50, school_id=10, student_id=100, class_id=7),
                TestFollowUp(id=51, school_id=10, student_id=100, class_id=7),
            ]
        )
        db.add_all(
            [
                TestFollowUpLog(id=1, school_id=10, student_id=100, followup_id=50, created_at=10, log_type="parent_contact"),
                TestFollowUpLog(id=2, school_id=10, student_id=100, followup_id=50, created_at=20, log_type="parent_contact"),
                TestFollowUpLog(id=3, school_id=10, student_id=100, followup_id=51, created_at=20, log_type="parent_contact"),
                TestFollowUpLog(id=4, school_id=10, student_id=100, followup_id=50, created_at=30, log_type="note"),
                TestFollowUpLog(id=5, school_id=10, student_id=101, followup_id=50, created_at=40, log_type="parent_contact"),
                TestFollowUpLog(id=6, school_id=20, student_id=100, followup_id=50, created_at=50, log_type="parent_contact"),
                TestFollowUpLog(id=7, school_id=10, student_id=100, followup_id=999, created_at=60, log_type="parent_contact"),
            ]
        )
        db.commit()
        rows = service.parent_contact_rows(db, school_id=10, student_id=100)

    assert [row.id for row in rows] == [3, 2, 1]


def test_class_parent_contact_rows_keep_join_school_class_type_and_created_order():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    service = FollowUpService(
        followup_model=TestFollowUp,
        followup_log_model=TestFollowUpLog,
    )

    with Session(engine) as db:
        db.add_all(
            [
                TestFollowUp(id=50, school_id=10, student_id=100, class_id=7),
                TestFollowUp(id=51, school_id=10, student_id=101, class_id=7),
                TestFollowUp(id=52, school_id=10, student_id=102, class_id=8),
                TestFollowUp(id=53, school_id=20, student_id=103, class_id=7),
            ]
        )
        db.add_all(
            [
                TestFollowUpLog(id=1, school_id=10, student_id=100, followup_id=50, created_at=10, log_type="parent_contact"),
                TestFollowUpLog(id=2, school_id=10, student_id=101, followup_id=51, created_at=30, log_type="parent_contact"),
                TestFollowUpLog(id=3, school_id=10, student_id=100, followup_id=50, created_at=20, log_type="note"),
                TestFollowUpLog(id=4, school_id=10, student_id=102, followup_id=52, created_at=40, log_type="parent_contact"),
                TestFollowUpLog(id=5, school_id=20, student_id=103, followup_id=53, created_at=50, log_type="parent_contact"),
                TestFollowUpLog(id=6, school_id=99, student_id=100, followup_id=50, created_at=60, log_type="parent_contact"),
            ]
        )
        db.commit()
        rows = service.class_parent_contact_rows(db, school_id=10, class_id=7)

    assert [row.id for row in rows] == [6, 2, 1]


def test_timeline_rows_keep_school_student_optional_class_order_and_limit():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    service = FollowUpService(
        followup_model=TestFollowUp,
        followup_log_model=TestFollowUpLog,
    )

    with Session(engine) as db:
        db.add_all(
            [
                TestFollowUp(id=1, school_id=10, student_id=100, class_id=7, created_at=10),
                TestFollowUp(id=2, school_id=10, student_id=100, class_id=7, created_at=30),
                TestFollowUp(id=3, school_id=10, student_id=100, class_id=8, created_at=40),
                TestFollowUp(id=4, school_id=10, student_id=101, class_id=7, created_at=50),
                TestFollowUp(id=5, school_id=20, student_id=100, class_id=7, created_at=60),
            ]
        )
        db.commit()
        class_rows = service.timeline_rows(
            db, school_id=10, student_id=100, class_id=7, limit=20
        )
        all_rows = service.timeline_rows(
            db, school_id=10, student_id=100, class_id=None, limit=2
        )

    assert [row.id for row in class_rows] == [2, 1]
    assert [row.id for row in all_rows] == [3, 2]


def test_timeline_log_rows_keep_school_followup_ids_order_and_limit():
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
                TestFollowUpLog(id=2, school_id=10, student_id=100, followup_id=51, created_at=30),
                TestFollowUpLog(id=3, school_id=10, student_id=100, followup_id=50, created_at=20),
                TestFollowUpLog(id=4, school_id=10, student_id=100, followup_id=99, created_at=40),
                TestFollowUpLog(id=5, school_id=20, student_id=100, followup_id=50, created_at=50),
            ]
        )
        db.commit()
        rows = service.timeline_log_rows(
            db, school_id=10, followup_ids=[50, 51], limit=2
        )
        empty = service.timeline_log_rows(
            db, school_id=10, followup_ids=[], limit=40
        )

    assert [row.id for row in rows] == [2, 3]
    assert empty == []


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
    assert legacy.followup_parent_contact_rows.__self__ is service
    assert legacy.followup_class_parent_contact_rows.__self__ is service
    assert legacy.followup_timeline_rows.__self__ is service
    assert legacy.followup_timeline_log_rows.__self__ is service
