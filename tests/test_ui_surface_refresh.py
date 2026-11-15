import re

import pytest
from fastapi.testclient import TestClient

from app import app


@pytest.mark.parametrize(
    ("path", "surface"),
    [
        ("/new", "product"),
        ("/start", "personal"),
        ("/parent-accounts", "personal"),
        ("/teacher/ai-settings", "personal"),
        ("/operator-console", "operator"),
        ("/v1", "shell"),
        ("/v1/workspace", "shell"),
        ("/v1/student", "shell"),
        ("/v1/tool", "hub"),
        ("/classic?legacy=1&unified=1&from=v1&page=users", "classic"),
        ("/v1/homework", "homework"),
        ("/v1/knowledge", "weekend"),
        ("/v1/knowledge-map", "weekend"),
        ("/v1/my-knowledge-map", "weekend"),
        ("/v1/exam-prep", "weekend"),
        ("/v1/exam-paper", "weekend"),
        ("/v1/exam-report", "weekend"),
        ("/v1/weekend-plan", "weekend"),
        ("/v1/weekend-board", "board"),
        ("/v1/weekend-practice", "weekend"),
        ("/v1/classroom-board/1", "board"),
    ],
)
def test_production_route_renders_scoped_styles_without_changing_scripts(
    monkeypatch, path, surface
):
    monkeypatch.setenv("HOMEWORK_ASSISTANT", "1")
    monkeypatch.setenv("KNOWLEDGE_MAP", "1")
    monkeypatch.setenv("CHANGYING_UI_REFRESH", "1")
    with TestClient(app) as client:
        refreshed = client.get(path, follow_redirects=False)
        monkeypatch.setenv("CHANGYING_UI_REFRESH", "0")
        original = client.get(path, follow_redirects=False)

    assert refreshed.status_code == original.status_code == 200
    assert f'data-cy-ui="{surface}"' in refreshed.text
    assert refreshed.text.count('id="cy-ui-surfaces"') == 1
    assert 'id="cy-ui-surfaces"' not in original.text
    snippets = r"<script\b[^>]*>[\s\S]*?</script>"
    assert re.findall(snippets, refreshed.text) == re.findall(snippets, original.text)


def test_weekend_board_exposes_a_scrollable_keyboard_region():
    response = TestClient(app).get("/v1/weekend-board")
    assert response.status_code == 200
    assert "tabindex:'0',role:'region','aria-label':'课堂投影内容'" in response.text
    assert "body.style.overflow='auto'" in response.text
    assert "if(keepScroll)body.scrollTop=oldScroll" in response.text
