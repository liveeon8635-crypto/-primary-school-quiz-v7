from pathlib import Path

from changying.domain.student_continuity import CompletionActor


def test_completion_actor_vocabulary_is_stable():
    assert [x.value for x in CompletionActor] == [
        "student", "parent_assisted", "parent_submitted", "teacher_recorded"
    ]


def test_submission_actor_is_nullable_for_legacy_rows_and_new_student_writes_are_explicit():
    source=(Path(__file__).resolve().parents[1]/"app_v924.py").read_text(encoding="utf-8")
    assert 'completion_actor:Mapped[str|None]=mapped_column(String(30),nullable=True,index=True)' in source
    assert 'def save_sub(db,u,aid,title,normalized,correct,total,score,completion_actor="student"):' in source
    assert 'old.completion_actor=completion_actor' in source
    assert 'completion_actor=completion_actor' in source
    assert 'completion_actor:Mapped[str]=mapped_column' not in source


def test_new_evidence_context_preserves_actor_provenance_without_mastery_inference():
    source=(Path(__file__).resolve().parents[1]/"changying/services/submission_evidence.py").read_text(encoding="utf-8")
    assert source.count('completionActor=getattr(submission, "completion_actor", None)') == 2
    assert "mastery" not in source.lower().split("def append_submission_evidence",1)[1].split("def install_canonical_submission_evidence",1)[0]
