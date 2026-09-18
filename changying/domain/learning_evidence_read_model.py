"""Pure read model for one student's continuous learning-evidence record.

This module turns validated LearningEvidence items into a UI-friendly snapshot.
It deliberately summarizes observations without inferring mastery, diagnosis,
or intervention. The input must belong to one stable student_id.
"""

from __future__ import annotations

from collections import defaultdict
from statistics import fmean
from typing import Any, Iterable

from changying.domain.learning_evidence import LearningEvidence, evidence_state


def _avg(values: list[float]) -> float | None:
    if not values:
        return None
    return round(fmean(values), 1)


def _success_rate(values: list[bool]) -> float | None:
    if not values:
        return None
    return round(sum(1 for value in values if value) / len(values) * 100, 1)


def student_evidence_snapshot(
    items: Iterable[LearningEvidence],
    *,
    recent_limit: int = 12,
) -> dict[str, Any]:
    """Build a conservative read model for one student's evidence history."""
    rows = list(items)
    state = evidence_state(rows)

    if recent_limit < 0:
        raise ValueError("recent_limit must be non-negative")

    by_subject: dict[str, list[LearningEvidence]] = defaultdict(list)
    by_knowledge: dict[tuple[str, str], list[LearningEvidence]] = defaultdict(list)

    for item in rows:
        subject = item.subject.strip() or "未标注学科"
        by_subject[subject].append(item)
        if item.knowledge_key.strip():
            by_knowledge[(subject, item.knowledge_key.strip())].append(item)

    subject_rows = []
    for subject, group in sorted(by_subject.items(), key=lambda pair: pair[0]):
        scores = [float(x.score) for x in group if x.score is not None]
        successes = [x.success for x in group if isinstance(x.success, bool)]
        subject_rows.append(
            {
                "subject": subject,
                "sampleCount": len(group),
                "averageObservedScore": _avg(scores),
                "observedSuccessRate": _success_rate(successes),
                "latestAt": max(x.occurred_at for x in group).isoformat(),
            }
        )

    knowledge_rows = []
    for (subject, knowledge), group in by_knowledge.items():
        scores = [float(x.score) for x in group if x.score is not None]
        successes = [x.success for x in group if isinstance(x.success, bool)]
        knowledge_rows.append(
            {
                "subject": subject,
                "knowledgeKey": knowledge,
                "sampleCount": len(group),
                "averageObservedScore": _avg(scores),
                "observedSuccessRate": _success_rate(successes),
                "latestAt": max(x.occurred_at for x in group).isoformat(),
                "evidenceTypes": sorted({x.evidence_type for x in group}),
            }
        )
    knowledge_rows.sort(
        key=lambda row: (row["latestAt"], row["subject"], row["knowledgeKey"]),
        reverse=True,
    )

    ordered = sorted(rows, key=lambda item: item.occurred_at, reverse=True)
    recent = [
        {
            "occurredAt": item.occurred_at.isoformat(),
            "evidenceType": item.evidence_type,
            "subject": item.subject,
            "knowledgeKey": item.knowledge_key,
            "success": item.success,
            "score": item.score,
            "sourceType": item.source_type,
            "sourceId": item.source_id,
            "context": item.context,
        }
        for item in ordered[:recent_limit]
    ]

    return {
        **state,
        "subjects": subject_rows,
        "knowledge": knowledge_rows,
        "recentEvidence": recent,
        # Explicitly remind consumers that this snapshot is descriptive only.
        "masteryInferred": False,
    }


__all__ = ["student_evidence_snapshot"]
