from __future__ import annotations

from types import SimpleNamespace

import jwt

from changying.security.tokens import make_token


def test_extracted_signer_preserves_claims_and_access_lifetime():
    user = SimpleNamespace(id=11, role="teacher", school_id=5)
    security = SimpleNamespace(password_changed_at=None)
    token = make_token(
        user,
        security,
        False,
        secret="unit-test-secret",
        algorithm="HS256",
        access_hours=12,
        remember_days=30,
    )
    payload = jwt.decode(token, "unit-test-secret", algorithms=["HS256"])

    assert payload["sub"] == "11"
    assert payload["role"] == "teacher"
    assert payload["school_id"] == 5
    assert payload["pwdv"] == 0
    assert abs((payload["exp"] - payload["iat"]) - 12 * 3600) <= 2


def test_extracted_signer_preserves_remember_lifetime():
    user = SimpleNamespace(id=12, role="admin", school_id=5)
    security = SimpleNamespace(password_changed_at=None)
    token = make_token(
        user,
        security,
        True,
        secret="unit-test-secret",
        algorithm="HS256",
        access_hours=12,
        remember_days=30,
    )
    payload = jwt.decode(token, "unit-test-secret", algorithms=["HS256"])

    assert abs((payload["exp"] - payload["iat"]) - 30 * 86400) <= 2


def test_production_wrapper_uses_existing_legacy_jwt_configuration():
    import app_v924 as legacy
    import changying.production  # noqa: F401 - installs runtime compatibility hooks

    user = SimpleNamespace(id=13, role="student", school_id=2)
    security = SimpleNamespace(password_changed_at=None)
    payload = jwt.decode(
        legacy.make_token(user, security, remember=False),
        legacy.JWT_SECRET,
        algorithms=[legacy.JWT_ALG],
    )

    assert payload["sub"] == "13"
    assert payload["role"] == "student"
    assert payload["school_id"] == 2
    assert abs((payload["exp"] - payload["iat"]) - legacy.ACCESS_HOURS * 3600) <= 2
