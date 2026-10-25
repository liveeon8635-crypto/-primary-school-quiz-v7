"""周末课 课前互动课件：每一页讲解／例题可配一个经审核的互动课件.

teacher  GET  /teacher/weekend/lessons/{lid}/courseware            pages of the lesson and their courseware (draft/approved)
         POST /teacher/weekend/lessons/{lid}/courseware/generate   {stageNo, page} AI picks a reviewed template for this page (draft)
         PUT  /teacher/weekend/lessons/{lid}/courseware            {stageNo, page, kind, params, writtenTask} teacher edits (draft)
         POST /teacher/weekend/lessons/{lid}/courseware/approve    {stageNo, page} classrooms show it on that page
         POST /teacher/weekend/lessons/{lid}/courseware/remove     {stageNo, page} remove a page's courseware
         POST /teacher/weekend/sessions/{sid}/courseware/view      {view} live screen state while teaching (no AI)

A lesson keeps one row; its items are keyed by (stage, page), so every slide or worked example can have its own
courseware without a schema change. Rows written by the first pilot (one courseware, kind column) are read as one
item. The approved parameters reach the big screen with the existing session state (weekend_views.state) only
when the screen is on that page. When the teacher ticks it, an approved item also gives pupils a written task
through the existing written questions (text/photo, teacher review, question-by-question release).
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import Column, DateTime, Integer, String, Table, Text, delete, insert, select, update

from changying.services import weekend_courseware as cw
from changying.services.weekend_stages import STAGE_COUNT

AI_FEATURE = "weekend_courseware"


class PageBody(BaseModel):
    stageNo: int = Field(default=3, ge=1, le=STAGE_COUNT)
    page: int | None = Field(default=None, ge=0)


class SaveBody(PageBody):
    kind: str = Field(max_length=20)
    params: dict[str, Any]
    writtenTask: bool = False


class ViewBody(BaseModel):
    view: dict[str, Any]


def register_courseware_table(implementation: Any) -> Table:
    md = implementation.Base.metadata
    if "weekend_courseware" not in md.tables:
        Table("weekend_courseware", md,
              Column("id", Integer, primary_key=True),
              Column("school_id", Integer, nullable=False, index=True),
              Column("lesson_id", Integer, nullable=False, unique=True),
              Column("teacher_id", Integer, nullable=False),
              Column("kind", String(20), nullable=False),
              Column("stage_no", Integer, nullable=False),
              Column("status", String(12), nullable=False),            # draft | approved (any item approved)
              Column("params_json", Text, nullable=False),             # {"version": 2, "items": [...]}; pilot rows: one params
              Column("approved_json", Text, nullable=True),            # non-null when some item is approved
              Column("approved_stage", Integer, nullable=True),
              Column("template_id", Integer, nullable=True),
              Column("live_json", Text, nullable=False),               # {"session:stage:page": screen state}
              Column("updated_at", DateTime, nullable=False))
    return md.tables["weekend_courseware"]


def stage_pages(lesson: Any, stage_no: int) -> list[str]:
    """The pages the big screen pages through in this stage (slides or worked examples); empty when it has none."""
    from changying.services.weekend_presentation import lesson_deck
    return lesson_deck({"ppt_json": lesson.ppt_json, "examples_json": lesson.examples_json, "reading_plan": lesson.reading_plan}, stage_no)


def _short(text: str, limit: int = 40) -> str:
    line = " ".join(str(text or "").split())
    return line if len(line) <= limit else line[:limit] + "…"


def items_of(row: Any) -> list[dict[str, Any]]:
    """Every page item of a lesson's courseware row; a pilot row (single courseware) becomes one or two items."""
    if row is None:
        return []
    data = json.loads(row.params_json or "{}")
    if isinstance(data, dict) and data.get("version") == 2:
        return list(data.get("items") or [])
    draft = data if isinstance(data, dict) else {}
    approved = json.loads(row.approved_json) if row.approved_json else None
    items = [{"stage": int(row.stage_no), "page": draft.get("page"), "kind": row.kind, "status": row.status, "params": draft,
              "approved": None, "writtenTask": True, "templateId": row.template_id, "pageText": "", "updatedAt": ""}]
    if approved is not None:
        key = (int(row.approved_stage or row.stage_no), approved.get("page"))
        if key == (items[0]["stage"], items[0]["page"]):
            items[0]["approved"] = approved
        else:
            items[0]["templateId"] = None
            items.append({"stage": key[0], "page": key[1], "kind": row.kind, "status": "approved", "params": approved, "approved": approved,
                          "writtenTask": True, "templateId": row.template_id, "pageText": "", "updatedAt": ""})
    return items


