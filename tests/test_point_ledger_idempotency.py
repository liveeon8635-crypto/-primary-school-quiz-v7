from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_point_ledger_awards_the_same_thing_only_once(tmp_path):
    db_path = tmp_path / "point-ledger-idempotency.sqlite3"
    script = r'''
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

import app_v924 as legacy
from app import app

with TestClient(app) as client:
    with legacy.engine.connect() as conn:
        columns = {row[1] for row in conn.execute(text("PRAGMA table_info(point_ledger)"))}
        assert "idempotency_key" in columns, columns
        index_rows = [
            row[0]
            for row in conn.execute(
                text("SELECT sql FROM sqlite_master WHERE type='index' AND name='uq_point_ledger_idempotency'")
            )
        ]
        assert index_rows and "UNIQUE" in index_rows[0].upper(), index_rows

    with legacy.SessionLocal() as db:
        school = db.scalar(legacy.select(legacy.School))
        student = db.scalar(legacy.select(legacy.User).where(legacy.User.username == "student1"))
        assert school is not None and student is not None
        key = "learning_submission:999999"
        db.add(
            legacy.PointLedger(
                school_id=school.id,
                student_id=student.id,
                category="learning",
                points=2,
                reason="first award",
                source="learning_submission",
                idempotency_key=key,
            )
        )
        db.commit()
        db.add(
            legacy.PointLedger(
                school_id=school.id,
                student_id=student.id,
                category="learning",
                points=2,
                reason="second award",
                source="learning_submission",
                idempotency_key=key,
            )
        )
        try:
            db.commit()
            raise AssertionError("duplicate idempotency key was accepted")
        except IntegrityError:
            db.rollback()

        # A teacher may grant or reverse the same manual bonus more than once,
        # so manual rows keep the key empty and must not collide.
        for _ in range(2):
            db.add(
                legacy.PointLedger(
                    school_id=school.id,
                    student_id=student.id,
                    category="activity",
                    points=1,
                    reason="manual bonus",
                    source="classroom",
                )
            )
        db.commit()
'''
    env = dict(
        os.environ,
        DATABASE_URL="sqlite:///" + db_path.as_posix(),
        ENABLE_DEMO_SEED="1",
        PYTHONPATH=str(ROOT),
        PYTHONUTF8="1",
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=240,
    )
    assert result.returncode == 0, result.stdout + result.stderr
