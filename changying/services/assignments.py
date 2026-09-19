"""Database-backed assignment service extracted from the legacy monolith."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable

from sqlalchemy import func, select


class AssignmentService:
    """Read-side assignment orchestration with injected legacy ORM models."""

    def __init__(
        self,
        *,
        assignment_submission_setting_model: Any,
        submission_model: Any,
        homework_media_submit_model: Any,
        homework_media_model: Any,
        user_model: Any,
        assignment_recipient_model: Any,
        assignment_model: Any,
        class_model: Any,
        valid_submission_modes: set[str],
        assignment_mode_name: Callable[[str], str],
        school_local_iso: Callable[[Any], str],
        due_deadline_utc: Callable[[str], Any],
    ) -> None:
        self.AssignmentSubmissionSetting = assignment_submission_setting_model
        self.Submission = submission_model
        self.HomeworkMediaSubmit = homework_media_submit_model
        self.HomeworkMedia = homework_media_model
        self.User = user_model
        self.AssignmentRecipient = assignment_recipient_model
        self.Assignment = assignment_model
        self.SchoolClass = class_model
        self.valid_submission_modes = set(valid_submission_modes)
        self.assignment_mode_name = assignment_mode_name
        self.school_local_iso = school_local_iso
        self.due_deadline_utc = due_deadline_utc

    def submission_setting(self, db, assignment):
        return db.scalar(
            select(self.AssignmentSubmissionSetting).where(
                self.AssignmentSubmissionSetting.assignment_id == assignment.id,
                self.AssignmentSubmissionSetting.school_id == assignment.school_id,
            )
        )

    def submission_mode(self, db, assignment) -> str:
        row = self.submission_setting(db, assignment)
        return (
            row.mode
            if row and row.mode in self.valid_submission_modes
            else "quiz"
        )

    def student_assignment_for(
        self,
        db,
        school_id: int,
        student_id: int,
        assignment_id: int,
    ):
        """Return one assignment only when it was addressed to the student."""
        return db.scalar(
            select(self.Assignment)
            .join(
                self.AssignmentRecipient,
                self.AssignmentRecipient.assignment_id == self.Assignment.id,
            )
            .where(
                self.Assignment.id == assignment_id,
                self.Assignment.school_id == school_id,
                self.AssignmentRecipient.school_id == school_id,
                self.AssignmentRecipient.student_id == student_id,
            )
            .limit(1)
        )

    def student_assignment_for_paper(
        self,
        db,
        school_id: int,
        student_id: int,
        paper_id: int,
    ):
        """Return an addressed assignment for a paper using the legacy access contract."""
        return db.scalar(
            select(self.Assignment)
            .join(
                self.AssignmentRecipient,
                self.AssignmentRecipient.assignment_id == self.Assignment.id,
            )
            .where(
                self.Assignment.paper_id == paper_id,
                self.Assignment.school_id == school_id,
                self.AssignmentRecipient.student_id == student_id,
            )
            .limit(1)
        )

    def teacher_assignment_for(
        self,
        db,
        school_id: int,
        teacher_id: int,
        assignment_id: int,
    ):
        """Return one assignment only when it belongs to the requesting teacher."""
        return db.scalar(
            select(self.Assignment)
            .join(self.SchoolClass, self.Assignment.class_id == self.SchoolClass.id)
            .where(
                self.Assignment.id == assignment_id,
                self.Assignment.school_id == school_id,
                self.SchoolClass.teacher_id == teacher_id,
            )
        )

    def recipient_students(self, db, assignment) -> list[Any]:
        """Return assignment recipients using the existing role/school/order contract."""
        return list(
            db.scalars(
                select(self.User)
                .join(
                    self.AssignmentRecipient,
                    self.AssignmentRecipient.student_id == self.User.id,
                )
                .where(
                    self.AssignmentRecipient.assignment_id == assignment.id,
                    self.AssignmentRecipient.school_id == assignment.school_id,
                    self.User.school_id == assignment.school_id,
                    self.User.role == "student",
                )
                .order_by(self.User.name, self.User.id)
            ).all()
        )

    def homework_media_count(
        self,
        db,
        assignment_id: int,
        student_id: int,
        school_id: int,
    ) -> int:
        return int(
            db.scalar(
                select(func.count())
                .select_from(self.HomeworkMedia)
                .where(
                    self.HomeworkMedia.school_id == school_id,
                    self.HomeworkMedia.assignment_id == assignment_id,
                    self.HomeworkMedia.student_id == student_id,
                )
            )
            or 0
        )

    def effective_status(
        self,
        db,
        assignment,
        student_id: int,
        now: datetime | None = None,
    ) -> dict:
        mode = self.submission_mode(db, assignment)
        quiz_sub = db.scalar(
            select(self.Submission)
            .where(
                self.Submission.assignment_id == assignment.id,
                self.Submission.student_id == student_id,
                self.Submission.school_id == assignment.school_id,
            )
            .order_by(
                self.Submission.submitted_at.desc(),
                self.Submission.id.desc(),
            )
            .limit(1)
        )
        media_sub = db.scalar(
            select(self.HomeworkMediaSubmit)
            .where(
                self.HomeworkMediaSubmit.assignment_id == assignment.id,
                self.HomeworkMediaSubmit.student_id == student_id,
                self.HomeworkMediaSubmit.school_id == assignment.school_id,
            )
            .limit(1)
        )

        quiz_ok = bool(quiz_sub)
        media_ok = bool(media_sub)
        completed = (
            quiz_ok
            if mode == "quiz"
            else media_ok
            if mode == "media"
            else bool(quiz_ok and media_ok)
        )

        completed_at = None
        if completed:
            stamps = []
            if mode in ("quiz", "mixed") and quiz_sub:
                stamps.append(quiz_sub.submitted_at)
            if mode in ("media", "mixed") and media_sub:
                stamps.append(media_sub.submitted_at)
            completed_at = max(stamps) if stamps else None

        deadline = self.due_deadline_utc(assignment.due_date)
        now = now or datetime.utcnow()
        late = bool(completed and completed_at and deadline and completed_at > deadline)
        overdue = bool((not completed) and deadline and now > deadline)
        status = (
            ("逾期完成" if late else "已完成")
            if completed
            else ("逾期未交" if overdue else "未完成")
        )
        code = (
            ("late_completed" if late else "completed")
            if completed
            else ("overdue" if overdue else "pending")
        )

        return {
            "completed": completed,
            "status": status,
            "statusCode": code,
            "late": late,
            "overdue": overdue,
            "deadlinePassed": bool(deadline and now > deadline),
            "submissionMode": mode,
            "submissionModeName": self.assignment_mode_name(mode),
            "quizSubmitted": quiz_ok,
            "mediaSubmitted": media_ok,
            "mediaCount": self.homework_media_count(
                db,
                assignment.id,
                student_id,
                assignment.school_id,
            ),
            "submittedAt": (
                self.school_local_iso(completed_at) if completed_at else None
            ),
            "quizSubmission": quiz_sub,
            "mediaSubmission": media_sub,
        }



def teacher_assignment_rows(
    db: Any,
    *,
    assignment_model: Any,
    class_model: Any,
    school_id: int,
    teacher_id: int,
) -> list[Any]:
    """Return a teacher's assignments using the existing legacy query contract."""
    statement = (
        select(assignment_model)
        .join(class_model, assignment_model.class_id == class_model.id)
        .where(
            assignment_model.school_id == school_id,
            class_model.teacher_id == teacher_id,
        )
        .order_by(assignment_model.id.desc())
    )
    return list(db.scalars(statement).all())


def student_assignment_rows(
    db: Any,
    *,
    assignment_model: Any,
    assignment_recipient_model: Any,
    school_id: int,
    student_id: int,
) -> list[Any]:
    """Return assignments addressed to one student using the legacy query contract."""
    statement = (
        select(assignment_model)
        .join(
            assignment_recipient_model,
            assignment_recipient_model.assignment_id == assignment_model.id,
        )
        .where(
            assignment_model.school_id == school_id,
            assignment_recipient_model.school_id == school_id,
            assignment_recipient_model.student_id == student_id,
        )
        .order_by(assignment_model.id.desc())
    )
    return list(db.scalars(statement).all())


__all__ = ["AssignmentService", "teacher_assignment_rows", "student_assignment_rows"]
