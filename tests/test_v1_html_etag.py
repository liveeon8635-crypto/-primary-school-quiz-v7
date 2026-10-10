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
    assert "no-cache" in first.headers["cache-control"] and "private" in first.headers["cache-control"]
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


def test_multi_valued_headers_and_background_survive():
    from starlette.background import BackgroundTask

    app = FastAPI()
    ran = []

    @app.get("/v1/multi")
    def multi():
        r = HTMLResponse("<html>" + "x" * 50 + "</html>", headers=NO_STORE, background=BackgroundTask(lambda: ran.append(1)))
        r.raw_headers.append((b"x-multi", b"a"))
        r.raw_headers.append((b"x-multi", b"b"))
        return r

    install_v1_html_etag(app)
    res = TestClient(app).get("/v1/multi")
    assert res.headers.get_list("x-multi") == ["a", "b"]
    assert ran == [1]
    assert res.headers["content-length"] == str(len(res.content))


def test_real_app_serves_etag_through_gzip_and_compat_middleware():
    import subprocess, sys, textwrap

    code = textwrap.dedent(
        """
        from fastapi.testclient import TestClient
        from app import app

        c = TestClient(app)
        for url in ('/v1/workspace', '/classic?legacy=1&unified=1&from=v1&page=classes'):
            first = c.get(url, headers={'Accept-Encoding': 'gzip'})
            assert first.status_code == 200, url
            assert first.headers.get('content-encoding') == 'gzip', url
            etag = first.headers['etag']
            assert 'no-store' not in first.headers['cache-control']
            second = c.get(url, headers={'Accept-Encoding': 'gzip', 'If-None-Match': etag})
            assert second.status_code == 304 and second.content == b'', url
        assert 'no-store' in c.get('/v1/feedback').headers['cache-control']
        """
    )
    result = subprocess.run([sys.executable, "-c", code], text=True, capture_output=True, timeout=90)
    assert result.returncode == 0, result.stdout + result.stderr
