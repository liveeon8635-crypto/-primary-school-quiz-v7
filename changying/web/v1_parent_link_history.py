"""Read-only parent/student relationship history for the continuous student record.

Current ParentStudent rows are authoritative for the present relationship.
Historical intervals are reconstructed from existing parent.bind / parent.unbind
AuditLog events. Unknown legacy start/end times remain explicit instead of being
invented.
"""

from __future__ import annotations

from types import ModuleType
from typing import Any

from changying.services.parent_link_history import ParentLinkHistoryService


def _iso(implementation: ModuleType, value) -> str | None:
    return implementation.school_local_iso(value) if value is not None else None


def parent_link_history(
    implementation: ModuleType,
    db: Any,
    student_id: int,
    school_id: int,
) -> list[dict[str, Any]]:
    service = ParentLinkHistoryService(
        select_fn=implementation.select,
        audit_log_model=implementation.AuditLog,
        parent_student_model=implementation.ParentStudent,
        user_model=implementation.User,
        local_iso=implementation.school_local_iso,
    )
    return service.history(db, student_id=student_id, school_id=school_id)


def attach_parent_link_history(
    implementation: ModuleType,
    db: Any,
    profile: dict[str, Any],
    student_id: int,
    school_id: int,
) -> dict[str, Any]:
    result = dict(profile)
    result["parentHistory"] = parent_link_history(
        implementation,
        db,
        student_id,
        school_id,
    )
    return result


def install_v1_parent_link_history_profile(implementation: ModuleType) -> None:
    if getattr(implementation, "_v1_parent_link_history_profile_installed", False):
        return

    original = implementation.student_growth_profile_data

    def wrapped_student_growth_profile_data(
        db,
        stu,
        school_id: int,
        class_id: int | None = None,
    ):
        profile = original(db, stu, school_id, class_id)
        try:
            return attach_parent_link_history(
                implementation,
                db,
                profile,
                int(stu.id),
                int(school_id),
            )
        except Exception:
            return profile

    implementation.student_growth_profile_data = wrapped_student_growth_profile_data
    implementation._v1_parent_link_history_profile_installed = True


__all__ = [
    "attach_parent_link_history",
    "install_v1_parent_link_history_profile",
    "parent_link_history",
]
