"""Read-only compatibility mapping from legacy learning facts to V1.1 evidence.

The existing production database already contains useful historical facts such
as Submission.student_id, submitted_at, score and answer correctness. This
module converts those facts into the new evidence vocabulary without creating
tables, mutating rows or pretending that old data proves dimensions it did not
actually record.

Important policy: legacy rows may produce only performance evidence.
Independent, retention and transfer require explicit future facts.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Mapping

from changying.domain.learning_evidence import LearningEvidence


LEGACY_INFERRED_EVIDENCE_TYPES = frozenset({"performance"})


def legacy_utc(value: datetime) -> datetime:
    """Interpret legacy naive datetimes as UTC, preserving aware values."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _context(*, assignment_id: Any = None, class_id: Any = None, extra: str = "") -> str:
    parts: list[str] = []
    if assignment_id is not None:
        parts.append(f"assignment:{assignment_id}")
    if class_id is not None:
        parts.append(f"class:{class_id}")
    if extra.strip():
        parts.append(extra.strip())
    return " · ".join(parts)


def submission_to_performance_evidence(
    submission: Any,
    *,
    subject: str = "",
    knowledge_key: str = "",
    class_id: Any = None,
    context: str = "",
) -> LearningEvidence:
    """Map one legacy Submission-like object to one summary performance fact."""
    return LearningEvidence(
        student_id=str(submission.student_id),
        evidence_type="performance",
        occurred_at=legacy_utc(submission.submitted_at),
        source_type="submission",
        source_id=str(submission.id),
        subject=subject,
        knowledge_key=knowledge_key,
        success=None,
        score=float(submission.score),
        context=_context(
            assignment_id=getattr(submission, "assignment_id", None),
            class_id=class_id,
            extra=context,
        ),
    )


def submission_answers_to_performance_evidence(
    submission: Any,
    *,
    question_knowledge: Mapping[int, str],
    subject: str = "",
    class_id: Any = None,
    context: str = "",
) -> list[LearningEvidence]:
    """Map normalized answer rows to knowledge-level performance facts.

    Only rows with an integer question_id, a boolean correct flag and a known
    non-empty knowledge label are emitted. Missing or ambiguous legacy
    information is skipped instead of being guessed.
    """
    try:
        rows = json.loads(getattr(submission, "answers_json", "") or "[]")
    except (TypeError, json.JSONDecodeError):
        return []
    if not isinstance(rows, list):
        return []

    result: list[LearningEvidence] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        question_id = row.get("question_id")
        correct = row.get("correct")
        if not isinstance(question_id, int) or not isinstance(correct, bool):
            continue
        knowledge = str(question_knowledge.get(question_id, "") or "").strip()
        if not knowledge:
            continue
        result.append(
            LearningEvidence(
                student_id=str(submission.student_id),
                evidence_type="performance",
                occurred_at=legacy_utc(submission.submitted_at),
                source_type="submission_answer",
                source_id=f"{submission.id}:question:{question_id}",
                subject=subject,
                knowledge_key=knowledge,
                success=correct,
                score=100.0 if correct else 0.0,
                context=_context(
                    assignment_id=getattr(submission, "assignment_id", None),
                    class_id=class_id,
                    extra=context,
                ),
            )
        )
    return result


__all__ = [
    "LEGACY_INFERRED_EVIDENCE_TYPES",
    "legacy_utc",
    "submission_answers_to_performance_evidence",
    "submission_to_performance_evidence",
]
