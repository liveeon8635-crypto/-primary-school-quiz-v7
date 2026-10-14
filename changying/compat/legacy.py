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
from changying.security.login_rate import BoundedLoginRateLimiter, LoginRateLimitExceeded
from changying.security.tokens import make_token as issue_token
from changying.services.academic_summary import AcademicSummaryService
from changying.services.assignments import AssignmentService
from changying.services.class_history import ClassHistoryService
from changying.services.assessment_reliability import install_assessment_reliability
from changying.services.assessment_context_policy import install_subject_aware_assessment_context
from changying.services.followups import FollowUpService
from changying.services.learning_points import install_learning_points
from changying.services.language_question_quality import install_language_question_quality
from changying.services.points import PointService
from changying.services.reinforcement_subject_policy import install_reinforcement_subject_policy
from changying.services.rubric_evidence_closure import install_rubric_evidence_closure, manual_question_meta
from changying.services.submission_evidence import install_canonical_submission_evidence
from changying.services.textbook_registry import install_textbook_registry_guard
from changying.services.teaching import TeachingService
from changying.services.teacher_ai_rich_generation import install_teacher_ai_rich_generation
from changying.services.wrong_questions import WrongQuestionService
from changying.utils.datetime_tools import SCHOOL_TZ, due_deadline_utc, school_local_iso
from changying.utils.json_tools import json_list
from changying.web.classic_ui import install_classic_ui_patch
from changying.web.health_revision import install_health_revision_route
from changying.web.product_shell import (
    PRODUCT_SHELL_MARKER,
    install_product_shell,
    teacher_workbench_html,
)
from changying.web.operator_usage_metering import install_operator_usage_metering_routes
from changying.web.operator_console_legacy import OPERATOR_HTML
from changying.web.pwa import (
    ICON_180_PNG,
    ICON_192_PNG,
    ICON_512_PNG,
    ICON_SVG,
    build_manifest,
    install_favicon_route,
)
from changying.web.v1 import install_v1_routes
from changying.web.v1_acceptance_polish import install_v1_acceptance_polish_patch
from changying.web.v1_auth_handoff import install_v1_auth_handoff_routes
from changying.web.v1_audit_localization import install_v1_audit_localization
from changying.web.v1_classic_embed_bootstrap import install_v1_classic_embed_bootstrap
from changying.web.v1_classic_gzip_embed import install_v1_classic_gzip_embed
from changying.web.v1_html_etag import install_v1_html_etag
from changying.web.v1_classroom_review import (
    install_v1_classroom_review_patch,
    install_v1_classroom_review_routes,
)
from changying.web.v1_classroom_execution import (
    install_v1_classroom_execution_patch,
    install_v1_classroom_execution_routes,
)
from changying.web.paper_composition_routes import install_paper_composition_routes
from changying.web.paper_import_routes import install_paper_import_routes
from changying.web.v1_classroom_quick_check import (
    install_v1_classroom_quick_check_patch,
    install_v1_classroom_quick_check_routes,
)
from changying.web.v1_classroom_presentation_review import (
    install_v1_classroom_presentation_review_patch,
    install_v1_classroom_presentation_review_routes,
)
from changying.web.v1_classroom_handout_release import (
    install_v1_classroom_handout_release_patch,
    install_v1_classroom_handout_release_routes,
)
from changying.web.v1_classroom_longitudinal_profile import install_v1_classroom_longitudinal_profile
from changying.web.v1_completion import install_v1_completion_patch
from changying.web.v1_data_quality import install_v1_data_quality_patch
from changying.web.v1_fast_path import install_v1_fast_path_patch, install_v1_fast_read_routes
from changying.web.v1_final_closure import install_v1_final_closure_patch
from changying.web.v1_full_visibility import install_v1_full_visibility_patch
from changying.web.v1_guardian_visibility import install_v1_guardian_visibility_patch
from changying.web.v1_history_focus import install_v1_history_focus_patch
from changying.web.v1_identity_clarity import install_v1_identity_clarity_patch
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
from changying.web.v1_transition_plan import install_v1_transition_plan_routes
from changying.web.v1_transition_plan_view import install_v1_transition_plan_view_patch
from changying.web.v1_teaching_cycle import install_v1_teaching_cycle_routes
from changying.web.v1_transition_facts_view import install_v1_transition_facts_view_patch
from changying.web.v27_stage_evidence_comparison import install_v27_stage_evidence_routes
from changying.web.v27_stage_evidence_view import install_v27_stage_evidence_view_patch
from changying.web.v1_learning_evidence_view import install_v1_learning_evidence_view_patch
from changying.web.v1_learning_evidence_access import install_v1_learning_evidence_access_patch, install_v1_learning_evidence_access_routes
from changying.web.v1_mastery_evidence import install_v1_mastery_evidence_patch
from changying.web.v1_membership_reliability import install_v1_membership_reliability_patch
from changying.web.v1_membership_visibility import install_v1_membership_visibility_patch
from changying.web.v1_operational import install_v1_operational_patch
from changying.web.v1_parent_link_history import install_v1_parent_link_history_profile
from changying.web.v1_school_facts import install_v1_school_facts_patch
from changying.web.v1_product_guide import install_v1_product_guide_patch
from changying.web.v1_training_sandbox import install_v1_training_sandbox_routes
from changying.web.v1_training_workbench import install_v1_training_workbench_route
from changying.web.v1_product_assistant import (
    install_v1_product_assistant_patch,
    install_v1_product_assistant_routes,
)
from changying.web.v1_student_detail_visibility import install_v1_student_detail_visibility_patch
from changying.web.v1_student_practice import install_v1_student_practice_patch, install_v1_student_practice_routes
from changying.web.v1_teaching_actions import install_v1_teaching_actions_patch
from changying.web.v1_transition_selection import install_v1_transition_selection_patch
from changying.web.v1_unified_tools import (
    install_v1_unified_tool_route,
    install_v1_unified_tools_patch,
)
from changying.web.v1_workspace_tabs import install_v1_workspace_tabs_patch
from changying.web.v1_unified_tools_session_bridge import install_v1_unified_tool_session_bridge
from changying.web.reinforcement_quality import install_reinforcement_figure_fallback
from changying.web.rubric_review_ui import install_rubric_review_ui
from changying.web.science_teacher_ai import install_science_teacher_ai_workflow
from changying.web.student_quiz_navigation import install_student_quiz_navigation
from changying.web.classroom_quick_login import install_classroom_quick_login
from changying.services.homework_assistant_tables import register_homework_assistant_tables
from changying.services.homework_knowledge import register_homework_knowledge_table
from changying.web.homework_assistant import install_homework_assistant
from changying.web.homework_help import install_homework_help
from changying.web.homework_knowledge_views import install_homework_knowledge_views
from changying.web.kp_cards_views import install_kp_cards_views
from changying.web.weekend_plan_views import install_weekend_plan
from changying.web.weekend_practice import install_weekend_practice
from changying.web.weekend_scoring_views import install_weekend_scoring
from changying.web.weekend_views import install_weekend_views
from changying.web.v1_classroom_live_board import (
    install_v1_classroom_live_board_patch,
    install_v1_classroom_live_board_routes,
)
from changying.web.student_wrong_practice import install_student_wrong_practice
from changying.web.teacher_ai_rich_generation_ui import install_teacher_ai_rich_generation_ui

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



