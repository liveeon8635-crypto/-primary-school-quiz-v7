from changying.domain.guardian_readmodel import (
    guardian_ids_from_legacy,
    guardian_links_from_legacy,
)
from changying.domain.student_continuity import (
    GuardianLinkStatus,
    GuardianRelationship,
)


def test_legacy_guardians_project_to_active_links_without_storage_write():
    rows = [
        {"id": 8, "relationship": "母亲", "is_primary_contact": True},
        {"account_id": "11", "relation": "grandparent"},
    ]

    links = guardian_links_from_legacy(42, rows)

    assert [link.guardian_account_id for link in links] == [8, 11]
    assert all(link.student_id == 42 for link in links)
    assert all(link.status is GuardianLinkStatus.ACTIVE for link in links)
    assert links[0].relationship is GuardianRelationship.PARENT
    assert links[0].is_primary_contact is True
    assert links[1].relationship is GuardianRelationship.GRANDPARENT


def test_readmodel_deduplicates_accounts_and_ignores_invalid_ids():
    rows = [
        {"id": 8, "relationship": "父亲"},
        {"user_id": 8, "relationship": "parent"},
        {"id": None},
        {"id": 0},
        {"id": "not-an-id"},
    ]

    assert guardian_ids_from_legacy(42, rows) == (8,)


def test_unknown_relationship_stays_explicitly_other_guardian():
    [link] = guardian_links_from_legacy(42, [{"id": 9, "relationship": "姑姑"}])
    assert link.relationship is GuardianRelationship.OTHER_GUARDIAN


def test_invalid_student_id_returns_no_projection():
    assert guardian_links_from_legacy(0, [{"id": 8}]) == ()
    assert guardian_links_from_legacy("bad", [{"id": 8}]) == ()
