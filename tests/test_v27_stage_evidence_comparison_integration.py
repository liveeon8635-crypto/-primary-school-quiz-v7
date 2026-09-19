from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_stage_evidence_comparison_is_descriptive_and_role_safe(tmp_path):
    db_path = tmp_path / "stage-evidence.sqlite3"
    script = r"""
from datetime import datetime, timedelta
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
    parent_token = login_and_change(
        client, "parent1", "123456", "Parent1234"
    )
    student_token = login_and_change(
        client, "student1", "123456", "Student1234"
    )
    th = {"Authorization": f"Bearer {teacher_token}"}
    ph = {"Authorization": f"Bearer {parent_token}"}
    sh = {"Authorization": f"Bearer {student_token}"}

    sid = client.get("/session", headers=sh).json()["userID"]
    now = datetime.utcnow()

    with legacy.SessionLocal() as db:
        teacher = db.scalar(
            legacy.select(legacy.User).where(
                legacy.User.username == "teacher1",
                legacy.User.role == "teacher",
            )
        )
        parent = db.scalar(
            legacy.select(legacy.User).where(
                legacy.User.username == "parent1",
                legacy.User.role == "parent",
            )
        )
        student = db.get(legacy.User, sid)
        assert teacher and parent and student

        parent_link = db.scalar(
            legacy.select(legacy.ParentStudent).where(
                legacy.ParentStudent.parent_id == parent.id,
                legacy.ParentStudent.student_id == student.id,
            )
        )
        if parent_link is None:
            db.add(
                legacy.ParentStudent(
                    parent_id=parent.id,
                    student_id=student.id,
                )
            )

        # Remove current class links so teacher authorization is deterministic.
        links = db.scalars(
            legacy.select(legacy.ClassStudent).where(
                legacy.ClassStudent.student_id == student.id
            )
        ).all()
        for link in links:
            db.delete(link)

        old_class = legacy.SchoolClass(
            school_id=student.school_id,
            name="五年级阶段",
            grade=5,
            teacher_id=teacher.id,
        )
        current_class = legacy.SchoolClass(
            school_id=student.school_id,
            name="六年级阶段",
            grade=6,
            teacher_id=teacher.id,
        )
        db.add_all([old_class, current_class])
        db.flush()
        db.add(
            legacy.ClassStudent(
                class_id=current_class.id,
                student_id=student.id,
            )
        )

        old_join = now - timedelta(days=300)
        old_left = now - timedelta(days=150)
        current_join = now - timedelta(days=149)
        db.add_all(
            [
                legacy.StudentClassHistory(
                    school_id=student.school_id,
                    student_id=student.id,
                    class_id=old_class.id,
                    joined_at=old_join,
                    left_at=old_left,
                    leave_reason="transfer",
                    actor_id=teacher.id,
                    source="stage-test",
                ),
                legacy.StudentClassHistory(
                    school_id=student.school_id,
                    student_id=student.id,
                    class_id=current_class.id,
                    joined_at=current_join,
                    left_at=None,
                    leave_reason="",
                    actor_id=teacher.id,
                    source="stage-test",
                ),
            ]
        )

        db.add_all(
            [
                legacy.Submission(
                    school_id=student.school_id,
                    assignment_id=None,
                    student_id=student.id,
                    title="旧阶段表现",
                    score=78,
                    correct=18,
                    total=25,
                    answers_json="[]",
                    submitted_at=now - timedelta(days=200),
                ),
                legacy.Submission(
                    school_id=student.school_id,
                    assignment_id=None,
                    student_id=student.id,
                    title="当前阶段表现",
                    score=88,
                    correct=22,
                    total=25,
                    answers_json="[]",
                    submitted_at=now - timedelta(days=10),
                ),
            ]
        )

        db.add_all(
            [
                legacy.LearningEvidenceEvent(
                    school_id=student.school_id,
                    student_id=student.id,
                    actor_id=teacher.id,
                    event_kind="record",
                    target_event_id=None,
                    evidence_type="retention",
                    subject="数学",
                    knowledge_key="分数",
                    success=True,
                    note="旧阶段延迟复测",
                    context="教师内部：旧阶段复测",
                    source_type="teacher_observation",
                    occurred_at=now - timedelta(days=190),
                ),
                legacy.LearningEvidenceEvent(
                    school_id=student.school_id,
                    student_id=student.id,
                    actor_id=teacher.id,
                    event_kind="record",
                    target_event_id=None,
                    evidence_type="independent",
                    subject="数学",
                    knowledge_key="比例",
                    success=True,
                    note="当前阶段独立完成",
                    context="教师内部：课堂独立任务",
                    source_type="teacher_observation",
                    occurred_at=now - timedelta(days=8),
                ),
                legacy.LearningEvidenceEvent(
                    school_id=student.school_id,
                    student_id=student.id,
                    actor_id=teacher.id,
                    event_kind="record",
                    target_event_id=None,
                    evidence_type="transfer",
                    subject="数学",
                    knowledge_key="比例",
                    success=True,
                    note="当前阶段迁移应用",
                    context="教师内部：新情境任务",
                    source_type="teacher_observation",
                    occurred_at=now - timedelta(days=7),
                ),
            ]
        )
        db.commit()

    teacher = client.get(
        f"/v2/students/{sid}/stage-evidence-comparison",
        headers=th,
    )
    assert teacher.status_code == 200, teacher.text
    body = teacher.json()

    assert body["currentStage"]["stage"]["className"] == "六年级阶段"
    assert body["previousStage"]["stage"]["className"] == "五年级阶段"
    assert body["currentStage"]["evidence"]["dimensions"] == [
        "independent",
        "performance",
        "transfer",
    ]
    assert body["previousStage"]["evidence"]["dimensions"] == [
        "performance",
        "retention",
    ]
    assert body["comparison"]["newlyRecordedDimensions"] == [
        "independent",
        "transfer",
    ]
    assert body["comparison"]["previousOnlyDimensions"] == ["retention"]
    assert body["comparison"]["sharedDimensions"] == ["performance"]
    assert body["comparison"]["automaticProgressJudgment"] is False
    assert body["comparison"]["automaticRegressionJudgment"] is False
    assert body["comparison"]["automaticMasteryJudgment"] is False
    assert body["comparison"]["automaticRecommendation"] is False
    assert "不代表学生能力进步、退步" in body["comparison"]["note"]

    teacher_recent = body["currentStage"]["evidence"]["recentEvidence"]
    assert any("context" in row for row in teacher_recent)
    assert any("sourceId" in row for row in teacher_recent)

    parent = client.get(
        f"/v2/students/{sid}/stage-evidence-comparison",
        headers=ph,
    )
    student = client.get(
        f"/v2/students/{sid}/stage-evidence-comparison",
        headers=sh,
    )
    assert parent.status_code == student.status_code == 200
    for shared in (parent.json(), student.json()):
        assert shared["comparison"]["newlyRecordedDimensions"] == [
            "independent",
            "transfer",
        ]
        for stage_key in ("currentStage", "previousStage"):
            for row in shared[stage_key]["evidence"]["recentEvidence"]:
                assert "context" not in row
                assert "sourceId" not in row

    unauth = client.get(
        f"/v2/students/{sid}/stage-evidence-comparison"
    )
    assert unauth.status_code == 401
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
