"""语数英知识地图与应试专项统一错题本服务（错题自动入本、重做答对自动消错、一键跳地图修补）.

独立维护 ``arena_wrong_items`` 表，零侵入教师人工批改作业错题表 ``wrong_question_records``，
并在学生「我的错题」页统一融合展示。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import Column, DateTime, Integer, String, Table, Text, UniqueConstraint, desc, insert, select, update

from changying.services import arena_review_and_custom as arc

SUBJECT_MAP_URL = {
    "数学": "/v1/math-star-map",
    "英语": "/v1/english-star-map",
    "语文": "/v1/chinese-star-map",
}


def register_arena_wrongbook_table(implementation: Any) -> Table:
    md = implementation.Base.metadata
    if "arena_wrong_items" not in md.tables:
        Table(
            "arena_wrong_items",
            md,
            Column("id", Integer, primary_key=True),
            Column("school_id", Integer, nullable=False, index=True),
            Column("student_id", Integer, nullable=False, index=True),
            Column("subject", String(16), nullable=False, index=True),
            Column("source_kind", String(16), nullable=False),  # map | sprint
            Column("node_key", String(24), nullable=False),
            Column("node_name", String(120), nullable=False),
            Column("question_id", String(120), nullable=False),
            Column("question_type", String(32), nullable=False),
            Column("type_label", String(32), nullable=False),
            Column("text", Text, nullable=False),
            Column("answer", Text, nullable=False),
            Column("explanation", Text, nullable=False),
            Column("wrong_count", Integer, nullable=False, default=1),
            Column("status", String(16), nullable=False, default="active"),  # active | mastered
            Column("last_wrong_at", DateTime, nullable=False),
            Column("updated_at", DateTime, nullable=False),
            UniqueConstraint("school_id", "student_id", "subject", "question_id", name="uq_arena_wrong_student_q"),
        )
    return md.tables["arena_wrong_items"]


def record_arena_outcomes(
    implementation: Any,
    db: Any,
    *,
    school_id: int,
    student_id: int,
    subject: str,
    source_kind: str,
    details: list[dict[str, Any]],
    default_node_key: str = "",
    default_node_name: str = "",
) -> dict[str, int]:
    """根据本次交卷明细自动记录错题（入本/累加）与攻克错题（自动标为 mastered）."""
    tbl = register_arena_wrongbook_table(implementation)
    arc.ensure_tables_on_session(db, tbl)
    now = datetime.utcnow()
    added = 0
    resolved = 0

    for d in details:
        qid = str(d.get("id") or "").strip()
        if not qid:
            continue
        ok = bool(d.get("correct"))
        nk = str(d.get("nodeKey") or default_node_key or "").strip()
        nn = str(d.get("nodeName") or default_node_name or nk).strip()
        existing = db.execute(
            select(tbl).where(
                tbl.c.school_id == int(school_id),
                tbl.c.student_id == int(student_id),
                tbl.c.subject == subject,
                tbl.c.question_id == qid,
            )
        ).first()

        if ok:
            if existing is not None and existing.status == "active":
                db.execute(
                    update(tbl)
                    .where(tbl.c.id == existing.id)
                    .values(status="mastered", updated_at=now)
                )
                resolved += 1
        else:
            if existing is None:
                db.execute(
                    insert(tbl).values(
                        school_id=int(school_id),
                        student_id=int(student_id),
                        subject=subject,
                        source_kind=source_kind,
                        node_key=nk[:24],
                        node_name=nn[:120],
                        question_id=qid[:120],
                        question_type=str(d.get("questionType") or "")[:32],
                        type_label=str(d.get("typeLabel") or "")[:32],
                        text=str(d.get("text") or ""),
                        answer=str(d.get("answer") or ""),
                        explanation=str(d.get("explanation") or ""),
                        wrong_count=1,
                        status="active",
                        last_wrong_at=now,
                        updated_at=now,
                    )
                )
                added += 1
            else:
                db.execute(
                    update(tbl)
                    .where(tbl.c.id == existing.id)
                    .values(
                        source_kind=source_kind,
                        wrong_count=int(existing.wrong_count or 0) + 1,
                        status="active",
                        last_wrong_at=now,
                        updated_at=now,
                    )
                )
                added += 1

    return {"added": added, "resolved": resolved}


def install_arena_wrongbook_views(implementation: Any) -> APIRouter:
    app = implementation.app
    if getattr(app.state, "arena_wrongbook_installed", False):
        return app.state.arena_wrongbook_router
    tbl = register_arena_wrongbook_table(implementation)
    current_user, get_db, need = implementation.current_user, implementation.get_db, implementation.need
    router = APIRouter()

    @router.get("/student/arena-wrongbook")
    def list_student_arena_wrongbook(
        subject: str = "",
        status: str = "active",
        u: Any = Depends(current_user),
        db: Any = Depends(get_db),
    ):
        need(u, "student")
        arc.ensure_tables_on_session(db, tbl)
        q = select(tbl).where(
            tbl.c.school_id == u.school_id,
            tbl.c.student_id == u.id,
        )
        if status in ("active", "mastered"):
            q = q.where(tbl.c.status == status)
        all_rows = db.execute(q.order_by(desc(tbl.c.last_wrong_at), desc(tbl.c.id))).all()

        counts = {"数学": 0, "英语": 0, "语文": 0}
        items: list[dict[str, Any]] = []
        for r in all_rows:
            if r.subject in counts:
                counts[r.subject] += 1
            if subject and r.subject != subject:
                continue
            base_url = SUBJECT_MAP_URL.get(r.subject, "/v1/math-star-map")
            items.append({
                "id": int(r.id),
                "subject": r.subject,
                "sourceKind": r.source_kind,
                "sourceLabel": "应试专项" if r.source_kind == "sprint" else "知识地图",
                "nodeKey": r.node_key,
                "nodeName": r.node_name,
                "questionId": r.question_id,
                "questionType": r.question_type,
                "typeLabel": r.type_label,
                "text": r.text,
                "answer": r.answer,
                "explanation": r.explanation,
                "wrongCount": int(r.wrong_count),
                "status": r.status,
                "repairUrl": f"{base_url}#node={r.node_key}" if r.node_key else base_url,
            })

        return {
            "total": len(all_rows),
            "counts": counts,
            "items": items[:100],
        }

    @router.post("/student/arena-wrongbook/{item_id}/master")
    def mark_arena_wrong_mastered(
        item_id: int,
        u: Any = Depends(current_user),
        db: Any = Depends(get_db),
    ):
        need(u, "student")
        arc.ensure_tables_on_session(db, tbl)
        row = db.execute(
            select(tbl).where(
                tbl.c.id == item_id,
                tbl.c.school_id == u.school_id,
                tbl.c.student_id == u.id,
            )
        ).first()
        if row is None:
            raise HTTPException(404, "未找到该错题记录")
        db.execute(
            update(tbl)
            .where(tbl.c.id == row.id)
            .values(status="mastered", updated_at=datetime.utcnow())
        )
        db.commit()
        return {"id": int(row.id), "status": "mastered"}

    app.include_router(router)
    app.state.arena_wrongbook_installed = True
    app.state.arena_wrongbook_router = router
    return router


__all__ = [
    "install_arena_wrongbook_views",
    "record_arena_outcomes",
    "register_arena_wrongbook_table",
]
