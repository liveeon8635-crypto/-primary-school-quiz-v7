"""Read-only comparison of standardized evidence across student stages.

The comparison is descriptive only. Differences in evidence coverage between
stages do not imply improvement, regression, readiness, placement, or mastery.
"""

from __future__ import annotations

from datetime import timezone
from types import ModuleType

from fastapi import Depends

from changying.domain.learning_evidence_growth_profile import (
    growth_profile_learning_evidence,
)
from changying.domain.learning_evidence_read_model import student_evidence_snapshot
from changying.domain.learning_evidence_visibility import learning_evidence_for_role
from changying.web.v1_learning_evidence_profile import legacy_student_evidence
from changying.web.v1_transition_snapshot import _authorized_student


def _utc_naive(value):
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _stage_rows(implementation: ModuleType, db, student_id: int, school_id: int):
    rows = db.scalars(
        implementation.select(implementation.StudentClassHistory)
        .where(
            implementation.StudentClassHistory.student_id == student_id,
            implementation.StudentClassHistory.school_id == school_id,
        )
        .order_by(
            implementation.StudentClassHistory.joined_at.desc(),
            implementation.StudentClassHistory.id.desc(),
        )
    ).all()
    out = []
    for row in rows:
        klass = db.get(implementation.SchoolClass, row.class_id)
        out.append(
            {
                "id": int(row.id),
                "classID": int(row.class_id),
                "className": klass.name if klass is not None else f"班级#{row.class_id}",
                "grade": klass.grade if klass is not None else None,
                "joinedAtRaw": row.joined_at,
                "leftAtRaw": row.left_at,
                "joinedAt": implementation.school_local_iso(row.joined_at),
                "leftAt": implementation.school_local_iso(row.left_at) if row.left_at else None,
                "current": row.left_at is None,
                "leaveReason": row.leave_reason or "",
            }
        )
    return out


def _assign_evidence_to_stages(items, stages):
    by_stage = {row["id"]: [] for row in stages}
    unassigned = []

    # Newest joined stage wins when malformed/legacy history intervals overlap.
    ordered = sorted(
        stages,
        key=lambda row: (row["joinedAtRaw"], row["id"]),
        reverse=True,
    )
    for item in items:
        occurred = _utc_naive(item.occurred_at)
        matched = None
        for stage in ordered:
            joined = stage["joinedAtRaw"]
            left = stage["leftAtRaw"]
            if occurred < joined:
                continue
            if left is not None and occurred > left:
                continue
            matched = stage
            break
        if matched is None:
            unassigned.append(item)
        else:
            by_stage[matched["id"]].append(item)
    return by_stage, unassigned


def _stage_snapshot(stage, items, role: str, student_id: int):
    snapshot = growth_profile_learning_evidence(
        student_evidence_snapshot(items)
    )
    if snapshot.get("studentId") is None:
        snapshot["studentId"] = str(student_id)
    snapshot = learning_evidence_for_role(snapshot, role)
    return {
        "stage": {
            "id": stage["id"],
            "classID": stage["classID"],
            "className": stage["className"],
            "grade": stage["grade"],
            "joinedAt": stage["joinedAt"],
            "leftAt": stage["leftAt"],
            "current": stage["current"],
            "leaveReason": stage["leaveReason"],
        },
        "evidence": snapshot,
    }


def stage_evidence_comparison(
    implementation: ModuleType,
    db,
    student,
    school_id: int,
    viewer_role: str,
):
    stages = _stage_rows(implementation, db, int(student.id), int(school_id))
    items = legacy_student_evidence(
        implementation,
        db,
        int(student.id),
        int(school_id),
    )
    by_stage, unassigned = _assign_evidence_to_stages(items, stages)

    current = next((row for row in stages if row["current"]), stages[0] if stages else None)
    previous = next(
        (
            row
            for row in stages
            if current is not None and row["id"] != current["id"] and not row["current"]
        ),
        None,
    )

    current_view = (
        _stage_snapshot(
            current,
            by_stage.get(current["id"], []),
            viewer_role,
            int(student.id),
        )
        if current is not None
        else None
    )
    previous_view = (
        _stage_snapshot(
            previous,
            by_stage.get(previous["id"], []),
            viewer_role,
            int(student.id),
        )
        if previous is not None
        else None
    )

    current_dims = set(
        (current_view or {}).get("evidence", {}).get("dimensions") or []
    )
    previous_dims = set(
        (previous_view or {}).get("evidence", {}).get("dimensions") or []
    )

    return {
        "student": {
            "id": int(student.id),
            "name": student.name,
        },
        "currentStage": current_view,
        "previousStage": previous_view,
        "comparison": {
            "newlyRecordedDimensions": sorted(current_dims - previous_dims),
            "previousOnlyDimensions": sorted(previous_dims - current_dims),
            "sharedDimensions": sorted(current_dims & previous_dims),
            "unassignedEvidenceCount": len(unassigned),
            "note": (
                "阶段差异只表示各阶段被系统记录到的证据覆盖不同，"
                "不代表学生能力进步、退步、掌握或未掌握。"
            ),
            "automaticProgressJudgment": False,
            "automaticRegressionJudgment": False,
            "automaticMasteryJudgment": False,
            "automaticRecommendation": False,
        },
    }


def install_v27_stage_evidence_routes(implementation: ModuleType) -> None:
    app = implementation.app
    if getattr(app.state, "v27_stage_evidence_routes_installed", False):
        return

    @app.get(
        "/v2/students/{sid}/stage-evidence-comparison",
        include_in_schema=False,
    )
    def read_stage_evidence_comparison(
        sid: int,
        user=Depends(implementation.current_user),
        db=Depends(implementation.get_db),
    ):
        student = _authorized_student(implementation, db, user, sid)
        return stage_evidence_comparison(
            implementation,
            db,
            student,
            int(user.school_id),
            user.role,
        )

    app.state.v27_stage_evidence_routes_installed = True


__all__ = [
    "install_v27_stage_evidence_routes",
    "stage_evidence_comparison",
]
