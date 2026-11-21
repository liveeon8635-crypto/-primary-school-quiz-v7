"""课堂节点逐级开放与撤回服务层（块四：node_reveal_states）。"""

from __future__ import annotations

from datetime import datetime
import importlib
from typing import Any

from sqlalchemy import Column, DateTime, Integer, String, Table, UniqueConstraint, select


REVEAL_LEVELS = ("hidden", "hint", "answer", "analysis")

_default_implementation: Any = None


def _resolve_implementation(implementation: Any = None) -> Any:
    global _default_implementation
    if implementation is not None:
        _default_implementation = implementation
        return implementation
    if _default_implementation is not None:
        return _default_implementation
    _default_implementation = importlib.import_module("app_v924")
    return _default_implementation


def register_node_reveal_states_table(implementation: Any = None) -> Table:
    """在 implementation.Base.metadata 中注册 node_reveal_states 表。"""
    impl = _resolve_implementation(implementation)
    md = impl.Base.metadata
    table = md.tables.get("node_reveal_states")
    if table is None:
        table = Table(
            "node_reveal_states",
            md,
            Column("id", Integer, primary_key=True),
            Column("school_id", Integer, nullable=False, index=True, default=0),
            Column("classroom_session_id", Integer, nullable=False, index=True),
            Column("lesson_id", Integer, nullable=True, index=True),
            Column("class_id", Integer, nullable=True, index=True),
            Column("node_id", String(40), nullable=False, index=True),
            Column("reveal_level", String(16), nullable=False),
            Column("revealed_by", Integer, nullable=False, default=0),
            Column("revealed_at", DateTime, nullable=False, default=datetime.utcnow),
            Column("revoked_at", DateTime, nullable=True),
            Column("revoke_reason", String(200), nullable=True),
            UniqueConstraint("classroom_session_id", "node_id", name="uq_node_reveal_states_session_node"),
        )
    return table


def _reveal_row_to_dict(row: Any) -> dict[str, Any]:
    data = dict(row._mapping) if hasattr(row, "_mapping") else dict(row)
    return {
        "id": int(data["id"]),
        "school_id": int(data["school_id"]),
        "classroom_session_id": int(data["classroom_session_id"]),
        "lesson_id": int(data["lesson_id"]) if data.get("lesson_id") is not None else None,
        "class_id": int(data["class_id"]) if data.get("class_id") is not None else None,
        "node_id": str(data["node_id"]),
        "reveal_level": str(data["reveal_level"]),
        "revealed_by": int(data["revealed_by"]),
        "revealed_at": data["revealed_at"],
        "revoked_at": data["revoked_at"],
        "revoke_reason": data["revoke_reason"],
        "is_active": data["revoked_at"] is None,
    }


def _infer_session_context(
    session: Any,
    impl: Any,
    session_id: int,
    school_id: int | None,
    lesson_id: int | None,
    class_id: int | None,
) -> tuple[int, int | None, int | None, int | None]:
    md = impl.Base.metadata
    resolved_school = school_id
    resolved_lesson = lesson_id
    resolved_class = class_id
    resolved_teacher = None

    classroom_sessions = md.tables.get("classroom_sessions")
    if classroom_sessions is not None:
        row = session.execute(
            select(classroom_sessions).where(classroom_sessions.c.id == int(session_id))
        ).first()
        if row is not None:
            data = dict(row._mapping) if hasattr(row, "_mapping") else dict(row)
            if resolved_school is None and data.get("school_id") is not None:
                resolved_school = int(data["school_id"])
            if resolved_lesson is None and data.get("lesson_id") is not None:
                resolved_lesson = int(data["lesson_id"])
            if resolved_class is None and data.get("class_id") is not None:
                resolved_class = int(data["class_id"])
            if data.get("teacher_id") is not None:
                resolved_teacher = int(data["teacher_id"])

    if resolved_school is None:
        weekend_sessions = md.tables.get("weekend_sessions")
        if weekend_sessions is not None:
            row = session.execute(
                select(weekend_sessions).where(weekend_sessions.c.id == int(session_id))
            ).first()
            if row is not None:
                data = dict(row._mapping) if hasattr(row, "_mapping") else dict(row)
                if data.get("school_id") is not None:
                    resolved_school = int(data["school_id"])
                if resolved_lesson is None and data.get("lesson_id") is not None:
                    resolved_lesson = int(data["lesson_id"])
                if data.get("teacher_id") is not None:
                    resolved_teacher = int(data["teacher_id"])

    if resolved_school is None:
        resolved_school = 1
    if resolved_lesson is None:
        resolved_lesson = 0
    return int(resolved_school), resolved_lesson, resolved_class, resolved_teacher


