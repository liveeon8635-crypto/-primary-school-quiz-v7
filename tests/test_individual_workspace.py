"""Personal free workspace: one account that is both admin and teacher.

The whole point of the personal edition is a single self-serve account: it
creates its own student list, adds students into it, fills its own AI key and
teaches from that same identity. Institutions keep their existing behaviour.

Each test builds its own workspace with unique codes, so nothing depends on
another test's leftovers.
"""

from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

COMMERCIAL_KEY = "individual-workspace-commercial-key-0123456789"
PASSWORD = "Teacher1234"
CHANGED = "Teacher5678"
AI_PAYLOAD = {
    "provider": "openai_compatible",
    "base_url": "https://api.deepseek.com/v1",
    "model": "deepseek-chat",
    "api_key": "sk-test-0123456789abcdef",
    "enabled": True,
    "allow_student_data": False,
}


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    db_path = tmp_path_factory.mktemp("individual") / "app.sqlite3"
    os.environ.setdefault("DATABASE_URL", f"sqlite:///{db_path}")
    os.environ["ENABLE_DEMO_SEED"] = "0"
    os.environ.setdefault("JWT_SECRET", "individual-workspace-jwt-secret-0123456789abcdef")
    import app as app_module
    import app_v924 as legacy

    # The operator key is read into a module constant at import time, and another
    # test module may already have imported the app in this process.
    legacy.COMMERCIAL_ADMIN_KEY = COMMERCIAL_KEY
    legacy.ensure_school_individual_column()

    with TestClient(app_module.app) as c:
        yield c


def _suffix():
    return uuid.uuid4().hex[:8]


def _login(client, username, password=PASSWORD):
    """Log in, clearing the forced first-password change when needed."""
    r = client.post("/login", json={"username": username, "password": password})
    if r.status_code == 401 and password == PASSWORD:
        r = client.post("/login", json={"username": username, "password": CHANGED})
    assert r.status_code == 200, (username, r.status_code, r.text[:300])
    data = r.json()
    if data.get("mustChangePassword"):
        h = {"Authorization": "Bearer " + data["token"]}
        r2 = client.post("/change-password", json={"current_password": password, "new_password": CHANGED}, headers=h)
        assert r2.status_code == 200, r2.text[:300]
        data = client.post("/login", json={"username": username, "password": CHANGED}).json()
    return {"Authorization": "Bearer " + data["token"]}, data


def _personal_workspace(client, prefix="personal"):
    tag = _suffix()
    code = f"{prefix}-{tag}"
    r = client.post(
        "/operator/schools/create",
        headers={"X-Commercial-Key": COMMERCIAL_KEY},
        json={
            "school_name": f"个人工作室{tag}",
            "school_code": code,
            "admin_name": "李老师",
            "admin_username": code,
            "admin_password": PASSWORD,
            "individual": True,
        },
    )
    assert r.status_code == 200, r.text[:400]
    body = r.json()
    headers, session = _login(client, code)
    return {"code": code, "body": body, "headers": headers, "session": session, "school_id": body["school"]["schoolID"]}


def _school(client, prefix="org"):
    tag = _suffix()
    code = f"{prefix}-{tag}"
    r = client.post(
        "/operator/schools/create",
        headers={"X-Commercial-Key": COMMERCIAL_KEY},
        json={
            "school_name": f"机构{tag}",
            "school_code": code,
            "admin_name": "机构管理员",
            "admin_username": code,
            "admin_password": PASSWORD,
            "plan_code": "school_basic",
        },
    )
    assert r.status_code == 200, r.text[:400]
    return {"code": code, "body": r.json(), "school_id": r.json()["school"]["schoolID"]}


def _add_student(client, headers, name, grade=5):
    username = f"stu-{_suffix()}"
    r = client.post(
        "/teacher/students",
        headers=headers,
        json={"name": name, "username": username, "password": PASSWORD, "grade": grade},
    )
    assert r.status_code == 200, r.text[:300]
    return r.json()


