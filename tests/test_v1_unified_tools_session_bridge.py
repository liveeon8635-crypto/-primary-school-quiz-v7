import subprocess
import sys
import textwrap

from changying.web.v1_unified_tools import unified_tool_html
from changying.web.v1_unified_tools_session_bridge import (
    V1_UNIFIED_SESSION_BRIDGE_MARKER,
    patch_unified_tool_session_bridge,
)


def run_isolated(code: str) -> None:
    result = subprocess.run(
        [sys.executable, "-c", textwrap.dedent(code)],
        text=True,
        capture_output=True,
        timeout=45,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_bridge_preserves_classic_hidden_state_and_copies_validated_session():
    html = patch_unified_tool_session_bridge(unified_tool_html())

    assert V1_UNIFIED_SESSION_BRIDGE_MARKER in html
    assert ".shell:not(.hidden){display:block!important" in html
    assert ".shell{display:block!important" not in html
    assert "function bridgeClassicSession(t,s)" in html
    assert "localStorage.getItem('v717Remember')==='1'" in html
    assert "const store=remember?localStorage:sessionStorage" in html
    assert "store.setItem('v717Token',t)" in html
    assert "store.setItem('v717User',JSON.stringify(legacyUser))" in html
    assert "bridgeClassicSession(t,s);role=String(s.role||'teacher')" in html


def test_bridge_actively_validates_classic_session_after_iframe_load():
    html = patch_unified_tool_session_bridge(unified_tool_html())

    assert "const doc=frame.contentDocument,win=frame.contentWindow" in html
    assert "typeof win.markNetwork==='function'" in html
    assert "win.markNetwork(true)" in html
    assert "typeof win.validateSavedSession==='function'" in html
    assert "Promise.resolve(win.validateSavedSession())" in html
    assert html.index("win.markNetwork(true)") < html.index("win.validateSavedSession()")
    assert "旧版功能登录状态尚未就绪" in html


def test_runtime_tool_html_contains_session_bridge():
    run_isolated(
        """
        from fastapi.testclient import TestClient
        from app import app
        from changying.web.v1_unified_tools_session_bridge import V1_UNIFIED_SESSION_BRIDGE_MARKER

        client = TestClient(app)
        response = client.get('/v1/tool?page=classes')
        assert response.status_code == 200
        assert V1_UNIFIED_SESSION_BRIDGE_MARKER in response.text
        assert "function bridgeClassicSession(t,s)" in response.text
        assert ".shell:not(.hidden){display:block!important" in response.text
        assert "win.markNetwork(true)" in response.text
        assert "Promise.resolve(win.validateSavedSession())" in response.text
        """
    )
