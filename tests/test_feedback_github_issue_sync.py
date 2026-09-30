import json
from types import SimpleNamespace
from unittest.mock import Mock

import requests

from changying.web import v1_product_assistant as assistant


def test_feedback_issue_sync_payload(monkeypatch):
    monkeypatch.setenv("CHANGYING_FEEDBACK_GITHUB_TOKEN", "test-token")
    monkeypatch.setenv("CHANGYING_FEEDBACK_GITHUB_REPO", "owner/repo")
    captured = {}

    def fake_post(url, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"number": 321, "html_url": "https://github.com/owner/repo/issues/321"}
        return response

    monkeypatch.setattr(assistant.requests, "post", fake_post)
    row = SimpleNamespace(id=77, created_at=None)
    result = assistant._sync_feedback_github_issue(
        row,
        {"message": "反馈中心希望自动同步到 Freeman 白板并跟踪处理进度", "page": "/v1/feedback"},
    )

    assert result == {"issue_number": 321, "issue_url": "https://github.com/owner/repo/issues/321"}
    assert captured["url"] == "https://api.github.com/repos/owner/repo/issues"
    assert captured["timeout"] == 4
    payload = captured["json"]
    assert payload["title"].startswith("[User Feedback] ")
    assert payload["labels"] == ["user-feedback", "need-freeman-agent"]
    assert "反馈中心希望自动同步到 Freeman 白板并跟踪处理进度" in payload["body"]
    assert "来源页面: /v1/feedback" in payload["body"]
    assert "关联反馈 ID: 77" in payload["body"]
    assert captured["headers"]["Authorization"] == "Bearer test-token"


def test_feedback_issue_sync_missing_token_degrades(monkeypatch):
    monkeypatch.delenv("CHANGYING_FEEDBACK_GITHUB_TOKEN", raising=False)
    post = Mock()
    monkeypatch.setattr(assistant.requests, "post", post)
    assert assistant._sync_feedback_github_issue(SimpleNamespace(id=78), {"message": "test"}) is None
    post.assert_not_called()


def test_feedback_issue_sync_github_failure_degrades(monkeypatch):
    monkeypatch.setenv("CHANGYING_FEEDBACK_GITHUB_TOKEN", "test-token")
    monkeypatch.setattr(
        assistant.requests,
        "post",
        Mock(side_effect=requests.Timeout("github timeout")),
    )
    assert assistant._sync_feedback_github_issue(
        SimpleNamespace(id=79, created_at=None),
        {"message": "用户反馈仍应先完成本地入库", "page": "/v1/feedback"},
    ) is None
