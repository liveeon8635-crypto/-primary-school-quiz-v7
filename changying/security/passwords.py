"""Password helpers extracted from the legacy application.

The algorithms and return format intentionally match the existing production
contract so stored password hashes remain fully compatible.
"""

from __future__ import annotations

import hashlib
import secrets
from typing import Any


def hash_password(password: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.scrypt(
        password.encode(),
        salt=salt.encode(),
        n=2**14,
        r=8,
        p=1,
        dklen=32,
    ).hex()
    return f"scrypt${salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algorithm, salt, digest = stored.split("$", 2)
        actual = hash_password(password, salt).split("$", 2)[2]
        return algorithm == "scrypt" and secrets.compare_digest(actual, digest)
    except Exception:
        return False


def password_ok(password: str) -> bool:
    return (
        len(password) >= 8
        and any(character.isalpha() for character in password)
        and any(character.isdigit() for character in password)
    )


def password_version(security: Any) -> int:
    changed_at = security.password_changed_at
    return int(changed_at.timestamp()) if changed_at else 0


__all__ = ["hash_password", "password_ok", "password_version", "verify_password"]
