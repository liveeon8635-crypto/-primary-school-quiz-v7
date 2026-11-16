"""Role-aware visibility for continuous learning evidence.

Teachers and admins may read the full evidence facts needed for instruction and
audit. Parents and students share the same evidence state and aggregate facts,
but teacher-internal observation context and technical source identifiers are
not exposed through shared views.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping


FULL_DETAIL_ROLES = frozenset({"teacher", "admin"})
SHARED_SUMMARY_ROLES = frozenset({"parent", "student"})

_SHARED_RECENT_KEYS = (
    "occurredAt",
    "evidenceType",
    "subject",
    "knowledgeKey",
    "success",
    "score",
)

# Shared views are built from this allowlist only: a field added later to the
# teacher-facing evidence must not leak to parents/students by default.
_SHARED_TOP_LEVEL_KEYS = (
    "studentId",
    "state",
    "sampleCount",
    "dimensions",
    "subjects",
    "knowledge",
    "recentEvidence",
    "masteryInferred",
    "stableMasteryInferred",
    "contractVersion",
)


def _shared_view(evidence: Mapping[str, Any]) -> dict[str, Any]:
    result = {
        key: deepcopy(evidence[key])
        for key in _SHARED_TOP_LEVEL_KEYS
        if key in evidence
    }
    recent = []
    for row in evidence.get("recentEvidence") or []:
        if not isinstance(row, Mapping):
            continue
        recent.append({key: deepcopy(row.get(key)) for key in _SHARED_RECENT_KEYS})
    result["recentEvidence"] = recent
    return result


def learning_evidence_for_role(
    evidence: Mapping[str, Any],
    role: str,
) -> dict[str, Any]:
    """Return evidence with role-appropriate detail without changing semantics."""
    if role in FULL_DETAIL_ROLES:
        return deepcopy(dict(evidence))

    if role in SHARED_SUMMARY_ROLES:
        return _shared_view(evidence)

    # Unknown roles are denied instead of silently receiving the shared view.
    raise PermissionError(f"unsupported role for learning evidence: {role!r}")


__all__ = [
    "FULL_DETAIL_ROLES",
    "SHARED_SUMMARY_ROLES",
    "learning_evidence_for_role",
]
