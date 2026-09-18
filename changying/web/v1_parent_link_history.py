"""Read-only parent/student relationship history for the continuous student record.

Current ParentStudent rows are authoritative for the present relationship.
Historical intervals are reconstructed from existing parent.bind / parent.unbind
AuditLog events. Unknown legacy start/end times remain explicit instead of being
invented.
"""

from __future__ import annotations

from types import ModuleType
from typing import Any


def _iso(implementation: ModuleType, value) -> str | None:
    return implementation.school_local_iso(value) if value is not None else None


def parent_link_history(
    implementation: ModuleType,
    db: Any,
    student_id: int,
    school_id: int,
) -> list[dict[str, Any]]:
    logs = db.scalars(
        implementation.select(implementation.AuditLog)
        .where(
            implementation.AuditLog.school_id == school_id,
            implementation.AuditLog.action.in_(["parent.bind", "parent.unbind"]),
            implementation.AuditLog.detail.like(f"{student_id}:%"),
        )
        .order_by(
            implementation.AuditLog.created_at.asc(),
            implementation.AuditLog.id.asc(),
        )
    ).all()

    intervals: list[dict[str, Any]] = []
    open_row: dict[str, Any] | None = None

    for log in logs:
        detail = log.detail or ""
        if log.action == "parent.bind":
            parts = detail.split(":", 3)
            if len(parts) < 4:
                continue
            try:
                parent_id = int(parts[2])
            except (TypeError, ValueError):
                continue
            parent_name = parts[3].strip() or f"家长#{parent_id}"

            if open_row is not None:
                open_row["endedAt"] = _iso(implementation, log.created_at)
                open_row["endReason"] = "replaced"
                open_row["current"] = False
                intervals.append(open_row)

            open_row = {
                "parentID": parent_id,
                "parentName": parent_name,
                "startedAt": _iso(implementation, log.created_at),
                "endedAt": None,
                "endReason": "",
                "current": False,
                "source": "audit",
                "startKnown": True,
                "endKnown": False,
            }
        elif log.action == "parent.unbind":
            if open_row is not None:
                open_row["endedAt"] = _iso(implementation, log.created_at)
                open_row["endReason"] = "unbind"
                open_row["current"] = False
                open_row["endKnown"] = True
                intervals.append(open_row)
                open_row = None

    current_links = db.scalars(
        implementation.select(implementation.ParentStudent).where(
            implementation.ParentStudent.student_id == student_id
        )
    ).all()
    current_ids = {int(link.parent_id) for link in current_links}

    if open_row is not None:
        if open_row["parentID"] in current_ids:
            open_row["current"] = True
            open_row["endKnown"] = True
        else:
            # Audit says a relationship opened, but current storage says it no
            # longer exists and no matching unbind time is available.
            open_row["endReason"] = "ended_time_unknown"
        intervals.append(open_row)

    represented_current = {
        row["parentID"]
        for row in intervals
        if row.get("current") is True
    }
    for link in current_links:
        parent_id = int(link.parent_id)
        if parent_id in represented_current:
            continue
        parent = db.get(implementation.User, parent_id)
        intervals.append(
            {
                "parentID": parent_id,
                "parentName": parent.name if parent is not None else f"家长#{parent_id}",
                "startedAt": None,
                "endedAt": None,
                "endReason": "",
                "current": True,
                "source": "current_link",
                "startKnown": False,
                "endKnown": True,
            }
        )

    intervals.sort(
        key=lambda row: (
            row["startedAt"] or "",
            row["parentID"],
        ),
        reverse=True,
    )
    return intervals


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
