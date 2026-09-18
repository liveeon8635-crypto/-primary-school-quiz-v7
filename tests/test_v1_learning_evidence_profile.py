from types import SimpleNamespace

from changying.web.v1_learning_evidence_profile import (
    install_v1_learning_evidence_profile,
)


def test_installer_adds_learning_evidence_without_mutating_legacy_fields(monkeypatch):
    legacy = {
        "student": {"id": 7, "name": "小明"},
        "academic": {"avgScore": 82},
        "suggestions": ["继续观察"],
        "timeline": [{"title": "学习成绩"}],
    }

    impl = SimpleNamespace(
        student_growth_profile_data=lambda db, stu, school_id, class_id=None: dict(legacy),
    )
    stu = SimpleNamespace(id=7)

    monkeypatch.setattr(
        "changying.web.v1_learning_evidence_profile.legacy_student_evidence",
        lambda implementation, db, student_id, school_id: [],
    )

    install_v1_learning_evidence_profile(impl)
    result = impl.student_growth_profile_data(object(), stu, 3)

    assert result["student"] == legacy["student"]
    assert result["academic"] == legacy["academic"]
    assert result["suggestions"] == legacy["suggestions"]
    assert result["timeline"] == legacy["timeline"]
    assert result["learningEvidence"]["studentId"] is None
    assert result["learningEvidence"]["state"] == "evidence_insufficient"
    assert result["learningEvidence"]["masteryInferred"] is False


def test_installer_is_idempotent(monkeypatch):
    calls = {"legacy": 0}

    def legacy_profile(db, stu, school_id, class_id=None):
        calls["legacy"] += 1
        return {"student": {"id": stu.id}}

    impl = SimpleNamespace(student_growth_profile_data=legacy_profile)
    monkeypatch.setattr(
        "changying.web.v1_learning_evidence_profile.legacy_student_evidence",
        lambda implementation, db, student_id, school_id: [],
    )

    install_v1_learning_evidence_profile(impl)
    first = impl.student_growth_profile_data
    install_v1_learning_evidence_profile(impl)
    second = impl.student_growth_profile_data

    assert first is second
    second(object(), SimpleNamespace(id=7), 3)
    assert calls["legacy"] == 1


def test_evidence_failure_falls_back_to_legacy_profile(monkeypatch):
    legacy = {
        "student": {"id": 7},
        "academic": {"avgScore": 88},
        "futureField": {"keep": True},
    }
    impl = SimpleNamespace(
        student_growth_profile_data=lambda db, stu, school_id, class_id=None: dict(legacy),
    )

    def fail(*args, **kwargs):
        raise RuntimeError("legacy evidence read failed")

    monkeypatch.setattr(
        "changying.web.v1_learning_evidence_profile.legacy_student_evidence",
        fail,
    )

    install_v1_learning_evidence_profile(impl)
    result = impl.student_growth_profile_data(
        object(),
        SimpleNamespace(id=7),
        3,
    )
    assert result == legacy
    assert "learningEvidence" not in result


def test_installer_keeps_mastery_conclusion_disabled(monkeypatch):
    from datetime import datetime, timezone

    from changying.domain.learning_evidence import LearningEvidence

    item = LearningEvidence(
        student_id="7",
        evidence_type="performance",
        occurred_at=datetime(2026, 9, 18, tzinfo=timezone.utc),
        source_type="submission",
        source_id="91",
        subject="数学",
        score=100,
    )

    impl = SimpleNamespace(
        student_growth_profile_data=lambda db, stu, school_id, class_id=None: {
            "student": {"id": stu.id}
        },
    )
    monkeypatch.setattr(
        "changying.web.v1_learning_evidence_profile.legacy_student_evidence",
        lambda implementation, db, student_id, school_id: [item],
    )

    install_v1_learning_evidence_profile(impl)
    result = impl.student_growth_profile_data(
        object(),
        SimpleNamespace(id=7),
        3,
    )
    assert result["learningEvidence"]["sampleCount"] == 1
    assert result["learningEvidence"]["masteryInferred"] is False
    assert result["learningEvidence"]["stableMasteryInferred"] is False
