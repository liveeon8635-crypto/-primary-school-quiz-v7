"""Read-only production revision endpoint for deployment acceptance."""

from __future__ import annotations

import os
import re
from collections.abc import Mapping

from fastapi import FastAPI

_SHA40 = re.compile(r"^[0-9a-fA-F]{40}$")


def render_git_commit(environ: Mapping[str, str] | None = None) -> str | None:
    source = os.environ if environ is None else environ
    value = str(source.get("RENDER_GIT_COMMIT") or "").strip()
    return value.lower() if _SHA40.fullmatch(value) else None


def install_health_revision_route(app: FastAPI) -> None:
    if getattr(app.state, "health_revision_route_installed", False):
        return

    @app.get("/health/revision", include_in_schema=False)
    def health_revision():
        return {
            "status": "ok",
            "version": render_git_commit(),
        }

    app.state.health_revision_route_installed = True


__all__ = ["install_health_revision_route", "render_git_commit"]
