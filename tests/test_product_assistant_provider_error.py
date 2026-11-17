import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import HTTPException

import app_v924 as implementation


def test_image_provider_failure_logs_status_and_code_without_raw_message(monkeypatch, capsys):
    monkeypatch.setattr("changying.services.guardian_consent.require_student_ai_authorized", lambda *a, **kw: None)
    monkeypatch.setattr(implementation, "_ai_rate_check", lambda db, school_id: None)
    monkeypatch.setattr(
        implementation, "_ai_active_config",
        lambda db, school_id: (None, "openai_compatible", "https://example.invalid", "deepseek-flash", "test-key"),
    )
    response = Mock(ok=False, status_code=400)
    response.json.return_value = {"error": {"code": "invalid_request_error", "message": "private upstream detail"}}
    monkeypatch.setattr(implementation.requests, "post", lambda *args, **kwargs: response)
    db = Mock()
    user = SimpleNamespace(id=7, school_id=2)
    with pytest.raises(HTTPException) as exc:
        implementation._ai_call(db, user, "product_assistant", "what color?", images=["data:image/png;base64,AAAA"])
    assert exc.value.status_code == 502
    event = json.loads(capsys.readouterr().out.strip())
    assert event == {
        "event": "PRODUCT_ASSISTANT_IMAGE_PROVIDER_REJECTED",
        "provider": "openai_compatible",
        "upstreamStatus": 400,
        "errorCode": "invalid_request_error",
    }
    db.add.assert_called_once()
    db.commit.assert_called_once()
