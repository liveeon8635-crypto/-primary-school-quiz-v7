from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

from sqlalchemy import Boolean, DateTime, Integer, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

import app_v924 as legacy
from app import app  # noqa: F401
from changying.services.points import PointService


class Base(DeclarativeBase):
    pass


class TestSchoolClass(Base):
    __tablename__ = "c2_test_point_classes"

    id: Mapped[int] = mapped_column(primary_key=True)
    school_id: Mapped[int] = mapped_column(Integer)
    teacher_id: Mapped[int] = mapped_column(Integer)


class TestUser(Base):
    __tablename__ = "c2_test_point_users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80))


class TestPointRule(Base):
    __tablename__ = "c2_test_point_rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))


class TestPointLedger(Base):
    __tablename__ = "c2_test_point_ledger"

    id: Mapped[int] = mapped_column(primary_key=True)
    school_id: Mapped[int] = mapped_column(Integer)
    student_id: Mapped[int] = mapped_column(Integer)
    class_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    category: Mapped[str] = mapped_column(String(40))
    points: Mapped[int] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(String(40))
    actor_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rule_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reason: Mapped[str | None] = mapped_column(String(180), nullable=True)
    note: Mapped[str | None] = mapped_column(String(240), nullable=True)
    related_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reversed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


def test_class_window_summary_preserves_scope_source_window_and_student_aggregation():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    service = PointService(point_ledger_model=TestPointLedger)
    start = datetime(2026, 9, 19, 0, 0, 0)
    end = datetime(2026, 9, 20, 0, 0, 0)

    with Session(engine) as db:
        db.add_all(
            [
                TestPointLedger(id=1, school_id=10, student_id=100, class_id=20, category="activity", points=3, source="classroom", created_at=datetime(2026, 9, 19, 8, 0, 0)),
                TestPointLedger(id=2, school_id=10, student_id=100, class_id=20, category="discipline", points=-1, source="classroom", created_at=datetime(2026, 9, 19, 9, 0, 0)),
                TestPointLedger(id=3, school_id=10, student_id=101, class_id=20, category="activity", points=2, source="adjustment", created_at=datetime(2026, 9, 19, 10, 0, 0)),
                TestPointLedger(id=4, school_id=10, student_id=101, class_id=20, category="activity", points=-2, source="reversal", created_at=datetime(2026, 9, 19, 11, 0, 0)),
                TestPointLedger(id=5, school_id=10, student_id=100, class_id=20, category="adjustment", points=-20, source="redemption", created_at=datetime(2026, 9, 19, 12, 0, 0)),
                TestPointLedger(id=6, school_id=10, student_id=100, class_id=21, category="activity", points=30, source="classroom", created_at=datetime(2026, 9, 19, 12, 0, 0)),
                TestPointLedger(id=7, school_id=20, student_id=100, class_id=20, category="activity", points=40, source="classroom", created_at=datetime(2026, 9, 19, 12, 0, 0)),
                TestPointLedger(id=8, school_id=10, student_id=100, class_id=20, category="activity", points=50, source="classroom", created_at=end),
            ]
        )
        db.commit()

        summary = service.class_window_summary(
            db,
            school_id=10,
            class_id=20,
            start_utc=start,
            end_utc=end,
        )

    assert summary["recordCount"] == 4
    assert summary["studentCount"] == 2
    assert summary["activity"] == 3
    assert summary["discipline"] == -1
    assert summary["net"] == 2
    by_id = {item["studentID"]: item for item in summary["students"]}
    assert by_id[100] == {"studentID": 100, "net": 2, "activity": 3, "discipline": -1, "learning": 0, "records": 2}
    assert by_id[101] == {"studentID": 101, "net": 0, "activity": 0, "discipline": 0, "learning": 0, "records": 2}


