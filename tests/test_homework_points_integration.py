"""Late-care consolidation practice uses the new rule instead of per-question learning points."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SCRIPT = r'''
from fastapi.testclient import TestClient

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
        th = headers_for(db, "teacher1")
        sh = headers_for(db, "student1")

    baseline = client.get("/student/points", headers=sh).json()
    baseline_balance = baseline["summary"]["balance"]
    baseline_learning = baseline["summary"].get("learning", 0)

    classes = client.get("/teacher/classes", headers=th).json()
    class_id = classes[0]["id"]

    questions = [
        {
            "grade": 5, "subject": "数学", "textbook": "人教版", "semester": "上册",
            "unit": "综合", "knowledge": "计算", "text": "1+1等于多少？",
            "options": ["1", "2", "3", "4"], "correct_index": 1,
            "explanation": "1+1=2", "question_type": "single_choice",
            "answer": "", "accepted_answers": [], "figure": {},
        },
        {
            "grade": 5, "subject": "数学", "textbook": "人教版", "semester": "上册",
            "unit": "综合", "knowledge": "计算", "text": "2+2等于多少？",
            "options": ["2", "3", "4", "5"], "correct_index": 2,
            "explanation": "2+2=4", "question_type": "single_choice",
            "answer": "", "accepted_answers": [], "figure": {},
        },
    ]
    assigned = client.post(
        "/ai/questions/assign",
        headers=th,
        json={
            "questions": questions,
            "title": "学生1 · 晚托提问巩固练习（数学）",
            "class_id": class_id,
            "due_date": "2099-01-01",
            "instructions": "晚托巩固练习",
        },
    )
    assert assigned.status_code == 200, assigned.text
    aid = assigned.json()["assignment"]["id"]
    pid = assigned.json()["paperID"]

    public = client.get(f"/papers/{pid}/questions", headers=sh).json()
    assert len(public) == 2
    with legacy.SessionLocal() as db:
        paper = db.get(legacy.Paper, pid)
        import json
        qids = json.loads(paper.question_ids_json)
        q1 = db.get(legacy.Question, qids[0])
        q2 = db.get(legacy.Question, qids[1])

    submitted = client.post(
        f"/student/assignments/{aid}/submit",
        headers=sh,
        json={"answers": [
            {"question_id": q1.id, "selected_index": int(q1.correct_index)},
            {"question_id": q2.id, "selected_index": 0 if int(q2.correct_index) != 0 else 1},
        ]},
    )
    assert submitted.status_code == 200, submitted.text
    body = submitted.json()
    # 按时 +3；1/2 = 50%，正确率 -1；合计 2。原来的每题 1 学习积分不再发放。
    assert body["learningPointsAwarded"] == 0
    assert body["homeworkPointsAwarded"] == 2
    assert body["homeworkPointsDetail"]["onTime"] is True
    assert body["homeworkPointsDetail"]["accuracy"] == 50.0

    after = client.get("/student/points", headers=sh).json()
    assert after["summary"]["balance"] == baseline_balance + 2
    assert after["summary"].get("learning", 0) == baseline_learning + 2

    rows = [row for row in after["ledger"] if row["relatedID"] == body["id"]]
    homework = [row for row in rows if row["source"] == "homework_practice"]
    learning = [row for row in rows if row["source"] == "learning_submission"]
    assert len(homework) == 1, rows
    assert homework[0]["points"] == 2 and homework[0]["category"] == "learning"
    assert learning == [], rows

    page = client.get("/v1", headers=sh)
    assert page.status_code == 200, page.text
    assert "homeworkPointsDetail" in page.text
    assert "晚托作业积分" in page.text

print("OK")
'''


def test_late_care_practice_replaces_learning_points(tmp_path):
    db_path = tmp_path / "homework-points.sqlite3"
    env = dict(os.environ)
    env.update({
        "DATABASE_URL": "sqlite:///" + str(db_path).replace("\\", "/"),
        "HOMEWORK_ASSISTANT": "1",
        "KNOWLEDGE_MAP": "1",
        "PYTHONPATH": str(ROOT),
    })
    result = subprocess.run(
        [sys.executable, "-c", SCRIPT],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        timeout=300,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "OK" in result.stdout
