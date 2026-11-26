"""Operator-controlled in-place conversion of a single-teacher school to Personal Free Edition."""

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

COMMERCIAL_KEY = "personal-migration-commercial-key-0123456789"
PASSWORD = "Teacher1234"
CHANGED = "Teacher5678"


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    db_path = tmp_path_factory.mktemp("migration") / "app.sqlite3"
    os.environ.setdefault("DATABASE_URL", f"sqlite:///{db_path}")
    os.environ["ENABLE_DEMO_SEED"] = "0"
    os.environ.setdefault("JWT_SECRET", "migration-jwt-secret-0123456789abcdef")
    import app as app_module
    import app_v924 as legacy

    legacy.COMMERCIAL_ADMIN_KEY = COMMERCIAL_KEY
    legacy.ensure_school_individual_column()
    with TestClient(app_module.app) as c:
        yield c


def _login(client, username, password=PASSWORD):
    r = client.post("/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text[:300]
    data = r.json()
    headers = {"Authorization": "Bearer " + data["token"]}
    if data.get("mustChangePassword"):
        assert client.post(
            "/change-password",
            json={"current_password": password, "new_password": CHANGED},
            headers=headers,
        ).status_code == 200
        r = client.post("/login", json={"username": username, "password": CHANGED})
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        headers = {"Authorization": "Bearer " + data["token"]}
    return r, headers, data


def _create_school(client, tag):
    code = f"mig-{tag}"
    r = client.post(
        "/operator/schools/create",
        headers={"X-Commercial-Key": COMMERCIAL_KEY},
        json={
            "school_name": f"旧试点学校{tag}",
            "school_code": code,
            "admin_name": "旧管理员",
            "admin_username": f"adm-{tag}",
            "admin_password": PASSWORD,
            "plan_code": "school_basic",
            "status": "trial",
        },
    )
    assert r.status_code == 200, r.text[:300]
    return r.json()["school"]["schoolID"], f"adm-{tag}"


def test_convert_single_teacher_school_preserves_data_and_enables_personal_edition(client):
    tag = uuid.uuid4().hex[:8]
    school_id, admin_user = _create_school(client, tag)
    _, admin_headers, _ = _login(client, admin_user)

    # Create one teacher (like zhonglaoshi), one class, one student, one parent
    t_user = f"zhong-{tag}"
    assert client.post(
        "/admin/users",
        headers=admin_headers,
        json={"name": "钟老师", "username": t_user, "password": PASSWORD, "role": "teacher"},
    ).status_code == 200
    _, t_headers, t_login_before = _login(client, t_user)
    assert t_login_before["schoolIndividual"] is False

    cls = client.post(
        "/teacher/classes",
        headers=t_headers,
        json={"name": "五年级一班", "grade": 5},
    )
    assert cls.status_code == 200
    cid = cls.json()["id"]

    stu_user = f"stu-{tag}"
    stu = client.post(
        "/teacher/students",
        headers=t_headers,
        json={"name": "小明", "username": stu_user, "password": PASSWORD, "class_id": cid, "grade": 5},
    )
    assert stu.status_code == 200
    sid = stu.json()["id"]

    # Preview must report eligible with zhonglaoshi as owner and old admin as extra admin
    op_headers = {"X-Commercial-Key": COMMERCIAL_KEY}
    prev = client.get(f"/operator/schools/{school_id}/convert-personal/preview", headers=op_headers)
    assert prev.status_code == 200, prev.text[:300]
    p = prev.json()
    assert p["eligible"] is True
    assert p["owner"]["username"] == t_user
    assert [a["username"] for a in p["extraAdmins"]] == [admin_user]
    assert p["counts"]["students"] == 1 and p["counts"]["classes"] == 1

    # Must reject without confirm=True
    bad = client.post(
        f"/operator/schools/{school_id}/convert-personal",
        headers=op_headers,
        json={"confirm": False},
    )
    assert bad.status_code == 400

    # Execute conversion
    done = client.post(
        f"/operator/schools/{school_id}/convert-personal",
        headers=op_headers,
        json={"confirm": True, "deactivate_extra_admins": True, "note": "旧账号迁入个人版"},
    )
    assert done.status_code == 200, done.text[:300]
    body = done.json()
    assert body["ok"] is True
    assert body["owner"]["username"] == t_user
    assert body["deactivatedAdmins"] == [admin_user]
    assert body["school"]["planCode"] == "free"
    assert body["school"]["status"] == "active"

    # Teacher now logs in as personal workspace owner, gets cy_personal_home=1, and keeps all students
    login_res, t_headers2, payload = _login(client, t_user, password=CHANGED)
    assert payload["schoolIndividual"] is True
    assert "cy_personal_home=1" in ";".join(login_res.headers.get_list("set-cookie"))
    summary = client.get("/start/summary", headers=t_headers2)
    assert summary.status_code == 200
    assert summary.json()["students"] == 1

    # Student still exists and remains strictly student role (no escalation)
    stu_login, stu_headers, stu_payload = _login(client, stu_user)
    assert stu_payload["role"] == "student"
    assert "cy_personal_home=1" not in ";".join(stu_login.headers.get_list("set-cookie"))
    assert client.get("/start/summary", headers=stu_headers).status_code == 403

    # Old admin is deactivated (cannot log in)
    assert client.post("/login", json={"username": admin_user, "password": CHANGED}).status_code == 401

    # Re-running preview reports alreadyIndividual and ineligible
    prev2 = client.get(f"/operator/schools/{school_id}/convert-personal/preview", headers=op_headers).json()
    assert prev2["alreadyIndividual"] is True and prev2["eligible"] is False


def test_convert_blocks_multi_teacher_school_and_operator_ui_exposes_entry(client):
    tag = uuid.uuid4().hex[:8]
    school_id, admin_user = _create_school(client, tag)
    _, admin_headers, _ = _login(client, admin_user)

    for idx in (1, 2):
        assert client.post(
            "/admin/users",
            headers=admin_headers,
            json={"name": f"老师{idx}", "username": f"t{idx}-{tag}", "password": PASSWORD, "role": "teacher"},
        ).status_code == 200

    op_headers = {"X-Commercial-Key": COMMERCIAL_KEY}
    prev = client.get(f"/operator/schools/{school_id}/convert-personal/preview", headers=op_headers).json()
    assert prev["eligible"] is False
    assert "2 名活跃教师" in prev["reason"]

    res = client.post(
        f"/operator/schools/{school_id}/convert-personal",
        headers=op_headers,
        json={"confirm": True},
    )
    assert res.status_code == 400

    op_html = client.get("/operator-console").text
    assert "openConvertPersonal(" in op_html
    assert "/convert-personal/preview" in op_html
