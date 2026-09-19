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


def learning_evidence_for_role(
    evidence: Mapping[str, Any],
    role: str,
) -> dict[str, Any]:
    """Return evidence with role-appropriate detail without changing semantics."""
    result = deepcopy(dict(evidence))
    if role in FULL_DETAIL_ROLES:
        return result

    if role in SHARED_SUMMARY_ROLES:
        recent = []
        for row in result.get("recentEvidence") or []:
            if not isinstance(row, Mapping):
                continue
            recent.append(
                {
                    key: deepcopy(row.get(key))
                    for key in _SHARED_RECENT_KEYS
                }
            )
        result["recentEvidence"] = recent
        return result

    # Unknown roles get the conservative shared view.
    recent = []
    for row in result.get("recentEvidence") or []:
        if not isinstance(row, Mapping):
            continue
        recent.append(
            {
                key: deepcopy(row.get(key))
                for key in _SHARED_RECENT_KEYS
            }
        )
    result["recentEvidence"] = recent
    return result


__all__ = [
    "FULL_DETAIL_ROLES",
    "SHARED_SUMMARY_ROLES",
    "learning_evidence_for_role",
]
