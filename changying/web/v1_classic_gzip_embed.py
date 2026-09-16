"""Safely enhance gzip-compressed embedded Classic HTML for the V1 tool shell.

The legacy app enables GZipMiddleware before the later Classic compatibility
middleware is installed. In production that means /classic can already be gzip
encoded by the time the compatibility layer sees it, so the normal injector
intentionally leaves the body untouched. For the V1 embedded tool surface we
need the bootstrap script inside that compressed document. This narrow bridge
only handles GET /classic?embedded=1, safely decompresses, injects, and
recompresses the HTML, leaving every other response unchanged.
"""

from __future__ import annotations

import gzip
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response

from changying.web import classic_ui
from changying.web.v1_classic_embed_bootstrap import inject_v1_classic_embed

V1_CLASSIC_GZIP_EMBED_MARKER = "changying_v1_classic_gzip_embed_v1"


async def _body_bytes(response: Response) -> bytes:
    chunks: list[bytes] = []
    async for chunk in response.body_iterator:  # type: ignore[attr-defined]
        if isinstance(chunk, str):
            chunk = chunk.encode(response.charset or "utf-8")
        chunks.append(chunk)
    return b"".join(chunks)


def enhance_embedded_classic_html(html: str) -> str:
    """Apply both Classic polish and the in-frame V1 bootstrap idempotently."""
    return inject_v1_classic_embed(classic_ui.inject_classic_ui(html))


def install_v1_classic_gzip_embed(app: FastAPI) -> None:
    """Install the narrow gzip bridge needed by same-origin embedded Classic."""
    if getattr(app.state, "v1_classic_gzip_embed_installed", False):
        return

    @app.middleware("http")
    async def v1_classic_gzip_embed_middleware(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        response = await call_next(request)
        if request.method != "GET" or request.url.path != "/classic":
            return response
        if request.query_params.get("embedded") != "1":
            return response
        if response.status_code != 200:
            return response
        if "text/html" not in response.headers.get("content-type", ""):
            return response
        if response.headers.get("content-encoding", "").strip().lower() != "gzip":
            return response

        raw = await _body_bytes(response)
        headers = dict(response.headers)
        headers.pop("content-length", None)

        try:
            decoded = gzip.decompress(raw)
            charset = response.charset or "utf-8"
            html = decoded.decode(charset, errors="replace")
            enhanced = enhance_embedded_classic_html(html).encode(charset)
            payload = gzip.compress(enhanced, mtime=0)
        except (OSError, EOFError):
            # The body has already been consumed. Preserve the original payload
            # rather than turning a malformed upstream gzip response into blank HTML.
            return Response(
                raw,
                status_code=response.status_code,
                headers=headers,
                media_type="text/html",
            )

        headers["content-encoding"] = "gzip"
        headers["X-Changying-Classic-UI"] = classic_ui.CLASSIC_UI_MARKER
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
    "enhance_embedded_classic_html",
    "install_v1_classic_gzip_embed",
]
