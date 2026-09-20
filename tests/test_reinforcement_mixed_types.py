from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_mixed_reinforcement_types_figures_and_text_grading(tmp_path):
    db_path = tmp_path / "reinforcement-mixed.sqlite3"
    script = r'''
import json
from fastapi.testclient import TestClient
import app_v924 as legacy
from app import app
from changying.services.assessment_feedback import student_assessment_context

def login_and_change(client, username, old_password, new_password):
    r = client.post("/login", json={"username": username, "password": old_password, "remember": False})
    assert r.status_code == 200, r.text
    token = r.json()["token"]
    r = client.post("/change-password", headers={"Authorization": f"Bearer {token}"}, json={"current_password": old_password, "new_password": new_password, "remember": False})
    assert r.status_code == 200, r.text
    return r.json()["token"]

with TestClient(app) as client:
    teacher_token = login_and_change(client, "teacher1", "123456", "Teacher1234")
    student_token = login_and_change(client, "student1", "123456", "Student1234")
    th = {"Authorization": f"Bearer {teacher_token}"}
    sh = {"Authorization": f"Bearer {student_token}"}
    sid = client.get("/session", headers=sh).json()["userID"]
    class_id = client.get("/teacher/classes", headers=th).json()[0]["id"]

    opts = client.get(f"/teacher/students/{sid}/practice-options", params={"grade": 5, "subject": "数学", "textbook": "人教版"}, headers=th).json()
    knowledge = opts["modules"][0]["knowledge"]
    created = client.post(f"/teacher/students/{sid}/auto-practice", headers=th, json={"grade": 5, "subject": "数学", "textbook": "人教版", "kind": "module", "knowledge": knowledge, "question_count": 4, "due_date": "2026-09-30", "class_id": class_id})
    assert created.status_code == 200, created.text
    aid = created.json()["assignment"]["id"]
    pid = created.json()["paper"]["id"]

    with legacy.SessionLocal() as db:
        paper = db.get(legacy.Paper, pid)
        qids = json.loads(paper.question_ids_json)
        qmap = {q.id: q for q in db.scalars(legacy.select(legacy.Question).where(legacy.Question.id.in_(qids))).all()}
        wrong_answers = []
        for qid in qids:
            q = qmap[qid]
            question_type = legacy.question_type_of(q)
            if question_type in {"single_choice", "true_false"}:
                options = json.loads(q.options_json)
                wrong_answers.append({"question_id": qid, "selected_index": (q.correct_index + 1) % len(options)})
            else:
                wrong_answers.append({"question_id": qid, "text_answer": "__definitely_wrong__"})

    submitted = client.post(f"/student/assignments/{aid}/submit", headers=sh, json={"answers": wrong_answers})
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["score"] == 0

    with legacy.SessionLocal() as db:
        cfg = legacy.ai_config_for(db, 1, True)
        cfg.allow_student_data = True
        db.commit()

    def fake_ai_call(db, user, feature, prompt, images=None, timeout=90):
        assert feature == "reinforcement_generate"
        assert "single_choice" in prompt and "fill_blank" in prompt and "figure" in prompt
        return json.dumps({"items": [
            {"question_type": "single_choice", "grade": 5, "subject": "数学", "textbook": "错误版", "semester": "上册", "unit": "小数除法", "knowledge": knowledge, "text": "下面哪个计算结果正确？", "options": ["1.2", "1.4", "1.6", "1.8"], "correct_index": 1, "answer": "", "accepted_answers": [], "figure": {}, "explanation": "选择正确结果。"},
            {"question_type": "true_false", "grade": 5, "subject": "数学", "textbook": "错误版", "semester": "上册", "unit": "多边形的面积", "knowledge": knowledge, "text": "图中平行四边形的面积计算方法是否正确？", "options": ["随意", "内容"], "correct_index": 0, "answer": "", "accepted_answers": [], "figure": {"type": "geometry", "shape": "parallelogram", "labels": {"bottom": "8 cm", "height": "5 cm"}}, "explanation": "底乘高。"},
            {"question_type": "fill_blank", "grade": 5, "subject": "数学", "textbook": "错误版", "semester": "上册", "unit": "位置", "knowledge": knowledge, "text": "点A向右移动2格后，横坐标是____。", "options": [], "correct_index": -1, "answer": "5", "accepted_answers": ["5.0"], "figure": {"type": "coordinate_grid", "xMax": 8, "yMax": 8, "points": [{"x": 3, "y": 4, "label": "A"}]}, "explanation": "横坐标增加2。"},
            {"question_type": "calculation", "grade": 5, "subject": "数学", "textbook": "错误版", "semester": "上册", "unit": "小数乘法", "knowledge": knowledge, "text": "计算 2.5×5。", "options": [], "correct_index": -1, "answer": "12.5", "accepted_answers": ["12.50"], "figure": {}, "explanation": "2.5×5=12.5。"}
        ]}, ensure_ascii=False)

    legacy._ai_call = fake_ai_call
    generated = client.post(f"/teacher/students/{sid}/reinforcement/generate", headers=th, json={"assignment_id": aid, "count": 4, "difficulty": "中等", "notes": ""})
    assert generated.status_code == 200, generated.text
    body = generated.json()
    assert [x["question_type"] for x in body["items"]] == ["single_choice", "true_false", "fill_blank", "calculation"]
    assert all(x["textbook"] == "人教版" for x in body["items"])
    assert body["items"][1]["options"] == ["正确", "错误"]
    assert body["items"][2]["figure"]["type"] == "coordinate_grid"

    assigned = client.post(f"/teacher/students/{sid}/reinforcement/assign", headers=th, json={"questions": body["items"], "title": "混合题型针对性练习", "due_date": "2026-09-30", "wrong_ids": body["wrongIDs"], "instructions": "完成混合题型练习"})
    assert assigned.status_code == 200, assigned.text
    rid = assigned.json()["assignment"]["id"]
    rpid = assigned.json()["paperID"]

    public = client.get(f"/papers/{rpid}/questions", headers=sh)
    assert public.status_code == 200, public.text
    items = public.json()
    assert [x["questionType"] for x in items] == ["single_choice", "true_false", "fill_blank", "calculation"]
    assert items[2]["figure"]["type"] == "coordinate_grid"
    assert "answer" not in items[2]
    assert "correctIndex" not in items[0]

    answers = [
        {"question_id": items[0]["id"], "selected_index": 1},
        {"question_id": items[1]["id"], "selected_index": 0},
        {"question_id": items[2]["id"], "text_answer": "4"},
        {"question_id": items[3]["id"], "text_answer": "12.50"},
    ]
    result = client.post(f"/student/assignments/{rid}/submit", headers=sh, json={"answers": answers})
    assert result.status_code == 200, result.text
    rb = result.json()
    assert (rb["correct"], rb["total"], rb["score"]) == (3, 4, 75)
    assert rb["learningFeedbackArchived"] == 1

    with legacy.SessionLocal() as db:
        paper = db.get(legacy.Paper, rpid)
        rows = [db.get(legacy.Question, qid) for qid in json.loads(paper.question_ids_json)]
        assert [legacy.question_type_of(q) for q in rows] == ["single_choice", "true_false", "fill_blank", "calculation"]
        assert legacy.question_answer_meta(rows[2])["answer"] == "5"
        assert legacy.question_figure(rows[2])["type"] == "coordinate_grid"
        wrong = list(db.scalars(legacy.select(legacy.WrongQuestionRecord).where(legacy.WrongQuestionRecord.assignment_id == rid, legacy.WrongQuestionRecord.student_id == sid)).all())
        assert len(wrong) == 1
        assert wrong[0].wrong_answer == "4"
        assert wrong[0].correct_answer == "5"
        link = db.scalar(legacy.select(legacy.ReinforcementLink).where(legacy.ReinforcementLink.assignment_id == rid, legacy.ReinforcementLink.student_id == sid))
        assert link.result_score == 75 and link.completed_at is not None
        context = student_assessment_context(db, AssignmentRecipient=legacy.AssignmentRecipient, Assignment=legacy.Assignment, Submission=legacy.Submission, Paper=legacy.Paper, Question=legacy.Question, school_id=1, student_id=sid, limit=6, textbook_filter="人教版")
        assert any(x["kind"] == "reinforcement" for x in context["assessments"])
'''

    env = os.environ.copy()
    env.update({
        "DATABASE_URL": f"sqlite:///{db_path}",
        "JWT_SECRET": "x" * 64,
        "COMMERCIAL_ADMIN_KEY": "y" * 40,
        "ENABLE_DEMO_SEED": "1",
        "PYTHONPATH": str(ROOT),
    })
    result = subprocess.run([sys.executable, "-c", script], cwd=ROOT, env=env, capture_output=True, text=True, timeout=180, check=False)
    assert result.returncode == 0, (
        "mixed reinforcement integration subprocess failed\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
