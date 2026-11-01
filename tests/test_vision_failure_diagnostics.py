"""Exercise real recognition failure handling with a fake remote HTTP response."""
import base64
import json
from types import SimpleNamespace

import pytest
import requests

from changying.services import homework_vision as vision


@pytest.mark.parametrize('mode,reason,upstream', [
    (401, 'upstream_auth', 401), (402, 'upstream_billing', 402),
    (403, 'upstream_forbidden', 403), (404, 'upstream_not_found', 404),
    (400, 'upstream_request', 400), (422, 'upstream_request', 422),
    (429, 'upstream_busy', 429), (503, 'upstream_server', 503),
    (418, 'upstream_error', 418), ('network', 'network', None),
    ('timeout', 'timeout', None), ('empty', 'empty_response', None),
    ('unreadable', 'unreadable_response', None),
])
def test_recognition_failures_keep_safe_categories_without_provider_details(monkeypatch, mode, reason, upstream):
    logs = []
    monkeypatch.setattr(vision, 'vision_config', lambda: dict(provider='openai_compatible',
        base_url='https://example.invalid/v1', model='test-model', api_key='private-key'))

    def post(*args, **kwargs):
        if mode == 'network': raise requests.ConnectionError('private-key student-answer')
        if mode == 'timeout': raise requests.Timeout('private-key student-answer')
        body = {'error': {'code': 'private-key', 'message': 'student-answer'}}
        if mode == 'empty': body = {}
        if mode == 'unreadable': body = {'content': '{}'}
        return SimpleNamespace(ok=not isinstance(mode, int), status_code=mode if isinstance(mode, int) else 200, json=lambda: body)

    monkeypatch.setattr(vision.requests, 'post', post)
    impl = SimpleNamespace(_validate_ai_base_url=lambda url, **kwargs: url,
        _ai_extract_text=lambda data: data.get('content', ''), _ai_json=json.loads,
        AIUsageLog=lambda **kwargs: SimpleNamespace(**kwargs))
    db = SimpleNamespace(add=logs.append, commit=lambda: None, rollback=lambda: None)
    image = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+j5WQAAAAASUVORK5CYII=')
    with pytest.raises(vision.VisionFailure) as caught:
        vision.recognize_image(impl, db, SimpleNamespace(id=1, school_id=1), image, feature='homework_help_written_precheck_ocr')
    failure = caught.value
    assert failure.reason == reason and failure.upstream_status == upstream
    assert failure.status_code == (504 if mode == 'timeout' else 422 if mode == 'unreadable' else 502)
    assert len(logs) == 1 and logs[0].status == 'error'
    visible = failure.detail + vision.VISION_FAILURE_MESSAGES[reason] + logs[0].error
    assert 'private-key' not in visible and 'student-answer' not in visible
