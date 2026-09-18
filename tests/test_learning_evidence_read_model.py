from datetime import datetime, timedelta, timezone

import pytest

from changying.domain.learning_evidence import LearningEvidence
from changying.domain.learning_evidence_read_model import student_evidence_snapshot


BASE = datetime(2026, 9, 1, 8, 0, tzinfo=timezone.utc)


def ev(
    *,
    student_id: str = "7",
    days: int = 0,
    kind: str = "performance",
    subject: str = "数学",
    knowledge: str = "分数加法",
    success: bool | None = True,
    score: float | None = 90,
    source_id: str = "s1",
    context: str = "",
) -> LearningEvidence:
    return LearningEvidence(
        student_id=student_id,
        evidence_type=kind,
        occurred_at=BASE + timedelta(days=days),
        source_type="submission",
        source_id=source_id,
        subject=subject,
        knowledge_key=knowledge,
        success=success,
        score=score,
        context=context,
    )


def test_snapshot_keeps_one_stable_student_identity_across_grade_contexts():
    snapshot = student_evidence_snapshot([
        ev(days=0, source_id="g5", context="五年级A班"),
        ev(days=180, source_id="g6", context="六年级C班"),
    ])
    assert snapshot["studentId"] == "7"
    assert snapshot["sampleCount"] == 2
    assert snapshot["recentEvidence"][0]["sourceId"] == "g6"
    assert snapshot["recentEvidence"][1]["sourceId"] == "g5"


def test_snapshot_never_infers_mastery_from_coverage_or_scores():
    snapshot = student_evidence_snapshot([
        ev(kind="performance", source_id="p"),
        ev(kind="independent", source_id="i"),
        ev(kind="retention", source_id="r"),
        ev(kind="transfer", source_id="t"),
    ])
    assert snapshot["state"] == "stable_evidence_available"
    assert snapshot["stableMasteryInferred"] is False
    assert snapshot["masteryInferred"] is False


def test_subject_summary_reports_only_observed_metrics():
    snapshot = student_evidence_snapshot([
        ev(score=80, success=True, source_id="a"),
        ev(score=60, success=False, source_id="b"),
        ev(subject="语文", knowledge="阅读概括", score=None, success=None, source_id="c"),
    ])
    math = next(x for x in snapshot["subjects"] if x["subject"] == "数学")
    chinese = next(x for x in snapshot["subjects"] if x["subject"] == "语文")
    assert math["averageObservedScore"] == 70.0
    assert math["observedSuccessRate"] == 50.0
    assert chinese["averageObservedScore"] is None
    assert chinese["observedSuccessRate"] is None


def test_knowledge_summary_keeps_evidence_types_and_latest_time():
    snapshot = student_evidence_snapshot([
        ev(kind="performance", days=0, score=70, source_id="a"),
        ev(kind="retention", days=7, score=90, source_id="b"),
    ])
    row = snapshot["knowledge"][0]
    assert row["knowledgeKey"] == "分数加法"
    assert row["sampleCount"] == 2
    assert row["averageObservedScore"] == 80.0
    assert row["evidenceTypes"] == ["performance", "retention"]
    assert row["latestAt"].startswith("2026-09-08")


def test_recent_limit_is_bounded_and_sorted_newest_first():
    snapshot = student_evidence_snapshot(
        [
            ev(days=0, source_id="a"),
            ev(days=1, source_id="b"),
            ev(days=2, source_id="c"),
        ],
        recent_limit=2,
    )
    assert [x["sourceId"] for x in snapshot["recentEvidence"]] == ["c", "b"]


def test_zero_recent_limit_returns_empty_timeline():
    snapshot = student_evidence_snapshot([ev()], recent_limit=0)
    assert snapshot["recentEvidence"] == []


def test_negative_recent_limit_is_rejected():
    with pytest.raises(ValueError, match="recent_limit"):
        student_evidence_snapshot([ev()], recent_limit=-1)


def test_mixed_students_are_rejected_instead_of_blended():
    with pytest.raises(ValueError, match="one student_id"):
        student_evidence_snapshot([
            ev(student_id="7", source_id="a"),
            ev(student_id="8", source_id="b"),
        ])


def test_blank_subject_is_visible_as_unlabeled_not_dropped():
    snapshot = student_evidence_snapshot([
        ev(subject="", knowledge="", source_id="a"),
    ])
    assert snapshot["subjects"][0]["subject"] == "未标注学科"
    assert snapshot["knowledge"] == []
