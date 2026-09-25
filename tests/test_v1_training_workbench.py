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
