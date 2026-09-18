from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_learning_evidence_endpoint_role_access(tmp_path):
    db_path = tmp_path / "evidence-access.sqlite3"
    script = r'''
from fastapi.testclient import TestClient
from app import app

def login_and_change(client, username, old_password, new_password):
    login = client.post("/login", json={"username":username,"password":old_password,"remember":False})
    assert login.status_code == 200, login.text
    token = login.json()["token"]
    changed = client.post("/change-password", headers={"Authorization":f"Bearer {token}"}, json={"current_password":old_password,"new_password":new_password,"remember":False})
    assert changed.status_code == 200, changed.text
    return changed.json()["token"]

with TestClient(app) as client:
    student_token = login_and_change(client, "student1", "123456", "Student1234")
    parent_token = login_and_change(client, "parent1", "123456", "Parent1234")
    teacher_token = login_and_change(client, "teacher1", "123456", "Teacher1234")

    sh = {"Authorization":f"Bearer {student_token}"}
    ph = {"Authorization":f"Bearer {parent_token}"}
    th = {"Authorization":f"Bearer {teacher_token}"}

    student_session = client.get("/session", headers=sh).json()
    sid = student_session["userID"]

    own = client.get(f"/v1/students/{sid}/learning-evidence", headers=sh)
    assert own.status_code == 200, own.text
    assert own.json()["studentId"] in {str(sid), None}
    assert own.json()["masteryInferred"] is False

    parent = client.get(f"/v1/students/{sid}/learning-evidence", headers=ph)
    assert parent.status_code == 200, parent.text
    assert parent.json()["masteryInferred"] is False

    teacher = client.get(f"/v1/students/{sid}/learning-evidence", headers=th)
    assert teacher.status_code == 200, teacher.text
    assert teacher.json()["masteryInferred"] is False

    other = client.get(f"/v1/students/{sid+999}/learning-evidence", headers=sh)
    assert other.status_code in {403,404}

    unauth = client.get(f"/v1/students/{sid}/learning-evidence")
    assert unauth.status_code == 401
'''

    env = os.environ.copy()
    env.update({
        "DATABASE_URL": f"sqlite:///{db_path}",
        "JWT_SECRET": "integration-test-jwt-secret-0123456789abcdef0123456789abcdef",
        "COMMERCIAL_ADMIN_KEY": "integration-test-commercial-key-0123456789",
        "ENABLE_DEMO_SEED": "1",
        "PYTHONPATH": str(ROOT),
    })
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert result.returncode == 0, f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"


def test_v1_student_page_fetches_evidence_only_when_missing():
    from app import app  # noqa: F401
    from changying.web import v1 as v1_module
    html = v1_module.v1_html()
    assert "/v1/students/"+"" in "/v1/students/"
    assert "if(!profile.learningEvidence&&id)" in html
    assert "'/learning-evidence'" in html
    assert "profile.learningEvidence=await api" in html