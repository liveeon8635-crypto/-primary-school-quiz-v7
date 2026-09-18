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


def legacy_student_evidence(implementation: ModuleType, db: Any, student_id: int, school_id: int):
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

    evidence = []
    for sub in rows:
        subject = ""
        class_id = None
        question_knowledge: dict[int, str] = {}

        if sub.assignment_id:
            assignment = db.scalar(
                implementation.select(implementation.Assignment).where(
                    implementation.Assignment.id == sub.assignment_id,
                    implementation.Assignment.school_id == school_id,
                )
            )
            if assignment is not None:
                class_id = assignment.class_id
                paper = db.scalar(
                    implementation.select(implementation.Paper).where(
                        implementation.Paper.id == assignment.paper_id,
                        implementation.Paper.school_id == school_id,
                    )
                )
                if paper is not None:
                    subject = paper.subject or ""
                    qids = implementation._json_list(paper.question_ids_json)
                    if qids:
                        questions = db.scalars(
                            implementation.select(implementation.Question).where(
                                implementation.Question.school_id == school_id,
                                implementation.Question.id.in_(qids),
                            )
                        ).all()
                        question_knowledge = {
                            int(q.id): (q.knowledge or "")
                            for q in questions
                        }

        evidence.append(
            submission_to_performance_evidence(
                sub,
                subject=subject,
                class_id=class_id,
            )
        )
        evidence.extend(
            submission_answers_to_performance_evidence(
                sub,
                question_knowledge=question_knowledge,
                subject=subject,
                class_id=class_id,
            )
        )

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
