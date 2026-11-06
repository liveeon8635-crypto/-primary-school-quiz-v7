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

import hashlib
import json
import logging
import re
from datetime import date, datetime, timedelta
from typing import Any, Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from sqlalchemy import Column, DateTime, Integer, String, Table, UniqueConstraint, delete, func, insert, select, update

from changying.services import lesson_markdown
from changying.services import weekend_question_gen as qg
from changying.services.lesson_import import MAX_FILE_BYTES, MAX_TEXT_CHARS, SUPPORTED, detect_lesson_no, extract
from changying.web.weekend_pages import plan_page_html
from changying.services.lesson_written import (MAX_KNOWLEDGE, lesson_goals, literal_written_questions, suggest_knowledge,
    valid_written_questions, replace_written_drafts, written_templates, template_meta)

AI_FEATURE = "weekend_lesson_draft"
SUBJECTS = ("语文", "数学")
LESSONS = 18
MAX_BATCH_FILES = 18
REMOVED_STAGE = "weekend_removed"
LEVELS = ("C", "C", "B", "B", "A", "A")
# Why a rejected upload was rejected: production only logs a status code otherwise, and a
# teacher's "导入失败，没有提示" report cannot be traced back to a file or a rule.
logger = logging.getLogger("changying.weekend_lesson_import")
OFFICE_REPAIR_HINTS = {
    ".docx": "请用 Word/WPS 打开原文件后「另存为」.docx 再导入（旧版 .doc 需要先另存）。",
    ".pptx": "请用 PowerPoint/WPS 打开原文件后「另存为」.pptx 再导入（旧版 .ppt 需要先另存）。",
    ".pdf": "请确认 PDF 未加密、未损坏（可在浏览器里打开试试），或改用 Word 导入。",
}
# Word formats the server cannot read: python-docx only opens the .docx package.
LEGACY_WORD_EXTENSIONS = {".doc", ".dot", ".docm", ".dotx", ".wps", ".wpt"}
# The structured import maps these aliases and rejects anything else: a silent default
# would turn a written question into a choice one (or the reverse) without anyone noticing.
WRITTEN_TYPE_ALIASES = {
    "short_answer": "short_answer", "简答": "short_answer", "简答题": "short_answer", "问答": "short_answer",
    "final_answer": "final_answer", "最终答案": "final_answer", "填空": "final_answer", "填空题": "final_answer",
    "composition": "composition", "作文": "composition", "写作": "composition", "习作": "composition",
}


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


class PlanQuestionBody(BaseModel):
    """One choice question of a structured lesson plan (no model involved)."""

    stem: str = Field(min_length=1, max_length=300)
    options: list[str] = Field(default_factory=list, max_length=4)
    correctIndex: int | None = None
    explanation: str = Field(default="", max_length=300)
    knowledge: str = Field(default="", max_length=160)


class PlanWrittenBody(BaseModel):
    """One written question (short answer / final answer / composition)."""

    type: str = "short_answer"
    material: str = Field(default="", max_length=20000)
    stem: str = Field(min_length=1, max_length=20000)
    reference: str = Field(default="", max_length=4000)
    hints: list[str] = Field(default_factory=list, max_length=3)


class PlanLessonBody(BaseModel):
    """One lesson of a structured import; the same fields the AI path fills."""

    lessonNo: int = Field(ge=1, le=LESSONS)
    title: str = Field(default="", max_length=180)
    coreTarget: str = Field(default="", max_length=1000)
    teacherPlan: str = Field(default="", max_length=MAX_TEXT_CHARS)
    ppt: list[str] = Field(default_factory=list)
    examples: list[str] = Field(default_factory=list)
    closureTraining: str = Field(default="", max_length=MAX_TEXT_CHARS)
    questions: list[PlanQuestionBody] = Field(default_factory=list, max_length=12)
    writtenQuestions: list[PlanWrittenBody] = Field(default_factory=list, max_length=30)


class StructuredImportBody(BaseModel):
    """Batch envelope for ``import/structured``: deterministic, no model call."""

    schemaVersion: int = 1
    subject: str
    dryRun: bool = False
    onConflict: Literal["ask", "skip", "overwrite"] = "ask"
    items: list[PlanLessonBody] = Field(min_length=1, max_length=LESSONS)


class DraftBody(BaseModel):
    subject: str
    lessonNo: int
    force: bool = False
    onlyQuestions: bool = False      # keep the existing plan, only (re)generate draft questions (12, by quota)


class GenerateBody(BaseModel):
    count: int = 12


class LessonEditBody(BaseModel):
    title: str = ""
    coreTarget: str = ""
    teacherPlan: str = Field(default="", max_length=MAX_TEXT_CHARS)
    sourceText: str | None = Field(default=None, max_length=MAX_TEXT_CHARS)
    closureTraining: str = Field(default="", max_length=MAX_TEXT_CHARS)
    examples: list[str] = []
    ppt: list[str] = []


class WrittenMarkBody(BaseModel):
    knowledge: str = Field(default="", max_length=MAX_KNOWLEDGE)
    afterClass: bool = False


class WrittenDraftBody(BaseModel):
    stem: str = Field(min_length=1, max_length=20000)
    reference: str = Field(default="", max_length=4000)
    type: str = "short_answer"
    hints: list[str] = Field(default_factory=list, max_length=3)


class DeleteLessonBody(BaseModel):
    subject: str
    lessonNo: int
    confirmed: bool = False


