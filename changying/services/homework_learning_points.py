"""Late-care consolidation-practice points.

The ordinary ``learning_points`` rule awards one point per correct answer.  For
the late-care practice assignments created by the homework assistant we replace
that rule with the business rules in ``homework_points_rule``:

* on-time completion: ``DEFAULT_ON_TIME_POINTS``;
* accuracy ladder after the practice is graded (60% midpoint, +/-3);
* deductions never take the student's balance below zero;
* one ledger row per submission, so repeated callbacks do not double-award.

The assignment is recognised by the title marker written by
``homework_practice_views``; no schema change is needed.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from changying.services import homework_points_rule as rule

HOMEWORK_PRACTICE_SOURCE = "homework_practice"
HOMEWORK_POINT_CATEGORY = "learning"
MAX_POINTS = rule.DEFAULT_ON_TIME_POINTS + rule.MAX_ADJUST


def _assignment(implementation: Any, db: Any, submission: Any) -> Any:
    assignment_id = getattr(submission, "assignment_id", None)
    if assignment_id is None:
        return None
    return db.get(implementation.Assignment, int(assignment_id))


def is_late_care_practice(implementation: Any, db: Any, submission: Any) -> bool:
    assignment = _assignment(implementation, db, submission)
    return bool(assignment is not None and rule.is_late_care_title(assignment.title))


def _class_id_for_submission(implementation: Any, db: Any, submission: Any) -> int | None:
    assignment = _assignment(implementation, db, submission)
    if assignment is not None and assignment.class_id is not None:
        return int(assignment.class_id)
    current = implementation.current_class_for(
        db,
        int(submission.student_id),
        int(submission.school_id),
    )
    return int(current.id) if current is not None else None


def _balance(implementation: Any, db: Any, submission: Any) -> int:
    balance = getattr(implementation, "point_balance", None)
    if callable(balance):
        return int(balance(db, int(submission.student_id), int(submission.school_id)) or 0)
    return int(
        db.scalar(
            select(func.coalesce(func.sum(implementation.PointLedger.points), 0)).where(
                implementation.PointLedger.school_id == int(submission.school_id),
                implementation.PointLedger.student_id == int(submission.student_id),
            )
        )
        or 0
    )


def _existing(implementation: Any, db: Any, submission: Any) -> Any:
    return db.scalar(
        select(implementation.PointLedger).where(
            implementation.PointLedger.school_id == int(submission.school_id),
            implementation.PointLedger.student_id == int(submission.student_id),
            implementation.PointLedger.source == HOMEWORK_PRACTICE_SOURCE,
            implementation.PointLedger.related_id == int(submission.id),
        ).limit(1)
    )


def award_homework_practice_points(
    implementation: Any,
    db: Any,
    *,
    submission: Any,
    actor: Any,
) -> dict[str, Any]:
    """Settle one late-care practice submission, replacing per-question points."""
    if submission is None or actor is None:
        return {"points": 0, "maximum": MAX_POINTS, "source": HOMEWORK_PRACTICE_SOURCE}

    assignment = _assignment(implementation, db, submission)
    if assignment is None or not rule.is_late_care_title(assignment.title):
        return {"points": 0, "maximum": MAX_POINTS, "source": HOMEWORK_PRACTICE_SOURCE}

    existing = _existing(implementation, db, submission)
    if existing is not None:
        return {
            "points": int(existing.points or 0),
            "maximum": MAX_POINTS,
            "source": HOMEWORK_PRACTICE_SOURCE,
            "alreadySettled": True,
        }

    status = implementation.assignment_status(assignment.due_date, submission)
    on_time = not bool(status.get("late"))
    total = max(0, int(getattr(submission, "total", 0) or 0))
    correct = max(0, min(total, int(getattr(submission, "correct", 0) or 0)))
    accuracy = (correct * 100.0 / total) if total else None
    result = rule.total_for_assignment(
        on_time,
        accuracy,
        graded=accuracy is not None,
        balance=_balance(implementation, db, submission),
    )
    points = int(result["total"])

    entries = result["entries"]
    note_parts = [str(entry["note"]) for entry in entries if entry.get("points") or not entry.get("settled")]
    row = implementation.PointLedger(
        school_id=int(submission.school_id),
        student_id=int(submission.student_id),
        class_id=_class_id_for_submission(implementation, db, submission),
        actor_id=getattr(actor, "id", None),
        rule_id=None,
        category=HOMEWORK_POINT_CATEGORY,
        points=points,
        reason=f"晚托巩固练习积分：{str(getattr(assignment, 'title', '') or '')[:100]}",
        note="；".join(note_parts)[:1000],
        source=HOMEWORK_PRACTICE_SOURCE,
        related_id=int(submission.id),
        idempotency_key=f"{HOMEWORK_PRACTICE_SOURCE}:{int(submission.id)}",
    )
    try:
        with db.begin_nested():
            db.add(row)
            db.flush()
    except IntegrityError:
        # Another request settled this same practice between our check and insert.
        return {
            "points": 0,
            "maximum": MAX_POINTS,
            "source": HOMEWORK_PRACTICE_SOURCE,
            "alreadySettled": True,
        }
    if points > 0:
        implementation.reconcile_auto_rewards(
            db,
            int(submission.school_id),
            [int(submission.student_id)],
            getattr(actor, "id", None),
        )

    return {
        "points": points,
        "maximum": MAX_POINTS,
        "source": HOMEWORK_PRACTICE_SOURCE,
        "onTime": on_time,
        "accuracy": None if accuracy is None else round(accuracy, 1),
        "fullySettled": bool(result["fullySettled"]),
        "entries": entries,
    }


__all__ = [
    "HOMEWORK_POINT_CATEGORY",
    "HOMEWORK_PRACTICE_SOURCE",
    "award_homework_practice_points",
    "is_late_care_practice",
]
