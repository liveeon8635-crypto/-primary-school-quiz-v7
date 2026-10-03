"""Feedback #323: card/internal navigation must not reopen the first-login guide."""

from fastapi.testclient import TestClient

from app import app


def test_workspace_tutorial_auto_open_is_once_per_login():
    response = TestClient(app).get("/v1/workspace")
    assert response.status_code == 200
    html = response.text
    assert "const shouldAutoOpenTutorial=" in html
    assert "shownFor!==personaId" in html
    assert "shouldAutoOpenTutorial(ready,persona.id,feedbackReview,sessionShownFor())" in html


def test_internal_route_loading_does_not_clear_tutorial_marker():
    response = TestClient(app).get("/v1/workspace")
    assert response.status_code == 200
    html = response.text
    assert "if(!ready)return" in html
    assert "clearSessionShown();return" not in html
    assert "cyV1RoleTutorialShownThisLoginV7" in html
