from fastapi import FastAPI
from fastapi.testclient import TestClient
from fastapi.responses import HTMLResponse

from changying.web.product_shell import install_product_shell, teacher_workbench_html


def test_product_shell_html_contains_brand_and_classic_entry():
    html = teacher_workbench_html()

    assert "长缨辅学" in html
    assert "教师工作台" in html
    assert "/classic" in html
    assert "完整系统" in html


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
    assert legacy.status_code == 200
    assert legacy.text == "legacy-home"
