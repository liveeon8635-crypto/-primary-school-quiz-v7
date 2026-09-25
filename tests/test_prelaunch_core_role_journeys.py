from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_public_launch_core_role_journeys_stay_operable_and_isolated(tmp_path):
    db_path = tmp_path / "prelaunch-role-journeys.sqlite3"
    script = r'''
from fastapi.testclient import TestClient
from app import app


def login_and_change(client, username, new_password):
    response = client.post(
        "/login",
        json={"username": username, "password": "123456", "remember": False},
    )
    assert response.status_code == 200, (username, response.text)
    token = response.json()["token"]
    changed = client.post(
        "/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "current_password": "123456",
            "new_password": new_password,
            "remember": False,
        },
    )
    assert changed.status_code == 200, (username, changed.text)
    return changed.json()["token"]


with TestClient(app) as client:
    tokens = {
        "admin": login_and_change(client, "admin", "Admin1234"),
        "teacher": login_and_change(client, "teacher1", "Teacher1234"),
        "student": login_and_change(client, "student1", "Student1234"),
        "parent": login_and_change(client, "parent1", "Parent1234"),
    }
    headers = {
        role: {"Authorization": f"Bearer {token}"}
        for role, token in tokens.items()
    }

    # Every production identity can still establish and hydrate a session.
    for role in ("admin", "teacher", "student", "parent"):
        session = client.get("/session", headers=headers[role])
        assert session.status_code == 200, (role, session.text)
        assert session.json()["role"] == role

    # Representative daily-use read paths for each identity.
    admin = client.get("/admin/overview", headers=headers["admin"])
    assert admin.status_code == 200, admin.text
    assert admin.json()["students"] >= 1

    teacher = client.get("/teacher/dashboard", headers=headers["teacher"])
    assert teacher.status_code == 200, teacher.text

    student = client.get("/student/assignments", headers=headers["student"])
    assert student.status_code == 200, student.text
    assert isinstance(student.json(), list)

    progress = client.get("/student/progress", headers=headers["student"])
    assert progress.status_code == 200, progress.text

    children = client.get("/parent/children", headers=headers["parent"])
    assert children.status_code == 200, children.text
    assert children.json(), children.text
    child_id = children.json()[0]["id"]

    child_assignments = client.get(
        f"/parent/children/{child_id}/assignments",
        headers=headers["parent"],
    )
    assert child_assignments.status_code == 200, child_assignments.text

    child_progress = client.get(
        f"/parent/children/{child_id}/progress",
        headers=headers["parent"],
    )
    assert child_progress.status_code == 200, child_progress.text

    # Role-only surfaces must reject other identities rather than silently
    # falling back to a teacher/admin view.
    assert client.get("/admin/overview", headers=headers["student"]).status_code == 403
    assert client.get("/admin/overview", headers=headers["teacher"]).status_code == 403
    assert client.get("/teacher/dashboard", headers=headers["parent"]).status_code == 403
    assert client.get("/student/progress", headers=headers["parent"]).status_code == 403
    assert client.get("/parent/children", headers=headers["student"]).status_code == 403

    # Product shell remains loadable independently of the API role checks.
    assert client.get("/v1").status_code == 200
    assert client.get("/v1/tool").status_code == 200
'''

    env = os.environ.copy()
    env.update(
        {
            "DATABASE_URL": f"sqlite:///{db_path}",
            "JWT_SECRET": "prelaunch-role-jwt-secret-0123456789abcdef0123456789abcdef",
            "COMMERCIAL_ADMIN_KEY": "prelaunch-role-commercial-key-0123456789",
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
        timeout=150,
        check=False,
    )

    assert result.returncode == 0, (
        "prelaunch role journey subprocess failed\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
