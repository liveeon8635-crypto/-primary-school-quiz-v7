"""Map explicit production evidence events into the domain evidence vocabulary."""

from __future__ import annotations

from datetime import timezone
import json
from types import ModuleType
from typing import Any

from changying.domain.learning_evidence import LearningEvidence


EXPLICIT_PERFORMANCE_SOURCES = frozenset(
    {"teacher_confirmed_grading", "teacher_confirmed_rubric"}
)


def _context_json(raw: str) -> dict[str, Any]:
    try:
        value = json.loads(raw or "{}")
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


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
            implementation.LearningEvidenceEvent.event_kind == "record",
            implementation.LearningEvidenceEvent.source_type == "teacher_confirmed_grading",
        )
    ).all()
    result = set()
    for row in rows:
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
            implementation.LearningEvidenceEvent.event_kind == "record",
            implementation.LearningEvidenceEvent.source_type.in_(EXPLICIT_PERFORMANCE_SOURCES),
        )
        .order_by(
            implementation.LearningEvidenceEvent.occurred_at.asc(),
            implementation.LearningEvidenceEvent.id.asc(),
        )
    ).all()
    result = []
    for row in rows:
        context = _context_json(row.context or "")
        score = None
        if row.source_type == "teacher_confirmed_grading":
            try:
                score = float(context.get("score")) if context.get("score") is not None else None
            except Exception:
                score = None
        occurred = row.occurred_at
        if occurred.tzinfo is None:
            occurred = occurred.replace(tzinfo=timezone.utc)
        source_id = (
            f"grading-review:{context.get('reviewID')}"
            if row.source_type == "teacher_confirmed_grading"
            else f"grading-review:{context.get('reviewID')}:question:{context.get('questionID')}"
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
    "explicit_student_evidence",
    "teacher_confirmed_assignment_ids",
]
