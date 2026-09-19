"""Runtime compatibility bridge for the legacy monolith.

The production service still imports ``app_v924`` while individual helpers are
moved into maintainable modules. This adapter installs the extracted functions
onto the legacy module so existing route functions continue resolving the same
global names without a risky all-at-once rewrite.
"""

from __future__ import annotations

from types import ModuleType

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

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
from changying.domain.growth import (
    auto_period_window,
    calendar_week_window_utc,
    day_window_utc,
    discipline_streak_from_trend,
    period_cutoff_utc,
    progress_streak_from_trend,
)
from changying.security.passwords import hash_password, password_ok, password_version, verify_password
from changying.security.tokens import make_token as issue_token
from changying.utils.datetime_tools import SCHOOL_TZ, due_deadline_utc, school_local_iso
from changying.utils.json_tools import json_list
from changying.web.classic_ui import install_classic_ui_patch
from changying.web.product_shell import (
    PRODUCT_SHELL_MARKER,
    install_product_shell,
    teacher_workbench_html,
)
from changying.web.pwa import build_manifest
from changying.web.v1 import install_v1_routes
from changying.web.v1_acceptance_polish import install_v1_acceptance_polish_patch
from changying.web.v1_auth_handoff import install_v1_auth_handoff_routes
from changying.web.v1_audit_localization import install_v1_audit_localization
from changying.web.v1_classic_embed_bootstrap import install_v1_classic_embed_bootstrap
from changying.web.v1_classic_gzip_embed import install_v1_classic_gzip_embed
from changying.web.v1_completion import install_v1_completion_patch
from changying.web.v1_data_quality import install_v1_data_quality_patch
from changying.web.v1_fast_path import install_v1_fast_path_patch, install_v1_fast_read_routes
from changying.web.v1_final_closure import install_v1_final_closure_patch
from changying.web.v1_full_visibility import install_v1_full_visibility_patch
from changying.web.v1_guardian_visibility import install_v1_guardian_visibility_patch
from changying.web.v1_history_focus import install_v1_history_focus_patch
from changying.web.v1_identity_clarity import install_v1_identity_clarity_patch
from changying.web.v1_legacy_capabilities import install_v1_legacy_capabilities_patch
from changying.web.v1_learning_evidence_profile import install_v1_learning_evidence_profile
from changying.web.v2_learning_evidence_recording import install_v2_learning_evidence_routes
from changying.web.v2_learning_evidence_recording_view import install_v2_learning_evidence_recorder_patch
from changying.web.v2_teaching_evidence_context import install_v21_teaching_evidence_context_routes
from changying.web.v2_teaching_evidence_context_view import install_v21_teaching_evidence_context_view_patch
from changying.web.v22_evidence_coverage import install_v22_evidence_coverage_routes
from changying.web.v22_evidence_coverage_view import install_v22_evidence_coverage_view_patch
from changying.web.v1_historical_teaching import install_v1_historical_teaching_routes
from changying.web.v1_historical_teaching_view import install_v1_historical_teaching_view_patch
from changying.web.v1_transition_snapshot import install_v1_transition_snapshot_routes
from changying.web.v1_transition_facts_view import install_v1_transition_facts_view_patch
from changying.web.v1_learning_evidence_view import install_v1_learning_evidence_view_patch
from changying.web.v1_learning_evidence_access import install_v1_learning_evidence_access_patch, install_v1_learning_evidence_access_routes
from changying.web.v1_mastery_evidence import install_v1_mastery_evidence_patch
from changying.web.v1_membership_reliability import install_v1_membership_reliability_patch
from changying.web.v1_membership_visibility import install_v1_membership_visibility_patch
from changying.web.v1_operational import install_v1_operational_patch
from changying.web.v1_parent_link_history import install_v1_parent_link_history_profile
from changying.web.v1_school_facts import install_v1_school_facts_patch
from changying.web.v1_student_detail_visibility import install_v1_student_detail_visibility_patch
from changying.web.v1_teaching_actions import install_v1_teaching_actions_patch
from changying.web.v1_transition_selection import install_v1_transition_selection_patch
from changying.web.v1_unified_tools import (
    install_v1_unified_tool_route,
    install_v1_unified_tools_patch,
)
from changying.web.v1_unified_tools_session_bridge import install_v1_unified_tool_session_bridge

