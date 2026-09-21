from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_all_question_workflows_feed_one_student_point_dynamic(tmp_path):
    db_path = tmp_path / "learning-points-fusion.sqlite3"
    script = r'''
import json

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
        teacher = db.scalar(legacy.select(legacy.User).where(legacy.User.username == "teacher1"))
        student = db.scalar(legacy.select(legacy.User).where(legacy.User.username == "student1"))
        teacher_id = teacher.id
        sid = student.id

    baseline = client.get("/student/points", headers=sh)
    assert baseline.status_code == 200, baseline.text
    baseline_body = baseline.json()
    baseline_balance = baseline_body["summary"]["balance"]
    baseline_learning = baseline_body["summary"].get("learning", 0)

    classes = client.get("/teacher/classes", headers=th)
    assert classes.status_code == 200, classes.text
    class_id = classes.json()[0]["id"]

    objective = [
        {
            "grade": 5, "subject": "数学", "textbook": "人教版", "semester": "上册",
            "unit": "综合", "knowledge": "计算", "text": "2+3等于多少？",
            "options": ["4", "5", "6", "7"], "correct_index": 1, "explanation": "2+3=5",
            "question_type": "single_choice", "answer": "", "accepted_answers": [], "figure": {},
        },
        {
            "grade": 5, "subject": "数学", "textbook": "人教版", "semester": "上册",
            "unit": "综合", "knowledge": "计算", "text": "4+4等于多少？",
            "options": ["6", "7", "8", "9"], "correct_index": 2, "explanation": "4+4=8",
            "question_type": "single_choice", "answer": "", "accepted_answers": [], "figure": {},
        },
    ]
    assigned = client.post(
        "/ai/questions/assign",
        headers=th,
        json={
            "questions": objective,
            "title": "学习积分正式作业",
            "class_id": class_id,
            "due_date": "2026-09-30",
            "instructions": "",
        },
    )
    assert assigned.status_code == 200, assigned.text
    aid = assigned.json()["assignment"]["id"]
    pid = assigned.json()["paperID"]

    public_questions = client.get(f"/papers/{pid}/questions", headers=sh)
    assert public_questions.status_code == 200, public_questions.text
    public_items = public_questions.json()
    assert len(public_items) == 2
    assert all(item["learningPoints"] == 1 for item in public_items)

    with legacy.SessionLocal() as db:
        paper = db.get(legacy.Paper, pid)
        qids = json.loads(paper.question_ids_json)
        q1 = db.get(legacy.Question, qids[0])
        q2 = db.get(legacy.Question, qids[1])
        wrong2 = 0 if int(q2.correct_index) != 0 else 1

    submitted = client.post(
        f"/student/assignments/{aid}/submit",
        headers=sh,
        json={
            "answers": [
                {"question_id": q1.id, "selected_index": int(q1.correct_index)},
                {"question_id": q2.id, "selected_index": wrong2},
            ]
        },
    )
    assert submitted.status_code == 200, submitted.text
    submitted_body = submitted.json()
    assert submitted_body["correct"] == 1
    assert submitted_body["total"] == 2
    assert submitted_body["learningPointsAwarded"] == 1
    assert submitted_body["learningPointMax"] == 2

    after_assignment = client.get("/student/points", headers=sh).json()
    assert after_assignment["summary"]["balance"] == baseline_balance + 1
    assert after_assignment["summary"]["learning"] == baseline_learning + 1
    assert after_assignment["weekly"]["learning"] >= 1
    assignment_learning = [
        row for row in after_assignment["ledger"]
        if row["source"] == "learning_submission" and row["relatedID"] == submitted_body["id"]
    ]
    assert len(assignment_learning) == 1
    assert assignment_learning[0]["points"] == 1
    assert assignment_learning[0]["category"] == "learning"

    practice_question = [{
        "grade": 5, "subject": "数学", "textbook": "人教版", "semester": "上册",
        "unit": "综合", "knowledge": "计算", "text": "6+7等于多少？",
        "options": ["11", "12", "13", "14"], "correct_index": 2, "explanation": "6+7=13",
        "question_type": "single_choice", "answer": "", "accepted_answers": [], "figure": {},
    }]
    saved = client.post("/ai/questions/save", headers=th, json={"questions": practice_question})
    assert saved.status_code == 200, saved.text
    practice_qid = saved.json()["items"][0]["id"]

    practice = client.post(
        "/student/practice-submit",
        headers=sh,
        json={
            "title": "学习积分自主练习",
            "answers": [{"question_id": practice_qid, "selected_index": 2}],
        },
    )
    assert practice.status_code == 200, practice.text
    practice_body = practice.json()
    assert practice_body["learningPointsAwarded"] == 1
    assert practice_body["learningPointMax"] == 1

    after_practice = client.get("/student/points", headers=sh).json()
    assert after_practice["summary"]["balance"] == baseline_balance + 2
    assert after_practice["summary"]["learning"] == baseline_learning + 2
    practice_learning = [
        row for row in after_practice["ledger"]
        if row["source"] == "learning_submission" and row["relatedID"] == practice_body["id"]
    ]
    assert len(practice_learning) == 1

    manual = [{
        "grade": 5, "subject": "数学", "textbook": "人教版", "semester": "上册",
        "unit": "综合", "knowledge": "解决问题",
        "text": "说明每袋5千克、2袋共多少千克的解题思路。",
        "options": [], "correct_index": -1, "explanation": "教师审核",
        "question_type": "non_choice",
        "reference_answer": "根据数量关系列式5×2=10，并写答语和单位。",
        "scoring_points": ["数量关系正确", "列式正确", "答语和单位正确"],
        "answer": "", "accepted_answers": [], "figure": {},
    }]
    manual_assigned = client.post(
        "/ai/questions/assign",
        headers=th,
        json={
            "questions": manual,
            "title": "学习积分主观题",
            "class_id": class_id,
            "due_date": "2026-09-30",
            "instructions": "",
        },
    )
    assert manual_assigned.status_code == 200, manual_assigned.text
    manual_aid = manual_assigned.json()["assignment"]["id"]
    manual_pid = manual_assigned.json()["paperID"]

    with legacy.SessionLocal() as db:
        paper = db.get(legacy.Paper, manual_pid)
        manual_qid = json.loads(paper.question_ids_json)[0]
        review = legacy.AIGradingReview(
            school_id=1,
            assignment_id=manual_aid,
            student_id=sid,
            teacher_id=teacher_id,
            ai_result_json=json.dumps(
                {
                    "summary": "评分点整体达到要求。",
                    "rubric_results": [{
                        "question_id": manual_qid,
                        "knowledge": "解决问题",
                        "met_points": ["数量关系正确", "列式正确"],
                        "missed_points": ["答语和单位正确"],
                        "suggested_ratio": 0.6667,
                        "needs_teacher_review": [],
                    }],
                    "suggested_score": 70,
                    "issues": [],
                },
                ensure_ascii=False,
            ),
            suggested_score=70,
            status="draft",
        )
        db.add(review)
        db.commit()

    confirmed = client.post(
        f"/teacher/assignments/{manual_aid}/students/{sid}/grading-confirm",
        headers=th,
        json={"score": 70, "feedback": "继续注意答语单位。", "archive_wrong": True},
    )
    assert confirmed.status_code == 200, confirmed.text
    confirmed_body = confirmed.json()
    assert confirmed_body["learningPointsDelta"] == 1
    assert confirmed_body["learningPointsTotal"] == 1
    assert confirmed_body["learningPointMax"] == 1

    after_subjective = client.get("/student/points", headers=sh).json()
    assert after_subjective["summary"]["balance"] == baseline_balance + 3
    assert after_subjective["summary"]["learning"] == baseline_learning + 3
    grading_rows = [
        row for row in after_subjective["ledger"]
        if row["source"] == "learning_grading"
    ]
    assert len(grading_rows) == 1
    assert grading_rows[0]["points"] == 1
    assert grading_rows[0]["category"] == "learning"

    confirmed_again = client.post(
        f"/teacher/assignments/{manual_aid}/students/{sid}/grading-confirm",
        headers=th,
        json={"score": 70, "feedback": "重复确认不应重复积分。", "archive_wrong": True},
    )
    assert confirmed_again.status_code == 200, confirmed_again.text
    assert confirmed_again.json()["learningPointsDelta"] == 0
    assert confirmed_again.json()["learningPointsTotal"] == 1

    final_points = client.get("/student/points", headers=sh).json()
    assert final_points["summary"]["balance"] == baseline_balance + 3
    assert final_points["summary"]["learning"] == baseline_learning + 3
    assert "学习积分" in legacy.INDEX_HTML
    assert "本周学习" in legacy.INDEX_HTML

    reinforcement_questions = [
        {
            "grade": 5, "subject": "数学", "textbook": "人教版", "semester": "上册",
            "unit": "综合", "knowledge": "计算", "text": "3+4等于多少？",
            "options": ["5", "6", "7", "8"], "correct_index": 2, "explanation": "3+4=7",
            "question_type": "single_choice", "answer": "", "accepted_answers": [], "figure": {},
        },
        {
            "grade": 5, "subject": "数学", "textbook": "人教版", "semester": "上册",
            "unit": "综合", "knowledge": "计算", "text": "5+5等于多少？",
            "options": ["8", "9", "10", "11"], "correct_index": 2, "explanation": "5+5=10",
            "question_type": "single_choice", "answer": "", "accepted_answers": [], "figure": {},
        },
        {
            "grade": 5, "subject": "数学", "textbook": "人教版", "semester": "上册",
            "unit": "综合", "knowledge": "计算", "text": "6+6等于多少？",
            "options": ["10", "11", "12", "13"], "correct_index": 2, "explanation": "6+6=12",
            "question_type": "single_choice", "answer": "", "accepted_answers": [], "figure": {},
        },
    ]
    reinforcement_assigned = client.post(
        "/ai/questions/assign",
        headers=th,
        json={
            "questions": reinforcement_questions,
            "title": "学习积分数学针对性练习",
            "class_id": class_id,
            "due_date": "2026-09-30",
            "instructions": "",
        },
    )
    assert reinforcement_assigned.status_code == 200, reinforcement_assigned.text
    reinforcement_aid = reinforcement_assigned.json()["assignment"]["id"]
    reinforcement_pid = reinforcement_assigned.json()["paperID"]

    with legacy.SessionLocal() as db:
        paper = db.get(legacy.Paper, reinforcement_pid)
        reinforcement_qids = json.loads(paper.question_ids_json)
        reinforcement_rows = [db.get(legacy.Question, qid) for qid in reinforcement_qids]
        reinforcement_wrong = 0 if int(reinforcement_rows[2].correct_index) != 0 else 1

    reinforcement_submitted = client.post(
        f"/student/assignments/{reinforcement_aid}/submit",
        headers=sh,
        json={
            "answers": [
                {"question_id": reinforcement_rows[0].id, "selected_index": int(reinforcement_rows[0].correct_index)},
                {"question_id": reinforcement_rows[1].id, "selected_index": int(reinforcement_rows[1].correct_index)},
                {"question_id": reinforcement_rows[2].id, "selected_index": reinforcement_wrong},
            ]
        },
    )
    assert reinforcement_submitted.status_code == 200, reinforcement_submitted.text
    reinforcement_body = reinforcement_submitted.json()
    assert reinforcement_body["correct"] == 2
    assert reinforcement_body["total"] == 3
    assert reinforcement_body["learningPointsAwarded"] == 2
    assert reinforcement_body["learningPointMax"] == 3

    after_reinforcement = client.get("/student/points", headers=sh).json()
    assert after_reinforcement["summary"]["balance"] == baseline_balance + 5
    assert after_reinforcement["summary"]["learning"] == baseline_learning + 5
    reinforcement_learning = [
        row for row in after_reinforcement["ledger"]
        if row["source"] == "learning_submission" and row["relatedID"] == reinforcement_body["id"]
    ]
    assert len(reinforcement_learning) == 1
    assert reinforcement_learning[0]["points"] == 2
    assert reinforcement_learning[0]["category"] == "learning"

    reinforcement_resubmitted = client.post(
        f"/student/assignments/{reinforcement_aid}/submit",
        headers=sh,
        json={
            "answers": [
                {"question_id": reinforcement_rows[0].id, "selected_index": int(reinforcement_rows[0].correct_index)},
                {"question_id": reinforcement_rows[1].id, "selected_index": int(reinforcement_rows[1].correct_index)},
                {"question_id": reinforcement_rows[2].id, "selected_index": reinforcement_wrong},
            ]
        },
    )
    assert reinforcement_resubmitted.status_code == 409, reinforcement_resubmitted.text
    assert reinforcement_resubmitted.json()["detail"] == "在线答题已提交，不能重复提交"
    after_reinforcement_resubmit = client.get("/student/points", headers=sh).json()
    assert after_reinforcement_resubmit["summary"]["balance"] == baseline_balance + 5
    assert after_reinforcement_resubmit["summary"]["learning"] == baseline_learning + 5
    reinforcement_learning_after = [
        row for row in after_reinforcement_resubmit["ledger"]
        if row["source"] == "learning_submission" and row["relatedID"] == reinforcement_body["id"]
    ]
    assert len(reinforcement_learning_after) == 1
    assert reinforcement_learning_after[0]["points"] == 2
'''

    env = os.environ.copy()
    env.update(
        {
            "DATABASE_URL": f"sqlite:///{db_path}",
            "JWT_SECRET": "learning-points-test-" + "signing-material-0123456789abcdef",
            "COMMERCIAL_ADMIN_KEY": "learning-points-test-" + "operator-material-012345",
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
        "learning-points fusion integration subprocess failed\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
