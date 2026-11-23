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
from sqlalchemy import Boolean, Column, DateTime, Integer, String, Table, Text, UniqueConstraint, desc, insert, select, update

from changying.services.weekend_stages import (
    MAX_EXTEND_MIN, STAGE_COUNT, STAGES, remaining_seconds, stage_by_no, stage_content, stages_for,
)
from changying.services.weekend_course_types import (
    course_type_for, frozen_session, lesson_snapshot, practice_stage,
    register_weekend_course_type_tables, workflow_for,
)
from changying.services.weekend_answers import count_practice_ready, practice_deck, practice_cursor, session_question_ids
from changying.web.weekend_pages import board_page_html, control_page_html

NO_CACHE = {"Cache-Control": "no-store"}


class CreateBody(BaseModel):
    lessonId: int
    classId: int | None = None
    requireReady: bool = False


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
    session_q = md.tables.get("weekend_session_questions")
    if session_q is None:
        session_q = Table(
            "weekend_session_questions", md,
            Column("id", Integer, primary_key=True),
            Column("school_id", Integer, nullable=False, index=True),
            Column("session_id", Integer, nullable=False, index=True),
            Column("question_id", Integer, nullable=False),
            Column("added_at", DateTime, nullable=False, default=datetime.utcnow),
            UniqueConstraint("session_id", "question_id", name="uq_weekend_session_question"),
        )
    if "weekend_open_questions" not in md.tables:
        Table("weekend_open_questions", md,
              Column("session_id", Integer, primary_key=True),
              Column("school_id", Integer, nullable=False, index=True),
              Column("opened_question_ids", Text, nullable=False, default="[]"))
    return {"sessions": sessions, "log": log, "slide": slide, "session_questions": session_q}