def test_class_window_categories_preserve_scope_fallback_sort_and_limit_contract():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    service = PointService(point_ledger_model=TestPointLedger)
    start = datetime(2026, 9, 1, 0, 0, 0)
    end = datetime(2026, 9, 8, 0, 0, 0)

    with Session(engine) as db:
        db.add_all(
            [
                TestPointLedger(id=1, school_id=10, student_id=100, class_id=20, category="activity", points=3, source="classroom", reason="举手", created_at=datetime(2026, 9, 2)),
                TestPointLedger(id=2, school_id=10, student_id=101, class_id=20, category="activity", points=2, source="adjustment", reason="举手", created_at=datetime(2026, 9, 3)),
                TestPointLedger(id=3, school_id=10, student_id=100, class_id=20, category="discipline", points=-6, source="classroom", reason=None, created_at=datetime(2026, 9, 4)),
                TestPointLedger(id=4, school_id=10, student_id=100, class_id=20, category="activity", points=20, source="redemption", reason="应排除", created_at=datetime(2026, 9, 5)),
                TestPointLedger(id=5, school_id=10, student_id=100, class_id=21, category="activity", points=30, source="classroom", reason="其他班", created_at=datetime(2026, 9, 2)),
                TestPointLedger(id=6, school_id=20, student_id=100, class_id=20, category="activity", points=40, source="classroom", reason="其他学校", created_at=datetime(2026, 9, 2)),
                TestPointLedger(id=7, school_id=10, student_id=100, class_id=20, category="activity", points=50, source="classroom", reason="窗口外", created_at=datetime(2026, 9, 8)),
            ]
        )
        db.commit()

        full = service.class_window_categories(
            db,
            school_id=10,
            class_id=20,
            start_utc=start,
            end_utc=end,
        )
        limited = service.class_window_categories(
            db,
            school_id=10,
            class_id=20,
            start_utc=start,
            end_utc=end,
            limit=1,
        )

    assert full == [
        {"reason": "守纪情况", "category": "discipline", "count": 1, "points": -6},
        {"reason": "举手", "category": "activity", "count": 2, "points": 5},
    ]
    assert limited == [full[0]]


def test_ledger_json_preserves_legacy_names_fallbacks_and_shape():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    service = PointService(
        point_ledger_model=TestPointLedger,
        user_model=TestUser,
        point_rule_model=TestPointRule,
        school_local_iso_fn=lambda value: f"local:{value.isoformat()}" if value else None,
    )

    created_at = datetime(2026, 9, 19, 7, 30, 0)
    with Session(engine) as db:
        db.add_all(
            [
                TestUser(id=100, name="学生甲"),
                TestUser(id=200, name="王老师"),
                TestPointRule(id=300, name="主动回答"),
                TestPointLedger(
                    id=1,
                    school_id=10,
                    student_id=100,
                    class_id=20,
                    actor_id=200,
                    rule_id=300,
                    category="activity",
                    points=2,
                    reason="课堂表现",
                    note="回答完整",
                    source="classroom",
                    related_id=999,
                    reversed=True,
                    created_at=created_at,
                ),
                TestPointLedger(
                    id=2,
                    school_id=10,
                    student_id=100,
                    class_id=20,
                    actor_id=None,
                    rule_id=None,
                    category="adjustment",
                    points=1,
                    reason="补录",
                    note="",
                    source="adjustment",
                    related_id=None,
                    reversed=False,
                    created_at=created_at,
                ),
            ]
        )
        db.commit()

        first = service.ledger_json(db, db.get(TestPointLedger, 1))
        second = service.ledger_json(db, db.get(TestPointLedger, 2))

    assert first == {
        "id": 1,
        "studentID": 100,
        "studentName": "学生甲",
        "classID": 20,
        "actorName": "王老师",
        "ruleName": "主动回答",
        "category": "activity",
        "points": 2,
        "reason": "课堂表现",
        "note": "回答完整",
        "source": "classroom",
        "relatedID": 999,
        "reversed": True,
        "createdAt": "local:2026-09-19T07:30:00",
    }
    assert second["actorName"] == "系统"
    assert second["ruleName"] == ""
    assert second["relatedID"] is None
    assert second["reversed"] is False


