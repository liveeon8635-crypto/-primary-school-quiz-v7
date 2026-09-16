from changying.web.v1_classic_embed_bootstrap import V1_CLASSIC_EMBED_MARKER, inject_v1_classic_embed


def test_classic_embed_bootstrap_runs_inside_frame_and_reports_ready():
    html = inject_v1_classic_embed('<html><body><div class="shell hidden"></div></body></html>')
    assert V1_CLASSIC_EMBED_MARKER in html
    assert "params.get('embedded')!=='1'" in html
    assert "window.markNetwork(true)" in html
    assert "window.validateSavedSession()" in html
    assert "parent.postMessage({source:'changying-classic'" in html
    assert "html.cy-v1-embedded .sidebar" in html


def test_classic_embed_bootstrap_is_idempotent():
    first = inject_v1_classic_embed('<html><body></body></html>')
    second = inject_v1_classic_embed(first)
    assert second == first
