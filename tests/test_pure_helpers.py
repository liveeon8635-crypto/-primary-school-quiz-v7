from __future__ import annotations

from datetime import datetime, timezone

from changying.utils.datetime_tools import SCHOOL_TZ, due_deadline_utc, school_local_iso
from changying.utils.json_tools import json_list


def test_json_list_matches_legacy_fallback_behavior():
    assert json_list('[1, "x"]') == [1, "x"]
    assert json_list('{"not": "a list"}') == []
    assert json_list('not-json') == []
    assert json_list(None) == []


def test_due_deadline_date_uses_end_of_school_day():
    assert due_deadline_utc("2026-09-14") == datetime(2026, 9, 14, 15, 59, 59)


def test_due_deadline_handles_aware_timestamp():
    assert due_deadline_utc("2026-09-14T08:30:00Z") == datetime(2026, 9, 14, 8, 30)
    assert due_deadline_utc("bad-date") is None


def test_school_local_iso_converts_naive_utc_to_school_timezone():
    assert school_local_iso(datetime(2026, 9, 14, 0, 0)) == "2026-09-14 08:00"
    assert school_local_iso(datetime(2026, 9, 14, 0, 0, tzinfo=timezone.utc)) == "2026-09-14 08:00"
    assert school_local_iso(None) == ""
    assert SCHOOL_TZ.utcoffset(None).total_seconds() == 8 * 3600


def test_production_loader_installs_legacy_compatibility_hooks():
    import app_v924 as legacy
    import changying.production  # noqa: F401 - importing installs compatibility hooks

    assert legacy.SCHOOL_TZ is SCHOOL_TZ
    assert legacy.due_deadline_utc is due_deadline_utc
    assert legacy.school_local_iso is school_local_iso
    assert legacy._json_list is json_list
