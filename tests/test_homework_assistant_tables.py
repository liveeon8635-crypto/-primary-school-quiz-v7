from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NEW_TABLES = ("homework_notices", "homework_recipients", "help_requests")


def run_isolated(tmp_path, script: str) -> str:
    env = {
        **os.environ,
        "DATABASE_URL": f"sqlite:///{tmp_path / 'm1.sqlite3'}",
        "PYTHONPATH": str(ROOT),
    }
    result = subprocess.run(
        [sys.executable, "-c", script], cwd=ROOT, env=env, text=True, capture_output=True, timeout=240
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "OK" in result.stdout, result.stdout
    return result.stdout


def test_registration_is_idempotent_and_does_not_touch_other_tables():
    import app_v924 as legacy
    import app  # noqa: F401  (runs the production wiring)
    from changying.services.homework_assistant_tables import (
        HOMEWORK_ASSISTANT_TABLES,
        register_homework_assistant_tables,
    )

    assert HOMEWORK_ASSISTANT_TABLES == NEW_TABLES
    before = set(legacy.Base.metadata.tables)
    first = register_homework_assistant_tables(legacy)
    second = register_homework_assistant_tables(legacy)
    assert set(first) == set(NEW_TABLES)
    assert all(first[name] is second[name] for name in NEW_TABLES)
    assert set(legacy.Base.metadata.tables) == before
    assert set(NEW_TABLES) <= before
    # Foreign keys only point from the new tables to existing ones (or to each other).
    for name in NEW_TABLES:
        for fk in legacy.Base.metadata.tables[name].foreign_keys:
            assert fk.column.table.name in {"schools", "users", "homework_notices"}


def test_startup_creates_only_new_tables_and_rollback_script_removes_only_them(tmp_path):
    script = r'''
import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import inspect

import app_v924 as legacy
from app import app

NEW = ("homework_notices", "homework_recipients", "help_requests")


def snapshot(conn_url):
    insp = inspect(legacy.engine)
    return {
        t: sorted((c["name"], str(c["type"])) for c in insp.get_columns(t))
        for t in insp.get_table_names()
        if t not in NEW
    }


# Simulate an existing production database: every table except the new ones already exists.
old_tables = [t for n, t in legacy.Base.metadata.tables.items() if n not in NEW]
legacy.Base.metadata.create_all(legacy.engine, tables=old_tables)
before = snapshot(None)
assert not set(NEW) & set(inspect(legacy.engine).get_table_names())

with TestClient(app) as client:
    pass  # startup runs Base.metadata.create_all

insp = inspect(legacy.engine)
names = set(insp.get_table_names())
assert set(NEW) <= names
assert snapshot(None) == before, "existing tables must be unchanged"

# Constraint: one recipient row per (notice, student).
uniques = {tuple(u["column_names"]) for u in insp.get_unique_constraints("homework_recipients")}
assert ("notice_id", "student_id") in uniques

# Rollback script drops exactly the three new tables.
db_path = legacy.engine.url.database
sql = (Path("scripts") / "m1_rollback.sql").read_text(encoding="utf-8")
legacy.engine.dispose()
conn = sqlite3.connect(db_path)
conn.executescript(sql)
conn.commit()
left = {r[0] for r in conn.execute("select name from sqlite_master where type='table'")}
conn.close()
assert not set(NEW) & left
assert names - set(NEW) <= left, "rollback must not drop any other table"
print("OK")
'''
    run_isolated(tmp_path, script)


def test_verify_counts_script_is_read_only_and_runs(tmp_path):
    script = r'''
import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

import app_v924 as legacy
from app import app

with TestClient(app) as client:
    pass
sql = (Path("scripts") / "m1_verify_counts.sql").read_text(encoding="utf-8")
lowered = sql.lower()
for word in ("insert ", "update ", "delete ", "drop ", "alter ", "create "):
    assert word not in lowered, word
conn = sqlite3.connect(legacy.engine.url.database)
rows = conn.execute(sql.rstrip().rstrip(";")).fetchall()
conn.close()
assert {r[0] for r in rows} >= {"users", "schools", "submissions", "ai_usage_logs"}
print("OK")
'''
    run_isolated(tmp_path, script)
