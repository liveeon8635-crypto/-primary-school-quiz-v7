"""Production entry policy for 长缨辅学.

V1 is the default product surface. The legacy teaching system remains available,
but only after an explicit transition from V1 (or an explicit ``legacy=1`` URL).
A short-lived, HTTP-only cookie keeps refreshes inside the legacy system after
that explicit transition without turning stale classic bookmarks into the
product default again.
"""

from __future__ import annotations

from urllib.parse import urlsplit

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse, Response

V1_ENTRY = "/v1"
LEGACY_PATH = "/classic"
LEGACY_ACCESS_COOKIE = "cy_legacy_access"
LEGACY_ACCESS_MAX_AGE = 30 * 60


def _came_from_v1(request: Request) -> bool:
    referer = request.headers.get("referer", "")
    if not referer:
        return False
    try:
        return urlsplit(referer).path.startswith("/v1")
    except ValueError:
        return False


def _legacy_access_explicit(request: Request) -> bool:
    return (
        request.query_params.get("legacy") == "1"
        or request.cookies.get(LEGACY_ACCESS_COOKIE) == "1"
        or _came_from_v1(request)
    )


def _redirect_to_v1() -> RedirectResponse:
    return RedirectResponse(
        V1_ENTRY,
        status_code=307,
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
            "X-Changying-Entry": "v1-default",
        },
    )


def install_entry_policy(app: FastAPI) -> None:
    """Make V1 the default entry and require an explicit transition to classic."""
    if getattr(app.state, "entry_policy_installed", False):
        return

    @app.middleware("http")
    async def entry_policy(request: Request, call_next) -> Response:
        path = request.url.path
        if request.method == "GET" and path == "/":
            return _redirect_to_v1()

        if request.method == "GET" and path == LEGACY_PATH:
            if not _legacy_access_explicit(request):
                return _redirect_to_v1()

            response = await call_next(request)
            if request.cookies.get(LEGACY_ACCESS_COOKIE) != "1":
                response.set_cookie(
                    LEGACY_ACCESS_COOKIE,
                    "1",
                    max_age=LEGACY_ACCESS_MAX_AGE,
                    httponly=True,
                    secure=request.url.scheme == "https",
                    samesite="lax",
                    path=LEGACY_PATH,
                )
            return response

        return await call_next(request)

    app.state.entry_policy_installed = True


__all__ = [
    "LEGACY_ACCESS_COOKIE",
    "LEGACY_ACCESS_MAX_AGE",
    "LEGACY_PATH",
    "V1_ENTRY",
    "install_entry_policy",
]
