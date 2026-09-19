"""Read-only teaching-planning facts derived from one student's evidence record.

This module deliberately does not produce diagnosis, mastery, placement, or
teaching recommendations. It only reshapes already-recorded evidence into a
teacher-facing planning context.
"""

from __future__ import annotations

from types import ModuleType

from fastapi import Depends, HTTPException

from changying.domain.learning_evidence import EVIDENCE_TYPES
from changying.domain.learning_evidence_read_model import student_evidence_snapshot
from changying.web.v1_learning_evidence_profile import legacy_student_evidence


DIMENSION_NAMES = {
    "performance": "学习表现",
    "independent": "独立完成",
    "retention": "跨时保持",
    "transfer": "迁移应用",
}


def build_teaching_evidence_context(snapshot: dict) -> dict:
    dimensions = set(snapshot.get("dimensions") or [])
    missing = sorted(set(EVIDENCE_TYPES) - dimensions)
    available = sorted(dimensions)

    knowledge = []
    for row in (snapshot.get("knowledge") or [])[:10]:
        knowledge.append(
            {
                "subject": row.get("subject") or "",
                "knowledgeKey": row.get("knowledgeKey") or "",
                "sampleCount": int(row.get("sampleCount") or 0),
                "averageObservedScore": row.get("averageObservedScore"),
                "observedSuccessRate": row.get("observedSuccessRate"),
                "latestAt": row.get("latestAt") or "",
                "evidenceTypes": list(row.get("evidenceTypes") or []),
            }
        )

    recent = []
    for row in (snapshot.get("recentEvidence") or [])[:10]:
        recent.append(
            {
                "occurredAt": row.get("occurredAt") or "",
                "evidenceType": row.get("evidenceType") or "",
                "subject": row.get("subject") or "",
                "knowledgeKey": row.get("knowledgeKey") or "",
                "success": row.get("success"),
                "score": row.get("score"),
                "sourceType": row.get("sourceType") or "",
                "context": row.get("context") or "",
            }
        )

    return {
        "state": snapshot.get("state") or "evidence_insufficient",
        "sampleCount": int(snapshot.get("sampleCount") or 0),
        "availableDimensions": available,
        "missingDimensions": missing,
        "dimensionNames": DIMENSION_NAMES,
        "subjects": list(snapshot.get("subjects") or [])[:8],
        "knowledgeFacts": knowledge,
        "recentFacts": recent,
        "decisionRequiredByTeacher": True,
        "automaticDiagnosis": False,
        "automaticRecommendation": False,
        "automaticPlacementDecision": False,
        "boundary": (
            "这里仅汇总已记录的学习事实。缺少某类证据只表示系统尚无记录，"
            "不等于学生存在能力缺口；教学目标、材料、节奏与下一步安排仍由教师"
            "结合课程标准、教材、课堂观察和实际教学情境决定。"
        ),
        "teachingToolPath": "/v1/tool?page=teaching",
    }


def _teacher_student(implementation: ModuleType, db, user, sid: int):
    implementation.need(user, "teacher", "admin")
    student = db.scalar(
        implementation.select(implementation.User).where(
            implementation.User.id == sid,
            implementation.User.school_id == user.school_id,
            implementation.User.role == "student",
        )
    )
    if student is None:
        raise HTTPException(404, "学生不存在")
    return implementation.can_manage_student_points(db, user, sid, None)


def install_v21_teaching_evidence_context_routes(implementation: ModuleType) -> None:
    app = implementation.app
    if getattr(app.state, "v21_teaching_evidence_context_routes_installed", False):
        return

    @app.get("/v2/students/{sid}/teaching-evidence-context", include_in_schema=False)
    def teaching_evidence_context(
        sid: int,
        user=Depends(implementation.current_user),
        db=Depends(implementation.get_db),
    ):
        student = _teacher_student(implementation, db, user, sid)
        items = legacy_student_evidence(
            implementation,
            db,
            int(student.id),
            int(user.school_id),
        )
        snapshot = student_evidence_snapshot(items)
        return {
            "student": {"id": int(student.id), "name": student.name},
            **build_teaching_evidence_context(snapshot),
        }

    app.state.v21_teaching_evidence_context_routes_installed = True


__all__ = [
    "DIMENSION_NAMES",
    "build_teaching_evidence_context",
    "install_v21_teaching_evidence_context_routes",
]
