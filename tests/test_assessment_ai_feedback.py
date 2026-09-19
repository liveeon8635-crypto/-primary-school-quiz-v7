from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_auto_assessment_feedback_flows_into_ai_reinforcement(tmp_path):
    db_path = tmp_path / "assessment-ai-feedback.sqlite3"
    script = r'''
import json

from fastapi.testclient import TestClient

import app_v924 as legacy
from app import app
from changying.services.assessment_feedback import student_assessment_context


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

    student_session = client.get("/session", headers=sh)
    assert student_session.status_code == 200, student_session.text
    sid = student_session.json()["userID"]

    classes = client.get("/teacher/classes", headers=th)
    assert classes.status_code == 200, classes.text
    class_id = classes.json()[0]["id"]

    options = client.get(
        f"/teacher/students/{sid}/practice-options",
        params={"grade": 5, "subject": "数学", "textbook": "北师大版"},
        headers=th,
    )
    assert options.status_code == 200, options.text
    options_body = options.json()
    assert options_body["textbooks"] == ["人教版"]
    assert options_body["selectedTextbook"] == "人教版"
    assert options_body["modules"]
    knowledge = options_body["modules"][0]["knowledge"]

    rejected = client.post(
        f"/teacher/students/{sid}/auto-practice",
        headers=th,
        json={
            "grade": 5,
            "subject": "数学",
            "textbook": "北师大版",
            "kind": "module",
            "knowledge": knowledge,
            "question_count": 4,
            "due_date": "2026-09-30",
            "class_id": class_id,
        },
    )
    assert rejected.status_code == 400, rejected.text
    assert "人教版" in rejected.text

    created = client.post(
        f"/teacher/students/{sid}/auto-practice",
        headers=th,
        json={
            "grade": 5,
            "subject": "数学",
            "textbook": "人教版",
            "kind": "module",
            "knowledge": knowledge,
            "question_count": 4,
            "due_date": "2026-09-30",
            "class_id": class_id,
        },
    )
    assert created.status_code == 200, created.text
    created_body = created.json()
    aid = created_body["assignment"]["id"]
    pid = created_body["paper"]["id"]
    assert created_body["textbook"] == "人教版"

    questions = client.get(f"/papers/{pid}/questions", headers=sh)
    assert questions.status_code == 200, questions.text
    public_questions = questions.json()
    assert public_questions

    with legacy.SessionLocal() as db:
        paper = db.get(legacy.Paper, pid)
        qids = json.loads(paper.question_ids_json)
        qmap = {
            row.id: row
            for row in db.scalars(
                legacy.select(legacy.Question).where(
                    legacy.Question.id.in_(qids),
                    legacy.Question.school_id == paper.school_id,
                )
            ).all()
        }
        answers = []
        for qid in qids:
            q = qmap[qid]
            opts = json.loads(q.options_json)
            wrong_index = (int(q.correct_index) + 1) % len(opts)
            answers.append(
                {"question_id": qid, "selected_index": wrong_index}
            )

    submitted = client.post(
        f"/student/assignments/{aid}/submit",
        headers=sh,
        json={"answers": answers},
    )
    assert submitted.status_code == 200, submitted.text
    submit_body = submitted.json()
    assert submit_body["score"] == 0
    assert submit_body["assessmentFeedbackArchived"] == len(answers)

    with legacy.SessionLocal() as db:
        wrong = list(
            db.scalars(
                legacy.select(legacy.WrongQuestionRecord).where(
                    legacy.WrongQuestionRecord.school_id == 1,
                    legacy.WrongQuestionRecord.student_id == sid,
                    legacy.WrongQuestionRecord.assignment_id == aid,
                    legacy.WrongQuestionRecord.source == "assessment",
                )
            ).all()
        )
        assert len(wrong) == len(answers)
        assert all(row.status == "active" for row in wrong)

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
        assert context["primary"]["textbook"] == "人教版"
        assert context["primary"]["subject"] == "数学"
        assert context["weakKnowledge"]
        assert context["weakKnowledge"][0]["accuracy"] == 0

        cfg = legacy.ai_config_for(db, 1, True)
        cfg.allow_student_data = True
        db.commit()

    def fake_ai_call(db, user, feature, prompt, images=None, timeout=90):
        assert feature == "reinforcement_generate"
        assert "人教版" in prompt
        assert knowledge in prompt
        return json.dumps(
            {
                "items": [
                    {
                        "grade": 3,
                        "subject": "错误科目",
                        "textbook": "错误版",
                        "semester": "上册",
                        "unit": "",
                        "knowledge": knowledge,
                        "text": "针对薄弱知识点的新情境题？",
                        "options": ["1", "2", "3", "4"],
                        "correct_index": 1,
                        "explanation": "测试解析",
                    }
                ]
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
            "notes": "根据本次测试反馈生成",
        },
    )
    assert generated.status_code == 200, generated.text
    generated_body = generated.json()
    assert generated_body["assessmentContext"]["assessmentCount"] == 1
    assert generated_body["assessmentContext"]["primary"]["textbook"] == "人教版"
    assert generated_body["wrongIDs"]
    assert "已关联最近 1 次测试/练习反馈" in generated_body["notice"]
    assert generated_body["items"][0]["grade"] == 5
    assert generated_body["items"][0]["subject"] == "数学"
    assert generated_body["items"][0]["textbook"] == "人教版"

    assigned = client.post(
        f"/teacher/students/{sid}/reinforcement/assign",
        headers=th,
        json={
            "questions": generated_body["items"],
            "title": "AI 针对性练习",
            "due_date": "2026-09-30",
            "wrong_ids": generated_body["wrongIDs"],
            "instructions": "教师审核后的针对性练习",
        },
    )
    assert assigned.status_code == 200, assigned.text
    reinforcement_id = assigned.json()["assignment"]["id"]
    reinforcement_pid = assigned.json()["paperID"]

    reinforcement_questions = client.get(
        f"/papers/{reinforcement_pid}/questions",
        headers=sh,
    )
    assert reinforcement_questions.status_code == 200, reinforcement_questions.text
    q = reinforcement_questions.json()[0]
    wrong_index = 0 if q["correct_index"] != 0 else 1

    reinforcement_submit = client.post(
        f"/student/assignments/{reinforcement_id}/submit",
        headers=sh,
        json={
            "answers": [
                {
                    "question_id": q["id"],
                    "selected_index": wrong_index,
                }
            ]
        },
    )
    assert reinforcement_submit.status_code == 200, reinforcement_submit.text
    reinforcement_body = reinforcement_submit.json()
    assert reinforcement_body["score"] == 0
    assert reinforcement_body["learningFeedbackArchived"] == 1

    with legacy.SessionLocal() as db:
        new_wrong = list(
            db.scalars(
                legacy.select(legacy.WrongQuestionRecord).where(
                    legacy.WrongQuestionRecord.school_id == 1,
                    legacy.WrongQuestionRecord.student_id == sid,
                    legacy.WrongQuestionRecord.assignment_id == reinforcement_id,
                    legacy.WrongQuestionRecord.source == "assessment",
                )
            ).all()
        )
        assert len(new_wrong) == 1
        assert new_wrong[0].knowledge == knowledge
        assert new_wrong[0].status == "active"

        link = db.scalar(
            legacy.select(legacy.ReinforcementLink).where(
                legacy.ReinforcementLink.assignment_id == reinforcement_id,
                legacy.ReinforcementLink.student_id == sid,
            )
        )
        assert link is not None
        assert link.completed_at is not None
        assert link.result_score == 0

        reinforcement_context = student_assessment_context(
            db,
            AssignmentRecipient=legacy.AssignmentRecipient,
            Assignment=legacy.Assignment,
            Submission=legacy.Submission,
            Paper=legacy.Paper,
            Question=legacy.Question,
            school_id=1,
            student_id=sid,
            assignment_id=reinforcement_id,
            textbook_filter="人教版",
        )
        assert reinforcement_context["assessmentCount"] == 1
        assert reinforcement_context["primary"]["assignmentID"] == reinforcement_id
        assert reinforcement_context["primary"]["kind"] == "reinforcement"
        assert reinforcement_context["primary"]["score"] == 0
        assert reinforcement_context["weakKnowledge"][0]["knowledge"] == knowledge
        assert reinforcement_context["weakKnowledge"][0]["accuracy"] == 0
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
        "assessment-to-AI feedback integration subprocess failed\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