def test_personal_workspace_is_one_account_that_owns_its_own_student_list(client):
    ws = _personal_workspace(client)
    assert ws["body"]["school"]["planCode"] == "free"
    # The client is told to open the teaching UI, while the stored role stays admin.
    assert ws["session"]["role"] == "teacher"
    assert ws["session"]["schoolIndividual"] is True
    assert client.get("/session", headers=ws["headers"]).json()["role"] == "teacher"
    # Account-level endpoints still work because the stored role is admin.
    assert client.get("/admin/users", headers=ws["headers"]).status_code == 200
    # The account export serialises the real ORM row, not a per-request stand-in.
    export = client.get("/account/export.json", headers=ws["headers"])
    assert export.status_code == 200, export.text[:300]
    assert export.headers["content-type"].startswith("application/json")
    assert export.json()["meta"]["appVersion"]
    # The teaching UI and the AI settings page both open for this one account.
    for page in ("/v1/workspace?mode=institution", "/v1/tool?page=ai", "/v1/weekend-plan"):
        r = client.get(page, headers=ws["headers"])
        assert r.status_code == 200, (page, r.status_code, r.text[:200])
    assert ws["body"]["school"]["readOnly"] is False
    # No shadow teaching account: the admin account is the teacher.
    assert "teacherCredential" not in ws["body"]
    headers = ws["headers"]

    first = _add_student(client, headers, "小明")
    _add_student(client, headers, "小红")

    classes = client.get("/teacher/classes", headers=headers).json()
    assert len(classes) == 1
    assert classes[0]["name"] == "我的学生名单（5年级）"
    assert classes[0]["studentCount"] == 2

    # The same identity that added the student can read the roster back and open
    # the student archive: teacher_id is this account, not a second one.
    roster = client.get(f"/teacher/classes/{classes[0]['id']}/students", headers=headers)
    assert roster.status_code == 200, roster.text[:300]
    assert {row["name"] for row in roster.json()} == {"小明", "小红"}

    profile = client.get(f"/teacher/students/{first['id']}/growth-profile", headers=headers)
    assert profile.status_code == 200, profile.text[:300]
    assert profile.json()["student"]["name"] == "小明"

    # Re-stating the list never creates a second class nor hits the plan cap.
    r = client.post("/teacher/classes", headers=headers, json={"name": "周末班", "grade": 5})
    assert r.status_code == 200, r.text[:300]
    assert r.json()["id"] == classes[0]["id"]
    assert len(client.get("/teacher/classes", headers=headers).json()) == 1

    # Parents are still created and bound by the same account.
    parent_username = f"parent-{_suffix()}"
    r = client.post(
        "/admin/users",
        headers=headers,
        json={"name": "小明家长", "username": parent_username, "password": PASSWORD, "role": "parent"},
    )
    assert r.status_code == 200, r.text[:300]
    r = client.post(f"/teacher/students/{first['id']}/parent", headers=headers, json={"parent_id": r.json()["id"]})
    assert r.status_code == 200, r.text[:300]
    assert r.json()["parent"]["username"] == parent_username


def test_personal_workspace_cannot_grow_a_second_teacher(client):
    ws = _personal_workspace(client)
    r = client.post(
        "/admin/users",
        headers=ws["headers"],
        json={"name": "王老师", "username": f"t-{_suffix()}", "password": PASSWORD, "role": "teacher"},
    )
    assert r.status_code == 400
    assert "任课老师" in r.json()["detail"]


