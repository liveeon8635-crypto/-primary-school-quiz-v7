"""周末课 7 环节控制条 (阶段 3a).

teacher  GET  /teacher/weekend/lessons                       lessons the teacher can run
         POST /teacher/weekend/sessions                      {lessonId}
         GET  /teacher/weekend/sessions                      recent sessions
         GET  /teacher/weekend/sessions/{id}                 state + stage timer + content (control bar)
         POST /teacher/weekend/sessions/{id}/start|next|prev|goto|extend|cover|finish
board    GET  /teacher/weekend/sessions/{id}/board           what the big screen may show (same login as the teacher)
pages    /v1/weekend (control)   /v1/weekend-board?s={id} (big screen)

Every state change is recorded in weekend_stage_log (the stage timeline used later for the lesson archive).
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy import Boolean, Column, DateTime, Integer, String, Table, desc, insert, select, update

from changying.services.weekend_stages import (
    MAX_EXTEND_MIN, STAGE_COUNT, STAGES, remaining_seconds, stage_by_no, stage_content,
)
from changying.web.weekend_pages import board_page_html, control_page_html

NO_CACHE = {"Cache-Control": "no-store"}


class CreateBody(BaseModel):
    lessonId: int


class GotoBody(BaseModel):
    stage: int


class ExtendBody(BaseModel):
    minutes: int = 5


class SlideBody(BaseModel):
    delta: int = 0
    index: int | None = None


class CoverBody(BaseModel):
    covered: bool = True


def register_weekend_tables(implementation: Any) -> dict[str, Table]:
    md = implementation.Base.metadata
    sessions = md.tables.get("weekend_sessions")
    if sessions is None:
        sessions = Table(
            "weekend_sessions", md,
            Column("id", Integer, primary_key=True),
            Column("school_id", Integer, nullable=False, index=True),
            Column("teacher_id", Integer, nullable=False, index=True),
            Column("lesson_id", Integer, nullable=False, index=True),
            Column("title", String(220), nullable=False, default=""),
            Column("status", String(20), nullable=False, default="planned", index=True),
            Column("current_stage", Integer, nullable=False, default=0),
            Column("covered", Boolean, nullable=False, default=False),
            Column("created_at", DateTime, nullable=False, default=datetime.utcnow),
            Column("started_at", DateTime, nullable=True),
            Column("ended_at", DateTime, nullable=True),
        )
    log = md.tables.get("weekend_stage_log")
    if log is None:
        log = Table(
            "weekend_stage_log", md,
            Column("id", Integer, primary_key=True),
            Column("school_id", Integer, nullable=False, index=True),
            Column("session_id", Integer, nullable=False, index=True),
            Column("stage_no", Integer, nullable=False),
            Column("planned_min", Integer, nullable=False, default=0),
            Column("extend_min", Integer, nullable=False, default=0),
            Column("started_at", DateTime, nullable=False, default=datetime.utcnow),
            Column("ended_at", DateTime, nullable=True),
        )
    slide = md.tables.get("weekend_slide_state")
    if slide is None:
        slide = Table(
            "weekend_slide_state", md,
            Column("id", Integer, primary_key=True),
            Column("school_id", Integer, nullable=False, index=True),
            Column("session_id", Integer, nullable=False, unique=True),
            Column("stage_no", Integer, nullable=False, default=0),
            Column("idx", Integer, nullable=False, default=0),
        )
    return {"sessions": sessions, "log": log, "slide": slide}


def install_weekend_views(implementation: Any) -> APIRouter:
    app = implementation.app
    if getattr(app.state, "weekend_installed", False):
        return app.state.weekend_router
    t = register_weekend_tables(implementation)
    sessions, log, slide_t = t["sessions"], t["log"], t["slide"]
    Lesson = implementation.TeachingLesson
    current_user, get_db, need = implementation.current_user, implementation.get_db, implementation.need
    router = APIRouter()

    def lesson_dict(db: Any, school_id: int, lesson_id: int) -> dict[str, Any]:
        row = db.get(Lesson, lesson_id)
        if row is None or int(row.school_id) != int(school_id):
            raise HTTPException(404, "没有找到这节课")
        return {c: getattr(row, c) for c in ("id", "subject", "lesson_no", "unit", "title", "core_target", "duration_min",
                                             "teacher_plan", "examples_json", "ppt_json", "closure_training")}

    def mine(db: Any, u: Any, sid: int) -> Any:
        row = db.execute(select(sessions).where(sessions.c.id == sid, sessions.c.school_id == u.school_id)).first()
        if row is None or int(row.teacher_id) != int(u.id):
            raise HTTPException(404, "没有找到这节课堂")
        return row

    def open_log(db: Any, sid: int) -> Any:
        return db.execute(select(log).where(log.c.session_id == sid, log.c.ended_at.is_(None)).order_by(desc(log.c.id))).first()

    def begin_stage(db: Any, row: Any, stage_no: int, now: datetime) -> None:
        cur = open_log(db, row.id)
        if cur is not None:
            db.execute(update(log).where(log.c.id == cur.id).values(ended_at=now))
        st = stage_by_no(stage_no)
        db.execute(insert(log).values(school_id=row.school_id, session_id=row.id, stage_no=stage_no, planned_min=st["minutes"], extend_min=0, started_at=now))
        db.execute(update(sessions).where(sessions.c.id == row.id).values(current_stage=stage_no))

    def deck_for(lesson: dict[str, Any], stage_no: int) -> list[str]:
        """Pages the teacher pages through on the big screen: their own slides (stage 2) or worked examples (stage 3)."""
        raw = lesson.get("ppt_json") if stage_no == 2 else lesson.get("examples_json")
        try:
            items = json.loads(raw or "[]")
        except Exception:  # noqa: BLE001
            return []
        return [" ".join(str(x).split())[:400] for x in items if str(x or "").strip()] if isinstance(items, list) else []

    def state(db: Any, row: Any, *, board: bool = False) -> dict[str, Any]:
        now = datetime.utcnow()
        lesson = lesson_dict(db, int(row.school_id), int(row.lesson_id))
        cur = open_log(db, row.id) if row.status == "running" else None
        no = int(row.current_stage or 0)
        stage = stage_by_no(no)
        timer = None
        if stage and cur is not None:
            timer = remaining_seconds(cur.planned_min, cur.extend_min, cur.started_at, now)
        out: dict[str, Any] = {
            "id": row.id, "title": row.title, "status": row.status, "covered": bool(row.covered),
            "currentStage": no, "stageName": stage["name"] if stage else "", "goal": stage["goal"] if stage else "",
            "remainingSeconds": timer, "stageCount": STAGE_COUNT,
            "content": stage_content(no, lesson) if stage and row.status == "running" else [],
        }
        if no in (2, 3) and row.status == "running":
            deck = deck_for(lesson, no)
            if deck:
                st_row = db.execute(select(slide_t).where(slide_t.c.session_id == row.id)).first()
                idx = int(st_row.idx) if st_row is not None and int(st_row.stage_no) == no else 0
                idx = max(0, min(idx, len(deck) - 1))
                out["deck"] = {"total": len(deck), "index": idx}
                out["content"] = [deck[idx]]
        if no == 5 and row.status == "running":
            # 练习复盘: name the pupil asked to explain, and the question — never the pupils who got it wrong.
            peer_t = implementation.Base.metadata.tables.get("weekend_peer_help")
            if peer_t is not None:
                User, TQ = implementation.User, implementation.TeachingQuestion
                seen: set[tuple[int, int]] = set()
                lines = []
                for p in db.execute(select(peer_t.c.tutor_id, peer_t.c.question_id).where(peer_t.c.session_id == row.id).order_by(peer_t.c.id)).all():
                    key = (int(p.tutor_id), int(p.question_id))
                    if key in seen:
                        continue
                    seen.add(key)
                    who = db.scalar(select(User.name).where(User.id == p.tutor_id))
                    stem = db.scalar(select(TQ.stem).where(TQ.id == p.question_id))
                    if who and stem:
                        lines.append(f"请 {who} 同学来讲：{stem}")
                out["content"] = out["content"] + lines
        if no == 4 and row.status == "running":
            # 随堂练习: the big screen shows the question stems (never options or answers) next to the instructions.
            TQ = implementation.TeachingQuestion
            stems = db.scalars(select(TQ.stem).where(TQ.school_id == row.school_id, TQ.lesson_id == row.lesson_id, TQ.active.is_(True)).order_by(TQ.id).limit(12)).all()
            out["content"] = out["content"] + [f"{i}. {t}" for i, t in enumerate(stems, start=1)]
        if board:
            if row.covered:
                out["content"] = []
            return out
        stages = []
        for s in STAGES:
            done = db.execute(select(log).where(log.c.session_id == row.id, log.c.stage_no == s["no"]).order_by(log.c.id)).all()
            stages.append({"no": s["no"], "name": s["name"], "minutes": s["minutes"], "goal": s["goal"],
                           "visited": bool(done), "extendMin": sum(int(d.extend_min) for d in done)})
        out["stages"] = stages
        out["lesson"] = {"title": lesson["title"], "subject": lesson["subject"], "unit": lesson["unit"]}
        return out

    @router.get("/v1/weekend", include_in_schema=False)
    def control_page():
        return HTMLResponse(control_page_html(), headers=NO_CACHE)

    @router.get("/v1/weekend-board", include_in_schema=False)
    def board_page():
        return HTMLResponse(board_page_html(), headers=NO_CACHE)

    @router.get("/teacher/weekend/lessons")
    def lessons(u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "teacher")
        rows = db.scalars(select(Lesson).where(Lesson.school_id == u.school_id).order_by(Lesson.subject, Lesson.lesson_no)).all()
        return {"items": [{"id": r.id, "subject": r.subject, "lessonNo": r.lesson_no, "unit": r.unit, "title": r.title} for r in rows]}

    @router.post("/teacher/weekend/sessions")
    def create(b: CreateBody, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "teacher")
        lesson = lesson_dict(db, int(u.school_id), b.lessonId)
        sid = int(db.execute(insert(sessions).values(
            school_id=u.school_id, teacher_id=u.id, lesson_id=b.lessonId, status="planned", current_stage=0, covered=False,
            title=f"{lesson['subject']} 第{lesson['lesson_no']}课 {lesson['title']}"[:220], created_at=datetime.utcnow())).inserted_primary_key[0])
        db.commit()
        return state(db, mine(db, u, sid))

    @router.get("/teacher/weekend/sessions")
    def recent(u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "teacher")
        rows = db.execute(select(sessions).where(sessions.c.school_id == u.school_id, sessions.c.teacher_id == u.id).order_by(desc(sessions.c.id)).limit(20)).all()
        return {"items": [{"id": r.id, "title": r.title, "status": r.status, "currentStage": r.current_stage,
                           "createdAt": r.created_at.strftime("%Y-%m-%d %H:%M")} for r in rows]}

    @router.get("/teacher/weekend/sessions/{sid}")
    def get_state(sid: int, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "teacher")
        return state(db, mine(db, u, sid))

    @router.get("/teacher/weekend/sessions/{sid}/board")
    def board(sid: int, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "teacher")
        return state(db, mine(db, u, sid), board=True)

    def running(row: Any) -> None:
        if row.status != "running":
            raise HTTPException(409, "这节课还没开始或已结束")

    @router.post("/teacher/weekend/sessions/{sid}/start")
    def start(sid: int, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "teacher")
        row = mine(db, u, sid)
        if row.status != "planned":
            raise HTTPException(409, "这节课已经开始过了")
        now = datetime.utcnow()
        db.execute(update(sessions).where(sessions.c.id == sid).values(status="running", started_at=now))
        row = mine(db, u, sid)
        begin_stage(db, row, 1, now)
        db.commit()
        return state(db, mine(db, u, sid))

    @router.post("/teacher/weekend/sessions/{sid}/next")
    def nxt(sid: int, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "teacher")
        row = mine(db, u, sid)
        running(row)
        if int(row.current_stage) >= STAGE_COUNT:
            return finish_session(db, u, row)
        begin_stage(db, row, int(row.current_stage) + 1, datetime.utcnow())
        db.commit()
        return state(db, mine(db, u, sid))

    @router.post("/teacher/weekend/sessions/{sid}/prev")
    def prev(sid: int, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "teacher")
        row = mine(db, u, sid)
        running(row)
        if int(row.current_stage) <= 1:
            raise HTTPException(400, "已经是第一个环节")
        begin_stage(db, row, int(row.current_stage) - 1, datetime.utcnow())
        db.commit()
        return state(db, mine(db, u, sid))

    @router.post("/teacher/weekend/sessions/{sid}/goto")
    def goto(sid: int, b: GotoBody, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "teacher")
        row = mine(db, u, sid)
        running(row)
        if stage_by_no(b.stage) is None:
            raise HTTPException(400, "没有这个环节")
        if b.stage != int(row.current_stage):
            begin_stage(db, row, b.stage, datetime.utcnow())
            db.commit()
        return state(db, mine(db, u, sid))

    @router.post("/teacher/weekend/sessions/{sid}/extend")
    def extend(sid: int, b: ExtendBody, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "teacher")
        row = mine(db, u, sid)
        running(row)
        cur = open_log(db, sid)
        minutes = max(1, min(int(b.minutes), MAX_EXTEND_MIN))
        if cur is not None:
            db.execute(update(log).where(log.c.id == cur.id).values(extend_min=min(int(cur.extend_min) + minutes, MAX_EXTEND_MIN)))
            db.commit()
        return state(db, mine(db, u, sid))

    @router.post("/teacher/weekend/sessions/{sid}/slide")
    def slide(sid: int, b: SlideBody, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "teacher")
        row = mine(db, u, sid)
        running(row)
        no = int(row.current_stage)
        deck = deck_for(lesson_dict(db, int(row.school_id), int(row.lesson_id)), no) if no in (2, 3) else []
        if not deck:
            raise HTTPException(409, "这个环节没有可翻页的内容")
        cur = state(db, row)["deck"]["index"]
        target = b.index if b.index is not None else cur + b.delta
        target = max(0, min(int(target), len(deck) - 1))
        ex = db.execute(select(slide_t.c.id).where(slide_t.c.session_id == sid)).first()
        if ex:
            db.execute(update(slide_t).where(slide_t.c.id == ex.id).values(stage_no=no, idx=target))
        else:
            db.execute(insert(slide_t).values(school_id=row.school_id, session_id=sid, stage_no=no, idx=target))
        db.commit()
        return state(db, mine(db, u, sid))

    @router.post("/teacher/weekend/sessions/{sid}/cover")
    def cover(sid: int, b: CoverBody, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "teacher")
        mine(db, u, sid)
        db.execute(update(sessions).where(sessions.c.id == sid).values(covered=bool(b.covered)))
        db.commit()
        return state(db, mine(db, u, sid))

    def finish_session(db: Any, u: Any, row: Any) -> dict[str, Any]:
        now = datetime.utcnow()
        cur = open_log(db, row.id)
        if cur is not None:
            db.execute(update(log).where(log.c.id == cur.id).values(ended_at=now))
        db.execute(update(sessions).where(sessions.c.id == row.id).values(status="finished", ended_at=now, covered=False))
        db.commit()
        return state(db, mine(db, u, int(row.id)))

    @router.post("/teacher/weekend/sessions/{sid}/finish")
    def finish(sid: int, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "teacher")
        row = mine(db, u, sid)
        if row.status == "finished":
            return state(db, row)
        return finish_session(db, u, row)

    app.include_router(router)
    app.state.weekend_installed = True
    app.state.weekend_router = router
    return router


__all__ = ["install_weekend_views", "register_weekend_tables"]
