from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_isolated_sqlite_startup_migrations_and_core_schema_contract(tmp_path):
    """Lock the legacy ORM/schema boundary before service/router extraction begins."""
    db_path = tmp_path / "schema-regression.sqlite3"
    script = r'''
from fastapi.testclient import TestClient
from sqlalchemy import inspect, select

import app_v924 as legacy
from app import app

EXPECTED_COLUMNS = {
    "schools": {"id", "name", "code", "active", "created_at"},
    "users": {"id", "school_id", "username", "password_hash", "name", "role", "grade", "active"},
    "user_security": {"user_id", "must_change_password", "failed_login_count", "locked_until", "password_changed_at"},
    "classes": {"id", "school_id", "name", "grade", "teacher_id"},
    "class_students": {"id", "class_id", "student_id"},
    "student_class_history": {"id", "school_id", "student_id", "class_id", "joined_at", "left_at"},
    "parent_students": {"id", "parent_id", "student_id"},
    "questions": {"id", "school_id", "grade", "subject", "textbook", "semester", "unit", "knowledge", "text", "correct_index"},
    "papers": {"id", "school_id", "title", "grade", "subject", "question_ids_json", "teacher_id"},
    "assignments": {"id", "school_id", "title", "class_id", "paper_id", "due_date"},
    "assignment_recipients": {"id", "school_id", "assignment_id", "class_id", "student_id", "assigned_at", "source"},
    "submissions": {"id", "school_id", "assignment_id", "student_id", "score", "correct", "total", "answers_json", "submitted_at"},
    "learning_evidence_events": {"id", "school_id", "student_id", "actor_id", "event_kind", "target_event_id", "evidence_type", "occurred_at", "created_at"},
    "point_ledger": {"id", "school_id", "student_id", "class_id", "actor_id", "category", "points", "reason", "reversed", "reversal_of_id", "created_at"},
    "schema_migrations": {"version", "description", "applied_at"},
}


def snapshot():
    inspector = inspect(legacy.engine)
    tables = set(inspector.get_table_names())
    missing = set(EXPECTED_COLUMNS) - tables
    assert not missing, f"missing core tables: {sorted(missing)}"
    for table_name, required_columns in EXPECTED_COLUMNS.items():
        actual = {column["name"] for column in inspector.get_columns(table_name)}
        absent = required_columns - actual
        assert not absent, f"{table_name} missing columns: {sorted(absent)}"
    with legacy.SessionLocal() as db:
        versions = [row.version for row in db.scalars(select(legacy.SchemaMigration).order_by(legacy.SchemaMigration.version)).all()]
        latest = db.scalar(select(legacy.SchemaMigration).order_by(legacy.SchemaMigration.applied_at.desc()).limit(1))
        assert latest is not None
        assert latest.version == legacy.SCHEMA_VERSION
        return tables, versions


with TestClient(app):
    first_tables, first_versions = snapshot()

# Startup/migrations must be idempotent on the same isolated database.
with TestClient(app):
    second_tables, second_versions = snapshot()

assert second_tables == first_tables
assert second_versions == first_versions
assert len(second_versions) == len(set(second_versions))
'''

    env = os.environ.copy()
    env.update(
        {
            "DATABASE_URL": f"sqlite:///{db_path}",
            "JWT_SECRET": "schema-test-jwt-secret-0123456789abcdef0123456789abcdef",
            "COMMERCIAL_ADMIN_KEY": "schema-test-commercial-key-0123456789",
            "ENABLE_DEMO_SEED": "1",
            "PYTHONPATH": str(ROOT),
        }
    )

    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )

    assert result.returncode == 0, (
        "isolated schema regression subprocess failed\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
