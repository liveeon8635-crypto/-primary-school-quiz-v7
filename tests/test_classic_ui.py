from fastapi import FastAPI
from fastapi.middleware.gzip import GZipMiddleware
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
    assert "长缨辅学 V1" in once
    assert "今日教学快捷入口" in once
    assert "学生管理" in once
    assert "题库组卷" in once
    assert "成绩分析" in once
    assert "data-cy-action" in once
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
    assert "长缨辅学教学系统" in classic_response.text
    assert "今日教学快捷入口" in classic_response.text
    assert "/v1" in classic_response.text

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

def test_classic_ui_middleware_preserves_gzip_encoded_html():
    app = FastAPI()

    @app.get("/classic")
    def classic():
        return HTMLResponse("<html><body><main>legacy-compressed</main></body></html>")

    app.add_middleware(GZipMiddleware, minimum_size=1)
    install_classic_ui_patch(app)

    response = TestClient(app).get("/classic", headers={"Accept-Encoding": "gzip"})

    assert response.status_code == 200
    assert response.headers["content-encoding"] == "gzip"
    assert "legacy-compressed" in response.text
    assert "X-Changying-Classic-UI" not in response.headers

