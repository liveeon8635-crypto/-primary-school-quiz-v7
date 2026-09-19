from changying.domain.learning_evidence_export import (
    learning_evidence_export_payload,
)


def evidence():
    return {
        "state": "stable_evidence_available",
        "sampleCount": 4,
        "dimensions": ["independent", "performance", "retention", "transfer"],
        "subjects": [
            {
                "subject": "数学",
                "sampleCount": 4,
                "averageObservedScore": 88.0,
                "observedSuccessRate": 75.0,
                "latestAt": "2026-09-18T10:00:00+00:00",
            }
        ],
        "knowledge": [
            {
                "subject": "数学",
                "knowledgeKey": "分数加法",
                "sampleCount": 3,
                "averageObservedScore": 88.0,
                "observedSuccessRate": 66.7,
                "latestAt": "2026-09-18T10:00:00+00:00",
                "evidenceTypes": ["performance", "retention"],
            }
        ],
        "recentEvidence": [
            {
                "occurredAt": "2026-09-18T10:00:00+00:00",
                "evidenceType": "retention",
                "subject": "数学",
                "knowledgeKey": "分数加法",
                "success": True,
                "score": None,
                "sourceType": "teacher_observation",
                "sourceId": "teacher-evidence:99",
                "context": "教师内部观察原文-不进入普通成长报告",
            }
        ],
        "masteryInferred": False,
    }


def test_export_keeps_evidence_semantics_and_chinese_labels():
    result = learning_evidence_export_payload(evidence())
    assert result["stateName"] == "稳定证据集可用"
    assert result["sampleCount"] == 4
    assert result["dimensionNames"] == [
        "独立完成",
        "学习表现",
        "跨时保持",
        "迁移应用",
    ]
    assert result["masteryInferred"] is False
    assert "不自动形成掌握" in result["note"]


def test_general_growth_export_omits_internal_note_and_technical_ids():
    result = learning_evidence_export_payload(evidence())
    row = result["recentEvidence"][0]
    assert row == {
        "occurredAt": "2026-09-18T10:00:00+00:00",
        "evidenceType": "retention",
        "evidenceTypeName": "跨时保持",
        "subject": "数学",
        "knowledgeKey": "分数加法",
        "successName": "观察到成功表现",
        "score": None,
        "sourceName": "教师观察",
    }
    assert "context" not in row
    assert "sourceId" not in row
    assert "sourceType" not in row


def test_export_does_not_mutate_evidence_source():
    source = evidence()
    learning_evidence_export_payload(source)
    assert source["recentEvidence"][0]["sourceId"] == "teacher-evidence:99"
    assert "教师内部观察原文" in source["recentEvidence"][0]["context"]


def test_empty_evidence_has_explicit_non_diagnostic_state():
    result = learning_evidence_export_payload({})
    assert result["state"] == "evidence_insufficient"
    assert result["stateName"] == "证据不足"
    assert result["sampleCount"] == 0
    assert result["recentEvidence"] == []
    assert result["masteryInferred"] is False
