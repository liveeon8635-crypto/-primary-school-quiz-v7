"""Schema for the after-school homework assistant (migration only).

Three new tables, registered on the legacy ``Base.metadata`` so the existing startup
``Base.metadata.create_all`` creates them when they are missing. No existing table is altered
and nothing reads or writes these tables yet: the first users are the follow-up PRs listed in
``docs/analysis/after-school-homework-assistant.md`` (section 10).

The tables are created whether or not the (future) ``HOMEWORK_ASSISTANT`` feature flag is on,
so a later deploy never has to change the schema at the same time as it switches a feature on.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Table, Text, UniqueConstraint

HOMEWORK_ASSISTANT_TABLES = ("homework_notices", "homework_recipients", "help_requests")


def _utcnow() -> datetime:
    return datetime.utcnow()


def register_homework_assistant_tables(implementation: Any) -> dict[str, Table]:
    """Idempotently register the three tables on ``implementation.Base.metadata``."""
    metadata = implementation.Base.metadata

    notices = metadata.tables.get("homework_notices")
    if notices is None:
        notices = Table(
            "homework_notices",
            metadata,
            Column("id", Integer, primary_key=True),
            Column("school_id", Integer, ForeignKey("schools.id"), nullable=False, index=True),
            Column("teacher_id", Integer, ForeignKey("users.id"), nullable=False, index=True),
            Column("group_label", String(120), nullable=False, default=""),
            Column("source_kind", String(10), nullable=False, default="text"),
            Column("raw_text", Text, nullable=False, default=""),
            Column("items_json", Text, nullable=False, default="[]"),
            Column("status", String(12), nullable=False, default="draft", index=True),
            Column("created_at", DateTime, nullable=False, default=_utcnow, index=True),
            Column("published_at", DateTime, nullable=True),
            # 本次全部科目的总时长（分钟）。NULL = 未启用计时，历史通知保持不变。
            Column("time_limit_minutes", Integer, nullable=True),
        )

    recipients = metadata.tables.get("homework_recipients")
    if recipients is None:
        recipients = Table(
            "homework_recipients",
            metadata,
            Column("id", Integer, primary_key=True),
            Column("school_id", Integer, ForeignKey("schools.id"), nullable=False, index=True),
            Column("notice_id", Integer, ForeignKey("homework_notices.id"), nullable=False, index=True),
            Column("student_id", Integer, ForeignKey("users.id"), nullable=False, index=True),
            Column("done_json", Text, nullable=False, default="[]"),
            Column("created_at", DateTime, nullable=False, default=_utcnow),
            # 学生实际开始时间与全部完成时间；由服务端写入，刷新/换设备不重置。
            Column("started_at", DateTime, nullable=True),
            Column("completed_at", DateTime, nullable=True),
            UniqueConstraint("notice_id", "student_id", name="uq_homework_recipient_notice_student"),
        )

    helps = metadata.tables.get("help_requests")
    if helps is None:
        helps = Table(
            "help_requests",
            metadata,
            Column("id", Integer, primary_key=True),
            Column("school_id", Integer, ForeignKey("schools.id"), nullable=False, index=True),
            Column("student_id", Integer, ForeignKey("users.id"), nullable=False, index=True),
            Column("grade", Integer, nullable=True),
            Column("notice_id", Integer, ForeignKey("homework_notices.id"), nullable=True, index=True),
            Column("item_idx", Integer, nullable=True),
            Column("question_text", Text, nullable=False, default=""),
            Column("ai_json", Text, nullable=False, default="{}"),
            Column("verify_status", String(12), nullable=False, default="skipped"),
            Column("state", String(12), nullable=False, default="confirmed", index=True),
            Column("student_note", Text, nullable=False, default=""),
            Column("teacher_note", Text, nullable=False, default=""),
            Column("escalate_reason", String(40), nullable=False, default=""),
            Column("created_at", DateTime, nullable=False, default=_utcnow, index=True),
            Column("escalated_at", DateTime, nullable=True, index=True),
            Column("resolved_at", DateTime, nullable=True),
        )

    registered = {"homework_notices": notices, "homework_recipients": recipients, "help_requests": helps}
    assert tuple(registered) == HOMEWORK_ASSISTANT_TABLES
    return registered


def ensure_time_columns(engine: Any) -> None:
    """给已有的晚托表补上计时列；不改历史数据，NULL 表示未启用计时。"""
    from sqlalchemy import inspect, text as sql_text

    wanted = {
        "homework_notices": ("time_limit_minutes", "INTEGER"),
        "homework_recipients": ("started_at", "TIMESTAMP"),
    }
    inspector = inspect(engine)
    with engine.begin() as conn:
        for table, (column, ddl_type) in wanted.items():
            if not inspector.has_table(table):
                continue
            have = {c["name"] for c in inspector.get_columns(table)}
            if column in have:
                continue
            conn.execute(sql_text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl_type}"))
    # recipients 还有 completed_at
    inspector = inspect(engine)
    with engine.begin() as conn:
        if inspector.has_table("homework_recipients"):
            have = {c["name"] for c in inspector.get_columns("homework_recipients")}
            if "completed_at" not in have:
                conn.execute(sql_text("ALTER TABLE homework_recipients ADD COLUMN completed_at TIMESTAMP"))
