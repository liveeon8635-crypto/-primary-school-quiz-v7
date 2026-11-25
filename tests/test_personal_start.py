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


def test_shell_loads_an_external_home_script(client):
    """The redirect lives in an external file so inline hashes, and therefore the
    shared Safari 12 manifest, never change."""
    shell = client.get("/v1").text
    assert '<script src="/v1/personal-home.js"></script>' in shell

    # The classic shell (where个人账号 actually lands) loads the same script.
    assert '<script src="/v1/personal-home.js"></script>' in client.get("/classic?legacy=1").text

    js = client.get("/v1/personal-home.js")
    assert js.status_code == 200
    assert "application/javascript" in js.headers["content-type"]
    assert "cy_personal_home" in js.text
    assert "/start" in js.text


def test_session_marks_a_personal_browser(client):
    headers = _personal_workspace(client)
    r = client.get("/session", headers=headers)
    assert r.status_code == 200
    cookies = ";".join(r.headers.get_list("set-cookie"))
    assert "cy_personal_home=1" in cookies


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
    for href in ("/v1/weekend-plan", "/v1/weekend", "/v1/homework", "/v1/knowledge-map", "/v1/exam-prep"):
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


def test_start_page_hydrates_state_for_a_real_browser(client):
    """A browser navigates to /start without an Authorization header.

    The page therefore carries the ids the script updates and the endpoint it
    reads them from; otherwise the teacher sees "no students" forever.
    """
    page = client.get("/start").text
    assert 'id="cy-build"' in page
    assert 'id="cy-s1text"' in page and 'id="cy-s3link"' in page
    assert page.count("/start/summary") == 1
    assert page.rstrip().endswith("</html>")


def test_start_summary_refuses_anonymous_and_institution_accounts(client):
    assert client.get("/start/summary").status_code == 401

    tag = uuid.uuid4().hex[:8]
    code = f"orgs-{tag}"
    client.post(
        "/operator/schools/create",
        headers={"X-Commercial-Key": COMMERCIAL_KEY},
        json={"school_name": f"机构{tag}", "school_code": code, "admin_name": "王管理", "admin_username": code, "admin_password": PASSWORD, "plan_code": "school_basic"},
    )
    data = client.post("/login", json={"username": code, "password": PASSWORD}).json()
    headers = {"Authorization": "Bearer " + data["token"]}
    if data.get("mustChangePassword"):
        client.post("/change-password", json={"current_password": PASSWORD, "new_password": CHANGED}, headers=headers)
        data = client.post("/login", json={"username": code, "password": CHANGED}).json()
        headers = {"Authorization": "Bearer " + data["token"]}
    assert client.get("/start/summary", headers=headers).status_code == 403


def test_start_summary_follows_students_and_the_first_course(client):
    headers = _personal_workspace(client)

    data = client.get("/start/summary", headers=headers).json()
    assert data["ok"] is True
    assert data["students"] == 0 and data["has_program"] is False
    assert data["s1cls"] == "" and data["s3cls"] == ""

    created = client.post(
        "/teacher/students",
        headers=headers,
        json={"name": "小明", "username": f"stu-{uuid.uuid4().hex[:8]}", "password": PASSWORD, "grade": 5},
    )
    assert created.status_code == 200, created.text[:300]

    data = client.get("/start/summary", headers=headers).json()
    assert data["students"] == 1
    assert data["s1cls"] == "ok" and "1 名学生" in data["s1text"]

    r = client.post("/start/program", headers=headers, data={"subject": "数学"}, follow_redirects=False)
    assert r.status_code == 303

    data = client.get("/start/summary", headers=headers).json()
    assert data["has_program"] is True and data["lessons"] == 18
    assert data["s3cls"] == "ok" and data["s3url"] == "/v1/weekend-plan"
    assert "18 节课" in data["s3text"]


def test_start_stages_the_classic_handoff_before_leaving(client):
    """Clicking a classic entry from /start must hand the session over first.

    Without it, classic cannot see the V1 token in every context (another tab,
    another browser, a just-expired token) and drops the teacher on the legacy
    login page with no way back.
    """
    page = client.get("/start").text
    assert "'/v1/auth-handoff'" in page
    assert 'id="cy-link-msg"' in page

    headers = _personal_workspace(client)
    r = client.post("/v1/auth-handoff", headers=headers)
    assert r.status_code == 200
    assert "cy_v1_auth_handoff" in ";".join(r.headers.get_list("set-cookie"))


