import inspect

import app_v924 as legacy


def test_learning_evidence_event_table_is_registered_and_required():
    assert "learning_evidence_events" in legacy.Base.metadata.tables

    source = inspect.getsource(legacy.production_readiness_payload)
    assert '"learning_evidence_events"' in source


def test_learning_evidence_event_model_keeps_append_only_event_fields():
    table = legacy.LearningEvidenceEvent.__table__
    columns = set(table.columns.keys())

    assert {
        "id",
        "school_id",
        "student_id",
        "actor_id",
        "event_kind",
        "target_event_id",
        "evidence_type",
        "subject",
        "knowledge_key",
        "success",
        "note",
        "context",
        "source_type",
        "occurred_at",
        "created_at",
    } <= columns

    assert "updated_at" not in columns
    assert "deleted_at" not in columns


def test_learning_evidence_audit_actions_have_chinese_labels():
    assert legacy.AUDIT_ACTION_NAMES["learning.evidence.record"] == "记录学习证据"
    assert legacy.AUDIT_ACTION_NAMES["learning.evidence.retract"] == "撤回学习证据"
