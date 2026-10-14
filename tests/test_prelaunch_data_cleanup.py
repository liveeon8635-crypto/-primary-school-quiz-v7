from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("prelaunch_data_cleanup", ROOT / "scripts" / "prelaunch_data_cleanup.py")
cleanup = importlib.util.module_from_spec(spec)
sys.modules["prelaunch_data_cleanup"] = cleanup
spec.loader.exec_module(cleanup)


def all_app_tables():
    import app_v924 as legacy
    from app import app  # noqa: F401  - installs the extra tables (homework assistant, feedback attachments, ...)

    return legacy.Base.metadata


def test_every_table_is_classified_keep_or_delete_and_nothing_is_both():
    names = set(all_app_tables().tables)
    known = set(cleanup.DELETE_TABLES) | set(cleanup.KEEP_TABLES)
    assert names <= known, f"classify these tables in scripts/prelaunch_data_cleanup.py: {sorted(names - known)}"
    assert not set(cleanup.DELETE_TABLES) & set(cleanup.KEEP_TABLES)


def test_accounts_configuration_and_feedback_are_never_in_the_delete_list():
    protected = {"users", "user_security", "schools", "classes", "class_students", "parent_students", "school_ai_configs",
                 "school_subscriptions", "questions", "papers", "audit_logs", "product_feedback_attachments"}
    assert protected <= set(cleanup.KEEP_TABLES)
    assert not protected & set(cleanup.DELETE_TABLES)


def make_db(tmp_path):
    import app_v924 as legacy

    db = tmp_path / "pre.db"
    engine = create_engine(f"sqlite:///{db}")
    all_app_tables().create_all(engine)
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO schools (id, name, code, active, created_at) VALUES (1, 's', 'c', 1, CURRENT_TIMESTAMP)"))
        conn.execute(text("INSERT INTO users (id, school_id, username, password_hash, name, role, active, created_at) "
                          "VALUES (1, 1, 't', 'h', 'T', 'teacher', 1, CURRENT_TIMESTAMP), (2, 1, 's', 'h', 'S', 'student', 1, CURRENT_TIMESTAMP)"))
        conn.execute(text("INSERT INTO user_security (user_id, must_change_password, failed_login_count, locked_until) "
                          "VALUES (2, 0, 4, '2099-01-01')"))
        conn.execute(text("INSERT INTO homework_notices (school_id, teacher_id, group_label, source_kind, raw_text, items_json, status, created_at) "
                          "VALUES (1, 1, '', 'text', '', '[]', 'published', CURRENT_TIMESTAMP)"))
        conn.execute(text("INSERT INTO ai_usage_logs (school_id, user_id, feature, provider, model, status, prompt_chars, output_chars, "
                          "input_tokens, output_tokens, latency_ms, error, created_at) VALUES (1, 1, 'f', 'p', 'm', 'ok', 0, 0, 0, 0, 0, '', CURRENT_TIMESTAMP)"))
        conn.execute(text("INSERT INTO audit_logs (school_id, user_id, action, detail, created_at) VALUES (1, 1, 'product_feedback', '{}', CURRENT_TIMESTAMP)"))
    return f"sqlite:///{db}", engine


def counts(engine):
    with engine.connect() as conn:
        return {n: conn.execute(text(f"SELECT COUNT(*) FROM {n}")).scalar() for n in
                ("users", "user_security", "audit_logs", "homework_notices", "ai_usage_logs")}


def test_dry_run_changes_nothing_and_execute_needs_the_backup_flag(tmp_path, monkeypatch, capsys):
    url, engine = make_db(tmp_path)
    monkeypatch.setenv("DATABASE_URL", url)
    before = counts(engine)
    assert cleanup.main(["--allow-after-launch"]) == 0 and counts(engine) == before                       # dry run
    assert cleanup.main(["--allow-after-launch", "--execute"]) == 2 and counts(engine) == before            # refuses without the backup flag
    out = capsys.readouterr().out
    assert "Dry run: nothing was changed." in out and "homework_notices" in out