def courseware_for_session(implementation: Any, db: Any, row: Any, page_index: int | None) -> tuple[dict[str, Any] | None, str]:
    """The approved courseware of the page on screen, without answers; else a note for the teacher."""
    t = register_courseware_table(implementation)
    c = db.execute(select(t).where(t.c.school_id == row.school_id, t.c.lesson_id == row.lesson_id,
                                   t.c.approved_json.isnot(None))).first()
    stage = int(row.current_stage or 0)
    approved = [i for i in items_of(c) if i.get("approved") is not None and int(i["stage"]) == stage]
    if not approved:
        return None, ""
    pages = stage_pages(db.get(implementation.TeachingLesson, row.lesson_id), stage)
    if pages:
        # Each courseware belongs to one slide or worked example; other pages keep their own content.
        bound = [i for i in approved if i.get("page") is not None and 0 <= int(i["page"]) < len(pages)]
        item = next((i for i in bound if int(i["page"]) == page_index), None)
        if item is None:
            if bound:
                return None, "本环节第 " + "、".join(str(int(i["page"]) + 1) for i in sorted(bound, key=lambda i: i["page"])) + " 页有互动课件。"
            return None, "本环节有互动课件，但没有对应到具体的页（例题）。请到备课页“互动课件”选择对应页并重新审核。"
    else:
        item = approved[0]
    params = item["approved"]
    key = f"{row.id}:{stage}:{item.get('page')}"
    view = json.loads(c.live_json or "{}").get(key) or cw.clean_view(item["kind"], params, {})
    return {"id": c.id, "kind": item["kind"], "kindLabel": cw.KIND_LABEL[item["kind"]], "stageNo": stage, "page": item.get("page"),
            "params": cw.public_params(item["kind"], params), "view": view}, ""


