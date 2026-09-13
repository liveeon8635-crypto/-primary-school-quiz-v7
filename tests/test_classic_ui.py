from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.testclient import TestClient

from changying.web.classic_ui import (
    CLASSIC_UI_MARKER,
    inject_classic_ui,
    install_classic_ui_patch,
    is_classic_html_path,
)


def test_classic_ui_path_detection_is_narrow():
    assert is_classic_html_path("/classic")
    assert not is_classic_html_path("/")
    assert not is_classic_html_path("/health")
    assert not is_classic_html_path("/admin/overview")


def test_inject_classic_ui_preserves_original_html_and_is_idempotent():
    html = "<html><head><title>旧系统</title></head><body><main>legacy</main></body></html>"

    once = inject_classic_ui(html)
    twice = inject_classic_ui(once)

    assert "<main>legacy</main>" in once
    assert "新版工作台" in once
    assert CLASSIC_UI_MARKER in once
    assert once == twice


def test_classic_ui_middleware_enhances_only_classic_html():
    app = FastAPI()

    @app.get("/classic")
    def classic():
        return HTMLResponse("<html><body><main>legacy-home</main></body></html>")

    @app.get("/admin/overview")
    def overview():
        return JSONResponse({"students": 2})

    install_classic_ui_patch(app)

    client = TestClient(app)
    classic_response = client.get("/classic")
    api_response = client.get("/admin/overview")

    assert classic_response.status_code == 200
    assert classic_response.headers["X-Changying-Classic-UI"] == CLASSIC_UI_MARKER
    assert "legacy-home" in classic_response.text
    assert "长缨辅学完整系统" in classic_response.text
    assert "/workbench" in classic_response.text

    assert api_response.status_code == 200
    assert api_response.json() == {"students": 2}
    assert "X-Changying-Classic-UI" not in api_response.headers


def test_classic_ui_patch_install_is_idempotent():
    app = FastAPI()

    @app.get("/classic")
    def classic():
        return HTMLResponse("<html><body>legacy</body></html>")

    install_classic_ui_patch(app)
    install_classic_ui_patch(app)

    response = TestClient(app).get("/classic")
    assert response.status_code == 200
    assert response.text.count(CLASSIC_UI_MARKER) >= 1
