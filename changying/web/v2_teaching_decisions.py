"""Teacher-authored planning decisions linked to frozen evidence facts.

Facts and decisions remain separate:
- learning evidence records what was observed;
- the system only summarizes those facts;
- a teaching decision is authored by a teacher/admin and stored append-only.

Corrections are represented by retract events. Original decisions are never
overwritten or physically deleted.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from types import ModuleType
from typing import Any

from fastapi import Depends, HTTPException
from pydantic import BaseModel

from changying.domain.learning_evidence_read_model import student_evidence_snapshot
from changying.web.v1_learning_evidence_profile import legacy_student_evidence


class TeachingDecisionCreateBody(BaseModel):
    subject: str = ""
    goal: str
    plan: str
    note: str = ""
    plannedFor: str = ""


class TeachingDecisionRetractBody(BaseModel):
    reason: str


def _bounded(value: str, limit: int, field: str, *, required: bool = False) -> str:
    cleaned = (value or "").strip()
    if required and not cleaned:
        raise HTTPException(400, f"请填写{field}")
    if len(cleaned) > limit:
        raise HTTPException(400, f"{field}过长")
    return cleaned


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


def _evidence_snapshot(implementation: ModuleType, db, student_id: int, school_id: int) -> dict:
    items = legacy_student_evidence(implementation, db, student_id, school_id)
    snapshot = student_evidence_snapshot(items)
    recent_ids = [
        row.get("sourceId")
        for row in (snapshot.get("recentEvidence") or [])[:20]
        if row.get("sourceId")
    ]
    return {
        "capturedAt": datetime.now(timezone.utc).isoformat(),
        "state": snapshot.get("state") or "evidence_insufficient",
        "sampleCount": int(snapshot.get("sampleCount") or 0),
        "dimensions": list(snapshot.get("dimensions") or []),
        "recentSourceIds": recent_ids,
        "masteryInferred": False,
        "automaticRecommendation": False,
    }


def _event_rows(implementation: ModuleType, db: Any, student_id: int, school_id: int):
    return db.scalars(
        implementation.select(implementation.TeachingDecisionEvent)
        .where(
            implementation.TeachingDecisionEvent.school_id == school_id,
            implementation.TeachingDecisionEvent.student_id == student_id,
        )
        .order_by(
            implementation.TeachingDecisionEvent.created_at.asc(),
            implementation.TeachingDecisionEvent.id.asc(),
        )
    ).all()


def active_decision_rows(implementation: ModuleType, db: Any, student_id: int, school_id: int):
    rows = _event_rows(implementation, db, student_id, school_id)
    retracted = {
        int(row.target_event_id)
        for row in rows
        if row.event_kind == "retract" and row.target_event_id is not None
    }
    return [
        row
        for row in rows
        if row.event_kind == "record" and int(row.id) not in retracted
    ]


def _snapshot_json(row) -> dict:
    try:
        value = json.loads(row.evidence_snapshot_json or "{}")
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def _row_json(row, actor_name: str = "") -> dict:
    return {
        "id": int(row.id),
        "studentID": int(row.student_id),
        "actorID": int(row.actor_id),
        "actorName": actor_name,
        "eventKind": row.event_kind,
        "targetEventID": row.target_event_id,
        "subject": row.subject or "",
        "goal": row.goal or "",
        "plan": row.plan or "",
        "note": row.note or "",
        "plannedFor": row.planned_for or "",
        "evidenceSnapshot": _snapshot_json(row),
        "createdAt": row.created_at.replace(tzinfo=timezone.utc).isoformat()
        if row.created_at.tzinfo is None
        else row.created_at.isoformat(),
        "authoredByTeacher": True,
        "automaticRecommendation": False,
    }


def install_v22_teaching_decision_routes(implementation: ModuleType) -> None:
    app = implementation.app
    if getattr(app.state, "v22_teaching_decision_routes_installed", False):
        return

    @app.get("/v2/students/{sid}/teaching-decisions", include_in_schema=False)
    def list_teaching_decisions(
        sid: int,
        user=Depends(implementation.current_user),
        db=Depends(implementation.get_db),
    ):
        student = _teacher_student(implementation, db, user, sid)
        rows = active_decision_rows(
            implementation,
            db,
            int(student.id),
            int(user.school_id),
        )
        actor_ids = {int(row.actor_id) for row in rows}
        actors = {}
        if actor_ids:
            actor_rows = db.scalars(
                implementation.select(implementation.User).where(
                    implementation.User.school_id == user.school_id,
                    implementation.User.id.in_(actor_ids),
                )
            ).all()
            actors = {int(row.id): row.name for row in actor_rows}
        return {
            "student": {"id": int(student.id), "name": student.name},
            "decisions": [
                _row_json(row, actors.get(int(row.actor_id), ""))
                for row in reversed(rows)
            ],
            "count": len(rows),
            "appendOnly": True,
            "factDecisionSeparation": True,
        }

    @app.post("/v2/students/{sid}/teaching-decisions", include_in_schema=False)
    def create_teaching_decision(
        sid: int,
        body: TeachingDecisionCreateBody,
        user=Depends(implementation.current_user),
        db=Depends(implementation.get_db),
    ):
        student = _teacher_student(implementation, db, user, sid)
        subject = _bounded(body.subject, 80, "学科")
        goal = _bounded(body.goal, 1500, "本次教学目标", required=True)
        plan = _bounded(body.plan, 4000, "教学安排", required=True)
        note = _bounded(body.note, 1500, "教师备注")
        planned_for = _bounded(body.plannedFor, 40, "计划日期")

        snapshot = _evidence_snapshot(
            implementation,
            db,
            int(student.id),
            int(user.school_id),
        )
        row = implementation.TeachingDecisionEvent(
            school_id=int(user.school_id),
            student_id=int(student.id),
            actor_id=int(user.id),
            event_kind="record",
            target_event_id=None,
            subject=subject,
            goal=goal,
            plan=plan,
            note=note,
            planned_for=planned_for,
            evidence_snapshot_json=json.dumps(snapshot, ensure_ascii=False),
        )
        db.add(row)
        db.flush()
        implementation.audit(
            db,
            user,
            "teaching.decision.record",
            f"{student.id}:{row.id}",
        )
        db.commit()
        db.refresh(row)
        return {
            "ok": True,
            "decision": _row_json(row, user.name),
            "appendOnly": True,
            "factDecisionSeparation": True,
            "notice": "本条内容由教师填写；系统只冻结当时证据快照，没有自动生成教学决定。",
        }

    @app.post("/v2/teaching-decisions/{event_id}/retract", include_in_schema=False)
    def retract_teaching_decision(
        event_id: int,
        body: TeachingDecisionRetractBody,
        user=Depends(implementation.current_user),
        db=Depends(implementation.get_db),
    ):
        implementation.need(user, "teacher", "admin")
        record = db.scalar(
            implementation.select(implementation.TeachingDecisionEvent).where(
                implementation.TeachingDecisionEvent.id == event_id,
                implementation.TeachingDecisionEvent.school_id == user.school_id,
                implementation.TeachingDecisionEvent.event_kind == "record",
            )
        )
        if record is None:
            raise HTTPException(404, "教师备课决定不存在")
        _teacher_student(implementation, db, user, int(record.student_id))
        if user.role != "admin" and int(record.actor_id) != int(user.id):
            raise HTTPException(403, "只能撤回自己记录的教师备课决定")

        existing = db.scalar(
            implementation.select(implementation.TeachingDecisionEvent).where(
                implementation.TeachingDecisionEvent.school_id == user.school_id,
                implementation.TeachingDecisionEvent.event_kind == "retract",
                implementation.TeachingDecisionEvent.target_event_id == record.id,
            )
        )
        if existing is not None:
            raise HTTPException(409, "该教师备课决定已经撤回")

        reason = _bounded(body.reason, 500, "撤回原因", required=True)
        retract = implementation.TeachingDecisionEvent(
            school_id=int(user.school_id),
            student_id=int(record.student_id),
            actor_id=int(user.id),
            event_kind="retract",
            target_event_id=int(record.id),
            subject=record.subject or "",
            goal="",
            plan="",
            note=reason,
            planned_for=record.planned_for or "",
            evidence_snapshot_json=record.evidence_snapshot_json or "{}",
        )
        db.add(retract)
        db.flush()
        implementation.audit(
            db,
            user,
            "teaching.decision.retract",
            f"{record.student_id}:{record.id}:{retract.id}",
        )
        db.commit()
        return {
            "ok": True,
            "retractedEventID": int(record.id),
            "retractEventID": int(retract.id),
            "appendOnly": True,
        }

    app.state.v22_teaching_decision_routes_installed = True


__all__ = [
    "active_decision_rows",
    "install_v22_teaching_decision_routes",
]
