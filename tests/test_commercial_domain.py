from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace

from changying.domain.commercial import (
    COMMERCIAL_PLANS,
    FEATURE_NAMES,
    SUBSCRIPTION_STATUS_NAMES,
    commercial_plan,
    effective_subscription_status,
)


def _subscription(status: str, *, trial=None, period=None, grace=None):
    return SimpleNamespace(
        status=status,
        trial_ends_at=trial,
        current_period_ends_at=period,
        grace_ends_at=grace,
    )


def test_commercial_plan_catalog_and_fallback_contract():
    assert list(COMMERCIAL_PLANS) == [
        "free",
        "teacher_pro",
        "school_basic",
        "school_standard",
        "custom",
    ]
    assert commercial_plan("teacher_pro")["annualPrice"] == 299
    assert commercial_plan("school_standard")["limits"]["students"] == 1500
    assert commercial_plan("unknown") is COMMERCIAL_PLANS["free"]
    assert commercial_plan(None) is COMMERCIAL_PLANS["free"]
    assert SUBSCRIPTION_STATUS_NAMES["grace"] == "宽限期"
    assert FEATURE_NAMES["school_backup"] == "学校数据备份"


def test_trial_status_expires_at_deadline():
    now = datetime(2026, 9, 14, 8, 0, 0)
    assert effective_subscription_status(
        _subscription("trial", trial=now + timedelta(seconds=1)), now
    ) == "trial"
    assert effective_subscription_status(
        _subscription("trial", trial=now), now
    ) == "expired"


def test_active_status_transitions_to_grace_then_expired():
    now = datetime(2026, 9, 14, 8, 0, 0)
    active = _subscription("active", period=now + timedelta(days=1))
    assert effective_subscription_status(active, now) == "active"

    grace = _subscription(
        "active",
        period=now,
        grace=now + timedelta(days=7),
    )
    assert effective_subscription_status(grace, now) == "grace"

    expired = _subscription("active", period=now, grace=now)
    assert effective_subscription_status(expired, now) == "expired"


def test_explicit_grace_and_custom_status_contract():
    now = datetime(2026, 9, 14, 8, 0, 0)
    assert effective_subscription_status(
        _subscription("grace", grace=now + timedelta(seconds=1)), now
    ) == "grace"
    assert effective_subscription_status(
        _subscription("grace", grace=now), now
    ) == "expired"
    assert effective_subscription_status(_subscription("expired"), now) == "expired"
    assert effective_subscription_status(_subscription("paused"), now) == "paused"


def test_production_loader_installs_commercial_rules():
    import app_v924 as legacy
    import changying.production  # noqa: F401

    assert legacy.COMMERCIAL_PLANS is COMMERCIAL_PLANS
    assert legacy.SUBSCRIPTION_STATUS_NAMES is SUBSCRIPTION_STATUS_NAMES
    assert legacy.FEATURE_NAMES is FEATURE_NAMES
    assert legacy._commercial_plan is commercial_plan
    assert legacy._effective_subscription_status is effective_subscription_status
