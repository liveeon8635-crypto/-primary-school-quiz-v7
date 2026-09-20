from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_teacher_ai_save_assign_preserves_rich_question_semantics(tmp_path):
    db_path = tmp_path / "teacher-ai-persistence.sqlite3"
    script = r'''
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
    class_id = client.get("/teacher/classes", headers=th).json()[0]["id"]

    rich = [
        {
            "grade": 5, "subject": "数学", "textbook": "人教版", "semester": "上册",
            "unit": "综合", "knowledge": "选择", "text": "2+3等于多少？",
            "options": ["4","5","6","7"], "correct_index": 1, "explanation": "2+3=5",
            "question_type": "single_choice", "answer": "", "accepted_answers": [], "figure": {}
        },
        {
            "grade": 5, "subject": "数学", "textbook": "人教版", "semester": "上册",
            "unit": "综合", "knowledge": "判断", "text": "0.5等于1/2。",
            "options": ["任意","任意"], "correct_index": 0, "explanation": "0.5=1/2",
            "question_type": "true_false", "answer": "", "accepted_answers": [], "figure": {}
        },
        {
            "grade": 5, "subject": "数学", "textbook": "人教版", "semester": "上册",
            "unit": "综合", "knowledge": "填空", "text": "点A横坐标是____。",
            "options": [], "correct_index": -1, "explanation": "读取横坐标",
            "question_type": "fill_blank", "answer": "3", "accepted_answers": ["3.0"],
            "figure": {"type": "coordinate_grid", "xMax": 5, "yMax": 5, "points": [{"x":3,"y":2,"label":"A"}]}
        },
        {
            "grade": 5, "subject": "数学", "textbook": "人教版", "semester": "上册",
            "unit": "综合", "knowledge": "计算", "text": "计算2.5×4。",
            "options": [], "correct_index": -1, "explanation": "2.5×4=10",
            "question_type": "calculation", "answer": "10", "accepted_answers": ["10.0"], "figure": {}
        },
        {
            "grade": 5, "subject": "数学", "textbook": "人教版", "semester": "上册",
            "unit": "综合", "knowledge": "应用", "text": "每袋5千克，2袋共多少千克？",
            "options": [], "correct_index": -1, "explanation": "5×2=10",
            "question_type": "short_answer", "answer": "10千克", "accepted_answers": ["10", "10kg"], "figure": {}
        },
    ]

    saved = client.post("/ai/questions/save", headers=th, json={"questions": rich})
    assert saved.status_code == 200, saved.text
    saved_items = saved.json()["items"]
    assert [x["questionType"] for x in saved_items] == [
        "single_choice", "true_false", "fill_blank", "calculation", "short_answer"
    ]
    assert saved_items[2]["answer"] == "3"
    assert saved_items[2]["acceptedAnswers"] == ["3.0"]
    assert saved_items[2]["figure"]["type"] == "coordinate_grid"

    assigned = client.post(
        "/ai/questions/assign",
        headers=th,
        json={
            "questions": rich,
            "title": "教师AI多题型闭环",
            "class_id": class_id,
            "due_date": "2026-09-30",
            "instructions": "",
        },
    )
    assert assigned.status_code == 200, assigned.text
    body = assigned.json()
    assert body["submissionMode"] == "quiz"
    aid = body["assignment"]["id"]
    pid = body["paperID"]

    public = client.get(f"/papers/{pid}/questions", headers=sh)
    assert public.status_code == 200, public.text
    items = public.json()
    assert [x["questionType"] for x in items] == [
        "single_choice", "true_false", "fill_blank", "calculation", "short_answer"
    ]
    assert items[1]["options"] == ["正确", "错误"]
    assert items[2]["figure"]["type"] == "coordinate_grid"
    assert "answer" not in items[2]
    assert "correctIndex" not in items[0]

    answers = [
        {"question_id": items[0]["id"], "selected_index": 1},
        {"question_id": items[1]["id"], "selected_index": 0},
        {"question_id": items[2]["id"], "text_answer": "3.0"},
        {"question_id": items[3]["id"], "text_answer": "10.0"},
        {"question_id": items[4]["id"], "text_answer": "10kg"},
    ]
    result = client.post(f"/student/assignments/{aid}/submit", headers=sh, json={"answers": answers})
    assert result.status_code == 200, result.text
    assert (result.json()["correct"], result.json()["total"], result.json()["score"]) == (5, 5, 100)

    with legacy.SessionLocal() as db:
        paper = db.get(legacy.Paper, pid)
        qids = json.loads(paper.question_ids_json)
        rows = [db.get(legacy.Question, qid) for qid in qids]
        assert [legacy.question_type_of(q) for q in rows] == [
            "single_choice", "true_false", "fill_blank", "calculation", "short_answer"
        ]
        assert legacy.question_answer_meta(rows[2])["answer"] == "3"
        assert legacy.question_answer_meta(rows[4])["accepted"] == ["10", "10kg"]
        assert legacy.question_figure(rows[2])["type"] == "coordinate_grid"

    manual = [{
        "grade": 5, "subject": "数学", "textbook": "人教版", "semester": "上册",
        "unit": "综合", "knowledge": "应用", "text": "说明你的解题思路。",
        "options": [], "correct_index": -1, "explanation": "教师审核",
        "question_type": "non_choice", "reference_answer": "根据数量关系列式并说明理由",
        "scoring_points": ["数量关系正确", "列式正确", "理由清楚"],
        "answer": "", "accepted_answers": [], "figure": {}
    }]
    manual_assigned = client.post(
        "/ai/questions/assign",
        headers=th,
        json={
            "questions": manual,
            "title": "教师AI主观题",
            "class_id": class_id,
            "due_date": "2026-09-30",
            "instructions": "",
        },
    )
    assert manual_assigned.status_code == 200, manual_assigned.text
    assert manual_assigned.json()["submissionMode"] == "media"
    manual_pid = manual_assigned.json()["paperID"]
    with legacy.SessionLocal() as db:
        paper = db.get(legacy.Paper, manual_pid)
        qid = json.loads(paper.question_ids_json)[0]
        q = db.get(legacy.Question, qid)
        meta = legacy.manual_question_meta(q)
        assert q.question_type == "non_choice"
        assert meta["reference_answer"] == "根据数量关系列式并说明理由"
        assert meta["scoring_points"] == ["数量关系正确", "列式正确", "理由清楚"]
'''

    env = os.environ.copy()
    env.update({
        "DATABASE_URL": f"sqlite:///{db_path}",
        "JWT_SECRET": "x" * 64,
        "COMMERCIAL_ADMIN_KEY": "y" * 40,
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
        "teacher AI persistence integration subprocess failed\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
