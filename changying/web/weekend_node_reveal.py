"""课堂节点逐级开放与撤回 Web 接口（块四）。

POST /v1/classroom/{session_id}/nodes/{node_id}/reveal  body {level}
POST /v1/classroom/{session_id}/nodes/{node_id}/retract body {reason?}
GET  /v1/classroom/{session_id}/node-reveals
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from changying.services.node_approvals import (
    CONTENT_CHANGE_REVOKE_REASON,
    DEFAULT_REVOKE_REASON,
    approve_node,
    get_node_approval,
    invalidate_approvals_on_content_change,
    register_node_approvals_table,
    revoke_node,
)
from changying.services.node_identity import (
    VALID_NODE_KINDS,
    VALID_QUESTION_TYPES,
    compute_content_hash,
    normalize_node_text,
    register_lesson_nodes_table,
    stable_node_id,
    upsert_lesson_node,
    validate_node_kind_and_question_type,
)
from changying.services.node_reveal import (
    REVEAL_LEVELS,
    list_node_reveal,
    register_node_reveal_states_table,
    retract_node,
    reveal_node,
)
from changying.utils.datetime_tools import school_local_iso
from changying.web.v1_classroom_execution import register_classroom_execution_tables


class NodeRevealRequestBody(BaseModel):
    level: str | None = None


class NodeRetractRequestBody(BaseModel):
    reason: str | None = None


def register_block4_node_tables(implementation: Any) -> dict[str, Any]:
    """统一注册块四的三张加法表：lesson_nodes、node_approvals、node_reveal_states。"""
    register_classroom_execution_tables(implementation)
    return {
        "lesson_nodes": register_lesson_nodes_table(implementation),
        "node_approvals": register_node_approvals_table(implementation),
        "node_reveal_states": register_node_reveal_states_table(implementation),
    }


def _mapping(row: Any) -> dict[str, Any]:
    if row is None:
        return {}
    return dict(row._mapping) if hasattr(row, "_mapping") else dict(row)


def _serialize_reveal_item(item: dict[str, Any]) -> dict[str, Any]:
    revealed_at = item.get("revealed_at")
    revoked_at = item.get("revoked_at")
    return {
        "id": int(item["id"]),
        "school_id": int(item["school_id"]),
        "classroom_session_id": int(item["classroom_session_id"]),
        "lesson_id": item.get("lesson_id"),
        "class_id": item.get("class_id"),
        "node_id": str(item["node_id"]),
        "reveal_level": str(item["reveal_level"]),
        "level": str(item["reveal_level"]),
        "revealed_by": int(item["revealed_by"]),
        "revealed_at": school_local_iso(revealed_at) if revealed_at else None,
        "revoked_at": school_local_iso(revoked_at) if revoked_at else None,
        "revoke_reason": item.get("revoke_reason"),
        "is_active": item.get("revoked_at") is None,
    }


def _find_scoped_classroom_session(db: Any, implementation: Any, user: Any, session_id: int) -> dict[str, Any]:
    implementation.need(user, "teacher", "admin")
    md = implementation.Base.metadata
    classroom_sessions = md.tables.get("classroom_sessions")
    if classroom_sessions is not None:
        row = db.execute(
            select(classroom_sessions).where(
                classroom_sessions.c.id == int(session_id),
                classroom_sessions.c.school_id == int(user.school_id),
            )
        ).first()
        if row is not None:
            data = _mapping(row)
            if getattr(user, "role", "") == "teacher" and int(data.get("teacher_id") or 0) not in (0, int(user.id)):
                raise HTTPException(404, "课堂实例不存在或无权限")
            return {
                "id": int(data["id"]),
                "school_id": int(data["school_id"]),
                "lesson_id": int(data["lesson_id"]) if data.get("lesson_id") is not None else 0,
                "class_id": int(data["class_id"]) if data.get("class_id") is not None else None,
                "teacher_id": int(data.get("teacher_id") or user.id),
            }

    weekend_sessions = md.tables.get("weekend_sessions")
    if weekend_sessions is not None:
        row = db.execute(
            select(weekend_sessions).where(
                weekend_sessions.c.id == int(session_id),
                weekend_sessions.c.school_id == int(user.school_id),
            )
        ).first()
        if row is not None:
            data = _mapping(row)
            if getattr(user, "role", "") == "teacher" and int(data.get("teacher_id") or 0) not in (0, int(user.id)):
                raise HTTPException(404, "课堂实例不存在或无权限")
            return {
                "id": int(data["id"]),
                "school_id": int(data["school_id"]),
                "lesson_id": int(data["lesson_id"]) if data.get("lesson_id") is not None else 0,
                "class_id": None,
                "teacher_id": int(data.get("teacher_id") or user.id),
            }

    raise HTTPException(404, "课堂实例不存在或无权限")


def install_weekend_node_reveal(implementation: Any) -> APIRouter:
    """注册块四节点逐级开放/撤回表与路由。"""
    app = implementation.app
    if getattr(app.state, "weekend_node_reveal_installed", False):
        return app.state.weekend_node_reveal_router

    register_block4_node_tables(implementation)
    current_user = implementation.current_user
    get_db = implementation.get_db
    router = APIRouter()

    @router.post("/v1/classroom/{session_id}/nodes/{node_id}/reveal")
    def reveal_classroom_node(
        session_id: int,
        node_id: str,
        body: NodeRevealRequestBody = Body(default_factory=NodeRevealRequestBody),
        u: Any = Depends(current_user),
        db: Any = Depends(get_db),
    ) -> dict[str, Any]:
        sess = _find_scoped_classroom_session(db, implementation, u, session_id)
        raw_level = (body.level or "").strip() if body is not None else ""
        if raw_level not in REVEAL_LEVELS:
            raise HTTPException(400, f"开放层级不合法，必须为 {', '.join(REVEAL_LEVELS)} 之一")
        try:
            state = reveal_node(
                session_id,
                node_id,
                raw_level,
                revealed_by=int(u.id),
                school_id=int(sess["school_id"]),
                lesson_id=sess["lesson_id"],
                class_id=sess["class_id"],
                db=db,
                implementation=implementation,
            )
        except ValueError as exc:
            raise HTTPException(400, str(exc))
        return _serialize_reveal_item(state)

    @router.post("/v1/classroom/{session_id}/nodes/{node_id}/retract")
    def retract_classroom_node(
        session_id: int,
        node_id: str,
        body: NodeRetractRequestBody | None = Body(default=None),
        u: Any = Depends(current_user),
        db: Any = Depends(get_db),
    ) -> dict[str, Any]:
        _find_scoped_classroom_session(db, implementation, u, session_id)
        reason = body.reason if body is not None else None
        try:
            state = retract_node(
                session_id,
                node_id,
                reason,
                db=db,
                implementation=implementation,
            )
        except LookupError as exc:
            raise HTTPException(404, str(exc))
        except ValueError as exc:
            raise HTTPException(400, str(exc))
        return _serialize_reveal_item(state)

    @router.get("/v1/classroom/{session_id}/node-reveals")
    def get_classroom_node_reveals(
        session_id: int,
        u: Any = Depends(current_user),
        db: Any = Depends(get_db),
    ) -> dict[str, Any]:
        _find_scoped_classroom_session(db, implementation, u, session_id)
        items = list_node_reveal(session_id, db=db, implementation=implementation)
        return {
            "classroom_session_id": int(session_id),
            "items": [_serialize_reveal_item(item) for item in items],
        }

    app.include_router(router)
    app.state.weekend_node_reveal_installed = True
    app.state.weekend_node_reveal_router = router
    return router


__all__ = [
    "CONTENT_CHANGE_REVOKE_REASON",
    "DEFAULT_REVOKE_REASON",
    "NodeRetractRequestBody",
    "NodeRevealRequestBody",
    "REVEAL_LEVELS",
    "VALID_NODE_KINDS",
    "VALID_QUESTION_TYPES",
    "approve_node",
    "compute_content_hash",
    "get_node_approval",
    "install_weekend_node_reveal",
    "invalidate_approvals_on_content_change",
    "list_node_reveal",
    "normalize_node_text",
    "register_block4_node_tables",
    "register_lesson_nodes_table",
    "register_node_approvals_table",
    "register_node_reveal_states_table",
    "retract_node",
    "reveal_node",
    "revoke_node",
    "stable_node_id",
    "upsert_lesson_node",
    "validate_node_kind_and_question_type",
]
