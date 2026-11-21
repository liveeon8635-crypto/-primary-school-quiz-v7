"""节点审核状态服务层（块四：node_approvals 审核、撤回与内容变更批量失效）。"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
import importlib
from typing import Any

from sqlalchemy import Column, DateTime, Integer, String, Table, UniqueConstraint, select

from changying.services.node_identity import compute_content_hash, register_lesson_nodes_table


DEFAULT_REVOKE_REASON = "教师撤回审核"
CONTENT_CHANGE_REVOKE_REASON = "内容变更自动失效"

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


def register_node_approvals_table(implementation: Any = None) -> Table:
    """在 implementation.Base.metadata 中注册 node_approvals 表。"""
    impl = _resolve_implementation(implementation)
    md = impl.Base.metadata
    table = md.tables.get("node_approvals")
    if table is None:
        table = Table(
            "node_approvals",
            md,
            Column("id", Integer, primary_key=True),
            Column("school_id", Integer, nullable=False, index=True, default=0),
            Column("lesson_id", Integer, nullable=False, index=True),
            Column("node_id", String(40), nullable=False, index=True),
            Column("approved_content_hash", String(64), nullable=False, default=""),
            Column("approved_by", Integer, nullable=False, default=0),
            Column("approved_at", DateTime, nullable=False, default=datetime.utcnow),
            Column("revoked_at", DateTime, nullable=True),
            Column("revoke_reason", String(200), nullable=True),
            UniqueConstraint("lesson_id", "node_id", name="uq_node_approvals_lesson_node"),
        )
    return table


def _approval_row_to_dict(row: Any) -> dict[str, Any]:
    data = dict(row._mapping) if hasattr(row, "_mapping") else dict(row)
    return {
        "id": int(data["id"]),
        "school_id": int(data["school_id"]),
        "lesson_id": int(data["lesson_id"]),
        "node_id": str(data["node_id"]),
        "approved_content_hash": str(data["approved_content_hash"]),
        "approved_by": int(data["approved_by"]),
        "approved_at": data["approved_at"],
        "revoked_at": data["revoked_at"],
        "revoke_reason": data["revoke_reason"],
        "is_active": data["revoked_at"] is None,
    }


def _resolve_school_and_hash(
    session: Any,
    impl: Any,
    lesson_id: int,
    node_id: str,
    school_id: int | None,
    approved_content_hash: str | None,
    content_text: str | None,
) -> tuple[int, str]:
    nodes_table = register_lesson_nodes_table(impl)
    node_row = session.execute(
        select(nodes_table).where(
            nodes_table.c.lesson_id == int(lesson_id),
            nodes_table.c.node_id == str(node_id),
        )
    ).first()
    node_data = (dict(node_row._mapping) if hasattr(node_row, "_mapping") else dict(node_row)) if node_row else {}

    resolved_school_id = school_id
    if resolved_school_id is None and node_data.get("school_id") is not None:
        resolved_school_id = int(node_data["school_id"])
    if resolved_school_id is None:
        Lesson = getattr(impl, "TeachingLesson", None)
        if Lesson is not None:
            lesson_obj = session.get(Lesson, int(lesson_id))
            if lesson_obj is not None and getattr(lesson_obj, "school_id", None) is not None:
                resolved_school_id = int(lesson_obj.school_id)
    if resolved_school_id is None:
        resolved_school_id = 1

    resolved_hash = approved_content_hash
    if not resolved_hash and content_text is not None:
        resolved_hash = compute_content_hash(content_text)
    if not resolved_hash and node_data.get("content_hash"):
        resolved_hash = str(node_data["content_hash"])
    if not resolved_hash:
        resolved_hash = compute_content_hash(node_id)

    return int(resolved_school_id), str(resolved_hash)[:64]


def approve_node(
    lesson_id: int,
    node_id: str,
    approved_content_hash: str | None = None,
    *,
    approved_by: int = 0,
    school_id: int | None = None,
    content_text: str | None = None,
    db: Any = None,
    implementation: Any = None,
) -> dict[str, Any]:
    """审核通过指定节点；若曾被撤回则清除 revoked_at/revoke_reason 并更新审核指纹与时间。"""
    impl = _resolve_implementation(implementation)
    table = register_node_approvals_table(impl)
    clean_node_id = str(node_id or "").strip()
    if not clean_node_id or len(clean_node_id) > 40:
        raise ValueError("节点 ID 不能为空且长度不能超过 40 个字符")

    def _run(session: Any) -> dict[str, Any]:
        resolved_school_id, resolved_hash = _resolve_school_and_hash(
            session,
            impl,
            int(lesson_id),
            clean_node_id,
            school_id,
            approved_content_hash,
            content_text,
        )
        now = datetime.utcnow()
        existing = session.execute(
            select(table).where(
                table.c.lesson_id == int(lesson_id),
                table.c.node_id == clean_node_id,
            )
        ).first()
        if existing is None:
            session.execute(
                table.insert().values(
                    school_id=resolved_school_id,
                    lesson_id=int(lesson_id),
                    node_id=clean_node_id,
                    approved_content_hash=resolved_hash,
                    approved_by=int(approved_by),
                    approved_at=now,
                    revoked_at=None,
                    revoke_reason=None,
                )
            )
        else:
            session.execute(
                table.update()
                .where(
                    table.c.lesson_id == int(lesson_id),
                    table.c.node_id == clean_node_id,
                )
                .values(
                    school_id=resolved_school_id,
                    approved_content_hash=resolved_hash,
                    approved_by=int(approved_by),
                    approved_at=now,
                    revoked_at=None,
                    revoke_reason=None,
                )
            )
        session.commit()
        row = session.execute(
            select(table).where(
                table.c.lesson_id == int(lesson_id),
                table.c.node_id == clean_node_id,
            )
        ).first()
        return _approval_row_to_dict(row)

    if db is not None:
        return _run(db)
    with impl.SessionLocal() as session:
        return _run(session)


def revoke_node(
    lesson_id: int,
    node_id: str,
    reason: str | None = DEFAULT_REVOKE_REASON,
    *,
    db: Any = None,
    implementation: Any = None,
) -> dict[str, Any]:
    """撤回节点审核：只写 revoked_at 与 revoke_reason 留痕，不删除记录行。"""
    impl = _resolve_implementation(implementation)
    table = register_node_approvals_table(impl)
    clean_node_id = str(node_id or "").strip()
    if not clean_node_id:
        raise ValueError("节点 ID 不能为空")
    clean_reason = str(reason if reason is not None else DEFAULT_REVOKE_REASON)[:200]

    def _run(session: Any) -> dict[str, Any]:
        existing = session.execute(
            select(table).where(
                table.c.lesson_id == int(lesson_id),
                table.c.node_id == clean_node_id,
            )
        ).first()
        if existing is None:
            raise LookupError("未找到该节点的审核记录")
        now = datetime.utcnow()
        session.execute(
            table.update()
            .where(
                table.c.lesson_id == int(lesson_id),
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
                table.c.lesson_id == int(lesson_id),
                table.c.node_id == clean_node_id,
            )
        ).first()
        return _approval_row_to_dict(row)

    if db is not None:
        return _run(db)
    with impl.SessionLocal() as session:
        return _run(session)


def invalidate_approvals_on_content_change(
    lesson_id: int,
    node_ids: Iterable[str],
    *,
    reason: str = CONTENT_CHANGE_REVOKE_REASON,
    db: Any = None,
    implementation: Any = None,
) -> list[dict[str, Any]]:
    """当节点内容发生变更时，批量把对应 node_approvals 置为 revoked_at / revoke_reason（留痕不删行）。"""
    impl = _resolve_implementation(implementation)
    table = register_node_approvals_table(impl)
    target_ids = [str(nid).strip() for nid in (node_ids or []) if str(nid).strip()]
    if not target_ids:
        return []
    clean_reason = str(reason or CONTENT_CHANGE_REVOKE_REASON)[:200]

    def _run(session: Any) -> list[dict[str, Any]]:
        now = datetime.utcnow()
        session.execute(
            table.update()
            .where(
                table.c.lesson_id == int(lesson_id),
                table.c.node_id.in_(target_ids),
            )
            .values(
                revoked_at=now,
                revoke_reason=clean_reason,
            )
        )
        session.commit()
        rows = session.execute(
            select(table)
            .where(
                table.c.lesson_id == int(lesson_id),
                table.c.node_id.in_(target_ids),
            )
            .order_by(table.c.id)
        ).all()
        return [_approval_row_to_dict(r) for r in rows]

    if db is not None:
        return _run(db)
    with impl.SessionLocal() as session:
        return _run(session)


def get_node_approval(
    lesson_id: int,
    node_id: str,
    *,
    db: Any = None,
    implementation: Any = None,
) -> dict[str, Any] | None:
    """查询单个节点的审核状态记录。"""
    impl = _resolve_implementation(implementation)
    table = register_node_approvals_table(impl)
    clean_node_id = str(node_id or "").strip()

    def _run(session: Any) -> dict[str, Any] | None:
        row = session.execute(
            select(table).where(
                table.c.lesson_id == int(lesson_id),
                table.c.node_id == clean_node_id,
            )
        ).first()
        return _approval_row_to_dict(row) if row is not None else None

    if db is not None:
        return _run(db)
    with impl.SessionLocal() as session:
        return _run(session)


__all__ = [
    "CONTENT_CHANGE_REVOKE_REASON",
    "DEFAULT_REVOKE_REASON",
    "approve_node",
    "get_node_approval",
    "invalidate_approvals_on_content_change",
    "register_node_approvals_table",
    "revoke_node",
]
