"""Canonical performance evidence for new objective submissions.

Historical submissions remain readable through the legacy mapping layer. New
submissions append explicit LearningEvidenceEvent rows so the continuous student
record no longer depends on reconstructing facts later.

Only facts directly established by the submitted work are written:
* one assignment/practice-level performance event with the actual score;
* one question-level performance event with the actual correct flag.

This module deliberately does not infer independence, retention, transfer or
mastery from a single submission.
"""

from __future__ import annotations

from datetime import datetime
from functools import wraps
import json
from types import ModuleType
from typing import Any


SUMMARY_SOURCE = "submission"
ITEM_SOURCE = "submission_answer"


def _context(**values: Any) -> str:
    return json.dumps(values, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _route(implementation: ModuleType, path: str, method: str):
    for route in implementation.app.routes:
        if getattr(route, "path", None) == path and method in getattr(route, "methods", set()):
            return route
    raise RuntimeError(f"route not found: {method} {path}")


def _existing(
    implementation: ModuleType,
    db: Any,
    *,
    school_id: int,
    student_id: int,
    source_type: str,
    submission_id: int,
    question_id: int | None = None,
) -> bool:
    rows = db.scalars(
        implementation.select(implementation.LearningEvidenceEvent).where(
            implementation.LearningEvidenceEvent.school_id == school_id,
            implementation.LearningEvidenceEvent.student_id == student_id,
            implementation.LearningEvidenceEvent.event_kind == "record",
            implementation.LearningEvidenceEvent.source_type == source_type,
        )
    ).all()
    for row in rows:
        try:
            data = json.loads(row.context or "{}")
        except Exception:
            continue
        if not isinstance(data, dict):
            continue
        try:
            if int(data.get("submissionID")) != int(submission_id):
                continue
        except Exception:
            continue
        if question_id is None:
            return True
        try:
            if int(data.get("questionID")) == int(question_id):
                return True
        except Exception:
            continue
    return False


def append_submission_evidence(
    implementation: ModuleType,
    db: Any,
    *,
    submission: Any,
    actor: Any,
) -> int:
    """Append idempotent explicit performance evidence for one Submission."""
    if submission is None or actor is None:
        return 0

    school_id = int(submission.school_id)
    student_id = int(submission.student_id)
    submission_id = int(submission.id)
    assignment_id = (
        int(submission.assignment_id)
        if getattr(submission, "assignment_id", None) is not None
        else None
    )

    subject = ""
    class_id = None
    assignment = None
    paper = None
    qmap: dict[int, Any] = {}
    if assignment_id is not None:
        assignment = db.get(implementation.Assignment, assignment_id)
        if assignment is not None:
            class_id = int(assignment.class_id) if assignment.class_id is not None else None
            if assignment.paper_id is not None:
                paper = db.get(implementation.Paper, int(assignment.paper_id))
    if paper is not None:
        subject = str(paper.subject or "")

    try:
        answer_rows = json.loads(submission.answers_json or "[]")
    except Exception:
        answer_rows = []
    if not isinstance(answer_rows, list):
        answer_rows = []

    qids = []
    for answer in answer_rows:
        if not isinstance(answer, dict):
            continue
        try:
            qids.append(int(answer.get("question_id")))
        except Exception:
            continue
    if qids:
        questions = db.scalars(
            implementation.select(implementation.Question).where(
                implementation.Question.school_id == school_id,
                implementation.Question.id.in_(qids),
            )
        ).all()
        qmap = {int(q.id): q for q in questions}
        if not subject:
            subjects = {str(q.subject or "").strip() for q in questions if str(q.subject or "").strip()}
            if len(subjects) == 1:
                subject = next(iter(subjects))

    occurred_at = getattr(submission, "submitted_at", None) or datetime.utcnow()
    added = 0

    summary_context = _context(
        marker="submission",
        submissionID=submission_id,
        assignmentID=assignment_id,
        classID=class_id,
        title=str(getattr(submission, "title", "") or "")[:160],
        score=int(getattr(submission, "score", 0) or 0),
        correct=int(getattr(submission, "correct", 0) or 0),
        total=int(getattr(submission, "total", 0) or 0),
        completionActor=getattr(submission, "completion_actor", None),
    )
    if not _existing(
        implementation,
        db,
        school_id=school_id,
        student_id=student_id,
        source_type=SUMMARY_SOURCE,
        submission_id=submission_id,
    ):
        db.add(
            implementation.LearningEvidenceEvent(
                school_id=school_id,
                student_id=student_id,
                actor_id=int(actor.id),
                event_kind="record",
                target_event_id=None,
                evidence_type="performance",
                subject=subject,
                knowledge_key="",
                success=None,
                note="正式提交表现",
                context=summary_context,
                source_type=SUMMARY_SOURCE,
                occurred_at=occurred_at,
            )
        )
        added += 1

    for answer in answer_rows:
        if not isinstance(answer, dict) or not isinstance(answer.get("correct"), bool):
            continue
        try:
            qid = int(answer.get("question_id"))
        except Exception:
            continue
        question = qmap.get(qid)
        if question is None:
            continue
        knowledge = str(question.knowledge or "").strip()
        if not knowledge:
            continue
        if _existing(
            implementation,
            db,
            school_id=school_id,
            student_id=student_id,
            source_type=ITEM_SOURCE,
            submission_id=submission_id,
            question_id=qid,
        ):
            continue
        item_context = _context(
            marker="submission_answer",
            submissionID=submission_id,
            assignmentID=assignment_id,
            classID=class_id,
            questionID=qid,
            completionActor=getattr(submission, "completion_actor", None),
        )
        db.add(
            implementation.LearningEvidenceEvent(
                school_id=school_id,
                student_id=student_id,
                actor_id=int(actor.id),
                event_kind="record",
                target_event_id=None,
                evidence_type="performance",
                subject=str(question.subject or subject),
                knowledge_key=knowledge,
                success=bool(answer.get("correct")),
                note="逐题作答事实",
                context=item_context,
                source_type=ITEM_SOURCE,
                occurred_at=occurred_at,
            )
        )
        added += 1

    return added


def install_canonical_submission_evidence(implementation: ModuleType) -> None:
    app = implementation.app
    if getattr(app.state, "canonical_submission_evidence_installed", False):
        return

    # Formal assigned quiz.
    assignment_route = _route(
        implementation,
        "/student/assignments/{aid}/submit",
        "POST",
    )
    original_assignment = assignment_route.dependant.call

    @wraps(original_assignment)
    def assignment_submit(*args: Any, __original=original_assignment, **kwargs: Any):
        result = __original(*args, **kwargs)
        db = kwargs.get("db")
        actor = kwargs.get("u")
        if db is None or actor is None or not isinstance(result, dict):
            return result
        submission_id = result.get("id")
        submission = db.get(implementation.Submission, int(submission_id)) if submission_id else None
        added = append_submission_evidence(
            implementation,
            db,
            submission=submission,
            actor=actor,
        )
        if added:
            implementation.audit(
                db,
                actor,
                "learning.evidence.submission",
                f"submission={submission_id}:events={added}",
            )
            db.commit()
        payload = dict(result)
        payload["learningEvidenceAdded"] = added
        return payload

    assignment_route.dependant.call = assignment_submit
    assignment_route.endpoint = assignment_submit

    # Student self-practice also produces real performance facts, but has no
    # assignment id. Each practice submission has its own Submission id.
    practice_route = _route(implementation, "/student/practice-submit", "POST")
    original_practice = practice_route.dependant.call

    @wraps(original_practice)
    def practice_submit(*args: Any, __original=original_practice, **kwargs: Any):
        result = __original(*args, **kwargs)
        db = kwargs.get("db")
        actor = kwargs.get("u")
        if db is None or actor is None or not isinstance(result, dict):
            return result
        submission_id = result.get("id")
        submission = db.get(implementation.Submission, int(submission_id)) if submission_id else None
        added = append_submission_evidence(
            implementation,
            db,
            submission=submission,
            actor=actor,
        )
        if added:
            implementation.audit(
                db,
                actor,
                "learning.evidence.practice_submission",
                f"submission={submission_id}:events={added}",
            )
            db.commit()
        payload = dict(result)
        payload["learningEvidenceAdded"] = added
        return payload

    practice_route.dependant.call = practice_submit
    practice_route.endpoint = practice_submit

    app.state.canonical_submission_evidence_installed = True


__all__ = [
    "ITEM_SOURCE",
    "SUMMARY_SOURCE",
    "append_submission_evidence",
    "install_canonical_submission_evidence",
]
