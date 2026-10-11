"""After-school homework assistant: routes.

Everything here sits behind the ``HOMEWORK_ASSISTANT`` environment flag (default off). With the flag
off every route below answers 404, exactly as if it did not exist. The flag is read per request, so
switching it on or off needs no code change.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy import insert, select, update

from changying.services.homework_assistant_tables import register_homework_assistant_tables
from changying.services.homework_prompts import (
    MAX_NOTICE_CHARS,
    build_parse_prompt,
    clean_items,
    clean_parse_result,
    scrub_notice_text,
)
from changying.services.homework_vision import MAX_IMAGE_BYTES, recognize_image, vision_enabled
from changying.web.homework_assistant_pages import homework_page_html

HOMEWORK_ASSISTANT_FLAG = "HOMEWORK_ASSISTANT"
TODAY_WINDOW_DAYS = 3
DRAFT_RAW_TEXT_DAYS = 7
NO_CACHE = {"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"}


def homework_enabled() -> bool:
    return os.getenv(HOMEWORK_ASSISTANT_FLAG, "").strip().lower() in {"1", "true", "yes", "on"}


def require_enabled() -> None:
    if not homework_enabled():
        raise HTTPException(404, "Not Found")


class ParseBody(BaseModel):
    text: str


class NoticeBody(BaseModel):
    groupLabel: str = ""
    items: list[dict[str, Any]] = []


class PublishBody(BaseModel):
    studentIDs: list[int]


class DoneBody(BaseModel):
    done: bool = True


def _mapping(row: Any) -> dict[str, Any]:
    if row is None:
        return {}
    return dict(row._mapping) if hasattr(row, "_mapping") else dict(row)


def _json_list(raw: Any) -> list[Any]:
    try:
        value = json.loads(raw or "[]")
    except Exception:
        return []
    return value if isinstance(value, list) else []


def _iso(value: Any) -> str:
    return value.strftime("%Y-%m-%d %H:%M") if hasattr(value, "strftime") else ""


def _ints(raw: Any) -> list[int]:
    return [int(x) for x in _json_list(raw) if isinstance(x, int) and not isinstance(x, bool)]


async def _read_image(file: UploadFile) -> bytes:
    data = await file.read(MAX_IMAGE_BYTES + 1)
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(413, "图片太大，请重新拍一张")
    return data


def install_homework_assistant(implementation: Any) -> APIRouter:
    app = implementation.app
    if getattr(app.state, "homework_assistant_installed", False):
        return app.state.homework_router

    tables = register_homework_assistant_tables(implementation)
    notices, recipients = tables["homework_notices"], tables["homework_recipients"]

    User = implementation.User
    SchoolClass = implementation.SchoolClass
    ClassStudent = implementation.ClassStudent
    current_user = implementation.current_user
    get_db = implementation.get_db
    need = implementation.need
    router = APIRouter(dependencies=[Depends(require_enabled)])
    # Follow-up routes (help requests) register on the same router through this handle.
    app.state.homework_tables = tables

    def teacher_students(db: Any, teacher: Any) -> list[dict[str, Any]]:
        rows = db.execute(
            select(User.id, User.name, User.grade, SchoolClass.id, SchoolClass.name)
            .join(ClassStudent, ClassStudent.student_id == User.id)
            .join(SchoolClass, SchoolClass.id == ClassStudent.class_id)
            .where(
                SchoolClass.teacher_id == teacher.id,
                SchoolClass.school_id == teacher.school_id,
                User.school_id == teacher.school_id,
                User.role == "student",
                User.active.is_(True),
            )
            .order_by(SchoolClass.id, User.id)
        ).all()
        seen: set[int] = set()
        out: list[dict[str, Any]] = []
        for sid, name, grade, cid, cname in rows:
            if sid in seen:
                continue
            seen.add(sid)
            out.append({"id": sid, "name": name, "grade": grade, "classID": cid, "className": cname})
        return out

    def own_notice(db: Any, teacher: Any, notice_id: int) -> dict[str, Any]:
        row = db.execute(
            select(notices).where(
                notices.c.id == notice_id,
                notices.c.school_id == teacher.school_id,
                notices.c.teacher_id == teacher.id,
            )
        ).first()
        if row is None:
            raise HTTPException(404, "清单不存在")
        return _mapping(row)

    def notice_json(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": row["id"],
            "groupLabel": row["group_label"],
            "status": row["status"],
            "sourceKind": row["source_kind"],
            "items": _json_list(row["items_json"]),
            "createdAt": _iso(row["created_at"]),
            "publishedAt": _iso(row["published_at"]),
        }

    def purge_old_draft_text(db: Any, teacher: Any) -> None:
        """Lazy retention: pasted notice text is not kept on drafts for more than a week."""
        cutoff = datetime.utcnow() - timedelta(days=DRAFT_RAW_TEXT_DAYS)
        db.execute(
            update(notices)
            .where(
                notices.c.school_id == teacher.school_id,
                notices.c.teacher_id == teacher.id,
                notices.c.created_at < cutoff,
                notices.c.raw_text != "",
            )
            .values(raw_text="")
        )
        db.commit()

    # ---------------------------------------------------------------- config / page
    @router.get("/homework/config")
    def homework_config():
        return {"enabled": True, "visionEnabled": vision_enabled()}

    @router.get("/v1/homework", include_in_schema=False)
    def homework_page():
        return HTMLResponse(homework_page_html(), headers=NO_CACHE)

    # ---------------------------------------------------------------- teacher
    @router.get("/teacher/homework/students")
    def students(u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "teacher")
        return teacher_students(db, u)

    @router.post("/teacher/homework/parse-image")
    async def parse_image(
        file: UploadFile = File(...),
        u: Any = Depends(current_user),
        db: Any = Depends(get_db),
    ):
        need(u, "teacher")
        data = await _read_image(file)
        implementation._ai_rate_check(db, u.school_id)
        result = recognize_image(implementation, db, u, data, feature="homework_parse_vision")
        return {"text": scrub_notice_text(result["text"]), "confidence": result["confidence"]}

    @router.post("/teacher/homework/parse")
    def parse(b: ParseBody, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "teacher")
        if len(b.text) > MAX_NOTICE_CHARS:
            raise HTTPException(400, f"通知太长，请控制在 {MAX_NOTICE_CHARS} 字以内")
        text = scrub_notice_text(b.text)
        if not text:
            raise HTTPException(400, "请先粘贴作业通知文字")
        raw = implementation._ai_call(db, u, "homework_parse", build_parse_prompt(text), timeout=60)
        try:
            parsed = clean_parse_result(implementation._ai_json(raw))
        except HTTPException:
            parsed = {"groupLabel": "", "items": []}
        if not parsed["items"]:
            raise HTTPException(422, "没有识别到作业条目，请手动录入")
        result = db.execute(
            insert(notices).values(
                school_id=u.school_id,
                teacher_id=u.id,
                group_label=parsed["groupLabel"],
                source_kind="text",
                raw_text=text,
                items_json=json.dumps(parsed["items"], ensure_ascii=False),
                status="draft",
                created_at=datetime.utcnow(),
            )
        )
        db.commit()
        return notice_json(own_notice(db, u, int(result.inserted_primary_key[0])))

    @router.post("/teacher/homework/notices")
    def create_notice(b: NoticeBody, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "teacher")
        items = clean_items(b.items)
        if not items:
            raise HTTPException(400, "至少需要一条作业")
        result = db.execute(
            insert(notices).values(
                school_id=u.school_id,
                teacher_id=u.id,
                group_label=(b.groupLabel or "").strip()[:120],
                source_kind="text",
                raw_text="",
                items_json=json.dumps(items, ensure_ascii=False),
                status="draft",
                created_at=datetime.utcnow(),
            )
        )
        db.commit()
        return notice_json(own_notice(db, u, int(result.inserted_primary_key[0])))

    @router.put("/teacher/homework/notices/{notice_id}")
    def update_notice(notice_id: int, b: NoticeBody, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "teacher")
        row = own_notice(db, u, notice_id)
        if row["status"] != "draft":
            raise HTTPException(409, "已发布的清单不能再修改条目")
        items = clean_items(b.items)
        if not items:
            raise HTTPException(400, "至少需要一条作业")
        db.execute(
            update(notices)
            .where(notices.c.id == notice_id)
            .values(group_label=(b.groupLabel or "").strip()[:120], items_json=json.dumps(items, ensure_ascii=False))
        )
        db.commit()
        return notice_json(own_notice(db, u, notice_id))

    @router.post("/teacher/homework/notices/{notice_id}/publish")
    def publish_notice(notice_id: int, b: PublishBody, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "teacher")
        row = own_notice(db, u, notice_id)
        if not _json_list(row["items_json"]):
            raise HTTPException(400, "清单里没有作业条目")
        wanted = list(dict.fromkeys(int(x) for x in b.studentIDs))
        if not wanted:
            raise HTTPException(400, "请至少选择一名学生")
        allowed = {item["id"] for item in teacher_students(db, u)}
        if not set(wanted) <= allowed:
            raise HTTPException(403, "只能分配给自己班级的学生")
        have = {
            int(x)
            for x in db.scalars(select(recipients.c.student_id).where(recipients.c.notice_id == notice_id)).all()
        }
        now = datetime.utcnow()
        for student_id in wanted:
            if student_id not in have:
                db.execute(
                    insert(recipients).values(
                        school_id=u.school_id, notice_id=notice_id, student_id=student_id, done_json="[]", created_at=now
                    )
                )
        values: dict[str, Any] = {"status": "published", "raw_text": ""}
        if row["published_at"] is None:
            values["published_at"] = now
        db.execute(update(notices).where(notices.c.id == notice_id).values(**values))
        implementation.audit(db, u, "homework.notice.publish", f"notice={notice_id} students={len(wanted)}")
        db.commit()
        return {"id": notice_id, "status": "published", "recipients": len(have | set(wanted))}

    @router.get("/teacher/homework/notices")
    def list_notices(u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "teacher")
        purge_old_draft_text(db, u)
        rows = db.execute(
            select(notices)
            .where(notices.c.school_id == u.school_id, notices.c.teacher_id == u.id)
            .order_by(notices.c.id.desc())
            .limit(30)
        ).all()
        out = []
        for raw in rows:
            row = _mapping(raw)
            people = db.execute(select(recipients.c.done_json).where(recipients.c.notice_id == row["id"])).all()
            item_count = len(_json_list(row["items_json"]))
            data = notice_json(row)
            data.pop("items")
            data.update(
                {
                    "itemCount": item_count,
                    "recipientCount": len(people),
                    "doneCount": sum(len(_ints(p[0])) for p in people),
                    "totalCount": item_count * len(people),
                }
            )
            out.append(data)
        return out

    @router.get("/teacher/homework/notices/{notice_id}")
    def notice_detail(notice_id: int, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "teacher")
        row = own_notice(db, u, notice_id)
        data = notice_json(row)
        people = db.execute(
            select(recipients.c.student_id, recipients.c.done_json, User.name)
            .join(User, User.id == recipients.c.student_id)
            .where(recipients.c.notice_id == notice_id, recipients.c.school_id == u.school_id)
            .order_by(recipients.c.student_id)
        ).all()
        data["recipients"] = [{"studentID": sid, "name": name, "done": _ints(done)} for sid, done, name in people]
        return data

    # ---------------------------------------------------------------- student
    @router.get("/student/homework/today")
    def student_today(u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "student")
        since = datetime.utcnow() - timedelta(days=TODAY_WINDOW_DAYS)
        rows = db.execute(
            select(notices, recipients.c.done_json)
            .join(recipients, recipients.c.notice_id == notices.c.id)
            .where(
                recipients.c.student_id == u.id,
                recipients.c.school_id == u.school_id,
                notices.c.status == "published",
                notices.c.published_at >= since,
            )
            .order_by(notices.c.published_at.desc(), notices.c.id.desc())
        ).all()
        out = []
        for raw in rows:
            row = _mapping(raw)
            done = set(_ints(row["done_json"]))
            items = [dict(item, done=int(item.get("seq", 0)) in done) for item in _json_list(row["items_json"])]
            out.append(
                {
                    "noticeID": row["id"],
                    "groupLabel": row["group_label"],
                    "publishedAt": _iso(row["published_at"]),
                    "items": items,
                }
            )
        return out

    @router.post("/student/homework/items/{notice_id}/{seq}/done")
    def student_mark_done(
        notice_id: int, seq: int, b: DoneBody, u: Any = Depends(current_user), db: Any = Depends(get_db)
    ):
        need(u, "student")
        row = db.execute(
            select(recipients.c.id, recipients.c.done_json, notices.c.items_json)
            .join(notices, notices.c.id == recipients.c.notice_id)
            .where(
                recipients.c.notice_id == notice_id,
                recipients.c.student_id == u.id,
                recipients.c.school_id == u.school_id,
                notices.c.status == "published",
            )
        ).first()
        if row is None:
            raise HTTPException(404, "没有这份作业")
        valid = {int(item.get("seq", 0)) for item in _json_list(row.items_json)}
        if seq not in valid:
            raise HTTPException(404, "没有这条作业")
        done = set(_ints(row.done_json))
        if b.done:
            done.add(seq)
        else:
            done.discard(seq)
        db.execute(update(recipients).where(recipients.c.id == row.id).values(done_json=json.dumps(sorted(done))))
        db.commit()
        return {"noticeID": notice_id, "seq": seq, "done": bool(b.done)}

    app.include_router(router)
    app.state.homework_assistant_installed = True
    app.state.homework_router = router
    return router


__all__ = ["HOMEWORK_ASSISTANT_FLAG", "homework_enabled", "install_homework_assistant", "require_enabled"]
