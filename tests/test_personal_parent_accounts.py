"""A solo teacher can create a parent account and bind it to a child.

Two gaps made 家长端 unreachable in a personal workspace: nothing in the UI
created a parent account, and GET /teacher/parents answered [] for every
individual school, so the "绑定家长" picker was always empty. Both are covered
here through the real routes the new page calls.
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

COMMERCIAL_KEY = "personal-parents-commercial-key-0123456789"
PASSWORD = "Teacher1234"
CHANGED = "Teacher5678"


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    db_path = tmp_path_factory.mktemp("parents") / "app.sqlite3"
    os.environ.setdefault("DATABASE_URL", f"sqlite:///{db_path}")
    os.environ["ENABLE_DEMO_SEED"] = "0"
    os.environ.setdefault("JWT_SECRET", "parents-page-jwt-secret-0123456789ab")
    import app as app_module
    import app_v924 as legacy

    legacy.COMMERCIAL_ADMIN_KEY = COMMERCIAL_KEY
    with TestClient(app_module.app) as c:
        yield c


def _workspace(client):
    tag = uuid.uuid4().hex[:8]
    code = f"par-{tag}"
    r = client.post(
        "/operator/schools/create",
        headers={"X-Commercial-Key": COMMERCIAL_KEY},
        json={
            "school_name": f"家长工作室{tag}",
            "school_code": code,
            "admin_name": "李老师",
            "admin_username": code,
            "admin_password": PASSWORD,
            "individual": True,
        },
    )
    assert r.status_code == 200, r.text[:300]
    data = client.post("/login", json={"username": code, "password": PASSWORD}).json()
    headers = {"Authorization": "Bearer " + data["token"]}
    if data.get("mustChangePassword"):
        assert client.post("/change-password", json={"current_password": PASSWORD, "new_password": CHANGED}, headers=headers).status_code == 200
        data = client.post("/login", json={"username": code, "password": CHANGED}).json()
        headers = {"Authorization": "Bearer " + data["token"]}
    return headers


def test_page_is_public_and_calls_the_real_endpoints(client):
    r = client.get("/parent-accounts")
    assert r.status_code == 200
    page = r.text
    for marker in ('id="cy-student"', 'id="cy-name"', 'id="cy-create"', 'id="cy-parent"', 'id="cy-bind"'):
        assert marker in page
    for endpoint in ("/teacher/classes", "/teacher/parents", "/admin/users", "/teacher/students/"):
        assert endpoint in page


def test_start_lists_the_page(client):
    assert 'href="/parent-accounts"' in client.get("/start").text


def test_personal_parents_are_listed_and_bindable(client):
    headers = _workspace(client)

    # The regression: a personal workspace used to get [] here even after creating one.
    assert client.get("/teacher/parents", headers=headers).json() == []

    created = client.post(
        "/admin/users",
        headers=headers,
        json={"name": "小明妈妈", "username": f"pm-{uuid.uuid4().hex[:8]}", "password": PASSWORD, "role": "parent"},
    )
    assert created.status_code == 200, created.text[:300]
    parent = created.json()

    listed = client.get("/teacher/parents", headers=headers).json()
    assert [p["id"] for p in listed] == [parent["id"]]

    student = client.post(
        "/teacher/students",
        headers=headers,
        json={"name": "小明", "username": f"stu-{uuid.uuid4().hex[:8]}", "password": PASSWORD, "grade": 5},
    )
    assert student.status_code == 200, student.text[:300]
    sid = student.json()["id"]
    cid = client.get("/teacher/classes", headers=headers).json()[0]["id"]

    bound = client.post(f"/teacher/students/{sid}/parent", headers=headers, json={"parent_id": parent["id"]})
    assert bound.status_code == 200, bound.text[:300]

    rows = client.get(f"/teacher/classes/{cid}/students", headers=headers).json()
    mine = next(row for row in rows if row["id"] == sid)
    assert mine["parentID"] == parent["id"] and mine["parentName"] == "小明妈妈"

    # Unbinding must leave the student in place.
    assert client.post(f"/teacher/students/{sid}/parent", headers=headers, json={"parent_id": None}).status_code == 200
    rows = client.get(f"/teacher/classes/{cid}/students", headers=headers).json()
    assert next(row for row in rows if row["id"] == sid)["parentID"] is None


def test_personal_workspace_cannot_create_a_second_teacher(client):
    headers = _workspace(client)
    r = client.post(
        "/admin/users",
        headers=headers,
        json={"name": "另一位老师", "username": f"t-{uuid.uuid4().hex[:8]}", "password": PASSWORD, "role": "teacher"},
    )
    assert r.status_code == 400
