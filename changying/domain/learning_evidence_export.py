"""Safe export payload for standardized learning evidence.

The general growth report is often downloaded and shared. It therefore exports
evidence coverage and observed facts, but deliberately omits teacher-internal
context, technical source identifiers, and raw teacher observation notes.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping


STATE_LABELS = {
    "evidence_insufficient": "证据不足",
    "learning_evidence_available": "已有学习证据",
    "basic_evidence_available": "基础证据可用",
    "stable_evidence_available": "稳定证据集可用",
}

DIMENSION_LABELS = {
    "performance": "学习表现",
    "independent": "独立完成",
    "retention": "跨时保持",
    "transfer": "迁移应用",
}

SOURCE_LABELS = {
    "submission": "作业/测验",
    "submission_answer": "逐题作答",
    "teacher_observation": "教师观察",
}


def _success_text(value: Any) -> str:
    if value is True:
        return "观察到成功表现"
    if value is False:
        return "本次未观察到成功表现"
    return "未记录成功/失败"


def learning_evidence_export_payload(
    evidence: Mapping[str, Any],
) -> dict[str, Any]:
    """Return a share-safe, descriptive export model."""
    dimensions = list(evidence.get("dimensions") or [])
    recent_rows = []
    for row in evidence.get("recentEvidence") or []:
        if not isinstance(row, Mapping):
            continue
        recent_rows.append(
            {
                "occurredAt": row.get("occurredAt") or "",
                "evidenceType": row.get("evidenceType") or "",
                "evidenceTypeName": DIMENSION_LABELS.get(
                    row.get("evidenceType") or "",
                    row.get("evidenceType") or "未标注证据",
                ),
                "subject": row.get("subject") or "",
                "knowledgeKey": row.get("knowledgeKey") or "",
                "successName": _success_text(row.get("success")),
                "score": row.get("score"),
                "sourceName": SOURCE_LABELS.get(
                    row.get("sourceType") or "",
                    "学习记录",
                ),
            }
        )

    return {
        "state": evidence.get("state") or "evidence_insufficient",
        "stateName": STATE_LABELS.get(
            evidence.get("state") or "evidence_insufficient",
            "证据状态未标注",
        ),
        "sampleCount": int(evidence.get("sampleCount") or 0),
        "dimensions": dimensions,
        "dimensionNames": [
            DIMENSION_LABELS.get(value, value)
            for value in dimensions
        ],
        "subjects": deepcopy(list(evidence.get("subjects") or [])),
        "knowledge": deepcopy(list(evidence.get("knowledge") or [])),
        "recentEvidence": recent_rows,
        "masteryInferred": False,
        "note": "本页描述系统已记录的学习证据，不自动形成掌握、能力诊断或分流结论。",
    }


__all__ = [
    "DIMENSION_LABELS",
    "SOURCE_LABELS",
    "STATE_LABELS",
    "learning_evidence_export_payload",
]
