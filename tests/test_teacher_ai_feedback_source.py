from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_teacher_ai_direct_practice_reenters_reinforcement_context(tmp_path):
    db_path = tmp_path / "teacher-ai-feedback.sqlite3"
    script = r'''
import json
from fastapi.testclient import TestClient

import app_v924 as legacy
from app import app
from changying.services.assessment_feedback import (
    LEARNING_FEEDBACK_SOURCES,
    student_assessment_context,
)


def login_and_change(client, username, old_password, new_password):
    r = client.post(
        "/login",
        json={"username": username, "password": old_password, "remember": False},
    )
    assert r.status_code == 200, r.text
    token = r.json()["token"]
    r = client.post(
        "/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "current_password": old_password,
            "new_password": new_password,
            "remember": False,
        },
    )
    assert r.status_code == 200, r.text
    return r.json()["token"]


assert LEARNING_FEEDBACK_SOURCES["teacher_ai_practice"] == "teacher_ai"

with TestClient(app) as client:
    teacher_token = login_and_change(
        client, "teacher1", "123456", "Teacher1234"
    )
    student_token = login_and_change(
        client, "student1", "123456", "Student1234"
    )
    th = {"Authorization": f"Bearer {teacher_token}"}
    sh = {"Authorization": f"Bearer {student_token}"}

    session = client.get("/session", headers=sh)
    assert session.status_code == 200, session.text
    sid = session.json()["userID"]

    classes = client.get("/teacher/classes", headers=th)
    assert classes.status_code == 200, classes.text
    class_id = classes.json()[0]["id"]

    questions = [
        {
            "grade": 5,
            "subject": "数学",
            "textbook": "人教版",
            "semester": "上册",
            "unit": "综合",
            "knowledge": "小数乘法",
            "text": "2.5×4等于多少？",
            "options": ["8", "9", "10", "12"],
            "correct_index": 2,
            "explanation": "2.5×4=10",
            "question_type": "single_choice",
            "answer": "",
            "accepted_answers": [],
            "figure": {},
        }
    ]

    assigned = client.post(
        "/ai/questions/assign",
        headers=th,
        json={
            "questions": questions,
            "title": "教师AI反馈闭环",
            "class_id": class_id,
            "due_date": "2026-09-30",
            "instructions": "",
        },
    )
    assert assigned.status_code == 200, assigned.text
    assigned_body = assigned.json()
    assert assigned_body["submissionMode"] == "quiz"
    aid = assigned_body["assignment"]["id"]
    pid = assigned_body["paperID"]

    with legacy.SessionLocal() as db:
        recipient = db.scalar(
            legacy.select(legacy.AssignmentRecipient).where(
                legacy.AssignmentRecipient.assignment_id == aid,
                legacy.AssignmentRecipient.student_id == sid,
            )
        )
        assert recipient is not None
        assert recipient.source == "teacher_ai_practice"

    public = client.get(f"/papers/{pid}/questions", headers=sh)
    assert public.status_code == 200, public.text
    item = public.json()[0]

    with legacy.SessionLocal() as db:
        internal = db.get(legacy.Question, item["id"])
        assert internal is not None
        wrong_index = 0 if int(internal.correct_index) != 0 else 1

    submitted = client.post(
        f"/student/assignments/{aid}/submit",
        headers=sh,
        json={
            "answers": [
                {
                    "question_id": item["id"],
                    "selected_index": wrong_index,
                }
            ]
        },
    )
    assert submitted.status_code == 200, submitted.text
    submitted_body = submitted.json()
    assert submitted_body["score"] == 0
    assert submitted_body["assessmentFeedbackArchived"] == 1
    assert submitted_body["learningFeedbackArchived"] == 1
    assert submitted_body["learningEvidenceAdded"] == 2

    with legacy.SessionLocal() as db:
        wrong = list(
            db.scalars(
                legacy.select(legacy.WrongQuestionRecord).where(
                    legacy.WrongQuestionRecord.student_id == sid,
                    legacy.WrongQuestionRecord.assignment_id == aid,
                    legacy.WrongQuestionRecord.source == "assessment",
                )
            ).all()
        )
        assert len(wrong) == 1
        assert wrong[0].knowledge == "小数乘法"
        assert wrong[0].status == "active"

        context = student_assessment_context(
            db,
            AssignmentRecipient=legacy.AssignmentRecipient,
            Assignment=legacy.Assignment,
            Submission=legacy.Submission,
            Paper=legacy.Paper,
            Question=legacy.Question,
            school_id=1,
            student_id=sid,
            assignment_id=aid,
            textbook_filter="人教版",
        )
        assert context["assessmentCount"] == 1
        assert context["primary"]["assignmentID"] == aid
        assert context["primary"]["kind"] == "teacher_ai"
        assert context["primary"]["subject"] == "数学"
        assert context["primary"]["textbook"] == "人教版"
        assert context["weakKnowledge"][0]["knowledge"] == "小数乘法"
        assert context["weakKnowledge"][0]["accuracy"] == 0
'''

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
        timeout=180,
        check=False,
    )
    assert result.returncode == 0, (
        "teacher AI feedback loop integration failed\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
