"""Safely enhance Classic HTML for V1 integration.

The legacy app enables GZipMiddleware before later compatibility middleware is
installed, so Classic HTML can already be gzip encoded when the V1 layer sees
it.  This bridge handles both the older iframe embed mode and the reliable
same-tab unified mode.

The same-tab mode intentionally redirects ``/v1/tool`` to Classic as the
*top-level* document.  That preserves Classic's existing sessionStorage and auth
lifecycle on iPhone Safari while still injecting the V1 navigation chrome.
"""
from __future__ import annotations

import gzip
from collections.abc import Awaitable, Callable
from urllib.parse import quote

from fastapi import FastAPI, Request, Response
from fastapi.responses import RedirectResponse

from changying.web import classic_ui
from changying.web.v1_classic_embed_bootstrap import inject_v1_classic_embed
from changying.web.v1_classic_unified_top import (
    V1_CLASSIC_UNIFIED_MARKER,
    inject_v1_classic_unified,
)

V1_CLASSIC_GZIP_EMBED_MARKER = "changying_v1_classic_gzip_embed_v1"
V1_CLASSIC_TOP_LEVEL_MARKER = "changying_v1_classic_top_level_v1"

_ALLOWED_TOOL_PAGES = frozenset(
    {
        "classes",
        "classPoints",
        "ai",
        "teaching",
        "resources",
        "catalog",
        "papers",
        "analytics",
        "audit",
        "leaderboard",
        "account",
        "syncLearning",
        "rewards",
        "assignments",
        "wrongbook",
        "practice",
        "progress",
        "childLearning",
        "childRewards",
        "childProgress",
        "childAssignments",
        "admin",
        "subscription",
        "users",
        "pointsAdmin",
        "imports",
        "adminAudit",
        "system",
    }
)


async def _body_bytes(response: Response) -> bytes:
    chunks: list[bytes] = []
    async for chunk in response.body_iterator:  # type: ignore[attr-defined]
        if isinstance(chunk, str):
            chunk = chunk.encode(response.charset or "utf-8")
        chunks.append(chunk)
    return b"".join(chunks)


def _safe_tool_page(raw: str | None) -> str:
    page = str(raw or "").strip()
    return page if page in _ALLOWED_TOOL_PAGES else "classes"


def _unified_tool_url(page: str) -> str:
    return "/classic?legacy=1&unified=1&from=v1&page=" + quote(page, safe="")


def enhance_embedded_classic_html(html: str) -> str:
    """Apply both Classic polish and the in-frame V1 bootstrap idempotently."""
    return inject_v1_classic_embed(classic_ui.inject_classic_ui(html))


def enhance_unified_classic_html(html: str) -> str:
    """Apply Classic polish plus top-level V1 navigation chrome."""
    return inject_v1_classic_unified(classic_ui.inject_classic_ui(html))


def install_v1_classic_gzip_embed(app: FastAPI) -> None:
    """Install Classic integration for iframe compatibility and top-level V1 use."""
    if getattr(app.state, "v1_classic_gzip_embed_installed", False):
        return

    @app.middleware("http")
    async def v1_classic_gzip_embed_middleware(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        # The iframe approach repeatedly failed on iPhone Safari because the
        # legacy app stores auth in a browsing-context-scoped sessionStorage.
        # Keep the public V1 URL stable but move the mature workflow into the
        # same top-level browsing context, where the existing auth lifecycle is
        # already proven.
        if request.method == "GET" and request.url.path == "/v1/tool":
            page = _safe_tool_page(request.query_params.get("page"))
            return RedirectResponse(
                _unified_tool_url(page),
                status_code=307,
                headers={
                    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                    "X-Changying-V1-Tool": V1_CLASSIC_TOP_LEVEL_MARKER,
                },
            )

        # Old V1 capability links can still point directly at Classic.  Normalize
        # every V1-originated top-level Classic navigation through unified mode
        # so the one-time auth handoff is always consumed before Classic renders.
        if (
            request.method == "GET"
            and request.url.path == "/classic"
            and request.query_params.get("from") == "v1"
            and request.query_params.get("unified") != "1"
            and request.query_params.get("embedded") != "1"
        ):
            page = _safe_tool_page(request.query_params.get("page"))
            return RedirectResponse(
                _unified_tool_url(page),
                status_code=307,
                headers={
                    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                    "X-Changying-V1-Tool": V1_CLASSIC_TOP_LEVEL_MARKER,
                },
            )

        response = await call_next(request)
        if request.method != "GET" or request.url.path != "/classic":
            return response

        embedded = request.query_params.get("embedded") == "1"
        unified = request.query_params.get("unified") == "1"
        if not embedded and not unified:
            return response
        if response.status_code != 200:
            return response
        if "text/html" not in response.headers.get("content-type", ""):
            return response

        content_encoding = response.headers.get("content-encoding", "").strip().lower()
        if content_encoding not in {"", "identity", "gzip"}:
            return response

        raw = await _body_bytes(response)
        headers = dict(response.headers)
        headers.pop("content-length", None)
        charset = response.charset or "utf-8"

        try:
            decoded = gzip.decompress(raw) if content_encoding == "gzip" else raw
            html = decoded.decode(charset, errors="replace")
            enhanced = (
                enhance_unified_classic_html(html)
                if unified
                else enhance_embedded_classic_html(html)
            ).encode(charset)
            payload = gzip.compress(enhanced, mtime=0) if content_encoding == "gzip" else enhanced
        except (OSError, EOFError):
            return Response(
                raw,
                status_code=response.status_code,
                headers=headers,
                media_type="text/html",
            )

        if content_encoding == "gzip":
            headers["content-encoding"] = "gzip"
        else:
            headers.pop("content-encoding", None)
        headers["X-Changying-Classic-UI"] = classic_ui.CLASSIC_UI_MARKER
        if unified:
            headers["X-Changying-V1-Classic-Unified"] = V1_CLASSIC_UNIFIED_MARKER
        else:
            headers["X-Changying-V1-Classic-Embed"] = V1_CLASSIC_GZIP_EMBED_MARKER

        return Response(
            payload,
            status_code=response.status_code,
            headers=headers,
            media_type="text/html",
        )

    app.state.v1_classic_gzip_embed_installed = True


__all__ = [
    "V1_CLASSIC_GZIP_EMBED_MARKER",
    "V1_CLASSIC_TOP_LEVEL_MARKER",
    "enhance_embedded_classic_html",
    "enhance_unified_classic_html",
    "install_v1_classic_gzip_embed",
]
