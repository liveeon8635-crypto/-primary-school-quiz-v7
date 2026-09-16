from changying.web.v1_unified_tools import unified_tool_html
from changying.web.v1_unified_tools_session_bridge import (
    V1_UNIFIED_SESSION_BRIDGE_MARKER,
    patch_unified_tool_session_bridge,
)


def test_bridge_preserves_hidden_state_and_prepares_validated_session_handoff():
    """Keep the old iframe bridge unit-tested while it is no longer the live path."""
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


def test_runtime_no_longer_relies_on_iframe_session_bridge():
    from fastapi.testclient import TestClient
    from app import app

    response = TestClient(app, follow_redirects=False).get('/v1/tool?page=classes')
    assert response.status_code == 307
    assert response.headers['location'] == '/classic?legacy=1&unified=1&from=v1&page=classes'
