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
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel
from sqlalchemy import Boolean, Column, DateTime, Integer, String, Table, desc, insert, select, update

from changying.services.weekend_stages import (
    MAX_EXTEND_MIN, STAGE_COUNT, STAGES, remaining_seconds, stage_by_no, stage_content,
)
from changying.services.weekend_answers import practice_deck, practice_cursor
from changying.web.weekend_pages import board_page_html, control_page_html

NO_CACHE = {"Cache-Control": "no-store"}


class CreateBody(BaseModel):
    lessonId: int
    classId: int | None = None


class ClassBody(BaseModel):
    classId: int


class GotoBody(BaseModel):
    stage: int


class ExtendBody(BaseModel):
    minutes: int = 5


class SlideBody(BaseModel):
    delta: int = 0
    index: int | None = None


class PublishAnswerBody(BaseModel):
    question: int


class CoverBody(BaseModel):
    covered: bool = True


def register_weekend_tables(implementation: Any) -> dict[str, Table]:
    from changying.services.weekend_roster import register_roster_table
    register_roster_table(implementation)
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
                                             "teacher_plan", "examples_json", "ppt_json", "closure_training", "reading_plan")}

    def mine(db: Any, u: Any, sid: int) -> Any:
        row = db.execute(select(sessions).where(sessions.c.id == sid, sessions.c.school_id == u.school_id).with_for_update()).first()
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
        from changying.services.weekend_presentation import lesson_deck
        return lesson_deck(lesson, stage_no)

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
            deck, count, idx, total = practice_deck(implementation, db, row)
            out["answersPublished"] = bool(total) and count == total
            out["answerRelease"] = {"published": count, "total": total, "nextQuestion": count+1 if count < total else None}
            out["content"] = [
                "随堂练习来自‘习题审核’中的审核题；与本节例题完全重复的题目不会再次发放。",
                "已公布题目请听老师讲评，其余题目继续作答。" if count else "请先独立作答并提交，等待老师逐题公布答案。",
            ]
            if deck:
                out["deck"] = {"total": len(deck), "index": idx}
                out["answerRelease"].update({"currentQuestion": deck[idx]["question"], "currentPublished": deck[idx]["published"]})
                out["content"].append(deck[idx]["text"])
        if no in (4, 5) and row.status == "running":
            from changying.web.weekend_written import register_written_tables
            written_q = register_written_tables(implementation)['questions']
            peer_t = implementation.Base.metadata.tables.get('weekend_peer_help')
            if peer_t is not None:
                for p in db.execute(select(peer_t).where(peer_t.c.session_id == row.id, peer_t.c.question_id < 0).order_by(peer_t.c.id)):
                    who = db.scalar(select(implementation.User.name).where(implementation.User.id == p.tutor_id))
                    stem = db.scalar(select(written_q.c.stem).where(written_q.c.id == -p.question_id, written_q.c.session_id == row.id))
                    if who and stem:
                        out['content'].append(f"请 {who} 同学来讲：{stem.split(chr(10)+chr(10))[-1]}")
        if row.status == "running" and not (board and row.covered):
            from changying.web.weekend_courseware import courseware_for_session
            courseware, notice = courseware_for_session(implementation, db, row, out["deck"]["index"] if "deck" in out else None)
            if courseware is not None:
                out["courseware"] = courseware
            if notice and not board:
                out["coursewareNotice"] = notice
        if board:
            if row.covered:
                out["content"] = []
            return out
        stages = []
        for s in STAGES:
            done = db.execute(select(log).where(log.c.session_id == row.id, log.c.stage_no == s["no"]).order_by(log.c.id)).all()
            stages.append({"no": s["no"], "name": s["name"], "minutes": s["minutes"], "goal": s["goal"],
                           "visited": bool(done), "extendMin": sum(int(d.extend_min) for d in done)})
        from changying.services.weekend_roster import session_class, session_roster
        bound = session_class(implementation, db, row)
        out["class"] = {"id": bound.class_id, "name": bound.class_name, "studentCount": len(session_roster(implementation, db, row))} if bound else None
        out["stages"] = stages
        out["lesson"] = {"title": lesson["title"], "subject": lesson["subject"], "unit": lesson["unit"]}
        return out

    @router.get("/v1/lesson11-methods-v2.js", include_in_schema=False)
    def lesson11_methods_script():
        # External ES5-only diagram patch keeps existing Safari12 compiled inline
        # scripts unchanged. This contains no student or teacher data.
        return Response(
            Path(__file__).with_name("lesson11_methods_v2.js").read_text(encoding="utf-8"),
            media_type="application/javascript", headers={"Cache-Control": "public, max-age=3600"},
        )

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
        from changying.services.weekend_roster import class_members, bind_class
        if b.classId is not None:
            class_members(implementation, db, u, b.classId)
        lesson = lesson_dict(db, int(u.school_id), b.lessonId)
        db.execute(select(Lesson.id).where(Lesson.id == b.lessonId).with_for_update()).first()
        sid = int(db.execute(insert(sessions).values(
            school_id=u.school_id, teacher_id=u.id, lesson_id=b.lessonId, status="planned", current_stage=0, covered=False,
            title=f"{lesson['subject']} 第{lesson['lesson_no']}课 {lesson['title']}"[:220], created_at=datetime.utcnow())).inserted_primary_key[0])
        from changying.services.lesson_written import snapshot_written_questions
        from changying.web.weekend_written import register_written_tables
        snapshot_written_questions(db, register_written_tables(implementation)["questions"], u.school_id, u.id, b.lessonId, sid)
        if b.classId is not None:
            bind_class(implementation, db, mine(db, u, sid), u, b.classId)
        db.commit()
        return state(db, mine(db, u, sid))

    @router.get("/teacher/weekend/classes")
    def classes(u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "teacher")
        SC, CS, User = implementation.SchoolClass, implementation.ClassStudent, implementation.User
        rows = db.scalars(select(SC).where(SC.school_id == u.school_id, SC.teacher_id == u.id).order_by(SC.name, SC.id)).all()
        return {"items": [{"id": c.id, "name": c.name, "studentCount": len(db.scalars(select(User.id).join(CS, CS.student_id == User.id).where(CS.class_id == c.id, User.school_id == u.school_id, User.role == "student")).all())} for c in rows]}

    @router.put("/teacher/weekend/sessions/{sid}/class")
    def choose_class(sid: int, b: ClassBody, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "teacher")
        row = mine(db, u, sid)
        db.execute(select(sessions.c.id).where(sessions.c.id == sid).with_for_update()).first()
        # Binding is allowed for an untouched legacy classroom, even if its
        # clock has started. Never reinterpret existing answers or points.
        md = implementation.Base.metadata
        for name in ("weekend_answers", "weekend_hint_log", "weekend_written_submissions", "weekend_written_hint_log", "weekend_peer_help", "weekend_awards", "weekend_metrics", "weekend_briefs"):
            table = md.tables.get(name)
            if table is not None and db.execute(select(table).where(table.c.session_id == sid).limit(1)).first() is not None:
                raise HTTPException(409, "本节课已有学生学习或积分记录，不能更换班级；请为正确班级新建课堂")
        if row.status == "finished":
            raise HTTPException(409, "已结束的课堂不能更换班级")
        from changying.services.weekend_roster import bind_class
        bind_class(implementation, db, row, u, b.classId)
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
        db.execute(select(sessions.c.id).where(sessions.c.id == sid, sessions.c.school_id == u.school_id).with_for_update()).first()
        row = mine(db, u, sid)
        running(row)
        no = int(row.current_stage)
        deck = practice_deck(implementation, db, row)[0] if no == 4 else deck_for(lesson_dict(db, int(row.school_id), int(row.lesson_id)), no) if no in (2, 3) else []
        if not deck:
            raise HTTPException(409, "这个环节没有可翻页的内容")
        cur = state(db, row)["deck"]["index"]
        target = b.index if b.index is not None else cur + b.delta
        target = max(0, min(int(target), len(deck) - 1))
        if no == 4:
            target = practice_cursor(practice_deck(implementation, db, row)[1], target)
        ex = db.execute(select(slide_t.c.id).where(slide_t.c.session_id == sid)).first()
        if ex:
            db.execute(update(slide_t).where(slide_t.c.id == ex.id).values(stage_no=no, idx=target))
        else:
            db.execute(insert(slide_t).values(school_id=row.school_id, session_id=sid, stage_no=no, idx=target))
        db.commit()
        return state(db, mine(db, u, sid))

    @router.post("/teacher/weekend/sessions/{sid}/practice-question")
    def show_practice_question(sid: int, b: PublishAnswerBody, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "teacher")
        db.execute(select(sessions.c.id).where(sessions.c.id == sid, sessions.c.school_id == u.school_id).with_for_update()).first()
        row = mine(db, u, sid)
        running(row)
        if row.current_stage != 4:
            raise HTTPException(409, "请在随堂练习环节选择题目")
        deck, count, _, total = practice_deck(implementation, db, row)
        if not 1 <= b.question <= total:
            raise HTTPException(400, "请选择有效题目")
        page = next(i for i, item in enumerate(deck) if item['question'] == b.question)
        value = practice_cursor(count, page)
        cursor = db.execute(select(slide_t.c.id).where(slide_t.c.session_id == sid)).first()
        if cursor:
            db.execute(update(slide_t).where(slide_t.c.id == cursor.id).values(stage_no=4, idx=value))
        else:
            db.execute(insert(slide_t).values(school_id=row.school_id, session_id=sid, stage_no=4, idx=value))
        db.commit()
        return state(db, mine(db, u, sid))

    @router.post("/teacher/weekend/sessions/{sid}/publish-answers")
    def publish_answers(sid: int, b: PublishAnswerBody, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "teacher")
        row = mine(db, u, sid)
        db.execute(select(sessions.c.id).where(sessions.c.id == sid).with_for_update()).first()
        running(row)
        if int(row.current_stage) != 4:
            raise HTTPException(409, "请在随堂练习环节公布答案")
        deck, count, _, total = practice_deck(implementation, db, row)
        if not 1 <= b.question <= total:
            raise HTTPException(400, "请选择有效题目")
        if b.question > count+1:
            raise HTTPException(409, "请按题目顺序公布答案")
        if b.question == count+1:
            # The request carries the ordinal: retries cannot release another question.
            count += 1
            page = next(i for i, item in enumerate(deck) if item["question"] == b.question)
            cursor = db.execute(select(slide_t.c.id).where(slide_t.c.session_id == sid)).first()
            value = practice_cursor(count, page)
            if cursor:
                db.execute(update(slide_t).where(slide_t.c.id == cursor.id).values(stage_no=4, idx=value))
            else:
                db.execute(insert(slide_t).values(school_id=row.school_id, session_id=sid, stage_no=4, idx=value))
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
    from changying.web.weekend_backup import install_weekend_backup
    install_weekend_backup(implementation)
    return router


__all__ = ["install_weekend_views", "register_weekend_tables"]



