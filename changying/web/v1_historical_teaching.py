"""Read-only historical teaching facts scoped to a teacher's own assignments.

A teacher may query students who received assignments that were authored by
that same teacher. This preserves historical teaching access after a student
changes class without granting access to the student's later/current profile.
"""

from __future__ import annotations

from collections import defaultdict
from types import ModuleType
from typing import Any

from fastapi import APIRouter, Depends


def _latest_submission(rows):
    latest = {}
    for row in rows:
        key = (int(row.assignment_id), int(row.student_id))
        previous = latest.get(key)
        if previous is None or (row.submitted_at, row.id) > (
            previous.submitted_at,
            previous.id,
        ):
            latest[key] = row
    return latest


def teacher_historical_students(
    implementation: ModuleType,
    db: Any,
    teacher_id: int,
    school_id: int,
    *,
    query: str = "",
    subject: str = "",
    limit: int = 60,
) -> list[dict[str, Any]]:
    """Return only assignment-recipient facts owned by one teacher."""
    papers = db.scalars(
        implementation.select(implementation.Paper).where(
            implementation.Paper.school_id == school_id,
            implementation.Paper.teacher_id == teacher_id,
        )
    ).all()
    if not papers:
        return []

    paper_by_id = {int(row.id): row for row in papers}
    paper_ids = set(paper_by_id)
    assignments = db.scalars(
        implementation.select(implementation.Assignment).where(
            implementation.Assignment.school_id == school_id,
            implementation.Assignment.paper_id.in_(paper_ids),
        )
    ).all()
    if not assignments:
        return []

    assignment_by_id = {int(row.id): row for row in assignments}
    assignment_ids = set(assignment_by_id)
    recipients = db.scalars(
        implementation.select(implementation.AssignmentRecipient).where(
            implementation.AssignmentRecipient.school_id == school_id,
            implementation.AssignmentRecipient.assignment_id.in_(assignment_ids),
        )
    ).all()
    if not recipients:
        return []

    student_ids = {int(row.student_id) for row in recipients}
    class_ids = {int(row.class_id) for row in recipients}
    students = db.scalars(
        implementation.select(implementation.User).where(
            implementation.User.school_id == school_id,
            implementation.User.role == "student",
            implementation.User.id.in_(student_ids),
        )
    ).all()
    student_by_id = {int(row.id): row for row in students}
    classes = db.scalars(
        implementation.select(implementation.SchoolClass).where(
            implementation.SchoolClass.school_id == school_id,
            implementation.SchoolClass.id.in_(class_ids),
        )
    ).all()
    class_by_id = {int(row.id): row for row in classes}
    submissions = db.scalars(
        implementation.select(implementation.Submission).where(
            implementation.Submission.school_id == school_id,
            implementation.Submission.assignment_id.in_(assignment_ids),
            implementation.Submission.student_id.in_(student_ids),
        )
    ).all()
    submission_by_pair = _latest_submission(submissions)

    grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for recipient in recipients:
        assignment = assignment_by_id.get(int(recipient.assignment_id))
        if assignment is None:
            continue
        paper = paper_by_id.get(int(assignment.paper_id))
        if paper is None:
            continue
        if subject and (paper.subject or "").strip() != subject:
            continue
        student = student_by_id.get(int(recipient.student_id))
        if student is None:
            continue
        klass = class_by_id.get(int(recipient.class_id))
        submission = submission_by_pair.get(
            (int(recipient.assignment_id), int(recipient.student_id))
        )
        grouped[int(student.id)].append(
            {
                "assignmentID": int(assignment.id),
                "title": assignment.title,
                "classID": int(recipient.class_id),
                "className": klass.name if klass is not None else "",
                "grade": klass.grade if klass is not None else None,
                "subject": paper.subject or "",
                "unit": paper.unit or "",
                "assignedAt": implementation.school_local_iso(recipient.assigned_at),
                "dueDate": assignment.due_date,
                "submitted": submission is not None,
                "score": submission.score if submission is not None else None,
                "submittedAt": (
                    implementation.school_local_iso(submission.submitted_at)
                    if submission is not None
                    else None
                ),
            }
        )

    needle = query.strip().lower()
    out: list[dict[str, Any]] = []
    for student_id, records in grouped.items():
        student = student_by_id[student_id]
        records.sort(
            key=lambda row: (
                row["assignedAt"] or "",
                row["assignmentID"],
            ),
            reverse=True,
        )
        haystack = " ".join(
            [
                student.name or "",
                *[row["className"] or "" for row in records],
                *[row["subject"] or "" for row in records],
                *[row["title"] or "" for row in records],
            ]
        ).lower()
        if needle and needle not in haystack:
            continue

        scores = [
            float(row["score"])
            for row in records
            if row["score"] is not None
        ]
        classes_seen = []
        subjects_seen = []
        for row in records:
            if row["className"] and row["className"] not in classes_seen:
                classes_seen.append(row["className"])
            if row["subject"] and row["subject"] not in subjects_seen:
                subjects_seen.append(row["subject"])

        out.append(
            {
                "studentID": student_id,
                "studentName": student.name,
                "assignmentCount": len(records),
                "submissionCount": sum(1 for row in records if row["submitted"]),
                "averageObservedScore": (
                    round(sum(scores) / len(scores), 1) if scores else None
                ),
                "firstAssignedAt": records[-1]["assignedAt"],
                "lastAssignedAt": records[0]["assignedAt"],
                "classes": classes_seen,
                "subjects": subjects_seen,
                "records": records[:20],
                "scope": "teacher-owned-assignment-recipient-snapshots",
            }
        )

    out.sort(
        key=lambda row: (
            row["lastAssignedAt"] or "",
            row["studentID"],
        ),
        reverse=True,
    )
    return out[: max(1, min(int(limit or 60), 100))]



