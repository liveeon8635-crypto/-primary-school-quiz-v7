from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

from changying.services.classroom_review import (
    classroom_interaction_summary,
    classroom_review_summary,
)
from changying.web.v1_classroom_execution import _iso as execution_iso
from changying.web.v1_classroom_handout_release import _iso as release_iso
from changying.web.v1_classroom_presentation_review import _iso as presentation_iso
from changying.web.v1_classroom_quick_check import _iso as quick_check_iso
from changying.web.v1_classroom_review import _draft_payload


def test_classroom_review_student_and_assignment_times_are_school_local():
    utc_time = datetime(2026, 9, 22, 2, 5)
    assignment = SimpleNamespace(
        id=9,
        title="课堂练习",
        due_date="2026-09-22",
        created_at=utc_time,
    )
    class_row = SimpleNamespace(id=2, name="五年级1班", grade=5)
    paper = SimpleNamespace(
        id=3,
        title="第一单元",
        subject="语文",
        textbook="人教版",
        unit="第一单元",
    )
    student = SimpleNamespace(id=1, name="学生甲")
    submission = SimpleNamespace(
        id=11,
        student_id=1,
        submitted_at=utc_time,
        score=100,
        correct=0,
        total=0,
        answers_json="[]",
    )

    result = classroom_review_summary(
        assignment=assignment,
        class_row=class_row,
        paper=paper,
        recipients=[student],
        submissions=[submission],
        questions=[],
    )

    assert result["assignment"]["createdAt"] == "2026-09-22 10:05"
    assert result["students"][0]["submittedAt"] == "2026-09-22 10:05"


def test_classroom_interaction_times_are_school_local():
    utc_start = datetime(2026, 9, 22, 2, 0)
    utc_end = datetime(2026, 9, 22, 2, 40)
    result = classroom_interaction_summary(
        session=SimpleNamespace(
            id=7,
            title="课堂执行",
            status="completed",
            started_at=utc_start,
            completed_at=utc_end,
        ),
        segments=[],
        quick_checks=[],
        responses=[],
        presenter_turns=[],
        presentation_reviews=[],
    )
    assert result["session"]["startedAt"] == "2026-09-22 10:00"
    assert result["session"]["completedAt"] == "2026-09-22 10:40"


def test_classroom_web_payload_helpers_share_school_local_time_contract():
    utc_time = datetime(2026, 9, 22, 2, 5)
    expected = "2026-09-22 10:05"
    assert execution_iso(utc_time) == expected
    assert quick_check_iso(utc_time) == expected
    assert release_iso(utc_time) == expected
    assert presentation_iso(utc_time) == expected

    draft = _draft_payload(
        {
            "id": 1,
            "assignment_id": 32,
            "title": "复盘讲义",
            "selected_knowledge_json": "[]",
            "selected_question_ids_json": "[]",
            "teacher_notes": "",
            "content_text": "正文",
            "created_at": utc_time,
            "updated_at": utc_time,
        }
    )
    assert draft is not None
    assert draft["createdAt"] == expected
    assert draft["updatedAt"] == expected
