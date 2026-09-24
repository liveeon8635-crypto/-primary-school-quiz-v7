"""Attach read-only longitudinal classroom facts to the V1 student profile."""

from __future__ import annotations

from types import ModuleType

from changying.services.classroom_longitudinal import classroom_student_snapshot


def install_v1_classroom_longitudinal_profile(implementation: ModuleType) -> None:
    if getattr(implementation, "_v1_classroom_longitudinal_profile_installed", False):
        return

    original = implementation.student_growth_profile_data

    def wrapped_student_growth_profile_data(db, stu, school_id: int, class_id: int | None = None):
        profile = original(db, stu, school_id, class_id)
        try:
            classroom = classroom_student_snapshot(
                implementation,
                db,
                student_id=int(stu.id),
                school_id=int(school_id),
            )
            enriched = dict(profile)
            enriched["classroomParticipation"] = classroom

            existing = list(profile.get("timeline") or [])
            classroom_events = list(classroom.get("timelineEvents") or [])
            merged = existing + classroom_events
            merged.sort(key=lambda item: str(item.get("time") or ""), reverse=True)
            enriched["timeline"] = merged[:120]
            return enriched
        except Exception:
            # This is an additive read model. It must not break the mature profile.
            return profile

    implementation.student_growth_profile_data = wrapped_student_growth_profile_data
    implementation._v1_classroom_longitudinal_profile_installed = True


__all__ = ["install_v1_classroom_longitudinal_profile"]
