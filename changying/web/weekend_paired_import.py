"""Paired teacher+student import, binding review, errata logs and concurrency protection."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import Column, DateTime, Integer, String, Table, Text, delete, insert, select, update

from changying.services.weekend_paired_import import pair_teacher_and_student_docs


class BindingUpdateBody(BaseModel):
    status: Literal["pending", "confirmed", "ignored"] | None = None
    stageNo: int | None = Field(default=None, ge=1, le=7)
    targetKey: str | None = Field(default=None, max_length=80)
    text: str | None = Field(default=None, max_length=20000)
    expectedRevision: int = Field(ge=1)


def register_paired_import_tables(implementation: Any) -> dict[str, Table]:
    md = implementation.Base.metadata
    if "lesson_import_pairs" not in md.tables:
        Table(
            "lesson_import_pairs",
            md,
            Column("id", Integer, primary_key=True),
            Column("school_id", Integer, nullable=False, index=True),
            Column("lesson_id", Integer, nullable=False, index=True),
            Column("teacher_file_name", String(180), nullable=False),
            Column("teacher_sha256", String(64), nullable=False),
            Column("student_file_name", String(180), nullable=False),
            Column("student_sha256", String(64), nullable=False),
            Column("meta_json", Text, nullable=False),
            Column("revision", Integer, nullable=False, default=1),
            Column("created_by", Integer, nullable=False),
            Column("created_at", DateTime, nullable=False),
            Column("updated_at", DateTime, nullable=False),
        )
    if "lesson_content_bindings" not in md.tables:
        Table(
            "lesson_content_bindings",
            md,
            Column("id", Integer, primary_key=True),
            Column("school_id", Integer, nullable=False, index=True),
            Column("lesson_id", Integer, nullable=False, index=True),
            Column("pair_id", Integer, nullable=False, index=True),
            Column("item_key", String(80), nullable=False),
            Column("stage_no", Integer, nullable=False),
            Column("item_type", String(30), nullable=False),
            Column("target_key", String(80), nullable=False),
            Column("source_file", String(180), nullable=False),
            Column("source_part", String(180), nullable=False),
            Column("confidence", String(20), nullable=False),
            Column("status", String(20), nullable=False),
            Column("pending_reason", String(240), nullable=False),
            Column("payload_json", Text, nullable=False),
            Column("revision", Integer, nullable=False, default=1),
            Column("updated_by", Integer, nullable=False),
            Column("updated_at", DateTime, nullable=False),
        )
    if "lesson_errata_logs" not in md.tables:
        Table(
            "lesson_errata_logs",
            md,
            Column("id", Integer, primary_key=True),
            Column("school_id", Integer, nullable=False, index=True),
            Column("lesson_id", Integer, nullable=False, index=True),
            Column("binding_id", Integer, nullable=False, index=True),
            Column("field_name", String(60), nullable=False),
            Column("old_value", Text, nullable=False),
            Column("new_value", Text, nullable=False),
            Column("edited_by", Integer, nullable=False),
            Column("edited_at", DateTime, nullable=False),
        )
    return {
        "lesson_import_pairs": md.tables["lesson_import_pairs"],
        "lesson_content_bindings": md.tables["lesson_content_bindings"],
        "lesson_errata_logs": md.tables["lesson_errata_logs"],
    }


def _serialize_binding(row: Any) -> dict[str, Any]:
    return {
        "id": int(row.id),
        "pairId": int(row.pair_id),
        "itemKey": str(row.item_key),
        "stageNo": int(row.stage_no),
        "itemType": str(row.item_type),
        "targetKey": str(row.target_key or ""),
        "sourceFile": str(row.source_file),
        "sourcePart": str(row.source_part),
        "confidence": str(row.confidence),
        "status": str(row.status),
        "pendingReason": str(row.pending_reason or ""),
        "payload": json.loads(row.payload_json or "{}"),
        "revision": int(row.revision),
    }


def install_weekend_paired_import(implementation: Any) -> APIRouter:
    router = APIRouter()
    tables = register_paired_import_tables(implementation)
    pairs_t = tables["lesson_import_pairs"]
    bindings_t = tables["lesson_content_bindings"]
    errata_t = tables["lesson_errata_logs"]
    Lesson = implementation.TeachingLesson
    get_db, current_user, need = implementation.get_db, implementation.current_user, implementation.need

    def _my_lesson(db: Any, u: Any, lid: int) -> Any:
        need(u, "teacher")
        row = db.scalar(select(Lesson).where(Lesson.id == lid, Lesson.school_id == u.school_id))
        if row is None:
            raise HTTPException(404, "没有找到这节课的教案")
        return row

    @router.post("/teacher/weekend/lessons/{lid}/paired-import")
    async def upload_paired_docs(
        lid: int,
        teacherFile: UploadFile = File(...),
        studentFile: UploadFile = File(...),
        u: Any = Depends(current_user),
        db: Any = Depends(get_db),
    ) -> dict[str, Any]:
        lesson = _my_lesson(db, u, lid)
        t_bytes = await teacherFile.read()
        s_bytes = await studentFile.read()
        if not t_bytes or not s_bytes:
            raise HTTPException(400, "请同时上传教师版和学生版两份文件")
        try:
            parsed = pair_teacher_and_student_docs(
                t_bytes, teacherFile.filename or "teacher.docx",
                s_bytes, studentFile.filename or "student.docx",
            )
        except Exception as exc:
            raise HTTPException(422, f"配对解析失败，未保存任何变更：{exc}") from exc

        now = datetime.utcnow()
        # Replace previous pair bindings for this lesson atomically in one transaction.
        db.execute(delete(bindings_t).where(bindings_t.c.school_id == u.school_id, bindings_t.c.lesson_id == lesson.id))
        db.execute(delete(pairs_t).where(pairs_t.c.school_id == u.school_id, pairs_t.c.lesson_id == lesson.id))
        pair_id = int(
            db.execute(
                insert(pairs_t).values(
                    school_id=int(u.school_id),
                    lesson_id=int(lesson.id),
                    teacher_file_name=parsed["teacherFile"][:180],
                    teacher_sha256=parsed["teacherSha256"],
                    student_file_name=parsed["studentFile"][:180],
                    student_sha256=parsed["studentSha256"],
                    meta_json=json.dumps(
                        {
                            "teacherMediaCount": parsed["teacherMediaCount"],
                            "studentMediaCount": parsed["studentMediaCount"],
                        },
                        ensure_ascii=False,
                    ),
                    revision=1,
                    created_by=int(u.id),
                    created_at=now,
                    updated_at=now,
                )
            ).inserted_primary_key[0]
        )
        for item in parsed["bindings"]:
            db.execute(
                insert(bindings_t).values(
                    school_id=int(u.school_id),
                    lesson_id=int(lesson.id),
                    pair_id=pair_id,
                    item_key=item["itemKey"][:80],
                    stage_no=int(item["stageNo"]),
                    item_type=item["itemType"][:30],
                    target_key=str(item.get("targetKey") or "")[:80],
                    source_file=item["sourceFile"][:180],
                    source_part=item["sourcePart"][:180],
                    confidence=item["confidence"][:20],
                    status=item["status"][:20],
                    pending_reason=str(item.get("pendingReason") or "")[:240],
                    payload_json=json.dumps(item["payload"], ensure_ascii=False),
                    revision=1,
                    updated_by=int(u.id),
                    updated_at=now,
                )
            )
        implementation.audit(db, u, "weekend.paired_import", f"lesson={lesson.id}:pair={pair_id}:count={len(parsed['bindings'])}")
        db.commit()
        return get_paired_import(lid, u, db)

    @router.get("/teacher/weekend/lessons/{lid}/paired-import")
    def get_paired_import(lid: int, u: Any = Depends(current_user), db: Any = Depends(get_db)) -> dict[str, Any]:
        lesson = _my_lesson(db, u, lid)
        pair = db.execute(
            select(pairs_t).where(pairs_t.c.school_id == u.school_id, pairs_t.c.lesson_id == lesson.id).order_by(pairs_t.c.id.desc()).limit(1)
        ).first()
        if pair is None:
            return {"lessonId": int(lesson.id), "pair": None, "bindings": [], "errata": []}
        rows = db.execute(
            select(bindings_t).where(bindings_t.c.pair_id == pair.id).order_by(bindings_t.c.id)
        ).all()
        errata = db.execute(
            select(errata_t).where(errata_t.c.school_id == u.school_id, errata_t.c.lesson_id == lesson.id).order_by(errata_t.c.id.desc()).limit(100)
        ).all()
        return {
            "lessonId": int(lesson.id),
            "pair": {
                "id": int(pair.id),
                "teacherFile": str(pair.teacher_file_name),
                "teacherSha256": str(pair.teacher_sha256),
                "studentFile": str(pair.student_file_name),
                "studentSha256": str(pair.student_sha256),
                "revision": int(pair.revision),
                **json.loads(pair.meta_json or "{}"),
            },
            "bindings": [_serialize_binding(r) for r in rows],
            "errata": [
                {
                    "id": int(e.id),
                    "bindingId": int(e.binding_id),
                    "fieldName": str(e.field_name),
                    "oldValue": str(e.old_value),
                    "newValue": str(e.new_value),
                    "editedBy": int(e.edited_by),
                    "editedAt": e.edited_at.isoformat(),
                }
                for e in errata
            ],
        }

    @router.put("/teacher/weekend/lessons/{lid}/bindings/{bid}")
    def update_binding(
        lid: int,
        bid: int,
        b: BindingUpdateBody,
        u: Any = Depends(current_user),
        db: Any = Depends(get_db),
    ) -> dict[str, Any]:
        lesson = _my_lesson(db, u, lid)
        row = db.execute(
            select(bindings_t).where(
                bindings_t.c.id == bid,
                bindings_t.c.lesson_id == lesson.id,
                bindings_t.c.school_id == u.school_id,
            ).with_for_update()
        ).first()
        if row is None:
            raise HTTPException(404, "未找到对应的导入绑定项")
        if int(row.revision) != int(b.expectedRevision):
            raise HTTPException(409, "该条记录已被其他教师更新，请刷新后再保存（修订号冲突）")

        now = datetime.utcnow()
        payload = json.loads(row.payload_json or "{}")
        updates: dict[str, Any] = {"revision": int(row.revision) + 1, "updated_by": int(u.id), "updated_at": now}
        errata_rows: list[tuple[str, str, str]] = []

        if b.stageNo is not None and int(b.stageNo) != int(row.stage_no):
            errata_rows.append(("stageNo", str(row.stage_no), str(b.stageNo)))
            updates["stage_no"] = int(b.stageNo)
        if b.targetKey is not None and b.targetKey != str(row.target_key or ""):
            errata_rows.append(("targetKey", str(row.target_key or ""), b.targetKey))
            updates["target_key"] = b.targetKey
        if b.text is not None and b.text != str(payload.get("text") or ""):
            errata_rows.append(("text", str(payload.get("text") or ""), b.text))
            payload["text"] = b.text
            updates["payload_json"] = json.dumps(payload, ensure_ascii=False)
            # Modifying an already-confirmed item invalidates its confirmation until re-checked.
            if row.status == "confirmed" and b.status is None:
                updates["status"] = "pending"
                updates["pending_reason"] = "内容已勘误修改，需重新确认"
        if b.status is not None:
            if b.status == "confirmed" and row.item_type == "image" and not (updates.get("target_key", row.target_key)):
                raise HTTPException(400, "图片必须先绑定到具体文章或题目，才能确认")
            if b.status == "confirmed" and row.item_type in ("answer", "explanation", "hint") and not (updates.get("target_key", row.target_key)):
                raise HTTPException(400, "答案、提示或解析必须先绑定到具体题目，才能确认")
            if b.status != row.status:
                errata_rows.append(("status", str(row.status), b.status))
            updates["status"] = b.status
            if b.status == "confirmed":
                updates["pending_reason"] = ""

        db.execute(update(bindings_t).where(bindings_t.c.id == row.id).values(**updates))
        for field_name, old_val, new_val in errata_rows:
            db.execute(
                insert(errata_t).values(
                    school_id=int(u.school_id),
                    lesson_id=int(lesson.id),
                    binding_id=int(row.id),
                    field_name=field_name,
                    old_value=old_val,
                    new_value=new_val,
                    edited_by=int(u.id),
                    edited_at=now,
                )
            )
        implementation.audit(db, u, "weekend.binding.update", f"lesson={lesson.id}:binding={row.id}:rev={updates['revision']}")
        db.commit()
        updated = db.execute(select(bindings_t).where(bindings_t.c.id == row.id)).first()
        return {"binding": _serialize_binding(updated)}

    app = implementation.app
    app.include_router(router)
    return router


__all__ = ["install_weekend_paired_import", "register_paired_import_tables"]
