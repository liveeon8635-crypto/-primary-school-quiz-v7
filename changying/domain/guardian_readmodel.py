"""Read-only guardian projections for the V1 continuous student record.

Legacy endpoints already expose guardian/parent rows in several shapes.  This
module normalizes those rows into the storage-neutral GuardianLink contract
without changing database rows or granting authorization.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from changying.domain.student_continuity import (
    GuardianLink,
    GuardianLinkStatus,
    GuardianRelationship,
)

_RELATIONSHIP_ALIASES = {
    "parent": GuardianRelationship.PARENT,
    "父亲": GuardianRelationship.PARENT,
    "母亲": GuardianRelationship.PARENT,
    "家长": GuardianRelationship.PARENT,
    "grandparent": GuardianRelationship.GRANDPARENT,
    "祖父": GuardianRelationship.GRANDPARENT,
    "祖母": GuardianRelationship.GRANDPARENT,
    "外祖父": GuardianRelationship.GRANDPARENT,
    "外祖母": GuardianRelationship.GRANDPARENT,
}


def _positive_int(value: Any) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _relationship(value: Any) -> GuardianRelationship:
    key = str(value or "").strip().lower()
    return _RELATIONSHIP_ALIASES.get(key, GuardianRelationship.OTHER_GUARDIAN)


def guardian_links_from_legacy(
    student_id: int,
    rows: Iterable[Mapping[str, Any]] | None,
) -> tuple[GuardianLink, ...]:
    """Normalize legacy guardian rows into active read-only relationship links.

    Invalid/missing account ids are ignored. Duplicate account ids are collapsed
    so one student cannot render the same guardian twice. Legacy rows represent
    already-established relationships, therefore they project as ACTIVE; this
    function never writes that state back to storage.
    """

    stable_student_id = _positive_int(student_id)
    if stable_student_id is None:
        return ()

    links: list[GuardianLink] = []
    seen: set[int] = set()
    for row in rows or ():
        account_id = _positive_int(
            row.get("guardian_account_id")
            or row.get("account_id")
            or row.get("user_id")
            or row.get("id")
        )
        if account_id is None or account_id in seen:
            continue
        seen.add(account_id)
        links.append(
            GuardianLink(
                student_id=stable_student_id,
                guardian_account_id=account_id,
                relationship=_relationship(row.get("relationship") or row.get("relation")),
                status=GuardianLinkStatus.ACTIVE,
                is_primary_contact=bool(row.get("is_primary_contact") or row.get("primary")),
            )
        )
    return tuple(links)


def guardian_ids_from_legacy(
    student_id: int,
    rows: Iterable[Mapping[str, Any]] | None,
) -> tuple[int, ...]:
    """Return stable guardian account ids for StudentRecordRef projections."""

    return tuple(link.guardian_account_id for link in guardian_links_from_legacy(student_id, rows))


__all__ = ["guardian_ids_from_legacy", "guardian_links_from_legacy"]