def test_personal_workspace_stays_free_and_writable_against_operator_tools(client):
    ws = _personal_workspace(client)
    headers = ws["headers"]
    sid = ws["school_id"]

    # Never expires, even if the stored subscription row drifts.
    sub = client.get("/subscription/me", headers=headers)
    assert sub.status_code == 200
    assert sub.json()["canWrite"] is True
    assert sub.json()["periodEndsAt"] is None

    # Operator tools refuse to make it read-only, charge it, or cap it.
    r = client.post(
        f"/operator/subscriptions/{sid}",
        headers={"X-Commercial-Key": COMMERCIAL_KEY},
        json={"plan_code": "school_basic", "status": "expired"},
    )
    assert r.status_code == 400, r.text[:300]

    r = client.post(
        f"/operator/schools/{sid}/renewals",
        headers={"X-Commercial-Key": COMMERCIAL_KEY},
        json={"plan_code": "school_basic", "period_days": 365, "amount_yuan": 100},
    )
    assert r.status_code == 400, r.text[:300]

    r = client.post(
        f"/operator/schools/{sid}/quota",
        headers={"X-Commercial-Key": COMMERCIAL_KEY},
        json={"students": "1", "note": "try to cap"},
    )
    assert r.status_code == 400, r.text[:300]

    # go-live must refuse before it changes anything, so a paused attempt leaves no trace.
    r = client.post(
        f"/operator/schools/{sid}/go-live",
        headers={"X-Commercial-Key": COMMERCIAL_KEY},
        json={"plan_code": "school_basic", "period_days": 365, "amount_yuan": 0},
    )
    assert r.status_code == 400, r.text[:300]
    detail = client.get(
        f"/operator/schools/{sid}/events", headers={"X-Commercial-Key": COMMERCIAL_KEY}
    )
    assert detail.status_code == 200, detail.text[:200]
    assert not [e for e in detail.json() if e.get("action") == "formal_go_live"]

    # Still writable afterwards.
    _add_student(client, headers, "小刚")
    assert client.get("/subscription/me", headers=headers).json()["canWrite"] is True


def test_teacher_fills_own_ai_key_only_in_personal_workspace(client):
    org = _school(client)
    school_headers, _ = _login(client, org["code"])
    teacher_username = f"org-teacher-{_suffix()}"
    r = client.post(
        "/admin/users",
        headers=school_headers,
        json={"name": "王老师", "username": teacher_username, "password": PASSWORD, "role": "teacher"},
    )
    assert r.status_code == 200, r.text[:300]
    school_teacher_headers, _ = _login(client, teacher_username)

    # A school teacher may not change the school's AI settings.
    r = client.put("/teacher/ai-config", headers=school_teacher_headers, json=AI_PAYLOAD)
    assert r.status_code == 403
    assert "学校管理员" in r.json()["detail"]
    assert client.post("/teacher/ai-test", headers=school_teacher_headers).status_code == 403

    # The personal account fills its own key.
    ws = _personal_workspace(client)
    r = client.get("/teacher/ai-config", headers=ws["headers"])
    assert r.status_code == 200
    assert r.json()["configured"] is False

    r = client.put("/teacher/ai-config", headers=ws["headers"], json=AI_PAYLOAD)
    assert r.status_code == 200, r.text[:300]
    assert r.json()["config"]["hasKey"] is True
    assert r.json()["config"]["enabled"] is True
    assert client.get("/teacher/ai-config", headers=ws["headers"]).json()["configured"] is True

    # The school admin route still works exactly as before.
    r = client.put("/admin/ai-config", headers=school_headers, json=AI_PAYLOAD)
    assert r.status_code == 200, r.text[:300]


def test_schools_keep_classes_multiple_teachers_and_the_old_contract(client):
    org = _school(client)
    school_headers, session = _login(client, org["code"])
    assert session["role"] == "admin"

    # An institution admin stays an administrator, not a teacher.
    assert client.get("/teacher/classes", headers=school_headers).status_code == 403

    teacher_username = f"org-teacher-{_suffix()}"
    r = client.post(
        "/admin/users",
        headers=school_headers,
        json={"name": "王老师", "username": teacher_username, "password": PASSWORD, "role": "teacher"},
    )
    assert r.status_code == 200, r.text[:300]
    teacher_headers, _ = _login(client, teacher_username)

    # Adding a student without a class stays a validation error, as before.
    r = client.post(
        "/teacher/students",
        headers=teacher_headers,
        json={"name": "学生甲", "username": f"stu-{_suffix()}", "password": PASSWORD, "grade": 5},
    )
    assert r.status_code == 422, r.text[:300]

    # Named classes still behave like classes.
    r = client.post("/teacher/classes", headers=teacher_headers, json={"name": "五(2)班", "grade": 5})
    assert r.status_code == 200, r.text[:300]
    class_id = r.json()["id"]
    r = client.post(
        "/teacher/students",
        headers=teacher_headers,
        json={"name": "学生乙", "username": f"stu-{_suffix()}", "password": PASSWORD, "grade": 5, "class_id": class_id},
    )
    assert r.status_code == 200, r.text[:300]
    assert [c["name"] for c in client.get("/teacher/classes", headers=teacher_headers).json()] == ["五(2)班"]
