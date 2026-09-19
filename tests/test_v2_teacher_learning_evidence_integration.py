from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_teacher_evidence_record_retract_and_continuous_profile(tmp_path):
    db_path = tmp_path / "teacher-evidence-v2.sqlite3"
    script = r"""
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
    parent_token = login_and_change(
        client, "parent1", "123456", "Parent1234"
    )
    th = {"Authorization": f"Bearer {teacher_token}"}
    sh = {"Authorization": f"Bearer {student_token}"}
    ph = {"Authorization": f"Bearer {parent_token}"}

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
        assert teacher and student

        linked = db.scalar(
            legacy.select(legacy.ClassStudent.id)
            .join(
                legacy.SchoolClass,
                legacy.SchoolClass.id == legacy.ClassStudent.class_id,
            )
            .where(
                legacy.ClassStudent.student_id == student.id,
                legacy.SchoolClass.school_id == teacher.school_id,
                legacy.SchoolClass.teacher_id == teacher.id,
            )
        )
        if not linked:
            klass = legacy.SchoolClass(
                school_id=teacher.school_id,
                name="V2证据测试班",
                grade=student.grade or 5,
                teacher_id=teacher.id,
            )
            db.add(klass)
            db.flush()
            db.add(
                legacy.ClassStudent(
                    class_id=klass.id,
                    student_id=student.id,
                )
            )

        db.add(
            legacy.Submission(
                school_id=student.school_id,
                assignment_id=None,
                student_id=student.id,
                title="自动学习表现证据",
                score=88,
                correct=22,
                total=25,
                answers_json="[]",
            )
        )
        db.commit()

    base = client.get(
        f"/v1/students/{sid}/learning-evidence",
        headers=th,
    )
    assert base.status_code == 200, base.text
    assert "performance" in base.json()["dimensions"]

    created = {}
    payloads = {
        "independent": {
            "evidenceType": "independent",
            "subject": "数学",
            "knowledgeKey": "异分母分数加法",
            "success": True,
            "note": "无直接提示下独立完成三道变式题",
            "context": "周末课课堂练习",
            "occurredAt": "2026-09-18T10:00:00+08:00",
        },
        "retention": {
            "evidenceType": "retention",
            "subject": "数学",
            "knowledgeKey": "异分母分数加法",
            "success": True,
            "note": "一周后复测仍能独立完成",
            "context": "延迟复测",
            "occurredAt": "2026-09-18T10:10:00+08:00",
        },
        "transfer": {
            "evidenceType": "transfer",
            "subject": "数学",
            "knowledgeKey": "异分母分数加法",
            "success": True,
            "note": "在新题型中正确迁移通分方法",
            "context": "新情境应用",
            "occurredAt": "2026-09-18T10:20:00+08:00",
        },
    }
    for kind, payload in payloads.items():
        response = client.post(
            f"/v2/students/{sid}/learning-evidence",
            headers=th,
            json=payload,
        )
        assert response.status_code == 200, response.text
        created[kind] = response.json()["record"]["id"]
        assert response.json()["record"]["evidenceType"] == kind
        assert response.json()["appendOnly"] is True

    manual = client.get(
        f"/v2/students/{sid}/learning-evidence/manual",
        headers=th,
    )
    assert manual.status_code == 200, manual.text
    assert manual.json()["count"] == 3
    assert manual.json()["appendOnly"] is True

    combined = client.get(
        f"/v1/students/{sid}/learning-evidence",
        headers=th,
    )
    assert combined.status_code == 200, combined.text
    body = combined.json()
    assert body["dimensions"] == [
        "independent",
        "performance",
        "retention",
        "transfer",
    ]
    assert body["state"] == "stable_evidence_available"
    assert body["masteryInferred"] is False
    assert body["stableMasteryInferred"] is False

    profile = client.get(
        f"/teacher/students/{sid}/growth-profile",
        headers=th,
    )
    assert profile.status_code == 200, profile.text
    assert profile.json()["learningEvidence"]["state"] == "stable_evidence_available"

    bad_performance = client.post(
        f"/v2/students/{sid}/learning-evidence",
        headers=th,
        json={
            "evidenceType": "performance",
            "note": "教师不应手工制造 performance",
        },
    )
    assert bad_performance.status_code == 400

    student_write = client.post(
        f"/v2/students/{sid}/learning-evidence",
        headers=sh,
        json=payloads["independent"],
    )
    assert student_write.status_code == 403

    parent_write = client.post(
        f"/v2/students/{sid}/learning-evidence",
        headers=ph,
        json=payloads["independent"],
    )
    assert parent_write.status_code == 403

    retract = client.post(
        f"/v2/learning-evidence/{created['independent']}/retract",
        headers=th,
        json={"reason": "课堂记录录入对象有误"},
    )
    assert retract.status_code == 200, retract.text
    assert retract.json()["appendOnly"] is True
    assert retract.json()["retractedEventID"] == created["independent"]

    after = client.get(
        f"/v1/students/{sid}/learning-evidence",
        headers=th,
    )
    assert after.status_code == 200, after.text
    assert "independent" not in after.json()["dimensions"]
    assert "performance" in after.json()["dimensions"]
    assert "retention" in after.json()["dimensions"]
    assert "transfer" in after.json()["dimensions"]
    assert after.json()["state"] == "learning_evidence_available"

    manual_after = client.get(
        f"/v2/students/{sid}/learning-evidence/manual",
        headers=th,
    )
    assert manual_after.status_code == 200
    assert manual_after.json()["count"] == 2

    duplicate_retract = client.post(
        f"/v2/learning-evidence/{created['independent']}/retract",
        headers=th,
        json={"reason": "重复撤回"},
    )
    assert duplicate_retract.status_code == 409

    with legacy.SessionLocal() as db:
        rows = db.scalars(
            legacy.select(legacy.LearningEvidenceEvent).where(
                legacy.LearningEvidenceEvent.student_id == sid
            )
        ).all()
        assert len(rows) == 4
        assert sum(1 for row in rows if row.event_kind == "record") == 3
        assert sum(1 for row in rows if row.event_kind == "retract") == 1
        original = next(
            row
            for row in rows
            if row.id == created["independent"]
        )
        assert original.event_kind == "record"
        assert original.note == "无直接提示下独立完成三道变式题"
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
