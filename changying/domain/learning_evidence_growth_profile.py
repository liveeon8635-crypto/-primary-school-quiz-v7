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


__all__ = [
    "attach_learning_evidence",
    "growth_profile_learning_evidence",
]
