from pathlib import Path

def test_completion_actor_migration_runs_before_submission_backfill():
    source=(Path(__file__).resolve().parents[1]/"app_v924.py").read_text(encoding="utf-8")
    startup=source.split('def startup():',1)[1].split('def production_readiness_payload',1)[0]
    alter="ALTER TABLE submissions ADD COLUMN completion_actor VARCHAR(30) NULL"
    assert '"completion_actor" not in submission_columns' in startup
    assert alter in startup
    assert startup.index(alter) < startup.index("v730_backfill(db)")
