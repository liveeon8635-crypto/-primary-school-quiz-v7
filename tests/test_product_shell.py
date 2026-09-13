from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient

from changying.web.product_shell import (
    PRODUCT_SHELL_MARKER,
    install_product_shell,
    teacher_workbench_html,
)


def test_product_shell_html_contains_brand_and_classic_entry():
    html = teacher_workbench_html()

    assert "长缨辅学" in html
    assert "教师工作台" in html
    assert "V1.1" in html
    assert PRODUCT_SHELL_MARKER == "changying_product_shell_v1_1"
    assert "/classic" in html
    assert "完整系统" in html


def test_product_shell_reads_existing_auth_and_live_dashboard_sources():
    html = teacher_workbench_html()

    assert "v717Token" in html
    assert "v717Remember" in html
    assert "v6Token" in html
    assert "/session" in html
    assert "/admin/overview" in html
    assert "/teacher/classes" in html
    assert "kpi-students" in html
    assert "classList" in html


def test_product_shell_preserves_legacy_root_at_classic():
    app = FastAPI()

    @app.get("/")
    def legacy_home():
        return HTMLResponse("legacy-home")

    install_product_shell(app)

    client = TestClient(app)
    modern = client.get("/")
    legacy = client.get("/classic")

    assert modern.status_code == 200
    assert "长缨辅学" in modern.text
    assert "教师工作台" in modern.text
    assert "v717Token" in modern.text
    assert legacy.status_code == 200
    assert legacy.text == "legacy-home"


def test_product_shell_install_is_idempotent():
    app = FastAPI()

    @app.get("/")
    def legacy_home():
        return HTMLResponse("legacy-home")

    install_product_shell(app)
    install_product_shell(app)

    client = TestClient(app)
    assert client.get("/").status_code == 200
    assert client.get("/classic").text == "legacy-home"
