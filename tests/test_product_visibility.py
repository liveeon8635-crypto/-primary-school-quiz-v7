from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient

from changying.compat.legacy import (
    NO_CACHE_HEADERS,
    install_product_visibility_routes,
)
from changying.web.product_shell import PRODUCT_SHELL_MARKER


def test_product_visibility_routes_add_explicit_workbench_entries():
    app = FastAPI()
    install_product_visibility_routes(app)

    client = TestClient(app)
    for path in ("/workbench", "/new"):
        response = client.get(path)
        assert response.status_code == 200
        assert "长缨辅学" in response.text
        assert "小学托管与教学" in response.text
        assert response.headers["X-Changying-Product-UI"] == PRODUCT_SHELL_MARKER
        for header, value in NO_CACHE_HEADERS.items():
            assert response.headers[header] == value


def test_product_visibility_headers_cover_root_and_classic():
    app = FastAPI()

    @app.get("/")
    def home():
        return HTMLResponse("home")

    @app.get("/classic")
    def classic():
        return HTMLResponse("classic")

    install_product_visibility_routes(app)
    client = TestClient(app)

    for path in ("/", "/classic"):
        response = client.get(path)
        assert response.status_code == 200
        assert response.headers["X-Changying-Product-UI"] == PRODUCT_SHELL_MARKER
        for header, value in NO_CACHE_HEADERS.items():
            assert response.headers[header] == value


def test_product_visibility_install_is_idempotent():
    app = FastAPI()
    install_product_visibility_routes(app)
    install_product_visibility_routes(app)

    client = TestClient(app)
    assert client.get("/workbench").status_code == 200
    assert client.get("/new").status_code == 200

