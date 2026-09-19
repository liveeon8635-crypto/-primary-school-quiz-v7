from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from changying.web.v22_evidence_coverage import teacher_evidence_coverage


class Column:
    def __eq__(self, other):
        return self

    def in_(self, other):
        return self

    def asc(self):
        return self


class SelectStub:
    def where(self, *args):
        return self

    def order_by(self, *args):
        return self


class ScalarsResult:
    def __init__(self, rows):
        self.rows = rows

    def all(self):
        return list(self.rows)


class FakeDB:
    def __init__(self, batches):
        self.batches = list(batches)
        self.calls = 0

    def scalars(self, stmt):
        rows = self.batches[self.calls]
        self.calls += 1
        return ScalarsResult(rows)


def implementation():
    def need(user, *roles):
        if user.role not in roles:
            raise HTTPException(403, "无权限")

    return SimpleNamespace(
        SchoolClass=SimpleNamespace(
            school_id=Column(),
            teacher_id=Column(),
            grade=Column(),
            id=Column(),
        ),
        ClassStudent=SimpleNamespace(class_id=Column()),
        User=SimpleNamespace(
            school_id=Column(),
            role=Column(),
            id=Column(),
            active=Column(),
        ),
        Submission=SimpleNamespace(
            school_id=Column(),
            student_id=Column(),
        ),
        LearningEvidenceEvent=SimpleNamespace(
            school_id=Column(),
            student_id=Column(),
        ),
        select=lambda model: SelectStub(),
        need=need,
        school_local_iso=lambda value: value,
    )


def test_coverage_is_batched_and_retracted_evidence_is_not_counted():
    klass = SimpleNamespace(id=1, name="五年级一班", grade=5, teacher_id=10)
    link = SimpleNamespace(class_id=1, student_id=7)
    student = SimpleNamespace(id=7, name="小明", grade=5, active=True)
    submission = SimpleNamespace(student_id=7, submitted_at="2026-09-19 09:00")
    independent = SimpleNamespace(
        id=101,
        student_id=7,
        event_kind="record",
        target_event_id=None,
        evidence_type="independent",
        occurred_at="2026-09-19 10:00",
    )
    retention = SimpleNamespace(
        id=102,
        student_id=7,
        event_kind="record",
        target_event_id=None,
        evidence_type="retention",
        occurred_at="2026-09-19 11:00",
    )
    retract = SimpleNamespace(
        id=103,
        student_id=7,
        event_kind="retract",
        target_event_id=102,
        evidence_type="retention",
        occurred_at="2026-09-19 12:00",
    )
    db = FakeDB([
        [klass],
        [link],
        [student],
        [submission],
        [independent, retention, retract],
    ])
    user = SimpleNamespace(id=10, school_id=1, role="teacher")

    body = teacher_evidence_coverage(implementation(), db, user)
    assert db.calls == 5
    row = body["students"][0]

    assert row["availableDimensions"] == ["independent", "performance"]
    assert row["missingDimensions"] == ["retention", "transfer"]
    assert row["sourceEventCount"] == 2
    assert row["automaticDiagnosis"] is False
    assert body["automaticDiagnosis"] is False
    assert body["automaticRanking"] is False
    assert "不等于学生不会" in body["boundary"]


def test_teacher_cannot_select_a_class_outside_visible_classes():
    klass = SimpleNamespace(id=1, name="五年级一班", grade=5, teacher_id=10)
    db = FakeDB([[klass]])
    user = SimpleNamespace(id=10, school_id=1, role="teacher")

    with pytest.raises(HTTPException) as exc:
        teacher_evidence_coverage(
            implementation(),
            db,
            user,
            class_id=999,
        )
    assert exc.value.status_code == 403


def test_parent_and_student_cannot_open_teacher_coverage():
    for role in ("parent", "student"):
        db = FakeDB([])
        user = SimpleNamespace(id=1, school_id=1, role=role)
        with pytest.raises(HTTPException) as exc:
            teacher_evidence_coverage(implementation(), db, user)
        assert exc.value.status_code == 403


def test_empty_visible_classes_returns_descriptive_empty_state():
    db = FakeDB([[]])
    user = SimpleNamespace(id=10, school_id=1, role="teacher")
    body = teacher_evidence_coverage(implementation(), db, user)

    assert body["students"] == []
    assert body["summary"]["studentCount"] == 0
    assert body["automaticDiagnosis"] is False
    assert body["automaticRanking"] is False