def reveal_node(
    session_id: int,
    node_id: str,
    level: str,
    *,
    revealed_by: int | None = None,
    school_id: int | None = None,
    lesson_id: int | None = None,
    class_id: int | None = None,
    db: Any = None,
    implementation: Any = None,
) -> dict[str, Any]:
    """在指定课堂实例中开放或调整节点显示层级；若此前撤回过则恢复为有效状态（revoked_at 置回 None）。"""
    clean_level = str(level or "").strip()
    if clean_level not in REVEAL_LEVELS:
        raise ValueError(f"开放层级不合法：{level}，必须为 hidden、hint、answer 或 analysis")
    clean_node_id = str(node_id or "").strip()
    if not clean_node_id or len(clean_node_id) > 40:
        raise ValueError("节点 ID 不能为空且长度不能超过 40 个字符")

    impl = _resolve_implementation(implementation)
    table = register_node_reveal_states_table(impl)

    def _run(session: Any) -> dict[str, Any]:
        resolved_school, resolved_lesson, resolved_class, resolved_teacher = _infer_session_context(
            session, impl, int(session_id), school_id, lesson_id, class_id
        )
        actor_id = int(revealed_by if revealed_by is not None else (resolved_teacher or 0))
        now = datetime.utcnow()
        existing = session.execute(
            select(table).where(
                table.c.classroom_session_id == int(session_id),
                table.c.node_id == clean_node_id,
            )
        ).first()
        if existing is None:
            session.execute(
                table.insert().values(
                    school_id=resolved_school,
                    classroom_session_id=int(session_id),
                    lesson_id=resolved_lesson,
                    class_id=resolved_class,
                    node_id=clean_node_id,
                    reveal_level=clean_level,
                    revealed_by=actor_id,
                    revealed_at=now,
                    revoked_at=None,
                    revoke_reason=None,
                )
            )
        else:
            update_values: dict[str, Any] = {
                "reveal_level": clean_level,
                "revealed_by": actor_id,
                "revealed_at": now,
                "revoked_at": None,
                "revoke_reason": None,
            }
            if school_id is not None:
                update_values["school_id"] = int(school_id)
            if lesson_id is not None:
                update_values["lesson_id"] = int(lesson_id)
            if class_id is not None:
                update_values["class_id"] = int(class_id)
            session.execute(
                table.update()
                .where(
                    table.c.classroom_session_id == int(session_id),
                    table.c.node_id == clean_node_id,
                )
                .values(**update_values)
            )
        session.commit()
        row = session.execute(
            select(table).where(
                table.c.classroom_session_id == int(session_id),
                table.c.node_id == clean_node_id,
            )
        ).first()
        return _reveal_row_to_dict(row)

    if db is not None:
        return _run(db)
    with impl.SessionLocal() as session:
        return _run(session)


def retract_node(
    session_id: int,
    node_id: str,
    reason: str | None = None,
    *,
    db: Any = None,
    implementation: Any = None,
) -> dict[str, Any]:
    """撤回课堂中已开放的节点：写入 revoked_at 与 revoke_reason 留痕，不删除记录行。"""
    clean_node_id = str(node_id or "").strip()
    if not clean_node_id or len(clean_node_id) > 40:
        raise ValueError("节点 ID 不能为空且长度不能超过 40 个字符")
    clean_reason = str(reason)[:200] if reason is not None else None

    impl = _resolve_implementation(implementation)
    table = register_node_reveal_states_table(impl)

    def _run(session: Any) -> dict[str, Any]:
        existing = session.execute(
            select(table).where(
                table.c.classroom_session_id == int(session_id),
                table.c.node_id == clean_node_id,
            )
        ).first()
        if existing is None:
            raise LookupError("未找到该节点的开放记录，无法撤回")
        now = datetime.utcnow()
        session.execute(
            table.update()
            .where(
                table.c.classroom_session_id == int(session_id),
                table.c.node_id == clean_node_id,
            )
            .values(
                revoked_at=now,
                revoke_reason=clean_reason,
            )
        )
        session.commit()
        row = session.execute(
            select(table).where(
                table.c.classroom_session_id == int(session_id),
                table.c.node_id == clean_node_id,
            )
        ).first()
        return _reveal_row_to_dict(row)

    if db is not None:
        return _run(db)
    with impl.SessionLocal() as session:
        return _run(session)


def list_node_reveal(
    session_id: int,
    *,
    db: Any = None,
    implementation: Any = None,
) -> list[dict[str, Any]]:
    """列出指定课堂实例下的全部节点开放/撤回状态记录。"""
    impl = _resolve_implementation(implementation)
    table = register_node_reveal_states_table(impl)

    def _run(session: Any) -> list[dict[str, Any]]:
        rows = session.execute(
            select(table)
            .where(table.c.classroom_session_id == int(session_id))
            .order_by(table.c.id)
        ).all()
        return [_reveal_row_to_dict(r) for r in rows]

    if db is not None:
        return _run(db)
    with impl.SessionLocal() as session:
        return _run(session)


__all__ = [
    "REVEAL_LEVELS",
    "list_node_reveal",
    "register_node_reveal_states_table",
    "retract_node",
    "reveal_node",
]