def test_point_rule_serializers_preserve_school_class_and_inherited_contracts():
    service = PointService(point_ledger_model=TestPointLedger)
    school_rule = SimpleNamespace(
        id=11,
        name="主动回答",
        category="activity",
        points=2,
        active=1,
        require_note=0,
        sort_order=3,
    )
    class_rule = SimpleNamespace(
        id=12,
        name="课前准备",
        category="discipline",
        points=1,
        active=True,
        require_note=True,
        sort_order=4,
        class_id=99,
    )

    assert service.rule_json(school_rule) == {
        "id": 11,
        "name": "主动回答",
        "category": "activity",
        "points": 2,
        "active": True,
        "requireNote": False,
        "sortOrder": 3,
    }
    assert service.class_rule_json(class_rule) == {
        "id": 12,
        "name": "课前准备",
        "category": "discipline",
        "points": 1,
        "active": True,
        "requireNote": True,
        "sortOrder": 4,
        "scope": "class",
        "classID": 99,
    }
    assert service.inherited_rule_json(school_rule) == {
        "id": 11,
        "name": "主动回答",
        "category": "activity",
        "points": 2,
        "active": True,
        "requireNote": False,
        "sortOrder": 3,
        "scope": "school",
        "inherited": True,
    }


def test_school_history_rows_preserve_school_all_sources_and_descending_order():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    service = PointService(point_ledger_model=TestPointLedger)

    with Session(engine) as db:
        db.add_all(
            [
                TestPointLedger(id=1, school_id=10, student_id=100, category="activity", points=2, source="classroom"),
                TestPointLedger(id=3, school_id=10, student_id=101, category="reward", points=5, source="refund"),
                TestPointLedger(id=2, school_id=10, student_id=100, category="reward", points=-5, source="redemption"),
                TestPointLedger(id=4, school_id=20, student_id=100, category="activity", points=9, source="classroom"),
            ]
        )
        db.commit()

        rows = service.school_history_rows(db, school_id=10)
        ascending_rows = service.school_history_rows(db, school_id=10, descending=False)

    assert [row.id for row in rows] == [3, 2, 1]
    assert [row.source for row in rows] == ["refund", "redemption", "classroom"]
    assert [row.id for row in ascending_rows] == [1, 2, 3]


def test_student_history_rows_preserve_school_student_all_sources_and_ascending_order():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    service = PointService(point_ledger_model=TestPointLedger)

    with Session(engine) as db:
        db.add_all(
            [
                TestPointLedger(id=3, school_id=10, student_id=100, category="reward", points=5, source="refund"),
                TestPointLedger(id=1, school_id=10, student_id=100, category="activity", points=2, source="classroom"),
                TestPointLedger(id=2, school_id=10, student_id=100, category="reward", points=-5, source="redemption"),
                TestPointLedger(id=4, school_id=10, student_id=101, category="activity", points=9, source="classroom"),
                TestPointLedger(id=5, school_id=20, student_id=100, category="activity", points=10, source="classroom"),
            ]
        )
        db.commit()

        rows = service.student_history_rows(db, student_id=100, school_id=10)

    assert [row.id for row in rows] == [1, 2, 3]
    assert [row.source for row in rows] == ["classroom", "redemption", "refund"]


def test_student_recent_rows_preserve_school_student_order_limit_and_all_sources():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    service = PointService(point_ledger_model=TestPointLedger)

    with Session(engine) as db:
        db.add_all(
            [
                TestPointLedger(id=1, school_id=10, student_id=100, category="activity", points=2, source="classroom"),
                TestPointLedger(id=2, school_id=10, student_id=100, category="reward", points=-5, source="redemption"),
                TestPointLedger(id=3, school_id=10, student_id=100, category="reward", points=5, source="refund"),
                TestPointLedger(id=4, school_id=10, student_id=101, category="activity", points=9, source="classroom"),
                TestPointLedger(id=5, school_id=20, student_id=100, category="activity", points=10, source="classroom"),
            ]
        )
        db.commit()

        rows = service.student_recent_rows(db, student_id=100, school_id=10, limit=2)

    assert [row.id for row in rows] == [3, 2]
    assert [row.source for row in rows] == ["refund", "redemption"]


