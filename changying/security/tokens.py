"""JWT signing helpers extracted from the legacy application.

Configuration is injected by the production loader so the existing production
secret, algorithm, and token lifetimes remain authoritative.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Callable

import jwt

from changying.security.passwords import password_version


def make_token(
    user: Any,
    security: Any,
    remember: bool = False,
    *,
    secret: str,
    algorithm: str,
    access_hours: int,
    remember_days: int,
    password_version_fn: Callable[[Any], int] = password_version,
) -> str:
    """Issue a JWT with the same claims and lifetimes as the legacy app."""
    now = datetime.now(timezone.utc)
    expiry = now + (
        timedelta(days=remember_days) if remember else timedelta(hours=access_hours)
    )
    return jwt.encode(
        {
            "sub": str(user.id),
            "role": user.role,
            "school_id": user.school_id,
            "pwdv": password_version_fn(security),
            "iat": now,
            "exp": expiry,
        },
        secret,
        algorithm=algorithm,
    )


__all__ = ["make_token"]
