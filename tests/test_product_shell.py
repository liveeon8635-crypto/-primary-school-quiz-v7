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
    assert "实践工作台" in html
    assert "V1.3" in html
    assert PRODUCT_SHELL_MARKER == "changying_product_shell_v1_3"
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


def test_product_shell_v13_contains_operating_guidance():
    html = teacher_workbench_html()
    assert "今日上课路径" in html
    assert "运营体检" in html
    assert "首次使用建议" in html
    assert "STEP 01" in html
    assert "移动端快捷入口" in html


def test_product_shell_v13_frames_elementary_tutoring_scope():
    html = teacher_workbench_html()
    assert "小学阶段晚托、周末课、寒暑假班" in html
    assert "当前教学" in html
    assert "学习动态" in html
    assert "历史与衔接" in html
    assert "年级/升学衔接" in html


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
    assert "实践工作台" in modern.text
    assert "V1.3" in modern.text
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
