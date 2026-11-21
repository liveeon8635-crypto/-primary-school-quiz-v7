"""Persisted weekend lesson types and per-classroom frozen content snapshots."""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy import Column, DateTime, Integer, String, Table, Text, UniqueConstraint, insert, select, update
from sqlalchemy.exc import IntegrityError

COURSE_TYPES = {"reading", "writing"}


class WorkflowRevisionConflict(Exception):
    """A competing teacher update changed the selected course workflow."""


def practice_stage(course_type: str | None) -> int:
    """Stage where the existing written/choice task API accepts submissions."""
    if course_type in COURSE_TYPES:
        return 5
    return 4
LESSON_CONTENT_FIELDS = (
    "id", "school_id", "program_id", "subject", "lesson_no", "unit", "title",
    "core_target", "duration_min", "teacher_plan", "reading_plan", "writing_plan",
    "examples_json", "ppt_json", "closure_training", "essay_review",
)


def register_weekend_course_type_tables(implementation: Any) -> dict[str, Table]:
    md = implementation.Base.metadata
    config = md.tables.get("weekend_lesson_workflows")
    if config is None:
        config = Table(
            "weekend_lesson_workflows", md,
            Column("id", Integer, primary_key=True),
            Column("school_id", Integer, nullable=False, index=True),
            Column("program_id", Integer, nullable=False, index=True),
            Column("subject", String(20), nullable=False),
            Column("lesson_no", Integer, nullable=False),
            Column("lesson_id", Integer, nullable=True, index=True),
            Column("course_type", String(20), nullable=False),
            Column("revision", Integer, nullable=False, default=1),
            Column("updated_by", Integer, nullable=False),
            Column("updated_at", DateTime, nullable=False, default=datetime.utcnow),
            UniqueConstraint("school_id", "program_id", "subject", "lesson_no", name="uq_weekend_lesson_workflow"),
        )
    frozen = md.tables.get("weekend_session_workflows")
    if frozen is None:
        frozen = Table(
            "weekend_session_workflows", md,
            Column("session_id", Integer, primary_key=True),
            Column("school_id", Integer, nullable=False, index=True),
            Column("lesson_id", Integer, nullable=False, index=True),
            Column("course_type", String(20), nullable=False),
            Column("revision", Integer, nullable=False),
            Column("lesson_json", Text, nullable=False),
            Column("created_at", DateTime, nullable=False, default=datetime.utcnow),
        )
    materials = md.tables.get("weekend_lesson_materials")
    if materials is None:
        materials = Table(
            "weekend_lesson_materials", md,
            Column("id", Integer, primary_key=True),
            Column("school_id", Integer, nullable=False, index=True),
            Column("lesson_id", Integer, nullable=False, index=True),
            Column("source_file", String(240), nullable=False),
            Column("source_part", String(160), nullable=False),
            Column("source_sha256", String(64), nullable=False),
            Column("source_format", String(20), nullable=False),
            Column("media_type", String(30), nullable=False),
            Column("data_url", Text, nullable=False),
            Column("status", String(20), nullable=False, default="pending"),
            Column("relationship", String(40), nullable=False, default=""),
            Column("stage_no", Integer, nullable=True),
            Column("sort_order", Integer, nullable=False, default=0),
            Column("revision", Integer, nullable=False, default=1),
            Column("created_by", Integer, nullable=False),
            Column("created_at", DateTime, nullable=False, default=datetime.utcnow),
            Column("reviewed_by", Integer, nullable=True),
            Column("reviewed_at", DateTime, nullable=True),
            UniqueConstraint("lesson_id", "source_file", "source_sha256", name="uq_weekend_lesson_material_source"),
        )
    return {"config": config, "frozen": frozen, "materials": materials}


def store_pending_materials(
    db: Any,
    implementation: Any,
    *,
    school_id: int,
    lesson_id: int,
    source_file: str,
    created_by: int,
    figures: list[dict[str, Any]],
) -> int:
    """Persist extracted pictures as teacher-only pending material, never as approved courseware."""
    table = register_weekend_course_type_tables(implementation)["materials"]
    stored = 0
    for index, figure in enumerate(figures, start=1):
        url = str(figure.get("data_url") or "")
        if not url.startswith(("data:image/jpeg;base64,", "data:image/png;base64,")) or len(url) > 700_000:
            continue
        part = str(figure.get("source_name") or f"image-{index}")[:160]
        digest = str(figure.get("source_sha256") or "")
        if len(digest) != 64:
            import hashlib
            digest = hashlib.sha256(url.encode("ascii", "ignore")).hexdigest()
        exists = db.execute(select(table.c.id).where(
            table.c.lesson_id == int(lesson_id), table.c.source_file == str(source_file)[:240],
            table.c.source_sha256 == digest,
        )).first()
        if exists:
            continue
        db.execute(insert(table).values(
            school_id=int(school_id), lesson_id=int(lesson_id), source_file=str(source_file)[:240],
            source_part=part, source_sha256=digest,
            source_format=str(figure.get("source_format") or "unknown")[:20],
            media_type="image", data_url=url, status="pending", relationship="", stage_no=None,
            sort_order=index, revision=1, created_by=int(created_by), created_at=datetime.utcnow(),
        ))
        stored += 1
    return stored


