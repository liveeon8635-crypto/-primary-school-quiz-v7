"""Pure V1.1 learning-evidence rules.

This module defines a small, append-friendly evidence vocabulary for the
continuous student record.  It deliberately does not infer mastery from a
single score and does not write to production storage.
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


def evidence_state(items: Iterable[LearningEvidence]) -> dict[str, Any]:
    """Return a conservative state; stable mastery requires all dimensions.

    The function only describes evidence coverage.  It intentionally does not
    turn scores into an ability diagnosis.
    """
    rows = list(items)
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
