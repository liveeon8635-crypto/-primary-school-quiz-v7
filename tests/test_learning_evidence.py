from datetime import datetime, timezone

import pytest

from changying.domain.learning_evidence import LearningEvidence, evidence_state


def evidence(kind: str, *, student_id: str = "student-1") -> LearningEvidence:
    return LearningEvidence(
        student_id=student_id,
        evidence_type=kind,
        occurred_at=datetime(2026, 9, 16, 8, 0, tzinfo=timezone.utc),
        source_type="assignment",
        source_id=f"source-{kind}",
        subject="math",
        knowledge_key="fraction-addition",
        success=True,
        score=90,
    )


def test_empty_evidence_is_insufficient():
    state = evidence_state([])
    assert state["state"] == "evidence_insufficient"
    assert state["stableMasteryInferred"] is False


def test_single_high_score_never_becomes_stable_mastery():
    state = evidence_state([evidence("performance")])
    assert state["state"] == "learning_evidence_available"
    assert state["stableMasteryInferred"] is False


def test_performance_plus_independent_marks_basic_evidence_only():
    state = evidence_state([evidence("performance"), evidence("independent")])
    assert state["state"] == "basic_evidence_available"
    assert state["stableMasteryInferred"] is False


def test_all_four_dimensions_only_mark_stable_evidence_available():
    state = evidence_state([
        evidence("performance"),
        evidence("independent"),
        evidence("retention"),
        evidence("transfer"),
    ])
    assert state["state"] == "stable_evidence_available"
    assert state["stableMasteryInferred"] is False


def test_student_id_is_required():
    with pytest.raises(ValueError, match="student_id required"):
        evidence("performance", student_id="")


def test_unknown_dimension_is_rejected():
    with pytest.raises(ValueError, match="unsupported evidence_type"):
        evidence("confidence")


def test_naive_timestamp_is_rejected():
    with pytest.raises(ValueError, match="timezone-aware"):
        LearningEvidence(
            student_id="student-1",
            evidence_type="performance",
            occurred_at=datetime(2026, 9, 16, 8, 0),
            source_type="assignment",
            source_id="a-1",
        )


def test_score_range_is_bounded():
    with pytest.raises(ValueError, match="score must be between"):
        LearningEvidence(
            student_id="student-1",
            evidence_type="performance",
            occurred_at=datetime.now(timezone.utc),
            source_type="assignment",
            source_id="a-1",
            score=101,
        )
