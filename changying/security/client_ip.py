"""Trusted client-IP resolution for Render/Cloudflare production traffic.

Render's public edge runs behind Cloudflare and forwards the true client chain from
its own internal network (a private address space). Forwarding headers are therefore
only honoured when the direct peer is a trusted proxy; a request that reaches the
process from a public peer address keeps that peer address as its identity, so a
caller cannot mint a fresh rate-limit key per request by inventing
``CF-Connecting-IP`` / ``X-Forwarded-For`` values.

Deployments with a custom proxy topology can extend the trusted peer list with
``TRUSTED_PROXY_CIDRS`` (comma-separated CIDR blocks).
"""

from __future__ import annotations

import os
from ipaddress import ip_address, ip_network
from typing import Mapping, Optional

_TRUSTED_PROXY_CIDRS = (
    "127.0.0.0/8",
    "10.0.0.0/8",
    "172.16.0.0/12",
    "192.168.0.0/16",
    "::1/128",
    "fc00::/7",
)


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


def _trusted_networks():
    configured = str(os.getenv("TRUSTED_PROXY_CIDRS") or "")
    raw_items = [item.strip() for item in configured.split(",") if item.strip()]
    nets = []
    for item in (raw_items or list(_TRUSTED_PROXY_CIDRS)):
        try:
            nets.append(ip_network(item, strict=False))
        except ValueError:
            continue
    return nets


def _peer_is_trusted(peer: Optional[str]) -> bool:
    if not peer:
        return False
    try:
        address = ip_address(peer)
    except ValueError:
        return False
    for network in _trusted_networks():
        if address.version == network.version and address in network:
            return True
    return False


def trusted_client_ip(
    headers: Mapping[str, str] | None,
    peer_host: object = None,
) -> str:
    """Return the validated client identity used by auth rate limits."""

    headers = headers or {}
    peer = _valid_ip(peer_host)
    if not _peer_is_trusted(peer):
        # A direct (non-proxy) caller cannot be allowed to choose its own identity.
        return peer or "unknown"

    canonical = _valid_ip(headers.get("cf-connecting-ip"))
    if canonical:
        return canonical

    forwarded = str(headers.get("x-forwarded-for") or "")
    for candidate in reversed(forwarded.split(",")):
        valid = _valid_ip(candidate)
        if valid:
            return valid

    return peer or "unknown"


__all__ = ["trusted_client_ip"]
