"""Short-lived server-side auth handoff between V1 and Classic browser contexts.

V1 and Classic keep their normal Bearer-token session model.  This module only
bridges the navigation boundary where iPhone Safari/PWA may create a new
sessionStorage context.  The bearer is copied into a 120-second HttpOnly,
SameSite=Strict cookie, consumed once by Classic, then immediately deleted.
"""

from __future__ import annotations

from types import ModuleType

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import JSONResponse

V1_AUTH_HANDOFF_COOKIE = "cy_v1_auth_handoff"
V1_AUTH_HANDOFF_MAX_AGE = 120
V1_AUTH_HANDOFF_STAGE_PATH = "/v1/auth-handoff"
V1_AUTH_HANDOFF_CONSUME_PATH = "/v1/auth-handoff/consume"


def _no_store(response: JSONResponse) -> JSONResponse:
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    return response


def _request_is_https(request: Request) -> bool:
    """True for direct TLS and for TLS terminated by the platform proxy.

    Render terminates TLS and forwards plain HTTP to uvicorn, so ``request.url.scheme``
    reads "http" in production.  Without honouring ``X-Forwarded-Proto`` the one-time
    handoff cookie would be issued *without* ``Secure``.
    """
    if request.url.scheme == "https":
        return True
    forwarded = str(request.headers.get("x-forwarded-proto", "")).split(",")[0].strip().lower()
    return forwarded == "https"


def _delete_handoff_cookie(response: JSONResponse, request: Request) -> None:
    response.delete_cookie(
        V1_AUTH_HANDOFF_COOKIE,
        path="/",
        secure=_request_is_https(request),
        httponly=True,
        samesite="strict",
    )


def install_v1_auth_handoff_routes(implementation: ModuleType) -> None:
    """Install the bounded, one-time V1 -> Classic authentication bridge."""

    app = implementation.app
    if getattr(app.state, "v1_auth_handoff_routes_installed", False):
        return

    router = APIRouter()

    @router.post(V1_AUTH_HANDOFF_STAGE_PATH, include_in_schema=False)
    def stage_v1_auth_handoff(
        request: Request,
        authorization: str | None = Header(default=None),
        db=Depends(implementation.get_db),
    ):
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(401, "未登录")

        # Reuse the existing production token validation and account-state checks.
        implementation.authenticated_user(authorization=authorization, db=db)
        token = authorization[7:]

        response = _no_store(
            JSONResponse({"ok": True, "expiresIn": V1_AUTH_HANDOFF_MAX_AGE})
        )
        response.set_cookie(
            V1_AUTH_HANDOFF_COOKIE,
            token,
            max_age=V1_AUTH_HANDOFF_MAX_AGE,
            path="/",
            secure=_request_is_https(request),
            httponly=True,
            samesite="strict",
        )
        return response

    @router.post(V1_AUTH_HANDOFF_CONSUME_PATH, include_in_schema=False)
    def consume_v1_auth_handoff(
        request: Request,
        db=Depends(implementation.get_db),
    ):
        token = request.cookies.get(V1_AUTH_HANDOFF_COOKIE, "")
        if not token:
            response = _no_store(JSONResponse({"detail": "登录交接不存在或已过期"}, status_code=401))
            _delete_handoff_cookie(response, request)
            return response

        # A cross-site POST must never be allowed to turn the HttpOnly bridge
        # back into a script-readable bearer token.
        if request.headers.get("sec-fetch-site", "").lower() == "cross-site":
            response = _no_store(JSONResponse({"detail": "跨站登录交接已拒绝"}, status_code=403))
            _delete_handoff_cookie(response, request)
            return response

        try:
            user = implementation.authenticated_user(
                authorization=f"Bearer {token}",
                db=db,
            )
        except HTTPException as exc:
            response = _no_store(
                JSONResponse({"detail": str(exc.detail)}, status_code=exc.status_code)
            )
            _delete_handoff_cookie(response, request)
            return response

        security = implementation.security_for(db, user)
        payload = {
            "token": token,
            "valid": True,
            "userID": user.id,
            "name": user.name,
            "role": user.role,
            "grade": user.grade,
            "mustChangePassword": bool(security.must_change_password),
            "subscription": implementation.subscription_payload(db, user.school_id),
        }
        response = _no_store(JSONResponse(payload))
        # Destructive read: the cookie is gone before the browser can make a
        # second consume request. Classic keeps the validated token only in its
        # normal session/local storage according to remember semantics.
        _delete_handoff_cookie(response, request)
        return response

    app.include_router(router)
    app.state.v1_auth_handoff_routes_installed = True


__all__ = [
    "V1_AUTH_HANDOFF_COOKIE",
    "V1_AUTH_HANDOFF_CONSUME_PATH",
    "V1_AUTH_HANDOFF_MAX_AGE",
    "V1_AUTH_HANDOFF_STAGE_PATH",
    "install_v1_auth_handoff_routes",
]
