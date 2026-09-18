"""Pure V1.1 learning-evidence rules.

This module defines an append-friendly evidence vocabulary for the continuous
student record. Evidence is always anchored to a stable student_id, while
source_type/source_id preserve where the evidence came from. The module does
not write production data and does not infer mastery from a score alone.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable


EVIDENCE_TYPES = {
    "performance",          # 当次任务/测验表现
    "independent",          # 无直接提示下独立完成
    "retention",            # 跨时间再次完成/回忆
    "transfer",             # 新材料、新题型或新情境迁移
}


@dataclass(frozen=True)
class LearningEvidence:
    student_id: str
    evidence_type: str
    occurred_at: datetime
    source_type: str
    source_id: str
    subject: str = ""
    knowledge_key: str = ""
    success: bool | None = None
    score: float | None = None
    context: str = ""

    def __post_init__(self) -> None:
        if not self.student_id.strip():
            raise ValueError("student_id required")
        if self.evidence_type not in EVIDENCE_TYPES:
            raise ValueError(f"unsupported evidence_type: {self.evidence_type}")
        if not self.source_type.strip() or not self.source_id.strip():
            raise ValueError("source_type and source_id required")
        if self.occurred_at.tzinfo is None:
            raise ValueError("occurred_at must be timezone-aware")
        if self.score is not None and not 0 <= float(self.score) <= 100:
            raise ValueError("score must be between 0 and 100")

    def as_dict(self) -> dict[str, Any]:
        return {
            "studentId": self.student_id,
            "evidenceType": self.evidence_type,
            "occurredAt": self.occurred_at.isoformat(),
            "sourceType": self.source_type,
            "sourceId": self.source_id,
            "subject": self.subject,
            "knowledgeKey": self.knowledge_key,
            "success": self.success,
            "score": self.score,
            "context": self.context,
        }


def evidence_dimensions(items: Iterable[LearningEvidence]) -> set[str]:
    return {item.evidence_type for item in items}


def _single_student_id(items: list[LearningEvidence]) -> str | None:
    if not items:
        return None
    ids = {item.student_id for item in items}
    if len(ids) != 1:
        raise ValueError("evidence_state requires one student_id")
    return next(iter(ids))


def evidence_state(items: Iterable[LearningEvidence]) -> dict[str, Any]:
    """Describe evidence coverage for one student's continuous record.

    The result is deliberately conservative: even when all four evidence
    dimensions are present, mastery is not inferred automatically.
    """
    rows = list(items)
    student_id = _single_student_id(rows)
    dimensions = evidence_dimensions(rows)

    if not rows:
        state = "evidence_insufficient"
    elif {"performance", "independent", "retention", "transfer"} <= dimensions:
        state = "stable_evidence_available"
    elif {"performance", "independent"} <= dimensions:
        state = "basic_evidence_available"
    else:
        state = "learning_evidence_available"

    return {
        "studentId": student_id,
        "state": state,
        "sampleCount": len(rows),
        "dimensions": sorted(dimensions),
        "stableMasteryInferred": False,
    }


__all__ = [
    "EVIDENCE_TYPES",
    "LearningEvidence",
    "evidence_dimensions",
    "evidence_state",
]
