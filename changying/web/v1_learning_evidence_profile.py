"""Read-only V1.1 learning-evidence integration for legacy growth-profile.

The installer wraps the existing student_growth_profile_data function. The
legacy profile is generated first and kept intact. Historical submissions are
then mapped conservatively into evidence and attached as one additive
learningEvidence section. No database writes occur here.
"""

from __future__ import annotations

from types import ModuleType
from typing import Any

from changying.domain.learning_evidence_growth_profile import attach_learning_evidence
from changying.domain.learning_evidence_mapping import (
    submission_answers_to_performance_evidence,
    submission_to_performance_evidence,
)
from changying.domain.learning_evidence_read_model import student_evidence_snapshot
from changying.domain.stored_learning_evidence import (
    canonical_submission_ids,
    explicit_student_evidence,
    teacher_confirmed_assignment_ids,
)
from changying.web.v2_learning_evidence_recording import manual_student_evidence


def legacy_student_evidence(implementation: ModuleType, db: Any, student_id: int, school_id: int):
    """Read one student's legacy evidence with a bounded set of batch queries."""
    rows = db.scalars(
        implementation.select(implementation.Submission)
        .where(
            implementation.Submission.school_id == school_id,
            implementation.Submission.student_id == student_id,
        )
        .order_by(
            implementation.Submission.submitted_at.asc(),
            implementation.Submission.id.asc(),
        )
    ).all()

    assignment_ids = {
        int(sub.assignment_id)
        for sub in rows
        if getattr(sub, "assignment_id", None) is not None
    }
    assignments = []
    if assignment_ids:
        assignments = db.scalars(
            implementation.select(implementation.Assignment).where(
                implementation.Assignment.school_id == school_id,
                implementation.Assignment.id.in_(assignment_ids),
            )
        ).all()
    assignment_by_id = {int(row.id): row for row in assignments}

    paper_ids = {
        int(row.paper_id)
        for row in assignments
        if getattr(row, "paper_id", None) is not None
    }
    papers = []
    if paper_ids:
        papers = db.scalars(
            implementation.select(implementation.Paper).where(
                implementation.Paper.school_id == school_id,
                implementation.Paper.id.in_(paper_ids),
            )
        ).all()
    paper_by_id = {int(row.id): row for row in papers}

    paper_question_ids: dict[int, list[int]] = {}
    all_question_ids: set[int] = set()
    for paper in papers:
        qids = [
            int(qid)
            for qid in implementation._json_list(paper.question_ids_json)
            if isinstance(qid, int) or (isinstance(qid, str) and qid.isdigit())
        ]
        paper_question_ids[int(paper.id)] = qids
        all_question_ids.update(qids)

    questions = []
    if all_question_ids:
        questions = db.scalars(
            implementation.select(implementation.Question).where(
                implementation.Question.school_id == school_id,
                implementation.Question.id.in_(all_question_ids),
            )
        ).all()
    knowledge_by_question = {
        int(question.id): (question.knowledge or "")
        for question in questions
    }

    confirmed_assignment_ids = teacher_confirmed_assignment_ids(
        implementation,
        db,
        student_id,
        school_id,
    )
    explicit_submission_ids = canonical_submission_ids(
        implementation,
        db,
        student_id,
        school_id,
    )

    evidence = []
    for sub in rows:
        subject = ""
        class_id = None
        question_knowledge: dict[int, str] = {}

        assignment = assignment_by_id.get(int(sub.assignment_id)) if sub.assignment_id else None
        if assignment is not None:
            class_id = assignment.class_id
            paper = paper_by_id.get(int(assignment.paper_id)) if assignment.paper_id else None
            if paper is not None:
                subject = paper.subject or ""
                question_knowledge = {
                    qid: knowledge_by_question.get(qid, "")
                    for qid in paper_question_ids.get(int(paper.id), [])
                }

        has_canonical_submission = int(sub.id) in explicit_submission_ids
        if not has_canonical_submission and not (
            sub.assignment_id is not None
            and int(sub.assignment_id) in confirmed_assignment_ids
        ):
            evidence.append(
                submission_to_performance_evidence(
                    sub,
                    subject=subject,
                    class_id=class_id,
                )
            )
        if not has_canonical_submission:
            evidence.extend(
                submission_answers_to_performance_evidence(
                    sub,
                    question_knowledge=question_knowledge,
                    subject=subject,
                    class_id=class_id,
                )
            )

    evidence.extend(
        explicit_student_evidence(
            implementation,
            db,
            student_id,
            school_id,
        )
    )
    evidence.extend(manual_student_evidence(implementation, db, student_id, school_id))
    return evidence


def install_v1_learning_evidence_profile(implementation: ModuleType) -> None:
    """Attach read-only learningEvidence to the existing growth-profile."""
    if getattr(
        implementation,
        "_v1_learning_evidence_profile_installed",
        False,
    ):
        return

    original = implementation.student_growth_profile_data

    def wrapped_student_growth_profile_data(
        db,
        stu,
        school_id: int,
        class_id: int | None = None,
    ):
        profile = original(db, stu, school_id, class_id)
        try:
            items = legacy_student_evidence(
                implementation,
                db,
                int(stu.id),
                int(school_id),
            )
            snapshot = student_evidence_snapshot(items)
            return attach_learning_evidence(profile, snapshot)
        except Exception:
            # Evidence is additive. A compatibility-layer failure must never
            # take down the mature growth-profile endpoint.
            return profile

    implementation.student_growth_profile_data = wrapped_student_growth_profile_data
    implementation._v1_learning_evidence_profile_installed = True


__all__ = [
    "install_v1_learning_evidence_profile",
    "legacy_student_evidence",
]
