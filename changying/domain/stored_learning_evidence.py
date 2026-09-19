"""Map explicit production evidence events into the domain evidence vocabulary."""

from __future__ import annotations

from datetime import timezone
import json
from types import ModuleType
from typing import Any

from changying.domain.learning_evidence import LearningEvidence


EXPLICIT_PERFORMANCE_SOURCES = frozenset(
    {
        "submission",
        "submission_answer",
        "teacher_confirmed_grading",
        "teacher_confirmed_rubric",
    }
)


def _context_json(raw: str) -> dict[str, Any]:
    try:
        value = json.loads(raw or "{}")
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}





def canonical_submission_ids(
    implementation: ModuleType,
    db: Any,
    student_id: int,
    school_id: int,
) -> set[int]:
    """Return submissions already represented by explicit canonical events."""
    rows = db.scalars(
        implementation.select(implementation.LearningEvidenceEvent).where(
            implementation.LearningEvidenceEvent.school_id == school_id,
            implementation.LearningEvidenceEvent.student_id == student_id,
            implementation.LearningEvidenceEvent.event_kind == "record",
            implementation.LearningEvidenceEvent.source_type == "submission",
        )
    ).all()
    result: set[int] = set()
    for row in rows:
        value = _context_json(row.context or "").get("submissionID")
        try:
            result.add(int(value))
        except Exception:
            continue
    return result


def teacher_confirmed_assignment_ids(
    implementation: ModuleType,
    db: Any,
    student_id: int,
    school_id: int,
) -> set[int]:
    rows = db.scalars(
        implementation.select(implementation.LearningEvidenceEvent).where(
            implementation.LearningEvidenceEvent.school_id == school_id,
            implementation.LearningEvidenceEvent.student_id == student_id,
        )
    ).all()
    retracted = {
        int(row.target_event_id)
        for row in rows
        if row.event_kind == "retract" and row.target_event_id is not None
    }
    result = set()
    for row in rows:
        if (
            row.event_kind != "record"
            or row.source_type != "teacher_confirmed_grading"
            or int(row.id) in retracted
        ):
            continue
        value = _context_json(row.context or "").get("assignmentID")
        try:
            result.add(int(value))
        except Exception:
            continue
    return result


def explicit_student_evidence(
    implementation: ModuleType,
    db: Any,
    student_id: int,
    school_id: int,
) -> list[LearningEvidence]:
    rows = db.scalars(
        implementation.select(implementation.LearningEvidenceEvent)
        .where(
            implementation.LearningEvidenceEvent.school_id == school_id,
            implementation.LearningEvidenceEvent.student_id == student_id,
        )
        .order_by(
            implementation.LearningEvidenceEvent.occurred_at.asc(),
            implementation.LearningEvidenceEvent.id.asc(),
        )
    ).all()
    retracted = {
        int(row.target_event_id)
        for row in rows
        if row.event_kind == "retract" and row.target_event_id is not None
    }
    result = []
    for row in rows:
        if (
            row.event_kind != "record"
            or row.source_type not in EXPLICIT_PERFORMANCE_SOURCES
            or int(row.id) in retracted
        ):
            continue
        context = _context_json(row.context or "")
        score = None
        if row.source_type in {"submission", "teacher_confirmed_grading"}:
            try:
                score = float(context.get("score")) if context.get("score") is not None else None
            except Exception:
                score = None
        occurred = row.occurred_at
        if occurred.tzinfo is None:
            occurred = occurred.replace(tzinfo=timezone.utc)
        if row.source_type == "submission":
            source_id = f"submission:{context.get('submissionID')}"
        elif row.source_type == "submission_answer":
            source_id = (
                f"submission:{context.get('submissionID')}:question:"
                f"{context.get('questionID')}"
            )
        elif row.source_type == "teacher_confirmed_grading":
            source_id = f"grading-review:{context.get('reviewID')}"
        else:
            source_id = (
                f"grading-review:{context.get('reviewID')}:question:"
                f"{context.get('questionID')}"
            )
        result.append(
            LearningEvidence(
                student_id=str(row.student_id),
                evidence_type="performance",
                occurred_at=occurred,
                source_type=row.source_type,
                source_id=source_id,
                subject=row.subject or "",
                knowledge_key=row.knowledge_key or "",
                success=row.success,
                score=score,
                context=row.note or "",
            )
        )
    return result


__all__ = [
    "EXPLICIT_PERFORMANCE_SOURCES",
    "canonical_submission_ids",
    "explicit_student_evidence",
    "teacher_confirmed_assignment_ids",
]
