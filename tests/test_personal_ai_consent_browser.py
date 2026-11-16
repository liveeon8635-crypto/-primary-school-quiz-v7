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


def test_real_browser_homework_notice_parse_flow(tmp_path, monkeypatch):
    import json
    from types import SimpleNamespace
    playwright_sync = pytest.importorskip("playwright.sync_api")

    db_path = tmp_path / "hw_browser.sqlite3"
    os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"
    os.environ["ENABLE_DEMO_SEED"] = "0"
    os.environ["HOMEWORK_ASSISTANT"] = "1"
    os.environ.setdefault("JWT_SECRET", "browser-hw-jwt-secret-0123456789abcdef")

    import app as app_module
    import app_v924 as legacy

    legacy.COMMERCIAL_ADMIN_KEY = COMMERCIAL_KEY
    monkeypatch.setattr(legacy, "_validate_ai_base_url", lambda base, runtime=False: base)
    http_calls = []

    def fake_post(url, *args, **kwargs):
        http_calls.append(kwargs.get("json"))
        return SimpleNamespace(
            ok=True,
            status_code=200,
            json=lambda: {
                "choices": [{
                    "message": {
                        "content": json.dumps({
                            "groupLabel": "五年级1班",
                            "items": [{"subject": "数学", "content": "第5页练习", "page": "P5", "requirement": "订正"}],
                        }, ensure_ascii=False)
                    }
                }]
            },
        )

    monkeypatch.setattr(legacy.requests, "post", fake_post)

    with TestClient(app_module.app) as client:
        tag = uuid.uuid4().hex[:8]
        code = f"hwb-{tag}"
        assert client.post(
            "/operator/schools/create",
            headers={"X-Commercial-Key": COMMERCIAL_KEY},
            json={
                "school_name": f"晚托浏览器测试{tag}",
                "school_code": code,
                "admin_name": "校长",
                "admin_username": code,
                "admin_password": PASSWORD,
                "individual": False,
            },
        ).status_code == 200
        adm_tok = client.post("/login", json={"username": code, "password": PASSWORD}).json()["token"]
        adm_tok = client.post("/change-password", headers={"Authorization": f"Bearer {adm_tok}"}, json={"current_password": PASSWORD, "new_password": CHANGED}).json()["token"]
        adm_h = {"Authorization": f"Bearer {adm_tok}"}
        tid = client.post("/admin/users", headers=adm_h, json={"name": "林老师", "username": f"ht-{tag}", "password": PASSWORD, "role": "teacher"}).json()["id"]
        with legacy.SessionLocal() as db:
            t_u = db.get(legacy.User, tid)
            cls = legacy.SchoolClass(school_id=t_u.school_id, name="五年级1班", grade=5, teacher_id=tid)
            db.add(cls)
            db.commit()
            cls_id = cls.id
            cfg = legacy.ai_config_for(db, t_u.school_id, True)
            cfg.enabled = True
            cfg.allow_student_data = True
            cfg.provider = "openai_compatible"
            cfg.base_url = "https://api.deepseek.com/v1"
            cfg.model = "deepseek-chat"
            cfg.api_key_cipher = legacy._ai_encrypt_key("sk-browser-hw-key")
            db.commit()
        t_tok = client.post("/login", json={"username": f"ht-{tag}", "password": PASSWORD}).json()["token"]
        t_tok = client.post("/change-password", headers={"Authorization": f"Bearer {t_tok}"}, json={"current_password": PASSWORD, "new_password": CHANGED}).json()["token"]
        sid = client.post("/teacher/students", headers={"Authorization": f"Bearer {t_tok}"}, json={"name": "小明", "username": f"hs-{tag}", "password": PASSWORD, "grade": 5, "class_id": cls_id}).json()["id"]

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
            browser = p.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                seen_parse_bodies = []
                page.on("request", lambda req: seen_parse_bodies.append(req.post_data_json) if req.url.endswith("/teacher/homework/parse") else None)
                page.goto(f"http://127.0.0.1:{port}/v1/homework", wait_until="domcontentloaded")
                page.evaluate("tok => localStorage.setItem('v717Token', tok)", t_tok)
                page.reload(wait_until="networkidle")

                page.wait_for_selector("input[type='checkbox']")
                page.fill("textarea", "学生姓名：张小明 学号：20260105 成绩：58分 13812345678 明天完成数学第5页")
                page.click("button:has-text('AI 解析')")
                page.wait_for_selector("button:has-text('发布给选中的学生')")

                assert len(seen_parse_bodies) == 1
                assert seen_parse_bodies[0]["studentIds"] == [sid]
                assert len(http_calls) == 1
                sent_prompt = json.dumps(http_calls[0], ensure_ascii=False)
                for secret in ("张小明", "20260105", "58分", "13812345678"):
                    assert secret not in sent_prompt

                # Uncheck student scope -> parse MUST be blocked (0 new HTTP)
                page.uncheck("input[type='checkbox']")
                page.click("button:has-text('AI 解析')")
                page.wait_for_function("() => document.body.textContent.includes('禁止向外部 AI 发送')")
                assert len(http_calls) == 1
            finally:
                browser.close()
    finally:
        server.should_exit = True
        thread.join(timeout=5)
