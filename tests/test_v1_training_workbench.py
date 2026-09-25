from fastapi import FastAPI
from fastapi.testclient import TestClient

from changying.web.v1_training_workbench import (
    TRAINING_WORKBENCH_MARKER,
    TRAINING_WORKBENCH_PATH,
    install_v1_training_workbench_route,
    training_workbench_html,
)


def test_training_workbench_registers_cache_safe_route():
    app = FastAPI()
    install_v1_training_workbench_route(app)
    response = TestClient(app).get(TRAINING_WORKBENCH_PATH)
    assert response.status_code == 200
    assert response.headers["x-changying-v1-training"] == TRAINING_WORKBENCH_MARKER
    assert "no-store" in response.headers["cache-control"]


def test_training_workbench_is_interactive_not_static_screenshot_tutorial():
    html = training_workbench_html()
    for text in (
        "角色实操沙盒",
        "创建学生账号",
        "组卷 / 自动出题",
        "布置作业",
        "亲自体验学生端",
        "自动模拟关联数据",
        "结果与学习证据",
        "AI 针对性练习",
        "课堂复盘",
        "互动课堂与随堂检测",
        "积分与课堂评价",
        "往期教学",
        "升年级与升学衔接",
        "全部功能关系图",
    ):
        assert text in html

    assert "/v1/training-sandbox/start" in html
    assert "/v1/training-sandbox/" in html
    assert "student_submit" in html
    assert "simulate_student_submission" in html
    assert "switch_to_student" in html
    assert "return_primary_role" in html
    assert "load_scenario" in html
    assert "/v1/product-assistant/query" in html
    assert "/v1/product-feedback" in html
    assert "角色关系不清楚" in html


def test_training_workbench_supports_progress_review_and_reset_controls():
    html = training_workbench_html()
    for text in (
        "训练地图",
        "上一步",
        "跳过",
        "角色关系",
        "重做本步",
        "下一步",
        "从已布置作业开始",
        "从已有学生提交开始",
        "从课堂复盘开始",
        "清空本次实操沙盒并从头重新练习",
    ):
        assert text in html


def test_training_workbench_never_posts_to_production_business_routes():
    html = training_workbench_html()
    forbidden = (
        "fetch('/teacher/",
        'fetch("/teacher/',
        "fetch('/student/",
        'fetch("/student/',
        "fetch('/admin/",
        'fetch("/admin/',
    )
    for item in forbidden:
        assert item not in html


def test_all_roles_have_actionable_training_pages():
    html = training_workbench_html()
    for text in (
        "我的作业",
        "逐题作答",
        "我的学情",
        "我的错题",
        "家长端重点是理解孩子发生了什么",
        "家长只查看状态",
        "平台总览",
        "账号管理",
        "班级与教学归属",
        "积分规则",
        "全校审计",
        "系统设置",
    ):
        assert text in html

    for action in (
        "student_submit_self",
        "complete_student_practice",
        "admin_create_account",
        "admin_create_class",
        "admin_set_point_rule",
        "admin_set_system",
    ):
        assert action in html


def test_workbench_explains_auxiliary_pages_instead_of_falling_back_to_wrong_role_screen():
    html = training_workbench_html()
    for text in (
        "教材、教案和课件",
        "浏览题库不等于给学生布置任务",
        "班级排行用于激励",
        "套餐和功能授权",
        "AI 服务和学生数据授权边界",
        "批量导入账号和基础关系",
        "学习首页只负责汇总今天要做什么",
        "家长端重点是理解孩子发生了什么",
    ):
        assert text in html

    assert "views[step.id]||(()=>auxiliaryPage(step,'教师'" in html
    assert "adminAuxDetail(step.id)" in html


def test_training_workbench_inline_script_parses_in_node(tmp_path):
    import subprocess

    html = training_workbench_html()
    assert "<script>" in html and "</script>" in html
    script_text = html.split("<script>", 1)[1].split("</script>", 1)[0]
    script = tmp_path / "training-workbench.js"
    script.write_text(script_text, encoding="utf-8")
    checked = subprocess.run(
        ["node", "--check", str(script)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert checked.returncode == 0, checked.stderr
