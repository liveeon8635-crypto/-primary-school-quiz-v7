from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_representative_teacher_admin_parent_student_permission_matrix(tmp_path):
    db_path = tmp_path / "role-permissions.sqlite3"
    script = r'''
from fastapi.testclient import TestClient
from app import app


def login_and_change(client, username, new_password):
    login = client.post(
        "/login",
        json={"username": username, "password": "123456", "remember": False},
    )
    assert login.status_code == 200, login.text
    token = login.json()["token"]
    changed = client.post(
        "/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "current_password": "123456",
            "new_password": new_password,
            "remember": False,
        },
    )
    assert changed.status_code == 200, changed.text
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

    student_session = client.get("/session", headers=headers["student"])
    assert student_session.status_code == 200, student_session.text
    sid = student_session.json()["userID"]

    # Teacher/admin operational evidence coverage is intentionally staff-only.
    for role in ("teacher", "admin"):
        response = client.get("/v2/teacher/evidence-coverage", headers=headers[role])
        assert response.status_code == 200, (role, response.text)

    for role in ("student", "parent"):
        response = client.get("/v2/teacher/evidence-coverage", headers=headers[role])
        assert response.status_code == 403, (role, response.text)

    unauthenticated = client.get("/v2/teacher/evidence-coverage")
    assert unauthenticated.status_code == 401, unauthenticated.text

    # The continuous student evidence view is shared only through the existing
    # role-safe relationship checks: staff, the bound parent and the student.
    for role in ("teacher", "admin", "student", "parent"):
        response = client.get(
            f"/v1/students/{sid}/learning-evidence",
            headers=headers[role],
        )
        assert response.status_code == 200, (role, response.text)
        assert response.json()["masteryInferred"] is False

    # Teacher-internal manual observation detail remains staff-only.
    for role in ("teacher", "admin"):
        response = client.get(
            f"/v2/students/{sid}/learning-evidence/manual",
            headers=headers[role],
        )
        assert response.status_code == 200, (role, response.text)

    for role in ("student", "parent"):
        response = client.get(
            f"/v2/students/{sid}/learning-evidence/manual",
            headers=headers[role],
        )
        assert response.status_code == 403, (role, response.text)
'''

    env = os.environ.copy()
    env.update(
        {
            "DATABASE_URL": f"sqlite:///{db_path}",
            "JWT_SECRET": "role-test-jwt-secret-0123456789abcdef0123456789abcdef",
            "COMMERCIAL_ADMIN_KEY": "role-test-commercial-key-0123456789",
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
        "isolated role permission matrix subprocess failed\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
