from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from changying.web.v1_parent_link_history import (
    parent_link_history,
)


class Column:
    def __eq__(self, other):
        return self
    def in_(self, other):
        return self
    def like(self, other):
        return self
    def asc(self):
        return self


class SelectStub:
    def where(self, *args):
        return self
    def order_by(self, *args):
        return self


class ScalarsResult:
    def __init__(self, rows):
        self.rows = rows
    def all(self):
        return list(self.rows)


class FakeDB:
    def __init__(self, logs, links, users):
        self.logs = logs
        self.links = links
        self.users = users
        self.calls = 0

    def scalars(self, stmt):
        self.calls += 1
        return ScalarsResult(self.logs if self.calls == 1 else self.links)

    def get(self, model, ident):
        return self.users.get(ident)


def implementation():
    Audit = SimpleNamespace(
        school_id=Column(),
        action=Column(),
        detail=Column(),
        created_at=Column(),
        id=Column(),
    )
    ParentStudent = SimpleNamespace(student_id=Column())
    return SimpleNamespace(
        AuditLog=Audit,
        ParentStudent=ParentStudent,
        User=object(),
        select=lambda model: SelectStub(),
        school_local_iso=lambda dt: dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M"),
    )


def log(action, detail, minute):
    return SimpleNamespace(
        action=action,
        detail=detail,
        created_at=datetime(2026, 9, 1, 8, minute, tzinfo=timezone.utc),
        id=minute,
    )


def test_bind_then_unbind_produces_closed_interval():
    db = FakeDB(
        [
            log("parent.bind", "7:小明:11:妈妈", 0),
            log("parent.unbind", "7:小明:妈妈", 10),
        ],
        [],
        {},
    )
    rows = parent_link_history(implementation(), db, 7, 3)
    assert len(rows) == 1
    assert rows[0]["parentID"] == 11
    assert rows[0]["parentName"] == "妈妈"
    assert rows[0]["current"] is False
    assert rows[0]["endReason"] == "unbind"
    assert rows[0]["startKnown"] is True
    assert rows[0]["endKnown"] is True


def test_rebind_closes_previous_parent_at_new_bind_time():
    db = FakeDB(
        [
            log("parent.bind", "7:小明:11:妈妈", 0),
            log("parent.bind", "7:小明:12:爸爸", 10),
        ],
        [SimpleNamespace(parent_id=12)],
        {12: SimpleNamespace(name="爸爸")},
    )
    rows = parent_link_history(implementation(), db, 7, 3)
    by_id = {row["parentID"]: row for row in rows}
    assert by_id[11]["endReason"] == "replaced"
    assert by_id[11]["endedAt"] == "2026-09-01 08:10"
    assert by_id[12]["current"] is True


def test_current_link_without_audit_keeps_unknown_start_explicit():
    db = FakeDB(
        [],
        [SimpleNamespace(parent_id=12)],
        {12: SimpleNamespace(name="爸爸")},
    )
    rows = parent_link_history(implementation(), db, 7, 3)
    assert rows == [
        {
            "parentID": 12,
            "parentName": "爸爸",
            "startedAt": None,
            "endedAt": None,
            "endReason": "",
            "current": True,
            "source": "current_link",
            "startKnown": False,
            "endKnown": True,
        }
    ]


def test_open_audit_relation_not_in_current_storage_is_not_called_current():
    db = FakeDB(
        [log("parent.bind", "7:小明:11:妈妈", 0)],
        [],
        {},
    )
    rows = parent_link_history(implementation(), db, 7, 3)
    assert rows[0]["current"] is False
    assert rows[0]["endedAt"] is None
    assert rows[0]["endKnown"] is False
    assert rows[0]["endReason"] == "ended_time_unknown"


def test_malformed_audit_bind_is_skipped_not_guessed():
    db = FakeDB(
        [log("parent.bind", "7:小明:不是ID:妈妈", 0)],
        [],
        {},
    )
    assert parent_link_history(implementation(), db, 7, 3) == []