def test_student_recent_rows_support_optional_class_and_created_at_order_without_changing_default():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    service = PointService(point_ledger_model=TestPointLedger)

    with Session(engine) as db:
        db.add_all(
            [
                TestPointLedger(id=1, school_id=10, student_id=100, class_id=20, category="activity", points=1, source="classroom", created_at=datetime(2026, 9, 2, 8, 0, 0)),
                TestPointLedger(id=2, school_id=10, student_id=100, class_id=21, category="activity", points=2, source="classroom", created_at=datetime(2026, 9, 4, 8, 0, 0)),
                TestPointLedger(id=3, school_id=10, student_id=100, class_id=20, category="activity", points=3, source="classroom", created_at=datetime(2026, 9, 3, 8, 0, 0)),
                TestPointLedger(id=4, school_id=10, student_id=100, class_id=20, category="activity", points=4, source="classroom", created_at=datetime(2026, 9, 3, 8, 0, 0)),
                TestPointLedger(id=5, school_id=10, student_id=101, class_id=20, category="activity", points=5, source="classroom", created_at=datetime(2026, 9, 5, 8, 0, 0)),
            ]
        )
        db.commit()

        default_rows = service.student_recent_rows(db, student_id=100, school_id=10, limit=3)
        timeline_rows = service.student_recent_rows(
            db,
            student_id=100,
            school_id=10,
            class_id=20,
            limit=3,
            order_by_created_at=True,
        )
        snapshot_rows = service.student_recent_rows(
            db,
            student_id=100,
            school_id=10,
            class_id=20,
            limit=3,
            order_by_created_at=True,
            id_tiebreak=True,
        )

    assert [row.id for row in default_rows] == [4, 3, 2]
    assert {row.id for row in timeline_rows} == {1, 3, 4}
    assert timeline_rows[-1].id == 1
    assert [row.id for row in snapshot_rows] == [4, 3, 1]


def test_recent_rows_preserve_source_school_teacher_class_and_order_contract():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    service = PointService(
        point_ledger_model=TestPointLedger,
        school_class_model=TestSchoolClass,
    )

    with Session(engine) as db:
        db.add_all(
            [
                TestSchoolClass(id=1, school_id=10, teacher_id=100),
                TestSchoolClass(id=2, school_id=10, teacher_id=200),
                TestSchoolClass(id=3, school_id=20, teacher_id=100),
                TestPointLedger(id=1, school_id=10, student_id=300, class_id=1, category="activity", points=2, source="classroom"),
                TestPointLedger(id=2, school_id=10, student_id=300, class_id=1, category="activity", points=-2, source="reversal"),
                TestPointLedger(id=3, school_id=10, student_id=301, class_id=2, category="activity", points=5, source="adjustment"),
                TestPointLedger(id=4, school_id=20, student_id=300, class_id=3, category="activity", points=9, source="classroom"),
                TestPointLedger(id=5, school_id=10, student_id=300, class_id=1, category="adjustment", points=-1, source="redemption"),
            ]
        )
        db.commit()

        teacher_rows = service.recent_rows(db, school_id=10, teacher_id=100)
        class_rows = service.recent_rows(db, school_id=10, class_id=2)
        admin_rows = service.recent_rows(db, school_id=10, limit=2)

    assert [row.id for row in teacher_rows] == [2, 1]
    assert [row.id for row in class_rows] == [3]
    assert [row.id for row in admin_rows] == [3, 2]


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


