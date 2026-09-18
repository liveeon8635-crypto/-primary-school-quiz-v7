from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_former_teacher_can_query_only_own_historical_teaching_facts(tmp_path):
    db_path = tmp_path / "historical-teaching.sqlite3"
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
    student_token = login_and_change(
        client, "student1", "123456", "Student1234"
    )
    th = {"Authorization": f"Bearer {teacher_token}"}
    sh = {"Authorization": f"Bearer {student_token}"}

    student_session = client.get("/session", headers=sh)
    assert student_session.status_code == 200, student_session.text
    sid = student_session.json()["userID"]

    with legacy.SessionLocal() as db:
        teacher = db.scalar(
            legacy.select(legacy.User).where(
                legacy.User.username == "teacher1",
                legacy.User.role == "teacher",
            )
        )
        student = db.get(legacy.User, sid)
        admin = db.scalar(
            legacy.select(legacy.User).where(legacy.User.role == "admin")
        )
        assert teacher and student and admin

        teacher_links = db.scalars(
            legacy.select(legacy.ClassStudent)
            .join(
                legacy.SchoolClass,
                legacy.ClassStudent.class_id == legacy.SchoolClass.id,
            )
            .where(
                legacy.ClassStudent.student_id == student.id,
                legacy.SchoolClass.school_id == teacher.school_id,
                legacy.SchoolClass.teacher_id == teacher.id,
            )
        ).all()
        for link in teacher_links:
            db.delete(link)

        old_class = legacy.SchoolClass(
            school_id=teacher.school_id,
            name="历史教学班",
            grade=5,
            teacher_id=teacher.id,
        )
        current_class = legacy.SchoolClass(
            school_id=teacher.school_id,
            name="当前其他教师班",
            grade=6,
            teacher_id=admin.id,
        )
        db.add_all([old_class, current_class])
        db.flush()
        db.add(
            legacy.ClassStudent(
                class_id=current_class.id,
                student_id=student.id,
            )
        )

        paper = legacy.Paper(
            school_id=teacher.school_id,
            title="历史数学测验",
            grade=5,
            subject="数学",
            textbook="人教版",
            unit="分数",
            question_ids_json="[]",
            teacher_id=teacher.id,
        )
        db.add(paper)
        db.flush()
        assignment = legacy.Assignment(
            school_id=teacher.school_id,
            title="五年级历史任务",
            class_id=old_class.id,
            paper_id=paper.id,
            due_date="2026-06-20",
        )
        db.add(assignment)
        db.flush()
        db.add(
            legacy.AssignmentRecipient(
                school_id=teacher.school_id,
                assignment_id=assignment.id,
                class_id=old_class.id,
                student_id=student.id,
                source="assignment",
            )
        )
        db.add(
            legacy.Submission(
                school_id=teacher.school_id,
                assignment_id=assignment.id,
                student_id=student.id,
                title=assignment.title,
                score=88,
                correct=22,
                total=25,
                answers_json="[]",
            )
        )
        db.commit()

    full_profile = client.get(
        f"/teacher/students/{sid}/growth-profile",
        headers=th,
    )
    assert full_profile.status_code == 403

    history = client.get("/v1/teacher/history/students", headers=th)
    assert history.status_code == 200, history.text
    body = history.json()
    row = next(x for x in body["students"] if x["studentID"] == sid)
    assert row["scope"] == "teacher-owned-assignment-recipient-snapshots"
    assert row["assignmentCount"] >= 1
    assert any(x["title"] == "五年级历史任务" for x in row["records"])
    record = next(x for x in row["records"] if x["title"] == "五年级历史任务")
    assert record["className"] == "历史教学班"
    assert record["subject"] == "数学"
    assert record["submitted"] is True
    assert record["score"] == 88

    forbidden = client.get("/v1/teacher/history/students", headers=sh)
    assert forbidden.status_code == 403
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
