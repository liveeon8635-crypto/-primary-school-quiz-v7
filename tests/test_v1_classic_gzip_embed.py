from fastapi import FastAPI
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient

from changying.web.classic_ui import CLASSIC_UI_MARKER, install_classic_ui_patch
from changying.web.v1_classic_embed_bootstrap import V1_CLASSIC_EMBED_MARKER
from changying.web.v1_classic_gzip_embed import (
    V1_CLASSIC_GZIP_EMBED_MARKER,
    install_v1_classic_gzip_embed,
)


def build_app() -> FastAPI:
    app = FastAPI()

    @app.get('/classic')
    def classic():
        return HTMLResponse('<html><body><main>legacy-tool</main></body></html>')

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


def test_non_embedded_gzip_classic_keeps_existing_behavior():
    response = TestClient(build_app()).get(
        '/classic',
        headers={'Accept-Encoding': 'gzip'},
    )

    assert response.status_code == 200
    assert response.headers['content-encoding'] == 'gzip'
    assert 'legacy-tool' in response.text
    assert 'X-Changying-V1-Classic-Embed' not in response.headers
