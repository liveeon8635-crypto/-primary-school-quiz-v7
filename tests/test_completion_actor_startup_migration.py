from pathlib import Path

SOURCE=(Path(__file__).resolve().parents[1]/"app_v924.py").read_text(encoding="utf-8")


def test_completion_actor_column_migration_precedes_backfill():
    migration=SOURCE.index("def ensure_submission_completion_actor_column():")
    startup=SOURCE.index('def startup():')
    ensure=SOURCE.index("    ensure_submission_completion_actor_column()", startup)
    backfill=SOURCE.index("    v730_backfill(db)", startup)
    assert migration < startup < ensure < backfill


def test_completion_actor_migration_is_nullable_idempotent_and_never_backfills():
    start=SOURCE.index("def ensure_submission_completion_actor_column():")
    end=SOURCE.index('@app.on_event("startup")', start)
    body=SOURCE[start:end]
    assert 'if "completion_actor" in columns:' in body
    assert 'sa_text("ALTER TABLE submissions ADD COLUMN completion_actor VARCHAR(30) NULL")' in body
    assert 'sa_text("CREATE INDEX IF NOT EXISTS ix_submissions_completion_actor ON submissions (completion_actor)")' in body
    assert "UPDATE submissions" not in body
