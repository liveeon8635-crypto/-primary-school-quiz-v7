from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def test_runtime_growth_profile_keeps_classroom_dimensions_separate_and_read_only(tmp_path):
    db_path = tmp_path / "classroom-longitudinal.sqlite3"
    script = r"""
import json
from datetime import datetime

from sqlalchemy import func, select

import app_v924 as legacy
from app import app  # noqa: F401

# Importing the FastAPI app does not run lifespan/startup handlers in this
# subprocess. Create the isolated SQLite schema and seed it explicitly.
legacy.Base.metadata.create_all(legacy.engine)
with legacy.SessionLocal() as seed_db:
    legacy.seed(seed_db)

with legacy.SessionLocal() as db:
    teacher = db.scalar(select(legacy.User).where(legacy.User.username == "teacher1"))
    student = db.scalar(select(legacy.User).where(legacy.User.username == "student1"))
    cls = db.scalar(
        select(legacy.SchoolClass).where(
            legacy.SchoolClass.school_id == teacher.school_id,
            legacy.SchoolClass.teacher_id == teacher.id,
        )
    )
    if db.scalar(
        select(legacy.ClassStudent.id).where(
            legacy.ClassStudent.class_id == cls.id,
            legacy.ClassStudent.student_id == student.id,
        )
    ) is None:
        db.add(legacy.ClassStudent(class_id=cls.id, student_id=student.id))
        db.flush()

    tables = legacy.Base.metadata.tables
    sessions = tables["classroom_sessions"]
    segments = tables["classroom_segments"]
    turns = tables["classroom_presenter_turns"]
    checks = tables["classroom_quick_checks"]
    responses = tables["classroom_quick_check_responses"]
    reviews = tables["classroom_presentation_reviews"]

    sid = db.execute(
        sessions.insert().values(
            school_id=teacher.school_id,
            class_id=cls.id,
            teacher_id=teacher.id,
            subject="数学",
            textbook="人教版",
            title="小数乘法课堂",
            status="completed",
            started_at=datetime(2026, 9, 24, 2, 0, 0),
            completed_at=datetime(2026, 9, 24, 3, 0, 0),
            created_at=datetime(2026, 9, 24, 2, 0, 0),
            updated_at=datetime(2026, 9, 24, 3, 0, 0),
        )
    ).inserted_primary_key[0]
    segid = db.execute(
        segments.insert().values(
            school_id=teacher.school_id,
            session_id=sid,
            knowledge_key="小数乘法",
            title="小数乘法",
            order_no=1,
            mode="student",
            status="completed",
            created_at=datetime(2026, 9, 24, 2, 0, 0),
            updated_at=datetime(2026, 9, 24, 3, 0, 0),
        )
    ).inserted_primary_key[0]
    tid = db.execute(
        turns.insert().values(
            school_id=teacher.school_id,
            session_id=sid,
            segment_id=segid,
            student_id=student.id,
            requested_by=teacher.id,
            presenter_type="student",
            status="completed",
            invited_at=datetime(2026, 9, 24, 2, 10, 0),
            responded_at=datetime(2026, 9, 24, 2, 12, 0),
            started_at=datetime(2026, 9, 24, 2, 20, 0),
            completed_at=datetime(2026, 9, 24, 2, 35, 0),
            created_at=datetime(2026, 9, 24, 2, 10, 0),
        )
    ).inserted_primary_key[0]
    qid = db.execute(
        checks.insert().values(
            school_id=teacher.school_id,
            session_id=sid,
            segment_id=segid,
            created_by=teacher.id,
            question_type="single_choice",
            question_text="0.4×3 等于多少？",
            options_json=json.dumps(["0.12", "1.2", "12", "120"], ensure_ascii=False),
            correct_index=1,
            explanation="0.4×3=1.2",
            status="closed",
            decision="complete",
            opened_at=datetime(2026, 9, 24, 2, 40, 0),
            closed_at=datetime(2026, 9, 24, 2, 50, 0),
            decided_at=datetime(2026, 9, 24, 2, 52, 0),
            created_at=datetime(2026, 9, 24, 2, 38, 0),
            updated_at=datetime(2026, 9, 24, 2, 52, 0),
        )
    ).inserted_primary_key[0]
    db.execute(
        responses.insert().values(
            school_id=teacher.school_id,
            check_id=qid,
            session_id=sid,
            segment_id=segid,
            student_id=student.id,
            selected_index=1,
            is_correct=True,
            submitted_at=datetime(2026, 9, 24, 2, 45, 0),
            updated_at=datetime(2026, 9, 24, 2, 45, 0),
        )
    )
    db.execute(
        reviews.insert().values(
            school_id=teacher.school_id,
            session_id=sid,
            segment_id=segid,
            turn_id=tid,
            student_id=student.id,
            teacher_id=teacher.id,
            accuracy_rating=4,
            clarity_rating=5,
            interaction_rating=3,
            teacher_note="计算过程清楚，互动还可继续加强。",
            quick_check_id=qid,
            quick_check_accuracy=100,
            presenter_check_correct=True,
            granted_points=None,
            point_reason="",
            reviewed_at=datetime(2026, 9, 24, 2, 55, 0),
            created_at=datetime(2026, 9, 24, 2, 55, 0),
            updated_at=datetime(2026, 9, 24, 2, 55, 0),
        )
    )

    before_points = int(db.scalar(select(func.count()).select_from(legacy.PointLedger)) or 0)
    before_evidence = int(db.scalar(select(func.count()).select_from(legacy.LearningEvidenceEvent)) or 0)
    db.commit()

    profile = legacy.student_growth_profile_data(db, student, teacher.school_id, cls.id)
    classroom = profile["classroomParticipation"]
    assert classroom["summary"]["quickCheckCount"] == 1
    assert classroom["summary"]["quickCheckCorrectCount"] == 1
    assert classroom["summary"]["quickCheckAccuracy"] == 100
    assert classroom["summary"]["presentationCount"] == 1
    assert classroom["summary"]["reviewedPresentationCount"] == 1
    assert classroom["summary"]["accuracyRatingAverage"] == 4.0
    assert classroom["summary"]["clarityRatingAverage"] == 5.0
    assert classroom["summary"]["interactionRatingAverage"] == 3.0
    assert classroom["summary"]["dimensionsSeparate"] is True
    assert classroom["summary"]["combinedAbilityScore"] is None

    assert classroom["quickChecks"][0]["knowledgeKey"] == "小数乘法"
    assert classroom["quickChecks"][0]["isCorrect"] is True
    assert classroom["presentations"][0]["review"]["teacherNote"].startswith("计算过程清楚")
    assert classroom["presentations"][0]["review"]["accuracyRating"] == 4
    assert any(x["type"] == "classroom_quick_check" for x in profile["timeline"])
    assert any(x["type"] == "classroom_presentation" for x in profile["timeline"])

    after_points = int(db.scalar(select(func.count()).select_from(legacy.PointLedger)) or 0)
    after_evidence = int(db.scalar(select(func.count()).select_from(legacy.LearningEvidenceEvent)) or 0)
    assert after_points == before_points
    assert after_evidence == before_evidence
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
