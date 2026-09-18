import re
import subprocess

from fastapi.testclient import TestClient

from app import app
from changying.web.v1 import v1_html
from changying.web.v1_classic_unified_top import inject_v1_classic_unified
from changying.web.v1_legacy_capabilities import _LEGACY_CAPABILITIES_SNIPPET


HANDOFF_KEY = "cyV1SessionHandoff"


def _script_by_id(html: str, script_id: str) -> str:
    match = re.search(
        rf'<script id="{re.escape(script_id)}">(?P<script>.*?)</script>',
        html,
        re.S,
    )
    assert match, f"script {script_id} not found"
    return match.group("script")


def test_v1_stages_short_lived_handoff_before_tool_navigation() -> None:
    script = _script_by_id(v1_html(), "changying_v1_20260915-script")

    assert f"HANDOFF_KEY='{HANDOFF_KEY}'" in script
    assert "const cleanupToolHandoff=()" in script
    assert "cleanupToolHandoff();" in script
    assert "const stageToolHandoff=()" in script
    assert "expiresAt:Date.now()+120000" in script
    assert "a[href^=\"/v1/tool\"]" in script
    assert "if(tool)stageToolHandoff()" in script
    assert "localStorage.removeItem(HANDOFF_KEY)" in script


def test_capability_center_reads_nonremember_session_storage() -> None:
    assert "sessionStorage.getItem('v717Token')" in _LEGACY_CAPABILITIES_SNIPPET
    assert "sessionStorage.getItem('v6Token')" in _LEGACY_CAPABILITIES_SNIPPET


def test_unified_classic_consumes_only_live_handoff_and_clears_it() -> None:
    html = inject_v1_classic_unified("<html><body></body></html>")
    script = _script_by_id(html, "changying_v1_classic_unified_top_v1-script")

    assert "function v1HandoffToken()" in script
    assert f"localStorage.getItem('{HANDOFF_KEY}')" in script
    assert "Number(handoff.expiresAt||0)<=Date.now()" in script
    assert f"localStorage.removeItem('{HANDOFF_KEY}')" in script
    assert "var token=String(handoff.token);localStorage.removeItem('cyV1SessionHandoff');return token" in script
    assert "function clearV1Handoff()" in script
    assert "||v1HandoffToken()||''" in script
    assert "clearV1Handoff();sync();return true" in script


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


def test_real_app_unified_classic_response_contains_handoff_hydration() -> None:
    client = TestClient(app, follow_redirects=False)

    tool = client.get("/v1/tool?page=classes")
    assert tool.status_code == 307
    assert tool.headers["location"] == "/classic?legacy=1&unified=1&from=v1&page=classes"

    classic = client.get(
        tool.headers["location"],
        headers={"Accept-Encoding": "gzip"},
    )
    assert classic.status_code == 200
    assert "changying_v1_classic_unified_top_v1" in classic.text
    assert "function v1HandoffToken()" in classic.text
    assert HANDOFF_KEY in classic.text
    assert "fetch('/session'" in classic.text
    assert "clearV1Handoff();sync();return true" in classic.text
