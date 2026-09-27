"""Additive adapter from the V1.1 evidence read model to growth-profile JSON.

This adapter is intentionally non-destructive. It produces a new
learningEvidence section and never rewrites the existing academic,
suggestions or timeline fields. Consumers can adopt the new evidence
model incrementally without changing legacy behavior.
"""

from __future__ import annotations

from typing import Any, Mapping


def growth_profile_learning_evidence(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    """Return a stable, descriptive-only growth-profile evidence section."""
    return {
        "studentId": snapshot.get("studentId"),
        "state": snapshot.get("state", "evidence_insufficient"),
        "sampleCount": int(snapshot.get("sampleCount", 0) or 0),
        "dimensions": list(snapshot.get("dimensions") or []),
        "subjects": list(snapshot.get("subjects") or []),
        "knowledge": list(snapshot.get("knowledge") or []),
        "recentEvidence": list(snapshot.get("recentEvidence") or []),
        "masteryInferred": False,
        "stableMasteryInferred": False,
        "contractVersion": "v1.1-evidence-read-model",
    }


def attach_learning_evidence(
    growth_profile: Mapping[str, Any],
    snapshot: Mapping[str, Any],
) -> dict[str, Any]:
    """Return a shallow-compatible growth profile with one additive field."""
    result = dict(growth_profile)
    result["learningEvidence"] = growth_profile_learning_evidence(snapshot)
    return result


# 人教版小学数学教材版本与知识模块目录。
# 2024 年秋季起使用的最新人教版对五年级部分单元做了调整：
# 原“简易方程”单元已并入“用字母表示数/方程”相关编排，
# 原“位置”单元已调整为“位置（用数对确定位置）”并前移。
# 这里给出与最新教材一致的模块名称，供“知识模块练习”按版本展示。
TEXTBOOK_EDITION_RENMIN_2024 = "renmin-2024"

_GRADE5_KNOWLEDGE_MODULES_RENMIN_2024: tuple[dict[str, Any], ...] = (
    {
        "moduleId": "g5-numbers-and-algebra",
        "name": "用字母表示数与方程",
        "legacyNames": ("简易方程",),
        "revisedInEdition": TEXTBOOK_EDITION_RENMIN_2024,
    },
    {
        "moduleId": "g5-position-number-pair",
        "name": "位置（用数对确定位置）",
        "legacyNames": ("位置",),
        "revisedInEdition": TEXTBOOK_EDITION_RENMIN_2024,
    },
)


def grade5_knowledge_modules(textbook_edition: str | None = None) -> list[dict[str, Any]]:
    """Return Grade-5 knowledge modules aligned with the given textbook edition.

    When the caller requests the latest 人教版 edition, the revised module
    names are returned so the practice list no longer shows the outdated
    “简易方程” / “位置” labels. For any other/unknown edition the legacy
    names are preserved for backward compatibility.
    """
    use_latest = textbook_edition == TEXTBOOK_EDITION_RENMIN_2024
    modules: list[dict[str, Any]] = []
    for module in _GRADE5_KNOWLEDGE_MODULES_RENMIN_2024:
        legacy = list(module.get("legacyNames") or [])
        modules.append(
            {
                "moduleId": module["moduleId"],
                "name": module["name"] if use_latest else (legacy[0] if legacy else module["name"]),
                "textbookEdition": textbook_edition or "legacy",
                "revised": use_latest,
            }
        )
    return modules


__all__ = [
    "TEXTBOOK_EDITION_RENMIN_2024",
    "attach_learning_evidence",
    "grade5_knowledge_modules",
    "growth_profile_learning_evidence",
]
