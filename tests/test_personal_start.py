"""Personal workspace quick page: one screen a solo teacher can act on.

The institution workspace lists 晚托/周末课/作业/学情 as flat cards with school
vocabulary. A solo teacher needs three next steps and four doors, so /start shows
exactly that and points at the existing pages instead of duplicating them.
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

COMMERCIAL_KEY = "personal-start-commercial-key-0123456789"
PASSWORD = "Teacher1234"
PERSONAL_COOKIE = "cy_personal_home"
CHANGED = "Teacher5678"


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    db_path = tmp_path_factory.mktemp("start") / "app.sqlite3"
    os.environ.setdefault("DATABASE_URL", f"sqlite:///{db_path}")
    os.environ["ENABLE_DEMO_SEED"] = "0"
    os.environ.setdefault("JWT_SECRET", "start-page-jwt-secret-0123456789abcdef")
    import app as app_module
    import app_v924 as legacy

    legacy.COMMERCIAL_ADMIN_KEY = COMMERCIAL_KEY
    legacy.ensure_school_individual_column()
    with TestClient(app_module.app) as c:
        yield c


def _personal_workspace(client):
    tag = uuid.uuid4().hex[:8]
    code = f"start-{tag}"
    r = client.post(
        "/operator/schools/create",
        headers={"X-Commercial-Key": COMMERCIAL_KEY},
        json={
            "school_name": f"快捷页工作室{tag}",
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


def test_start_is_public_and_v1_lands_there_for_personal_browsers(client):
    # Browsers navigate without the JSON token, so the quick page must render as a guide.
    page = client.get("/start")
    assert page.status_code == 200
    assert "添加我的学生" in page.text

    # /v1 sends a personal browser to the quick page; other browsers keep the console.
    assert client.get("/v1", cookies={PERSONAL_COOKIE: "1"}).url.path == "/start"
    assert client.get("/v1").url.path == "/v1"


def test_start_page_guides_three_steps(client):
    headers = _personal_workspace(client)
    r = client.get("/start", headers=headers)
    assert r.status_code == 200, r.text[:300]
    page = r.text

    assert "工作室" in page
    assert "添加我的学生" in page
    assert "填写自己的 AI Key" in page
    assert "准备并上第一节课" in page
    # Fresh workspace: nothing done yet, so every step offers an action.
    assert "还没有学生" in page
    assert "AI 已配置" not in page

    # Doors to the real pages, not copies of them.
    for href in ("/v1/weekend-plan", "/v1/weekend", "/v1/homework", "/v1/knowledge-map"):
        assert f'href="{href}"' in page


def test_start_page_reflects_real_state(client):
    headers = _personal_workspace(client)
    r = client.post(
        "/teacher/students",
        headers=headers,
        json={"name": "小明", "username": f"stu-{uuid.uuid4().hex[:8]}", "password": PASSWORD, "grade": 5},
    )
    assert r.status_code == 200, r.text[:300]

    page = client.get("/start", headers=headers).text
    assert "已经有 1 名学生" in page

    # Adding a student must not change the AI step's wording.
    assert "还没有配置" in page or "填模型地址" in page
