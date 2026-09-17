from changying.domain.student_continuity import (
    GuardianLink,
    GuardianLinkStatus,
    GuardianRelationship,
)
from changying.web.guardian_visibility import (
    guardian_visibility,
    guardian_visibility_from_legacy,
)


def test_visibility_exposes_only_relationship_metadata_for_active_links():
    summary = guardian_visibility(
        [
            GuardianLink(
                student_id=42,
                guardian_account_id=8,
                relationship=GuardianRelationship.PARENT,
                status=GuardianLinkStatus.ACTIVE,
                is_primary_contact=True,
            ),
            GuardianLink(
                student_id=42,
                guardian_account_id=11,
                relationship=GuardianRelationship.GRANDPARENT,
                status=GuardianLinkStatus.REVOKED,
            ),
        ]
    )

    assert summary == {
        "count": 1,
        "items": (
            {
                "guardianAccountID": 8,
                "relationship": "parent",
                "relationshipLabel": "家长",
                "primary": True,
            },
        ),
    }
    assert "password" not in repr(summary).lower()
    assert "token" not in repr(summary).lower()
    assert "permissions" not in repr(summary).lower()


def test_legacy_visibility_reuses_readmodel_deduplication():
    summary = guardian_visibility_from_legacy(
        42,
        [
            {"id": 8, "relationship": "母亲", "primary": True},
            {"user_id": 8, "relationship": "parent"},
            {"id": 9, "relationship": "姑姑"},
        ],
    )

    assert summary["count"] == 2
    assert [item["guardianAccountID"] for item in summary["items"]] == [8, 9]
    assert [item["relationshipLabel"] for item in summary["items"]] == ["家长", "其他监护人"]


def test_empty_or_invalid_legacy_rows_render_zero_guardians():
    assert guardian_visibility_from_legacy(42, None) == {"count": 0, "items": ()}
    assert guardian_visibility_from_legacy(0, [{"id": 8}]) == {"count": 0, "items": ()}