def test_execute_removes_activity_data_but_keeps_accounts_audit_and_resets_lockouts(tmp_path, monkeypatch):
    url, engine = make_db(tmp_path)
    monkeypatch.setenv("DATABASE_URL", url)
    assert cleanup.main(["--allow-after-launch", "--execute", "--i-have-a-backup"]) == 0
    after = counts(engine)
    assert after["homework_notices"] == 0 and after["ai_usage_logs"] == 0
    assert after["users"] == 2 and after["audit_logs"] == 1                          # accounts and feedback/audit records stay
    with engine.connect() as conn:
        assert conn.execute(text("SELECT failed_login_count FROM user_security WHERE user_id = 2")).scalar() == 0
        assert conn.execute(text("SELECT locked_until FROM user_security WHERE user_id = 2")).scalar() is None


def test_an_unclassified_table_aborts_the_run(tmp_path, monkeypatch, capsys):
    url, engine = make_db(tmp_path)
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE brand_new_feature (id INTEGER PRIMARY KEY)"))
    monkeypatch.setenv("DATABASE_URL", url)
    before = counts(engine)
    assert cleanup.main(["--allow-after-launch", "--execute", "--i-have-a-backup"]) == 3
    assert counts(engine) == before
    assert "brand_new_feature" in capsys.readouterr().err


def test_the_psql_version_deletes_exactly_the_delete_list_children_first():
    import re

    from sqlalchemy import MetaData

    sql = (ROOT / "scripts" / "prelaunch_data_cleanup.sql").read_text(encoding="utf-8")
    deleted = re.findall(r"DELETE FROM (\w+) RETURNING", sql)
    assert sorted(deleted) == sorted(cleanup.DELETE_TABLES)
    # nothing that is kept is ever the target of a DELETE
    assert not set(deleted) & set(cleanup.KEEP_TABLES)
    # a table is deleted before any delete-table it points to (children first)
    meta = all_app_tables()
    position = {name: i for i, name in enumerate(deleted)}
    for table in meta.tables.values():
        if table.name not in position:
            continue
        for fk in table.foreign_keys:
            parent = fk.column.table.name
            if parent in position and parent != table.name:
                assert position[table.name] < position[parent], (table.name, parent)
    # safe by default: ends in a rollback unless -v do_commit=1 is given
    assert "ROLLBACK;" in sql and "\\if :do_commit" in sql and "\\set ON_ERROR_STOP on" in sql
    assert "UPDATE user_security SET failed_login_count = 0, locked_until = NULL;" in sql
    assert "DROP " not in sql and "TRUNCATE" not in sql


def test_database_url_is_rewritten_for_the_psycopg_v3_driver_like_the_app_does():
    import app_v924 as legacy

    assert cleanup.normalize_url("postgres://u:p@h:5432/db") == "postgresql+psycopg://u:p@h:5432/db"
    assert cleanup.normalize_url("postgresql://u:p@h/db") == "postgresql+psycopg://u:p@h/db"
    assert cleanup.normalize_url("postgresql+psycopg://u:p@h/db") == "postgresql+psycopg://u:p@h/db"
    assert cleanup.normalize_url("sqlite:///x.db") == "sqlite:///x.db"
    # the app itself ships only psycopg v3, so the script must never pick the default (psycopg2) driver
    assert legacy.engine.url.drivername in {"sqlite", "postgresql+psycopg"}


def test_the_cleanup_is_disabled_once_the_system_is_live(tmp_path, monkeypatch, capsys):
    url, engine = make_db(tmp_path)
    monkeypatch.setenv("DATABASE_URL", url)
    before = counts(engine)
    assert cleanup.main([]) == 5
    assert cleanup.main(["--execute", "--i-have-a-backup"]) == 5            # the backup flag alone is not enough
    assert counts(engine) == before
    assert "disabled" in capsys.readouterr().err
    sql = (ROOT / "scripts" / "prelaunch_data_cleanup.sql").read_text(encoding="utf-8")
    assert "\\if :{?allow_after_launch}" in sql and "\\quit" in sql
    assert "homework_ai_knowledge" in cleanup.KEEP_TABLES                   # the permanent AI-help record is never a delete target