def test_school_period_summary_preserves_school_cutoff_and_source_contract():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    service = PointService(point_ledger_model=TestPointLedger)
    cutoff = datetime(2026, 9, 1, 0, 0, 0)

    with Session(engine) as db:
        db.add_all(
            [
                TestPointLedger(id=1, school_id=10, student_id=100, category="activity", points=5, source="classroom", created_at=datetime(2026, 9, 2)),
                TestPointLedger(id=2, school_id=10, student_id=101, category="activity", points=3, source="adjustment", created_at=datetime(2026, 9, 3)),
                TestPointLedger(id=3, school_id=10, student_id=101, category="activity", points=-2, source="reversal", created_at=datetime(2026, 9, 4)),
                TestPointLedger(id=4, school_id=10, student_id=102, category="discipline", points=-4, source="classroom", created_at=datetime(2026, 9, 5)),
                TestPointLedger(id=5, school_id=10, student_id=102, category="discipline", points=1, source="adjustment", created_at=datetime(2026, 9, 5)),
                TestPointLedger(id=6, school_id=10, student_id=100, category="activity", points=-20, source="redemption", created_at=datetime(2026, 9, 5)),
                TestPointLedger(id=7, school_id=20, student_id=100, category="activity", points=50, source="classroom", created_at=datetime(2026, 9, 2)),
                TestPointLedger(id=8, school_id=10, student_id=100, category="activity", points=60, source="classroom", created_at=datetime(2026, 8, 31)),
            ]
        )
        db.commit()

        summary = service.school_period_summary(db, school_id=10, cutoff=cutoff)

    assert summary == {
        "earned": 9,
        "activity": 6,
        "discipline": -3,
        "learning": 0,
    }


def test_period_summary_preserves_scope_source_reason_sort_and_limit_contract():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    service = PointService(point_ledger_model=TestPointLedger)
    cutoff = datetime(2026, 9, 1, 0, 0, 0)

    with Session(engine) as db:
        db.add_all(
            [
                TestPointLedger(id=1, school_id=10, student_id=100, category="activity", points=5, source="classroom", reason="举手", created_at=datetime(2026, 9, 2)),
                TestPointLedger(id=2, school_id=10, student_id=100, category="activity", points=3, source="adjustment", reason="举手", created_at=datetime(2026, 9, 3)),
                TestPointLedger(id=3, school_id=10, student_id=100, category="activity", points=-2, source="reversal", reason="举手", created_at=datetime(2026, 9, 4)),
                TestPointLedger(id=4, school_id=10, student_id=100, category="discipline", points=-7, source="classroom", reason=None, created_at=datetime(2026, 9, 5)),
                TestPointLedger(id=5, school_id=10, student_id=100, category="adjustment", points=-20, source="redemption", reason="兑换", created_at=datetime(2026, 9, 5)),
                TestPointLedger(id=6, school_id=10, student_id=100, category="activity", points=50, source="classroom", reason="窗口外", created_at=datetime(2026, 8, 31)),
                TestPointLedger(id=7, school_id=10, student_id=101, category="activity", points=60, source="classroom", reason="其他学生", created_at=datetime(2026, 9, 2)),
                TestPointLedger(id=8, school_id=20, student_id=100, category="activity", points=70, source="classroom", reason="其他学校", created_at=datetime(2026, 9, 2)),
            ]
        )
        db.commit()

        summary = service.period_summary(
            db,
            student_id=100,
            school_id=10,
            cutoff=cutoff,
            reason_limit=1,
        )

    assert summary == {
        "earned": 8,
        "net": -1,
        "activity": 6,
        "discipline": -7,
        "learning": 0,
        "topReasons": [
            {"reason": "积分记录", "count": 1, "points": -7},
        ],
    }


def test_metric_value_preserves_cutoff_source_scope_and_metric_contract():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    service = PointService(point_ledger_model=TestPointLedger)
    cutoff = datetime(2026, 9, 1, 0, 0, 0)

    with Session(engine) as db:
        db.add_all(
            [
                TestPointLedger(id=1, school_id=10, student_id=100, category="activity", points=5, source="classroom", created_at=datetime(2026, 9, 2)),
                TestPointLedger(id=2, school_id=10, student_id=100, category="activity", points=3, source="adjustment", created_at=datetime(2026, 9, 3)),
                TestPointLedger(id=3, school_id=10, student_id=100, category="activity", points=-2, source="reversal", created_at=datetime(2026, 9, 4)),
                TestPointLedger(id=4, school_id=10, student_id=100, category="discipline", points=-4, source="classroom", created_at=datetime(2026, 9, 5)),
                TestPointLedger(id=5, school_id=10, student_id=100, category="adjustment", points=-20, source="redemption", created_at=datetime(2026, 9, 5)),
                TestPointLedger(id=6, school_id=10, student_id=100, category="activity", points=50, source="classroom", created_at=datetime(2026, 8, 31)),
                TestPointLedger(id=7, school_id=10, student_id=101, category="activity", points=60, source="classroom", created_at=datetime(2026, 9, 2)),
                TestPointLedger(id=8, school_id=20, student_id=100, category="activity", points=70, source="classroom", created_at=datetime(2026, 9, 2)),
            ]
        )
        db.commit()

        issued = service.metric_value(db, student_id=100, school_id=10, cutoff=cutoff, metric="issued")
        activity = service.metric_value(db, student_id=100, school_id=10, cutoff=cutoff, metric="activity")
        discipline = service.metric_value(db, student_id=100, school_id=10, cutoff=cutoff, metric="discipline")
        fallback = service.metric_value(db, student_id=100, school_id=10, cutoff=cutoff, metric="unknown")

    assert issued == (8, "issued")
    assert activity == (6, "activity")
    assert discipline == (-4, "discipline")
    assert fallback == (2, "net")


