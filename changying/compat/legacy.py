"""Runtime compatibility bridge for the legacy monolith.

The production service still imports ``app_v924`` while individual helpers are
moved into maintainable modules. This adapter installs the extracted functions
onto the legacy module so existing route functions continue resolving the same
global names without a risky all-at-once rewrite.
"""

from __future__ import annotations

from types import ModuleType

from changying.domain.assignments import (
    ASSIGNMENT_SUBMISSION_MODES,
    assignment_mode_name,
    assignment_status,
)
from changying.domain.commercial import (
    COMMERCIAL_PLANS,
    FEATURE_NAMES,
    SUBSCRIPTION_STATUS_NAMES,
    commercial_plan,
    effective_subscription_status,
)
from changying.security.passwords import hash_password, password_ok, password_version, verify_password
from changying.security.tokens import make_token as issue_token
from changying.utils.datetime_tools import SCHOOL_TZ, due_deadline_utc, school_local_iso
from changying.utils.json_tools import json_list
from changying.web.product_shell import install_product_shell
from changying.web.pwa import build_manifest


def apply_legacy_compatibility(implementation: ModuleType, *, asset_version: str) -> None:
    """Install extracted helpers while preserving legacy runtime configuration."""
    implementation.MANIFEST = build_manifest(asset_version=asset_version)
    implementation.SCHOOL_TZ = SCHOOL_TZ
    implementation.due_deadline_utc = due_deadline_utc
    implementation.school_local_iso = school_local_iso
    implementation._json_list = json_list
    implementation.ASSIGNMENT_SUBMISSION_MODES = ASSIGNMENT_SUBMISSION_MODES
    implementation.assignment_mode_name = assignment_mode_name
    implementation.assignment_status = assignment_status
    implementation.COMMERCIAL_PLANS = COMMERCIAL_PLANS
    implementation.SUBSCRIPTION_STATUS_NAMES = SUBSCRIPTION_STATUS_NAMES
    implementation.FEATURE_NAMES = FEATURE_NAMES
    implementation._commercial_plan = commercial_plan
    implementation._effective_subscription_status = effective_subscription_status
    implementation.hash_password = hash_password
    implementation.verify_password = verify_password
    implementation.password_ok = password_ok
    implementation.password_version = password_version

    # The legacy module remains the source of truth for production JWT config.
    # Supplying those values explicitly prevents a refactor from creating a
    # second secret or changing token lifetimes.
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
    install_product_shell(implementation.app)


__all__ = ["apply_legacy_compatibility"]
