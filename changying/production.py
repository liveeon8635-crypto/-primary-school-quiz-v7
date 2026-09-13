"""Production application loader.

Render imports ``app:app`` and never needs to know which legacy implementation
is currently promoted. Change ``PRODUCTION_MODULE`` and ``ASSET_VERSION`` only
when a newer implementation has passed CI and is ready for production.
"""

from __future__ import annotations

import importlib

from fastapi import FastAPI

from changying.utils.datetime_tools import SCHOOL_TZ, due_deadline_utc, school_local_iso
from changying.utils.json_tools import json_list
from changying.web.pwa import build_manifest

PRODUCTION_MODULE = "app_v924"
ASSET_VERSION = "924"


def load_production_app() -> FastAPI:
    implementation = importlib.import_module(PRODUCTION_MODULE)

    # Compatibility shims let us migrate low-risk helpers out of the legacy
    # module without rewriting the 700KB+ production file in one dangerous
    # change. Existing route functions resolve these module globals at runtime.
    implementation.MANIFEST = build_manifest(asset_version=ASSET_VERSION)
    implementation.SCHOOL_TZ = SCHOOL_TZ
    implementation.due_deadline_utc = due_deadline_utc
    implementation.school_local_iso = school_local_iso
    implementation._json_list = json_list
    return implementation.app


app = load_production_app()

__all__ = ["ASSET_VERSION", "PRODUCTION_MODULE", "app", "load_production_app"]
