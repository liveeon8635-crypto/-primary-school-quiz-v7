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
    assert "小学托管与教学" in html
    assert "日常托管" in html
    assert PRODUCT_SHELL_MARKER == "changying_product_shell_v1_3"
    assert "/classic" in html
    assert "进入教学系统" in html


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


def test_product_shell_v13_contains_operating_guidance():
    html = teacher_workbench_html()

    assert "今日教学安排" in html
    assert "教学概览" in html
    assert "使用指引" in html
    assert "STEP 01" in html
    assert "移动端快捷入口" in html


def test_product_shell_focuses_on_primary_school_teaching():
    html = teacher_workbench_html()
    for label in ("日常托管", "周末教学", "寒暑假班", "学校教学支持"):
        assert label in html
    for label in ("AI 与市场化", "AI 对接", "经营", "训练", "实践体系", "只读上线策略", "公众号获客", "会员服务"):
        assert label not in html


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
    assert "小学托管与教学" in modern.text
    assert "日常托管" in modern.text
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

