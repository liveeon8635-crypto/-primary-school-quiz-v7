from pathlib import Path

def test_completion_actor_migration_runs_before_submission_backfill():
    source=(Path(__file__).resolve().parents[1]/"app_v924.py").read_text(encoding="utf-8")
    alter='ALTER TABLE submissions ADD COLUMN completion_actor VARCHAR(30) NULL'
    assert '"completion_actor" not in submission_columns' in source\n    assert alter in source
    assert source.index(alter) < source.index("v730_backfill(db)")
