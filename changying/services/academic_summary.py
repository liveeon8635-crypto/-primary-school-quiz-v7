"""Read-only recent submission summary for one student and school."""

from __future__ import annotations

from typing import Any


class AcademicSummaryService:
    def __init__(self, *, submission_model: Any, select_fn: Any, period_cutoff_fn: Any) -> None:
        self.Submission = submission_model
        self.select = select_fn
        self.period_cutoff = period_cutoff_fn

    def summary(self, db: Any, student_id: int, school_id: int, days: int = 30) -> dict[str, Any]:
        cutoff, _ = self.period_cutoff(days)
        rows = db.scalars(
            self.select(self.Submission)
            .where(
                self.Submission.school_id == school_id,
                self.Submission.student_id == student_id,
                self.Submission.submitted_at >= cutoff,
            )
            .order_by(self.Submission.submitted_at.desc())
        ).all()
        if not rows:
            return {
                "days": days,
                "count": 0,
                "avgScore": None,
                "avgAccuracy": None,
                "latestScore": None,
            }
        scores = [int(row.score or 0) for row in rows]
        accuracies = [
            int(row.correct or 0) * 100 / int(row.total)
            for row in rows
            if int(row.total or 0) > 0
        ]
        return {
            "days": days,
            "count": len(rows),
            "avgScore": round(sum(scores) / len(scores), 1),
            "avgAccuracy": round(sum(accuracies) / len(accuracies), 1) if accuracies else None,
            "latestScore": scores[0],
        }


__all__ = ["AcademicSummaryService"]
