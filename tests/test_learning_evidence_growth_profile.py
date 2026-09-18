from copy import deepcopy

from changying.domain.learning_evidence_growth_profile import (
    attach_learning_evidence,
    growth_profile_learning_evidence,
)


def snapshot():
    return {
        "studentId": "7",
        "state": "basic_evidence_available",
        "sampleCount": 3,
        "dimensions": ["independent", "performance"],
        "subjects": [
            {
                "subject": "数学",
                "sampleCount": 3,
                "averageObservedScore": 82.3,
                "observedSuccessRate": 66.7,
                "latestAt": "2026-09-18T08:00:00+00:00",
            }
        ],
        "knowledge": [
            {
                "subject": "数学",
                "knowledgeKey": "分数加法",
                "sampleCount": 2,
                "averageObservedScore": 75.0,
                "observedSuccessRate": 50.0,
                "latestAt": "2026-09-18T08:00:00+00:00",
                "evidenceTypes": ["performance"],
            }
        ],
        "recentEvidence": [
            {
                "occurredAt": "2026-09-18T08:00:00+00:00",
                "evidenceType": "performance",
                "subject": "数学",
                "knowledgeKey": "分数加法",
                "success": True,
                "score": 100.0,
                "sourceType": "submission_answer",
                "sourceId": "91:question:11",
                "context": "assignment:33 · class:5",
            }
        ],
        "masteryInferred": False,
        "stableMasteryInferred": False,
    }


def legacy_profile():
    return {
        "student": {"id": 7, "name": "小明"},
        "academic": {
            "avgScore": 82,
            "weakKnowledge": [{"knowledge": "分数加法", "accuracy": 62}],
        },
        "suggestions": ["继续观察"],
        "timeline": [{"type": "academic", "title": "学习成绩"}],
    }


def test_adapter_adds_learning_evidence_without_rewriting_legacy_fields():
    original = legacy_profile()
    before = deepcopy(original)

    result = attach_learning_evidence(original, snapshot())

    assert original == before
    assert result["student"] == before["student"]
    assert result["academic"] == before["academic"]
    assert result["suggestions"] == before["suggestions"]
    assert result["timeline"] == before["timeline"]
    assert "learningEvidence" not in original
    assert "learningEvidence" in result


def test_learning_evidence_section_keeps_stable_student_identity():
    section = growth_profile_learning_evidence(snapshot())
    assert section["studentId"] == "7"
    assert section["sampleCount"] == 3
    assert section["dimensions"] == ["independent", "performance"]
    assert section["contractVersion"] == "v1.1-evidence-read-model"


def test_adapter_never_exports_mastery_conclusion():
    section = growth_profile_learning_evidence(
        {
            **snapshot(),
            "masteryInferred": True,
            "stableMasteryInferred": True,
        }
    )
    assert section["masteryInferred"] is False
    assert section["stableMasteryInferred"] is False


def test_adapter_does_not_create_legacy_weak_or_suggestion_fields():
    section = growth_profile_learning_evidence(snapshot())
    assert "weakKnowledge" not in section
    assert "suggestions" not in section
    assert "diagnosis" not in section
    assert "mastery" not in section


def test_empty_snapshot_is_explicit_not_silent():
    section = growth_profile_learning_evidence({})
    assert section == {
        "studentId": None,
        "state": "evidence_insufficient",
        "sampleCount": 0,
        "dimensions": [],
        "subjects": [],
        "knowledge": [],
        "recentEvidence": [],
        "masteryInferred": False,
        "stableMasteryInferred": False,
        "contractVersion": "v1.1-evidence-read-model",
    }


def test_adapter_is_shallow_compatible_for_unknown_legacy_fields():
    original = {"student": {"id": 7}, "futureLegacyField": {"keep": True}}
    result = attach_learning_evidence(original, snapshot())
    assert result["futureLegacyField"] == {"keep": True}