def workflow_for(db: Any, implementation: Any, lesson: Any) -> Any | None:
    tables = register_weekend_course_type_tables(implementation)
    return db.execute(select(tables["config"]).where(
        tables["config"].c.school_id == int(lesson.school_id),
        tables["config"].c.program_id == int(lesson.program_id),
        tables["config"].c.subject == str(lesson.subject),
        tables["config"].c.lesson_no == int(lesson.lesson_no),
    )).first()


def course_type_for(db: Any, implementation: Any, lesson: Any) -> str | None:
    if str(lesson.subject) == "数学":
        return "math"
    row = workflow_for(db, implementation, lesson)
    value = str(row.course_type) if row is not None else ""
    return value if value in COURSE_TYPES else None


def compare_and_set_course_type(
    db: Any,
    implementation: Any,
    *,
    school_id: int,
    program_id: int,
    lesson_no: int,
    lesson_id: int | None,
    course_type: str,
    expected_revision: int,
    updated_by: int,
    updated_at: datetime,
) -> int:
    """Persist a course choice only when the teacher edited the current revision."""
    if course_type not in COURSE_TYPES:
        raise ValueError("unsupported course type")
    table = register_weekend_course_type_tables(implementation)["config"]
    row = db.execute(select(table).where(
        table.c.school_id == int(school_id), table.c.program_id == int(program_id),
        table.c.subject == "语文", table.c.lesson_no == int(lesson_no),
    ).with_for_update()).first()
    current_revision = int(row.revision) if row else 0
    if current_revision != int(expected_revision):
        db.rollback()
        raise WorkflowRevisionConflict
    values = {
        "course_type": course_type,
        "lesson_id": int(lesson_id) if lesson_id is not None else None,
        "revision": current_revision + 1,
        "updated_by": int(updated_by),
        "updated_at": updated_at,
    }
    if row:
        result = db.execute(update(table).where(
            table.c.id == row.id, table.c.revision == current_revision,
        ).values(**values))
        if result.rowcount != 1:
            db.rollback()
            raise WorkflowRevisionConflict
    else:
        try:
            db.execute(insert(table).values(
                school_id=int(school_id), program_id=int(program_id),
                subject="语文", lesson_no=int(lesson_no), **values,
            ))
        except IntegrityError as exc:
            db.rollback()
            raise WorkflowRevisionConflict from exc
    return current_revision + 1


def lesson_snapshot(lesson: Any) -> str:
    payload = {key: getattr(lesson, key, None) for key in LESSON_CONTENT_FIELDS}
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def frozen_session(
    db: Any, implementation: Any, session_id: int, *, table: Any = None, metadata: Any = None,
) -> dict[str, Any] | None:
    """The course type a classroom froze when it was created.

    ``table`` lets a caller that only has the metadata (the launch-time cleanup classifier) read
    the snapshot with an empty registry instead of registering the tables as a side effect.
    ``metadata`` does the same when the caller owns the tables but not the implementation module;
    the snapshot is then absent instead of raising when the tables were never registered.
    """
    if table is None and metadata is not None:
        table = metadata.tables.get("weekend_session_workflows")
        if table is None:
            return None
    if table is None:
        table = register_weekend_course_type_tables(implementation)["frozen"]
    row = db.execute(select(table).where(table.c.session_id == int(session_id))).first()
    if row is None:
        return None
    try:
        lesson = json.loads(row.lesson_json)
    except (TypeError, json.JSONDecodeError):
        return None
    return {"courseType": str(row.course_type), "revision": int(row.revision), "lesson": lesson}


__all__ = [
    "COURSE_TYPES", "LESSON_CONTENT_FIELDS", "register_weekend_course_type_tables", "store_pending_materials",
    "workflow_for", "course_type_for", "compare_and_set_course_type", "WorkflowRevisionConflict",
    "lesson_snapshot", "frozen_session",
]
