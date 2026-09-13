"""Pure commercial-plan and subscription-status rules.

This module intentionally contains no database access. It mirrors the existing
production rules so pricing/limits/status decisions can be tested independently
before the database-backed commercial APIs are modularized.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any


COMMERCIAL_PLANS = {
    "free": {
        "code": "free",
        "name": "免费体验版",
        "monthlyPrice": 0,
        "annualPrice": 0,
        "limits": {"teachers": 1, "classes": 2, "students": 80},
        "features": {
            "growth_profile": True,
            "growth_report": False,
            "parent_communication": False,
            "bulk_import": False,
            "school_backup": False,
            "school_audit": False,
        },
    },
    "teacher_pro": {
        "code": "teacher_pro",
        "name": "教师专业版",
        "monthlyPrice": 39,
        "annualPrice": 299,
        "limits": {"teachers": 1, "classes": 10, "students": 500},
        "features": {
            "growth_profile": True,
            "growth_report": True,
            "parent_communication": True,
            "bulk_import": False,
            "school_backup": False,
            "school_audit": False,
        },
    },
    "school_basic": {
        "code": "school_basic",
        "name": "学校基础版",
        "monthlyPrice": None,
        "annualPrice": 2980,
        "limits": {"teachers": 10, "classes": None, "students": 500},
        "features": {
            "growth_profile": True,
            "growth_report": True,
            "parent_communication": True,
            "bulk_import": True,
            "school_backup": True,
            "school_audit": True,
        },
    },
    "school_standard": {
        "code": "school_standard",
        "name": "学校标准版",
        "monthlyPrice": None,
        "annualPrice": 6800,
        "limits": {"teachers": 30, "classes": None, "students": 1500},
        "features": {
            "growth_profile": True,
            "growth_report": True,
            "parent_communication": True,
            "bulk_import": True,
            "school_backup": True,
            "school_audit": True,
        },
    },
    "custom": {
        "code": "custom",
        "name": "学校定制版",
        "monthlyPrice": None,
        "annualPrice": None,
        "limits": {"teachers": None, "classes": None, "students": None},
        "features": {
            "growth_profile": True,
            "growth_report": True,
            "parent_communication": True,
            "bulk_import": True,
            "school_backup": True,
            "school_audit": True,
        },
    },
}

SUBSCRIPTION_STATUS_NAMES = {
    "trial": "试用中",
    "active": "已开通",
    "grace": "宽限期",
    "expired": "已到期",
}

FEATURE_NAMES = {
    "growth_profile": "学生成长档案",
    "growth_report": "成长报告导出",
    "parent_communication": "家校沟通",
    "bulk_import": "批量导入",
    "school_backup": "学校数据备份",
    "school_audit": "全校审计",
}


def commercial_plan(code: str | None) -> dict:
    return COMMERCIAL_PLANS.get(code or "") or COMMERCIAL_PLANS["free"]


def effective_subscription_status(row: Any, now: datetime | None = None) -> str:
    now = now or datetime.utcnow()
    status = (row.status or "active").lower()

    if status == "trial":
        if row.trial_ends_at and row.trial_ends_at <= now:
            return "expired"
        return "trial"

    if status == "active":
        if row.current_period_ends_at and row.current_period_ends_at <= now:
            if row.grace_ends_at and row.grace_ends_at > now:
                return "grace"
            return "expired"
        return "active"

    if status == "grace":
        if row.grace_ends_at and row.grace_ends_at <= now:
            return "expired"
        return "grace"

    return "expired" if status == "expired" else status


__all__ = [
    "COMMERCIAL_PLANS",
    "FEATURE_NAMES",
    "SUBSCRIPTION_STATUS_NAMES",
    "commercial_plan",
    "effective_subscription_status",
]