def _login_user(client, username, password=PASSWORD):
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


def test_personal_student_and_parent_cannot_escalate_or_get_personal_home_cookie(client):
    """Students and parents inside a personal workspace must keep their own role
    and home page, never act as teacher/admin or receive cy_personal_home=1."""
    teacher_headers = _personal_workspace(client)
    tag = uuid.uuid4().hex[:8]
    stu_username = f"pstu-{tag}"
    par_username = f"ppar-{tag}"

    stu_res = client.post(
        "/teacher/students",
        headers=teacher_headers,
        json={"name": "测试学生", "username": stu_username, "password": PASSWORD, "grade": 5},
    )
    assert stu_res.status_code == 200, stu_res.text[:300]

    par_res = client.post(
        "/admin/users",
        headers=teacher_headers,
        json={"name": "测试家长", "username": par_username, "password": PASSWORD, "role": "parent"},
    )
    assert par_res.status_code == 200, par_res.text[:300]

    # Personal teacher DOES get cy_personal_home=1 and it is readable by personal-home.js (not HttpOnly).
    teacher_sess = client.get("/session", headers=teacher_headers)
    assert teacher_sess.status_code == 200
    teacher_cookies = ";".join(teacher_sess.headers.get_list("set-cookie"))
    assert "cy_personal_home=1" in teacher_cookies
    assert "httponly" not in teacher_cookies.lower()

    for username, expected_role in ((stu_username, "student"), (par_username, "parent")):
        login_res, headers, payload = _login_user(client, username)
        assert payload["role"] == expected_role
        login_cookies = ";".join(login_res.headers.get_list("set-cookie"))
        assert "cy_personal_home=1" not in login_cookies
        assert "cy_personal_home=" in login_cookies  # explicitly cleared

        sess_res = client.get("/session", headers=headers)
        assert sess_res.status_code == 200
        assert sess_res.json()["role"] == expected_role
        sess_cookies = ";".join(sess_res.headers.get_list("set-cookie"))
        assert "cy_personal_home=1" not in sess_cookies

        # /start must not expose teacher studio student counts to student/parent
        start_page = client.get("/start", headers=headers).text
        assert "已经有 1 名学生" not in start_page

        # All teacher/admin/personal endpoints must reject student/parent with 403
        assert client.get("/start/summary", headers=headers).status_code == 403
        assert client.post("/start/program", headers=headers, data={"subject": "数学"}, follow_redirects=False).status_code == 403
        assert client.get("/teacher/ai-config", headers=headers).status_code == 403
        assert client.put(
            "/teacher/ai-config",
            headers=headers,
            json={"provider": "openai_responses", "base_url": "https://api.openai.com/v1", "model": "gpt-4o-mini", "api_key": "sk-bad", "enabled": True},
        ).status_code == 403
        assert client.get("/teacher/classes", headers=headers).status_code == 403
        assert client.get("/teacher/parents", headers=headers).status_code == 403
        assert client.post(
            "/admin/users",
            headers=headers,
            json={"name": "越权用户", "username": f"esc-{uuid.uuid4().hex[:8]}", "password": PASSWORD, "role": "parent"},
        ).status_code == 403


def test_start_page_utility_links_and_valid_inline_scripts(client):
    """Personal studio pages expose full-workspace/password/logout exits and ship valid ES5 JS."""
    import re
    import script_check

    start_html = client.get("/start").text
    for marker in ('href="/v1/workspace?view=all"', 'href="/v1/tool?page=account"', 'href="/v1/training"', 'id="cy-logout"'):
        assert marker in start_html

    for path in ("/start", "/parent-accounts", "/teacher/ai-settings"):
        html = client.get(path).text
        scripts = re.findall(r"<script>([\s\S]*?)</script>", html)
        assert scripts, f"{path} must include an inline script"
        for src in scripts:
            script_check.assert_parses(src)

    personal_js = client.get("/v1/personal-home.js")
    assert personal_js.status_code == 200
    script_check.assert_parses(personal_js.text)
    for marker in ("schoolIndividual", "change-password", "pushState", "个人工作室 · 全部功能", "cy-back-studio"):
        assert marker in personal_js.text
