"""A school teacher only sees the parents of pupils in their own classes (#1097).

GET /teacher/parents used to filter by school_id alone, so any teacher inside a
school could enumerate every parent account of that school. Inside a school the
list is now scoped to parents already bound to a pupil of a class the teacher
owns; a known account can still be found by exact username so binding a parent
who sits in another class keeps working.
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

COMMERCIAL_KEY = "teacher-parent-scope-key-0123456789"
PASSWORD = "Teacher1234"
CHANGED = "Teacher5678"


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    db_path = tmp_path_factory.mktemp("scope") / "app.sqlite3"
    os.environ.setdefault("DATABASE_URL", f"sqlite:///{db_path}")
    os.environ["ENABLE_DEMO_SEED"] = "0"
    os.environ.setdefault("JWT_SECRET", "teacher-parent-scope-jwt-0123456789ab")
    import app as app_module
    import app_v924 as legacy

    legacy.COMMERCIAL_ADMIN_KEY = COMMERCIAL_KEY
    with TestClient(app_module.app) as c:
        yield c


def _suffix():
    return uuid.uuid4().hex[:8]


def _login(client, username, password=PASSWORD):
    r = client.post("/login", json={"username": username, "password": password})
    assert r.status_code == 200, (username, r.status_code, r.text[:300])
    data = r.json()
    if data.get("mustChangePassword"):
        headers = {"Authorization": "Bearer " + data["token"]}
        changed = client.post(
            "/change-password",
            json={"current_password": password, "new_password": CHANGED},
            headers=headers,
        )
        assert changed.status_code == 200, changed.text[:300]
        data = client.post("/login", json={"username": username, "password": CHANGED}).json()
    return {"Authorization": "Bearer " + data["token"]}


def _school(client):
    tag = _suffix()
    code = f"org-{tag}"
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
    return _login(client, code)


def _teacher(client, admin_headers):
    username = f"t-{_suffix()}"
    r = client.post(
        "/admin/users",
        headers=admin_headers,
        json={"name": "任课老师", "username": username, "password": PASSWORD, "role": "teacher"},
    )
    assert r.status_code == 200, r.text[:300]
    return _login(client, username)


def _class(client, headers, name):
    r = client.post("/teacher/classes", headers=headers, json={"name": name, "grade": 5})
    assert r.status_code == 200, r.text[:300]
    return r.json()


def _student(client, headers, class_id, name):
    r = client.post(
        "/teacher/students",
        headers=headers,
        json={
            "name": name,
            "username": f"stu-{_suffix()}",
            "password": PASSWORD,
            "grade": 5,
            "class_id": class_id,
        },
    )
    assert r.status_code == 200, r.text[:300]
    return r.json()


def test_teacher_sees_only_own_class_parents_and_can_find_a_known_account(client):
    admin = _school(client)
    first = _teacher(client, admin)
    second = _teacher(client, admin)
    first_class = _class(client, first, "一班")
    second_class = _class(client, second, "二班")
    first_student = _student(client, first, first_class["id"], "小明")
    second_student = _student(client, second, second_class["id"], "小红")

    created = client.post(
        "/admin/users",
        headers=admin,
        json={"name": "小明妈妈", "username": f"pm-{_suffix()}", "password": PASSWORD, "role": "parent"},
    )
    assert created.status_code == 200, created.text[:300]
    parent = created.json()

    # A parent account that is not bound to any pupil is invisible to the teacher.
    assert client.get("/teacher/parents", headers=first).json() == []

    bound = client.post(
        f"/teacher/students/{first_student['id']}/parent",
        headers=first,
        json={"parent_id": parent["id"]},
    )
    assert bound.status_code == 200, bound.text[:300]

    # The owning teacher sees the parent they just bound.
    assert [p["id"] for p in client.get("/teacher/parents", headers=first).json()] == [parent["id"]]
    # Another teacher of the same school must not be able to enumerate it.
    assert client.get("/teacher/parents", headers=second).json() == []
    # Lookup is exact: neither a name nor a truncated account leaks an enumeration.
    assert client.get("/teacher/parents", headers=second, params={"q": "小明妈妈"}).json() == []
    assert client.get("/teacher/parents", headers=second, params={"q": parent["username"][:-1]}).json() == []

    # Knowing the exact account is enough to bind a pupil from another class.
    found = client.get("/teacher/parents", headers=second, params={"q": parent["username"]}).json()
    assert [p["id"] for p in found] == [parent["id"]]
    cross = client.post(
        f"/teacher/students/{second_student['id']}/parent",
        headers=second,
        json={"parent_id": parent["id"]},
    )
    assert cross.status_code == 200, cross.text[:300]

    # After binding, the second teacher sees it in their list as well.
    assert [p["id"] for p in client.get("/teacher/parents", headers=second).json()] == [parent["id"]]


def test_lookup_never_duplicates_an_already_listed_parent(client):
    admin = _school(client)
    teacher = _teacher(client, admin)
    classroom = _class(client, teacher, "一班")
    student = _student(client, teacher, classroom["id"], "小刚")
    created = client.post(
        "/admin/users",
        headers=admin,
        json={"name": "小刚爸爸", "username": f"pf-{_suffix()}", "password": PASSWORD, "role": "parent"},
    )
    assert created.status_code == 200, created.text[:300]
    parent = created.json()
    assert client.post(
        f"/teacher/students/{student['id']}/parent",
        headers=teacher,
        json={"parent_id": parent["id"]},
    ).status_code == 200

    listed = client.get("/teacher/parents", headers=teacher).json()
    looked_up = client.get("/teacher/parents", headers=teacher, params={"q": parent["username"]}).json()
    assert [p["id"] for p in listed] == [parent["id"]]
    assert [p["id"] for p in looked_up] == [parent["id"]]
