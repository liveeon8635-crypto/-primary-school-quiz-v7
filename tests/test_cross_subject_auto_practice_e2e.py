from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_english_and_chinese_auto_practice_reach_real_submission_loop(tmp_path):
    db_path = tmp_path / "cross-subject-acceptance.sqlite3"
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


def answer_for(question, correct):
    qtype = legacy.question_type_of(question)
    if qtype in ("single_choice", "true_false"):
        options = json.loads(question.options_json or "[]")
        if correct:
            selected = int(question.correct_index)
        else:
            selected = next(i for i in range(len(options)) if i != int(question.correct_index))
        return {"question_id": question.id, "selected_index": selected}
    meta = legacy.question_answer_meta(question)
    return {
        "question_id": question.id,
        "text_answer": meta["answer"] if correct else "__wrong_answer__",
    }


with TestClient(app) as client:
    with legacy.SessionLocal() as db:
        th = headers_for(db, "teacher1")
        sh = headers_for(db, "student1")
        student = db.scalar(legacy.select(legacy.User).where(legacy.User.username == "student1"))
        sid = int(student.id)

    classes = client.get("/teacher/classes", headers=th)
    assert classes.status_code == 200, classes.text
    class_id = classes.json()[0]["id"]

    points_before = client.get("/student/points", headers=sh)
    assert points_before.status_code == 200, points_before.text
    balance = points_before.json()["summary"]["balance"]

    with legacy.SessionLocal() as db:
        cfg = legacy.ai_config_for(db, 1, True)
        cfg.allow_student_data = True
        db.commit()

    def fake_ai_call(db, user, feature, prompt, images=None, timeout=90):
        assert feature == "reinforcement_generate"
        subject = "英语" if '"subject": "英语"' in prompt else "语文"
        if subject == "英语":
            items = [
                {
                    "question_type": "single_choice",
                    "grade": 5,
                    "subject": "错误学科",
                    "textbook": "错误版",
                    "semester": "上册",
                    "unit": "Unit 1",
                    "knowledge": "人物特征词汇",
                    "text": "Which word means '友善的'?",
                    "options": ["kind", "sad", "tired", "empty"],
                    "correct_index": 0,
                    "answer": "",
                    "accepted_answers": [],
                    "figure": {},
                    "explanation": "kind means 友善的。",
                },
                {
                    "question_type": "true_false",
                    "grade": 5,
                    "subject": "错误学科",
                    "textbook": "错误版",
                    "semester": "上册",
                    "unit": "Unit 1",
                    "knowledge": "人物描述句型",
                    "text": "True or false: 'She is kind.' is correct English.",
                    "options": ["X", "Y"],
                    "correct_index": 0,
                    "answer": "",
                    "accepted_answers": [],
                    "figure": {},
                    "explanation": "The sentence is correct.",
                },
                {
                    "question_type": "fill_blank",
                    "grade": 5,
                    "subject": "错误学科",
                    "textbook": "错误版",
                    "semester": "上册",
                    "unit": "Unit 1",
                    "knowledge": "人物特征词汇",
                    "text": "Complete: She is _____. (友善的)",
                    "options": [],
                    "correct_index": -1,
                    "answer": "kind",
                    "accepted_answers": ["Kind"],
                    "figure": {},
                    "explanation": "kind",
                },
            ]
        else:
            items = [
                {
                    "question_type": "single_choice",
                    "grade": 5,
                    "subject": "错误学科",
                    "textbook": "错误版",
                    "semester": "上册",
                    "unit": "全册基础",
                    "knowledge": "词语理解",
                    "text": "“镇定自若”的意思最接近哪一项？",
                    "options": ["沉着不慌张", "十分兴奋", "非常害怕", "故意回避"],
                    "correct_index": 0,
                    "answer": "",
                    "accepted_answers": [],
                    "figure": {},
                    "explanation": "结合语境理解词义。",
                },
                {
                    "question_type": "true_false",
                    "grade": 5,
                    "subject": "错误学科",
                    "textbook": "错误版",
                    "semester": "上册",
                    "unit": "全册基础",
                    "knowledge": "关联词运用",
                    "text": "判断：“虽然天气很冷，但是同学们仍按计划观察。”关联词使用恰当。",
                    "options": ["X", "Y"],
                    "correct_index": 0,
                    "answer": "",
                    "accepted_answers": [],
                    "figure": {},
                    "explanation": "前后是转折关系。",
                },
                {
                    "question_type": "fill_blank",
                    "grade": 5,
                    "subject": "错误学科",
                    "textbook": "错误版",
                    "semester": "上册",
                    "unit": "全册基础",
                    "knowledge": "关联词运用",
                    "text": "填写关联词：_____天气很冷，_____同学们仍按计划观察。",
                    "options": [],
                    "correct_index": -1,
                    "answer": "虽然……但是……",
                    "accepted_answers": ["虽然...但是..."],
                    "figure": {},
                    "explanation": "表示转折关系。",
                },
            ]
        return json.dumps({"items": items}, ensure_ascii=False)

    legacy._ai_call = fake_ai_call

    subjects = [
        ("英语", "人教版（PEP·当前最新版）"),
        ("语文", "统编版（人民教育出版社）"),
    ]

    for subject, textbook in subjects:
        options = client.get(
            f"/teacher/students/{sid}/practice-options",
            headers=th,
            params={"grade": 5, "subject": subject, "textbook": textbook},
        )
        assert options.status_code == 200, options.text
        option_body = options.json()
        assert option_body["selectedSubject"] == subject
        assert option_body["selectedTextbook"] == textbook
        assert option_body["availableQuestionCount"] == 129
        assert len(option_body["modules"]) == 16

        created = client.post(
            f"/teacher/students/{sid}/auto-practice",
            headers=th,
            json={
                "grade": 5,
                "subject": subject,
                "textbook": textbook,
                "kind": "comprehensive",
                "knowledge": "",
                "question_count": 8,
                "due_date": "2099-12-31",
                "class_id": class_id,
            },
        )
        assert created.status_code == 200, created.text
        created_body = created.json()
        aid = created_body["assignment"]["id"]
        pid = created_body["paper"]["id"]
        assert created_body["questionCount"] == 8
        assert created_body["textbook"] == textbook

        public = client.get(f"/papers/{pid}/questions", headers=sh)
        assert public.status_code == 200, public.text
        public_rows = public.json()
        assert len(public_rows) == 8
        types = {row["questionType"] for row in public_rows}
        assert {"single_choice", "true_false", "fill_blank"} <= types
        assert all("correctIndex" not in row for row in public_rows)
        assert all("answer" not in row for row in public_rows)

        with legacy.SessionLocal() as db:
            paper = db.get(legacy.Paper, pid)
            qids = json.loads(paper.question_ids_json)
            questions = [db.get(legacy.Question, qid) for qid in qids]
            answers = [answer_for(q, i % 2 == 0) for i, q in enumerate(questions)]

        submitted = client.post(
            f"/student/assignments/{aid}/submit",
            headers=sh,
            json={"answers": answers},
        )
        assert submitted.status_code == 200, submitted.text
        result = submitted.json()
        assert result["correct"] == 4
        assert result["total"] == 8
        assert result["score"] == 50
        assert result["learningPointsAwarded"] == 12
        assert result["learningPointMax"] == 16
        assert result["assessmentFeedbackArchived"] == 4

        balance += 12
        points = client.get("/student/points", headers=sh)
        assert points.status_code == 200, points.text
        assert points.json()["summary"]["balance"] == balance

        progress = client.get("/student/progress", headers=sh)
        assert progress.status_code == 200, progress.text
        latest = progress.json()["latestSubmission"]
        assert latest["assignmentID"] == aid
        assert latest["subject"] == subject
        assert latest["textbook"] == textbook
        assert latest["correct"] == 4
        assert latest["total"] == 8

        with legacy.SessionLocal() as db:
            wrong_count = db.scalar(
                legacy.select(legacy.func.count())
                .select_from(legacy.WrongQuestionRecord)
                .where(
                    legacy.WrongQuestionRecord.assignment_id == aid,
                    legacy.WrongQuestionRecord.student_id == sid,
                    legacy.WrongQuestionRecord.status == "active",
                )
            )
            assert int(wrong_count or 0) == 4

        generated = client.post(
            f"/teacher/students/{sid}/reinforcement/generate",
            headers=th,
            json={"assignment_id": aid, "count": 3, "difficulty": "中等", "notes": ""},
        )
        assert generated.status_code == 200, generated.text
        generated_body = generated.json()
        context = generated_body["assessmentContext"]
        assert context["primary"]["assignmentID"] == aid
        assert context["primary"]["subject"] == subject
        assert context["primary"]["textbook"] == textbook
        assert len(generated_body["wrongIDs"]) == 4
        assert {item["question_type"] for item in generated_body["items"]} == {
            "single_choice",
            "true_false",
            "fill_blank",
        }
        assert all(item["subject"] == subject for item in generated_body["items"])
        assert all(item["textbook"] == textbook for item in generated_body["items"])
        assert all(item["figure"] == {} for item in generated_body["items"])
        truth_item = next(
            item for item in generated_body["items"]
            if item["question_type"] == "true_false"
        )
        assert truth_item["options"] == (
            ["True", "False"] if subject == "英语" else ["正确", "错误"]
        )

        assigned = client.post(
            f"/teacher/students/{sid}/reinforcement/assign",
            headers=th,
            json={
                "questions": generated_body["items"],
                "title": f"{subject}针对性练习",
                "due_date": "2099-12-31",
                "wrong_ids": generated_body["wrongIDs"],
                "instructions": "针对本次测试反馈完成巩固。",
            },
        )
        assert assigned.status_code == 200, assigned.text
        assigned_body = assigned.json()
        assert len(assigned_body["wrongIDs"]) == 4
        rid = assigned_body["assignment"]["id"]
        rpid = assigned_body["paperID"]

        student_assignments = client.get("/student/assignments", headers=sh)
        assert student_assignments.status_code == 200, student_assignments.text
        visible = next(
            (row for row in student_assignments.json() if row["id"] == rid),
            None,
        )
        assert visible is not None, (
            f"{subject} AI targeted practice must appear in the student's assignment list"
        )
        assert visible["title"] == f"{subject}针对性练习"
        assert visible["completed"] is False
        assert visible["statusCode"] == "pending"
        assert visible["submissionMode"] == "quiz"
        assert visible["submissionModeName"] == "在线答题"
        assert visible["paperID"] == rpid
        assert visible["assignedClassName"]
        assert visible["paper"]["subject"] == subject
        assert visible["paper"]["textbook"] == textbook
        assert len(visible["paper"]["questionIDs"]) == 3

        listed_questions = client.get(
            f"/papers/{visible['paperID']}/questions",
            headers=sh,
        )
        assert listed_questions.status_code == 200, listed_questions.text
        assert len(listed_questions.json()) == 3
        assert all(row["subject"] == subject for row in listed_questions.json())
        assert all(row["textbook"] == textbook for row in listed_questions.json())

        with legacy.SessionLocal() as db:
            link = db.scalar(
                legacy.select(legacy.ReinforcementLink).where(
                    legacy.ReinforcementLink.assignment_id == rid,
                    legacy.ReinforcementLink.student_id == sid,
                )
            )
            assert link is not None
            assert len(json.loads(link.wrong_ids_json)) == 4
            reinforcement_paper = db.get(legacy.Paper, rpid)
            rqids = json.loads(reinforcement_paper.question_ids_json)
            reinforcement_questions = [db.get(legacy.Question, qid) for qid in rqids]
            reinforcement_answers = [
                answer_for(question, True)
                for question in reinforcement_questions
            ]

        reinforcement_submit = client.post(
            f"/student/assignments/{rid}/submit",
            headers=sh,
            json={"answers": reinforcement_answers},
        )
        assert reinforcement_submit.status_code == 200, reinforcement_submit.text
        reinforcement_result = reinforcement_submit.json()
        assert reinforcement_result["correct"] == 3
        assert reinforcement_result["total"] == 3
        assert reinforcement_result["score"] == 100
        assert reinforcement_result["learningPointsAwarded"] == 6
        assert reinforcement_result["learningEvidenceAdded"] == 4
        # Reliability policy deliberately requires repeated, knowledge-matched
        # confirmation before an old wrong question becomes mastered. One
        # perfect reinforcement submission must feed evidence back without
        # prematurely closing every linked historical wrong question.
        assert reinforcement_result["reinforcementClosed"] == 0

        balance += 6
        points = client.get("/student/points", headers=sh)
        assert points.status_code == 200, points.text
        assert points.json()["summary"]["balance"] == balance

        with legacy.SessionLocal() as db:
            link_after = db.scalar(
                legacy.select(legacy.ReinforcementLink).where(
                    legacy.ReinforcementLink.assignment_id == rid,
                    legacy.ReinforcementLink.student_id == sid,
                )
            )
            assert link_after is not None
            assert link_after.result_score == 100
            assert link_after.completed_at is not None

            remaining_active = db.scalar(
                legacy.select(legacy.func.count())
                .select_from(legacy.WrongQuestionRecord)
                .where(
                    legacy.WrongQuestionRecord.assignment_id == aid,
                    legacy.WrongQuestionRecord.student_id == sid,
                    legacy.WrongQuestionRecord.status == "active",
                )
            )
            mastered = db.scalar(
                legacy.select(legacy.func.count())
                .select_from(legacy.WrongQuestionRecord)
                .where(
                    legacy.WrongQuestionRecord.assignment_id == aid,
                    legacy.WrongQuestionRecord.student_id == sid,
                    legacy.WrongQuestionRecord.status == "mastered",
                )
            )
            assert int(remaining_active or 0) == 4
            assert int(mastered or 0) == 0
'''

    env = os.environ.copy()
    env.update(
        {
            "DATABASE_URL": f"sqlite:///{db_path}",
            "JWT_SECRET": "cross-subject-test-signing-material-0123456789abcdef",
            "COMMERCIAL_ADMIN_KEY": "cross-subject-test-operator-material-012345",
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
        timeout=240,
        check=False,
    )

    assert result.returncode == 0, (
        "cross-subject acceptance subprocess failed\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
