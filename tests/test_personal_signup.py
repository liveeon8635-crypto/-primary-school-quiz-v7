"""Personal free edition: self-serve signup.

A toC product cannot need an operator to open every account. This covers the
public signup path: an arithmetic challenge, per-IP rate limits, and the same
workspace creation the operator console uses. It must stay equivalent to the
operator path — one account, one student list, free forever.
"""

from __future__ import annotations

import os
import re
import sys
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PASSWORD = "Teacher1234"
CHANGED = "Teacher5678"


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    db_path = tmp_path_factory.mktemp("signup") / "app.sqlite3"
    os.environ.setdefault("DATABASE_URL", f"sqlite:///{db_path}")
    os.environ["ENABLE_DEMO_SEED"] = "0"
    os.environ.setdefault("JWT_SECRET", "signup-test-jwt-secret-0123456789abcdef")
    import app as app_module
    import app_v924 as legacy

    legacy.ensure_school_individual_column()
    legacy.PERSONAL_SIGNUP_ENABLED = True

    with TestClient(app_module.app) as c:
        yield c


@pytest.fixture(autouse=True)
def _fresh_signup_limiters(monkeypatch):
    """Each test starts with its own counters; the rate-limit test installs tight ones."""
    import app_v924 as legacy
    from changying.security.login_rate import BoundedLoginRateLimiter

    monkeypatch.setattr(legacy, "_signup_hour_limiter", BoundedLoginRateLimiter(window_seconds=3600, max_attempts=1000, max_keys=64))
    monkeypatch.setattr(legacy, "_signup_day_limiter", BoundedLoginRateLimiter(window_seconds=86400, max_attempts=1000, max_keys=64))


def _challenge(client):
    r = client.get("/signup/challenge")
    assert r.status_code == 200, r.text[:300]
    data = r.json()
    question = data["question"]
    left, right = [int(x) for x in question.replace("= ?", "").split("+")]
    return data["challengeId"], str(left + right)


def _signup(client, **overrides):
    tag = uuid.uuid4().hex[:8]
    challenge_id, answer = _challenge(client)
    payload = {
        "name": "李老师",
        "username": f"t{tag}",
        "password": PASSWORD,
        "workspace_name": f"李老师工作室{tag}",
        "contact": "13800000000",
        "challenge_id": challenge_id,
        "challenge_answer": answer,
    }
    payload.update(overrides)
    return client.post("/signup", json=payload)


def _login(client, username, password=PASSWORD):
    r = client.post("/login", json={"username": username, "password": password})
    if r.status_code == 401 and password == PASSWORD:
        r = client.post("/login", json={"username": username, "password": CHANGED})
    assert r.status_code == 200, r.text[:300]
    data = r.json()
    if data.get("mustChangePassword"):
        h = {"Authorization": "Bearer " + data["token"]}
        assert client.post("/change-password", json={"current_password": password, "new_password": CHANGED}, headers=h).status_code == 200
        data = client.post("/login", json={"username": username, "password": CHANGED}).json()
    return {"Authorization": "Bearer " + data["token"]}, data


def _inline_script(html):
    match = re.search(r"<script>([\s\S]*?)</script>", html)
    assert match, "signup page must ship one inline script"
    return match.group(1)


def test_signup_inline_script_is_valid_and_quote_safe(client):
    """The page once shipped a script broken by unescaped quotes, so every field
    showed 加载中… forever. Parse it for real when node is available."""
    import script_check

    script = _inline_script(client.get("/signup").text)
    assert 'innerHTML' not in script, "build messages with textContent, not innerHTML"
    assert '""+' not in script, "unescaped quotes would break the whole script"
    assert "msgText" in script
    # After success the form must be replaced, not left editable with a banner on top.
    page = client.get("/signup").text
    assert 'id="formView"' in page and 'id="doneView"' in page
    assert 'formView").hidden=true' in script
    script_check.assert_parses(script)


def test_signup_page_and_challenge_are_public(client):
    page = client.get("/signup")
    assert page.status_code == 200
    assert "免费注册个人工作台" in page.text
    assert 'fetch("/signup/challenge")' in page.text

    # Entry link lives in static shell markup, so it cannot change any inline script.
    shell = client.get("/v1")
    assert shell.status_code == 200
    assert 'href="/signup"' in shell.text

    # Someone who already has a workspace must be able to get to the login page.
    assert 'href="/v1"' in page.text
    assert '去登录' in page.text

    first = client.get("/signup/challenge").json()
    second = client.get("/signup/challenge").json()
    assert first["challengeId"] != second["challengeId"]
    assert "= ?" in first["question"]