def teacher_historical_classrooms(
    implementation: ModuleType,
    db: Any,
    teacher_id: int,
    school_id: int,
    *,
    limit: int = 40,
) -> list[dict[str, Any]]:
    """Return completed interactive classroom sessions owned by one teacher."""

    metadata = implementation.Base.metadata
    sessions = metadata.tables.get("classroom_sessions")
    segments = metadata.tables.get("classroom_segments")
    checks = metadata.tables.get("classroom_quick_checks")
    turns = metadata.tables.get("classroom_presenter_turns")
    reviews = metadata.tables.get("classroom_presentation_reviews")
    handouts = metadata.tables.get("classroom_review_handouts")
    if sessions is None:
        return []

    rows = db.execute(
        implementation.select(sessions)
        .where(
            sessions.c.school_id == school_id,
            sessions.c.teacher_id == teacher_id,
            sessions.c.status == "completed",
        )
        .order_by(sessions.c.completed_at.desc(), sessions.c.id.desc())
        .limit(max(1, min(int(limit or 40), 100)))
    ).all()

    out: list[dict[str, Any]] = []
    for raw in rows:
        row = raw._mapping
        sid = int(row["id"])
        assignment_id = int(row["source_assignment_id"]) if row["source_assignment_id"] else None
        assignment = db.get(implementation.Assignment, assignment_id) if assignment_id else None
        paper = db.get(implementation.Paper, assignment.paper_id) if assignment is not None else None
        klass = db.get(implementation.SchoolClass, int(row["class_id"]))

        segment_count = 0
        completed_segment_count = 0
        if segments is not None:
            segment_count = int(
                db.scalar(
                    implementation.select(implementation.func.count())
                    .select_from(segments)
                    .where(
                        segments.c.school_id == school_id,
                        segments.c.session_id == sid,
                    )
                )
                or 0
            )
            completed_segment_count = int(
                db.scalar(
                    implementation.select(implementation.func.count())
                    .select_from(segments)
                    .where(
                        segments.c.school_id == school_id,
                        segments.c.session_id == sid,
                        segments.c.status == "completed",
                    )
                )
                or 0
            )

        quick_check_rounds = 0
        reteach_count = 0
        if checks is not None:
            quick_check_rounds = int(
                db.scalar(
                    implementation.select(implementation.func.count())
                    .select_from(checks)
                    .where(
                        checks.c.school_id == school_id,
                        checks.c.session_id == sid,
                    )
                )
                or 0
            )
            reteach_count = int(
                db.scalar(
                    implementation.select(implementation.func.count())
                    .select_from(checks)
                    .where(
                        checks.c.school_id == school_id,
                        checks.c.session_id == sid,
                        checks.c.decision == "reteach",
                    )
                )
                or 0
            )

        presentation_count = 0
        if turns is not None:
            presentation_count = int(
                db.scalar(
                    implementation.select(implementation.func.count())
                    .select_from(turns)
                    .where(
                        turns.c.school_id == school_id,
                        turns.c.session_id == sid,
                        turns.c.status == "completed",
                    )
                )
                or 0
            )

        review_count = 0
        teacher_granted_points = 0
        if reviews is not None:
            review_count = int(
                db.scalar(
                    implementation.select(implementation.func.count())
                    .select_from(reviews)
                    .where(
                        reviews.c.school_id == school_id,
                        reviews.c.session_id == sid,
                    )
                )
                or 0
            )
            teacher_granted_points = int(
                db.scalar(
                    implementation.select(
                        implementation.func.coalesce(
                            implementation.func.sum(reviews.c.granted_points),
                            0,
                        )
                    ).where(
                        reviews.c.school_id == school_id,
                        reviews.c.session_id == sid,
                    )
                )
                or 0
            )

        handout_id = None
        handout_updated_at = None
        if handouts is not None and assignment_id:
            handout = db.execute(
                implementation.select(handouts.c.id, handouts.c.updated_at).where(
                    handouts.c.school_id == school_id,
                    handouts.c.assignment_id == assignment_id,
                )
            ).first()
            if handout is not None:
                handout_id = int(handout._mapping["id"])
                handout_updated_at = implementation.school_local_iso(
                    handout._mapping["updated_at"]
                )

        out.append(
            {
                "sessionID": sid,
                "assignmentID": assignment_id,
                "assignmentTitle": assignment.title if assignment is not None else "",
                "title": str(row["title"] or ""),
                "classID": int(row["class_id"]),
                "className": klass.name if klass is not None else "",
                "grade": klass.grade if klass is not None else None,
                "subject": str(row["subject"] or (paper.subject if paper is not None else "")),
                "textbook": str(row["textbook"] or (paper.textbook if paper is not None else "")),
                "startedAt": implementation.school_local_iso(row["started_at"]),
                "completedAt": implementation.school_local_iso(row["completed_at"]),
                "segmentCount": segment_count,
                "completedSegmentCount": completed_segment_count,
                "quickCheckRoundCount": quick_check_rounds,
                "reteachCount": reteach_count,
                "presentationCount": presentation_count,
                "presentationReviewCount": review_count,
                "teacherGrantedPoints": teacher_granted_points,
                "handoutID": handout_id,
                "handoutUpdatedAt": handout_updated_at,
                "scope": "teacher-owned-completed-classroom-sessions",
            }
        )
    return out



