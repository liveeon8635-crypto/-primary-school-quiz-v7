"""周末课 课前互动课件（试点：数学图形旋转、语文文本依据）.

teacher  GET  /teacher/weekend/lessons/{lid}/courseware            this lesson's courseware (draft and approved)
         POST /teacher/weekend/lessons/{lid}/courseware/generate   {stageNo} AI fills the template parameters (draft)
         PUT  /teacher/weekend/lessons/{lid}/courseware            {stageNo, params} teacher edits (back to draft)
         POST /teacher/weekend/lessons/{lid}/courseware/approve    approve: classrooms use it, pupils get its written task
         POST /teacher/weekend/sessions/{sid}/courseware/view      {view} live screen state while teaching (no AI)

The approved parameters reach the big screen with the existing session state (see weekend_views.state);
pupils answer the courseware task through the existing written questions (text/photo, teacher review,
question-by-question release). Templates and parameters are validated in services/weekend_courseware.py.
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import Column, DateTime, Integer, String, Table, Text, insert, select, update

from changying.services import weekend_courseware as cw
from changying.services.weekend_stages import STAGE_COUNT

AI_FEATURE = "weekend_courseware"


class GenerateBody(BaseModel):
    stageNo: int = Field(default=3, ge=1, le=STAGE_COUNT)
    page: int | None = Field(default=None, ge=0)


class SaveBody(BaseModel):
    stageNo: int = Field(ge=1, le=STAGE_COUNT)
    page: int | None = Field(default=None, ge=0)
    params: dict[str, Any]


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
              Column("status", String(12), nullable=False),            # draft | approved
              Column("params_json", Text, nullable=False),             # the version being edited
              Column("approved_json", Text, nullable=True),            # what classrooms use
              Column("approved_stage", Integer, nullable=True),
              Column("template_id", Integer, nullable=True),           # the pupils' written task (lesson template)
              Column("live_json", Text, nullable=False),               # {session id: screen state}
              Column("updated_at", DateTime, nullable=False))
    return md.tables["weekend_courseware"]


def stage_pages(lesson: Any, stage_no: int) -> list[str]:
    """The pages the big screen pages through in this stage (slides or worked examples); empty when it has none."""
    from changying.services.weekend_presentation import lesson_deck
    return lesson_deck({"ppt_json": lesson.ppt_json, "examples_json": lesson.examples_json, "reading_plan": lesson.reading_plan}, stage_no)


def _short(text: str, limit: int = 40) -> str:
    line = " ".join(str(text or "").split())
    return line if len(line) <= limit else line[:limit] + "…"


def courseware_for_session(implementation: Any, db: Any, row: Any, page_index: int | None) -> tuple[dict[str, Any] | None, str]:
    """The approved courseware when the screen is on its own page, without answers; else a note for the teacher."""
    t = register_courseware_table(implementation)
    c = db.execute(select(t).where(t.c.school_id == row.school_id, t.c.lesson_id == row.lesson_id,
                                   t.c.approved_json.isnot(None))).first()
    if c is None or int(c.approved_stage or 0) != int(row.current_stage or 0):
        return None, ""
    params = json.loads(c.approved_json)
    pages = stage_pages(db.get(implementation.TeachingLesson, row.lesson_id), int(c.approved_stage))
    page = params.get("page")
    if pages:
        # A courseware belongs to one slide or worked example; other pages keep their own content.
        if page is None or not 0 <= int(page) < len(pages):
            return None, "本环节有互动课件，但没有对应到具体的页（例题）。请到备课页“互动课件”选择对应页并重新审核。"
        if page_index != int(page):
            return None, f"互动课件在第 {int(page) + 1} 页显示：{_short(pages[int(page)])}"
    view = json.loads(c.live_json or "{}").get(str(row.id)) or cw.clean_view(c.kind, params, {})
    return {"id": c.id, "kind": c.kind, "kindLabel": cw.KIND_LABEL[c.kind], "stageNo": int(c.approved_stage), "page": page,
            "params": cw.public_params(c.kind, params), "view": view}, ""


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
        if lesson is None or int(lesson.school_id) != int(u.school_id) or lesson.subject not in cw.KINDS:
            raise HTTPException(404, "没有找到这节课")
        return lesson

    def row_for(db: Any, lesson: Any) -> Any:
        return db.execute(select(t).where(t.c.school_id == lesson.school_id, t.c.lesson_id == lesson.id)).first()

    def payload(db: Any, lesson: Any) -> dict[str, Any]:
        kind = cw.KINDS[lesson.subject]
        c = row_for(db, lesson)
        item = None
        if c is not None:
            params = json.loads(c.params_json)
            item = {"id": c.id, "kind": c.kind, "stageNo": int(c.stage_no), "status": c.status, "params": params,
                    "approvedStage": c.approved_stage, "hasApproved": c.approved_json is not None,
                    "templateId": c.template_id, "writtenTask": dict(zip(("stem", "reference"), cw.written_question(c.kind, params))),
                    "updatedAt": c.updated_at.strftime("%Y-%m-%d %H:%M")}
        return {"lessonId": lesson.id, "subject": lesson.subject, "kind": kind, "kindLabel": cw.KIND_LABEL[kind],
                "hasSource": bool((lesson.reading_plan or "").strip()), "item": item,
                "pages": {str(n): [_short(x, 80) for x in stage_pages(lesson, n)] for n in (2, 3)}}

    def checked_page(lesson: Any, stage_no: int, page: int | None) -> int | None:
        pages = stage_pages(lesson, stage_no)
        if not pages:
            return None
        if page is None or not 0 <= page < len(pages):
            raise HTTPException(400, "这个环节有分页，请选择课件对应的页（例题）")
        return page

    def save_draft(db: Any, u: Any, lesson: Any, kind: str, stage_no: int, params: dict[str, Any]) -> None:
        now = datetime.utcnow()
        c = row_for(db, lesson)
        values = dict(kind=kind, stage_no=stage_no, status="draft", params_json=json.dumps(params, ensure_ascii=False), updated_at=now)
        if c is None:
            db.execute(insert(t).values(school_id=u.school_id, lesson_id=lesson.id, teacher_id=u.id, live_json="{}", **values))
        else:
            # The approved version stays in use by classrooms until the new draft is approved.
            db.execute(update(t).where(t.c.id == c.id).values(**values))
        db.commit()

    @router.get("/teacher/weekend/lessons/{lid}/courseware")
    def get_courseware(lid: int, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        return payload(db, my_lesson(db, u, lid))

    @router.post("/teacher/weekend/lessons/{lid}/courseware/generate")
    def generate(lid: int, b: GenerateBody, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        """Preparation only: AI returns template parameters, validated before they are saved as a draft."""
        lesson = my_lesson(db, u, lid)
        kind = cw.KINDS[lesson.subject]
        if kind == "reading" and not (lesson.reading_plan or "").strip():
            raise HTTPException(400, "请先导入含阅读原文的教案，课件只能摘取原文")
        page = checked_page(lesson, b.stageNo, b.page)
        info = {"title": lesson.title, "coreTarget": lesson.core_target or "", "teacherPlan": lesson.teacher_plan or "",
                "sourceText": lesson.reading_plan or "",
                "pageText": stage_pages(lesson, b.stageNo)[page] if page is not None else ""}
        try:
            data = implementation._ai_json(implementation._ai_call(db, u, AI_FEATURE, cw.generation_prompt(kind, info), timeout=60))
            if isinstance(data, dict) and str(data.get("unsuitable") or "").strip():
                raise HTTPException(400, f"这一页不适合{cw.KIND_LABEL[kind]}模板：{str(data['unsuitable']).strip()[:120]}。已有课件未改动，请换一页")
            params = cw.clean(kind, data, lesson.reading_plan or "")
        except ValueError as e:
            raise HTTPException(502, f"AI 生成的课件未通过校验：{e}。已有课件未改动，可重试或手动填写")
        except HTTPException as e:
            if e.status_code == 400:
                raise
            raise HTTPException(502, f"生成失败：{e.detail}。已有课件未改动，可重试或手动填写")
        params["page"] = page
        save_draft(db, u, lesson, kind, b.stageNo, params)
        implementation.audit(db, u, "weekend.courseware.generate", f"lesson={lid}:kind={kind}")
        db.commit()
        return payload(db, lesson)

    @router.put("/teacher/weekend/lessons/{lid}/courseware")
    def save(lid: int, b: SaveBody, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        lesson = my_lesson(db, u, lid)
        kind = cw.KINDS[lesson.subject]
        try:
            params = cw.clean(kind, b.params, lesson.reading_plan or "")
        except ValueError as e:
            raise HTTPException(400, str(e))
        params["page"] = checked_page(lesson, b.stageNo, b.page)
        save_draft(db, u, lesson, kind, b.stageNo, params)
        return payload(db, lesson)

    @router.post("/teacher/weekend/lessons/{lid}/courseware/approve")
    def approve(lid: int, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        """Teacher review done: classrooms of this lesson show it; its written task joins the lesson's approved questions."""
        lesson = my_lesson(db, u, lid)
        c = row_for(db, lesson)
        if c is None:
            raise HTTPException(404, "还没有课件，请先生成或填写")
        stored = json.loads(c.params_json)
        params = cw.clean(c.kind, stored, lesson.reading_plan or "")
        params["page"] = checked_page(lesson, int(c.stage_no), stored.get("page"))
        stem, reference = cw.written_question(c.kind, params)
        meta = {"approved": True, "type": "short_answer", "hints": [], "courseware": c.id}
        template = next((q for q in written_templates(db, written, u.school_id, u.id, lesson.id) if q.id == c.template_id), None)
        if template is not None and template_meta(template).get("courseware") == c.id:
            db.execute(update(written).where(written.c.id == template.id).values(stem=stem, reference=reference,
                                                                                  hints_json=json.dumps(meta, ensure_ascii=False)))
            template_id = template.id
        else:
            template_id = db.execute(insert(written).values(school_id=u.school_id, teacher_id=u.id, lesson_id=lesson.id, session_id=0,
                                                            stem=stem, reference=reference, hints_json=json.dumps(meta, ensure_ascii=False))).inserted_primary_key[0]
        db.execute(update(t).where(t.c.id == c.id).values(status="approved", approved_json=json.dumps(params, ensure_ascii=False),
                                                          approved_stage=c.stage_no, template_id=template_id, updated_at=datetime.utcnow()))
        implementation.audit(db, u, "weekend.courseware.approve", f"lesson={lid}:courseware={c.id}:template={template_id}")
        db.commit()
        return payload(db, lesson)

    @router.post("/teacher/weekend/sessions/{sid}/courseware/view")
    def set_view(sid: int, b: ViewBody, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        """Teacher drags, turns or highlights during class: stores the screen state only."""
        need(u, "teacher")
        row = db.execute(select(sessions).where(sessions.c.id == sid, sessions.c.school_id == u.school_id,
                                                sessions.c.teacher_id == u.id)).first()
        if row is None:
            raise HTTPException(404, "没有找到这节课堂")
        if row.status != "running":
            raise HTTPException(409, "这节课还没开始或已结束")
        c = db.execute(select(t).where(t.c.school_id == row.school_id, t.c.lesson_id == row.lesson_id,
                                       t.c.approved_json.isnot(None)).with_for_update()).first()
        if c is None or int(c.approved_stage or 0) != int(row.current_stage or 0):
            raise HTTPException(409, "当前环节没有互动课件")
        cursor = db.execute(select(slide).where(slide.c.session_id == row.id)).first()
        index = int(cursor.idx) if cursor is not None and int(cursor.stage_no) == int(row.current_stage) else 0
        pages = stage_pages(db.get(Lesson, row.lesson_id), int(row.current_stage))
        index = max(0, min(index, len(pages) - 1)) if pages else index      # same clamp as the screen state
        shown, note = courseware_for_session(implementation, db, row, index)
        if shown is None:
            raise HTTPException(409, note or "当前页没有互动课件")
        view = cw.clean_view(c.kind, json.loads(c.approved_json), b.view)
        live = json.loads(c.live_json or "{}")
        live[str(sid)] = view
        db.execute(update(t).where(t.c.id == c.id).values(live_json=json.dumps(live, ensure_ascii=False)))
        db.commit()
        return {"view": view}

    app.include_router(router)
    app.state.weekend_courseware_installed = True
    app.state.weekend_courseware_router = router
    return router


__all__ = ["courseware_for_session", "install_weekend_courseware", "register_courseware_table"]
