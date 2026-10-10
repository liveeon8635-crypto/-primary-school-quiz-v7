"""Revalidate V1/Classic HTML shells with ETag/304 instead of ``no-store``.

The shells are the same for every user (identity lives in JS + storage; the
handoff cookie is only read by the POST consume endpoint), so a content hash is
a safe validator. ``private`` keeps shared proxies from storing them. ``no-cache`` keeps the old freshness: the
browser asks every time, but an unchanged ~120-150KB document answers 304.
"""

from __future__ import annotations

import hashlib
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response

# Pages whose contract (and tests) require a strict ``no-store``.
_STRICT_NO_STORE = frozenset({"/v1/feedback"})


def _is_shell_path(path: str) -> bool:
    if path in _STRICT_NO_STORE:
        return False
    return path == "/classic" or path == "/v1" or path.startswith("/v1/")


def _etag_matches(header: str, etag: str) -> bool:
    for token in header.split(","):
        token = token.strip()
        if token == "*" or token.removeprefix("W/") == etag.removeprefix("W/"):
            return True
    return False


def install_v1_html_etag(app: FastAPI) -> None:
    if getattr(app.state, "v1_html_etag_installed", False):
        return
    app.state.v1_html_etag_installed = True

    @app.middleware("http")
    async def v1_html_etag_middleware(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        response = await call_next(request)
        if request.method != "GET" or not _is_shell_path(request.url.path):
            return response
        if response.status_code != 200 or "text/html" not in response.headers.get("content-type", ""):
            return response
        if "no-store" not in response.headers.get("cache-control", "").lower():
            return response
        if "set-cookie" in response.headers or "etag" in response.headers:
            return response

        chunks: list[bytes] = []
        async for chunk in response.body_iterator:  # type: ignore[attr-defined]
            chunks.append(chunk.encode("utf-8") if isinstance(chunk, str) else chunk)
        body = b"".join(chunks)

        encoding = response.headers.get("content-encoding", "identity")
        digest = hashlib.sha256(body).hexdigest()[:32]
        etag = f'W/"{digest}-{encoding}"'

        raw = [
            (k, v)
            for k, v in response.raw_headers
            if k.lower() not in {b"content-length", b"cache-control", b"pragma", b"expires", b"vary"}
        ]
        vary = response.headers.get("vary", "")
        vary = vary if "accept-encoding" in vary.lower() else (vary + ", " if vary else "") + "Accept-Encoding"
        raw += [
            (b"cache-control", b"private, no-cache, must-revalidate, max-age=0"),
            (b"etag", etag.encode("latin-1")),
            (b"vary", vary.encode("latin-1")),
        ]

        if _etag_matches(request.headers.get("if-none-match", ""), etag):
            keep = {b"cache-control", b"etag", b"vary", b"x-changying-v1", b"x-changying-v1-tool"}
            not_modified = Response(status_code=304)
            not_modified.raw_headers = [(k, v) for k, v in raw if k.lower() in keep]
            not_modified.background = response.background
            return not_modified
        rebuilt = Response(body, status_code=200)
        rebuilt.raw_headers = raw + [(b"content-length", str(len(body)).encode("latin-1"))]
        rebuilt.background = response.background
        return rebuilt


__all__ = ["install_v1_html_etag"]
