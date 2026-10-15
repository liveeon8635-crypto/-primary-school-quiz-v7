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

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from sqlalchemy import Column, DateTime, Integer, String, Table, UniqueConstraint, delete, func, insert, select, update

from changying.services.lesson_import import MAX_FILE_BYTES, MAX_TEXT_CHARS, SUPPORTED, extract
from changying.web.weekend_pages import plan_page_html
from changying.services.lesson_written import (literal_written_questions, valid_written_questions,
    replace_written_drafts, written_templates, template_meta)

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
    onlyQuestions: bool = False      # keep the existing plan, only add draft questions


class LessonEditBody(BaseModel):
    title: str = ""
    coreTarget: str = ""
    teacherPlan: str = Field(default="", max_length=MAX_TEXT_CHARS)
    sourceText: str | None = Field(default=None, max_length=MAX_TEXT_CHARS)
    closureTraining: str = Field(default="", max_length=MAX_TEXT_CHARS)
    examples: list[str] = []
    ppt: list[str] = []


class WrittenDraftBody(BaseModel):
    stem: str = Field(min_length=1, max_length=20000)
    reference: str = Field(default="", max_length=4000)
    type: str = "short_answer"
    hints: list[str] = Field(default_factory=list, max_length=3)


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


def _content_lines(items: Any) -> list[str]:
    """Preserve imported/read-back teaching content; reject over-limit data instead of clipping it."""
    out = [json.dumps(x, ensure_ascii=False) if isinstance(x, (dict, list)) else str(x or "")
           for x in items if str(x or "").strip()] if isinstance(items, list) else []
    if sum(len(x) for x in out) > MAX_TEXT_CHARS:
        raise HTTPException(400, "内容超过20万字，请拆分后保存；没有截断保存")
    return out


def _homework_from_source(text: str, fallback: str) -> str:
    """A literal homework section wins over the model's abbreviated version."""
    heading = re.compile(r"(?m)^[ \t]*(?:[一二三四五六七八九十0-9]+[.．、][ \t]*)?(?:课后练习|课后作业|家庭作业|课后训练|作业)(?:[：:][ \t]*|[ \t]+|(?=\n|$|《))")
    matches = list(heading.finditer(text))
    return text[matches[-1].start():].strip() if matches else fallback


PLACEHOLDER_PREFIX = "请依据学校"      # the school's seeded template lessons carry this text: they are blank, not a plan


def has_real_plan(lesson: Any) -> bool:
    """A lesson counts as prepared only when the teacher (or AI) wrote real content: a real target or examples.
    The seeded template (generic timeline + "请依据学校…填写") does not count."""
    target = (lesson.core_target or "").strip()
    if target and not target.startswith(PLACEHOLDER_PREFIX):
        return True
    try:
        return bool(_lines(json.loads(lesson.examples_json or "[]")))
    except Exception:  # noqa: BLE001
        return False


