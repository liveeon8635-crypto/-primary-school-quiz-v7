from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_teaching_evidence_context_is_teacher_only_and_non_prescriptive(tmp_path):
    db_path = tmp_path / "teaching-evidence-context.sqlite3"
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
    teacher_token = login_and_change(client, "teacher1", "123456", "Teacher1234")
    student_token = login_and_change(client, "student1", "123456", "Student1234")
    parent_token = login_and_change(client, "parent1", "123456", "Parent1234")
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
            .join(legacy.SchoolClass, legacy.SchoolClass.id == legacy.ClassStudent.class_id)
            .where(
                legacy.ClassStudent.student_id == student.id,
                legacy.SchoolClass.school_id == teacher.school_id,
                legacy.SchoolClass.teacher_id == teacher.id,
            )
        )
        if not linked:
            klass = legacy.SchoolClass(
                school_id=teacher.school_id,
                name="备课事实测试班",
                grade=student.grade or 5,
                teacher_id=teacher.id,
            )
            db.add(klass)
            db.flush()
            db.add(legacy.ClassStudent(class_id=klass.id, student_id=student.id))

        db.add(
            legacy.Submission(
                school_id=student.school_id,
                assignment_id=None,
                student_id=student.id,
                title="自动学习表现",
                score=86,
                correct=21,
                total=25,
                answers_json="[]",
            )
        )
        db.add(
            legacy.LearningEvidenceEvent(
                school_id=student.school_id,
                student_id=student.id,
                actor_id=teacher.id,
                event_kind="record",
                target_event_id=None,
                evidence_type="independent",
                subject="数学",
                knowledge_key="分数加法",
                success=True,
                note="独立完成变式题",
                context="周末课",
                source_type="teacher_observation",
            )
        )
        db.commit()

    teacher = client.get(
        f"/v2/students/{sid}/teaching-evidence-context",
        headers=th,
    )
    assert teacher.status_code == 200, teacher.text
    body = teacher.json()
    assert body["student"]["id"] == sid
    assert "performance" in body["availableDimensions"]
    assert "independent" in body["availableDimensions"]
    assert "retention" in body["missingDimensions"]
    assert "transfer" in body["missingDimensions"]
    assert body["decisionRequiredByTeacher"] is True
    assert body["automaticDiagnosis"] is False
    assert body["automaticRecommendation"] is False
    assert body["automaticPlacementDecision"] is False
    assert body["teachingToolPath"] == "/v1/tool?page=teaching"
    assert "不等于学生存在能力缺口" in body["boundary"]

    student = client.get(
        f"/v2/students/{sid}/teaching-evidence-context",
        headers=sh,
    )
    parent = client.get(
        f"/v2/students/{sid}/teaching-evidence-context",
        headers=ph,
    )
    assert student.status_code == 403
    assert parent.status_code == 403

    unauth = client.get(f"/v2/students/{sid}/teaching-evidence-context")
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


def test_teaching_evidence_context_router_is_get_only_and_installed_once(monkeypatch):
    from types import SimpleNamespace

    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    import changying.web.v2_teaching_evidence_context as route_module

    app = FastAPI()
    user = SimpleNamespace(id=7, school_id=17, role="teacher")
    student = SimpleNamespace(id=23, name="测试学生")
    implementation = SimpleNamespace(
        app=app,
        current_user=lambda: user,
        get_db=lambda: object(),
    )
    monkeypatch.setattr(
        route_module,
        "_teacher_student",
        lambda implementation, db, actual_user, sid: student,
    )
    monkeypatch.setattr(
        route_module,
        "legacy_student_evidence",
        lambda implementation, db, student_id, school_id: [],
    )
    monkeypatch.setattr(
        route_module,
        "student_evidence_snapshot",
        lambda items: {"state": "evidence_insufficient", "sampleCount": 0, "dimensions": []},
    )
    monkeypatch.setattr(
        route_module,
        "build_teaching_evidence_context",
        lambda snapshot: {
            "sampleCount": snapshot["sampleCount"],
            "decisionRequiredByTeacher": True,
            "automaticDiagnosis": False,
        },
    )

    route_module.install_v21_teaching_evidence_context_routes(implementation)
    route_module.install_v21_teaching_evidence_context_routes(implementation)

    expected = {"/v2/students/{sid}/teaching-evidence-context"}
    matching = [
        child
        for route in app.routes
        for child in getattr(getattr(route, "original_router", route), "routes", [route])
        if getattr(child, "path", None) in expected
    ]
    assert {route.path for route in matching} == expected

    client = TestClient(app)
    response = client.get("/v2/students/23/teaching-evidence-context")
    assert response.status_code == 200
    assert response.json() == {
        "student": {"id": 23, "name": "测试学生"},
        "sampleCount": 0,
        "decisionRequiredByTeacher": True,
        "automaticDiagnosis": False,
    }
    assert client.post("/v2/students/23/teaching-evidence-context").status_code == 405
