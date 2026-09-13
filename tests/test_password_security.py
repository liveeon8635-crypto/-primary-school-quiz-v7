from __future__ import annotations

from types import SimpleNamespace

from changying.security.passwords import hash_password, password_ok, password_version, verify_password


def test_password_module_preserves_scrypt_contract():
    salt = "0123456789abcdef0123456789abcdef"
    stored = hash_password("Study123", salt=salt)

    assert stored.startswith(f"scrypt${salt}$")
    assert verify_password("Study123", stored) is True
    assert verify_password("Study124", stored) is False
    assert verify_password("Study123", "broken") is False


def test_password_policy_contract():
    assert password_ok("Study123") is True
    assert password_ok("short1") is False
    assert password_ok("abcdefgh") is False
    assert password_ok("12345678") is False


def test_password_version_default_contract():
    assert password_version(SimpleNamespace(password_changed_at=None)) == 0


def test_production_loader_installs_password_helpers():
    import app_v924 as legacy
    import changying.production  # noqa: F401

    assert legacy.hash_password is hash_password
    assert legacy.verify_password is verify_password
    assert legacy.password_ok is password_ok
    assert legacy.password_version is password_version
