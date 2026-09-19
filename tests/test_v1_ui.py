from fastapi import FastAPI
from fastapi.testclient import TestClient

from changying.web.v1 import V1_PATHS, V1_UI_MARKER, install_v1_routes, v1_html


def test_v1_contains_required_clickable_journey_and_product_boundaries():
    html = v1_html()

    for text in (
        "登录教学系统", "选择本次使用身份", "培训机构教学工作台", "学校教学工作台",
        "学生动态", "升年级与升学衔接", "学生连续发展档案",
        "晚托", "周末课", "寒假班", "暑假班", "今日课表", "批改/订正",
        "证据不足", "单项证据", "基础证据", "稳定证据集",
        "查看演示流程", "演示数据 · ",
    ):
        assert text in html
    assert ("往期教学 / 历史" in html) or ("往期教学" in html)
    assert "['不会','学习中','基本掌握','稳定掌握']" not in html
    assert "基本掌握（当前证据）" not in html

    for excluded in ("便利店", "健身训练", "AI 工作台", "市场化运营"):
        assert excluded not in html


def test_v1_reuses_existing_auth_and_teaching_apis():
    html = v1_html()
    for endpoint in (
        "/login", "/session", "/admin/users", "/admin/classes", "/teacher/classes",
        "/teacher/students/", "/parent/children", "/student/progress", "/student/assignments",
    ):
        assert endpoint in html


def test_v1_routes_install_without_replacing_existing_routes():
    app = FastAPI()

    @app.get("/health")
    def health():
        return {"ok": True}

    install_v1_routes(app)
    install_v1_routes(app)
    client = TestClient(app)

    assert client.get("/health").json() == {"ok": True}
    for path in V1_PATHS:
        response = client.get(path)
        assert response.status_code == 200
        assert response.headers["X-Changying-V1"] == V1_UI_MARKER
        assert "长缨辅学 V1" in response.text


def test_v1_student_workspace_uses_real_assignment_and_progress_summary():
    html = v1_html()
    assert "api('/student/assignments')" in html
    assert "api('/student/progress')" in html
    assert "studentAssignments.filter(x=>!x.completed).length" in html
    assert "studentProgress.avgScore??null" in html
    assert "assignedClassName" in html
