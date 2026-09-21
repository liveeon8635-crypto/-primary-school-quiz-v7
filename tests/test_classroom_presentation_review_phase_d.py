from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

from changying.services.classroom_presentation_review import (
    normalize_review_ratings,
    presentation_point_note,
)
from changying.web.v1 import v1_html
from changying.web.v1_classroom_execution import patch_v1_classroom_execution_html
from changying.web.v1_classroom_presentation_review import (
    V1_CLASSROOM_PRESENTATION_REVIEW_MARKER,
    patch_v1_classroom_presentation_review_html,
)
from changying.web.v1_classroom_quick_check import patch_v1_classroom_quick_check_html
from changying.web.v1_classroom_review import patch_v1_classroom_review_html


ROOT = Path(__file__).resolve().parents[1]


def test_presentation_review_helpers_are_teacher_entered_not_automatic_scores():
    assert normalize_review_ratings(
        accuracy_rating=5,
        clarity_rating=4,
        interaction_rating=None,
    ) == {
        "accuracy_rating": 5,
        "clarity_rating": 4,
        "interaction_rating": None,
    }
    note = presentation_point_note(
        knowledge_key="小数乘法",
        accuracy_rating=5,
        clarity_rating=4,
        interaction_rating=3,
        quick_check_accuracy=80,
        presenter_check_correct=True,
        teacher_note="思路清楚，能回应同学。",
    )
    assert "准确性5/5" in note
    assert "班级正确率80%" in note
    assert "讲解学生后续检测：正确" in note


def test_v1_phase_d_patch_keeps_review_and_point_confirmation_separate():
    html = patch_v1_classroom_presentation_review_html(
        patch_v1_classroom_quick_check_html(
            patch_v1_classroom_execution_html(
                patch_v1_classroom_review_html(v1_html())
            )
        )
    )
    assert V1_CLASSROOM_PRESENTATION_REVIEW_MARKER in html
    assert "学生讲解评价" in html
    assert "讲解后的随堂检测反馈" in html
    assert "保存评价" in html
    assert "确认加分" in html
    assert "点击确认前不会写入积分动态" in html
    assert "随堂检测正确率不会自动折算积分" in html


