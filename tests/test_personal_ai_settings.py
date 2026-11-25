"""A solo teacher fills in their own AI key.

The API (/teacher/ai-config, /teacher/ai-test) has existed since the personal
workspace shipped, but no page called it: the classic "AI 助手" page told a
one-person workspace to "contact the school administrator", and there is none.
This page is the missing front end; it lives outside INDEX_HTML so the shared
Safari 12 asset manifest never changes.
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

COMMERCIAL_KEY = "personal-ai-page-commercial-key-0123456789"
PASSWORD = "Teacher1234"
CHANGED = "Teacher5678"


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    db_path = tmp_path_factory.mktemp("aipage") / "app.sqlite3"
    os.environ.setdefault("DATABASE_URL", f"sqlite:///{db_path}")
    os.environ["ENABLE_DEMO_SEED"] = "0"
    os.environ.setdefault("JWT_SECRET", "ai-page-jwt-secret-0123456789abcdef")
    import app as app_module
    import app_v924 as legacy

    legacy.COMMERCIAL_ADMIN_KEY = COMMERCIAL_KEY
    with TestClient(app_module.app) as c:
        yield c


def _workspace(client):
    tag = uuid.uuid4().hex[:8]
    code = f"ai-{tag}"
    r = client.post(
        "/operator/schools/create",
        headers={"X-Commercial-Key": COMMERCIAL_KEY},
        json={
            "school_name": f"AI 设置工作室{tag}",
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
    r = client.get("/teacher/ai-settings")
    assert r.status_code == 200
    page = r.text
    for marker in ('id="cy-base"', 'id="cy-model"', 'id="cy-key"', 'id="cy-save"', 'id="cy-test"'):
        assert marker in page
    # The page is only useful if it talks to the existing API, not to a copy.
    assert "/teacher/ai-config" in page
    assert "/teacher/ai-test" in page


def test_start_step_two_points_here(client):
    headers = _workspace(client)
    page = client.get("/start", headers=headers).text
    assert 'href="/teacher/ai-settings"' in page
    assert client.get("/start/summary", headers=headers).json()["s2url"] == "/teacher/ai-settings"


def test_saving_a_key_through_the_same_api_the_page_uses(client):
    headers = _workspace(client)
    assert client.get("/teacher/ai-config", headers=headers).json()["hasKey"] is False

    r = client.put(
        "/teacher/ai-config",
        headers=headers,
        json={
            "provider": "openai_responses",
            "base_url": "https://api.openai.com/v1",
            "model": "gpt-4o-mini",
            "api_key": "sk-test-0123456789abcdef",
            "enabled": True,
            "allow_student_data": False,
            "clear_api_key": False,
        },
    )
    assert r.status_code == 200, r.text[:300]
    cfg = client.get("/teacher/ai-config", headers=headers).json()
    assert cfg["hasKey"] is True and cfg["keyLast4"] == "cdef" and cfg["enabled"] is True

    # Saving again without a key must keep the stored one, not wipe it.
    r = client.put(
        "/teacher/ai-config",
        headers=headers,
        json={"provider": "openai_responses", "base_url": "https://api.openai.com/v1", "model": "gpt-4o-mini", "api_key": "", "enabled": True},
    )
    assert r.status_code == 200
    assert client.get("/teacher/ai-config", headers=headers).json()["hasKey"] is True


def test_page_exposes_provider_selector_and_student_data_toggle(client):
    page = client.get("/teacher/ai-settings").text
    assert 'id="cy-provider"' in page
    assert 'value="openai_compatible"' in page
    assert 'id="cy-allow-student"' in page
    assert "provider:'openai_responses'" not in page
    assert "allow_student_data:false" not in page


def test_openai_compatible_protocol_saved_and_tested_without_key_leak(client, monkeypatch):
    headers = _workspace(client)
    r = client.put(
        "/teacher/ai-config",
        headers=headers,
        json={
            "provider": "openai_compatible",
            "base_url": "https://api.deepseek.com/v1",
            "model": "deepseek-chat",
            "api_key": "sk-deepseek-secret-99887766",
            "enabled": True,
            "allow_student_data": False,
        },
    )
    assert r.status_code == 200, r.text[:300]
    cfg = client.get("/teacher/ai-config", headers=headers).json()
    assert cfg["provider"] == "openai_compatible"
    assert cfg["baseURL"] == "https://api.deepseek.com/v1"

    import app_v924 as legacy

    monkeypatch.setattr(legacy, "_validate_ai_base_url", lambda base, runtime=False: base)
    seen = {}

    class _OkResp:
        ok = True
        status_code = 200
        def json(self):
            return {"choices": [{"message": {"content": "连接成功"}}], "usage": {"prompt_tokens": 3, "completion_tokens": 2}}

    def _fake_post(url, headers=None, json=None, timeout=None):
        seen["url"] = url
        return _OkResp()

    monkeypatch.setattr(legacy.requests, "post", _fake_post)
    test_res = client.post("/teacher/ai-test", headers=headers)
    assert test_res.status_code == 200
    assert seen["url"] == "https://api.deepseek.com/v1/chat/completions"

    class _ErrResp:
        ok = False
        status_code = 401
        def json(self):
            return {"error": {"message": "invalid api key"}}

    monkeypatch.setattr(legacy.requests, "post", lambda *a, **kw: _ErrResp())
    err_res = client.post("/teacher/ai-test", headers=headers)
    assert err_res.status_code == 502
    assert "sk-deepseek-secret-99887766" not in err_res.text


def test_page_exposes_pause_and_clear_key_controls(client):
    page = client.get("/teacher/ai-settings").text
    assert 'id="cy-disable"' in page
    assert 'id="cy-clear-key"' in page

    headers = _workspace(client)
    r = client.put(
        "/teacher/ai-config",
        headers=headers,
        json={
            "provider": "openai_compatible",
            "base_url": "https://api.deepseek.com/v1",
            "model": "deepseek-chat",
            "api_key": "sk-pause-clear-test-1234",
            "enabled": True,
            "allow_student_data": False,
            "clear_api_key": False,
        },
    )
    assert r.status_code == 200
    # Pause AI without clearing key
    r = client.put(
        "/teacher/ai-config",
        headers=headers,
        json={
            "provider": "openai_compatible",
            "base_url": "https://api.deepseek.com/v1",
            "model": "deepseek-chat",
            "api_key": "",
            "enabled": False,
            "allow_student_data": False,
            "clear_api_key": False,
        },
    )
    assert r.status_code == 200
    cfg = client.get("/teacher/ai-config", headers=headers).json()
    assert cfg["enabled"] is False and cfg["hasKey"] is True

    # Clear key and disable
    r = client.put(
        "/teacher/ai-config",
        headers=headers,
        json={
            "provider": "openai_compatible",
            "base_url": "https://api.deepseek.com/v1",
            "model": "deepseek-chat",
            "api_key": "",
            "enabled": False,
            "allow_student_data": False,
            "clear_api_key": True,
        },
    )
    assert r.status_code == 200
    cfg = client.get("/teacher/ai-config", headers=headers).json()
    assert cfg["enabled"] is False and cfg["hasKey"] is False
