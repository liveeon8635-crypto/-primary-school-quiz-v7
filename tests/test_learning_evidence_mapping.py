from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from changying.domain.learning_evidence_mapping import (
    LEGACY_INFERRED_EVIDENCE_TYPES,
    legacy_utc,
    submission_answers_to_performance_evidence,
    submission_to_performance_evidence,
)


def submission(**overrides):
    values = {
        "id": 91,
        "student_id": 7,
        "assignment_id": 33,
        "score": 86,
        "submitted_at": datetime(2026, 9, 1, 9, 30),
        "answers_json": (
            '[{"question_id":11,"selected_index":1,"correct":true},'
            '{"question_id":12,"selected_index":0,"correct":false}]'
        ),
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_legacy_mapping_only_infers_observed_performance():
    assert LEGACY_INFERRED_EVIDENCE_TYPES == frozenset({"performance"})


def test_submission_summary_keeps_stable_student_identity_and_traceability():
    item = submission_to_performance_evidence(
        submission(),
        subject="数学",
        class_id=5,
        context="五年级A班",
    )
    assert item.student_id == "7"
    assert item.evidence_type == "performance"
    assert item.source_type == "submission"
    assert item.source_id == "91"
    assert item.score == 86
    assert item.success is None
    assert "assignment:33" in item.context
    assert "class:5" in item.context


def test_naive_legacy_timestamp_is_interpreted_as_utc():
    item = submission_to_performance_evidence(submission())
    assert item.occurred_at.tzinfo == timezone.utc
    assert item.occurred_at.isoformat() == "2026-09-01T09:30:00+00:00"


def test_aware_timestamp_keeps_original_instant_and_offset():
    tz = timezone(timedelta(hours=8))
    value = datetime(2026, 9, 1, 17, 30, tzinfo=tz)
    assert legacy_utc(value) is value


def test_answer_rows_map_only_to_known_knowledge_performance():
    items = submission_answers_to_performance_evidence(
        submission(),
        question_knowledge={11: "分数加法", 12: "分数减法"},
        subject="数学",
        class_id=5,
    )
    assert [x.knowledge_key for x in items] == ["分数加法", "分数减法"]
    assert [x.success for x in items] == [True, False]
    assert [x.score for x in items] == [100.0, 0.0]
    assert all(x.student_id == "7" for x in items)
    assert all(x.evidence_type == "performance" for x in items)
    assert [x.source_id for x in items] == ["91:question:11", "91:question:12"]


def test_unknown_or_ambiguous_answer_rows_are_skipped_not_guessed():
    row = submission(
        answers_json=(
            '[{"question_id":11,"correct":true},'
            '{"question_id":12},'
            '{"question_id":"13","correct":false},'
            '{"question_id":14,"correct":true}]'
        )
    )
    items = submission_answers_to_performance_evidence(
        row,
        question_knowledge={11: "小数乘法", 14: ""},
    )
    assert len(items) == 1
    assert items[0].knowledge_key == "小数乘法"


def test_invalid_legacy_json_yields_no_question_evidence():
    row = submission(answers_json="{not-json")
    assert submission_answers_to_performance_evidence(
        row,
        question_knowledge={11: "分数加法"},
    ) == []


def test_class_or_grade_context_does_not_change_student_identity():
    old = submission_to_performance_evidence(
        submission(id=91),
        class_id=5,
        context="五年级A班",
    )
    later = submission_to_performance_evidence(
        submission(id=126, assignment_id=48, submitted_at=datetime(2027, 3, 2, 8, 0)),
        class_id=9,
        context="六年级C班",
    )
    assert old.student_id == later.student_id == "7"
    assert old.source_id != later.source_id


def test_mapping_never_synthesizes_retention_transfer_or_independence():
    summary = submission_to_performance_evidence(submission())
    answers = submission_answers_to_performance_evidence(
        submission(),
        question_knowledge={11: "分数加法", 12: "分数减法"},
    )
    kinds = {summary.evidence_type}
    kinds.update(x.evidence_type for x in answers)
    assert kinds == {"performance"}