def test_runtime_classroom_presentation_review_and_explicit_points_phase_d(tmp_path):
    db_path = tmp_path / "classroom-presentation-review.sqlite3"
    script = r"""
import json
from datetime import datetime

from fastapi.testclient import TestClient
from sqlalchemy import func, select

import app_v924 as legacy
from app import app


def auth(db, username):
    user = db.scalar(select(legacy.User).where(legacy.User.username == username))
    sec = legacy.security_for(db, user)
    sec.must_change_password = False
    db.commit()
    return user, {"Authorization": "Bearer " + legacy.make_token(user, sec, False)}


with TestClient(app) as client:
    with legacy.SessionLocal() as db:
        teacher, th = auth(db, "teacher1")
        student, sh = auth(db, "student1")
        cls = db.scalar(
            select(legacy.SchoolClass).where(
                legacy.SchoolClass.school_id == teacher.school_id,
                legacy.SchoolClass.teacher_id == teacher.id,
            )
        )
        assert cls is not None
        membership = db.scalar(
            select(legacy.ClassStudent).where(
                legacy.ClassStudent.class_id == cls.id,
                legacy.ClassStudent.student_id == student.id,
            )
        )
        if membership is None:
            db.add(legacy.ClassStudent(class_id=cls.id, student_id=student.id))
            db.flush()

        q = legacy.Question(
            school_id=teacher.school_id,
            grade=5,
            subject="数学",
            textbook="人教版",
            semester="上册",
            unit="小数乘法",
            knowledge="小数乘法",
            text="0.4×3 的结果是？",
            options_json=json.dumps(["0.12", "1.2", "12", "120"], ensure_ascii=False),
            correct_index=1,
            explanation="0.4乘3等于1.2",
            question_type="single_choice",
            answer_json="{}",
            figure_json="{}",
            creator_id=teacher.id,
        )
        db.add(q)
        db.flush()
        paper = legacy.Paper(
            school_id=teacher.school_id,
            title="讲解评价源练习",
            grade=5,
            subject="数学",
            textbook="人教版",
            unit="小数乘法",
            question_ids_json=json.dumps([q.id]),
            teacher_id=teacher.id,
        )
        db.add(paper)
        db.flush()
        assignment = legacy.Assignment(
            school_id=teacher.school_id,
            title="小数乘法讲解评价练习",
            class_id=cls.id,
            paper_id=paper.id,
            due_date="2026-09-30",
        )
        db.add(assignment)
        db.flush()
        db.add(
            legacy.AssignmentRecipient(
                school_id=teacher.school_id,
                assignment_id=assignment.id,
                class_id=cls.id,
                student_id=student.id,
                source="assignment",
            )
        )
        db.add(
            legacy.Submission(
                school_id=teacher.school_id,
                assignment_id=assignment.id,
                student_id=student.id,
                title=assignment.title,
                score=100,
                correct=1,
                total=1,
                answers_json=json.dumps(
                    [{"question_id": q.id, "selected_index": 1, "correct": True}],
                    ensure_ascii=False,
                ),
            )
        )
        handouts = legacy.Base.metadata.tables["classroom_review_handouts"]
        db.execute(
            handouts.insert().values(
                school_id=teacher.school_id,
                assignment_id=assignment.id,
                class_id=cls.id,
                teacher_id=teacher.id,
                title="小数乘法互动讲解讲义",
                selected_knowledge_json=json.dumps(["小数乘法"], ensure_ascii=False),
                selected_question_ids_json=json.dumps([q.id]),
                teacher_notes="",
                content_text="讲解小数乘法。",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
        )
        school_id = teacher.school_id
        student_id = student.id
        before_points = int(
            db.scalar(
                select(func.count())
                .select_from(legacy.PointLedger)
                .where(
                    legacy.PointLedger.school_id == school_id,
                    legacy.PointLedger.student_id == student_id,
                )
            )
            or 0
        )
        before_evidence = int(
            db.scalar(
                select(func.count())
                .select_from(legacy.LearningEvidenceEvent)
                .where(
                    legacy.LearningEvidenceEvent.school_id == school_id,
                    legacy.LearningEvidenceEvent.student_id == student_id,
                )
            )
            or 0
        )
        db.commit()
        aid = assignment.id

    created = client.post(
        f"/teacher/assignments/{aid}/classroom-session",
        headers=th,
        json={},
    )
    assert created.status_code == 200, created.text
    sid = created.json()["session"]["id"]
    segid = created.json()["segments"][0]["id"]

    assert client.post(
        f"/teacher/classroom-sessions/{sid}/state",
        headers=th,
        json={"status": "active"},
    ).status_code == 200

    mode = client.post(
        f"/teacher/classroom-sessions/{sid}/segments/{segid}/mode",
        headers=th,
        json={"mode": "student"},
    )
    assert mode.status_code == 200, mode.text

    invited = client.post(
        f"/teacher/classroom-sessions/{sid}/segments/{segid}/invite",
        headers=th,
        json={"student_id": student_id, "presenter_type": "student", "note": "请讲解你的思路。"},
    )
    assert invited.status_code == 200, invited.text
    turn_id = invited.json()["segments"][0]["presenterTurn"]["id"]

    accepted = client.post(
        f"/student/classroom-invitations/{turn_id}/respond",
        headers=sh,
        json={"response": "accepted"},
    )
    assert accepted.status_code == 200, accepted.text

    presenting = client.post(
        f"/teacher/classroom-sessions/{sid}/presenter-turns/{turn_id}/state",
        headers=th,
        json={"status": "presenting"},
    )
    assert presenting.status_code == 200, presenting.text

    completed = client.post(
        f"/teacher/classroom-sessions/{sid}/segments/{segid}/complete",
        headers=th,
    )
    assert completed.status_code == 200, completed.text

    draft = client.post(
        f"/teacher/classroom-sessions/{sid}/segments/{segid}/quick-checks/draft",
        headers=th,
        json={"question_type": "single_choice", "use_ai": False},
    )
    assert draft.status_code == 200, draft.text
    check_id = draft.json()["id"]

    edited = client.put(
        f"/teacher/classroom-sessions/{sid}/quick-checks/{check_id}",
        headers=th,
        json={
            "question_text": "0.6×4 的结果是？",
            "options": ["0.24", "2.4", "24", "240"],
            "correct_index": 1,
            "explanation": "0.6乘4等于2.4。",
        },
    )
    assert edited.status_code == 200, edited.text

    assert client.post(
        f"/teacher/classroom-sessions/{sid}/quick-checks/{check_id}/state",
        headers=th,
        json={"status": "open"},
    ).status_code == 200
    assert client.post(
        f"/student/classroom-quick-checks/{check_id}/respond",
        headers=sh,
        json={"selected_index": 1},
    ).status_code == 200
    closed = client.post(
        f"/teacher/classroom-sessions/{sid}/quick-checks/{check_id}/state",
        headers=th,
        json={"status": "closed"},
    )
    assert closed.status_code == 200, closed.text
    assert closed.json()["stats"]["accuracy"] == 100

    views = client.get(
        f"/teacher/classroom-sessions/{sid}/presentation-reviews",
        headers=th,
    )
    assert views.status_code == 200, views.text
    view = next(x for x in views.json() if x["turnID"] == turn_id)
    assert view["review"] is None
    assert view["feedback"]["quickCheckID"] == check_id
    assert view["feedback"]["classAccuracy"] == 100
    assert view["feedback"]["presenterResponded"] is True
    assert view["feedback"]["presenterCorrect"] is True

    saved = client.put(
        f"/teacher/classroom-sessions/{sid}/presenter-turns/{turn_id}/review",
        headers=th,
        json={
            "accuracy_rating": 5,
            "clarity_rating": 4,
            "interaction_rating": 5,
            "teacher_note": "讲解思路清楚，能回应同学提问。",
        },
    )
    assert saved.status_code == 200, saved.text
    review_id = saved.json()["reviewID"]
    assert "没有自动加分" in saved.json()["notice"]

    with legacy.SessionLocal() as db:
        after_review_points = int(
            db.scalar(
                select(func.count())
                .select_from(legacy.PointLedger)
                .where(
                    legacy.PointLedger.school_id == school_id,
                    legacy.PointLedger.student_id == student_id,
                )
            )
            or 0
        )
        after_review_evidence = int(
            db.scalar(
                select(func.count())
                .select_from(legacy.LearningEvidenceEvent)
                .where(
                    legacy.LearningEvidenceEvent.school_id == school_id,
                    legacy.LearningEvidenceEvent.student_id == student_id,
                )
            )
            or 0
        )
        assert after_review_points == before_points
        assert after_review_evidence == before_evidence

    grant = client.post(
        f"/teacher/classroom-sessions/{sid}/presentation-reviews/{review_id}/grant-points",
        headers=th,
        json={"points": 7, "reason": "知识点讲解表现"},
    )
    assert grant.status_code == 200, grant.text
    assert grant.json()["points"] == 7
    assert grant.json()["record"]["points"] == 7
    assert grant.json()["record"]["source"] == "classroom"
    assert grant.json()["record"]["relatedID"] == review_id
    ledger_id = grant.json()["record"]["id"]

    duplicate = client.post(
        f"/teacher/classroom-sessions/{sid}/presentation-reviews/{review_id}/grant-points",
        headers=th,
        json={"points": 7, "reason": "重复加分"},
    )
    assert duplicate.status_code == 400
    assert "不能重复加分" in duplicate.text

    after = client.get(
        f"/teacher/classroom-sessions/{sid}/presentation-reviews",
        headers=th,
    )
    row = next(x for x in after.json() if x["turnID"] == turn_id)
    assert row["point"]["ledgerID"] == ledger_id
    assert row["point"]["points"] == 7
    assert row["review"]["accuracyRating"] == 5
    assert row["feedback"]["classAccuracy"] == 100

    student_points = client.get("/student/points", headers=sh)
    assert student_points.status_code == 200, student_points.text
    visible_ledger = next(x for x in student_points.json()["ledger"] if x["id"] == ledger_id)
    assert visible_ledger["points"] == 7
    assert visible_ledger["reason"] == "知识点讲解表现"

    with legacy.SessionLocal() as db:
        after_points = int(
            db.scalar(
                select(func.count())
                .select_from(legacy.PointLedger)
                .where(
                    legacy.PointLedger.school_id == school_id,
                    legacy.PointLedger.student_id == student_id,
                )
            )
            or 0
        )
        after_evidence = int(
            db.scalar(
                select(func.count())
                .select_from(legacy.LearningEvidenceEvent)
                .where(
                    legacy.LearningEvidenceEvent.school_id == school_id,
                    legacy.LearningEvidenceEvent.student_id == student_id,
                )
            )
            or 0
        )
        assert after_points == before_points + 1
        assert after_evidence == before_evidence
        tables = legacy.Base.metadata.tables
        assert "classroom_presentation_reviews" in tables
        review_count = int(
            db.scalar(
                select(func.count()).select_from(tables["classroom_presentation_reviews"])
            )
            or 0
        )
        assert review_count == 1
"""

    env = os.environ.copy()
    env["DATABASE_URL"] = f"sqlite:///{db_path}"
    env["ENABLE_DEMO_SEED"] = "1"
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
    )
    assert completed.returncode == 0, completed.stdout + "\n" + completed.stderr