def test_signup_creates_a_working_personal_workspace(client):
    r = _signup(client)
    assert r.status_code == 200, r.text[:400]
    body = r.json()
    assert body["ok"] is True
    username = body["username"]

    headers, session = _login(client, username)
    assert session["role"] == "teacher"
    assert session["schoolIndividual"] is True

    # Free forever, one student list, students without a class.
    sub = client.get("/subscription/me", headers=headers).json()
    assert sub["planCode"] == "free" and sub["canWrite"] is True and sub["periodEndsAt"] is None

    classes = client.get("/teacher/classes", headers=headers).json()
    assert len(classes) == 1 and classes[0]["name"].startswith("我的学生名单")

    r = client.post(
        "/teacher/students",
        headers=headers,
        json={"name": "小明", "username": f"stu{uuid.uuid4().hex[:8]}", "password": PASSWORD, "grade": 5},
    )
    assert r.status_code == 200, r.text[:300]
    assert client.get("/teacher/classes", headers=headers).json()[0]["studentCount"] == 1

    # The same account fills its own AI key.
    r = client.put(
        "/teacher/ai-config",
        headers=headers,
        json={"provider": "openai_compatible", "base_url": "https://api.deepseek.com/v1", "model": "deepseek-chat", "api_key": "sk-test-0123456789abcdef", "enabled": True},
    )
    assert r.status_code == 200, r.text[:300]


def test_signup_rejects_bad_input_and_replay(client):
    challenge_id, answer = _challenge(client)
    base = {"name": "王老师", "username": f"t{uuid.uuid4().hex[:8]}", "password": PASSWORD, "workspace_name": f"王老师工作室{uuid.uuid4().hex[:6]}", "challenge_id": challenge_id, "challenge_answer": answer}

    # Wrong captcha answer.
    r = client.post("/signup", json={**base, "challenge_answer": "999"})
    assert r.status_code == 400 and "验证" in r.json()["detail"]

    # The challenge is single use.
    r = client.post("/signup", json=base)
    assert r.status_code == 400 and "过期" in r.json()["detail"]

    # Weak password.
    cid, ans = _challenge(client)
    r = client.post("/signup", json={**base, "challenge_id": cid, "challenge_answer": ans, "password": "abc"})
    assert r.status_code == 400 and "密码" in r.json()["detail"]

    # Bad username characters.
    cid, ans = _challenge(client)
    r = client.post("/signup", json={**base, "challenge_id": cid, "challenge_answer": ans, "username": "李 老师"})
    assert r.status_code == 400 and "账号" in r.json()["detail"]

    # Duplicate username.
    first = _signup(client)
    assert first.status_code == 200, first.text[:300]
    taken = first.json()["username"]
    cid, ans = _challenge(client)
    r = client.post("/signup", json={**base, "challenge_id": cid, "challenge_answer": ans, "username": taken})
    assert r.status_code == 400 and "已被使用" in r.json()["detail"]


def test_signup_is_rate_limited_per_client(client, monkeypatch):
    import app_v924 as legacy
    from changying.security.login_rate import BoundedLoginRateLimiter

    monkeypatch.setattr(legacy, "_signup_hour_limiter", BoundedLoginRateLimiter(window_seconds=3600, max_attempts=2, max_keys=64))
    monkeypatch.setattr(legacy, "_signup_day_limiter", BoundedLoginRateLimiter(window_seconds=86400, max_attempts=99, max_keys=64))

    statuses = []
    for _ in range(3):
        r = _signup(client, username=f"rate{uuid.uuid4().hex[:6]}")
        statuses.append(r.status_code)
    assert statuses[0] == 200 and statuses[1] == 200, statuses
    assert statuses[2] == 429, statuses


def test_signup_can_be_switched_off(client, monkeypatch):
    import app_v924 as legacy

    monkeypatch.setattr(legacy, "PERSONAL_SIGNUP_ENABLED", False)
    assert client.get("/signup").status_code == 404
    assert client.get("/signup/challenge").status_code == 404
    challenge_id, answer = "x", "1"
    r = client.post("/signup", json={"name": "李老师", "username": f"off{uuid.uuid4().hex[:6]}", "password": PASSWORD, "workspace_name": f"关{uuid.uuid4().hex[:6]}", "challenge_id": challenge_id, "challenge_answer": answer})
    assert r.status_code == 404
