"""Read-only usage metering for commercial pricing analysis.

This service deliberately derives usage from existing production facts. It does
not create billing events, mutate subscriptions, calculate prices, create
orders, or touch payment state. That keeps the first metering layer auditable
and historically queryable without a schema migration.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select

from changying.utils.datetime_tools import SCHOOL_TZ


METER_VERSION = "usage-metering-v1"


def billing_month_window(month: str | None = None, *, now: datetime | None = None):
    """Return a school-local calendar month as naive UTC [start, end)."""

    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    local_now = current.astimezone(SCHOOL_TZ)

    if month:
        text = str(month).strip()
        try:
            year_text, month_text = text.split("-", 1)
            year, number = int(year_text), int(month_text)
            if len(year_text) != 4 or not 1 <= number <= 12:
                raise ValueError
        except Exception as exc:
            raise ValueError("month must be YYYY-MM") from exc
    else:
        year, number = local_now.year, local_now.month

    local_start = datetime(year, number, 1, tzinfo=SCHOOL_TZ)
    if number == 12:
        local_end = datetime(year + 1, 1, 1, tzinfo=SCHOOL_TZ)
    else:
        local_end = datetime(year, number + 1, 1, tzinfo=SCHOOL_TZ)

    start_utc = local_start.astimezone(timezone.utc).replace(tzinfo=None)
    end_utc = local_end.astimezone(timezone.utc).replace(tzinfo=None)
    return {
        "key": f"{year:04d}-{number:02d}",
        "startUtc": start_utc,
        "endUtc": end_utc,
        "startLocal": local_start.strftime("%Y-%m-%d 00:00"),
        "endLocalExclusive": local_end.strftime("%Y-%m-%d 00:00"),
    }


def _int(value: Any) -> int:
    return int(value or 0)


class CommercialUsageMeteringService:
    """Aggregate school usage from existing database facts only."""

    def __init__(
        self,
        *,
        school_model: Any,
        user_model: Any,
        school_class_model: Any,
        assignment_model: Any,
        submission_model: Any,
        teaching_attempt_model: Any,
        learning_evidence_event_model: Any,
        ai_usage_log_model: Any,
        homework_media_model: Any,
        teaching_resource_model: Any,
        school_subscription_model: Any | None = None,
    ) -> None:
        self.School = school_model
        self.User = user_model
        self.SchoolClass = school_class_model
        self.Assignment = assignment_model
        self.Submission = submission_model
        self.TeachingAttempt = teaching_attempt_model
        self.LearningEvidenceEvent = learning_evidence_event_model
        self.AIUsageLog = ai_usage_log_model
        self.HomeworkMedia = homework_media_model
        self.TeachingResource = teaching_resource_model
        self.SchoolSubscription = school_subscription_model

    def _count(self, db, model, *conditions) -> int:
        return _int(
            db.scalar(
                select(func.count())
                .select_from(model)
                .where(*conditions)
            )
        )

    def _sum(self, db, column, *conditions) -> int:
        return _int(
            db.scalar(
                select(func.coalesce(func.sum(column), 0)).where(*conditions)
            )
        )

    def _current_scale(self, db, school_id: int) -> dict[str, int]:
        return {
            "teachers": self._count(
                db,
                self.User,
                self.User.school_id == school_id,
                self.User.role == "teacher",
                self.User.active.is_(True),
            ),
            "students": self._count(
                db,
                self.User,
                self.User.school_id == school_id,
                self.User.role == "student",
                self.User.active.is_(True),
            ),
            "classes": self._count(
                db,
                self.SchoolClass,
                self.SchoolClass.school_id == school_id,
            ),
        }

    def _activity(self, db, school_id: int, start_utc, end_utc) -> dict[str, int]:
        window = lambda column: (
            column >= start_utc,
            column < end_utc,
        )
        assignment_window = window(self.Assignment.created_at)
        submission_window = window(self.Submission.submitted_at)
        attempt_window = window(self.TeachingAttempt.created_at)
        evidence_window = window(self.LearningEvidenceEvent.created_at)

        return {
            "assignmentsCreated": self._count(
                db,
                self.Assignment,
                self.Assignment.school_id == school_id,
                *assignment_window,
            ),
            "submissions": self._count(
                db,
                self.Submission,
                self.Submission.school_id == school_id,
                *submission_window,
            ),
            "submissionQuestionUnits": self._sum(
                db,
                self.Submission.total,
                self.Submission.school_id == school_id,
                *submission_window,
            ),
            "teachingAttempts": self._count(
                db,
                self.TeachingAttempt,
                self.TeachingAttempt.school_id == school_id,
                *attempt_window,
            ),
            "teachingAttemptQuestionUnits": self._sum(
                db,
                self.TeachingAttempt.total,
                self.TeachingAttempt.school_id == school_id,
                *attempt_window,
            ),
            "learningEvidenceEvents": self._count(
                db,
                self.LearningEvidenceEvent,
                self.LearningEvidenceEvent.school_id == school_id,
                *evidence_window,
            ),
        }

    def _ai(self, db, school_id: int, start_utc, end_utc) -> dict[str, int]:
        conditions = (
            self.AIUsageLog.school_id == school_id,
            self.AIUsageLog.created_at >= start_utc,
            self.AIUsageLog.created_at < end_utc,
        )
        calls = self._count(db, self.AIUsageLog, *conditions)
        success = self._count(
            db,
            self.AIUsageLog,
            *conditions,
            self.AIUsageLog.status == "ok",
        )
        input_tokens = self._sum(db, self.AIUsageLog.input_tokens, *conditions)
        output_tokens = self._sum(db, self.AIUsageLog.output_tokens, *conditions)
        # 失败按类别分组：运营侧据此判断是超时、网络、还是模型真的读不出来。
        # 只统计失败记录；error 为空的历史记录归入 unknown，不猜原因。
        rows = db.execute(
            select(
                self.AIUsageLog.feature,
                self.AIUsageLog.status,
                self.AIUsageLog.error,
                func.count(),
            )
            .where(*conditions, self.AIUsageLog.status != "ok")
            .group_by(self.AIUsageLog.feature, self.AIUsageLog.status, self.AIUsageLog.error)
        ).all()
        breakdown: dict[str, dict[str, int]] = {}
        for feature, _status, error, count in rows:
            key = str(feature or "unknown")
            reason = str(error or "unknown")[:60]
            bucket = breakdown.setdefault(key, {})
            bucket[reason] = bucket.get(reason, 0) + int(count)

        return {
            "calls": calls,
            "successCalls": success,
            "failedCalls": max(0, calls - success),
            "inputTokens": input_tokens,
            "outputTokens": output_tokens,
            "totalTokens": input_tokens + output_tokens,
            "failureBreakdown": breakdown,
        }

    def _storage(self, db, school_id: int, start_utc, end_utc) -> dict[str, int]:
        homework_current = self._sum(
            db,
            self.HomeworkMedia.size_bytes,
            self.HomeworkMedia.school_id == school_id,
        )
        resource_current = self._sum(
            db,
            self.TeachingResource.size_bytes,
            self.TeachingResource.school_id == school_id,
        )
        homework_added = self._sum(
            db,
            self.HomeworkMedia.size_bytes,
            self.HomeworkMedia.school_id == school_id,
            self.HomeworkMedia.created_at >= start_utc,
            self.HomeworkMedia.created_at < end_utc,
        )
        resource_added = self._sum(
            db,
            self.TeachingResource.size_bytes,
            self.TeachingResource.school_id == school_id,
            self.TeachingResource.created_at >= start_utc,
            self.TeachingResource.created_at < end_utc,
        )
        return {
            "currentBytes": homework_current + resource_current,
            "addedBytes": homework_added + resource_added,
            "homeworkMediaBytes": homework_current,
            "teachingResourceBytes": resource_current,
        }

    def school_month(self, db, *, school_id: int, month: str | None = None) -> dict[str, Any]:
        school = db.get(self.School, school_id)
        if school is None:
            raise LookupError("school not found")
        period = billing_month_window(month)
        start_utc, end_utc = period["startUtc"], period["endUtc"]
        subscription = None
        if self.SchoolSubscription is not None:
            subscription = db.scalar(
                select(self.SchoolSubscription).where(
                    self.SchoolSubscription.school_id == school_id
                )
            )

        return {
            "meterVersion": METER_VERSION,
            "schoolID": school_id,
            "schoolName": getattr(school, "name", "") or "",
            "schoolActive": bool(getattr(school, "active", True)),
            "planCode": getattr(subscription, "plan_code", None) if subscription else None,
            "subscriptionStatus": getattr(subscription, "status", None) if subscription else None,
            "period": {
                "month": period["key"],
                "startLocal": period["startLocal"],
                "endLocalExclusive": period["endLocalExclusive"],
            },
            "scaleCurrent": self._current_scale(db, school_id),
            "activity": self._activity(db, school_id, start_utc, end_utc),
            "ai": self._ai(db, school_id, start_utc, end_utc),
            "storage": self._storage(db, school_id, start_utc, end_utc),
            "billing": {
                "measurementOnly": True,
                "autoCharge": False,
                "priceCalculated": False,
                "source": "existing-production-facts",
            },
        }

    def schools_month(self, db, *, month: str | None = None) -> dict[str, Any]:
        period = billing_month_window(month)
        rows = db.scalars(select(self.School).order_by(self.School.id)).all()
        schools = [
            self.school_month(db, school_id=int(row.id), month=period["key"])
            for row in rows
        ]
        return {
            "meterVersion": METER_VERSION,
            "period": {
                "month": period["key"],
                "startLocal": period["startLocal"],
                "endLocalExclusive": period["endLocalExclusive"],
            },
            "schools": schools,
            "totals": {
                "schools": len(schools),
                "teachers": sum(x["scaleCurrent"]["teachers"] for x in schools),
                "students": sum(x["scaleCurrent"]["students"] for x in schools),
                "classes": sum(x["scaleCurrent"]["classes"] for x in schools),
                "assignmentsCreated": sum(x["activity"]["assignmentsCreated"] for x in schools),
                "submissions": sum(x["activity"]["submissions"] for x in schools),
                "questionUnits": sum(
                    x["activity"]["submissionQuestionUnits"]
                    + x["activity"]["teachingAttemptQuestionUnits"]
                    for x in schools
                ),
                "aiCalls": sum(x["ai"]["calls"] for x in schools),
                "aiTokens": sum(x["ai"]["totalTokens"] for x in schools),
                "storageBytes": sum(x["storage"]["currentBytes"] for x in schools),
            },
            "billing": {
                "measurementOnly": True,
                "autoCharge": False,
                "priceCalculated": False,
            },
            "definitions": {
                "scaleCurrent": "当前有效教师/学生/班级规模，不代表历史峰值。",
                "questionUnits": "学生提交题量与自适应教学作答题量之和。",
                "aiTokens": "现有 AIUsageLog 中的输入 token + 输出 token。",
                "storageBytes": "当前作业媒体与教学资料文件大小之和。",
            },
        }


__all__ = [
    "CommercialUsageMeteringService",
    "METER_VERSION",
    "billing_month_window",
]
