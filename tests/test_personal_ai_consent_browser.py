"""Real browser verification for /teacher/ai-settings and /parent/ai-consent-confirm."""

from __future__ import annotations

import os
import socket
import sys
import threading
import time
import uuid
from pathlib import Path

import pytest
import uvicorn
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

COMMERCIAL_KEY = "browser-consent-commercial-key-0123456789"
PASSWORD = "Teacher1234"
CHANGED = "Teacher5678"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def test_real_browser_ai_settings_and_parent_consent_flow(tmp_path, monkeypatch):
    playwright_sync = pytest.importorskip("playwright.sync_api")

    db_path = tmp_path / "browser.sqlite3"
    os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"
    os.environ["ENABLE_DEMO_SEED"] = "0"
    os.environ.setdefault("JWT_SECRET", "browser-consent-jwt-secret-0123456789abcdef")

    import app as app_module
    import app_v924 as legacy

    legacy.COMMERCIAL_ADMIN_KEY = COMMERCIAL_KEY
    with TestClient(app_module.app) as client:
        tag = uuid.uuid4().hex[:8]
        t_code = f"bt-{tag}"
        assert client.post(
            "/operator/schools/create",
            headers={"X-Commercial-Key": COMMERCIAL_KEY},
            json={
                "school_name": f"浏览器测试工作室{tag}",
                "school_code": t_code,
                "admin_name": "李老师",
                "admin_username": t_code,
                "admin_password": PASSWORD,
                "individual": True,
            },
        ).status_code == 200
        t_tok = client.post("/login", json={"username": t_code, "password": PASSWORD}).json()["token"]
        t_tok = client.post(
            "/change-password",
            headers={"Authorization": f"Bearer {t_tok}"},
            json={"current_password": PASSWORD, "new_password": CHANGED},
        ).json()["token"]
        t_headers = {"Authorization": f"Bearer {t_tok}"}

        sid = client.post(
            "/teacher/students",
            headers=t_headers,
            json={"name": "小华", "username": f"bs-{tag}", "password": PASSWORD, "grade": 5},
        ).json()["id"]
        pid = client.post(
            "/admin/users",
            headers=t_headers,
            json={"name": "华妈妈", "username": f"bp-{tag}", "password": PASSWORD, "role": "parent"},
        ).json()["id"]
        assert client.post(f"/teacher/students/{sid}/parent", headers=t_headers, json={"parent_id": pid}).status_code == 200
        p_tok = client.post("/login", json={"username": f"bp-{tag}", "password": PASSWORD}).json()["token"]
        p_tok = client.post(
            "/change-password",
            headers={"Authorization": f"Bearer {p_tok}"},
            json={"current_password": PASSWORD, "new_password": CHANGED},
        ).json()["token"]
        consent_token = client.post(f"/teacher/students/{sid}/ai-consent/token", headers=t_headers, json={}).json()["token"]

    port = _free_port()
    server = uvicorn.Server(uvicorn.Config(app_module.app, host="127.0.0.1", port=port, log_level="error"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    try:
        for _ in range(40):
            if server.started:
                break
            time.sleep(0.1)

        with playwright_sync.sync_playwright() as p:
            try:
                browser = p.chromium.launch(headless=True)
            except Exception as exc:
                pytest.skip(f"Chromium browser binary unavailable: {exc}")
            try:
                page = browser.new_page()
                page.goto(f"http://127.0.0.1:{port}/teacher/ai-settings", wait_until="domcontentloaded")
                page.evaluate("tok => localStorage.setItem('v717Token', tok)", t_tok)
                page.reload(wait_until="networkidle")

                page.select_option("#cy-provider", "openai_compatible")
                page.fill("#cy-base", "https://api.deepseek.com/v1")
                page.fill("#cy-model", "deepseek-chat")
                page.fill("#cy-key", "sk-browser-secret-12345678")
                page.check("#cy-allow-student")
                page.click("#cy-save")
                page.wait_for_function("() => document.getElementById('cy-msg').textContent.includes('已保存')")

                page.reload(wait_until="networkidle")
                assert page.input_value("#cy-provider") == "openai_compatible"
                assert page.is_checked("#cy-allow-student") is True

                # Parent browser confirmation and revocation
                p_page = browser.new_page()
                p_page.goto(f"http://127.0.0.1:{port}/parent/ai-consent-confirm?token={consent_token}&studentId={sid}", wait_until="domcontentloaded")
                p_page.evaluate("tok => localStorage.setItem('v717Token', tok)", p_tok)
                p_page.reload(wait_until="networkidle")
                p_page.click("#gc-confirm")
                p_page.wait_for_function("() => document.getElementById('gc-msg').textContent.includes('active')")

                p_page.click("#gc-revoke")
                p_page.wait_for_function("() => document.getElementById('gc-msg').textContent.includes('已撤回')")

                # Verify that after browser revocation, an AI student-data call triggers 0 HTTP requests
                http_calls = []
                monkeypatch.setenv("STUDENT_AI_COMPLIANCE_APPROVED", "1")
                monkeypatch.setattr(legacy.requests, "post", lambda *a, **kw: http_calls.append(a))
                with legacy.SessionLocal() as db:
                    teacher_user = db.query(legacy.User).filter(legacy.User.username == t_code).first()
                    with pytest.raises(Exception) as exc_info:
                        legacy._ai_call(db, teacher_user, "homework_help_solve", "test", student_ids=(sid,))
                    assert getattr(exc_info.value, "status_code", None) == 403
                assert len(http_calls) == 0
            finally:
                browser.close()
    finally:
        server.should_exit = True
        thread.join(timeout=5)
