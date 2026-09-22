from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_transition_snapshot_is_shared_and_non_diagnostic_across_roles(tmp_path):
    db_path = tmp_path / "transition-facts.sqlite3"
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

    session = client.get("/session", headers=sh).json()
    sid = session["userID"]

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

        link = db.scalar(
            legacy.select(legacy.ParentStudent).where(
                legacy.ParentStudent.parent_id == parent.id,
                legacy.ParentStudent.student_id == student.id,
            )
        )
        if link is None:
            db.add(
                legacy.ParentStudent(
                    parent_id=parent.id,
                    student_id=student.id,
                )
            )

        old_class = legacy.SchoolClass(
            school_id=student.school_id,
            name="五年级历史班",
            grade=5,
            teacher_id=teacher.id,
        )
        current_class = legacy.SchoolClass(
            school_id=student.school_id,
            name="六年级衔接班",
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
        now = datetime.utcnow()
        db.add(
            legacy.StudentClassHistory(
                school_id=student.school_id,
                student_id=student.id,
                class_id=old_class.id,
                joined_at=now - timedelta(days=220),
                left_at=now - timedelta(days=20),
                leave_reason="transfer",
                actor_id=teacher.id,
                source="test",
            )
        )
        db.add(
            legacy.StudentClassHistory(
                school_id=student.school_id,
                student_id=student.id,
                class_id=current_class.id,
                joined_at=now + timedelta(seconds=2),
                left_at=None,
                leave_reason="",
                actor_id=teacher.id,
                source="test",
            )
        )
        student.grade = 6
        db.commit()

    teacher = client.get(
        f"/v1/students/{sid}/transition-snapshot",
        headers=th,
    )
    parent = client.get(
        f"/v1/students/{sid}/transition-snapshot",
        headers=ph,
    )
    student = client.get(
        f"/v1/students/{sid}/transition-snapshot",
        headers=sh,
    )
    assert teacher.status_code == parent.status_code == student.status_code == 200

    tb, pb, sb = teacher.json(), parent.json(), student.json()
    assert tb["student"]["id"] == pb["student"]["id"] == sb["student"]["id"] == sid
    assert tb["currentStage"]["className"] == "六年级衔接班"
    assert tb["previousStage"]["className"] == "五年级历史班"
    assert tb["transition"]["typeCandidate"] == "小升初"
    assert tb["transition"]["automaticDiagnosis"] is False
    assert tb["transition"]["automaticPlacementDecision"] is False
    assert tb["transition"]["automaticRecommendation"] is False
    assert "不等于学生能力缺口" in tb["evidenceAvailability"]["note"]
    assert tb["learningEvidence"]["masteryInferred"] is False

    forbidden = client.get(
        f"/v1/students/{sid + 999}/transition-snapshot",
        headers=sh,
    )
    assert forbidden.status_code in {403, 404}

    unauth = client.get(f"/v1/students/{sid}/transition-snapshot")
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


def test_transition_snapshot_router_is_get_only_and_installed_once(monkeypatch):
    from types import SimpleNamespace

    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    import changying.web.v1_transition_snapshot as route_module

    app = FastAPI()
    user = SimpleNamespace(school_id=17, role="teacher")
    student = SimpleNamespace(id=23, name="测试学生")
    implementation = SimpleNamespace(
        app=app,
        current_user=lambda: user,
        get_db=lambda: object(),
    )
    monkeypatch.setattr(
        route_module,
        "_authorized_student",
        lambda implementation, db, actual_user, sid: student,
    )
    monkeypatch.setattr(
        route_module,
        "transition_snapshot",
        lambda implementation, db, actual_student, school_id, viewer_role: {
            "student": {"id": int(actual_student.id)},
            "schoolID": school_id,
            "viewerRole": viewer_role,
        },
    )

    route_module.install_v1_transition_snapshot_routes(implementation)
    route_module.install_v1_transition_snapshot_routes(implementation)

    matching = [
        route
        for route in app.routes
        if getattr(route, "path", None) == "/v1/students/{sid}/transition-snapshot"
    ]
    assert len(matching) == 1

    client = TestClient(app)
    response = client.get("/v1/students/23/transition-snapshot")
    assert response.status_code == 200
    assert response.json() == {
        "student": {"id": 23},
        "schoolID": 17,
        "viewerRole": "teacher",
    }
    assert client.post("/v1/students/23/transition-snapshot").status_code == 405
