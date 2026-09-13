from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_login_session_password_rotation_and_business_gate(tmp_path):
    """Run the real FastAPI auth lifecycle against an isolated SQLite database."""
    db_path = tmp_path / "auth-integration.sqlite3"
    script = r'''
from fastapi.testclient import TestClient

from app import app

with TestClient(app) as client:
    unauthenticated = client.get("/session")
    assert unauthenticated.status_code == 401, unauthenticated.text

    bad = client.post(
        "/login",
        json={"username": "teacher1", "password": "wrong", "remember": False},
    )
    assert bad.status_code == 401, bad.text

    login = client.post(
        "/login",
        json={"username": "teacher1", "password": "123456", "remember": False},
    )
    assert login.status_code == 200, login.text
    login_body = login.json()
    assert login_body["role"] == "teacher"
    assert login_body["name"] == "王老师"
    assert login_body["mustChangePassword"] is True
    old_token = login_body["token"]
    old_headers = {"Authorization": f"Bearer {old_token}"}

    session = client.get("/session", headers=old_headers)
    assert session.status_code == 200, session.text
    assert session.json()["valid"] is True
    assert session.json()["mustChangePassword"] is True

    blocked = client.get("/subscription/me", headers=old_headers)
    assert blocked.status_code == 428, blocked.text

    changed = client.post(
        "/change-password",
        headers=old_headers,
        json={
            "current_password": "123456",
            "new_password": "Study1234",
            "remember": False,
        },
    )
    assert changed.status_code == 200, changed.text
    new_token = changed.json()["token"]
    assert new_token and new_token != old_token
    new_headers = {"Authorization": f"Bearer {new_token}"}

    old_session = client.get("/session", headers=old_headers)
    assert old_session.status_code == 401, old_session.text

    new_session = client.get("/session", headers=new_headers)
    assert new_session.status_code == 200, new_session.text
    assert new_session.json()["mustChangePassword"] is False

    subscription = client.get("/subscription/me", headers=new_headers)
    assert subscription.status_code == 200, subscription.text
    assert subscription.json()["status"] in {"active", "trial", "grace"}

    relogin = client.post(
        "/login",
        json={"username": "teacher1", "password": "Study1234", "remember": True},
    )
    assert relogin.status_code == 200, relogin.text
    assert relogin.json()["mustChangePassword"] is False
'''

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
        timeout=90,
        check=False,
    )

    assert result.returncode == 0, (
        "isolated auth integration subprocess failed\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
