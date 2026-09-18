from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_parent_history_is_attached_in_production_compat_chain(tmp_path):
    db_path = tmp_path / "parent-history.sqlite3"
    script = r"""
import app_v924 as legacy
from app import app  # noqa: F401

with legacy.SessionLocal() as db:
    student = db.scalar(
        legacy.select(legacy.User).where(
            legacy.User.username == "student1",
            legacy.User.role == "student",
        )
    )
    parent = db.scalar(
        legacy.select(legacy.User).where(
            legacy.User.username == "parent1",
            legacy.User.role == "parent",
        )
    )
    teacher = db.scalar(
        legacy.select(legacy.User).where(
            legacy.User.username == "teacher1",
            legacy.User.role == "teacher",
        )
    )
    assert student and parent and teacher

    current = db.scalar(
        legacy.select(legacy.ParentStudent).where(
            legacy.ParentStudent.student_id == student.id,
            legacy.ParentStudent.parent_id == parent.id,
        )
    )
    if current is None:
        db.add(
            legacy.ParentStudent(
                parent_id=parent.id,
                student_id=student.id,
            )
        )

    legacy.audit(
        db,
        teacher,
        "parent.bind",
        f"{student.id}:{student.name}:{parent.id}:{parent.name}",
    )
    db.commit()

    profile = legacy.student_growth_profile_data(
        db,
        student,
        student.school_id,
        None,
    )
    history = profile["parentHistory"]
    assert history
    assert history[0]["parentID"] == parent.id
    assert history[0]["current"] is True
    assert history[0]["startKnown"] is True

    link = db.scalar(
        legacy.select(legacy.ParentStudent).where(
            legacy.ParentStudent.student_id == student.id,
            legacy.ParentStudent.parent_id == parent.id,
        )
    )
    if link is not None:
        db.delete(link)
    legacy.audit(
        db,
        teacher,
        "parent.unbind",
        f"{student.id}:{student.name}:{parent.name}",
    )
    db.commit()

    closed = legacy.student_growth_profile_data(
        db,
        student,
        student.school_id,
        None,
    )["parentHistory"]
    assert closed
    assert closed[0]["parentID"] == parent.id
    assert closed[0]["current"] is False
    assert closed[0]["endReason"] == "unbind"
    assert closed[0]["endKnown"] is True
"""

    env = os.environ.copy()
    env.update(
        {
            "DATABASE_URL": f"sqlite:///{db_path}",
            "JWT_SECRET": "integration-test-jwt-secret-0123456789abcdef0123456789abcdef",
            "COMMERCIAL_ADMIN_KEY": "integration-test-commercial-key-0123456789",
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
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
