from __future__ import annotations

from sqlalchemy import Integer, String, create_engine
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
    assert legacy.point_summary.__self__ is service
