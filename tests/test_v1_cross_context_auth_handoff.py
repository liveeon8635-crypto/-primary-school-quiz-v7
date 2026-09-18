import re
import subprocess
from types import SimpleNamespace

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app import app
from changying.web.v1 import v1_html
from changying.web.v1_auth_handoff import (
    V1_AUTH_HANDOFF_COOKIE,
    V1_AUTH_HANDOFF_CONSUME_PATH,
    V1_AUTH_HANDOFF_MAX_AGE,
    V1_AUTH_HANDOFF_STAGE_PATH,
    install_v1_auth_handoff_routes,
)
from changying.web.v1_classic_unified_top import inject_v1_classic_unified
from changying.web.v1_legacy_capabilities import _LEGACY_CAPABILITIES_SNIPPET


def _script_by_id(html: str, script_id: str) -> str:
    match = re.search(
        rf'<script id="{re.escape(script_id)}">(?P<script>.*?)</script>',
        html,
        re.S,
    )
    assert match, f"script {script_id} not found"
    return match.group("script")


def test_v1_stages_server_handoff_before_context_sensitive_navigation() -> None:
    script = _script_by_id(v1_html(), "changying_v1_20260915-script")

    assert "const stageClassicHandoff=async()" in script
    assert "token==='demo'||authRemember()" not in script
    assert "token!=='demo'&&!authRemember()" not in script
    assert "fetch('/v1/auth-handoff'" in script
    assert "method:'POST'" in script
    assert "Authorization:'Bearer '+token" in script
    assert "credentials:'same-origin'" in script
    assert 'a[href^="/v1/tool"],a[href^="/classic"]' in script
    assert "openClassic('/v1/tool?page=account')" in script

    # The temporary bridge must not use script-readable persistent storage.
    assert "cyV1SessionHandoff" not in script
    assert "expiresAt:Date.now()" not in script


def test_capability_center_reads_nonremember_session_storage() -> None:
    assert "sessionStorage.getItem('v717Token')" in _LEGACY_CAPABILITIES_SNIPPET
    assert "sessionStorage.getItem('v6Token')" in _LEGACY_CAPABILITIES_SNIPPET


def test_unified_classic_consumes_server_handoff_when_storage_context_is_empty() -> None:
    html = inject_v1_classic_unified("<html><body></body></html>")
    script = _script_by_id(html, "changying_v1_classic_unified_top_v1-script")

    assert "async function consumeV1Handoff()" in script
    assert "fetch('/v1/auth-handoff/consume'" in script
    assert "method:'POST'" in script
    assert "credentials:'same-origin'" in script
    assert "params.get('from')==='v1'?await consumeV1Handoff():null" in script
    assert "bridge&&bridge.token" in script
    assert "state.token=t" in script
    assert "validateSavedSession" in script
    assert "cyV1SessionHandoff" not in script


def test_unified_top_runtime_javascript_is_valid() -> None:
    html = inject_v1_classic_unified("<html><body></body></html>")
    script = _script_by_id(html, "changying_v1_classic_unified_top_v1-script")
    result = subprocess.run(
        ["node", "--check", "-"],
        input=script,
        text=True,
        capture_output=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def _handoff_test_app() -> FastAPI:
    test_app = FastAPI()

    class User:
        id = 7
        name = "测试教师"
        role = "teacher"
        grade = None
        school_id = 3

    class Security:
        must_change_password = False

    def get_db():
        yield object()

    def authenticated_user(*, authorization, db):
        if authorization != "Bearer good-token":
            raise HTTPException(401, "登录令牌无效")
        return User()

    implementation = SimpleNamespace(
        app=test_app,
        get_db=get_db,
        authenticated_user=authenticated_user,
        security_for=lambda db, user: Security(),
        subscription_payload=lambda db, school_id: {"status": "active"},
    )
    install_v1_auth_handoff_routes(implementation)
    return test_app


def test_server_handoff_is_httponly_strict_bounded_and_one_time() -> None:
    client = TestClient(_handoff_test_app())

    staged = client.post(
        V1_AUTH_HANDOFF_STAGE_PATH,
        headers={"Authorization": "Bearer good-token"},
    )
    assert staged.status_code == 200
    assert staged.json() == {"ok": True, "expiresIn": V1_AUTH_HANDOFF_MAX_AGE}
    cookie = staged.headers["set-cookie"]
    assert V1_AUTH_HANDOFF_COOKIE in cookie
    assert "HttpOnly" in cookie
    assert "SameSite=strict" in cookie
    assert f"Max-Age={V1_AUTH_HANDOFF_MAX_AGE}" in cookie
    assert "good-token" not in staged.text
    assert staged.headers["cache-control"].startswith("no-store")

    consumed = client.post(V1_AUTH_HANDOFF_CONSUME_PATH)
    assert consumed.status_code == 200
    body = consumed.json()
    assert body["token"] == "good-token"
    assert body["role"] == "teacher"
    assert "Max-Age=0" in consumed.headers["set-cookie"]
    assert consumed.headers["cache-control"].startswith("no-store")

    second = client.post(V1_AUTH_HANDOFF_CONSUME_PATH)
    assert second.status_code == 401


def test_server_handoff_rejects_cross_site_consume() -> None:
    client = TestClient(_handoff_test_app())
    assert client.post(
        V1_AUTH_HANDOFF_STAGE_PATH,
        headers={"Authorization": "Bearer good-token"},
    ).status_code == 200

    response = client.post(
        V1_AUTH_HANDOFF_CONSUME_PATH,
        headers={"Sec-Fetch-Site": "cross-site"},
    )
    assert response.status_code == 403
    assert "Max-Age=0" in response.headers["set-cookie"]


def test_real_app_v1_and_classic_share_one_handoff_contract() -> None:
    client = TestClient(app, follow_redirects=False)

    v1 = client.get("/v1/workspace")
    assert v1.status_code == 200
    assert "fetch('/v1/auth-handoff'" in v1.text
    assert "cyV1SessionHandoff" not in v1.text
    assert "location.href='/classic'" not in v1.text

    tool = client.get("/v1/tool?page=classes")
    assert tool.status_code == 307
    assert tool.headers["location"] == "/classic?legacy=1&unified=1&from=v1&page=classes"

    classic = client.get(
        tool.headers["location"],
        headers={"Accept-Encoding": "gzip"},
    )
    assert classic.status_code == 200
    assert "changying_v1_classic_unified_top_v1" in classic.text
    assert "fetch('/v1/auth-handoff/consume'" in classic.text
    assert "fetch('/session'" in classic.text
    assert "cyV1SessionHandoff" not in classic.text


def test_server_handoff_cookie_is_secure_on_https() -> None:
    client = TestClient(_handoff_test_app(), base_url="https://example.test")
    response = client.post(
        V1_AUTH_HANDOFF_STAGE_PATH,
        headers={"Authorization": "Bearer good-token"},
    )
    assert response.status_code == 200
    cookie = response.headers["set-cookie"]
    assert "Secure" in cookie
    assert "HttpOnly" in cookie
    assert "SameSite=strict" in cookie


def test_invalid_bearer_never_creates_handoff_cookie() -> None:
    client = TestClient(_handoff_test_app())
    response = client.post(
        V1_AUTH_HANDOFF_STAGE_PATH,
        headers={"Authorization": "Bearer bad-token"},
    )
    assert response.status_code == 401
    assert V1_AUTH_HANDOFF_COOKIE not in response.headers.get("set-cookie", "")
