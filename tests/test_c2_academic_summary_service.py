"""Real SQLite coverage for school-scoped recent submission summaries."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_academic_summary_preserves_scope_window_and_accuracy(tmp_path):
    script = r"""
from datetime import datetime, timedelta
import app_v924 as m
from app import app

m.Base.metadata.create_all(m.engine)
with m.SessionLocal() as db:
    school = m.School(name="近期汇总学校", code="academic-summary")
    other = m.School(name="其他学校", code="academic-other")
    db.add_all([school, other])
    db.flush()
    student = m.User(school_id=school.id, username="academic-student", password_hash="x", name="学生", role="student")
    peer = m.User(school_id=school.id, username="academic-peer", password_hash="x", name="同学", role="student")
    db.add_all([student, peer])
    db.flush()
    now = datetime.utcnow()
    db.add_all([
        m.Submission(school_id=school.id, student_id=student.id, score=70, correct=3, total=4, submitted_at=now-timedelta(days=2)),
        m.Submission(school_id=school.id, student_id=student.id, score=90, correct=4, total=5, submitted_at=now-timedelta(days=1)),
        m.Submission(school_id=school.id, student_id=student.id, score=100, correct=0, total=0, submitted_at=now),
        m.Submission(school_id=school.id, student_id=student.id, score=10, correct=1, total=1, submitted_at=now-timedelta(days=10)),
        m.Submission(school_id=other.id, student_id=student.id, score=5, correct=0, total=5, submitted_at=now),
        m.Submission(school_id=school.id, student_id=peer.id, score=5, correct=0, total=5, submitted_at=now),
    ])
    db.commit()
    before = db.scalar(m.select(m.func.count()).select_from(m.Submission))
    summary = m.student_academic_summary(db, student.id, school.id, 7)
    after = db.scalar(m.select(m.func.count()).select_from(m.Submission))
    assert before == after == 6
    assert summary == {"days": 7, "count": 3, "avgScore": 86.7, "avgAccuracy": 77.5, "latestScore": 100}
    assert m.student_academic_summary(db, peer.id, other.id, 7) == {
        "days": 7, "count": 0, "avgScore": None, "avgAccuracy": None, "latestScore": None
    }
"""
    env = os.environ.copy()
    env.update({
        "DATABASE_URL": f"sqlite:///{tmp_path / 'academic-summary.sqlite3'}",
        "JWT_SECRET": "test-academic-summary-0123456789abcdef0123456789abcdef",
        "COMMERCIAL_ADMIN_KEY": "test-academic-summary-commercial-0123456789",
        "ENABLE_DEMO_SEED": "0",
        "PYTHONPATH": str(ROOT),
    })
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=ROOT, env=env, capture_output=True, text=True,
        timeout=120, check=False,
    )
    assert result.returncode == 0, (
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
