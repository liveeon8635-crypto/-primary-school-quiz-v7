"""Read-only grade-transition facts for one continuous student record.

The snapshot joins class history and standardized learning evidence. It does not
produce an automatic diagnosis, readiness score, placement decision, or
teaching recommendation.
"""

from __future__ import annotations

from types import ModuleType

from fastapi import APIRouter, Depends, HTTPException

from changying.domain.learning_evidence import EVIDENCE_TYPES
from changying.domain.learning_evidence_growth_profile import (
    growth_profile_learning_evidence,
)
from changying.domain.learning_evidence_read_model import student_evidence_snapshot
from changying.domain.learning_evidence_visibility import learning_evidence_for_role
from changying.web.v1_learning_evidence_profile import legacy_student_evidence


def _authorized_student(implementation: ModuleType, db, user, sid: int):
    student = db.scalar(
        implementation.select(implementation.User).where(
            implementation.User.id == sid,
            implementation.User.school_id == user.school_id,
            implementation.User.role == "student",
        )
    )
    if student is None:
        raise HTTPException(404, "学生不存在")

    if user.role == "admin":
        return student
    if user.role == "teacher":
        return implementation.can_manage_student_points(db, user, sid, None)
    if user.role == "parent":
        linked = db.scalar(
            implementation.select(implementation.ParentStudent.id).where(
                implementation.ParentStudent.parent_id == user.id,
                implementation.ParentStudent.student_id == sid,
            )
        )
        if not linked:
            raise HTTPException(403, "未绑定该学生")
        return student
    if user.role == "student":
        if int(user.id) != int(sid):
            raise HTTPException(403, "无权查看其他学生")
        return student
    raise HTTPException(403, "无权查看衔接事实")


def _stage_from_history(history):
    current = next((row for row in history if row.get("current")), None)
    previous = next((row for row in history if not row.get("current")), None)
    return current, previous


def transition_snapshot(
    implementation: ModuleType,
    db,
    student,
    school_id: int,
    viewer_role: str = "teacher",
):
    history = implementation.class_history_rows(db, int(student.id), school_id)
    current, previous = _stage_from_history(history)

    items = legacy_student_evidence(
        implementation,
        db,
        int(student.id),
        int(school_id),
    )
    evidence = growth_profile_learning_evidence(
        student_evidence_snapshot(items)
    )
    evidence = learning_evidence_for_role(evidence, viewer_role)
    available = set(evidence.get("dimensions") or [])
    missing = sorted(set(EVIDENCE_TYPES) - available)

    grade = current.get("grade") if current else getattr(student, "grade", None)
    next_grade = grade + 1 if isinstance(grade, int) and 1 <= grade < 6 else None
    transition_type = (
        f"{grade}升{next_grade}"
        if next_grade is not None
        else ("小升初" if grade == 6 else "阶段衔接")
    )

    return {
        "student": {
            "id": int(student.id),
            "name": student.name,
        },
        "currentStage": current,
        "previousStage": previous,
        "classHistory": history,
        "learningEvidence": evidence,
        "evidenceAvailability": {
            "availableDimensions": sorted(available),
            "missingDimensions": missing,
            "note": "缺少的是系统尚未记录的证据维度，不等于学生能力缺口。",
        },
        "transition": {
            "typeCandidate": transition_type,
            "currentGrade": grade,
            "nextGradeCandidate": next_grade,
            "factsReady": bool(history or evidence.get("sampleCount")),
            "automaticDiagnosis": False,
            "automaticPlacementDecision": False,
            "automaticRecommendation": False,
        },
    }


def install_v1_transition_snapshot_routes(implementation: ModuleType) -> None:
    app = implementation.app
    if getattr(app.state, "v1_transition_snapshot_routes_installed", False):
        return

    router = APIRouter()

    @router.get("/v1/students/{sid}/transition-snapshot", include_in_schema=False)
    def read_transition_snapshot(
        sid: int,
        user=Depends(implementation.current_user),
        db=Depends(implementation.get_db),
    ):
        student = _authorized_student(implementation, db, user, sid)
        return transition_snapshot(
            implementation,
            db,
            student,
            int(user.school_id),
            user.role,
        )

    app.include_router(router)
    app.state.v1_transition_snapshot_routes_installed = True


__all__ = [
    "install_v1_transition_snapshot_routes",
    "transition_snapshot",
]
