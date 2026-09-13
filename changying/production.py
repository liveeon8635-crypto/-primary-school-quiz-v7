"""Production application loader.

Render imports ``app:app`` and never needs to know which legacy implementation
is currently promoted. Change ``PRODUCTION_MODULE`` and ``ASSET_VERSION`` only
when a newer implementation has passed CI and is ready for production.
"""

from __future__ import annotations

import importlib

from fastapi import FastAPI

from changying.domain.assignments import (
    ASSIGNMENT_SUBMISSION_MODES,
    assignment_mode_name,
    assignment_status,
)
from changying.security.passwords import hash_password, password_ok, password_version, verify_password
from changying.security.tokens import make_token as issue_token
from changying.utils.datetime_tools import SCHOOL_TZ, due_deadline_utc, school_local_iso
from changying.utils.json_tools import json_list
from changying.web.pwa import build_manifest

PRODUCTION_MODULE = "app_v924"
ASSET_VERSION = "924"


def load_production_app() -> FastAPI:
    implementation = importlib.import_module(PRODUCTION_MODULE)

    # Compatibility shims let us migrate contained helpers out of the legacy
    # module without rewriting the 700KB+ production file in one dangerous
    # change. Existing route functions resolve these module globals at runtime.
    implementation.MANIFEST = build_manifest(asset_version=ASSET_VERSION)
    implementation.SCHOOL_TZ = SCHOOL_TZ
    implementation.due_deadline_utc = due_deadline_utc
    implementation.school_local_iso = school_local_iso
    implementation._json_list = json_list
    implementation.ASSIGNMENT_SUBMISSION_MODES = ASSIGNMENT_SUBMISSION_MODES
    implementation.assignment_mode_name = assignment_mode_name
    implementation.assignment_status = assignment_status
    implementation.hash_password = hash_password
    implementation.verify_password = verify_password
    implementation.password_ok = password_ok
    implementation.password_version = password_version

    # Keep the legacy module's existing JWT configuration authoritative. The
    # extracted signer receives that configuration explicitly, so this refactor
    # cannot create a second secret or change token lifetimes by accident.
    def legacy_make_token(user, security, remember=False):
        return issue_token(
            user,
            security,
            remember,
            secret=implementation.JWT_SECRET,
            algorithm=implementation.JWT_ALG,
            access_hours=implementation.ACCESS_HOURS,
            remember_days=implementation.REMEMBER_DAYS,
            password_version_fn=password_version,
        )

    implementation.make_token = legacy_make_token
    return implementation.app


app = load_production_app()

__all__ = ["ASSET_VERSION", "PRODUCTION_MODULE", "app", "load_production_app"]
