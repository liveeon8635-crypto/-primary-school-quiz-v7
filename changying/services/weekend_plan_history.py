"""Transactional undo for a weekend lesson re-import, scoped to teaching content."""
import hashlib
import json
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import Column, DateTime, Integer, String, Table, Text, delete, insert, select
from sqlalchemy.exc import IntegrityError


def register_history(metadata):
    name = "weekend_plan_import_history"
    if name not in metadata.tables:
        Table(name, metadata,
              Column("id", Integer, primary_key=True),
              Column("lesson_id", Integer, nullable=False, index=True),
              Column("school_id", Integer, nullable=False),
              Column("teacher_id", Integer, nullable=False),
              Column("before_json", Text, nullable=False),
              Column("after_hash", String(64), nullable=False))
    return metadata.tables[name]


def capture(db, lesson, choices, written, courseware, removed_stage):
    """Include unchanged approved rows in the digest so later edits block an undo."""
    db.flush()
    state = {"lesson": {c.name: getattr(lesson, c.name) for c in lesson.__table__.columns}}
    for key, table, condition in (
        ("choices", choices, choices.c.stage != removed_stage),
        ("written", written, written.c.session_id == 0),
        ("courseware", courseware, courseware.c.lesson_id == lesson.id),
    ):
        rows = db.execute(select(table).where(table.c.school_id == lesson.school_id,
            table.c.lesson_id == lesson.id, condition).order_by(table.c.id).with_for_update())
        state[key] = [dict(row) for row in rows.mappings()]
    return state


def serialize(state):
    return json.dumps(state, ensure_ascii=False, sort_keys=True, default=datetime.isoformat)


def digest(state):
    return hashlib.sha256(serialize(state).encode()).hexdigest()


def restore_content(db, lesson, before, current, choices, written, courseware):
    """Reconcile IDs in place; approved questions and their references usually need no write."""
    for name, value in before["lesson"].items():
        col = lesson.__table__.c[name]
        if isinstance(col.type, DateTime) and value is not None:
            value = datetime.fromisoformat(value)
        if getattr(lesson, name) != value:
            setattr(lesson, name, value)
    try:
        for key, table in (("choices", choices), ("written", written), ("courseware", courseware)):
            old = {row["id"]: row for row in before[key]}
            now = {row["id"]: row for row in current[key]}
            for row_id in now.keys() - old.keys():
                db.execute(delete(table).where(table.c.id == row_id, table.c.lesson_id == lesson.id))
            for row_id, row in old.items():
                values = {name: datetime.fromisoformat(v) if v is not None and isinstance(table.c[name].type, DateTime)
                          else v for name, v in row.items()}
                if row_id not in now:
                    db.execute(insert(table).values(**values))
                elif now[row_id] != values:
                    db.execute(table.update().where(table.c.id == row_id, table.c.lesson_id == lesson.id).values(**values))
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "题目或课件记录已被引用，无法安全恢复。") from exc
