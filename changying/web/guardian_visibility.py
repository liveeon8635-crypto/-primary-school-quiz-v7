"""Safe V1 presentation helpers for guardian relationships.

This module turns domain GuardianLink values into a minimal UI projection.  It
intentionally exposes relationship metadata only: credentials, authorization
state and unrelated account data never enter the student profile view model.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from changying.domain.guardian_readmodel import guardian_links_from_legacy
from changying.domain.student_continuity import GuardianLink, GuardianRelationship

_RELATIONSHIP_LABELS = {
    GuardianRelationship.PARENT: "家长",
    GuardianRelationship.GRANDPARENT: "祖辈监护人",
    GuardianRelationship.OTHER_GUARDIAN: "其他监护人",
}


def guardian_visibility(links: Iterable[GuardianLink]) -> dict[str, Any]:
    """Build the student-page guardian summary from already-authorized links."""

    active = tuple(link for link in links if link.active)
    return {
        "count": len(active),
        "items": tuple(
            {
                "guardianAccountID": link.guardian_account_id,
                "relationship": link.relationship.value,
                "relationshipLabel": _RELATIONSHIP_LABELS[link.relationship],
                "primary": link.is_primary_contact,
            }
            for link in active
        ),
    }


def guardian_visibility_from_legacy(
    student_id: int,
    rows: Iterable[Mapping[str, Any]] | None,
) -> dict[str, Any]:
    """Read-only legacy adapter suitable for the existing V1 student profile."""

    return guardian_visibility(guardian_links_from_legacy(student_id, rows))


__all__ = ["guardian_visibility", "guardian_visibility_from_legacy"]
