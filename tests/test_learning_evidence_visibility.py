from changying.domain.learning_evidence_visibility import (
    learning_evidence_for_role,
)


def sample():
    return {
        "studentId": "7",
        "state": "stable_evidence_available",
        "sampleCount": 4,
        "dimensions": ["independent", "performance", "retention", "transfer"],
        "subjects": [{"subject": "数学", "sampleCount": 4}],
        "knowledge": [{"subject": "数学", "knowledgeKey": "分数加法"}],
        "recentEvidence": [
            {
                "occurredAt": "2026-09-18T02:00:00+00:00",
                "evidenceType": "retention",
                "subject": "数学",
                "knowledgeKey": "分数加法",
                "success": True,
                "score": None,
                "sourceType": "teacher_observation",
                "sourceId": "teacher-evidence:31",
                "context": "周末课 · 教师记录：内部课堂观察原文-仅教师",
            }
        ],
        "masteryInferred": False,
        "stableMasteryInferred": False,
    }


def test_teacher_and_admin_keep_full_recent_evidence_details():
    for role in ("teacher", "admin"):
        result = learning_evidence_for_role(sample(), role)
        row = result["recentEvidence"][0]
        assert row["sourceType"] == "teacher_observation"
        assert row["sourceId"] == "teacher-evidence:31"
        assert "内部课堂观察原文-仅教师" in row["context"]


def test_parent_and_student_keep_same_semantics_but_not_internal_details():
    source = sample()
    for role in ("parent", "student"):
        result = learning_evidence_for_role(source, role)
        assert result["state"] == source["state"]
        assert result["sampleCount"] == source["sampleCount"]
        assert result["dimensions"] == source["dimensions"]
        assert result["subjects"] == source["subjects"]
        assert result["knowledge"] == source["knowledge"]
        assert result["masteryInferred"] is False
        row = result["recentEvidence"][0]
        assert row == {
            "occurredAt": "2026-09-18T02:00:00+00:00",
            "evidenceType": "retention",
            "subject": "数学",
            "knowledgeKey": "分数加法",
            "success": True,
            "score": None,
        }
        assert "sourceType" not in row
        assert "sourceId" not in row
        assert "context" not in row


def test_visibility_filter_does_not_mutate_full_source():
    source = sample()
    learning_evidence_for_role(source, "parent")
    row = source["recentEvidence"][0]
    assert row["sourceId"] == "teacher-evidence:31"
    assert "内部课堂观察原文-仅教师" in row["context"]


def test_unknown_role_defaults_to_shared_summary():
    result = learning_evidence_for_role(sample(), "unknown")
    row = result["recentEvidence"][0]
    assert "context" not in row
    assert "sourceId" not in row
    assert "sourceType" not in row
