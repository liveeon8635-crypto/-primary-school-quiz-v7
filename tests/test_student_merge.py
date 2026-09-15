from sqlalchemy import Boolean, Column, Integer, MetaData, String, Table, Text, create_engine, select
from sqlalchemy.orm import Session

from changying.domain.student_merge import StudentMergeConflict, StudentMergeError, merge_student_records, plan_student_merge


def build_db():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    meta = MetaData()
    Table(
        "users",
        meta,
        Column("id", Integer, primary_key=True),
        Column("school_id", Integer, nullable=False),
        Column("username", String, nullable=False, unique=True),
        Column("name", String, nullable=False),
        Column("role", String, nullable=False),
        Column("grade", Integer),
        Column("active", Boolean, nullable=False, default=True),
    )
    Table(
        "class_students",
        meta,
        Column("id", Integer, primary_key=True),
        Column("class_id", Integer, nullable=False),
        Column("student_id", Integer, nullable=False),
        sqlite_autoincrement=True,
    )
    Table(
        "student_class_history",
        meta,
        Column("id", Integer, primary_key=True),
        Column("school_id", Integer, nullable=False),
        Column("student_id", Integer, nullable=False),
        Column("class_id", Integer, nullable=False),
        Column("source", String, default="system"),
    )
    Table(
        "submissions",
        meta,
        Column("id", Integer, primary_key=True),
        Column("student_id", Integer, nullable=False),
        Column("score", Integer, nullable=False),
    )
    Table(
        "audit_logs",
        meta,
        Column("id", Integer, primary_key=True),
        Column("school_id", Integer, nullable=False),
        Column("user_id", Integer),
        Column("action", String, nullable=False),
        Column("detail", Text, nullable=False),
        Column("created_at", String),
    )
    meta.create_all(engine)
    return engine, meta


def seed_pair(session, meta, *, keep_name="张志轩", merge_name="张志轩"):
    users = meta.tables["users"]
    classes = meta.tables["class_students"]
    history = meta.tables["student_class_history"]
    submissions = meta.tables["submissions"]
    session.execute(users.insert(), [
        {"id": 11, "school_id": 1, "username": "primary", "name": keep_name, "role": "student", "grade": 1, "active": True},
        {"id": 13, "school_id": 1, "username": "duplicate", "name": merge_name, "role": "student", "grade": 5, "active": True},
    ])
    session.execute(classes.insert(), [
        {"id": 1, "class_id": 8, "student_id": 11},
        {"id": 2, "class_id": 6, "student_id": 13},
    ])
    session.execute(history.insert(), [{"id": 1, "school_id": 1, "student_id": 13, "class_id": 6, "source": "test"}])
    session.execute(submissions.insert(), [{"id": 1, "student_id": 11, "score": 90}])
    session.commit()


def test_merge_moves_student_scoped_relations_and_archives_duplicate():
    engine, meta = build_db()
    with Session(engine) as session:
        seed_pair(session, meta)
        plan = plan_student_merge(session, 11, 13, expected_name="张志轩")
        assert plan.reference_counts == {"class_students": 1, "student_class_history": 1}
        assert plan.target_grade == 5
        result = merge_student_records(session, 11, 13, expected_name="张志轩", reason="test")
        session.commit()
        assert result["status"] == "merged"
        users = meta.tables["users"]
        rows = {row.id: row for row in session.execute(select(users)).all()}
        assert rows[11].grade == 5
        assert rows[13].active is False
        classes = meta.tables["class_students"]
        assert [row.student_id for row in session.execute(select(classes).order_by(classes.c.id))] == [11, 11]
        history = meta.tables["student_class_history"]
        assert session.execute(select(history.c.student_id)).scalar_one() == 11
        submissions = meta.tables["submissions"]
        assert session.execute(select(submissions.c.student_id)).scalar_one() == 11
        audit = meta.tables["audit_logs"]
        assert session.execute(select(audit.c.action)).scalar_one() == "student.merge"


def test_merge_is_idempotent_after_duplicate_is_archived():
    engine, meta = build_db()
    with Session(engine) as session:
        seed_pair(session, meta)
        merge_student_records(session, 11, 13, expected_name="张志轩")
        session.commit()
        result = merge_student_records(session, 11, 13, expected_name="张志轩")
        assert result["status"] == "already_merged"
        assert result["moved"] == {}


def test_merge_rejects_different_names_before_writing():
    engine, meta = build_db()
    with Session(engine) as session:
        seed_pair(session, meta, merge_name="另一个学生")
        try:
            merge_student_records(session, 11, 13)
        except StudentMergeError as exc:
            assert "names do not match" in str(exc)
        else:
            raise AssertionError("expected name mismatch to abort")
        users = meta.tables["users"]
        assert session.execute(select(users.c.active).where(users.c.id == 13)).scalar_one() is True


def test_merge_rejects_unique_scope_collision_without_dropping_rows():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    meta = MetaData()
    users = Table(
        "users", meta,
        Column("id", Integer, primary_key=True), Column("school_id", Integer), Column("name", String),
        Column("role", String), Column("grade", Integer), Column("active", Boolean),
    )
    from sqlalchemy import UniqueConstraint
    classes = Table(
        "class_students", meta,
        Column("id", Integer, primary_key=True), Column("class_id", Integer), Column("student_id", Integer),
        UniqueConstraint("class_id", "student_id", name="uq_class_student"),
    )
    meta.create_all(engine)
    with Session(engine) as session:
        session.execute(users.insert(), [
            {"id": 11, "school_id": 1, "name": "同名", "role": "student", "grade": 5, "active": True},
            {"id": 13, "school_id": 1, "name": "同名", "role": "student", "grade": 5, "active": True},
        ])
        session.execute(classes.insert(), [
            {"id": 1, "class_id": 6, "student_id": 11},
            {"id": 2, "class_id": 6, "student_id": 13},
        ])
        session.commit()
        try:
            merge_student_records(session, 11, 13)
        except StudentMergeConflict as exc:
            assert "uq_class_student" in str(exc)
        else:
            raise AssertionError("expected unique conflict to abort")
        assert session.execute(select(classes.c.student_id).order_by(classes.c.id)).scalars().all() == [11, 13]
