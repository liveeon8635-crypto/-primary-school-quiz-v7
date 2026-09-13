from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import jwt

import app_v924 as legacy


def test_password_hash_and_verify_contract():
    salt = "0123456789abcdef0123456789abcdef"
    stored = legacy.hash_password("Study123", salt=salt)

    assert stored.startswith(f"scrypt${salt}$")
    assert legacy.verify_password("Study123", stored) is True
    assert legacy.verify_password("wrong-password", stored) is False
    assert legacy.verify_password("Study123", "malformed") is False


def test_password_version_uses_password_change_timestamp():
    assert legacy.password_version(SimpleNamespace(password_changed_at=None)) == 0
    changed = datetime(2026, 9, 14, 8, 30, tzinfo=timezone.utc)
    assert legacy.password_version(SimpleNamespace(password_changed_at=changed)) == int(changed.timestamp())


def _decode(token: str) -> dict:
    return jwt.decode(token, legacy.JWT_SECRET, algorithms=[legacy.JWT_ALG])


def test_access_token_claims_and_lifetime():
    user = SimpleNamespace(id=42, role="teacher", school_id=7)
    security = SimpleNamespace(password_changed_at=None)
    payload = _decode(legacy.make_token(user, security, remember=False))

    assert payload["sub"] == "42"
    assert payload["role"] == "teacher"
    assert payload["school_id"] == 7
    assert payload["pwdv"] == 0
    assert abs((payload["exp"] - payload["iat"]) - legacy.ACCESS_HOURS * 3600) <= 2


def test_remember_token_uses_day_lifetime():
    user = SimpleNamespace(id=8, role="admin", school_id=3)
    security = SimpleNamespace(password_changed_at=None)
    payload = _decode(legacy.make_token(user, security, remember=True))

    assert abs((payload["exp"] - payload["iat"]) - legacy.REMEMBER_DAYS * 86400) <= 2
