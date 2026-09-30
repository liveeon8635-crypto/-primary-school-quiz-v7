from fastapi.testclient import TestClient

from app import app


def test_feedback_center_has_deterministic_route_and_static_entry():
    home = TestClient(app).get("/v1")
    assert home.status_code == 200
    assert 'id="feedbackCenterLink"' in home.text
    assert 'href="/v1/feedback"' in home.text
    assert ">我的反馈</a>" in home.text

    page = TestClient(app).get("/v1/feedback")
    assert page.status_code == 200
    assert 'id="feedbackCenterLink"' in page.text
    assert "async function feedbackPage()" in page.text
    assert "/v1/product-feedback/mine" in page.text
    assert "取用状态" in page.text
    assert "处理回执" in page.text
    assert "奖励分" in page.text
    assert "追加反馈" in page.text
    assert "查收确认" in page.text
    assert "/follow-up" in page.text
    assert "/acknowledge" in page.text