def _valid_questions(raw: Any) -> list[dict[str, Any]]:
    qs = []
    for q in raw if isinstance(raw, list) else []:
        try:
            opts = [str(x).strip() for x in q.get("options")][:4]
            ci = int(q.get("correctIndex"))
        except (TypeError, ValueError, AttributeError):
            continue
        if str(q.get("stem") or "").strip() and len(opts) >= 2 and all(opts) and 0 <= ci < len(opts):
            qs.append({"stem": str(q["stem"]).strip()[:300], "options": opts, "ci": ci, "exp": str(q.get("explanation") or "")[:300], "kp": str(q.get("knowledge") or "")[:160]})
    return qs


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
    from changying.web.weekend_written import register_written_tables
    written = register_written_tables(implementation)["questions"]
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
        templates = written_templates(db, written, u.school_id, u.id, lesson.id)
        written_approved = sum(bool(template_meta(q).get("approved")) for q in templates)
        approved += written_approved
        draft += len(templates) - written_approved
        ran = db.scalar(select(func.count()).select_from(sessions).where(sessions.c.lesson_id == lesson.id, sessions.c.teacher_id == u.id, sessions.c.status != "planned")) or 0
        return {"lessonId": lesson.id, "title": lesson.title, "hasPlan": has_real_plan(lesson),
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
        if b.onlyQuestions and lesson is None:
            raise HTTPException(404, "这节课还没有教案，请先用 AI 备课草稿")
        if lesson is not None and not b.onlyQuestions and not b.force and has_real_plan(lesson):
            raise HTTPException(409, "这节课已经有教案了。要让 AI 重写请选择覆盖。")
        row = db.execute(select(sched).where(sched.c.teacher_id == u.id, sched.c.subject == b.subject, sched.c.lesson_no == b.lessonNo)).first()
        weak = weak_knowledge(db, u, b.subject)
        textbook = p.math_textbook if b.subject == "数学" else p.chinese_textbook
        prompt = (
            f"你是小学{p.grade}年级{b.subject}周末补课老师（{textbook}），一次课 2 小时、约 3 名学生、基础参差不齐。请为第 {b.lessonNo} 次课写备课草稿。\n"
            f"学校本周进度：{(row.school_unit if row and row.school_unit else '未提供')}（学校第 {row.school_week if row and row.school_week else '?'} 周）。\n"
            f"班里近期错得最多的知识点：{'、'.join(w['knowledge'] for w in weak) or '暂无'}。\n"
            + (f"这节课已有教案：课题《{lesson.title}》，目标：{lesson.core_target}。\n原教案与阅读材料：{lesson.reading_plan or lesson.teacher_plan}\n请只出习题，其余字段可留空。\n" if b.onlyQuestions and lesson is not None else "") +
            "要求：知识点讲解由浅入深，例题 2-3 道，随堂习题按教学内容选择题型：选择、填最终答案、阅读简答、扩写/缩写与作文。语文阅读必须有基于所给文章的简答或写作题，不能全部改成选择题；数学应含计算或过程题。选择题放questions，非选择题放writtenQuestions，合计4-6道，内容不超纲。"
            '只输出 JSON：{"title":"课题","coreTarget":"本节目标","teacherPlan":"教学流程(200字内)","ppt":["每页标题，6-9 页"],'
            '"examples":["例题和解答，2-3 条"],"closureTraining":"课后练习安排",'
            '"questions":[{"stem":"题目","options":["A","B","C"],"correctIndex":0,"explanation":"解析","knowledge":"知识点名"}],"writtenQuestions":[{"type":"short_answer或final_answer或composition","material":"本题所需完整阅读材料，不含答案","stem":"题目","reference":"参考答案和评分要点，仅老师可见","hints":["方向","第一步","完整思路"]}]}'
        )
        data = implementation._ai_json(implementation._ai_call(db, u, AI_FEATURE, prompt, timeout=90))
        if not isinstance(data, dict) or (not b.onlyQuestions and (not str(data.get("title") or "").strip() or not _lines(data.get("ppt")))):
            raise HTTPException(502, "AI 这次没有给出可用的备课草稿，请再试一次")
        qs = _valid_questions(data.get("questions"))
        wqs = valid_written_questions(data.get("writtenQuestions"))
        if b.subject == "语文" and not wqs:
            wqs = valid_written_questions(literal_written_questions(lesson.reading_plan or "")) if b.onlyQuestions and lesson is not None else []
            if not wqs:
                raise HTTPException(502, "AI 只返回了选择题，未满足简答／写作要求；原教案和已有习题未改变，请重试")
        if not qs and not wqs:
            raise HTTPException(502, "AI 没有给出合格的习题，请再试一次")
        now = datetime.utcnow()
        fields = dict(title=str(data.get("title") or "").strip()[:180], core_target=str(data.get("coreTarget") or "")[:1000], teacher_plan=str(data.get("teacherPlan") or "")[:3000],
                      ppt_json=json.dumps(_lines(data.get("ppt")), ensure_ascii=False), examples_json=json.dumps(_lines(data.get("examples")), ensure_ascii=False),
                      closure_training=str(data.get("closureTraining") or "")[:1000], unit=(row.school_unit if row and row.school_unit else "")[:120] or "待配置单元",
                      published=False, updated_at=now)
        if b.onlyQuestions:
            db.execute(delete(TQ).where(TQ.lesson_id == lesson.id, TQ.active.is_(False)))
        elif lesson is None:
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
        replace_written_drafts(db, written, u.school_id, u.id, lesson.id, wqs)
        db.commit()
        return {"lessonId": lesson.id, "status": lesson_status(db, u, lesson), "weakKnowledge": weak}

    @router.post("/teacher/weekend/lessons/import")
    async def import_lesson(subject: str = Form(...), lessonNo: int = Form(...), force: str = Form("0"), text: str = Form(""), file: UploadFile | None = File(None),
                            u: Any = Depends(current_user), db: Any = Depends(get_db)):
        """Teacher uploads their own lesson plan (.docx/.pptx/.pdf/.txt) or pastes the text; AI only tidies it into the lesson fields (no inventing)."""
        need(u, "teacher")
        check_subject(subject)
        if not 1 <= lessonNo <= LESSONS:
            raise HTTPException(400, f"课次需要在 1–{LESSONS} 之间")
        extracted: dict[str, Any] = {"text": text.strip(), "slides": []}
        raw = b""
        ext = ""
        if file is not None and file.filename:
            ext = ("." + file.filename.rsplit(".", 1)[-1]).lower() if "." in file.filename else ""
            if ext not in SUPPORTED:
                raise HTTPException(400, "支持的文件：" + "、".join(SUPPORTED))
            raw = await file.read(MAX_FILE_BYTES + 1)
            if len(raw) > MAX_FILE_BYTES:
                raise HTTPException(413, "文件不能超过 10MB")
            if ext in (".docx", ".pptx", ".pdf"):
                implementation._validate_office_upload(ext, raw)
            try:
                extracted = extract(ext, raw)
            except HTTPException:
                raise
            except ValueError as exc:
                if "20万字" in str(exc):
                    raise HTTPException(413, str(exc))
                raise HTTPException(400, "文件内容超出支持范围或无法解析，请拆分后重新导入")
            except Exception:  # noqa: BLE001
                raise HTTPException(400, "没能读出这个文件的文字，请换一个文件，或把教案文字粘贴进来")
        if len(extracted["text"]) > MAX_TEXT_CHARS:
            raise HTTPException(413, "教案文字超过20万字，请拆分后导入；未截断保存")
        if len(extracted["text"]) < 20:
            raise HTTPException(400, "没有读到足够的文字（扫描版 PDF 和纯图片暂不支持），请换文件或直接粘贴文字")
        p = program(db, int(u.school_id))
        lesson = db.scalar(select(Lesson).where(Lesson.school_id == u.school_id, Lesson.program_id == p.id, Lesson.subject == subject, Lesson.lesson_no == lessonNo))
        if lesson is not None and force != "1" and has_real_plan(lesson):
            raise HTTPException(409, "这节课已经有教案了。导入会覆盖教案文字（已通过的习题保留）。")
        prompt = (
            f"下面是一位小学{p.grade}年级{subject}老师自己写的周末课教案内容。请只整理、归类里面已有的内容，不要编造新内容；文档里没有的字段留空。\n"
            f"---教案内容开始---\n{extracted['text']}\n---教案内容结束---\n"
            '只输出 JSON：{"title":"课题","coreTarget":"本节目标","teacherPlan":"教学流程(300字内)","ppt":["每页或每个板块的标题"],'
            '"examples":["文档里的例题和解答，原文照录"],"closureTraining":"课后练习",'
            '"questions":[{"stem":"文档里已有的选择题","options":["A","B","C"],"correctIndex":0,"explanation":"解析","knowledge":"知识点名"}],"writtenQuestions":[{"type":"short_answer或final_answer或composition","material":"对应完整阅读文章，不含教师答案","stem":"原有题目，不得改题型或漏题","reference":"原文对应参考答案及评分要点","hints":[]}]}'
            "（questions 只放原有选择题，writtenQuestions放全部原有简答、填空、复述、写作和挑战题，不要编造新题。阅读文章和非选择题不可省略；原文由系统完整保存。closureTraining 必须包含全部课后题，不能只列前几题。）"
        )
        data = implementation._ai_json(implementation._ai_call(db, u, AI_FEATURE, prompt, timeout=90))
        if not isinstance(data, dict) or not (str(data.get("title") or "").strip() or str(data.get("coreTarget") or "").strip() or _lines(data.get("examples"))):
            raise HTTPException(502, "AI 没能整理出教案，请再试一次，或在“审改”里手动填写")
        slides = extracted["slides"] or _content_lines(data.get("ppt"))
        row = db.execute(select(sched).where(sched.c.teacher_id == u.id, sched.c.subject == subject, sched.c.lesson_no == lessonNo)).first()
        now = datetime.utcnow()
        fields = dict(title=(str(data.get("title") or "").strip() or f"{subject}第{lessonNo}课")[:180], core_target=str(data.get("coreTarget") or "")[:1000],
                      teacher_plan=str(data.get("teacherPlan") or ""), reading_plan=extracted["text"], ppt_json=json.dumps(slides, ensure_ascii=False),
                      examples_json=json.dumps(_content_lines(data.get("examples")), ensure_ascii=False),
                      closure_training=_homework_from_source(extracted["text"], str(data.get("closureTraining") or "")),
                      unit=(row.school_unit if row and row.school_unit else "")[:120] or "待配置单元", published=False, updated_at=now)
        if not fields["core_target"].strip() and not _lines(data.get("examples")):
            fields["core_target"] = fields["title"]            # a real (non-placeholder) target, so the lesson counts as prepared
        if lesson is None:
            lesson = Lesson(school_id=u.school_id, program_id=p.id, subject=subject, lesson_no=lessonNo, duration_min=120, **fields)
            db.add(lesson)
            db.flush()
        else:
            for k, v in fields.items():
                setattr(lesson, k, v)
            db.execute(delete(TQ).where(TQ.lesson_id == lesson.id, TQ.active.is_(False)))
        qs = _valid_questions(data.get("questions"))
        wqs = valid_written_questions(data.get("writtenQuestions"))
        literal = literal_written_questions(extracted["text"])
        if literal:
            # Literal paper questions take priority; retain model references only
            # when the original question text matches, never by array position.
            for q in literal:
                question = q["stem"].split("\n")[-1]
                match = next((a for a in wqs if question in a["stem"]), None)
                if match:
                    q["reference"] = match["reference"] or q["reference"]
                    q["hints"] = match["hints"]
            wqs = valid_written_questions(literal)
        replace_written_drafts(db, written, u.school_id, u.id, lesson.id, wqs)
        for i, q in enumerate(qs[:12]):
            db.add(TQ(school_id=u.school_id, program_id=p.id, lesson_id=lesson.id, stage="lesson", subject=subject, level=LEVELS[min(i, len(LEVELS) - 1)], knowledge=q["kp"],
                      stem=q["stem"], options_json=json.dumps(q["options"], ensure_ascii=False), correct_index=q["ci"], explanation=q["exp"], active=False))
        db.commit()
        return {"lessonId": lesson.id, "status": lesson_status(db, u, lesson), "slides": len(slides), "questionsFound": len(qs) + len(wqs), "writtenQuestionsFound": len(wqs),
                "sourceChars": len(extracted["text"]), "message": f"原文 {len(extracted['text'])} 字已完整保留（含阅读材料及非选择题）。已导入：{len(slides)} 页 PPT 内容、{len(qs)} 道选择题、{len(wqs)} 道简答/写作题（草稿，需你审核）。没有习题的话，点“AI 出习题（保留教案）”。"}

    @router.put("/teacher/weekend/lessons/{lid}")
    def edit_lesson(lid: int, b: LessonEditBody, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "teacher")
        lesson = my_lesson(db, u, lid)
        if b.title.strip():
            lesson.title = b.title.strip()[:180]
        lesson.core_target, lesson.teacher_plan, lesson.closure_training = b.coreTarget[:1000], b.teacherPlan, b.closureTraining
        if b.sourceText is not None:
            lesson.reading_plan = b.sourceText
        lesson.examples_json, lesson.ppt_json = json.dumps(_content_lines(b.examples), ensure_ascii=False), json.dumps(_content_lines(b.ppt), ensure_ascii=False)
        lesson.updated_at = datetime.utcnow()
        db.commit()
        return lesson_status(db, u, lesson)

    @router.get("/teacher/weekend/lessons/{lid}")
    def get_lesson(lid: int, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "teacher")
        lesson = my_lesson(db, u, lid)
        def lst(raw: str) -> list[str]:
            try:
                return _content_lines(json.loads(raw or "[]"))
            except (ValueError, TypeError):  # noqa: BLE001
                return []
        return {"id": lesson.id, "title": lesson.title, "coreTarget": lesson.core_target, "teacherPlan": lesson.teacher_plan, "sourceText": lesson.reading_plan or "", "closureTraining": lesson.closure_training,
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

    @router.get("/teacher/weekend/lessons/{lid}/written/questions")
    def lesson_written(lid: int, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "teacher")
        my_lesson(db, u, lid)
        return {"items": [{"id": q.id, "stem": q.stem, "reference": q.reference,
                 **template_meta(q)} for q in written_templates(db, written, u.school_id, u.id, lid)]}

    @router.put("/teacher/weekend/lessons/{lid}/written/questions/{qid}")
    def edit_written(lid: int, qid: int, b: WrittenDraftBody, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "teacher")
        my_lesson(db, u, lid)
        q = next((q for q in written_templates(db, written, u.school_id, u.id, lid) if q.id == qid), None)
        if q is None:
            raise HTTPException(404, "没有找到这道备课题")
        valid = valid_written_questions([b.model_dump()])
        if not valid or (b.hints and not valid[0]["hints"]):
            raise HTTPException(400, "题目不能为空；提示填写时需要完整三级，每级不超过300字")
        v = valid[0]
        # Editing a previously approved template requires another approval;
        # snapshots in existing classrooms remain unchanged.
        db.execute(update(written).where(written.c.id == qid).values(stem=v["stem"], reference=v["reference"],
            hints_json=json.dumps({"approved": False, "type": v["type"], "hints": v["hints"]}, ensure_ascii=False)))
        db.commit()
        return lesson_status(db, u, my_lesson(db, u, lid))

    @router.post("/teacher/weekend/lessons/{lid}/written/questions")
    def decide_written(lid: int, b: ApproveBody, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "teacher")
        lesson = my_lesson(db, u, lid)
        for q in written_templates(db, written, u.school_id, u.id, lid):
            meta = template_meta(q)
            if q.id in b.approve:
                meta["approved"] = True
                db.execute(update(written).where(written.c.id == q.id).values(hints_json=json.dumps(meta, ensure_ascii=False)))
            elif q.id in b.remove and not meta.get("approved"):
                db.execute(delete(written).where(written.c.id == q.id))
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
