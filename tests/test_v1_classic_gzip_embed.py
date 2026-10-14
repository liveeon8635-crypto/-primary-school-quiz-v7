from fastapi import FastAPI
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient

from changying.web.classic_ui import CLASSIC_UI_MARKER, install_classic_ui_patch
from changying.web.v1_classic_embed_bootstrap import V1_CLASSIC_EMBED_MARKER
from changying.web.v1_classic_gzip_embed import (
    V1_CLASSIC_GZIP_EMBED_MARKER,
    V1_CLASSIC_TOP_LEVEL_MARKER,
    install_v1_classic_gzip_embed,
)
from changying.web.v1_classic_unified_top import V1_CLASSIC_UNIFIED_MARKER


def build_app() -> FastAPI:
    app = FastAPI()

    @app.get('/classic')
    def classic():
        return HTMLResponse('<html><body><main>legacy-tool</main></body></html>')

    @app.get('/v1/tool')
    def old_tool_shell():
        return HTMLResponse('<html><body>old-iframe-shell</body></html>')

    app.add_middleware(GZipMiddleware, minimum_size=1)
    install_classic_ui_patch(app)
    install_v1_classic_gzip_embed(app)
    return app


def test_embedded_classic_is_enhanced_even_when_upstream_is_gzipped():
    response = TestClient(build_app()).get(
        '/classic?legacy=1&embedded=1&from=v1&page=ai',
        headers={'Accept-Encoding': 'gzip'},
    )

    assert response.status_code == 200
    assert response.headers['content-encoding'] == 'gzip'
    assert response.headers['X-Changying-Classic-UI'] == CLASSIC_UI_MARKER
    assert response.headers['X-Changying-V1-Classic-Embed'] == V1_CLASSIC_GZIP_EMBED_MARKER
    assert 'legacy-tool' in response.text
    assert CLASSIC_UI_MARKER in response.text
    assert V1_CLASSIC_EMBED_MARKER in response.text
    assert "params.get('embedded')!=='1'" in response.text
    assert 'validateSavedSession' in response.text
    assert 'changying-classic' in response.text


def test_v1_tool_redirects_to_same_tab_unified_classic():
    response = TestClient(build_app(), follow_redirects=False).get('/v1/tool?page=ai')

    assert response.status_code == 307
    assert response.headers['X-Changying-V1-Tool'] == V1_CLASSIC_TOP_LEVEL_MARKER
    assert response.headers['location'] == '/classic?legacy=1&unified=1&from=v1&page=ai'




def test_v1_tool_without_page_is_native_v1_hub_not_classic_redirect():
    from changying.web.v1_classic_gzip_embed import _ALLOWED_TOOL_PAGES
    from changying.web.v1_tool_hub import TOOL_HUB_MENUS, V1_TOOL_HUB_MARKER

    client = TestClient(build_app(), follow_redirects=False)
    for url in ('/v1/tool', '/v1/tool?page=__hub__'):
        response = client.get(url)
        assert response.status_code == 200
        assert response.headers['X-Changying-V1-Tool'] == V1_TOOL_HUB_MARKER
        assert 'no-store' in response.headers['Cache-Control']
        assert '全部功能' in response.text
        assert "'/v1/tool?page='" in response.text
        assert "/v1/auth-handoff" in response.text

    # Every card must open a page the redirect actually allows.
    for items in TOOL_HUB_MENUS.values():
        assert {page for page, *_ in items} <= _ALLOWED_TOOL_PAGES


def test_unknown_tool_page_is_safely_normalized():
    response = TestClient(build_app(), follow_redirects=False).get('/v1/tool?page=not-a-real-page')

    assert response.status_code == 307
    assert response.headers['location'].endswith('page=classes')


def test_direct_v1_classic_link_is_normalized_through_unified_mode():
    response = TestClient(build_app(), follow_redirects=False).get(
        '/classic?legacy=1&page=assignments&from=v1'
    )

    assert response.status_code == 307
    assert response.headers['X-Changying-V1-Tool'] == V1_CLASSIC_TOP_LEVEL_MARKER
    assert response.headers['location'] == '/classic?legacy=1&unified=1&from=v1&page=assignments'


def test_unified_classic_gets_v1_chrome_even_when_upstream_is_gzipped():
    response = TestClient(build_app()).get(
        '/classic?legacy=1&unified=1&from=v1&page=classes',
        headers={'Accept-Encoding': 'gzip'},
    )

    assert response.status_code == 200
    assert response.headers['content-encoding'] == 'gzip'
    assert response.headers['X-Changying-Classic-UI'] == CLASSIC_UI_MARKER
    assert response.headers['X-Changying-V1-Classic-Unified'] == V1_CLASSIC_UNIFIED_MARKER
    assert 'legacy-tool' in response.text
    assert V1_CLASSIC_UNIFIED_MARKER in response.text
    assert "params.get('unified')!=='1'" in response.text
    assert 'cy-v1-unified-picker' in response.text
    assert '/v1/workspace' in response.text
    assert '/v1/workspace?view=all' in response.text
    assert '班级学生' in response.text
    assert 'function autoResume()' in response.text
    assert "document.getElementById('continueSessionBtn')" in response.text
    assert "if(typeof markNetwork==='function')markNetwork(true)" in response.text
    assert 'btn.click()' in response.text
    assert '--cy-v1-navy:#a8101c' in response.text
    assert '--cy-v1-line:#eadfd8' in response.text
    assert 'background:#f3f6fb!important' in response.text
    assert 'border-radius:18px!important' in response.text
    assert 'background:var(--cy-v1-navy)!important' in response.text


def test_non_embedded_gzip_classic_keeps_existing_behavior():
    response = TestClient(build_app()).get(
        '/classic',
        headers={'Accept-Encoding': 'gzip'},
    )

    assert response.status_code == 200
    assert response.headers['content-encoding'] == 'gzip'
    assert 'legacy-tool' in response.text
    assert 'X-Changying-V1-Classic-Embed' not in response.headers
    assert 'X-Changying-V1-Classic-Unified' not in response.headers
