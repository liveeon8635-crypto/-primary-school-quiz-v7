from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_question_paper_assignment_submission_roundtrip(tmp_path):
    db_path = tmp_path / "teaching-crud.sqlite3"
    script = r'''
from fastapi.testclient import TestClient
from sqlalchemy import select

import app_v924 as legacy
from app import app


def headers_for(db, username):
    user = db.scalar(legacy.select(legacy.User).where(legacy.User.username == username))
    assert user is not None
    security = legacy.security_for(db, user)
    security.must_change_password = False
    db.commit()
    return {"Authorization": "Bearer " + legacy.make_token(user, security, False)}


with TestClient(app) as client:
    with legacy.SessionLocal() as db:
        teacher_headers = headers_for(db, "teacher1")
        student_headers = headers_for(db, "student1")

    classes = client.get("/teacher/classes", headers=teacher_headers)
    assert classes.status_code == 200, classes.text
    klass = next(row for row in classes.json() if row["studentCount"] >= 1)

    created_question = client.post(
        "/questions",
        headers=teacher_headers,
        json={
            "grade": klass["grade"],
            "subject": "数学",
            "textbook": "人教版",
            "semester": "上册",
            "unit": "C1 回归测试",
            "knowledge": "加法事实",
            "text": "2 + 3 = ?",
            "options": ["4", "5", "6", "7"],
            "correct_index": 1,
            "explanation": "2+3=5",
        },
    )
    assert created_question.status_code == 200, created_question.text
    question = created_question.json()
    qid = question["id"]
    assert question["correctIndex"] == 1

    listed_questions = client.get(
        "/questions",
        headers=teacher_headers,
        params={"grade": klass["grade"], "subject": "数学", "unit": "C1 回归测试"},
    )
    assert listed_questions.status_code == 200, listed_questions.text
    assert any(row["id"] == qid for row in listed_questions.json())

    created_paper = client.post(
        "/teacher/papers",
        headers=teacher_headers,
        json={
            "title": "C1 最小教学回归试卷",
            "grade": klass["grade"],
            "subject": "数学",
            "textbook": "人教版",
            "unit": "C1 回归测试",
            "question_ids": [qid],
        },
    )
    assert created_paper.status_code == 200, created_paper.text
    paper = created_paper.json()
    assert paper["questionIDs"] == [qid]

    created_assignment = client.post(
        "/teacher/assignments",
        headers=teacher_headers,
        json={
            "title": "C1 最小教学回归作业",
            "class_id": klass["id"],
            "paper_id": paper["id"],
            "due_date": "2099-12-31",
            "submission_mode": "quiz",
            "subject": "数学",
            "textbook": "人教版",
            "unit": "C1 回归测试",
            "instructions": "仅用于隔离数据库回归测试",
        },
    )
    assert created_assignment.status_code == 200, created_assignment.text
    assignment = created_assignment.json()
    aid = assignment["id"]
    assert assignment["studentCount"] >= 1
    assert assignment["submissionCount"] == 0
    assert assignment["submissionMode"] == "quiz"

    teacher_assignments = client.get("/teacher/assignments", headers=teacher_headers)
    assert teacher_assignments.status_code == 200, teacher_assignments.text
    assert any(row["id"] == aid for row in teacher_assignments.json())

    submitted = client.post(
        f"/student/assignments/{aid}/submit",
        headers=student_headers,
        json={"answers": [{"question_id": qid, "selected_index": 1}]},
    )
    assert submitted.status_code == 200, submitted.text
    result = submitted.json()
    assert result["score"] == 100
    assert result["correct"] == 1
    assert result["total"] == 1
    assert result["completed"] is True

    duplicate = client.post(
        f"/student/assignments/{aid}/submit",
        headers=student_headers,
        json={"answers": [{"question_id": qid, "selected_index": 1}]},
    )
    assert duplicate.status_code == 200, duplicate.text
    assert duplicate.json()["id"] == result["id"]
    assert duplicate.json()["learningPointsAwarded"] == 0

    submissions = client.get(
        f"/teacher/assignments/{aid}/submissions",
        headers=teacher_headers,
    )
    assert submissions.status_code == 200, submissions.text
    submitted_rows = [row for row in submissions.json() if row["id"] is not None]
    assert len(submitted_rows) == 1
    assert submitted_rows[0]["score"] == 100
    assert submitted_rows[0]["statusCode"] == "completed"

    with legacy.SessionLocal() as db:
        q = db.get(legacy.Question, qid)
        p = db.get(legacy.Paper, paper["id"])
        a = db.get(legacy.Assignment, aid)
        recipients = db.scalars(
            select(legacy.AssignmentRecipient).where(
                legacy.AssignmentRecipient.assignment_id == aid
            )
        ).all()
        saved_submissions = db.scalars(
            select(legacy.Submission).where(
                legacy.Submission.assignment_id == aid
            )
        ).all()
        assert q is not None and q.knowledge == "加法事实"
        assert p is not None and p.teacher_id is not None
        assert a is not None and a.paper_id == p.id
        assert len(recipients) >= 1
        assert len(saved_submissions) == 1
        assert saved_submissions[0].score == 100
'''

    env = os.environ.copy()
    env.update(
        {
            "DATABASE_URL": f"sqlite:///{db_path}",
            "JWT_SECRET": "crud-test-only-signing-material-0123456789abcdef",
            "COMMERCIAL_ADMIN_KEY": "crud-test-only-operator-material-012345",
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
        "isolated teaching CRUD subprocess failed\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )

