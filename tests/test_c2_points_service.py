from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

import app_v924 as legacy
from app import app  # noqa: F401
from changying.services.points import PointService


class Base(DeclarativeBase):
    pass


class TestPointLedger(Base):
    __tablename__ = "c2_test_point_ledger"

    id: Mapped[int] = mapped_column(primary_key=True)
    school_id: Mapped[int] = mapped_column(Integer)
    student_id: Mapped[int] = mapped_column(Integer)
    category: Mapped[str] = mapped_column(String(40))
    points: Mapped[int] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(String(40))
    created_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


def test_point_balance_preserves_student_and_school_filtering():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    service = PointService(point_ledger_model=TestPointLedger)

    with Session(engine) as db:
        db.add_all(
            [
                TestPointLedger(id=1, school_id=10, student_id=100, category="activity", points=12, source="classroom"),
                TestPointLedger(id=2, school_id=10, student_id=100, category="discipline", points=-4, source="classroom"),
                TestPointLedger(id=3, school_id=10, student_id=101, category="activity", points=50, source="classroom"),
                TestPointLedger(id=4, school_id=20, student_id=100, category="activity", points=60, source="classroom"),
            ]
        )
        db.commit()

        balance = service.balance(db, student_id=100, school_id=10)

    assert balance == 8


def test_point_window_summary_preserves_period_source_and_scope_contract():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    service = PointService(point_ledger_model=TestPointLedger)
    start = datetime(2026, 9, 1, 0, 0, 0)
    end = datetime(2026, 9, 8, 0, 0, 0)

    with Session(engine) as db:
        db.add_all(
            [
                TestPointLedger(id=1, school_id=10, student_id=100, category="activity", points=5, source="classroom", created_at=datetime(2026, 9, 2)),
                TestPointLedger(id=2, school_id=10, student_id=100, category="activity", points=3, source="adjustment", created_at=datetime(2026, 9, 3)),
                TestPointLedger(id=3, school_id=10, student_id=100, category="activity", points=-2, source="reversal", created_at=datetime(2026, 9, 4)),
                TestPointLedger(id=4, school_id=10, student_id=100, category="discipline", points=-4, source="classroom", created_at=datetime(2026, 9, 5)),
                TestPointLedger(id=5, school_id=10, student_id=100, category="adjustment", points=-20, source="redemption", created_at=datetime(2026, 9, 5)),
                TestPointLedger(id=6, school_id=10, student_id=100, category="activity", points=50, source="classroom", created_at=datetime(2026, 9, 8)),
                TestPointLedger(id=7, school_id=10, student_id=101, category="activity", points=60, source="classroom", created_at=datetime(2026, 9, 2)),
                TestPointLedger(id=8, school_id=20, student_id=100, category="activity", points=70, source="classroom", created_at=datetime(2026, 9, 2)),
            ]
        )
        db.commit()

        summary = service.window_summary(db, student_id=100, school_id=10, start_utc=start, end_utc=end)

    assert summary == {
        "earned": 8,
        "net": 2,
        "activity": 6,
        "discipline": -4,
        "records": 4,
    }


def test_point_summary_preserves_legacy_aggregation_contract():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    service = PointService(point_ledger_model=TestPointLedger)

    with Session(engine) as db:
        db.add_all(
            [
                TestPointLedger(id=1, school_id=10, student_id=100, category="activity", points=10, source="classroom"),
                TestPointLedger(id=2, school_id=10, student_id=100, category="discipline", points=-3, source="classroom"),
                TestPointLedger(id=3, school_id=10, student_id=100, category="activity", points=5, source="adjustment"),
                TestPointLedger(id=4, school_id=10, student_id=100, category="activity", points=-5, source="reversal"),
                TestPointLedger(id=5, school_id=10, student_id=100, category="adjustment", points=-20, source="redemption"),
                TestPointLedger(id=6, school_id=10, student_id=100, category="adjustment", points=4, source="refund"),
                TestPointLedger(id=7, school_id=10, student_id=101, category="activity", points=90, source="classroom"),
                TestPointLedger(id=8, school_id=20, student_id=100, category="activity", points=80, source="classroom"),
            ]
        )
        db.commit()

        summary = service.summary(db, student_id=100, school_id=10)

    assert summary == {
        "balance": -9,
        "available": 0,
        "earned": 15,
        "activity": 10,
        "discipline": -3,
        "redeemed": 16,
    }


def test_point_summary_service_is_installed_into_legacy_runtime():
    service = legacy.point_service

    assert isinstance(service, PointService)
    assert legacy.point_balance.__self__ is service
    assert legacy.point_summary.__self__ is service
    assert legacy.point_window_summary.__self__ is service
