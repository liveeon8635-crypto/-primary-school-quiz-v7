from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_former_teacher_can_query_only_own_historical_teaching_facts(tmp_path):
    db_path = tmp_path / "historical-teaching.sqlite3"
    script = r"""
from datetime import datetime

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

    with legacy.SessionLocal() as db:
        teacher = db.scalar(
            legacy.select(legacy.User).where(
                legacy.User.username == "teacher1",
                legacy.User.role == "teacher",
            )
        )
        student = db.get(legacy.User, sid)
        admin = db.scalar(
            legacy.select(legacy.User).where(legacy.User.role == "admin")
        )
        assert teacher and student and admin

        teacher_links = db.scalars(
            legacy.select(legacy.ClassStudent)
            .join(
                legacy.SchoolClass,
                legacy.ClassStudent.class_id == legacy.SchoolClass.id,
            )
            .where(
                legacy.ClassStudent.student_id == student.id,
                legacy.SchoolClass.school_id == teacher.school_id,
                legacy.SchoolClass.teacher_id == teacher.id,
            )
        ).all()
        for link in teacher_links:
            db.delete(link)

        old_class = legacy.SchoolClass(
            school_id=teacher.school_id,
            name="历史教学班",
            grade=5,
            teacher_id=teacher.id,
        )
        current_class = legacy.SchoolClass(
            school_id=teacher.school_id,
            name="当前其他教师班",
            grade=6,
            teacher_id=admin.id,
        )
        db.add_all([old_class, current_class])
        db.flush()
        db.add(
            legacy.ClassStudent(
                class_id=current_class.id,
                student_id=student.id,
            )
        )

        paper = legacy.Paper(
            school_id=teacher.school_id,
            title="历史数学测验",
            grade=5,
            subject="数学",
            textbook="人教版",
            unit="分数",
            question_ids_json="[]",
            teacher_id=teacher.id,
        )
        db.add(paper)
        db.flush()
        assignment = legacy.Assignment(
            school_id=teacher.school_id,
            title="五年级历史任务",
            class_id=old_class.id,
            paper_id=paper.id,
            due_date="2026-06-20",
        )
        db.add(assignment)
        db.flush()
        db.add(
            legacy.AssignmentRecipient(
                school_id=teacher.school_id,
                assignment_id=assignment.id,
                class_id=old_class.id,
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
                score=88,
                correct=22,
                total=25,
                answers_json="[]",
            )
        )
        db.flush()

        metadata = legacy.Base.metadata
        sessions = metadata.tables["classroom_sessions"]
        segments = metadata.tables["classroom_segments"]
        checks = metadata.tables["classroom_quick_checks"]
        turns = metadata.tables["classroom_presenter_turns"]
        reviews = metadata.tables["classroom_presentation_reviews"]
        handouts = metadata.tables["classroom_review_handouts"]
        started = datetime(2026, 6, 18, 9, 0)
        completed = datetime(2026, 6, 18, 9, 40)

        session_id = db.execute(
            sessions.insert().values(
                school_id=teacher.school_id,
                class_id=old_class.id,
                teacher_id=teacher.id,
                source_assignment_id=assignment.id,
                subject="数学",
                textbook="人教版",
                title="五年级分数互动课堂",
                status="completed",
                started_at=started,
                completed_at=completed,
                created_at=started,
                updated_at=completed,
            )
        ).inserted_primary_key[0]
        segment_id = db.execute(
            segments.insert().values(
                school_id=teacher.school_id,
                session_id=session_id,
                knowledge_key="分数",
                title="分数",
                order_no=1,
                mode="student",
                status="completed",
                baseline_accuracy=50,
                postcheck_accuracy=100,
                reveal_distribution=False,
                reveal_correct_answer=False,
                reveal_explanation=False,
                created_at=started,
                updated_at=completed,
            )
        ).inserted_primary_key[0]
        db.execute(
            checks.insert().values(
                school_id=teacher.school_id,
                session_id=session_id,
                segment_id=segment_id,
                created_by=teacher.id,
                question_type="single_choice",
                question_text="历史课堂检测",
                options_json='["A","B"]',
                correct_index=0,
                explanation="测试",
                status="closed",
                decision="reteach",
                opened_at=started,
                closed_at=completed,
                decided_at=completed,
                created_at=started,
                updated_at=completed,
            )
        )
        turn_id = db.execute(
            turns.insert().values(
                school_id=teacher.school_id,
                session_id=session_id,
                segment_id=segment_id,
                student_id=student.id,
                requested_by=teacher.id,
                presenter_type="student",
                status="completed",
                note="",
                invited_at=started,
                responded_at=started,
                started_at=started,
                completed_at=completed,
                created_at=started,
            )
        ).inserted_primary_key[0]
        db.execute(
            reviews.insert().values(
                school_id=teacher.school_id,
                session_id=session_id,
                segment_id=segment_id,
                turn_id=turn_id,
                student_id=student.id,
                teacher_id=teacher.id,
                accuracy_rating=4,
                clarity_rating=4,
                interaction_rating=5,
                teacher_note="历史课堂讲解",
                granted_points=2,
                point_reason="课堂讲解表现",
                reviewed_at=completed,
                points_granted_at=completed,
                created_at=completed,
                updated_at=completed,
            )
        )
        db.execute(
            handouts.insert().values(
                school_id=teacher.school_id,
                assignment_id=assignment.id,
                class_id=old_class.id,
                teacher_id=teacher.id,
                title="历史课堂讲义",
                selected_knowledge_json='["分数"]',
                selected_question_ids_json="[]",
                teacher_notes="",
                content_text="历史课堂讲义内容",
                created_at=completed,
                updated_at=completed,
            )
        )
        db.commit()

    full_profile = client.get(
        f"/teacher/students/{sid}/growth-profile",
        headers=th,
    )
    assert full_profile.status_code == 403

    history = client.get("/v1/teacher/history/students", headers=th)
    assert history.status_code == 200, history.text
    body = history.json()
    row = next(x for x in body["students"] if x["studentID"] == sid)
    assert row["scope"] == "teacher-owned-assignment-recipient-snapshots"
    assert row["assignmentCount"] >= 1
    assert any(x["title"] == "五年级历史任务" for x in row["records"])
    record = next(x for x in row["records"] if x["title"] == "五年级历史任务")
    assert record["className"] == "历史教学班"
    assert record["subject"] == "数学"
    assert record["submitted"] is True
    assert record["score"] == 88

    classrooms = client.get("/v1/teacher/history/classrooms", headers=th)
    assert classrooms.status_code == 200, classrooms.text
    classroom_body = classrooms.json()
    assert classroom_body["scope"] == "teacher-owned-completed-classroom-sessions"
    classroom = next(
        x for x in classroom_body["classrooms"]
        if x["assignmentID"] == record["assignmentID"]
    )
    assert classroom["title"] == "五年级分数互动课堂"
    assert classroom["className"] == "历史教学班"
    assert classroom["subject"] == "数学"
    assert classroom["segmentCount"] == 1
    assert classroom["completedSegmentCount"] == 1
    assert classroom["quickCheckRoundCount"] == 1
    assert classroom["reteachCount"] == 1
    assert classroom["presentationCount"] == 1
    assert classroom["presentationReviewCount"] == 1
    assert classroom["teacherGrantedPoints"] == 2
    assert classroom["handoutID"] is not None
    assert classroom["scope"] == "teacher-owned-completed-classroom-sessions"

    forbidden = client.get("/v1/teacher/history/students", headers=sh)
    assert forbidden.status_code == 403
    forbidden_classrooms = client.get("/v1/teacher/history/classrooms", headers=sh)
    assert forbidden_classrooms.status_code == 403
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
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
