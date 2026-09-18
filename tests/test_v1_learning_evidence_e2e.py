from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_real_database_record_is_shared_across_growth_profile_parent_and_student(tmp_path):
    db_path = tmp_path / "continuous-evidence-e2e.sqlite3"
    script = r"""
from fastapi.testclient import TestClient

import app_v924 as legacy
from app import app


def login_and_change(client, username, old_password, new_password):
    login = client.post(
        "/login",
        json={"username": username, "password": old_password, "remember": False},
    )
    assert login.status_code == 200, login.text
    old_token = login.json()["token"]
    changed = client.post(
        "/change-password",
        headers={"Authorization": f"Bearer {old_token}"},
        json={
            "current_password": old_password,
            "new_password": new_password,
            "remember": False,
        },
    )
    assert changed.status_code == 200, changed.text
    return changed.json()["token"]


with TestClient(app) as client:
    teacher_token = login_and_change(
        client, "teacher1", "123456", "Teacher1234"
    )
    parent_token = login_and_change(
        client, "parent1", "123456", "Parent1234"
    )
    student_token = login_and_change(
        client, "student1", "123456", "Student1234"
    )

    teacher_headers = {"Authorization": f"Bearer {teacher_token}"}
    parent_headers = {"Authorization": f"Bearer {parent_token}"}
    student_headers = {"Authorization": f"Bearer {student_token}"}

    student_session = client.get("/session", headers=student_headers)
    assert student_session.status_code == 200, student_session.text
    sid = student_session.json()["userID"]

    with legacy.SessionLocal() as db:
        student = db.scalar(
            legacy.select(legacy.User).where(
                legacy.User.id == sid,
                legacy.User.role == "student",
            )
        )
        assert student is not None
        db.add(
            legacy.Submission(
                school_id=student.school_id,
                assignment_id=None,
                student_id=student.id,
                title="连续档案真实历史练习",
                score=88,
                correct=22,
                total=25,
                answers_json="[]",
            )
        )
        db.commit()

    teacher_profile = client.get(
        f"/teacher/students/{sid}/growth-profile",
        headers=teacher_headers,
    )
    assert teacher_profile.status_code == 200, teacher_profile.text
    teacher_evidence = teacher_profile.json()["learningEvidence"]
    assert teacher_evidence["studentId"] == str(sid)
    assert teacher_evidence["sampleCount"] >= 1
    assert teacher_evidence["dimensions"] == ["performance"]
    assert teacher_evidence["masteryInferred"] is False

    parent_evidence = client.get(
        f"/v1/students/{sid}/learning-evidence",
        headers=parent_headers,
    )
    assert parent_evidence.status_code == 200, parent_evidence.text

    student_evidence = client.get(
        f"/v1/students/{sid}/learning-evidence",
        headers=student_headers,
    )
    assert student_evidence.status_code == 200, student_evidence.text

    parent_body = parent_evidence.json()
    student_body = student_evidence.json()

    assert parent_body["studentId"] == teacher_evidence["studentId"] == student_body["studentId"]
    assert parent_body["sampleCount"] == teacher_evidence["sampleCount"] == student_body["sampleCount"]
    assert parent_body["dimensions"] == teacher_evidence["dimensions"] == student_body["dimensions"]
    assert parent_body["masteryInferred"] is False
    assert student_body["masteryInferred"] is False
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
        "continuous evidence E2E subprocess failed\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