def install_weekend_views(implementation: Any) -> APIRouter:
    app = implementation.app
    if getattr(app.state, "weekend_installed", False):
        return app.state.weekend_router
    t = register_weekend_tables(implementation)
    sessions, log, slide_t, session_q = t["sessions"], t["log"], t["slide"], t["session_questions"]
    workflow_tables = register_weekend_course_type_tables(implementation)
    session_workflows = workflow_tables["frozen"]
    imported_materials = workflow_tables["materials"]
    Lesson = implementation.TeachingLesson
    current_user, get_db, need = implementation.current_user, implementation.get_db, implementation.need
    router = APIRouter()

    def lesson_dict(db: Any, school_id: int, lesson_id: int) -> dict[str, Any]:
        row = db.get(Lesson, lesson_id)
        if row is None or int(row.school_id) != int(school_id):
            raise HTTPException(404, "没有找到这节课")
        return {c: getattr(row, c) for c in ("id", "subject", "lesson_no", "unit", "title", "core_target", "duration_min",
                                             "teacher_plan", "examples_json", "ppt_json", "closure_training", "reading_plan",
                                             "writing_plan", "essay_review")}

    def session_course(db: Any, row: Any) -> dict[str, Any]:
        frozen = frozen_session(db, implementation, int(row.id))
        if frozen is not None:
            return frozen
        # Pre-upgrade sessions keep their original seven-stage behavior and content.
        return {"courseType": "legacy", "revision": 0,
                "lesson": lesson_dict(db, int(row.school_id), int(row.lesson_id))}

    def mine(db: Any, u: Any, sid: int) -> Any:
        row = db.execute(select(sessions).where(sessions.c.id == sid, sessions.c.school_id == u.school_id).with_for_update()).first()
        if row is None or int(row.teacher_id) != int(u.id):
            raise HTTPException(404, "没有找到这节课堂")
        return row

    def open_log(db: Any, sid: int) -> Any:
        return db.execute(select(log).where(log.c.session_id == sid, log.c.ended_at.is_(None)).order_by(desc(log.c.id))).first()

    def begin_stage(db: Any, row: Any, stage_no: int, now: datetime) -> None:
        course_type = session_course(db, row)["courseType"]
        cur = open_log(db, row.id)
        if cur is not None:
            db.execute(update(log).where(log.c.id == cur.id).values(ended_at=now))
        st = stage_by_no(stage_no, course_type)
        if st is None:
            raise HTTPException(400, "没有这个课型环节")
        db.execute(insert(log).values(school_id=row.school_id, session_id=row.id, stage_no=stage_no, planned_min=st["minutes"], extend_min=0, started_at=now))
        db.execute(update(sessions).where(sessions.c.id == row.id).values(current_stage=stage_no))

    def deck_for(lesson: dict[str, Any], stage_no: int, course_type: str = "math") -> list[str]:
        if course_type == "reading":
            key = {2: "reading_plan", 3: "ppt_json", 5: "closure_training"}.get(stage_no)
            raw = lesson.get(key) if key else ""
            if isinstance(raw, str):
                try:
                    raw = json.loads(raw)
                except (TypeError, ValueError):
                    raw = [line.strip() for line in raw.splitlines() if line.strip()]
            return [str(item.get("title") or item.get("text") or item.get("content") or item.get("stem") or "").strip()
                    if isinstance(item, dict) else str(item).strip() for item in raw] if isinstance(raw, list) else []
        if course_type == "writing":
            key = {2: "examples_json", 3: "ppt_json", 4: "reading_plan", 5: "writing_plan"}.get(stage_no)
            raw = lesson.get(key) if key else ""
            if isinstance(raw, str):
                try:
                    raw = json.loads(raw)
                except (TypeError, ValueError):
                    raw = [line.strip() for line in raw.splitlines() if line.strip()]
            return [str(item.get("title") or item.get("text") or item.get("content") or item.get("stem") or "").strip()
                    if isinstance(item, dict) else str(item).strip() for item in raw] if isinstance(raw, list) else []
        from changying.services.weekend_presentation import lesson_deck
        return lesson_deck(lesson, stage_no)

    def pending_sync_items(db: Any, row: Any) -> tuple[list[int], list[Any]]:
        """Newly approved practice (choice + written) not yet synced into this session."""
        lesson_obj = db.get(Lesson, int(row.lesson_id))
        if lesson_obj is None:
            return [], []
        from changying.services.lesson_written import template_meta, written_templates
        from changying.web.weekend_plan_views import duplicate_of, lesson_worked_examples, question_options
        from changying.web.weekend_written import register_written_tables

        examples = lesson_worked_examples(lesson_obj)
        TQ = implementation.TeachingQuestion
        snap_ids = session_question_ids(db, implementation, row.id)
        new_tqs: list[int] = []
        if snap_ids is not None:
            for q in db.scalars(select(TQ).where(TQ.school_id == row.school_id, TQ.lesson_id == row.lesson_id,
                                                 TQ.stage != "removed", TQ.active.is_(True)).order_by(TQ.id)).all():
                if int(q.id) not in snap_ids and not duplicate_of(q.stem, question_options(q), examples, []):
                    new_tqs.append(int(q.id))
        written = register_written_tables(implementation)["questions"]
        existing_stems = {str(r.stem) for r in db.execute(select(written.c.stem).where(written.c.session_id == row.id)).all()}
        new_written: list[Any] = []
        for w in written_templates(db, written, int(row.school_id), int(row.teacher_id), int(row.lesson_id)):
            if template_meta(w).get("approved") and str(w.stem) not in existing_stems:
                if not duplicate_of(str(w.stem).split("\n\n")[-1].strip(), [], examples, []):
                    new_written.append(w)
        return new_tqs, new_written

    def state(db: Any, row: Any, *, board: bool = False) -> dict[str, Any]:
        now = datetime.utcnow()
        course = session_course(db, row)
        course_type = course["courseType"]
        lesson = course["lesson"]
        cur = open_log(db, row.id) if row.status == "running" else None
        no = int(row.current_stage or 0)
        stages_for_session = stages_for(course_type)
        stage = stage_by_no(no, course_type)
        timer = None
        if stage and cur is not None:
            timer = remaining_seconds(cur.planned_min, cur.extend_min, cur.started_at, now)
        out: dict[str, Any] = {
            "id": row.id, "title": row.title, "status": row.status, "covered": bool(row.covered),
            "currentStage": no, "stageName": stage["name"] if stage else "", "goal": stage["goal"] if stage else "",
            "remainingSeconds": timer, "stageCount": len(stages_for_session), "courseType": course_type,
            "courseRevision": int(course["revision"]),
            "content": stage_content(no, lesson, course_type) if stage and row.status == "running" else [],
        }
        media_stages = (2, 3) if course_type in ("math", "legacy", "reading") else (2, 3, 4)
        if no in media_stages and row.status == "running":
            deck = deck_for(lesson, no, course_type)
            if deck:
                st_row = db.execute(select(slide_t).where(slide_t.c.session_id == row.id)).first()
                idx = int(st_row.idx) if st_row is not None and int(st_row.stage_no) == no else 0
                idx = max(0, min(idx, len(deck) - 1))
                out["deck"] = {"total": len(deck), "index": idx}
                out["content"] = [deck[idx]]
        if course_type in ("math", "legacy") and no == 5 and row.status == "running":
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
        practice_no = practice_stage(course_type)
        if no == practice_no and row.status == "running":
            deck, count, idx, total = practice_deck(implementation, db, row)
            out["answersPublished"] = bool(total) and count == total
            out["answerRelease"] = {"published": count, "total": total, "nextQuestion": count+1 if count < total else None}
            task_label = "随堂练习" if course_type in ("math", "legacy") else "综合练习" if course_type == "reading" else "写作练习"
            out["content"] = [f"{task_label}任务来自已审核内容；尚未开放的题目和答案不会发给学生。",
                              "已公布题目请听老师讲评，其余题目继续作答。" if count else "请先独立作答并提交，等待老师逐题公布答案。"]
            if not total:
                out["content"] = [f"本节课“{task_label}”还没有已审核的任务。",
                                  "请返回备课页导入或配置任务、确认素材关系并完成审核。"]
            if deck:
                out["deck"] = {"total": len(deck), "index": idx}
                out["answerRelease"].update({"currentQuestion": deck[idx]["question"], "currentPublished": deck[idx]["published"]})
                out["content"].append(deck[idx]["text"])
        if course_type in ("math", "legacy") and no in (practice_no, practice_no + 1) and row.status == "running":
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
            courseware, notice = courseware_for_session(implementation, db, row, out.get("deck", {}).get("index"))
            if courseware is not None:
                out["courseware"] = courseware
            if notice and not board:
                out["coursewareNotice"] = notice
        if board:
            if "courseware" in out and out["courseware"]["kind"] == "slide":
                # Keep the cursor/count contract, but send only the current page.
                # Hidden pages must not carry text, answers or media in the response.
                shown = out["courseware"]
                current = int(shown["view"].get("slideIndex", 0))
                shown["params"] = {**shown["params"], "slides": [
                    slide if index == current else {}
                    for index, slide in enumerate(shown["params"].get("slides", []))
                ]}
            if row.covered:
                out["content"] = []
            elif course_type in ("reading", "writing") and no != practice_no:
                # The legacy lesson fields can contain a complete teacher document,
                # including answers. They are not reviewed student-facing nodes:
                # only approved courseware of this page may reach the board.
                out["content"] = [courseware["kindLabel"]] if "courseware" in out else []
                out.pop("deck", None)
            elif course_type in ("reading", "writing") and no == practice_no and "deck" in out:
                from changying.services.weekend_answers import practice_items, question_is_open
                items = practice_items(implementation, db, row)
                question = int(out.get("answerRelease", {}).get("currentQuestion") or 0)
                item = items[question - 1] if 1 <= question <= len(items) else None
                if item is None or not question_is_open(implementation, db, row, item["kind"], item["id"]):
                    is_stage_slide = bool(
                        out.get("courseware")
                        and out["courseware"].get("kind") == "slide"
                        and out["courseware"].get("page") is None
                    )
                    out["content"] = [out["courseware"]["kindLabel"]] if is_stage_slide else ["请等待教师开放本题。"]
                    if not is_stage_slide:
                        out.pop("courseware", None)
                    out.pop("deck", None)
                    out.pop("answerRelease", None)
            return out
        stages = []
        for s in stages_for_session:
            done = db.execute(select(log).where(log.c.session_id == row.id, log.c.stage_no == s["no"]).order_by(log.c.id)).all()
            stages.append({"no": s["no"], "name": s["name"], "minutes": s["minutes"], "goal": s["goal"],
                           "visited": bool(done), "extendMin": sum(int(d.extend_min) for d in done)})
        from changying.services.weekend_roster import session_class, session_roster
        bound = session_class(implementation, db, row)
        out["class"] = {"id": bound.class_id, "name": bound.class_name, "studentCount": len(session_roster(implementation, db, row))} if bound else None
        out["stages"] = stages
        out["lesson"] = {"title": lesson["title"], "subject": lesson["subject"], "unit": lesson["unit"]}
        if row.status != "finished":
            new_tqs, new_written = pending_sync_items(db, row)
            out["pendingPracticeSync"] = len(new_tqs) + len(new_written)
        else:
            out["pendingPracticeSync"] = 0
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
        lesson_row = db.get(Lesson, b.lessonId)
        workflow = workflow_for(db, implementation, lesson_row)
        course_type = "math" if lesson_row.subject == "数学" else (str(workflow.course_type) if workflow else "")
        if lesson_row.subject == "语文" and course_type not in ("reading", "writing"):
            raise HTTPException(409, "这节语文课还未选择课型；请先在备课工作栏选择“阅读课”或“作文课”并保存。")
        if course_type in ("reading", "writing") and db.execute(select(imported_materials.c.id).where(
            imported_materials.c.school_id == int(u.school_id), imported_materials.c.lesson_id == int(lesson_row.id),
            imported_materials.c.status == "pending",
        ).limit(1)).first():
            raise HTTPException(409, "\u672c\u8bfe\u8fd8\u6709\u5bfc\u5165\u7d20\u6750\u5f85\u786e\u8ba4\uff0c\u8bf7\u5b8c\u6210\u7d20\u6750\u5ba1\u6838\u540e\u518d\u521b\u5efa\u8bfe\u5802\u3002")
        if b.requireReady and course_type not in ("reading", "writing") and lesson_row.subject != "语文":
            if count_practice_ready(db, implementation, int(u.school_id), int(u.id), lesson_row) == 0:
                raise HTTPException(
                    409,
                    "第4环节实际可用的随堂练习为 0 道（可能尚未通过练习，或已通过的题都与本课例题重复），暂时不能开课。"
                    "请先在“习题审核”里通过至少 1 道不与例题重复的随堂练习。",
                )
        if lesson_row.subject == "语文":
            from changying.services.chinese_lesson_readiness import chinese_lesson_readiness
            readiness = chinese_lesson_readiness(implementation, db, lesson_row, u.id)
            if not readiness["canStart"]:
                raise HTTPException(409, "不能开课：" + "；".join(readiness["startReasons"]))
        db.execute(select(Lesson.id).where(Lesson.id == b.lessonId).with_for_update()).first()
        now = datetime.utcnow()
        sid = int(db.execute(insert(sessions).values(
            school_id=u.school_id, teacher_id=u.id, lesson_id=b.lessonId, status="planned", current_stage=0, covered=False,
            title=f"{lesson['subject']} 第{lesson['lesson_no']}课 {lesson['title']}"[:220], created_at=now)).inserted_primary_key[0])
        if course_type in ("reading", "writing"):
            revision = int(workflow.revision) if workflow else 0
            db.execute(insert(session_workflows).values(
                session_id=sid, school_id=u.school_id, lesson_id=b.lessonId, course_type=course_type,
                revision=revision, lesson_json=lesson_snapshot(lesson_row), created_at=now,
            ))
        writing_pkg = None
        if course_type == "writing":
            from changying.services.writing_lesson import writing_package
            _, writing_pkg = writing_package(implementation, db, b.lessonId)
        if course_type == "writing" and writing_pkg is not None:
            content = json.loads(lesson_snapshot(lesson_row))
            content["writingPackage"] = {"title": writing_pkg["title"], "approved": True, "nodes": [
                {k:v for k,v in n.items() if k != "originalBase64"} for n in writing_pkg["nodes"] if n["status"] == "confirmed"]}
            content["writingState"] = {"revision": 0, "open": [], "feedback": {}}
            db.execute(update(session_workflows).where(session_workflows.c.session_id == sid).values(
                lesson_json=json.dumps(content, ensure_ascii=False)))
        # New classrooms start closed; only pre-upgrade classrooms lack a gate.
        # Persist this in the classroom creation transaction, before it is visible.
        opened = implementation.Base.metadata.tables["weekend_open_questions"]
        db.execute(insert(opened).values(
            session_id=sid, school_id=u.school_id, opened_question_ids="[]"))
        from changying.services.lesson_written import snapshot_written_questions
        from changying.web.weekend_written import register_written_tables
        from changying.web.weekend_plan_views import duplicate_of, lesson_worked_examples, question_options
        examples = lesson_worked_examples(lesson_row)
        db.execute(insert(session_q).values(school_id=u.school_id, session_id=sid, question_id=0, added_at=now))
        TQ = implementation.TeachingQuestion
        for q in ([] if course_type == "writing" and writing_pkg is not None else db.scalars(select(TQ).where(TQ.school_id == u.school_id, TQ.lesson_id == b.lessonId,
                                             TQ.stage != "removed", TQ.active.is_(True)).order_by(TQ.id)).all()):
            if not duplicate_of(q.stem, question_options(q), examples, []):
                db.execute(insert(session_q).values(school_id=u.school_id, session_id=sid, question_id=int(q.id), added_at=now))
        if course_type == "writing" and writing_pkg is not None:
            task = next(n for n in writing_pkg["nodes"] if n["role"] == "task" and n["status"] == "confirmed")
            db.execute(insert(register_written_tables(implementation)["questions"]).values(
                school_id=u.school_id, teacher_id=u.id, lesson_id=b.lessonId, session_id=sid,
                stem=task["text"], reference="", hints_json="[]"))
        else:
            snapshot_written_questions(db, register_written_tables(implementation)["questions"], u.school_id, u.id, b.lessonId, sid)
        if b.classId is not None:
            bind_class(implementation, db, mine(db, u, sid), u, b.classId)
        db.commit()
        return state(db, mine(db, u, sid))

    @router.post("/teacher/weekend/sessions/{sid}/sync-practice")
    def sync_practice(sid: int, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        """手动把课后新通过的随堂练习补进当前课堂，绝不改动已有题目记录与学生作答。"""
        need(u, "teacher")
        row = mine(db, u, sid)
        if row.status == "finished":
            raise HTTPException(409, "已结束的课堂不能再同步新增练习")
        new_tqs, new_written = pending_sync_items(db, row)
        now = datetime.utcnow()
        if new_tqs:
            if session_question_ids(db, implementation, row.id) is None:
                db.execute(insert(session_q).values(school_id=row.school_id, session_id=row.id, question_id=0, added_at=now))
            for qid in new_tqs:
                db.execute(insert(session_q).values(school_id=row.school_id, session_id=row.id, question_id=qid, added_at=now))
        if new_written:
            from changying.services.lesson_written import template_meta
            from changying.web.weekend_written import register_written_tables
            written = register_written_tables(implementation)["questions"]
            for w in new_written:
                meta = template_meta(w)
                db.execute(insert(written).values(
                    school_id=row.school_id, teacher_id=row.teacher_id, lesson_id=row.lesson_id, session_id=row.id,
                    stem=w.stem, reference=w.reference, hints_json=json.dumps(meta.get("hints", []), ensure_ascii=False),
                ))
        db.commit()
        added = len(new_tqs) + len(new_written)
        msg = f"已同步 {added} 道新增随堂练习到本节课堂（选择题 {len(new_tqs)} 道、文字/照片题 {len(new_written)} 道），已有作答与记录保持不变。" if added else "当前没有需要同步的新增练习。"
        out = state(db, mine(db, u, sid))
        out["addedChoices"] = len(new_tqs)
        out["addedWritten"] = len(new_written)
        out["addedTotal"] = added
        out["message"] = msg
        return out

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
        if session_course(db, row)["courseType"] in ("reading", "writing") and not session_course(db, row)["lesson"].get("writingPackage"):
            from changying.services.chinese_lesson_readiness import chinese_lesson_readiness
            lesson = db.get(Lesson, row.lesson_id)
            ready = chinese_lesson_readiness(implementation, db, lesson, u.id)
            if (not ready["canStart"] or ready["courseType"] != session_course(db, row)["courseType"]):
                raise HTTPException(409, "备课内容或审核已变化，请重新核对并创建课堂：" + "；".join(ready["startReasons"]))
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
        course_type = session_course(db, row)["courseType"]
        if int(row.current_stage) >= len(stages_for(course_type)):
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
        course_type = session_course(db, row)["courseType"]
        if stage_by_no(b.stage, course_type) is None:
            raise HTTPException(400, "没有这个课型环节")
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
        course_type = session_course(db, row)["courseType"]
        practice_no = practice_stage(course_type)
        media_stages = (2, 3) if course_type in ("math", "legacy", "reading") else (2, 3, 4)
        deck = practice_deck(implementation, db, row)[0] if no == practice_no else deck_for(session_course(db, row)["lesson"], no, course_type) if no in media_stages else []
        if not deck:
            raise HTTPException(409, "这个环节没有可翻页的内容")
        cur = state(db, row)["deck"]["index"]
        target = b.index if b.index is not None else cur + b.delta
        target = max(0, min(int(target), len(deck) - 1))
        if no == practice_no:
            from changying.services.weekend_answers import open_practice_question, practice_release
            # Opening a question keeps the answers that were already released; a
            # later board move never wins over a publish, so going back cannot
            # erase answers the class has already seen.
            open_practice_question(implementation, db, row, deck[target]['question'])
            count = practice_release(implementation, db, row)[1]
            target = practice_cursor(count, target)
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
        practice_no = practice_stage(session_course(db, row)["courseType"])
        if row.current_stage != practice_no:
            raise HTTPException(409, "请在随堂练习环节选择题目")
        deck, count, _, total = practice_deck(implementation, db, row)
        if not 1 <= b.question <= total:
            raise HTTPException(400, "请选择有效题目")
        from changying.services.weekend_answers import open_practice_question
        open_practice_question(implementation, db, row, b.question)
        page = next(i for i, item in enumerate(deck) if item['question'] == b.question)
        value = practice_cursor(count, page)
        cursor = db.execute(select(slide_t.c.id).where(slide_t.c.session_id == sid)).first()
        if cursor:
            db.execute(update(slide_t).where(slide_t.c.id == cursor.id).values(stage_no=practice_no, idx=value))
        else:
            db.execute(insert(slide_t).values(school_id=row.school_id, session_id=sid, stage_no=practice_no, idx=value))
        db.commit()
        return state(db, mine(db, u, sid))

    @router.post("/teacher/weekend/sessions/{sid}/publish-answers")
    def publish_answers(sid: int, b: PublishAnswerBody, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "teacher")
        row = mine(db, u, sid)
        db.execute(select(sessions.c.id).where(sessions.c.id == sid).with_for_update()).first()
        running(row)
        practice_no = practice_stage(session_course(db, row)["courseType"])
        if int(row.current_stage) != practice_no:
            raise HTTPException(409, "请在随堂练习环节公布答案")
        deck, count, _, total = practice_deck(implementation, db, row)
        if not 1 <= b.question <= total:
            raise HTTPException(400, "请选择有效题目")
        if b.question > count+1:
            raise HTTPException(409, "请按题目顺序公布答案")
        if b.question == count+1:
            # The request carries the ordinal: retries cannot release another question.
            from changying.services.weekend_answers import open_practice_question
            open_practice_question(implementation, db, row, b.question)
            count += 1
            page = next(i for i, item in enumerate(deck) if item["question"] == b.question)
            cursor = db.execute(select(slide_t.c.id).where(slide_t.c.session_id == sid)).first()
            value = practice_cursor(count, page)
            if cursor:
                db.execute(update(slide_t).where(slide_t.c.id == cursor.id).values(stage_no=practice_no, idx=value))
            else:
                db.execute(insert(slide_t).values(school_id=row.school_id, session_id=sid, stage_no=practice_no, idx=value))
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


