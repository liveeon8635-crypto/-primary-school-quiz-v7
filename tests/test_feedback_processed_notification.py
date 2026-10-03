"""Feedback #308: processed feedback must surface a direct verification CTA
in the live product-assistant feedback dropdown.
"""

from fastapi.testclient import TestClient

from app import app


def test_processed_feedback_dropdown_has_direct_acceptance_cta():
    response = TestClient(app).get("/v1/workspace")
    assert response.status_code == 200
    html = response.text
    assert "canConfirm=x.canConfirm===true" in html
    assert 'data-pa-dropdown-review="' in html
    assert "已处理 · 点击去验收" in html
    assert "feedbackReviewHref(x)" in html


def test_processed_feedback_cta_preserves_followup_and_record_actions():
    response = TestClient(app).get("/v1/workspace")
    assert response.status_code == 200
    html = response.text
    assert 'data-pa-dropdown-open="' in html
    assert 'data-pa-dropdown-followup="' in html
    assert "追加反馈（可传照片）" in html
