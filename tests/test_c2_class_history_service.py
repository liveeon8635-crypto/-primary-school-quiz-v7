"""Real SQLite coverage for the continuous class-history read contract."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_class_history_service_preserves_school_scope_order_and_archive(tmp_path):
    script = r"""
from datetime import datetime, timedelta
import app_v924 as m
from app import app

m.Base.metadata.create_all(m.engine)
with m.SessionLocal() as db:
    school = m.School(name="历史测试学校", code="history-test")
    other = m.School(name="其他学校", code="other-history-test")
    db.add_all([school, other])
    db.flush()
    teacher = m.User(school_id=school.id, username="history-teacher", password_hash="x", name="教师", role="teacher")
    student = m.User(school_id=school.id, username="history-student", password_hash="x", name="学生", role="student")
    db.add_all([teacher, student])
    db.flush()
    first = m.SchoolClass(school_id=school.id, name="旧班", grade=4, teacher_id=teacher.id)
    current = m.SchoolClass(school_id=school.id, name="新班", grade=5, teacher_id=teacher.id)
    foreign = m.SchoolClass(school_id=other.id, name="外校班", grade=6, teacher_id=teacher.id)
    db.add_all([first, current, foreign])
    db.flush()
    start = datetime(2026, 1, 1, 8)
    db.add_all([
        m.StudentClassHistory(school_id=school.id, student_id=student.id, class_id=first.id, joined_at=start, left_at=start + timedelta(days=30), leave_reason="transfer"),
        m.StudentClassHistory(school_id=school.id, student_id=student.id, class_id=current.id, joined_at=start + timedelta(days=30), leave_reason=""),
        m.StudentClassHistory(school_id=other.id, student_id=student.id, class_id=foreign.id, joined_at=start + timedelta(days=40), leave_reason=""),
    ])
    db.commit()
    before = db.scalar(m.select(m.func.count()).select_from(m.StudentClassHistory))
    rows = m.class_history_rows(db, student.id, school.id)
    after = db.scalar(m.select(m.func.count()).select_from(m.StudentClassHistory))
    assert before == after == 3
    assert [row["className"] for row in rows] == ["新班", "旧班"]
    assert [row["grade"] for row in rows] == [5, 4]
    assert rows[0]["current"] is True and rows[0]["leftAt"] is None
    assert rows[1]["current"] is False
    assert rows[1]["leaveReason"] == "transfer"
    assert rows[1]["leaveReasonName"] == "调班"
    assert rows[1]["joinedAt"] == m.school_local_iso(start)
    assert set(rows[0]) == {"id", "classID", "className", "grade", "joinedAt", "leftAt", "leaveReason", "leaveReasonName", "current"}
"""
    env = os.environ.copy()
    env.update({
        "DATABASE_URL": f"sqlite:///{tmp_path / 'class-history.sqlite3'}",
        "JWT_SECRET": "test-class-history-secret-0123456789abcdef0123456789abcdef",
        "COMMERCIAL_ADMIN_KEY": "test-class-history-commercial-key-0123456789",
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
