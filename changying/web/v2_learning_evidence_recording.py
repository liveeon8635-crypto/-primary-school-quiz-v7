"""Teacher-authored learning evidence for the continuous student record.

The storage contract is append-only. A correction is represented by a retract
event followed, when needed, by a new record event. Existing record rows are
never deleted or overwritten.
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import ModuleType
from typing import Any

from fastapi import Depends, HTTPException
from pydantic import BaseModel

from changying.domain.learning_evidence import LearningEvidence


MANUAL_EVIDENCE_TYPES = frozenset({"independent", "retention", "transfer"})


class LearningEvidenceCreateBody(BaseModel):
    evidenceType: str
    subject: str = ""
    knowledgeKey: str = ""
    success: bool | None = None
    note: str
    context: str = ""
    occurredAt: datetime | None = None


class LearningEvidenceRetractBody(BaseModel):
    reason: str


def _bounded(value: str, limit: int, field: str) -> str:
    cleaned = (value or "").strip()
    if len(cleaned) > limit:
        raise HTTPException(400, f"{field}过长")
    return cleaned


def _occurred_at(value: datetime | None) -> datetime:
    if value is None:
        return datetime.utcnow()
    if value.tzinfo is None:
        raise HTTPException(400, "发生时间必须包含时区")
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _aware_utc(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def _event_rows(implementation: ModuleType, db: Any, student_id: int, school_id: int):
    return db.scalars(
        implementation.select(implementation.LearningEvidenceEvent)
        .where(
            implementation.LearningEvidenceEvent.school_id == school_id,
            implementation.LearningEvidenceEvent.student_id == student_id,
        )
        .order_by(
            implementation.LearningEvidenceEvent.created_at.asc(),
            implementation.LearningEvidenceEvent.id.asc(),
        )
    ).all()


def active_manual_record_rows(
    implementation: ModuleType,
    db: Any,
    student_id: int,
    school_id: int,
):
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


def manual_student_evidence(
    implementation: ModuleType,
    db: Any,
    student_id: int,
    school_id: int,
) -> list[LearningEvidence]:
    out: list[LearningEvidence] = []
    for row in active_manual_record_rows(
        implementation,
        db,
        student_id,
        school_id,
    ):
        parts = []
        if (row.context or "").strip():
            parts.append(row.context.strip())
        if (row.note or "").strip():
            parts.append("教师记录：" + row.note.strip())
        out.append(
            LearningEvidence(
                student_id=str(row.student_id),
                evidence_type=row.evidence_type,
                occurred_at=_aware_utc(row.occurred_at),
                source_type="teacher_observation",
                source_id=f"teacher-evidence:{row.id}",
                subject=row.subject or "",
                knowledge_key=row.knowledge_key or "",
                success=row.success,
                score=None,
                context=" · ".join(parts),
            )
        )
    return out


def _record_json(row, actor_name: str = ""):
    return {
        "id": int(row.id),
        "studentID": int(row.student_id),
        "actorID": int(row.actor_id),
        "actorName": actor_name,
        "eventKind": row.event_kind,
        "targetEventID": row.target_event_id,
        "evidenceType": row.evidence_type,
        "subject": row.subject or "",
        "knowledgeKey": row.knowledge_key or "",
        "success": row.success,
        "note": row.note or "",
        "context": row.context or "",
        "sourceType": row.source_type or "",
        "occurredAt": _aware_utc(row.occurred_at).isoformat(),
        "createdAt": _aware_utc(row.created_at).isoformat(),
    }


def _write_student(implementation: ModuleType, db, user, sid: int):
    implementation.need(user, "teacher", "admin")
    return implementation.can_manage_student_points(db, user, sid, None)


def install_v2_learning_evidence_routes(implementation: ModuleType) -> None:
    app = implementation.app
    if getattr(app.state, "v2_learning_evidence_routes_installed", False):
        return

    @app.get("/v2/students/{sid}/learning-evidence/manual", include_in_schema=False)
    def list_manual_evidence(
        sid: int,
        user=Depends(implementation.current_user),
        db=Depends(implementation.get_db),
    ):
        _write_student(implementation, db, user, sid)
        rows = active_manual_record_rows(
            implementation,
            db,
            sid,
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
            "studentID": sid,
            "records": [
                _record_json(row, actors.get(int(row.actor_id), ""))
                for row in reversed(rows)
            ],
            "count": len(rows),
            "appendOnly": True,
        }

    @app.get("/v2/students/{sid}/learning-evidence/events", include_in_schema=False)
    def list_manual_evidence_events(
        sid: int,
        user=Depends(implementation.current_user),
        db=Depends(implementation.get_db),
    ):
        _write_student(implementation, db, user, sid)
        rows = _event_rows(
            implementation,
            db,
            sid,
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

        retraction_by_target = {
            int(row.target_event_id): row
            for row in rows
            if row.event_kind == "retract" and row.target_event_id is not None
        }

        events = []
        for row in reversed(rows):
            item = _record_json(row, actors.get(int(row.actor_id), ""))
            if row.event_kind == "record":
                retract = retraction_by_target.get(int(row.id))
                item["effectiveStatus"] = "retracted" if retract is not None else "active"
                item["retractEventID"] = int(retract.id) if retract is not None else None
                item["retractReason"] = (retract.note or "") if retract is not None else ""
                item["retractedAt"] = (
                    _aware_utc(retract.created_at).isoformat()
                    if retract is not None
                    else None
                )
            else:
                item["effectiveStatus"] = "retraction"
                item["retractEventID"] = int(row.id)
                item["retractReason"] = row.note or ""
                item["retractedAt"] = _aware_utc(row.created_at).isoformat()
            events.append(item)

        return {
            "studentID": sid,
            "events": events,
            "count": len(events),
            "appendOnly": True,
            "includesRetracted": True,
        }

    @app.post("/v2/students/{sid}/learning-evidence", include_in_schema=False)
    def create_manual_evidence(
        sid: int,
        body: LearningEvidenceCreateBody,
        user=Depends(implementation.current_user),
        db=Depends(implementation.get_db),
    ):
        student = _write_student(implementation, db, user, sid)
        evidence_type = (body.evidenceType or "").strip()
        if evidence_type not in MANUAL_EVIDENCE_TYPES:
            raise HTTPException(
                400,
                "教师手工记录仅支持独立完成、跨时保持、迁移应用；学习表现由作业/测验自动形成",
            )
        subject = _bounded(body.subject, 80, "学科")
        knowledge = _bounded(body.knowledgeKey, 160, "知识点")
        note = _bounded(body.note, 1000, "观察记录")
        context = _bounded(body.context, 500, "情境")
        if not note:
            raise HTTPException(400, "请填写观察记录")

        row = implementation.LearningEvidenceEvent(
            school_id=int(user.school_id),
            student_id=int(student.id),
            actor_id=int(user.id),
            event_kind="record",
            target_event_id=None,
            evidence_type=evidence_type,
            subject=subject,
            knowledge_key=knowledge,
            success=body.success,
            note=note,
            context=context,
            source_type="teacher_observation",
            occurred_at=_occurred_at(body.occurredAt),
        )
        db.add(row)
        db.flush()
        implementation.audit(
            db,
            user,
            "learning.evidence.record",
            f"{student.id}:{row.id}:{evidence_type}",
        )
        db.commit()
        db.refresh(row)
        return {
            "ok": True,
            "record": _record_json(row, user.name),
            "appendOnly": True,
        }

    @app.post("/v2/learning-evidence/{event_id}/retract", include_in_schema=False)
    def retract_manual_evidence(
        event_id: int,
        body: LearningEvidenceRetractBody,
        user=Depends(implementation.current_user),
        db=Depends(implementation.get_db),
    ):
        implementation.need(user, "teacher", "admin")
        record = db.scalar(
            implementation.select(implementation.LearningEvidenceEvent).where(
                implementation.LearningEvidenceEvent.id == event_id,
                implementation.LearningEvidenceEvent.school_id == user.school_id,
                implementation.LearningEvidenceEvent.event_kind == "record",
            )
        )
        if record is None:
            raise HTTPException(404, "学习证据记录不存在")
        if user.role != "admin" and int(record.actor_id) != int(user.id):
            raise HTTPException(403, "只能撤回自己记录的学习证据")

        existing = db.scalar(
            implementation.select(implementation.LearningEvidenceEvent).where(
                implementation.LearningEvidenceEvent.school_id == user.school_id,
                implementation.LearningEvidenceEvent.event_kind == "retract",
                implementation.LearningEvidenceEvent.target_event_id == record.id,
            )
        )
        if existing is not None:
            raise HTTPException(409, "该学习证据已经撤回")

        reason = _bounded(body.reason, 500, "撤回原因")
        if not reason:
            raise HTTPException(400, "请填写撤回原因")

        retract = implementation.LearningEvidenceEvent(
            school_id=int(user.school_id),
            student_id=int(record.student_id),
            actor_id=int(user.id),
            event_kind="retract",
            target_event_id=int(record.id),
            evidence_type=record.evidence_type,
            subject=record.subject or "",
            knowledge_key=record.knowledge_key or "",
            success=record.success,
            note=reason,
            context=record.context or "",
            source_type="teacher_observation_retraction",
            occurred_at=datetime.utcnow(),
        )
        db.add(retract)
        db.flush()
        implementation.audit(
            db,
            user,
            "learning.evidence.retract",
            f"{record.student_id}:{record.id}:{retract.id}",
        )
        db.commit()
        return {
            "ok": True,
            "retractedEventID": int(record.id),
            "retractEventID": int(retract.id),
            "appendOnly": True,
        }

    app.state.v2_learning_evidence_routes_installed = True


__all__ = [
    "MANUAL_EVIDENCE_TYPES",
    "active_manual_record_rows",
    "install_v2_learning_evidence_routes",
    "manual_student_evidence",
]