NO_CACHE_HEADERS = {
    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
    "Pragma": "no-cache",
    "Expires": "0",
}


def install_product_visibility_routes(app: FastAPI) -> None:
    """Add cache-safe entry points so the product UI is easy to find."""
    if getattr(app.state, "product_visibility_routes_installed", False):
        return

    def product_response() -> HTMLResponse:
        headers = {
            **NO_CACHE_HEADERS,
            "X-Changying-Product-UI": PRODUCT_SHELL_MARKER,
        }
        return HTMLResponse(teacher_workbench_html(), headers=headers)

    @app.get("/workbench", include_in_schema=False)
    @app.get("/new", include_in_schema=False)
    def changying_workbench_entry():
        return product_response()

    @app.middleware("http")
    async def product_visibility_headers(request, call_next):
        response = await call_next(request)
        if request.url.path in {"/", "/new", "/workbench", "/classic"}:
            for header, value in NO_CACHE_HEADERS.items():
                response.headers[header] = value
            response.headers["X-Changying-Product-UI"] = PRODUCT_SHELL_MARKER
        return response

    app.state.product_visibility_routes_installed = True


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
    implementation.period_cutoff_utc = period_cutoff_utc
    implementation.auto_period_window = auto_period_window
    implementation.calendar_week_window_utc = calendar_week_window_utc
    implementation.day_window_utc = day_window_utc
    implementation._progress_streak_from_trend = progress_streak_from_trend
    implementation._discipline_streak_from_trend = discipline_streak_from_trend
    implementation.hash_password = hash_password
    implementation.verify_password = verify_password
    implementation.password_ok = password_ok
    implementation.password_version = password_version

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
    install_product_visibility_routes(implementation.app)
    install_classic_ui_patch(implementation.app)
    install_v1_classic_embed_bootstrap()
    install_v1_classic_gzip_embed(implementation.app)
    install_v1_fast_read_routes(implementation)
    install_v1_data_quality_patch()
    install_v1_teaching_actions_patch()
    install_v1_transition_selection_patch()
    install_v1_operational_patch()
    install_v1_completion_patch()
    install_v1_mastery_evidence_patch()
    install_v1_school_facts_patch()
    install_v1_full_visibility_patch()
    install_v1_membership_visibility_patch()
    install_v1_student_detail_visibility_patch()
    install_v1_guardian_visibility_patch()
    install_v1_membership_reliability_patch()
    install_v1_final_closure_patch()
    install_v1_fast_path_patch()
    install_v1_identity_clarity_patch()
    install_v1_acceptance_polish_patch()
    install_v1_legacy_capabilities_patch()
    install_v1_unified_tools_patch()
    install_v1_unified_tool_session_bridge()
    install_v1_audit_localization()
    install_v1_history_focus_patch()
    install_v1_learning_evidence_profile(implementation)
    install_v2_learning_evidence_recorder_patch()
    install_v2_learning_evidence_routes(implementation)
    install_v21_teaching_evidence_context_view_patch()
    install_v21_teaching_evidence_context_routes(implementation)
    install_v22_evidence_coverage_view_patch()
    install_v22_evidence_coverage_routes(implementation)
    install_v1_historical_teaching_view_patch()
    install_v1_historical_teaching_routes(implementation)
    install_v1_transition_facts_view_patch()
    install_v1_transition_snapshot_routes(implementation)
    install_v1_parent_link_history_profile(implementation)
    install_v1_learning_evidence_view_patch()
    install_v1_learning_evidence_access_patch()
    install_v1_learning_evidence_access_routes(implementation)
    install_v1_auth_handoff_routes(implementation)
    install_v1_routes(implementation.app)
    install_v1_unified_tool_route(implementation.app)


__all__ = ["NO_CACHE_HEADERS", "apply_legacy_compatibility", "install_product_visibility_routes"]