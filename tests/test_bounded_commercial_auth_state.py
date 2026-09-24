from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from changying.security.login_rate import BoundedLoginRateLimiter


class FakeRequest:
    def __init__(self, ip: str):
        self.headers = {}
        self.client = SimpleNamespace(host=ip)


def test_commercial_operator_uses_bounded_limiter_and_preserves_attempt_limit(monkeypatch):
    import app_v924 as legacy

    monkeypatch.setattr(legacy, "COMMERCIAL_ADMIN_KEY", "k" * 32)
    limiter = BoundedLoginRateLimiter(
        window_seconds=legacy.COMMERCIAL_AUTH_WINDOW_SECONDS,
        max_attempts=legacy.COMMERCIAL_AUTH_MAX_ATTEMPTS,
        max_keys=32,
    )
    monkeypatch.setattr(legacy, "_commercial_auth_limiter", limiter)

    request = FakeRequest("203.0.113.10")
    for _ in range(legacy.COMMERCIAL_AUTH_MAX_ATTEMPTS):
        with pytest.raises(HTTPException) as exc:
            legacy.commercial_operator(request, "wrong-key")
        assert exc.value.status_code == 403

    with pytest.raises(HTTPException) as exc:
        legacy.commercial_operator(request, "wrong-key")
    assert exc.value.status_code == 429

    assert legacy.commercial_operator(FakeRequest("203.0.113.11"), "k" * 32) is True


def test_production_commercial_auth_tracker_has_a_fixed_client_capacity():
    import app_v924 as legacy

    assert not hasattr(legacy, "_commercial_auth_failures")
    assert legacy.COMMERCIAL_AUTH_MAX_CLIENTS == 512
    assert legacy._commercial_auth_limiter.max_keys == 512