def install_teacher_dashboard_current_student_count(implementation: ModuleType) -> None:
    """Keep the legacy teacher dashboard student KPI aligned with current class membership."""

    if getattr(implementation, "_teacher_dashboard_current_student_count_installed", False):
        return

    original = implementation.teacher_analytics_data

    def teacher_analytics_with_current_students(db, user):
        payload = dict(original(db, user))
        if getattr(user, "role", "") == "teacher":
            current_students = db.scalar(
                implementation.select(
                    implementation.func.count(
                        implementation.func.distinct(implementation.ClassStudent.student_id)
                    )
                )
                .select_from(implementation.ClassStudent)
                .join(
                    implementation.SchoolClass,
                    implementation.SchoolClass.id == implementation.ClassStudent.class_id,
                )
                .where(
                    implementation.SchoolClass.school_id == user.school_id,
                    implementation.SchoolClass.teacher_id == user.id,
                )
            )
            payload["students"] = int(current_students or 0)
        return payload

    implementation.teacher_analytics_data = teacher_analytics_with_current_students
    implementation._teacher_dashboard_current_student_count_installed = True


def apply_legacy_compatibility(implementation: ModuleType, *, asset_version: str) -> None:
    """Install extracted helpers while preserving legacy runtime configuration."""
    implementation.MANIFEST = build_manifest(asset_version=asset_version)
    implementation.ICON_SVG = ICON_SVG
    implementation.ICON_180_PNG = ICON_180_PNG
    implementation.ICON_192_PNG = ICON_192_PNG
    implementation.ICON_512_PNG = ICON_512_PNG
    install_favicon_route(implementation.app)
    implementation.SCHOOL_TZ = SCHOOL_TZ
    implementation.due_deadline_utc = due_deadline_utc
    implementation.school_local_iso = school_local_iso
    implementation._json_list = json_list
    implementation.ASSIGNMENT_SUBMISSION_MODES = ASSIGNMENT_SUBMISSION_MODES
    implementation.assignment_mode_name = assignment_mode_name
    implementation.assignment_status = assignment_status
    implementation.manual_question_meta = manual_question_meta
    implementation.OPERATOR_HTML = OPERATOR_HTML
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

    login_rate_limiter = BoundedLoginRateLimiter(
        window_seconds=implementation.LOGIN_RATE_WINDOW_SECONDS,
        max_attempts=implementation.LOGIN_RATE_MAX_ATTEMPTS,
        max_keys=2048,
    )

    def bounded_login_rate_check(request):
        key = implementation._client_ip(request)
        try:
            login_rate_limiter.check(key)
        except LoginRateLimitExceeded:
            raise implementation.HTTPException(429, "登录请求过于频繁，请稍后再试")
        return key

    def bounded_login_rate_failure(key):
        try:
            login_rate_limiter.failure(key)
        except LoginRateLimitExceeded:
            raise implementation.HTTPException(429, "登录请求过于频繁，请稍后再试")

    def bounded_login_rate_clear(key):
        login_rate_limiter.clear(key)

    implementation._bounded_login_rate_limiter = login_rate_limiter
    implementation.login_rate_check = bounded_login_rate_check
    implementation.login_rate_failure = bounded_login_rate_failure
    implementation.login_rate_clear = bounded_login_rate_clear

    assignment_service = AssignmentService(
        assignment_submission_setting_model=implementation.AssignmentSubmissionSetting,
        submission_model=implementation.Submission,
        homework_media_submit_model=implementation.HomeworkMediaSubmit,
        homework_media_model=implementation.HomeworkMedia,
        user_model=implementation.User,
        assignment_recipient_model=implementation.AssignmentRecipient,
        assignment_model=implementation.Assignment,
        class_model=implementation.SchoolClass,
        valid_submission_modes=ASSIGNMENT_SUBMISSION_MODES,
        assignment_mode_name=assignment_mode_name,
        school_local_iso=school_local_iso,
        due_deadline_utc=due_deadline_utc,
    )
    implementation.assignment_service = assignment_service
    implementation.assignment_submission_setting = assignment_service.submission_setting
    implementation.assignment_submission_mode = assignment_service.submission_mode
    implementation.homework_media_count = assignment_service.homework_media_count
    implementation.student_assignment_for = assignment_service.student_assignment_for
    implementation.student_assignment_for_paper = assignment_service.student_assignment_for_paper
    implementation.teacher_assignment_for = assignment_service.teacher_assignment_for
    implementation.recipient_students = assignment_service.recipient_students
    implementation.assignment_effective_status = assignment_service.effective_status

    original_assignment_json = implementation.aj

    def assignment_json_with_local_timeline(db, assignment):
        payload = dict(original_assignment_json(db, assignment))
        payload["assignedAt"] = school_local_iso(
            getattr(assignment, "created_at", None)
        )
        return payload

    implementation.aj = assignment_json_with_local_timeline
    install_teacher_dashboard_current_student_count(implementation)

    teaching_service = TeachingService(
        adaptive_session_model=implementation.TeachingAdaptiveSession,
        lesson_model=implementation.TeachingLesson,
        question_model=implementation.TeachingQuestion,
    )
    implementation.teaching_service = teaching_service
    implementation.latest_teaching_session = teaching_service.latest_session
    implementation.teaching_program_lessons = teaching_service.program_lessons
    implementation.teaching_question_counts = teaching_service.question_counts
    implementation.teaching_questions_for_level = teaching_service.questions_for_level

    class_history_service = ClassHistoryService(
        history_model=implementation.StudentClassHistory,
        class_model=implementation.SchoolClass,
        select_fn=implementation.select,
        local_iso=school_local_iso,
    )
    implementation.class_history_service = class_history_service
    implementation.class_history_rows = class_history_service.rows

    academic_summary_service = AcademicSummaryService(
        submission_model=implementation.Submission,
        select_fn=implementation.select,
        period_cutoff_fn=period_cutoff_utc,
    )
    implementation.academic_summary_service = academic_summary_service
    implementation.student_academic_summary = academic_summary_service.summary

    point_service = PointService(
        point_ledger_model=implementation.PointLedger,
        school_class_model=implementation.SchoolClass,
        user_model=implementation.User,
        point_rule_model=implementation.PointRule,
        school_local_iso_fn=school_local_iso,
    )
    implementation.point_service = point_service
    implementation.point_balance = point_service.balance
    implementation.point_class_window_categories = point_service.class_window_categories
    implementation.point_class_window_summary = point_service.class_window_summary
    implementation.point_ledger_json = point_service.ledger_json
    implementation.point_metric_value = point_service.metric_value
    implementation.point_period_summary = point_service.period_summary
    implementation.point_school_period_summary = point_service.school_period_summary
    implementation.point_rule_json = point_service.rule_json
    implementation.class_point_rule_json = point_service.class_rule_json
    implementation.inherited_point_rule_json = point_service.inherited_rule_json
    implementation.point_recent_rows = point_service.recent_rows
    implementation.point_school_history_rows = point_service.school_history_rows
    implementation.point_student_history_rows = point_service.student_history_rows
    implementation.point_student_recent_rows = point_service.student_recent_rows
    implementation.point_summary = point_service.summary
    implementation.point_window_series = point_service.window_series
    implementation.point_window_summary = point_service.window_summary

    wrong_question_service = WrongQuestionService(
        wrong_question_model=implementation.WrongQuestionRecord,
    )
    implementation.wrong_question_service = wrong_question_service
    implementation.wrong_question_assignment_rows = wrong_question_service.assignment_rows
    implementation.wrong_question_teacher_student_rows = wrong_question_service.teacher_student_rows
    implementation.wrong_question_student_rows = wrong_question_service.student_rows

    followup_service = FollowUpService(
        followup_model=implementation.StudentFollowUp,
        followup_log_model=implementation.StudentFollowUpLog,
        class_todo_model=implementation.ClassTodo,
    )
    implementation.followup_service = followup_service
    implementation.followup_student_history_rows = followup_service.student_history_rows
    implementation.followup_student_log_history_rows = followup_service.student_log_history_rows
    implementation.followup_item_log_rows = followup_service.item_log_rows
    implementation.followup_class_rows = followup_service.class_rows
    implementation.followup_item_row = followup_service.item_row
    implementation.followup_parent_contact_rows = followup_service.parent_contact_rows
    implementation.followup_class_parent_contact_rows = followup_service.class_parent_contact_rows
    implementation.followup_timeline_rows = followup_service.timeline_rows
    implementation.followup_timeline_log_rows = followup_service.timeline_log_rows
    implementation.followup_class_todo_rows = followup_service.class_todo_rows
    implementation.followup_class_parent_contact_count = followup_service.class_parent_contact_count
    implementation.followup_profile_rows = followup_service.profile_rows
    implementation.followup_profile_parent_contact_rows = followup_service.profile_parent_contact_rows
    implementation.followup_teacher_search_rows = followup_service.teacher_search_rows
    implementation.followup_workbench_stale_rows = followup_service.workbench_stale_rows

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
    install_assessment_reliability(implementation)
    install_subject_aware_assessment_context(implementation)
    install_reinforcement_subject_policy(implementation)
    install_rubric_evidence_closure(implementation)
    install_canonical_submission_evidence(implementation)
    install_language_question_quality(implementation)
    install_learning_points(implementation)
    install_teacher_ai_rich_generation(implementation)
    install_textbook_registry_guard(implementation)
    install_science_teacher_ai_workflow(implementation)
    install_teacher_ai_rich_generation_ui(implementation)
    install_reinforcement_figure_fallback(implementation)
    install_rubric_review_ui(implementation)
    install_student_quiz_navigation(implementation)
    install_product_shell(implementation.app)
    install_product_visibility_routes(implementation.app)
    install_health_revision_route(implementation.app)
    install_operator_usage_metering_routes(implementation)
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
    install_v1_student_practice_patch()
    install_v1_student_practice_routes(implementation)
    install_student_wrong_practice(implementation)
    install_v1_classroom_review_patch()
    install_v1_classroom_review_routes(implementation)
    install_v1_classroom_execution_patch()
    install_v1_classroom_execution_routes(implementation)
    install_v1_classroom_quick_check_patch()
    install_v1_classroom_quick_check_routes(implementation)
    install_v1_classroom_live_board_patch()
    install_v1_classroom_live_board_routes(implementation)
    install_classroom_quick_login(implementation)
    register_homework_assistant_tables(implementation)
    register_homework_knowledge_table(implementation)
    install_homework_assistant(implementation)
    install_homework_help(implementation)
    install_homework_knowledge_views(implementation)
    install_kp_cards_views(implementation)
    install_weekend_views(implementation)
    install_weekend_practice(implementation)
    install_weekend_scoring(implementation)
    install_weekend_plan(implementation)
    install_paper_composition_routes(implementation)
    install_paper_import_routes(implementation)
    install_v1_classroom_presentation_review_patch()
    install_v1_classroom_presentation_review_routes(implementation)
    install_v1_classroom_handout_release_patch()
    install_v1_classroom_handout_release_routes(implementation)
    install_v1_guardian_visibility_patch()
    install_v1_membership_reliability_patch()
    install_v1_final_closure_patch()
    install_v1_fast_path_patch()
    install_v1_identity_clarity_patch()
    install_v1_acceptance_polish_patch()
    install_v1_unified_tools_patch()
    install_v1_unified_tool_session_bridge()
    install_v1_audit_localization()
    install_v1_history_focus_patch()
    install_v1_product_guide_patch()
    install_v1_training_sandbox_routes(implementation)
    install_v1_training_workbench_route(implementation.app)
    install_v1_product_assistant_patch()
    install_v1_product_assistant_routes(implementation)
    install_v1_workspace_tabs_patch()
    install_v1_learning_evidence_profile(implementation)
    install_v1_classroom_longitudinal_profile(implementation)
    install_v2_learning_evidence_recorder_patch()
    install_v2_learning_evidence_routes(implementation)
    install_v21_teaching_evidence_context_view_patch()
    install_v21_teaching_evidence_context_routes(implementation)
    install_v22_evidence_coverage_view_patch()
    install_v22_evidence_coverage_routes(implementation)
    install_v1_historical_teaching_view_patch()
    install_v1_historical_teaching_routes(implementation)
    install_v1_transition_facts_view_patch()
    install_v1_transition_plan_view_patch()
    install_v1_transition_snapshot_routes(implementation)
    install_v1_transition_plan_routes(implementation)
    install_v1_teaching_cycle_routes(implementation)
    install_v27_stage_evidence_view_patch()
    install_v27_stage_evidence_routes(implementation)
    install_v1_parent_link_history_profile(implementation)
    install_v1_learning_evidence_view_patch()
    install_v1_learning_evidence_access_patch()
    install_v1_learning_evidence_access_routes(implementation)
    install_v1_auth_handoff_routes(implementation)
    install_v1_routes(implementation.app)
    install_v1_unified_tool_route(implementation.app)
    # Keep last so it wraps every V1/Classic HTML response installed above.
    install_v1_html_etag(implementation.app)


__all__ = ["NO_CACHE_HEADERS", "apply_legacy_compatibility", "install_product_visibility_routes", "install_teacher_dashboard_current_student_count"]