"""Operator-only read API for commercial usage metering."""

from __future__ import annotations

from types import ModuleType

from fastapi import Depends, HTTPException

from changying.services.commercial_usage import CommercialUsageMeteringService


def _service(implementation: ModuleType) -> CommercialUsageMeteringService:
    return CommercialUsageMeteringService(
        school_model=implementation.School,
        user_model=implementation.User,
        school_class_model=implementation.SchoolClass,
        assignment_model=implementation.Assignment,
        submission_model=implementation.Submission,
        teaching_attempt_model=implementation.TeachingAttempt,
        learning_evidence_event_model=implementation.LearningEvidenceEvent,
        ai_usage_log_model=implementation.AIUsageLog,
        homework_media_model=implementation.HomeworkMedia,
        teaching_resource_model=implementation.TeachingResource,
        school_subscription_model=implementation.SchoolSubscription,
    )


def install_operator_usage_metering_routes(implementation: ModuleType) -> None:
    app = implementation.app
    if getattr(app.state, "operator_usage_metering_routes_installed", False):
        return

    service = _service(implementation)

    @app.get("/operator/usage-metering")
    def operator_usage_metering(
        month: str = "",
        _ok: bool = Depends(implementation.commercial_operator),
        db=Depends(implementation.get_db),
    ):
        try:
            return service.schools_month(db, month=month or None)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

    @app.get("/operator/schools/{school_id}/usage-metering")
    def operator_school_usage_metering(
        school_id: int,
        month: str = "",
        _ok: bool = Depends(implementation.commercial_operator),
        db=Depends(implementation.get_db),
    ):
        try:
            return service.school_month(
                db,
                school_id=school_id,
                month=month or None,
            )
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        except LookupError as exc:
            raise HTTPException(404, "学校不存在") from exc

    app.state.operator_usage_metering_routes_installed = True


__all__ = ["install_operator_usage_metering_routes"]
