from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_teacher_confirmed_subjective_rubric_respects_archive_choice_and_feeds_reinforcement(tmp_path):
    db_path = tmp_path / "subjective-rubric-reinforcement.sqlite3"
    script = r'''
import json

from fastapi.testclient import TestClient

import app_v924 as legacy
from app import app


def login_and_change(client, username, old_password, new_password):
    login = client.post(
        "/login",
        json={"username": username, "password": old_password, "remember": False},
    )
    assert login.status_code == 200, login.text
    token = login.json()["token"]
    changed = client.post(
        "/change-password",
        headers={"Authorization": f"Bearer {token}"},
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

    teacher_session = client.get("/session", headers=th)
    student_session = client.get("/session", headers=sh)
    assert teacher_session.status_code == 200, teacher_session.text
    assert student_session.status_code == 200, student_session.text
    teacher_id = teacher_session.json()["userID"]
    sid = student_session.json()["userID"]

    classes = client.get("/teacher/classes", headers=th)
    assert classes.status_code == 200, classes.text
    class_id = classes.json()[0]["id"]

    manual = [{
        "grade": 5,
        "subject": "数学",
        "textbook": "人教版",
        "semester": "上册",
        "unit": "综合",
        "knowledge": "解决问题",
        "text": "说明每袋5千克、2袋共多少千克的解题思路。",
        "options": [],
        "correct_index": -1,
        "explanation": "教师审核",
        "question_type": "non_choice",
        "reference_answer": "先确定数量关系，再列式5×2=10，最后写答语和单位。",
        "scoring_points": ["数量关系正确", "列式正确", "答语和单位正确"],
        "answer": "",
        "accepted_answers": [],
        "figure": {},
    }]
    assigned = client.post(
        "/ai/questions/assign",
        headers=th,
        json={
            "questions": manual,
            "title": "教师AI主观题闭环回归",
            "class_id": class_id,
            "due_date": "2026-09-30",
            "instructions": "",
        },
    )
    assert assigned.status_code == 200, assigned.text
    assigned_body = assigned.json()
    assert assigned_body["submissionMode"] == "media"
    aid = assigned_body["assignment"]["id"]
    pid = assigned_body["paperID"]

    with legacy.SessionLocal() as db:
        paper = db.get(legacy.Paper, pid)
        qid = json.loads(paper.question_ids_json)[0]
        question = db.get(legacy.Question, qid)
        meta = legacy.manual_question_meta(question)
        assert meta["scoring_points"] == [
            "数量关系正确",
            "列式正确",
            "答语和单位正确",
        ]

        review = legacy.AIGradingReview(
            school_id=1,
            assignment_id=aid,
            student_id=sid,
            teacher_id=teacher_id,
            ai_result_json=json.dumps(
                {
                    "summary": "数量关系判断正确，但列式过程与单位需要改进。",
                    "rubric_results": [{
                        "question_id": qid,
                        "knowledge": "解决问题",
                        "met_points": ["数量关系正确"],
                        "missed_points": ["列式正确", "答语和单位正确"],
                        "suggested_ratio": 0.3333,
                        "needs_teacher_review": [],
                    }],
                    "suggested_score": 40,
                    "issues": [],
                },
                ensure_ascii=False,
            ),
            suggested_score=40,
            status="draft",
        )
        db.add(review)
        cfg = legacy.ai_config_for(db, 1, True)
        cfg.allow_student_data = True
        db.commit()

    no_archive = client.post(
        f"/teacher/assignments/{aid}/students/{sid}/grading-confirm",
        headers=th,
        json={
            "score": 40,
            "feedback": "先记录本次确认，但不归档错题。",
            "archive_wrong": False,
        },
    )
    assert no_archive.status_code == 200, no_archive.text
    no_archive_body = no_archive.json()
    assert no_archive_body["rubricWrongArchived"] == 0
    assert no_archive_body["scoreRecordedInProgress"] is True
    assert no_archive_body["learningEvidenceAdded"] >= 2
    assert "未归档错题" in no_archive_body["notice"]

    with legacy.SessionLocal() as db:
        wrong_before = list(
            db.scalars(
                legacy.select(legacy.WrongQuestionRecord).where(
                    legacy.WrongQuestionRecord.school_id == 1,
                    legacy.WrongQuestionRecord.student_id == sid,
                    legacy.WrongQuestionRecord.assignment_id == aid,
                )
            ).all()
        )
        assert wrong_before == []

        submission = db.scalar(
            legacy.select(legacy.Submission).where(
                legacy.Submission.school_id == 1,
                legacy.Submission.assignment_id == aid,
                legacy.Submission.student_id == sid,
            )
        )
        assert submission is not None
        assert submission.score == 40

    archived = client.post(
        f"/teacher/assignments/{aid}/students/{sid}/grading-confirm",
        headers=th,
        json={
            "score": 40,
            "feedback": "确认归档评分点薄弱项。",
            "archive_wrong": True,
        },
    )
    assert archived.status_code == 200, archived.text
    archived_body = archived.json()
    assert archived_body["rubricWrongArchived"] == 1

    with legacy.SessionLocal() as db:
        wrong = db.scalar(
            legacy.select(legacy.WrongQuestionRecord).where(
                legacy.WrongQuestionRecord.school_id == 1,
                legacy.WrongQuestionRecord.student_id == sid,
                legacy.WrongQuestionRecord.assignment_id == aid,
                legacy.WrongQuestionRecord.source == "ai",
            )
        )
        assert wrong is not None
        assert wrong.status == "active"
        assert wrong.subject == "数学"
        assert wrong.knowledge == "解决问题"
        assert "列式正确" in wrong.analysis
        assert "答语和单位正确" in wrong.analysis
        wrong_id = wrong.id

    def fake_ai_call(db, user, feature, prompt, images=None, timeout=90):
        assert feature == "reinforcement_generate"
        assert "列式正确" in prompt
        assert "答语和单位正确" in prompt
        return json.dumps(
            {
                "items": [{
                    "question_type": "single_choice",
                    "grade": 3,
                    "subject": "错误科目",
                    "textbook": "错误版",
                    "semester": "上册",
                    "unit": "",
                    "knowledge": "解决问题",
                    "text": "每盒6支笔，3盒共有多少支？",
                    "options": ["9", "12", "18", "24"],
                    "correct_index": 2,
                    "answer": "",
                    "accepted_answers": [],
                    "figure": {},
                    "explanation": "6×3=18。",
                }]
            },
            ensure_ascii=False,
        )

    legacy._ai_call = fake_ai_call
    generated = client.post(
        f"/teacher/students/{sid}/reinforcement/generate",
        headers=th,
        json={
            "assignment_id": aid,
            "count": 1,
            "difficulty": "中等",
            "notes": "针对教师确认的主观题评分点薄弱项生成",
        },
    )
    assert generated.status_code == 200, generated.text
    generated_body = generated.json()
    assert wrong_id in generated_body["wrongIDs"]
    assert generated_body["items"]
    assert generated_body["items"][0]["grade"] == 5
    assert generated_body["items"][0]["subject"] == "数学"
    assert generated_body["items"][0]["textbook"] == "人教版"
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
        "subjective-rubric-to-reinforcement integration subprocess failed\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