class CancelDebugBody(DeleteLessonBody):
    sessionIds: list[int] = Field(default_factory=list, max_length=100)


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
        approved = db.scalar(select(func.count()).select_from(TQ).where(TQ.lesson_id == lesson.id, TQ.stage != REMOVED_STAGE, TQ.active.is_(True))) or 0
        draft = db.scalar(select(func.count()).select_from(TQ).where(TQ.lesson_id == lesson.id, TQ.stage != REMOVED_STAGE, TQ.active.is_(False))) or 0
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

    def lesson_context(lesson: Any) -> dict[str, Any]:
        content = [str(lesson.teacher_plan or "")[:800]] + _lines(lesson.ppt_json)[:9] + _lines(lesson.examples_json)[:4]
        return {"title": lesson.title, "core_target": lesson.core_target, "content": "\n".join(x for x in content if x),
                "material": (lesson.reading_plan or "") if lesson.subject == "语文" else ""}

    def style_examples(db: Any, u: Any, lesson: Any) -> list[str]:
        """The school's approved weekend questions of the same subject, hardest first: style and difficulty reference."""
        rows = db.scalars(select(TQ).where(TQ.school_id == u.school_id, TQ.subject == lesson.subject, TQ.active.is_(True),
                                          TQ.stage != REMOVED_STAGE, TQ.lesson_id != lesson.id).order_by(TQ.level, TQ.id.desc()).limit(4)).all()
        out = []
        for q in rows:
            try:
                opts = json.loads(q.options_json or "[]")
                ans = opts[q.correct_index]
            except Exception:  # noqa: BLE001
                continue
            out.append(f"（{qg.CODE_LEVEL.get(q.level, '中等')}）{q.stem[:120]}｜答案：{str(ans)[:30]}")
        return out[:3]

    def existing_stems(db: Any, u: Any, lesson: Any) -> list[str]:
        """Approved questions of the lesson: new drafts must not repeat them."""
        stems = [q.stem for q in db.scalars(select(TQ).where(TQ.lesson_id == lesson.id, TQ.stage != REMOVED_STAGE, TQ.active.is_(True)))]
        stems += [q.stem.split("\n")[-1] for q in written_templates(db, written, u.school_id, u.id, lesson.id) if template_meta(q).get("approved")]
        return stems

    def generate_questions(db: Any, u: Any, lesson: Any, count: int) -> dict[str, Any]:
        """Questions only, to type and difficulty quotas; maths answers verified; one follow-up asks for what is missing."""
        if count not in qg.COUNTS:
            raise HTTPException(400, "题量只能是 " + "、".join(str(c) for c in qg.COUNTS) + " 道")
        p = program(db, int(u.school_id))
        textbook = p.math_textbook if lesson.subject == "数学" else p.chinese_textbook
        want = qg.quotas(lesson.subject, count)
        ctx, examples, have = lesson_context(lesson), style_examples(db, u, lesson), existing_stems(db, u, lesson)
        weak = [w["knowledge"] for w in weak_knowledge(db, u, lesson.subject)]
        kept: list[dict[str, Any]] = []
        dropped: dict[str, int] = {}
        for attempt in range(2):
            need_now = qg.missing(want, kept) if kept else want
            if not sum(need_now["types"].values()):
                break
            text = qg.prompt(lesson.subject, p.grade, textbook, ctx, need_now, examples, weak, have + [q["stem"] for q in kept])
            try:
                data = implementation._ai_json(implementation._ai_call(db, u, AI_FEATURE, text, timeout=90 if attempt == 0 else 60))
            except HTTPException:
                if attempt == 0:
                    raise
                break                                   # the follow-up is a bonus: keep what the first round gave
            rows = data.get("items") if isinstance(data, dict) else None
            checked = []
            for row in rows if isinstance(rows, list) else []:
                q, why = qg.check(row, lesson.subject)
                if q is None:
                    dropped[why] = dropped.get(why, 0) + 1
                else:
                    checked.append(q)
            kept += qg.select(checked, need_now, have + [q["stem"] for q in kept])
        if not kept:
            raise HTTPException(502, "AI 这次出的题都没通过检查（" + "、".join(f"{k} {v} 道" for k, v in dropped.items()) + "），请再试一次")
        db.execute(delete(TQ).where(TQ.lesson_id == lesson.id, TQ.stage != REMOVED_STAGE, TQ.active.is_(False)))
        for q in kept:
            if q["type"] == "choice":
                note = f"验算：{q['expression']}。" if q.get("expression") else ""
                db.add(TQ(school_id=u.school_id, program_id=lesson.program_id, lesson_id=lesson.id, stage="lesson", subject=lesson.subject,
                          level=qg.LEVEL_CODE[q["level"]], knowledge=q["knowledge"], stem=q["stem"][:300],
                          options_json=json.dumps(q["options"], ensure_ascii=False), correct_index=q["correctIndex"],
                          explanation=(note + q["explanation"])[:600], active=False))
        replace_written_drafts(db, written, u.school_id, u.id, lesson.id,
                               [{"stem": q["stem"], "reference": qg.reference_text(q), "hints": q["hints"], "type": q["type"],
                                 "extra": {"level": q["level"], "verified": q["verified"]}} for q in kept if q["type"] != "choice"])
        db.commit()
        left = qg.missing(want, kept)
        count_of = lambda key, part: {k: sum(1 for q in kept if q[key] == k) for k in want[part]}  # noqa: E731
        return {"lessonId": lesson.id, "status": lesson_status(db, u, lesson), "count": len(kept), "wanted": count,
                "byType": count_of("type", "types"), "byLevel": count_of("level", "levels"),
                "verified": sum(1 for q in kept if q["verified"]), "dropped": dropped, "short": sum(left["types"].values())}

    @router.post("/teacher/weekend/lessons/{lid}/questions/generate")
    def generate(lid: int, b: GenerateBody, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "teacher")
        lesson = my_lesson(db, u, lid)
        if not has_real_plan(lesson):
            raise HTTPException(409, "这节课还没有教案，请先导入教案或用 AI 写教案")
        return generate_questions(db, u, lesson, b.count)

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
        if b.onlyQuestions:
            return generate_questions(db, u, lesson, 12)
        if lesson is not None and not b.force and has_real_plan(lesson):
            raise HTTPException(409, "这节课已经有教案了。要让 AI 重写请选择覆盖。")
        row = db.execute(select(sched).where(sched.c.teacher_id == u.id, sched.c.subject == b.subject, sched.c.lesson_no == b.lessonNo)).first()
        weak = weak_knowledge(db, u, b.subject)
        textbook = p.math_textbook if b.subject == "数学" else p.chinese_textbook
        prompt = (
            f"你是小学{p.grade}年级{b.subject}周末补课老师（{textbook}），一次课 2 小时、约 3 名学生、基础参差不齐。请为第 {b.lessonNo} 次课写备课草稿。\n"
            f"学校本周进度：{(row.school_unit if row and row.school_unit else '未提供')}（学校第 {row.school_week if row and row.school_week else '?'} 周）。\n"
            f"班里近期错得最多的知识点：{'、'.join(w['knowledge'] for w in weak) or '暂无'}。\n"
            "要求：知识点讲解由浅入深，例题 2-3 道，内容不超纲。随堂习题不在这里出：教案保存后会单独按题型和难度出一整套。"
            '只输出 JSON：{"title":"课题","coreTarget":"本节目标","teacherPlan":"教学流程(200字内)","ppt":["完整讲解页：标题＋方法步骤＋示例，每页用\\n换行，6-9页，不能只有标题"],'
            '"examples":["例题和解答，2-3 条"],"closureTraining":"课后练习安排"}'
        )
        data = implementation._ai_json(implementation._ai_call(db, u, AI_FEATURE, prompt, timeout=90))
        if not isinstance(data, dict) or not str(data.get("title") or "").strip() or not _lines(data.get("ppt")):
            raise HTTPException(502, "AI 这次没有给出可用的备课草稿，请再试一次")
        # Questions come from generate_questions; any the model still adds here are kept as drafts.
        qs = _valid_questions(data.get("questions"))
        wqs = valid_written_questions(data.get("writtenQuestions"))
        now = datetime.utcnow()
        fields = dict(title=str(data.get("title") or "").strip()[:180], core_target=str(data.get("coreTarget") or "")[:1000], teacher_plan=str(data.get("teacherPlan") or "")[:3000],
                      ppt_json=json.dumps(_content_lines(data.get("ppt")), ensure_ascii=False), examples_json=json.dumps(_lines(data.get("examples")), ensure_ascii=False),
                      closure_training=str(data.get("closureTraining") or "")[:1000], unit=(row.school_unit if row and row.school_unit else "")[:120] or "待配置单元",
                      published=False, updated_at=now)
        if lesson is None:
            lesson = Lesson(school_id=u.school_id, program_id=p.id, subject=b.subject, lesson_no=b.lessonNo, duration_min=120, **fields)
            db.add(lesson)
            db.flush()
        else:
            for k, v in fields.items():
                setattr(lesson, k, v)
            db.execute(delete(TQ).where(TQ.lesson_id == lesson.id, TQ.stage != REMOVED_STAGE, TQ.active.is_(False)))      # replace the earlier un-approved draft
        for i, q in enumerate(qs[:6]):
            db.add(TQ(school_id=u.school_id, program_id=p.id, lesson_id=lesson.id, stage="lesson", subject=b.subject, level=LEVELS[i], knowledge=q["kp"], stem=q["stem"],
                      options_json=json.dumps(q["options"], ensure_ascii=False), correct_index=q["ci"], explanation=q["exp"], active=False))
        if wqs:
            replace_written_drafts(db, written, u.school_id, u.id, lesson.id, wqs)
        db.commit()
        return {"lessonId": lesson.id, "status": lesson_status(db, u, lesson), "weakKnowledge": weak}

    def _extract_upload(file: UploadFile | None, text: str) -> dict[str, Any]:
        """Validate and extract one uploaded file (or pasted text). Shared by the single and batch import routes."""
        extracted: dict[str, Any] = {"text": text.strip(), "slides": []}
        raw = b""
        ext = ""

        def _reject(status: int, detail: str) -> None:
            """Log why an upload was refused, then raise. The teacher only ever sees the detail."""
            logger.warning(
                "weekend.lesson_import.rejected file=%s ext=%s bytes=%d status=%d detail=%s",
                (file.filename if file is not None else "") or "", ext, len(raw), status, detail,
            )
            raise HTTPException(status, detail)

        if file is not None and file.filename:
            name = file.filename.strip() or "这个文件"
            # Downloads sometimes arrive as "教案.docx " (trailing space) or "教案" without
            # any suffix; read the suffix off the trimmed name instead of trusting it raw.
            ext = ("." + name.rsplit(".", 1)[-1]).strip().lower() if "." in name else ""
            if ext == "":
                _reject(400, f"《{name}》没有扩展名，看不出是什么格式。请用 Word/WPS 打开后「另存为」.docx，"
                             "或另存为 .pdf / .txt 再导入")
            if ext in LEGACY_WORD_EXTENSIONS:
                _reject(400, f"《{name}》是 {ext} 格式，不能直接导入。请用 Word/WPS 打开后「另存为」.docx 再导入")
            if ext not in SUPPORTED:
                _reject(400, f"《{name}》是 {ext} 格式，暂不支持。支持：" + "、".join(SUPPORTED)
                             + "；旧版 Word（.doc/.wps）请先用 Word/WPS 另存为 .docx")
            # This sync route runs extraction, database work and the blocking
            # model request in FastAPI's worker pool, leaving health checks free.
            raw = file.file.read(MAX_FILE_BYTES + 1)
            if len(raw) > MAX_FILE_BYTES:
                _reject(413, "文件不能超过 10MB，请拆分后导入")
            if ext in (".docx", ".pptx", ".pdf"):
                try:
                    implementation._validate_office_upload(ext, raw)
                except HTTPException as exc:
                    _reject(exc.status_code, f"{exc.detail}。{OFFICE_REPAIR_HINTS.get(ext, '请检查文件后重试。')}")
            try:
                extracted = extract(ext, raw)
            except HTTPException:
                raise
            except ValueError as exc:
                if "20万字" in str(exc):
                    _reject(413, str(exc))
                _reject(400, "文件内容超出支持范围或无法解析，请拆分后重新导入")
            except Exception:  # noqa: BLE001
                _reject(400, "没能读出这个文件的文字，请换一个文件，或把教案文字粘贴进来")
        if len(extracted["text"]) > MAX_TEXT_CHARS:
            _reject(413, "教案文字超过20万字，请拆分后导入；未截断保存")
        if len(extracted["text"]) < 20:
            _reject(400, "没有读到足够的文字（扫描版 PDF 和纯图片暂不支持），请换文件或直接粘贴文字")
        return extracted

    def _markdown_plan(extracted: dict[str, Any]) -> dict[str, Any] | None:
        """A plan parsed by rule when the text follows the documented convention, else None.

        Detection is deliberately conservative: the parser only accepts the fixed ``##``
        section names, so an ordinary free-form teaching document raises and falls back
        to the AI path unchanged.
        """
        try:
            return lesson_markdown.parse(extracted.get("text") or "", max_lesson=LESSONS)
        except ValueError:
            return None

    def _apply_lesson_plan(db: Any, u: Any, subject: str, lessonNo: int, data: dict[str, Any], source_text: str,
                           *, slides_hint: list[str] | None = None, use_literal: bool = True) -> dict[str, Any]:
        """Write one structured lesson plan plus its draft questions, then commit.

        Shared by the AI import, the structured JSON import and the Markdown import, so all
        three keep exactly the same validation and write behaviour.
        """
        p = program(db, int(u.school_id))
        lesson = db.scalar(select(Lesson).where(Lesson.school_id == u.school_id, Lesson.program_id == p.id, Lesson.subject == subject, Lesson.lesson_no == lessonNo))
        slides = slides_hint or _content_lines(data.get("ppt"))
        row = db.execute(select(sched).where(sched.c.teacher_id == u.id, sched.c.subject == subject, sched.c.lesson_no == lessonNo)).first()
        now = datetime.utcnow()
        fields = dict(title=(str(data.get("title") or "").strip() or f"{subject}第{lessonNo}课")[:180], core_target=str(data.get("coreTarget") or "")[:1000],
                      teacher_plan=str(data.get("teacherPlan") or ""), reading_plan=source_text, ppt_json=json.dumps(slides, ensure_ascii=False),
                      examples_json=json.dumps(_content_lines(data.get("examples")), ensure_ascii=False),
                      closure_training=_homework_from_source(source_text, str(data.get("closureTraining") or "")),
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
            db.execute(delete(TQ).where(TQ.lesson_id == lesson.id, TQ.stage != REMOVED_STAGE, TQ.active.is_(False)))
        qs = _valid_questions(data.get("questions"))
        wqs = valid_written_questions(data.get("writtenQuestions"))
        literal = literal_written_questions(source_text) if use_literal else []
        if literal:
            # Literal paper questions take priority; retain model references only
            # when the original question text matches, never by array position.
            for q in literal:
                question = q["stem"].split("\n")[-1]
                match = next((a for a in wqs if question in a["stem"]), None)
                if match:
                    q["reference"] = q["reference"] or match["reference"]
                    q["hints"] = match["hints"]
            wqs = valid_written_questions(literal)
        replace_written_drafts(db, written, u.school_id, u.id, lesson.id, wqs)
        for i, q in enumerate(qs[:12]):
            db.add(TQ(school_id=u.school_id, program_id=p.id, lesson_id=lesson.id, stage="lesson", subject=subject, level=LEVELS[min(i, len(LEVELS) - 1)], knowledge=q["kp"],
                      stem=q["stem"], options_json=json.dumps(q["options"], ensure_ascii=False), correct_index=q["ci"], explanation=q["exp"], active=False))
        db.commit()
        return {"lessonId": lesson.id, "status": lesson_status(db, u, lesson), "slides": len(slides), "questionsFound": len(qs) + len(wqs), "writtenQuestionsFound": len(wqs),
                "sourceChars": len(source_text), "message": f"原文 {len(source_text)} 字已完整保留（含阅读材料及非选择题）。已导入：{len(slides)} 页 PPT 内容、{len(qs)} 道选择题、{len(wqs)} 道简答/写作题（草稿，需你审核）。没有习题的话，点“AI 出习题（保留教案）”。"}

    def _apply_lesson_extract(db: Any, u: Any, subject: str, lessonNo: int, force: str, extracted: dict[str, Any]) -> dict[str, Any]:
        """AI tidies the extracted text into one lesson plus its draft questions, then commits."""
        p = program(db, int(u.school_id))
        lesson = db.scalar(select(Lesson).where(Lesson.school_id == u.school_id, Lesson.program_id == p.id, Lesson.subject == subject, Lesson.lesson_no == lessonNo))
        if lesson is not None and force != "1" and has_real_plan(lesson):
            raise HTTPException(409, "这节课已经有教案了。导入会覆盖教案文字（已通过的习题保留）。")
        plan = _markdown_plan(extracted)
        if plan is not None:
            got = _apply_lesson_plan(db, u, subject, lessonNo, plan, extracted["text"], use_literal=False)
            got["engine"] = "markdown"
            return got
        prompt = (
            f"下面是一位小学{p.grade}年级{subject}老师自己写的周末课教案内容。请只整理、归类里面已有的内容，不要编造新内容；文档里没有的字段留空。\n"
            f"---教案内容开始---\n{extracted['text']}\n---教案内容结束---\n"
            '只输出 JSON：{"title":"课题","coreTarget":"本节目标","teacherPlan":"教学流程(300字内)","ppt":["完整讲解页：标题＋原文中的方法步骤＋示例，每页用\\n换行，不得把每一行拆成一页；禁止放入教师参考答案或评分细则"],'
            '"examples":["文档里的例题和解答，原文照录"],"closureTraining":"课后练习",'
            '"questions":[{"stem":"文档里已有的选择题","options":["A","B","C"],"correctIndex":0,"explanation":"解析","knowledge":"知识点名"}],"writtenQuestions":[{"type":"short_answer或final_answer或composition","material":"对应完整阅读文章，不含教师答案","stem":"原有题目，不得改题型或漏题","reference":"原文对应参考答案及评分要点","hints":[]}]}'
            "（questions 只放原有选择题，writtenQuestions放全部原有简答、填空、复述、写作和挑战题，不要编造新题。阅读文章和非选择题不可省略；原文由系统完整保存。closureTraining 必须包含全部课后题，不能只列前几题。）"
        )
        data = implementation._ai_json(implementation._ai_call(db, u, AI_FEATURE, prompt, timeout=90))
        if not isinstance(data, dict) or not (str(data.get("title") or "").strip() or str(data.get("coreTarget") or "").strip() or _lines(data.get("examples"))):
            raise HTTPException(502, "AI 没能整理出教案，请再试一次，或在“审改”里手动填写")
        got = _apply_lesson_plan(db, u, subject, lessonNo, data, extracted["text"], slides_hint=extracted["slides"] or None)
        got["engine"] = "ai"
        return got

    @router.post("/teacher/weekend/lessons/import")
    def import_lesson(subject: str = Form(...), lessonNo: int = Form(...), force: str = Form("0"), text: str = Form(""), file: UploadFile | None = File(None),
                            u: Any = Depends(current_user), db: Any = Depends(get_db)):
        """Teacher uploads their own lesson plan (.docx/.pptx/.pdf/.txt) or pastes the text; AI only tidies it into the lesson fields (no inventing)."""
        need(u, "teacher")
        check_subject(subject)
        if not 1 <= lessonNo <= LESSONS:
            raise HTTPException(400, f"课次需要在 1–{LESSONS} 之间")
        return _apply_lesson_extract(db, u, subject, lessonNo, force, _extract_upload(file, text))

    @router.post("/teacher/weekend/lessons/import/preview")
    def import_preview(subject: str = Form(""), files: list[UploadFile] = File(...),
                            u: Any = Depends(current_user), db: Any = Depends(get_db)):
        """Read every selected file and report what would be imported. No model call, no database write."""
        need(u, "teacher")
        if not files:
            raise HTTPException(400, "请至少选择一个文件")
        if len(files) > MAX_BATCH_FILES:
            raise HTTPException(400, f"一次最多 {MAX_BATCH_FILES} 个文件")
        p = program(db, int(u.school_id)) if subject in SUBJECTS else None
        items: list[dict[str, Any]] = []
        for item in files:
            name = (item.filename or "").strip()
            lesson_no = detect_lesson_no(name, max_lesson=LESSONS)
            row: dict[str, Any] = {"filename": name, "lessonNo": lesson_no, "ok": False, "chars": 0, "error": "", "hasPlan": False, "engine": ""}
            try:
                extracted = _extract_upload(item, "")
                row.update(ok=True, chars=len(extracted["text"]), preview=extracted["text"][:120],
                           engine="markdown" if _markdown_plan(extracted) is not None else "ai")
                if lesson_no is not None and p is not None:
                    lesson = db.scalar(select(Lesson).where(Lesson.school_id == u.school_id, Lesson.program_id == p.id,
                                                            Lesson.subject == subject, Lesson.lesson_no == lesson_no))
                    row["hasPlan"] = bool(lesson is not None and has_real_plan(lesson))
            except HTTPException as exc:
                row["error"] = str(exc.detail)
            items.append(row)
        return {"items": items, "detected": sum(1 for i in items if i["lessonNo"]),
                "ready": sum(1 for i in items if i["ok"] and i["lessonNo"])}

    @router.post("/teacher/weekend/lessons/import/batch")
    def import_lessons(subject: str = Form(...), force: str = Form("0"), files: list[UploadFile] = File(...),
                            u: Any = Depends(current_user), db: Any = Depends(get_db)):
        """Import several lesson plans in one go: each file's 课次 comes from its name (第03课 / lesson-03).
        One bad file never stops the others and every file reports its own result."""
        need(u, "teacher")
        check_subject(subject)
        if not files:
            raise HTTPException(400, "请至少选择一个文件")
        if len(files) > MAX_BATCH_FILES:
            raise HTTPException(400, f"一次最多 {MAX_BATCH_FILES} 个文件")
        items: list[dict[str, Any]] = []
        for item in files:
            name = (item.filename or "").strip()
            lesson_no = detect_lesson_no(name, max_lesson=LESSONS)
            try:
                if lesson_no is None:
                    raise HTTPException(400, "没能从文件名看出课次，请把文件命名为「第03课」或「lesson-03」")
                got = _apply_lesson_extract(db, u, subject, lesson_no, force, _extract_upload(item, ""))
                items.append({"filename": name, "lessonNo": lesson_no, "ok": True, "lessonId": got["lessonId"],
                              "sourceChars": got["sourceChars"], "engine": got.get("engine", ""), "error": ""})
            except HTTPException as exc:
                db.rollback()
                items.append({"filename": name, "lessonNo": lesson_no, "ok": False, "error": str(exc.detail)})
            except Exception:  # noqa: BLE001
                db.rollback()
                items.append({"filename": name, "lessonNo": lesson_no, "ok": False, "error": "这个文件导入失败，请单独重试"})
        imported = sum(1 for i in items if i["ok"])
        failed = len(items) - imported
        return {"items": items, "imported": imported, "failed": failed,
                "message": f"成功导入 {imported} 节，失败 {failed} 节" + ("（失败的文件可以单独重试）" if failed else "")}

    def _plan_from_body(item: PlanLessonBody) -> dict[str, Any]:
        """Validate one structured lesson and convert it to the internal plan shape."""
        questions = []
        for index, q in enumerate(item.questions, start=1):
            options = [str(x).strip() for x in q.options]
            if q.correctIndex is None:
                raise HTTPException(422, f"第 {index} 道选择题缺少 correctIndex")
            if len(options) < 2 or any(not x for x in options):
                raise HTTPException(422, f"第 {index} 道选择题至少要两个非空选项")
            if not 0 <= int(q.correctIndex) < len(options):
                raise HTTPException(422, f"第 {index} 道选择题的 correctIndex 超出范围（0–{len(options) - 1}）")
            questions.append({"stem": q.stem.strip(), "options": options, "correctIndex": int(q.correctIndex),
                              "explanation": q.explanation.strip(), "knowledge": q.knowledge.strip()})
        written = []
        for index, w in enumerate(item.writtenQuestions, start=1):
            kind = WRITTEN_TYPE_ALIASES.get(str(w.type or "").strip())
            if kind is None:
                raise HTTPException(422, f"第 {index} 道简答题的 type 不认识：{w.type}；可用 short_answer / final_answer / composition")
            hints = [str(h).strip() for h in w.hints if str(h).strip()]
            if hints and len(hints) != 3:
                raise HTTPException(422, f"第 {index} 道简答题的 hints 要么不填，要么正好 3 条")
            written.append({"type": kind, "material": w.material.strip(), "stem": w.stem.strip(),
                            "reference": w.reference.strip(), "hints": hints})
        plan = {"title": item.title.strip(), "coreTarget": item.coreTarget.strip(), "teacherPlan": item.teacherPlan,
                "ppt": [str(x) for x in item.ppt], "examples": [str(x) for x in item.examples],
                "closureTraining": item.closureTraining, "questions": questions, "writtenQuestions": written}
        if not (plan["title"] or plan["coreTarget"] or plan["examples"] or plan["ppt"] or questions or written):
            raise HTTPException(422, "这一节没有任何内容（title / coreTarget / examples / ppt / 题目 全空）")
        return plan

    def _plan_fingerprint(plan: dict[str, Any]) -> str:
        """Content hash of the payload only; the identity (subject / lessonNo) stays out of it."""
        payload = json.dumps({k: plan.get(k) for k in ("title", "coreTarget", "teacherPlan", "ppt", "examples",
                                                       "closureTraining", "questions", "writtenQuestions")},
                             ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(lesson_markdown.canonical(payload).encode("utf-8")).hexdigest()

    def _plan_source_text(plan: dict[str, Any]) -> str:
        """A readable 原文 for the lesson page when the input carries no original text."""
        parts = []
        if plan.get("title"):
            parts.append(str(plan["title"]))
        if plan.get("coreTarget"):
            parts.append("本节目标\n" + str(plan["coreTarget"]))
        if plan.get("teacherPlan"):
            parts.append("教学流程\n" + str(plan["teacherPlan"]))
        if plan.get("examples"):
            parts.append("例题\n" + "\n\n".join(str(x) for x in plan["examples"]))
        if plan.get("closureTraining"):
            parts.append(str(plan["closureTraining"]))
        return "\n\n".join(parts)

    def _assert_lesson_not_in_use(db: Any, lesson: Any) -> None:
        """A classroom record or any pupil record blocks an overwrite (same checks as delete)."""
        if lesson is None:
            return
        if db.execute(select(sessions.c.id).where(sessions.c.lesson_id == lesson.id).limit(1)).first():
            raise HTTPException(409, "这节课已经有课堂记录（含待开课），不能覆盖教案。请改用其它课次，或先归档课堂。")
        for model in (implementation.TeachingAdaptiveSession, implementation.TeachingAttempt, implementation.TeachingEssay):
            if db.scalar(select(model.id).where(model.lesson_id == lesson.id).limit(1)) is not None:
                raise HTTPException(409, "这节课已经有学生学习记录，不能覆盖教案。请改用其它课次。")

    def _import_plans(db: Any, u: Any, subject: str, jobs: list[dict[str, Any]], *, dry_run: bool, on_conflict: str) -> dict[str, Any]:
        """Import already-structured plans one by one; one bad item never stops the rest."""
        p = program(db, int(u.school_id))
        results: list[dict[str, Any]] = []
        imported = 0
        for job in jobs:
            base = {"filename": job.get("filename") or "", "lessonNo": job.get("lessonNo")}
            plan = job.get("plan")
            if plan is None:
                results.append({**base, "ok": False, "status": "invalid", "error": job.get("error") or "内容无法解析"})
                continue
            try:
                fingerprint = _plan_fingerprint(plan)
                lesson = db.scalar(select(Lesson).where(Lesson.school_id == u.school_id, Lesson.program_id == p.id,
                                                        Lesson.subject == subject, Lesson.lesson_no == int(job["lessonNo"])))
                if lesson is not None and has_real_plan(lesson):
                    if on_conflict == "skip":
                        results.append({**base, "ok": False, "status": "skipped", "contentHash": fingerprint, "error": "这节课已有教案，已跳过"})
                        continue
                    if on_conflict == "ask":
                        results.append({**base, "ok": False, "status": "conflict", "contentHash": fingerprint,
                                        "error": "这节课已有教案；确认覆盖请把 onConflict 设为 overwrite"})
                        continue
                    _assert_lesson_not_in_use(db, lesson)
                if dry_run:
                    results.append({**base, "ok": True, "status": "ready", "contentHash": fingerprint})
                    continue
                source_text = job.get("sourceText") or _plan_source_text(plan)
                got = _apply_lesson_plan(db, u, subject, int(job["lessonNo"]), plan, source_text, use_literal=False)
                implementation.audit(db, u, "weekend.lessons.import_structured",
                                     f"lesson={job['lessonNo']}:hash={fingerprint[:16]}:chars={len(source_text)}")
                imported += 1
                results.append({**base, "ok": True, "status": "imported", "lessonId": got["lessonId"],
                                "contentHash": fingerprint, "questionsFound": got["questionsFound"]})
            except HTTPException as exc:
                db.rollback()
                results.append({**base, "ok": False, "status": "invalid", "error": str(exc.detail)})
        # A dry run writes nothing, so "not imported" is not "failed": count each status.
        ready = sum(1 for item in results if item["status"] == "ready")
        invalid = sum(1 for item in results if item["status"] == "invalid")
        blocked = len(results) - imported - ready - invalid
        if dry_run:
            parts = [f"可导入 {ready} 节"]
            if blocked:
                parts.append(f"冲突或跳过 {blocked} 节")
            if invalid:
                parts.append(f"非法 {invalid} 节")
            message = "预检（未写入）：" + "，".join(parts)
        else:
            parts = [f"成功导入 {imported} 节"]
            if blocked:
                parts.append(f"冲突或跳过 {blocked} 节")
            if invalid:
                parts.append(f"失败 {invalid} 节（可单独重试）")
            message = "，".join(parts)
        return {"items": results, "imported": imported, "ready": ready, "blocked": blocked,
                "failed": invalid, "dryRun": dry_run, "message": message}

    @router.post("/teacher/weekend/lessons/import/structured")
    def import_structured(b: StructuredImportBody, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        """Import already-structured lesson plans: no model call, deterministic fields."""
        need(u, "teacher")
        check_subject(b.subject)
        if b.schemaVersion != 1:
            raise HTTPException(422, "schemaVersion 只支持 1")
        jobs: list[dict[str, Any]] = []
        for item in b.items:
            try:
                jobs.append({"lessonNo": item.lessonNo, "plan": _plan_from_body(item), "sourceText": ""})
            except HTTPException as exc:
                jobs.append({"lessonNo": item.lessonNo, "plan": None, "error": str(exc.detail)})
        return _import_plans(db, u, b.subject, jobs, dry_run=b.dryRun, on_conflict=b.onConflict)

    @router.post("/teacher/weekend/lessons/import/markdown")
    def import_markdown(subject: str = Form(...), dryRun: str = Form("0"), onConflict: str = Form("ask"),
                        files: list[UploadFile] = File(...), u: Any = Depends(current_user), db: Any = Depends(get_db)):
        """Import .md/.txt files written in the documented convention: regex parsing, no model call."""
        need(u, "teacher")
        check_subject(subject)
        if onConflict not in ("ask", "skip", "overwrite"):
            raise HTTPException(400, "onConflict 只能是 ask / skip / overwrite")
        if not files:
            raise HTTPException(400, "请至少选择一个文件")
        if len(files) > MAX_BATCH_FILES:
            raise HTTPException(400, f"一次最多 {MAX_BATCH_FILES} 个文件")
        jobs: list[dict[str, Any]] = []
        for item in files:
            name = (item.filename or "").strip()
            try:
                extracted = _extract_upload(item, "")
                plan = lesson_markdown.parse(extracted["text"], max_lesson=LESSONS)
                lesson_no = plan.get("lessonNo") or detect_lesson_no(name, max_lesson=LESSONS)
                if lesson_no is None:
                    raise HTTPException(400, "文件名或标题里看不出课次，请命名为「第03课」或在标题写「第 3 课」")
                jobs.append({"filename": name, "lessonNo": lesson_no, "plan": plan, "sourceText": extracted["text"]})
            except HTTPException as exc:
                jobs.append({"filename": name, "lessonNo": None, "plan": None, "error": str(exc.detail)})
            except ValueError as exc:
                jobs.append({"filename": name, "lessonNo": None, "plan": None, "error": str(exc)})
        return _import_plans(db, u, subject, jobs, dry_run=dryRun == "1", on_conflict=onConflict)

    def debug_classrooms(db: Any, u: Any, lid: int) -> list[Any]:
        # Lock before checking evidence. Student submissions use the same session lock.
        rows = db.execute(select(sessions).where(sessions.c.lesson_id == lid)
                          .order_by(sessions.c.id).with_for_update()).all()
        disposable = {"weekend_stage_log", "weekend_slide_state", "weekend_class_rosters", "weekend_written_questions"}
        md = implementation.Base.metadata
        for row in rows:
            if row.school_id != u.school_id or row.teacher_id != u.id:
                raise HTTPException(409, "其他老师也有这节课的课堂，不能代为撤销")
            if row.status not in ("planned", "running", "finished"):
                raise HTTPException(409, "课堂状态无法核对，不能按调试课堂撤销")
            for name, table in md.tables.items():
                if name.startswith("weekend_") and "session_id" in table.c and name not in disposable:
                    if db.execute(select(table).where(table.c.session_id == row.id).limit(1)).first():
                        raise HTTPException(409, "课堂已有学生作答、提示、讲题、积分或反馈记录，不能按调试课堂撤销")
            reports = md.tables.get("weekend_reports")
            if reports is not None:
                keys = db.scalars(select(reports.c.session_key).where(reports.c.school_id == u.school_id)).all()
                if any(str(row.id) in str(key).split(",") for key in keys):
                    raise HTTPException(409, "课堂已关联学情报告，不能按调试课堂撤销")
        return rows

    @router.get("/teacher/weekend/lessons/{lid}/debug-classrooms")
    def preview_debug_classrooms(lid: int, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "teacher")
        my_lesson(db, u, lid)
        rows = debug_classrooms(db, u, lid)
        return {"items": [{"id": r.id, "title": r.title, "status": r.status} for r in rows]}

    @router.post("/teacher/weekend/lessons/{lid}/cancel-debug-classrooms")
    def cancel_debug_classrooms(lid: int, b: CancelDebugBody, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "teacher")
        lesson = my_lesson(db, u, lid)
        db.execute(select(Lesson.id).where(Lesson.id == lid).with_for_update()).first()
        if not b.confirmed or b.subject != lesson.subject or b.lessonNo != lesson.lesson_no:
            raise HTTPException(400, "请核对学科和课次，并确认没有实际上课，仅为调试")
        rows = debug_classrooms(db, u, lid)
        ids = [r.id for r in rows]
        if sorted(set(b.sessionIds)) != ids:
            raise HTTPException(409, "课堂列表已变化，请重新预览后确认撤销")
        if not ids:
            return {"message": "没有需要撤销的调试课堂；教案保持不变", "cancelled": 0}
        # Keep a recovery snapshot in the audit log; do not delete lesson templates.
        snapshot = {"lessonId": lid, "sessions": [dict(r._mapping) for r in rows], "related": {}}
        courseware = implementation.Base.metadata.tables.get("weekend_courseware")
        if courseware is not None:
            cw = db.execute(select(courseware).where(courseware.c.school_id == u.school_id,
                courseware.c.lesson_id == lid).with_for_update()).first()
            if cw is not None:
                live = json.loads(cw.live_json or "{}")
                prefixes = {str(sid) for sid in ids}
                removed = {key: value for key, value in live.items() if key.split(":", 1)[0] in prefixes}
                snapshot["coursewareLive"] = {"id": cw.id, "removed": removed}
                db.execute(update(courseware).where(courseware.c.id == cw.id).values(
                    live_json=json.dumps({key: value for key, value in live.items() if key not in removed}, ensure_ascii=False)))
        for name in ("weekend_stage_log", "weekend_slide_state", "weekend_class_rosters", "weekend_written_questions"):
            table = implementation.Base.metadata.tables.get(name)
            if table is not None:
                snapshot["related"][name] = [dict(r._mapping) for r in db.execute(select(table).where(table.c.session_id.in_(ids)))]
                db.execute(delete(table).where(table.c.session_id.in_(ids)))
        db.execute(delete(sessions).where(sessions.c.id.in_(ids)))
        implementation.audit(db, u, "weekend.cancel_debug_classrooms", json.dumps(snapshot, ensure_ascii=False, default=str))
        db.commit()
        return {"message": f"已撤销 {len(ids)} 个调试课堂，教案和已审核习题保留；现在可以删除教案或重新开课", "cancelled": len(ids)}

    @router.delete("/teacher/weekend/lessons/{lid}")
    def delete_lesson(lid: int, b: DeleteLessonBody, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "teacher")
        lesson = my_lesson(db, u, lid)
        db.execute(select(Lesson.id).where(Lesson.id == lid).with_for_update()).first()
        if not b.confirmed or b.subject != lesson.subject or b.lessonNo != lesson.lesson_no:
            raise HTTPException(400, "请核对学科和课次，并确认删除教案")
        if db.execute(select(sessions.c.id).where(sessions.c.lesson_id == lid).limit(1)).first():
            raise HTTPException(409, "这节课已有课堂记录（含待开课），为保留课堂和学生作答，不能删除教案")
        for model in (implementation.TeachingAdaptiveSession, implementation.TeachingAttempt, implementation.TeachingEssay):
            if db.scalar(select(model.id).where(model.lesson_id == lid).limit(1)) is not None:
                raise HTTPException(409, "这节课已有学生学习记录，不能删除教案")
        other = db.execute(select(written.c.id).where(written.c.lesson_id == lid, written.c.session_id == 0,
            written.c.teacher_id != u.id).limit(1)).first()
        if other:
            raise HTTPException(409, "其他老师也在使用这份教案，不能删除")
        # Retire question IDs rather than breaking foreign-key references.
        db.execute(update(TQ).where(TQ.lesson_id == lid).values(active=False, stage=REMOVED_STAGE))
        db.execute(delete(written).where(written.c.lesson_id == lid, written.c.session_id == 0,
            written.c.school_id == u.school_id, written.c.teacher_id == u.id))
        lesson.title = f"{lesson.subject}第{lesson.lesson_no}课"
        for field in ("core_target", "teacher_plan", "reading_plan", "writing_plan", "closure_training", "essay_review"):
            setattr(lesson, field, "")
        lesson.examples_json = lesson.ppt_json = "[]"
        lesson.published = False
        lesson.updated_at = datetime.utcnow()
        db.commit()
        return {"message": "教案及本课习题已清除，课次和进度表保留，可重新导入", "status": lesson_status(db, u, lesson)}

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
        for q in db.scalars(select(TQ).where(TQ.lesson_id == lesson.id, TQ.stage != REMOVED_STAGE).order_by(TQ.id)).all():
            try:
                opts = json.loads(q.options_json or "[]")
            except Exception:  # noqa: BLE001
                opts = []
            out.append({"id": q.id, "stem": q.stem, "options": opts, "correctIndex": q.correct_index, "explanation": q.explanation, "knowledge": q.knowledge,
                        "active": bool(q.active), "level": qg.CODE_LEVEL.get(q.level, ""), "verified": str(q.explanation or "").startswith("验算：")})
        return {"items": out}

    @router.post("/teacher/weekend/lessons/{lid}/questions")
    def decide_questions(lid: int, b: ApproveBody, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "teacher")
        lesson = my_lesson(db, u, lid)
        if b.approve:
            db.execute(update(TQ).where(TQ.lesson_id == lesson.id, TQ.stage != REMOVED_STAGE, TQ.id.in_(b.approve)).values(active=True))
        if b.remove:
            db.execute(delete(TQ).where(TQ.lesson_id == lesson.id, TQ.stage != REMOVED_STAGE, TQ.id.in_(b.remove), TQ.active.is_(False)))   # an approved question is never deleted here
        db.commit()
        return lesson_status(db, u, lesson)

    @router.get("/teacher/weekend/lessons/{lid}/written/questions")
    def lesson_written(lid: int, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "teacher")
        lesson = my_lesson(db, u, lid)
        return {"goals": lesson_goals(lesson.core_target or ""),
                "items": [{"id": q.id, "stem": q.stem, "reference": q.reference, "suggestedKnowledge": suggest_knowledge(q.stem),
                 **template_meta(q)} for q in written_templates(db, written, u.school_id, u.id, lid)]}

    @router.put("/teacher/weekend/lessons/{lid}/written/questions/{qid}/marks")
    def mark_written(lid: int, qid: int, b: WrittenMarkBody, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        """考点 and 课后题: report labels only, so an approved question stays approved; every class of this lesson uses them."""
        need(u, "teacher")
        my_lesson(db, u, lid)
        q = next((q for q in written_templates(db, written, u.school_id, u.id, lid) if q.id == qid), None)
        if q is None:
            raise HTTPException(404, "没有找到这道备课题")
        meta = {**template_meta(q), "knowledge": b.knowledge.strip(), "afterClass": b.afterClass}
        db.execute(update(written).where(written.c.id == qid).values(hints_json=json.dumps(meta, ensure_ascii=False)))
        db.commit()
        return {"id": qid, "knowledge": meta["knowledge"], "afterClass": meta["afterClass"]}

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
            hints_json=json.dumps({**template_meta(q), "approved": False, "type": v["type"], "hints": v["hints"]}, ensure_ascii=False)))
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

