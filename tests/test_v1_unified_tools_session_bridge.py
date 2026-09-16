import subprocess
import sys
import textwrap

from changying.web.v1_unified_tools import unified_tool_html
from changying.web.v1_unified_tools_session_bridge import (
    V1_UNIFIED_SESSION_BRIDGE_MARKER,
    patch_unified_tool_session_bridge,
)


def run_isolated(code: str) -> None:
    result = subprocess.run([sys.executable, "-c", textwrap.dedent(code)], text=True, capture_output=True, timeout=45)
    assert result.returncode == 0, result.stdout + result.stderr


def test_bridge_preserves_hidden_state_and_prepares_validated_session_handoff():
    html = patch_unified_tool_session_bridge(unified_tool_html())
    assert V1_UNIFIED_SESSION_BRIDGE_MARKER in html
    assert ".shell:not(.hidden){display:block!important" in html
    assert ".shell{display:block!important" not in html
    assert "sessionStorage.getItem(TOKEN_KEY)" in html
    assert "function bridgeClassicSession(t,s)" in html
    assert "classicSession={token:t,user:legacyUser,remember:remember}" in html
    assert "bridgeClassicSession(t,s);role=String(s.role||'teacher')" in html


def test_parent_uses_same_origin_postmessage_handshake_for_classic_session():
    html = patch_unified_tool_session_bridge(unified_tool_html())
    assert "function sendClassicSession()" in html
    assert "frame.contentWindow.postMessage({source:'changying-v1',type:'session',session:classicSession},location.origin)" in html
    assert "data.type==='session-needed'" in html
    assert "data.source!=='changying-classic'" in html
    assert "data.type==='ready'" in html
    assert "win.markNetwork(true)" not in html
    assert "Promise.resolve(win.validateSavedSession())" not in html


def test_runtime_tool_html_contains_session_handshake():
    run_isolated(
        """
        from fastapi.testclient import TestClient
        from app import app
        from changying.web.v1_unified_tools_session_bridge import V1_UNIFIED_SESSION_BRIDGE_MARKER
        client = TestClient(app)
        response = client.get('/v1/tool?page=classes')
        assert response.status_code == 200
        assert V1_UNIFIED_SESSION_BRIDGE_MARKER in response.text
        assert "function sendClassicSession()" in response.text
        assert "data.type==='session-needed'" in response.text
        assert "source:'changying-v1'" in response.text
        """
    )
