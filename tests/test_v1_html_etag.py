from fastapi import FastAPI
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.testclient import TestClient

from changying.web.v1_html_etag import install_v1_html_etag

NO_STORE = {"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"}
state = {"body": "<html>" + "shell " * 400 + "</html>"}


def build_app() -> TestClient:
    app = FastAPI()

    @app.get("/v1/workspace")
    def shell():
        return HTMLResponse(state["body"], headers=NO_STORE)

    @app.get("/classic")
    def classic():
        return HTMLResponse(state["body"], headers=NO_STORE)

    @app.get("/other")
    def other():
        return HTMLResponse(state["body"], headers=NO_STORE)

    @app.get("/v1/data")
    def data():
        return JSONResponse({"x": 1}, headers=NO_STORE)

    app.add_middleware(GZipMiddleware, minimum_size=1)
    install_v1_html_etag(app)
    return TestClient(app)


def test_shell_gets_etag_and_revalidates_with_304():
    client = build_app()
    first = client.get("/v1/workspace")
    assert first.status_code == 200
    etag = first.headers["etag"]
    assert "no-store" not in first.headers["cache-control"]
    assert "no-cache" in first.headers["cache-control"]
    assert first.text == state["body"]

    second = client.get("/v1/workspace", headers={"If-None-Match": etag})
    assert second.status_code == 304
    assert second.content == b""
    assert second.headers["etag"] == etag


def test_changed_body_never_returns_stale_304():
    client = build_app()
    etag = client.get("/classic").headers["etag"]
    state["body"] = "<html>new build</html>"
    try:
        again = client.get("/classic", headers={"If-None-Match": etag})
        assert again.status_code == 200
        assert "new build" in again.text
        assert again.headers["etag"] != etag
    finally:
        state["body"] = "<html>" + "shell " * 400 + "</html>"


def test_gzip_and_identity_variants_have_distinct_etags():
    client = build_app()
    gz = client.get("/v1/workspace", headers={"Accept-Encoding": "gzip"})
    plain = client.get("/v1/workspace", headers={"Accept-Encoding": "identity"})
    assert gz.headers["etag"] != plain.headers["etag"]
    assert gz.headers["content-encoding"] == "gzip"
    assert gz.text == plain.text


def test_non_shell_paths_and_json_are_untouched():
    client = build_app()
    other = client.get("/other")
    assert "etag" not in other.headers and "no-store" in other.headers["cache-control"]
    data = client.get("/v1/data")
    assert "etag" not in data.headers and "no-store" in data.headers["cache-control"]
