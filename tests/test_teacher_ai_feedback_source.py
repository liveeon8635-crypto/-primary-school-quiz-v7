from pathlib import Path

from changying.services.assessment_feedback import LEARNING_FEEDBACK_SOURCES


def test_teacher_ai_direct_assignment_is_a_learning_feedback_source():
    assert LEARNING_FEEDBACK_SOURCES["teacher_ai_practice"] == "teacher_ai"


def test_teacher_ai_assign_route_marks_recipients_as_feedback_bearing_practice():
    source = (Path(__file__).resolve().parents[1] / "app_v924.py").read_text(encoding="utf-8")
    assert 'ensure_recipient(db,a,sid,"teacher_ai_practice")' in source
    assert 'ensure_recipient(db,a,sid,"assignment")' in source  # ordinary manual assignment remains ordinary


def test_feedback_context_accepts_teacher_ai_practice_source():
    source = (
        Path(__file__).resolve().parents[1]
        / "changying"
        / "services"
        / "assessment_feedback.py"
    ).read_text(encoding="utf-8")
    assert '"teacher_ai_practice": "teacher_ai"' in source
    assert "recipient.source not in LEARNING_FEEDBACK_SOURCES" in source
    assert "AssignmentRecipient.source.in_(tuple(LEARNING_FEEDBACK_SOURCES))" in source
