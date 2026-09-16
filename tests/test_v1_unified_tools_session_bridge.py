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


def test_bridge_preserves_classic_hidden_state_and_copies_validated_session():
    html = patch_unified_tool_session_bridge(unified_tool_html())
    assert V1_UNIFIED_SESSION_BRIDGE_MARKER in html
    assert ".shell:not(.hidden){display:block!important" in html
    assert ".shell{display:block!important" not in html
    assert "function bridgeClassicSession(t,s)" in html
    assert "const store=remember?localStorage:sessionStorage" in html
    assert "store.setItem('v717Token',t)" in html
    assert "store.setItem('v717User',JSON.stringify(legacyUser))" in html
    assert "bridgeClassicSession(t,s);role=String(s.role||'teacher')" in html


def test_parent_waits_for_classic_readiness_message_without_direct_iframe_calls():
    html = patch_unified_tool_session_bridge(unified_tool_html())
    assert "window.addEventListener('message',event=>" in html
    assert "data.source!=='changying-classic'" in html
    assert "data.type==='ready'" in html
    assert "win.markNetwork(true)" not in html
    assert "Promise.resolve(win.validateSavedSession())" not in html


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
        assert "window.addEventListener('message',event=>" in response.text
        """
    )
