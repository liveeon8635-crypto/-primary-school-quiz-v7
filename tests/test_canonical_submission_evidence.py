from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from changying.domain.stored_learning_evidence import EXPLICIT_PERFORMANCE_SOURCES


ROOT = Path(__file__).resolve().parents[1]


def test_canonical_sources_cover_submission_summary_and_items():
    assert "submission" in EXPLICIT_PERFORMANCE_SOURCES
    assert "submission_answer" in EXPLICIT_PERFORMANCE_SOURCES


def test_runtime_installs_canonical_submission_writer():
    import app_v924 as legacy
    from app import app

    assert getattr(app.state, "canonical_submission_evidence_installed", False) is True
    paths = {
        (getattr(route, "path", ""), tuple(sorted(getattr(route, "methods", set()))))
        for route in app.routes
    }
    assert any(path == "/student/practice-submit" and "POST" in methods for path, methods in paths)
    assert any(path == "/student/assignments/{aid}/submit" and "POST" in methods for path, methods in paths)


def test_new_practice_submission_writes_explicit_evidence_without_double_counting(tmp_path):
    db_path = tmp_path / "canonical-submission-evidence.sqlite3"
    script = r"""
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
    old_token = login.json()["token"]
    changed = client.post(
        "/change-password",
        headers={"Authorization": f"Bearer {old_token}"},
        json={
            "current_password": old_password,
            "new_password": new_password,
            "remember": False,
        },
    )
    assert changed.status_code == 200, changed.text
    return changed.json()["token"]


with TestClient(app) as client:
    token = login_and_change(client, "student1", "123456", "Student1234")
    headers = {"Authorization": f"Bearer {token}"}
    session = client.get("/session", headers=headers)
    assert session.status_code == 200, session.text
    sid = session.json()["userID"]

    with legacy.SessionLocal() as db:
        student = db.get(legacy.User, sid)
        assert student is not None
        q1 = legacy.Question(
            school_id=student.school_id,
            grade=student.grade or 3,
            subject="数学",
            textbook="人教版",
            semester="上册",
            unit="证据测试",
            knowledge="加法",
            text="2+3=?",
            options_json=json.dumps(["4", "5", "6", "7"], ensure_ascii=False),
            correct_index=1,
            explanation="2+3=5",
            question_type="single_choice",
            answer_json="{}",
            figure_json="{}",
            creator_id=student.id,
        )
        q2 = legacy.Question(
            school_id=student.school_id,
            grade=student.grade or 3,
            subject="数学",
            textbook="人教版",
            semester="上册",
            unit="证据测试",
            knowledge="减法",
            text="9-4=?",
            options_json=json.dumps(["3", "4", "5", "6"], ensure_ascii=False),
            correct_index=2,
            explanation="9-4=5",
            question_type="single_choice",
            answer_json="{}",
            figure_json="{}",
            creator_id=student.id,
        )
        db.add_all([q1, q2])
        db.commit()
        db.refresh(q1)
        db.refresh(q2)
        qids = [q1.id, q2.id]

    submitted = client.post(
        "/student/practice-submit",
        headers=headers,
        json={
            "title": "标准证据测试",
            "answers": [
                {"question_id": qids[0], "selected_index": 1},
                {"question_id": qids[1], "selected_index": 0},
            ],
        },
    )
    assert submitted.status_code == 200, submitted.text
    body = submitted.json()
    assert body["score"] == 50
    assert body["correct"] == 1
    assert body["total"] == 2
    assert body["learningEvidenceAdded"] == 3
    submission_id = body["id"]

    with legacy.SessionLocal() as db:
        events = db.scalars(
            legacy.select(legacy.LearningEvidenceEvent)
            .where(
                legacy.LearningEvidenceEvent.student_id == sid,
                legacy.LearningEvidenceEvent.event_kind == "record",
            )
            .order_by(legacy.LearningEvidenceEvent.id)
        ).all()
        assert [row.source_type for row in events] == [
            "submission",
            "submission_answer",
            "submission_answer",
        ]
        summary = json.loads(events[0].context)
        assert summary["submissionID"] == submission_id
        assert summary["score"] == 50
        assert events[1].knowledge_key == "加法"
        assert events[1].success is True
        assert events[2].knowledge_key == "减法"
        assert events[2].success is False

    evidence = client.get(
        f"/v1/students/{sid}/learning-evidence",
        headers=headers,
    )
    assert evidence.status_code == 200, evidence.text
    snapshot = evidence.json()
    assert snapshot["dimensions"] == ["performance"]
    # Exactly 1 summary + 2 item facts. The legacy reconstruction for the
    # same Submission must be suppressed once canonical events exist.
    assert snapshot["sampleCount"] == 3
    assert snapshot["masteryInferred"] is False

    manual = client.get(
        f"/v2/students/{sid}/learning-evidence/manual",
        headers=headers,
    )
    # Students cannot use the teacher-only manual endpoint.
    assert manual.status_code == 403

    # Science uses the same canonical evidence pipeline. The test deliberately
    # supplies an explicit textbook label rather than inventing a national
    # default science edition.
    with legacy.SessionLocal() as db:
        student = db.get(legacy.User, sid)
        science = legacy.Question(
            school_id=student.school_id,
            grade=student.grade or 5,
            subject="科学",
            textbook="教师明确的科学教材",
            semester="上册",
            unit="观察与实验",
            knowledge="证据解释",
            text="在相同光照下，两株同种植物只有浇水量不同。哪一项最适合作为比较结果时需要控制的条件？",
            options_json=json.dumps(
                ["植物种类", "记录表颜色", "花盆编号", "观察者姓名"],
                ensure_ascii=False,
            ),
            correct_index=0,
            explanation="比较实验应尽量只改变一个研究变量，其余关键条件保持一致。",
            question_type="single_choice",
            answer_json="{}",
            figure_json="{}",
            creator_id=student.id,
        )
        db.add(science)
        db.commit()
        db.refresh(science)
        science_qid = science.id

    science_submit = client.post(
        "/student/practice-submit",
        headers=headers,
        json={
            "title": "科学标准证据测试",
            "answers": [{"question_id": science_qid, "selected_index": 0}],
        },
    )
    assert science_submit.status_code == 200, science_submit.text
    science_body = science_submit.json()
    assert science_body["score"] == 100
    assert science_body["learningEvidenceAdded"] == 2

    with legacy.SessionLocal() as db:
        science_events = db.scalars(
            legacy.select(legacy.LearningEvidenceEvent)
            .where(
                legacy.LearningEvidenceEvent.student_id == sid,
                legacy.LearningEvidenceEvent.source_type == "submission_answer",
                legacy.LearningEvidenceEvent.subject == "科学",
            )
            .order_by(legacy.LearningEvidenceEvent.id)
        ).all()
        assert len(science_events) == 1
        science_event = science_events[0]
        assert science_event.knowledge_key == "证据解释"
        assert science_event.success is True
        science_context = json.loads(science_event.context)
        assert science_context["questionID"] == science_qid
"""

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
        timeout=120,
        check=False,
    )
    assert result.returncode == 0, (
        "canonical submission evidence E2E failed\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
