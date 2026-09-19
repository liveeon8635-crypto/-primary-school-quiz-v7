from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_append_only_evidence_history_remains_visible_after_retraction(tmp_path):
    db_path = tmp_path / "evidence-history-v24.sqlite3"
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

    sid = client.get("/session", headers=sh).json()["userID"]

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
                name="证据历史测试班",
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
            db.commit()

    create = client.post(
        f"/v2/students/{sid}/learning-evidence",
        headers=th,
        json={
            "evidenceType": "retention",
            "subject": "数学",
            "knowledgeKey": "分数加法",
            "success": True,
            "note": "一周后复测仍能独立完成",
            "context": "延迟复测",
            "occurredAt": "2026-09-18T10:00:00+08:00",
        },
    )
    assert create.status_code == 200, create.text
    record_id = create.json()["record"]["id"]

    before = client.get(
        f"/v2/students/{sid}/learning-evidence/events",
        headers=th,
    )
    assert before.status_code == 200, before.text
    assert before.json()["count"] == 1
    assert before.json()["events"][0]["effectiveStatus"] == "active"

    retract = client.post(
        f"/v2/learning-evidence/{record_id}/retract",
        headers=th,
        json={"reason": "复测对象登记错误"},
    )
    assert retract.status_code == 200, retract.text

    active = client.get(
        f"/v2/students/{sid}/learning-evidence/manual",
        headers=th,
    )
    assert active.status_code == 200
    assert active.json()["count"] == 0

    history = client.get(
        f"/v2/students/{sid}/learning-evidence/events",
        headers=th,
    )
    assert history.status_code == 200, history.text
    body = history.json()
    assert body["appendOnly"] is True
    assert body["includesRetracted"] is True
    assert body["count"] == 2

    record = next(x for x in body["events"] if x["eventKind"] == "record")
    retract_event = next(x for x in body["events"] if x["eventKind"] == "retract")
    assert record["id"] == record_id
    assert record["effectiveStatus"] == "retracted"
    assert record["note"] == "一周后复测仍能独立完成"
    assert record["retractReason"] == "复测对象登记错误"
    assert record["retractEventID"] == retract_event["id"]
    assert retract_event["effectiveStatus"] == "retraction"
    assert retract_event["targetEventID"] == record_id
    assert retract_event["note"] == "复测对象登记错误"

    assert client.get(
        f"/v2/students/{sid}/learning-evidence/events",
        headers=sh,
    ).status_code == 403
    assert client.get(
        f"/v2/students/{sid}/learning-evidence/events",
        headers=ph,
    ).status_code == 403

    with legacy.SessionLocal() as db:
        rows = db.scalars(
            legacy.select(legacy.LearningEvidenceEvent).where(
                legacy.LearningEvidenceEvent.student_id == sid
            )
        ).all()
        assert len(rows) == 2
        original = next(x for x in rows if x.event_kind == "record")
        assert original.id == record_id
        assert original.note == "一周后复测仍能独立完成"
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
