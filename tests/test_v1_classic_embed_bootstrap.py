from changying.web.v1_classic_embed_bootstrap import V1_CLASSIC_EMBED_MARKER, inject_v1_classic_embed


def test_classic_embed_bootstrap_requests_and_hydrates_parent_session():
    html = inject_v1_classic_embed('<html><body><div class="shell hidden"></div></body></html>')
    assert V1_CLASSIC_EMBED_MARKER in html
    assert "params.get('embedded')!=='1'" in html
    assert "report('session-needed','')" in html
    assert "data.source!=='changying-v1'" in html
    assert "state.token=String(session.token)" in html
    assert "state.user=session.user" in html
    assert "state.remember=!!session.remember" in html
    assert "if(typeof saveAuth==='function')saveAuth()" in html
    assert "typeof markNetwork!=='function'" in html
    assert "Promise.resolve(validateSavedSession())" in html
    assert "parent.postMessage({source:'changying-classic'" in html
    assert "html.cy-v1-embedded .sidebar" in html


def test_classic_embed_bootstrap_is_idempotent():
    first = inject_v1_classic_embed('<html><body></body></html>')
    second = inject_v1_classic_embed(first)
    assert second == first
