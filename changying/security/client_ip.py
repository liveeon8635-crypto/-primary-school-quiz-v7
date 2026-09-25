"""Trusted client-IP resolution for Render/Cloudflare production traffic.

Render's public edge runs behind Cloudflare and forwards the true client chain.
Use the platform-provided canonical client address when available. For local/test
or non-Render paths, fall back to the rightmost valid X-Forwarded-For address,
then the ASGI peer address. This avoids trusting a caller-controlled leftmost
X-Forwarded-For entry for authentication rate-limit identity.
"""

from __future__ import annotations

from ipaddress import ip_address
from typing import Mapping, Optional


def _valid_ip(value: object) -> Optional[str]:
    raw = str(value or "").strip()
    if raw.startswith("[") and raw.endswith("]"):
        raw = raw[1:-1]
    if not raw:
        return None
    try:
        parsed = ip_address(raw)
    except ValueError:
        return None
    if parsed.version == 6 and parsed.ipv4_mapped:
        return str(parsed.ipv4_mapped)
    return str(parsed)


def trusted_client_ip(
    headers: Mapping[str, str] | None,
    peer_host: object = None,
) -> str:
    """Return the validated client identity used by auth rate limits."""

    headers = headers or {}
    canonical = _valid_ip(headers.get("cf-connecting-ip"))
    if canonical:
        return canonical

    forwarded = str(headers.get("x-forwarded-for") or "")
    for candidate in reversed(forwarded.split(",")):
        valid = _valid_ip(candidate)
        if valid:
            return valid

    return _valid_ip(peer_host) or "unknown"


__all__ = ["trusted_client_ip"]
