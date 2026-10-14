"""周末课 备课与学期进度 (阶段 2).

teacher  GET  /teacher/weekend/schedule?subject=            18 lessons of the term: school week/unit, lesson plan status
         PUT  /teacher/weekend/schedule                     {subject, rows:[{lessonNo, schoolWeek, schoolUnit, plannedDate, note}]}
         POST /teacher/weekend/schedule/shift               {subject, fromLessonNo, weeks} the school postponed: move everything from here on
         POST /teacher/weekend/schedule/parse               {subject, text} AI reads a pasted progress table into rows (nothing is saved)
         POST /teacher/weekend/lessons/draft                {subject, lessonNo, force?} AI drafts the whole lesson (plan, slides, examples, questions)
         PUT  /teacher/weekend/lessons/{id}                 edit the plan text
         GET  /teacher/weekend/lessons/{id}/questions       approved + draft questions
         POST /teacher/weekend/lessons/{id}/questions       {approve:[ids], remove:[ids]}
         GET  /teacher/weekend/next                         what to prepare next, per subject, with the class's weak knowledge points
page     /v1/weekend-plan

AI output is always a DRAFT: the lesson stays unpublished, drafted questions are inactive until the teacher approves them.
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy import Column, DateTime, Integer, String, Table, UniqueConstraint, delete, func, insert, select, update

from changying.web.weekend_pages import plan_page_html

AI_FEATURE = "weekend_lesson_draft"
SUBJECTS = ("语文", "数学")
LESSONS = 18
LEVELS = ("C", "C", "B", "B", "A", "A")


class RowBody(BaseModel):
    lessonNo: int
    schoolWeek: int | None = None
    schoolUnit: str = ""
    plannedDate: str = ""
    note: str = ""


class ScheduleBody(BaseModel):
    subject: str
    rows: list[RowBody]


class ShiftBody(BaseModel):
    subject: str
    fromLessonNo: int
    weeks: int


class ParseBody(BaseModel):
    subject: str
    text: str


class DraftBody(BaseModel):
    subject: str
    lessonNo: int
    force: bool = False


class LessonEditBody(BaseModel):
    title: str = ""
    coreTarget: str = ""
    teacherPlan: str = ""
    closureTraining: str = ""
    examples: list[str] = []
    ppt: list[str] = []


class ApproveBody(BaseModel):
    approve: list[int] = []
    remove: list[int] = []


def register_plan_tables(implementation: Any) -> Table:
    md = implementation.Base.metadata
    t = md.tables.get("weekend_schedule")
    if t is None:
        t = Table(
            "weekend_schedule", md,
            Column("id", Integer, primary_key=True),
            Column("school_id", Integer, nullable=False, index=True),
            Column("teacher_id", Integer, nullable=False, index=True),
            Column("subject", String(20), nullable=False),
            Column("lesson_no", Integer, nullable=False),
            Column("school_week", Integer, nullable=True),
            Column("school_unit", String(120), nullable=False, default=""),
            Column("planned_date", String(10), nullable=False, default=""),
            Column("note", String(200), nullable=False, default=""),
            Column("updated_at", DateTime, nullable=False, default=datetime.utcnow),
            UniqueConstraint("teacher_id", "subject", "lesson_no", name="uq_weekend_schedule"),
        )
    return t


def _lines(items: Any, limit: int = 12, size: int = 300) -> list[str]:
    out = []
    for x in items if isinstance(items, list) else []:
        text = " ".join((json.dumps(x, ensure_ascii=False) if isinstance(x, (dict, list)) else str(x or "")).split())[:size]
        if text:
            out.append(text)
    return out[:limit]


def _valid_date(text: str) -> str:
    try:
        return date.fromisoformat(text).isoformat() if text else ""
    except ValueError:
        return ""


def install_weekend_plan(implementation: Any) -> APIRouter:
    app = implementation.app
    if getattr(app.state, "weekend_plan_installed", False):
        return app.state.weekend_plan_router
    from changying.web.weekend_views import register_weekend_tables

    sessions = register_weekend_tables(implementation)["sessions"]
    sched = register_plan_tables(implementation)
    Lesson, TQ, Program = implementation.TeachingLesson, implementation.TeachingQuestion, implementation.TeachingProgram
    User, ClassStudent, SchoolClass = implementation.User, implementation.ClassStudent, implementation.SchoolClass
    Wrong = implementation.WrongQuestionRecord
    current_user, get_db, need = implementation.current_user, implementation.get_db, implementation.need
    router = APIRouter()

    def check_subject(subject: str) -> None:
        if subject not in SUBJECTS:
            raise HTTPException(400, "学科需要是：语文 或 数学")

    def program(db: Any, school_id: int) -> Any:
        p = db.scalar(select(Program).where(Program.school_id == school_id).order_by(Program.active.desc(), Program.id.desc()).limit(1))
        if p is None:
            raise HTTPException(400, "学校还没有教学方案，请先在“定制教学”里建立")
        return p

    def class_students(db: Any, u: Any) -> list[int]:
        return [int(x) for x in db.scalars(
            select(User.id).join(ClassStudent, ClassStudent.student_id == User.id).join(SchoolClass, SchoolClass.id == ClassStudent.class_id)
            .where(SchoolClass.teacher_id == u.id, SchoolClass.school_id == u.school_id)).all()]

    def weak_knowledge(db: Any, u: Any, subject: str, limit: int = 3) -> list[dict[str, Any]]:
        ids = class_students(db, u)
        if not ids:
            return []
        rows = db.execute(select(Wrong.knowledge, func.count(Wrong.id)).where(Wrong.school_id == u.school_id, Wrong.student_id.in_(ids), Wrong.status == "active",
                                                                              Wrong.subject == subject, Wrong.knowledge != "").group_by(Wrong.knowledge)
                          .order_by(func.count(Wrong.id).desc()).limit(limit)).all()
        return [{"knowledge": k, "count": int(c)} for k, c in rows]

    def my_lesson(db: Any, u: Any, lid: int) -> Any:
        row = db.get(Lesson, lid)
        if row is None or int(row.school_id) != int(u.school_id) or row.subject not in SUBJECTS:
            raise HTTPException(404, "没有找到这节课")
        return row

    def lesson_status(db: Any, u: Any, lesson: Any) -> dict[str, Any]:
        approved = db.scalar(select(func.count()).select_from(TQ).where(TQ.lesson_id == lesson.id, TQ.active.is_(True))) or 0
        draft = db.scalar(select(func.count()).select_from(TQ).where(TQ.lesson_id == lesson.id, TQ.active.is_(False))) or 0
        ran = db.scalar(select(func.count()).select_from(sessions).where(sessions.c.lesson_id == lesson.id, sessions.c.teacher_id == u.id, sessions.c.status != "planned")) or 0
        return {"lessonId": lesson.id, "title": lesson.title, "hasPlan": bool((lesson.teacher_plan or "").strip() or (lesson.core_target or "").strip()),
                "approvedQuestions": int(approved), "draftQuestions": int(draft), "taught": bool(ran)}

    @router.get("/v1/weekend-plan", include_in_schema=False)
    def page():
        return HTMLResponse(plan_page_html(), headers={"Cache-Control": "no-store"})

    @router.get("/teacher/weekend/schedule")
    def get_schedule(subject: str = "数学", u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "teacher")
        check_subject(subject)
        rows = {int(r.lesson_no): r for r in db.execute(select(sched).where(sched.c.teacher_id == u.id, sched.c.subject == subject)).all()}
        lessons = {int(l.lesson_no): l for l in db.scalars(select(Lesson).where(Lesson.school_id == u.school_id, Lesson.subject == subject)).all()}
        out = []
        for n in range(1, LESSONS + 1):
            r, l = rows.get(n), lessons.get(n)
            item = {"lessonNo": n, "schoolWeek": r.school_week if r else None, "schoolUnit": r.school_unit if r else "", "plannedDate": r.planned_date if r else "", "note": r.note if r else ""}
            item.update(lesson_status(db, u, l) if l else {"lessonId": None, "title": "", "hasPlan": False, "approvedQuestions": 0, "draftQuestions": 0, "taught": False})
            out.append(item)
        return {"subject": subject, "items": out}

    @router.put("/teacher/weekend/schedule")
    def put_schedule(b: ScheduleBody, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "teacher")
        check_subject(b.subject)
        now = datetime.utcnow()
        for r in b.rows:
            if not 1 <= r.lessonNo <= LESSONS:
                raise HTTPException(400, f"课次需要在 1–{LESSONS} 之间")
            if r.schoolWeek is not None and not 1 <= r.schoolWeek <= 30:
                raise HTTPException(400, "学校周次需要在 1–30 之间")
            vals = dict(school_week=r.schoolWeek, school_unit=r.schoolUnit.strip()[:120], planned_date=_valid_date(r.plannedDate.strip()), note=r.note.strip()[:200], updated_at=now)
            ex = db.execute(select(sched.c.id).where(sched.c.teacher_id == u.id, sched.c.subject == b.subject, sched.c.lesson_no == r.lessonNo)).first()
            if ex:
                db.execute(update(sched).where(sched.c.id == ex.id).values(**vals))
            else:
                db.execute(insert(sched).values(school_id=u.school_id, teacher_id=u.id, subject=b.subject, lesson_no=r.lessonNo, **vals))
        db.commit()
        return get_schedule(b.subject, u, db)

    @router.post("/teacher/weekend/schedule/shift")
    def shift(b: ShiftBody, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "teacher")
        check_subject(b.subject)
        if not -8 <= b.weeks <= 8 or b.weeks == 0:
            raise HTTPException(400, "顺延周数需要在 -8 到 8 之间（不含 0）")
        moved = 0
        for r in db.execute(select(sched).where(sched.c.teacher_id == u.id, sched.c.subject == b.subject, sched.c.lesson_no >= b.fromLessonNo)).all():
            vals: dict[str, Any] = {"updated_at": datetime.utcnow()}
            if r.school_week is not None:
                vals["school_week"] = max(1, min(30, int(r.school_week) + b.weeks))
            if r.planned_date:
                vals["planned_date"] = (date.fromisoformat(r.planned_date) + timedelta(days=7 * b.weeks)).isoformat()
            if len(vals) > 1:
                db.execute(update(sched).where(sched.c.id == r.id).values(**vals))
                moved += 1
        db.commit()
        return {"moved": moved}

    @router.post("/teacher/weekend/schedule/parse")
    def parse(b: ParseBody, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "teacher")
        check_subject(b.subject)
        text = b.text.strip()[:4000]
        if not text:
            raise HTTPException(400, "请先粘贴学校的进度安排")
        prompt = (f"下面是学校本学期{b.subject}的教学进度安排（可能是表格文字）。请按时间顺序整理成最多 {LESSONS} 条，每条是周末课补课的参考进度。\n{text}\n"
                  '只输出 JSON：{"rows":[{"schoolWeek":数字或null,"schoolUnit":"单元或内容(30字内)"}]}')
        data = implementation._ai_json(implementation._ai_call(db, u, AI_FEATURE, prompt, timeout=45))
        rows = data.get("rows") if isinstance(data, dict) else None
        if not isinstance(rows, list) or not rows:
            raise HTTPException(502, "AI 没能读懂这份进度，请再试一次，或手动填写")
        out = []
        for i, r in enumerate(rows[:LESSONS], start=1):
            try:
                week = int(r.get("schoolWeek")) if r.get("schoolWeek") is not None else None
            except (TypeError, ValueError):
                week = None
            out.append({"lessonNo": i, "schoolWeek": week if week and 1 <= week <= 30 else None, "schoolUnit": str(r.get("schoolUnit") or "")[:120]})
        return {"rows": out, "message": "这是 AI 的识别结果，请核对、修改后再保存。"}

    @router.post("/teacher/weekend/lessons/draft")
    def draft(b: DraftBody, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "teacher")
        check_subject(b.subject)
        if not 1 <= b.lessonNo <= LESSONS:
            raise HTTPException(400, f"课次需要在 1–{LESSONS} 之间")
        p = program(db, int(u.school_id))
        lesson = db.scalar(select(Lesson).where(Lesson.school_id == u.school_id, Lesson.program_id == p.id, Lesson.subject == b.subject, Lesson.lesson_no == b.lessonNo))
        if lesson is not None and not b.force and ((lesson.teacher_plan or "").strip() or (lesson.core_target or "").strip()):
            raise HTTPException(409, "这节课已经有教案了。要让 AI 重写请选择覆盖。")
        row = db.execute(select(sched).where(sched.c.teacher_id == u.id, sched.c.subject == b.subject, sched.c.lesson_no == b.lessonNo)).first()
        weak = weak_knowledge(db, u, b.subject)
        textbook = p.math_textbook if b.subject == "数学" else p.chinese_textbook
        prompt = (
            f"你是小学{p.grade}年级{b.subject}周末补课老师（{textbook}），一次课 2 小时、约 3 名学生、基础参差不齐。请为第 {b.lessonNo} 次课写备课草稿。\n"
            f"学校本周进度：{(row.school_unit if row and row.school_unit else '未提供')}（学校第 {row.school_week if row and row.school_week else '?'} 周）。\n"
            f"班里近期错得最多的知识点：{'、'.join(w['knowledge'] for w in weak) or '暂无'}。\n"
            "要求：知识点讲解由浅入深，例题 2-3 道，随堂选择题 4-6 道（3 个选项，只有一个正确，难度由易到难），内容不超纲。"
            '只输出 JSON：{"title":"课题","coreTarget":"本节目标","teacherPlan":"教学流程(200字内)","ppt":["每页标题，6-9 页"],'
            '"examples":["例题和解答，2-3 条"],"closureTraining":"课后练习安排",'
            '"questions":[{"stem":"题目","options":["A","B","C"],"correctIndex":0,"explanation":"解析","knowledge":"知识点名"}]}'
        )
        data = implementation._ai_json(implementation._ai_call(db, u, AI_FEATURE, prompt, timeout=90))
        if not isinstance(data, dict) or not str(data.get("title") or "").strip() or not _lines(data.get("ppt")):
            raise HTTPException(502, "AI 这次没有给出可用的备课草稿，请再试一次")
        qs = []
        for q in data.get("questions") if isinstance(data.get("questions"), list) else []:
            try:
                opts = [str(x).strip() for x in q.get("options")][:4]
                ci = int(q.get("correctIndex"))
            except (TypeError, ValueError, AttributeError):
                continue
            if str(q.get("stem") or "").strip() and len(opts) >= 2 and all(opts) and 0 <= ci < len(opts):
                qs.append({"stem": str(q["stem"]).strip()[:300], "options": opts, "ci": ci, "exp": str(q.get("explanation") or "")[:300], "kp": str(q.get("knowledge") or "")[:160]})
        if not qs:
            raise HTTPException(502, "AI 没有给出合格的习题，请再试一次")
        now = datetime.utcnow()
        fields = dict(title=str(data["title"]).strip()[:180], core_target=str(data.get("coreTarget") or "")[:1000], teacher_plan=str(data.get("teacherPlan") or "")[:3000],
                      ppt_json=json.dumps(_lines(data.get("ppt")), ensure_ascii=False), examples_json=json.dumps(_lines(data.get("examples")), ensure_ascii=False),
                      closure_training=str(data.get("closureTraining") or "")[:1000], unit=(row.school_unit if row and row.school_unit else "")[:120] or "待配置单元",
                      published=False, updated_at=now)
        if lesson is None:
            lesson = Lesson(school_id=u.school_id, program_id=p.id, subject=b.subject, lesson_no=b.lessonNo, duration_min=120, **fields)
            db.add(lesson)
            db.flush()
        else:
            for k, v in fields.items():
                setattr(lesson, k, v)
            db.execute(delete(TQ).where(TQ.lesson_id == lesson.id, TQ.active.is_(False)))      # replace the earlier un-approved draft
        for i, q in enumerate(qs[:6]):
            db.add(TQ(school_id=u.school_id, program_id=p.id, lesson_id=lesson.id, stage="lesson", subject=b.subject, level=LEVELS[i], knowledge=q["kp"], stem=q["stem"],
                      options_json=json.dumps(q["options"], ensure_ascii=False), correct_index=q["ci"], explanation=q["exp"], active=False))
        db.commit()
        return {"lessonId": lesson.id, "status": lesson_status(db, u, lesson), "weakKnowledge": weak}

    @router.put("/teacher/weekend/lessons/{lid}")
    def edit_lesson(lid: int, b: LessonEditBody, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "teacher")
        lesson = my_lesson(db, u, lid)
        if b.title.strip():
            lesson.title = b.title.strip()[:180]
        lesson.core_target, lesson.teacher_plan, lesson.closure_training = b.coreTarget[:1000], b.teacherPlan[:3000], b.closureTraining[:1000]
        lesson.examples_json, lesson.ppt_json = json.dumps(_lines(b.examples), ensure_ascii=False), json.dumps(_lines(b.ppt), ensure_ascii=False)
        lesson.updated_at = datetime.utcnow()
        db.commit()
        return lesson_status(db, u, lesson)

    @router.get("/teacher/weekend/lessons/{lid}")
    def get_lesson(lid: int, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "teacher")
        lesson = my_lesson(db, u, lid)
        def lst(raw: str) -> list[str]:
            try:
                return _lines(json.loads(raw or "[]"))
            except Exception:  # noqa: BLE001
                return []
        return {"id": lesson.id, "title": lesson.title, "coreTarget": lesson.core_target, "teacherPlan": lesson.teacher_plan, "closureTraining": lesson.closure_training,
                "examples": lst(lesson.examples_json), "ppt": lst(lesson.ppt_json)}

    @router.get("/teacher/weekend/lessons/{lid}/questions")
    def lesson_questions(lid: int, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "teacher")
        lesson = my_lesson(db, u, lid)
        out = []
        for q in db.scalars(select(TQ).where(TQ.lesson_id == lesson.id).order_by(TQ.id)).all():
            try:
                opts = json.loads(q.options_json or "[]")
            except Exception:  # noqa: BLE001
                opts = []
            out.append({"id": q.id, "stem": q.stem, "options": opts, "correctIndex": q.correct_index, "explanation": q.explanation, "knowledge": q.knowledge, "active": bool(q.active)})
        return {"items": out}

    @router.post("/teacher/weekend/lessons/{lid}/questions")
    def decide_questions(lid: int, b: ApproveBody, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "teacher")
        lesson = my_lesson(db, u, lid)
        if b.approve:
            db.execute(update(TQ).where(TQ.lesson_id == lesson.id, TQ.id.in_(b.approve)).values(active=True))
        if b.remove:
            db.execute(delete(TQ).where(TQ.lesson_id == lesson.id, TQ.id.in_(b.remove), TQ.active.is_(False)))   # an approved question is never deleted here
        db.commit()
        return lesson_status(db, u, lesson)

    @router.get("/teacher/weekend/next")
    def next_up(u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "teacher")
        out = []
        for subject in SUBJECTS:
            lessons = {int(l.lesson_no): l for l in db.scalars(select(Lesson).where(Lesson.school_id == u.school_id, Lesson.subject == subject)).all()}
            rows = {int(r.lesson_no): r for r in db.execute(select(sched).where(sched.c.teacher_id == u.id, sched.c.subject == subject)).all()}
            nxt = None
            for n in range(1, LESSONS + 1):
                st = lesson_status(db, u, lessons[n]) if n in lessons else None
                if not (st and st["taught"]):
                    nxt = n
                    break
            if nxt is None:
                out.append({"subject": subject, "done": True})
                continue
            r, l = rows.get(nxt), lessons.get(nxt)
            st = lesson_status(db, u, l) if l else {"lessonId": None, "title": "", "hasPlan": False, "approvedQuestions": 0, "draftQuestions": 0, "taught": False}
            tips = []
            if not st["hasPlan"]:
                tips.append("还没有教案：可以用 AI 备课草稿")
            if st["approvedQuestions"] == 0:
                tips.append("还没有审核通过的习题")
            out.append({"subject": subject, "lessonNo": nxt, "schoolWeek": r.school_week if r else None, "schoolUnit": r.school_unit if r else "", "plannedDate": r.planned_date if r else "",
                        **st, "weakKnowledge": weak_knowledge(db, u, subject), "tips": tips})
        return {"items": out}

    app.include_router(router)
    app.state.weekend_plan_installed = True
    app.state.weekend_plan_router = router
    return router


__all__ = ["install_weekend_plan", "register_plan_tables"]
