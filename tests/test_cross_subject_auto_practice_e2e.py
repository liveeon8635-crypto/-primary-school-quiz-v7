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
        assert option_body["availableQuestionCount"] == 176
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
                "due_date": "2026-09-30",
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
        assert {"single_choice", "true_false", "fill_blank", "short_answer"} <= types
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
        assert result["learningPointsAwarded"] == 4
        assert result["learningPointMax"] == 8
        assert result["assessmentFeedbackArchived"] == 4

        balance += 4
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
