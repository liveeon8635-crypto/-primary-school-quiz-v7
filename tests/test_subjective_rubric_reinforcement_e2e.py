from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_teacher_confirmed_subjective_rubric_gap_reaches_reinforcement(tmp_path):
    db_path = tmp_path / "subjective-rubric-reinforcement.sqlite3"
    script = r"""
import json
from fastapi.testclient import TestClient
import app_v924 as legacy
from app import app


def login_and_change(client, username, old_password, new_password):
    r = client.post("/login", json={"username": username, "password": old_password, "remember": False})
    assert r.status_code == 200, r.text
    token = r.json()["token"]
    r = client.post(
        "/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={"current_password": old_password, "new_password": new_password, "remember": False},
    )
    assert r.status_code == 200, r.text
    return r.json()["token"]


with TestClient(app) as client:
    teacher_token = login_and_change(client, "teacher1", "123456", "Teacher1234")
    student_token = login_and_change(client, "student1", "123456", "Student1234")
    th = {"Authorization": f"Bearer {teacher_token}"}
    sh = {"Authorization": f"Bearer {student_token}"}
    sid = client.get("/session", headers=sh).json()["userID"]
    teacher_id = client.get("/session", headers=th).json()["userID"]
    class_id = client.get("/teacher/classes", headers=th).json()[0]["id"]

    assigned = client.post(
        "/ai/questions/assign",
        headers=th,
        json={
            "questions": [{
                "grade": 5,
                "subject": "数学",
                "textbook": "人教版",
                "semester": "上册",
                "unit": "小数乘法",
                "knowledge": "小数乘法应用",
                "text": "每千克苹果2.5元，买4千克一共多少元？写出列式、计算和答语。",
                "options": [],
                "correct_index": -1,
                "explanation": "2.5×4=10（元）",
                "question_type": "non_choice",
                "reference_answer": "2.5×4=10（元），答：一共10元。",
                "scoring_points": ["列式正确", "计算正确", "答语和单位正确"],
                "answer": "",
                "accepted_answers": [],
                "figure": {},
            }],
            "title": "主观题评分点闭环",
            "class_id": class_id,
            "due_date": "2026-09-30",
            "instructions": "完成后由教师确认评分。",
        },
    )
    assert assigned.status_code == 200, assigned.text
    aid = assigned.json()["assignment"]["id"]
    qid = assigned.json()["questionIDs"][0]
    assert assigned.json()["submissionMode"] == "media"

    with legacy.SessionLocal() as db:
        db.add(legacy.AIGradingReview(
            school_id=1,
            assignment_id=aid,
            student_id=sid,
            teacher_id=teacher_id,
            ai_result_json=json.dumps({
                "rubric_results": [{
                    "question_id": qid,
                    "knowledge": "小数乘法应用",
                    "met_points": ["列式正确"],
                    "missed_points": ["计算正确", "答语和单位正确"],
                    "suggested_ratio": 1 / 3,
                    "needs_teacher_review": [],
                }],
                "suggested_score": 33,
            }, ensure_ascii=False),
            suggested_score=33,
            status="draft",
        ))
        cfg = legacy.ai_config_for(db, 1, True)
        cfg.allow_student_data = True
        db.commit()

    confirmed = client.post(
        f"/teacher/assignments/{aid}/students/{sid}/grading-confirm",
        headers=th,
        json={"score": 33, "feedback": "计算和单位需要继续巩固。", "archive_wrong": True},
    )
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["rubricWrongArchived"] == 1

    with legacy.SessionLocal() as db:
        wrong = list(db.scalars(
            legacy.select(legacy.WrongQuestionRecord).where(
                legacy.WrongQuestionRecord.school_id == 1,
                legacy.WrongQuestionRecord.student_id == sid,
                legacy.WrongQuestionRecord.assignment_id == aid,
                legacy.WrongQuestionRecord.question_id == qid,
                legacy.WrongQuestionRecord.source == "ai",
                legacy.WrongQuestionRecord.status == "active",
            )
        ).all())
        assert len(wrong) == 1
        wrong_id = wrong[0].id
        assert "计算正确" in wrong[0].analysis
        assert "答语和单位正确" in wrong[0].analysis

    def fake_ai_call(db, user, feature, prompt, images=None, timeout=90):
        assert feature == "reinforcement_generate"
        assert "小数乘法应用" in prompt
        assert "计算正确" in prompt
        return json.dumps({"items": [{
            "question_type": "calculation",
            "grade": 5,
            "subject": "数学",
            "textbook": "人教版",
            "semester": "上册",
            "unit": "小数乘法",
            "knowledge": "小数乘法应用",
            "text": "3.2×5等于多少？",
            "options": [],
            "correct_index": -1,
            "answer": "16",
            "accepted_answers": ["16.0"],
            "figure": {},
            "explanation": "3.2×5=16",
        }]}, ensure_ascii=False)

    legacy._ai_call = fake_ai_call
    generated = client.post(
        f"/teacher/students/{sid}/reinforcement/generate",
        headers=th,
        json={"assignment_id": aid, "count": 1, "difficulty": "中等", "notes": "按评分点薄弱项生成"},
    )
    assert generated.status_code == 200, generated.text
    assert wrong_id in generated.json()["wrongIDs"]
    assert generated.json()["items"][0]["knowledge"] == "小数乘法应用"
"""

    env = os.environ.copy()
    env.update({
        "DATABASE_URL": f"sqlite:///{db_path}",
        "JWT_SECRET": "j" * 64,
        "COMMERCIAL_ADMIN_KEY": "c" * 40,
        "ENABLE_DEMO_SEED": "1",
        "PYTHONPATH": str(ROOT),
    })
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
        "subjective rubric reinforcement integration failed\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
