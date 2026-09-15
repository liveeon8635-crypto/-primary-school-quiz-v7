from fastapi.testclient import TestClient

from app import app
from changying.web.v1 import V1_PATHS
from changying.web.v1_final_closure import (
    V1_FINAL_CLOSURE_MARKER,
    patch_v1_final_closure,
)
from changying.web.v1_membership_reliability import V1_MEMBERSHIP_RELIABILITY_MARKER


client = TestClient(app)


def final_html() -> str:
    response = client.get("/v1")
    assert response.status_code == 200
    return response.text


def test_all_v1_routes_render_after_final_closure():
    for path in V1_PATHS:
        response = client.get(path)
        assert response.status_code == 200
        assert V1_FINAL_CLOSURE_MARKER in response.text
        assert V1_MEMBERSHIP_RELIABILITY_MARKER in response.text


def test_top_level_roster_failures_no_longer_look_like_legitimate_empty_data():
    html = final_html()

    assert "学生列表读取失败：" in html
    assert "工作台读取失败：" in html
    assert "当前学生统计可能不完整" in html
    assert "不代表这些教学归属没有学生" in html


def test_unexpected_browser_read_failures_offer_a_generic_retry():
    html = final_html()

    assert "页面读取出现异常，当前显示可能不完整" in html
    assert "这不代表学生、班级或教学记录不存在" in html
    assert "data-cy-v1-retry" in html
    assert "window.addEventListener('unhandledrejection'" in html
    assert "window.addEventListener('error'" in html


def test_final_closure_patch_is_idempotent_and_does_not_add_a_second_layer():
    once = final_html()
    twice = patch_v1_final_closure(once)

    assert twice == once
    assert once.count(V1_FINAL_CLOSURE_MARKER) >= 1
