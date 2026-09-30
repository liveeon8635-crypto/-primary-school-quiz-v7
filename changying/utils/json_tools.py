"""JSON compatibility helpers shared across Changying business workflows."""

from __future__ import annotations

import json
from typing import Any


def json_list(raw: Any) -> list[Any]:
    """Parse a JSON list and fail closed to an empty list for invalid/non-list input."""
    try:
        value = json.loads(raw or "[]")
        return value if isinstance(value, list) else []
    except Exception:
        return []


__all__ = ["json_list"]