def install_v1_historical_teaching_routes(implementation: ModuleType) -> None:
    """Install the read-only historical teaching query endpoint."""
    app = implementation.app
    if getattr(app.state, "v1_historical_teaching_routes_installed", False):
        return

    router = APIRouter()

    @router.get("/v1/teacher/history/classrooms", include_in_schema=False)
    def historical_classrooms(
        limit: int = 40,
        user=Depends(implementation.current_user),
        db=Depends(implementation.get_db),
    ):
        implementation.need(user, "teacher")
        rows = teacher_historical_classrooms(
            implementation,
            db,
            int(user.id),
            int(user.school_id),
            limit=limit,
        )
        return {
            "scope": "teacher-owned-completed-classroom-sessions",
            "classrooms": rows,
            "count": len(rows),
        }

    @router.get("/v1/teacher/history/students", include_in_schema=False)
    def historical_students(
        q: str = "",
        subject: str = "",
        limit: int = 60,
        user=Depends(implementation.current_user),
        db=Depends(implementation.get_db),
    ):
        implementation.need(user, "teacher")
        rows = teacher_historical_students(
            implementation,
            db,
            int(user.id),
            int(user.school_id),
            query=q,
            subject=subject,
            limit=limit,
        )
        return {
            "scope": "teacher-owned-assignment-recipient-snapshots",
            "students": rows,
            "count": len(rows),
        }

    app.include_router(router)
    app.state.v1_historical_teaching_routes_installed = True


__all__ = [
    "install_v1_historical_teaching_routes",
    "teacher_historical_classrooms",
    "teacher_historical_students",
]