def install_weekend_courseware(implementation: Any) -> APIRouter:
    app = implementation.app
    if getattr(app.state, "weekend_courseware_installed", False):
        return app.state.weekend_courseware_router
    from changying.services.lesson_written import template_meta, written_templates
    from changying.web.weekend_views import register_weekend_tables
    from changying.web.weekend_written import register_written_tables

    t = register_courseware_table(implementation)
    tables = register_weekend_tables(implementation)
    sessions, slide = tables["sessions"], tables["slide"]
    written = register_written_tables(implementation)["questions"]
    Lesson = implementation.TeachingLesson
    current_user, get_db, need = implementation.current_user, implementation.get_db, implementation.need
    router = APIRouter()

    def my_lesson(db: Any, u: Any, lid: int) -> Any:
        need(u, "teacher")
        lesson = db.get(Lesson, lid)
        if lesson is None or int(lesson.school_id) != int(u.school_id) or lesson.subject not in cw.TEMPLATES:
            raise HTTPException(404, "没有找到这节课")
        return lesson

    def row_for(db: Any, lesson: Any, lock: bool = False) -> Any:
        q = select(t).where(t.c.school_id == lesson.school_id, t.c.lesson_id == lesson.id)
        return db.execute(q.with_for_update() if lock else q).first()

    def find(items: list[dict[str, Any]], stage: int, page: int | None) -> dict[str, Any] | None:
        return next((i for i in items if int(i["stage"]) == stage and i.get("page") == page), None)

    def checked_page(lesson: Any, stage_no: int, page: int | None) -> int | None:
        pages = stage_pages(lesson, stage_no)
        if not pages:
            return None
        if page is None or not 0 <= page < len(pages):
            raise HTTPException(400, "这个环节有分页，请选择课件对应的页（例题）")
        return page

    def write(db: Any, u: Any, lesson: Any, items: list[dict[str, Any]]) -> None:
        c = row_for(db, lesson, lock=True)
        items = sorted(items, key=lambda i: (int(i["stage"]), -1 if i.get("page") is None else int(i["page"])))
        approved = [[int(i["stage"]), i.get("page")] for i in items if i.get("approved") is not None]
        values = dict(kind="multi", stage_no=int(items[0]["stage"]) if items else 3, status="approved" if approved else "draft",
                      params_json=json.dumps({"version": 2, "items": items}, ensure_ascii=False),
                      approved_json=json.dumps(approved) if approved else None, approved_stage=None, template_id=None,
                      updated_at=datetime.utcnow())
        if c is None:
            db.execute(insert(t).values(school_id=u.school_id, lesson_id=lesson.id, teacher_id=u.id, live_json="{}", **values))
        else:
            db.execute(update(t).where(t.c.id == c.id).values(**values))
        db.commit()

    def task(item: dict[str, Any], params: dict[str, Any]) -> dict[str, str]:
        try:
            return dict(zip(("stem", "reference"), cw.written_question(item["kind"], params, item.get("pageText") or "")))
        except ValueError as e:
            return {"stem": str(e), "reference": ""}

    def payload(db: Any, lesson: Any) -> dict[str, Any]:
        items = []
        for i in items_of(row_for(db, lesson)):
            items.append({**i, "kindLabel": cw.KIND_LABEL.get(i["kind"], i["kind"]), "writtenTaskPreview": task(i, i["params"])})
        return {"lessonId": lesson.id, "subject": lesson.subject, "templates": list(cw.TEMPLATES[lesson.subject]), "kindLabels": cw.KIND_LABEL,
                "hasSource": bool((lesson.reading_plan or "").strip()), "items": items,
                "pages": {str(n): [_short(x, 80) for x in stage_pages(lesson, n)] for n in (2, 3)}}

    def upsert(db: Any, u: Any, lesson: Any, stage: int, page: int | None, kind: str, params: dict[str, Any],
               written_task: bool | None, page_text: str) -> None:
        items = items_of(row_for(db, lesson))
        old = find(items, stage, page)
        if old is None:
            items.append({"stage": stage, "page": page, "kind": kind, "status": "draft", "params": params, "approved": None,
                          "writtenTask": bool(written_task), "templateId": None, "pageText": page_text})
        else:
            # The approved version stays in classrooms until this draft is approved.
            old.update(kind=kind, status="draft", params=params, pageText=page_text or old.get("pageText", ""))
            if written_task is not None:
                old["writtenTask"] = bool(written_task)
        target = find(items, stage, page)
        target["updatedAt"] = datetime.now(implementation.SCHOOL_TZ).strftime("%Y-%m-%d %H:%M")
        write(db, u, lesson, items)

    @router.get("/teacher/weekend/lessons/{lid}/courseware")
    def get_courseware(lid: int, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        return payload(db, my_lesson(db, u, lid))

    @router.post("/teacher/weekend/lessons/{lid}/courseware/generate")
    def generate(lid: int, b: PageBody, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        """Preparation only: for one page, AI picks a reviewed template and fills it; validated, saved as a draft."""
        lesson = my_lesson(db, u, lid)
        page = checked_page(lesson, b.stageNo, b.page)
        pages = stage_pages(lesson, b.stageNo)
        page_text = pages[page] if page is not None else ""
        info = {"title": lesson.title, "coreTarget": lesson.core_target or "", "sourceText": lesson.reading_plan or "",
                "pageText": page_text or (lesson.teacher_plan or "")[:1500]}
        try:
            data = implementation._ai_json(implementation._ai_call(db, u, AI_FEATURE, cw.generation_prompt(lesson.subject, info), timeout=60))
            kind = str(data.get("template") or "") if isinstance(data, dict) else ""
            if kind not in cw.TEMPLATES[lesson.subject] or (kind == "reading" and not (lesson.reading_plan or "").strip()):
                raise ValueError("没有选择可用的模板")
            params = cw.clean(kind, data, lesson.reading_plan or "")
        except ValueError as e:
            raise HTTPException(502, f"第 {(page or 0) + 1} 页：AI 生成的课件未通过校验（{e}），已有课件未改动，可重试或手动填写")
        except HTTPException as e:
            raise HTTPException(502, f"第 {(page or 0) + 1} 页：生成失败（{e.detail}），已有课件未改动，可重试或手动填写")
        upsert(db, u, lesson, b.stageNo, page, kind, params, None, page_text)
        implementation.audit(db, u, "weekend.courseware.generate", f"lesson={lid}:stage={b.stageNo}:page={page}:kind={kind}")
        db.commit()
        return payload(db, lesson)

    @router.put("/teacher/weekend/lessons/{lid}/courseware")
    def save(lid: int, b: SaveBody, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        lesson = my_lesson(db, u, lid)
        if b.kind not in cw.TEMPLATES[lesson.subject]:
            raise HTTPException(400, "这门课不能使用这种课件模板")
        try:
            params = cw.clean(b.kind, b.params, lesson.reading_plan or "")
        except ValueError as e:
            raise HTTPException(400, str(e))
        page = checked_page(lesson, b.stageNo, b.page)
        pages = stage_pages(lesson, b.stageNo)
        upsert(db, u, lesson, b.stageNo, page, b.kind, params, b.writtenTask, pages[page] if page is not None else "")
        return payload(db, lesson)

    def drop_template(db: Any, u: Any, lesson: Any, template_id: int | None) -> None:
        # Only the lesson's preparation template (session_id 0); classroom snapshots are never touched.
        if template_id:
            db.execute(delete(written).where(written.c.id == template_id, written.c.session_id == 0,
                                             written.c.lesson_id == lesson.id, written.c.school_id == u.school_id))

    @router.post("/teacher/weekend/lessons/{lid}/courseware/approve")
    def approve(lid: int, b: PageBody, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        """Teacher review done for one page: classrooms show it on that page; optional written task for pupils."""
        lesson = my_lesson(db, u, lid)
        page = checked_page(lesson, b.stageNo, b.page)
        items = items_of(row_for(db, lesson))
        item = find(items, b.stageNo, page)
        if item is None:
            raise HTTPException(404, "这一页还没有课件，请先生成或填写")
        try:
            params = cw.clean(item["kind"], item["params"], lesson.reading_plan or "")
        except ValueError as e:
            raise HTTPException(400, str(e))
        template_id = item.get("templateId")
        if item.get("writtenTask"):
            try:
                stem, reference = cw.written_question(item["kind"], params, item.get("pageText") or "")
            except ValueError as e:
                raise HTTPException(400, str(e))
            meta = {"approved": True, "type": "short_answer", "hints": [], "courseware": f"{b.stageNo}:{page}"}
            template = next((q for q in written_templates(db, written, u.school_id, u.id, lesson.id) if q.id == template_id), None)
            if template is not None and template_meta(template).get("courseware"):
                db.execute(update(written).where(written.c.id == template.id).values(stem=stem, reference=reference,
                                                                                      hints_json=json.dumps(meta, ensure_ascii=False)))
            else:
                template_id = db.execute(insert(written).values(school_id=u.school_id, teacher_id=u.id, lesson_id=lesson.id, session_id=0, stem=stem,
                                                                reference=reference, hints_json=json.dumps(meta, ensure_ascii=False))).inserted_primary_key[0]
        else:
            drop_template(db, u, lesson, template_id)
            template_id = None
        item.update(status="approved", params=params, approved=params, templateId=template_id)
        write(db, u, lesson, items)
        implementation.audit(db, u, "weekend.courseware.approve", f"lesson={lid}:stage={b.stageNo}:page={page}:template={template_id}")
        db.commit()
        return payload(db, lesson)

    @router.post("/teacher/weekend/lessons/{lid}/courseware/remove")
    def remove(lid: int, b: PageBody, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        lesson = my_lesson(db, u, lid)
        items = items_of(row_for(db, lesson))
        item = find(items, b.stageNo, b.page)
        if item is None:
            raise HTTPException(404, "这一页没有课件")
        drop_template(db, u, lesson, item.get("templateId"))
        items.remove(item)
        write(db, u, lesson, items)
        return payload(db, lesson)

    @router.post("/teacher/weekend/sessions/{sid}/courseware/view")
    def set_view(sid: int, b: ViewBody, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        """Teacher drags, turns or reveals during class: stores the screen state only (no AI)."""
        need(u, "teacher")
        row = db.execute(select(sessions).where(sessions.c.id == sid, sessions.c.school_id == u.school_id,
                                                sessions.c.teacher_id == u.id)).first()
        if row is None:
            raise HTTPException(404, "没有找到这节课堂")
        if row.status != "running":
            raise HTTPException(409, "这节课还没开始或已结束")
        c = db.execute(select(t).where(t.c.school_id == row.school_id, t.c.lesson_id == row.lesson_id).with_for_update()).first()
        cursor = db.execute(select(slide).where(slide.c.session_id == row.id)).first()
        index = int(cursor.idx) if cursor is not None and int(cursor.stage_no) == int(row.current_stage) else 0
        pages = stage_pages(db.get(Lesson, row.lesson_id), int(row.current_stage))
        index = max(0, min(index, len(pages) - 1)) if pages else index      # same clamp as the screen state
        shown, note = courseware_for_session(implementation, db, row, index)
        if shown is None or c is None:
            raise HTTPException(409, note or "当前页没有互动课件")
        item = next(i for i in items_of(c) if i.get("approved") is not None and int(i["stage"]) == int(row.current_stage)
                    and i.get("page") == shown["page"])
        view = cw.clean_view(item["kind"], item["approved"], b.view)
        live = json.loads(c.live_json or "{}")
        live[f"{sid}:{int(row.current_stage)}:{shown['page']}"] = view
        db.execute(update(t).where(t.c.id == c.id).values(live_json=json.dumps(live, ensure_ascii=False)))
        db.commit()
        return {"view": view}

    app.include_router(router)
    app.state.weekend_courseware_installed = True
    app.state.weekend_courseware_router = router
    return router


__all__ = ["courseware_for_session", "install_weekend_courseware", "items_of", "register_courseware_table", "stage_pages"]
