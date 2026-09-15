from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient

from changying.web.entry_policy import LEGACY_ACCESS_COOKIE, install_entry_policy


def build_app():
    app = FastAPI()

    @app.get("/")
    def home():
        return HTMLResponse("product-home")

    @app.get("/v1")
    def v1():
        return HTMLResponse("v1-home")

    @app.get("/classic")
    def classic():
        return HTMLResponse("legacy-home")

    install_entry_policy(app)
    return app


def test_root_redirects_to_v1():
    client = TestClient(build_app(), follow_redirects=False)
    response = client.get("/")
    assert response.status_code == 307
    assert response.headers["location"] == "/v1"
    assert response.headers["X-Changying-Entry"] == "v1-default"


def test_stale_classic_url_redirects_to_v1():
    client = TestClient(build_app(), follow_redirects=False)
    response = client.get("/classic?page=teacher")
    assert response.status_code == 307
    assert response.headers["location"] == "/v1"


def test_classic_is_available_after_explicit_v1_transition_and_refresh():
    client = TestClient(build_app(), follow_redirects=False)
    first = client.get("/classic", headers={"referer": "https://example.test/v1/workspace"})
    assert first.status_code == 200
    assert first.text == "legacy-home"
    assert LEGACY_ACCESS_COOKIE in first.headers.get("set-cookie", "")

    refreshed = client.get("/classic?page=teacher")
    assert refreshed.status_code == 200
    assert refreshed.text == "legacy-home"


def test_classic_can_be_opened_with_explicit_legacy_marker():
    client = TestClient(build_app(), follow_redirects=False)
    response = client.get("/classic?legacy=1")
    assert response.status_code == 200
    assert response.text == "legacy-home"


def test_install_is_idempotent():
    app = build_app()
    install_entry_policy(app)
    client = TestClient(app, follow_redirects=False)
    assert client.get("/").status_code == 307