def test_window_series_preserves_scope_source_and_right_open_windows():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    service = PointService(point_ledger_model=TestPointLedger)
    first_start = datetime(2026, 9, 1, 0, 0, 0)
    second_start = datetime(2026, 9, 8, 0, 0, 0)
    final_end = datetime(2026, 9, 15, 0, 0, 0)

    with Session(engine) as db:
        db.add_all(
            [
                TestPointLedger(id=1, school_id=10, student_id=100, category="activity", points=5, source="classroom", created_at=datetime(2026, 9, 2)),
                TestPointLedger(id=2, school_id=10, student_id=100, category="discipline", points=-2, source="reversal", created_at=datetime(2026, 9, 7)),
                TestPointLedger(id=3, school_id=10, student_id=100, category="activity", points=3, source="adjustment", created_at=second_start),
                TestPointLedger(id=4, school_id=10, student_id=100, category="discipline", points=-4, source="classroom", created_at=datetime(2026, 9, 9)),
                TestPointLedger(id=5, school_id=10, student_id=100, category="adjustment", points=-20, source="redemption", created_at=datetime(2026, 9, 10)),
                TestPointLedger(id=6, school_id=10, student_id=101, category="activity", points=60, source="classroom", created_at=datetime(2026, 9, 2)),
                TestPointLedger(id=7, school_id=20, student_id=100, category="activity", points=70, source="classroom", created_at=datetime(2026, 9, 2)),
                TestPointLedger(id=8, school_id=10, student_id=100, category="activity", points=50, source="classroom", created_at=final_end),
            ]
        )
        db.commit()

        series = service.window_series(
            db,
            student_id=100,
            school_id=10,
            windows=[(first_start, second_start), (second_start, final_end)],
        )

    assert series == [
        {"earned": 5, "net": 3, "activity": 5, "discipline": -2, "learning": 0},
        {"earned": 3, "net": -1, "activity": 3, "discipline": -4, "learning": 0},
    ]


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
        "learning": 0,
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
        "learning": 0,
        "redeemed": 16,
    }


def test_point_summary_service_is_installed_into_legacy_runtime():
    service = legacy.point_service

    assert isinstance(service, PointService)
    assert legacy.point_balance.__self__ is service
    assert legacy.point_class_window_categories.__self__ is service
    assert legacy.point_class_window_summary.__self__ is service
    assert legacy.point_ledger_json.__self__ is service
    assert legacy.point_metric_value.__self__ is service
    assert legacy.point_period_summary.__self__ is service
    assert legacy.point_school_period_summary.__self__ is service
    assert legacy.point_rule_json.__self__ is service
    assert legacy.class_point_rule_json.__self__ is service
    assert legacy.inherited_point_rule_json.__self__ is service
    assert legacy.point_recent_rows.__self__ is service
    assert legacy.point_school_history_rows.__self__ is service
    assert legacy.point_student_history_rows.__self__ is service
    assert legacy.point_student_recent_rows.__self__ is service
    assert legacy.point_summary.__self__ is service
    assert legacy.point_window_series.__self__ is service
    assert legacy.point_window_summary.__self__ is service
