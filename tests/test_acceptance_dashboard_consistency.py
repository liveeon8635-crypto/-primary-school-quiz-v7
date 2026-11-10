from types import SimpleNamespace

from sqlalchemy import ForeignKey, Integer, create_engine, func, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from changying.compat.legacy import install_teacher_dashboard_current_student_count
from changying.web.v1_classic_unified_top import V1_CLASSIC_UNIFIED_SNIPPET


class Base(DeclarativeBase):
    pass


class SchoolClass(Base):
    __tablename__ = "acceptance_classes"

    id: Mapped[int] = mapped_column(primary_key=True)
    school_id: Mapped[int] = mapped_column(Integer)
    teacher_id: Mapped[int] = mapped_column(Integer)


class ClassStudent(Base):
    __tablename__ = "acceptance_class_students"

    id: Mapped[int] = mapped_column(primary_key=True)
    class_id: Mapped[int] = mapped_column(ForeignKey("acceptance_classes.id"))
    student_id: Mapped[int] = mapped_column(Integer)


def test_teacher_dashboard_student_kpi_uses_current_class_membership_not_assignment_recipients():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    implementation = SimpleNamespace(
        teacher_analytics_data=lambda db, user: {
            "classes": 4,
            "students": 3,  # legacy assignment-recipient count
            "assignments": 29,
        },
        select=select,
        func=func,
        SchoolClass=SchoolClass,
        ClassStudent=ClassStudent,
    )
    install_teacher_dashboard_current_student_count(implementation)

    with Session() as db:
        classes = [
            SchoolClass(id=101, school_id=1, teacher_id=9),
            SchoolClass(id=102, school_id=1, teacher_id=9),
            SchoolClass(id=103, school_id=1, teacher_id=9),
            SchoolClass(id=104, school_id=1, teacher_id=9),
            SchoolClass(id=201, school_id=1, teacher_id=2),
        ]
        db.add_all(classes)
        db.add_all(
            [
                ClassStudent(class_id=101, student_id=1),
                ClassStudent(class_id=101, student_id=2),
                ClassStudent(class_id=102, student_id=3),
                ClassStudent(class_id=102, student_id=4),
                ClassStudent(class_id=103, student_id=5),
                ClassStudent(class_id=103, student_id=6),
                ClassStudent(class_id=104, student_id=7),
                # A student can appear in more than one current teaching group;
                # the KPI still counts the person once.
                ClassStudent(class_id=104, student_id=1),
                # Another teacher's student must not leak into this KPI.
                ClassStudent(class_id=201, student_id=99),
            ]
        )
        db.commit()

        teacher = SimpleNamespace(id=9, school_id=1, role="teacher")
        payload = implementation.teacher_analytics_data(db, teacher)

    assert payload["classes"] == 4
    assert payload["students"] == 7
    assert payload["assignments"] == 29


def test_teacher_dashboard_count_patch_is_idempotent_and_leaves_non_teacher_payload_alone():
    implementation = SimpleNamespace(
        teacher_analytics_data=lambda db, user: {"students": 12},
        select=select,
        func=func,
        SchoolClass=SchoolClass,
        ClassStudent=ClassStudent,
    )
    install_teacher_dashboard_current_student_count(implementation)
    first = implementation.teacher_analytics_data
    install_teacher_dashboard_current_student_count(implementation)

    assert implementation.teacher_analytics_data is first
    assert implementation.teacher_analytics_data(None, SimpleNamespace(role="admin"))["students"] == 12


def test_unified_mobile_page_heading_is_kept_below_fixed_top_chrome():
    assert "html.cy-v1-unified #page>.page-head:first-child{margin-top:34px!important}" in V1_CLASSIC_UNIFIED_SNIPPET
    assert "#cy-v1-unified-top{position:fixed" in V1_CLASSIC_UNIFIED_SNIPPET


def test_repository_entrypoint_and_inventory_consistency():
    from app import app as main_app
    from changying.compat.legacy import apply_legacy_compatibility, NO_CACHE_HEADERS

    assert main_app is not None
    assert callable(apply_legacy_compatibility)
    assert "no-store" in NO_CACHE_HEADERS["Cache-Control"]
