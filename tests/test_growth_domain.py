from __future__ import annotations

from datetime import datetime

from changying.domain.growth import (
    auto_period_window,
    calendar_week_window_utc,
    day_window_utc,
    discipline_streak_from_trend,
    period_cutoff_utc,
    progress_streak_from_trend,
)
from changying.utils.datetime_tools import SCHOOL_TZ


FIXED_NOW = datetime(2026, 9, 16, 10, 30, tzinfo=SCHOOL_TZ)


def test_period_cutoff_is_clamped_and_school_timezone_aware():
    cutoff, days = period_cutoff_utc(7, FIXED_NOW)
    assert days == 7
    assert cutoff == datetime(2026, 9, 9, 2, 30)

    _, minimum = period_cutoff_utc(0, FIXED_NOW)
    _, maximum = period_cutoff_utc(999, FIXED_NOW)
    assert minimum == 7  # legacy ``days or 7`` behavior
    assert maximum == 90


def test_week_and_day_windows_match_school_calendar_boundaries():
    start, end, start_date, end_date = calendar_week_window_utc(0, FIXED_NOW)
    assert start == datetime(2026, 9, 13, 16, 0)
    assert end == datetime(2026, 9, 20, 16, 0)
    assert start_date == "2026-09-14"
    assert end_date == "2026-09-20"

    day_start, day_end, day_key = day_window_utc(0, FIXED_NOW)
    assert day_start == datetime(2026, 9, 15, 16, 0)
    assert day_end == datetime(2026, 9, 16, 16, 0)
    assert day_key == "2026-09-16"


def test_automatic_reward_period_windows_preserve_weekly_and_monthly_keys():
    weekly_start, weekly_key, weekly_period = auto_period_window("weekly", FIXED_NOW)
    assert weekly_start == datetime(2026, 9, 13, 16, 0)
    assert weekly_key == "2026-W38"
    assert weekly_period == "weekly"

    monthly_start, monthly_key, monthly_period = auto_period_window("monthly", FIXED_NOW)
    assert monthly_start == datetime(2026, 8, 31, 16, 0)
    assert monthly_key == "2026-09"
    assert monthly_period == "monthly"

    _, _, fallback_period = auto_period_window("unknown", FIXED_NOW)
    assert fallback_period == "weekly"


def test_growth_streak_rules_preserve_legacy_direction():
    trend = [{"net": 0}, {"net": 1}, {"net": 3}, {"net": 4}]
    assert progress_streak_from_trend(trend) == 3
    assert progress_streak_from_trend([{"net": 1}, {"net": 2}, {"net": 2}]) == 0
    assert progress_streak_from_trend([{"net": 1}]) == 0

    discipline = [{"discipline": 0}, {"discipline": -1}, {"discipline": -2}]
    assert discipline_streak_from_trend(discipline) == 2
    assert discipline_streak_from_trend([{"discipline": -1}, {"discipline": 0}]) == 0


def test_production_loader_installs_growth_rules():
    import app_v924 as legacy
    import changying.production  # noqa: F401

    assert legacy.period_cutoff_utc is period_cutoff_utc
    assert legacy.auto_period_window is auto_period_window
    assert legacy.calendar_week_window_utc is calendar_week_window_utc
    assert legacy.day_window_utc is day_window_utc
    assert legacy._progress_streak_from_trend is progress_streak_from_trend
    assert legacy._discipline_streak_from_trend is discipline_streak_from_trend
