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
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import Column, DateTime, Integer, String, Table, UniqueConstraint, delete, func, insert, select, update

from changying.services import lesson_markdown, weekend_plan_history as history
from changying.services.weekend_course_types import (
    COURSE_TYPES, WorkflowRevisionConflict, compare_and_set_course_type, course_type_for, store_pending_materials,
    register_weekend_course_type_tables, workflow_for,
)
from changying.services import weekend_question_gen as qg
from changying.services.weekend_presentation import literal_numbered_questions
from changying.services.lesson_import import MAX_FILE_BYTES, MAX_TEXT_CHARS, SUPPORTED, detect_lesson_no, extract
from changying.web.weekend_pages import plan_page_html
from changying.services.lesson_written import (MAX_KNOWLEDGE, lesson_goals, literal_written_questions, suggest_knowledge,
    valid_written_questions, replace_written_drafts, written_templates, template_meta, lesson_question_number)
from changying.web.weekend_courseware import PreparedPagesBody, auto_populate_courseware, import_prepared_courseware
from changying.services.guardian_consent import (
    TEACHING_DOCUMENT_EGRESS_DENIED_DETAIL, teaching_document_ai_egress_approved,
)

AI_FEATURE = "weekend_lesson_draft"
# A paper question starts with "3.【复述】", "C1.【对比】" or "1、概括…"; headings never do.
_PAPER_QUESTION = re.compile(r"^\s*([A-Za-z]?\d+|[（(]\s*\d+\s*[)）])\s*[.．、:：)）]?\s*【?")
_PAPER_ANSWER = "教师评分秘密："
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


class PlanWrittenFigureBody(BaseModel):
    """An optional source picture attached to one written question."""

    type: Literal["uploaded_image"] = "uploaded_image"
    data_url: str = Field(default="", max_length=700000)
    alt: str = Field(default="", max_length=80)
    question_no: int | None = Field(default=None, ge=1, le=999)


class PlanWrittenBody(BaseModel):
    """One written question (short answer / final answer / composition)."""

    type: str = "short_answer"
    material: str = Field(default="", max_length=20000)
    stem: str = Field(min_length=1, max_length=20000)
    reference: str = Field(default="", max_length=4000)
    hints: list[str] = Field(default_factory=list, max_length=3)
    figure: PlanWrittenFigureBody | None = None


class PlanLessonBody(BaseModel):
    """One lesson of a structured import; the same fields the AI path fills."""

    lessonNo: int = Field(ge=1, le=LESSONS)
    title: str = Field(default="", max_length=180)
    coreTarget: str = Field(default="", max_length=1000)
    teacherPlan: str = Field(default="", max_length=MAX_TEXT_CHARS)
    courseType: Literal["reading", "writing"] | None = None
    readingPlan: str = Field(default="", max_length=MAX_TEXT_CHARS)
    writingPlan: str = Field(default="", max_length=MAX_TEXT_CHARS)
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
    # Optional pre-authored courseware that belongs to the single lesson in this
    # envelope. It is imported as draft pages in the same transaction.
    courseware: PreparedPagesBody | None = None


class CourseTypeBody(BaseModel):
    courseType: Literal["reading", "writing"]
    expectedRevision: int = Field(default=0, ge=0)


class ImportedMaterialReviewBody(BaseModel):
    status: Literal["confirmed", "ignored"]
    relationship: Literal["short_reading", "long_reading", "article_illustration", "model_essay", "picture_writing", "writing_method", "task", "question_figure", "other"] = "other"
    stageNo: int | None = Field(default=None, ge=1, le=7)
    sortOrder: int = Field(default=0, ge=0, le=999)
    expectedRevision: int = Field(ge=1)


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
    force: bool = False


class ApproveBody(BaseModel):
    approve: list[int] = []
    remove: list[int] = []
    retract: list[int] = []          # 撤回通过：题不再进入课堂，但已上过的课和学生作答都保留
    confirmMissingFigure: bool = False


class MaterialItemBody(BaseModel):
    text: str
    role: Literal["example", "practice", "pending"]
    options: list[str] = Field(default_factory=list)
    correctIndex: int | None = None
    explanation: str = ""
    knowledge: str = ""
    reference: str = ""


class MaterialApplyBody(BaseModel):
    items: list[MaterialItemBody] = Field(default_factory=list, max_length=100)


_MENTIONS_FIGURE_RE = re.compile(r"如图|图中的|如下图所示|如下图所示|见图|右图|左图|上图|下图|图中|看图")
_SECTION_EXAMPLE_RE = re.compile(r"^(?:[一二三四五六七八九十0-9]+[、.．\s]*)?(?:典型例题|例题讲解|例题|典例精讲|典例|讲解示例)\s*[：:]*$")
_SECTION_PRACTICE_RE = re.compile(r"^(?:[一二三四五六七八九十0-9]+[、.．\s]*)?(?:随堂练习|课堂练习|巩固练习|课后练习|练一练|试一试|达标检测|习题)\s*[：:]*$")
_EXAMPLE_ITEM_RE = re.compile(r"^(?:【?\s*例\s*[0-9一二三四五六七八九十]+|例题\s*[0-9一二三四五六七八九十]+)")
_PRACTICE_ITEM_RE = re.compile(r"^(?:练习\s*[0-9一二三四五六七八九十]+|随堂练习\s*[0-9一二三四五六七八九十]+|练\s*[0-9一二三四五六七八九十]+)")
_NUMBERED_ITEM_RE = re.compile(r"^(?:第\s*[0-9一二三四五六七八九十]+\s*题|[0-9]{1,2}\s*[.．、)）]|[（(][0-9]{1,2}[）)])")


def mentions_figure(text: Any) -> bool:
    return bool(_MENTIONS_FIGURE_RE.search(str(text or "")))


def has_figure(fig: Any) -> bool:
    if not isinstance(fig, dict):
        return False
    return fig.get("type") == "uploaded_image" and bool(str(fig.get("data_url") or "").strip())


def suggest_material_groups(text: str) -> list[dict[str, Any]]:
    """按标题与题号拆分混合资料并提出用途建议；不确定的条目标为待定（pending）。"""
    lines = [line.rstrip() for line in str(text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    section_role: str | None = None
    chunks: list[tuple[str | None, list[str]]] = []
    cur_lines: list[str] = []
    cur_section: str | None = None

    def flush():
        nonlocal cur_lines
        joined = "\n".join(x for x in cur_lines).strip()
        if joined:
            chunks.append((cur_section, [joined]))
        cur_lines = []

    for raw in lines:
        s = raw.strip()
        if not s:
            if cur_lines:
                flush()
            continue
        if _SECTION_EXAMPLE_RE.match(s):
            flush()
            section_role = "example"
            cur_section = section_role
            continue
        if _SECTION_PRACTICE_RE.match(s):
            flush()
            section_role = "practice"
            cur_section = section_role
            continue
        is_new_item = bool(_EXAMPLE_ITEM_RE.match(s) or _PRACTICE_ITEM_RE.match(s) or _NUMBERED_ITEM_RE.match(s))
        if is_new_item and cur_lines:
            flush()
        if not cur_lines:
            cur_section = section_role
        cur_lines.append(s)
    flush()

    items: list[dict[str, Any]] = []
    for idx, (sec, block) in enumerate(chunks, start=1):
        body = block[0]
        first = body.split("\n", 1)[0].strip()
        if _EXAMPLE_ITEM_RE.match(first):
            role, reason = "example", "题号以“例/例题”开头，建议归入例题讲解"
        elif _PRACTICE_ITEM_RE.match(first):
            role, reason = "practice", "题号以“练习/练”开头，建议归入随堂练习"
        elif sec in ("example", "practice"):
            role = sec
            reason = "位于“例题”分区下，建议归入例题讲解" if sec == "example" else "位于“练习”分区下，建议归入随堂练习"
        else:
            role, reason = "pending", "标题或题号未明确归属，暂标为待定，请老师确认用途"
        items.append({"index": idx, "text": body, "role": role, "reason": reason})
    return items


class ExampleReviewBody(BaseModel):
    approve: list[int] = []
    retract: list[int] = []
    approveAll: bool = False


# 例题逐题审核的上线日：在这之前就已经存在的课，例题按“历史·已通过”显示，
# 不让正在教的旧课一开课就看到一屏“待审核”。
# 数据库里的时间列存的是 naive UTC，所以这里也写 UTC：2026-11-14 16:00 UTC = 2026-11-15 00:00 北京时间。
EXAMPLE_REVIEW_LEGACY_BEFORE = datetime(2026, 11, 14, 16, 0)
EXAMPLE_REVIEW_STATUS = {"approved": "已通过", "legacy": "历史·已通过", "changed": "已修改，待重新审核", "pending": "待审核"}


def example_review_hash(text: Any) -> str:
    """例题内容指纹：题干一改，指纹就变，审核状态自动回到“待重新审核”。"""
    return hashlib.sha256(" ".join(str(text or "").split()).encode("utf-8")).hexdigest()[:32]


def register_example_review_table(implementation: Any) -> Table:
    """例题逐题审核记录；启动时 create_all 建表，不改动任何已有表。"""
    md = implementation.Base.metadata
    if "weekend_example_reviews" not in md.tables:
        Table(
            "weekend_example_reviews", md,
            Column("id", Integer, primary_key=True),
            Column("school_id", Integer, nullable=False, index=True),
            Column("lesson_id", Integer, nullable=False, index=True),
            Column("teacher_id", Integer, nullable=False),
            Column("page_index", Integer, nullable=False),
            Column("stem_hash", String(32), nullable=False),
            Column("reviewed_at", DateTime, nullable=False),
            UniqueConstraint("lesson_id", "page_index", name="uq_weekend_example_review"),
        )
    return md.tables["weekend_example_reviews"]


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


_EXAMPLE_NO = re.compile(r"^\s*例\s*题?\s*([0-9]{1,3})")


def example_stems(raw: Any) -> list[dict[str, str]]:
    """本课例题的题干，形如 [{"label": "例1", "stem": "例1：2.5×4=？"}]。

    例题也要参加查重：随堂练习如果和例题一模一样，学生就只是照抄答案。
    examples_json 既可能是文字列表，也可能是带 title/answer 的对象列表，两种都认。
    """
    if isinstance(raw, str):
        try:
            raw = json.loads(raw or "[]")
        except (TypeError, ValueError):
            raw = [x for x in raw.splitlines() if x.strip()]
    out: list[dict[str, str]] = []
    for index, item in enumerate(raw if isinstance(raw, list) else [], start=1):
        title = ""
        if isinstance(item, dict):
            title = str(item.get("title") or item.get("label") or "").strip()
            text = next((str(item.get(k) or "").strip() for k in ("stem", "question", "text", "content")
                         if str(item.get(k) or "").strip()), "")
            if not text:
                # 只有 title + answer 的旧例题：把两段合起来当题干，至少能挡住同名例题。
                text = " ".join(x for x in (title, str(item.get("answer") or "").strip()) if x)
        else:
            text = str(item or "").strip()
        text = " ".join(text.split())
        if not text:
            continue
        found = _EXAMPLE_NO.match(text) or _EXAMPLE_NO.match(title)
        label = f"例{int(found.group(1))}" if found else f"例{index}"
        out.append({"label": label, "stem": text})
    return out


def merge_example_stems(stems: list[str], lesson: Any) -> list[str]:
    """把例题题干并入已有题干，生成新题时不再重复例题。"""
    raw = lesson.get("examples_json") if isinstance(lesson, dict) else getattr(lesson, "examples_json", "")
    return list(stems) + [e["stem"] for e in example_stems(raw)]


def question_options(row: Any) -> list[str]:
    """读取一道题的选项文本；坏数据按没有选项处理，不让审核接口报 500。"""
    raw = row.get("options_json") if isinstance(row, dict) else getattr(row, "options_json", "")
    try:
        data = json.loads(raw or "[]")
    except (TypeError, ValueError):
        return []
    return [str(x).strip() for x in data if str(x).strip()] if isinstance(data, list) else []


def _worked_example_match_text(page: Any) -> str:
    """Remove the slide-only numbered metadata header before comparing with a reviewed question stem."""
    lines = str(page or "").splitlines()
    # 老教案的例题页头是「例23（讲解用）」，新的是「第3题（基础）（4分）」：都是版面信息，不是题干。
    if len(lines) > 1 and (
            re.match(r"^\s*第\s*[0-9一二三四五六七八九十百]+\s*题", lines[0])
            or re.fullmatch(r"\s*例\s*[0-9]{1,3}\s*(?:[（(][^）)]{0,20}[）)])*\s*", lines[0])):
        lines = lines[1:]
    cleaned = []
    for line in lines:
        line = re.sub(r"^\s*原题\s*[|｜:：]\s*", "", line)
        if line.strip():
            cleaned.append(line.strip())
    return "\n".join(cleaned)


def lesson_worked_examples(lesson: Any) -> list[dict[str, str]]:
    """Return the same example pages shown in stage 3, including source questions from reading_plan."""
    from changying.services.weekend_presentation import lesson_deck

    pages = lesson_deck({
        "reading_plan": str(getattr(lesson, "reading_plan", "") or ""),
        "examples_json": str(getattr(lesson, "examples_json", "") or ""),
    }, 3)
    return [{"label": f"例{i}", "stem": _worked_example_match_text(page)} for i, page in enumerate(pages, start=1) if _worked_example_match_text(page)]


def _options_are_telling(options: list[str]) -> bool:
    """选项本身能不能证明是同一道题。

    判断题的“√／×”、只差一位的“3／4／5／6”“12／15／18／20”这类纯数字或单字选项，
    在互不相干的题里天天出现，拿它们判重会把不同的题当成重复、悄悄略过，
    所以只有“至少 3 个选项、且其中有一个不是纯数字”的选项组才参与判重。
    """
    cleaned = [qg.question_key(option) for option in options or []]
    return len(cleaned) >= 3 and any(not option.isdigit() for option in cleaned)


def duplicate_of(stem: str, options: list[str], examples: list[dict[str, str]],
                 others: list[tuple[str, list[str]]]) -> str:
    """这道题重复了谁：返回 "例3" / "本课习题" / ""（不重复），只用于页面提示。"""
    for example in examples:
        # 例题页与审核页的题干只差版面标注时也算同一道题，否则旧课会把整套例题当练习发出去。
        if qg.same_question_text(stem, example["stem"]):
            return example["label"]
    for other_stem, other_options in others:
        if qg.same_question(stem, other_stem):
            return "本课习题"
        if (_options_are_telling(options) and _options_are_telling(other_options)
                and qg.same_options(options, other_options)):
            return "本课习题"
    return ""


def _homework_from_source(text: str, fallback: str) -> str:
    """A literal homework section wins over the model's abbreviated version."""
    heading = re.compile(r"(?m)^[ \t]*(?:[一二三四五六七八九十0-9]+[.．、][ \t]*)?(?:课后练习|课后作业|家庭作业|课后训练|作业)(?:[：:][ \t]*|[ \t]+|(?=\n|$|《))")
    matches = list(heading.finditer(text))
    return text[matches[-1].start():].strip() if matches else fallback


# Lessons that are not prepared carry a hint instead of a real target: the school
# template says "请依据学校…", and the personal one-click course says "在上课时填写…".
# A hint is not a plan.
PLACEHOLDER_PREFIXES = ("请依据学校", "在上课时填写")


def has_real_plan(lesson: Any) -> bool:
    """A lesson counts as prepared only when the teacher (or AI) wrote real content: a real target or examples.
    Seeded template lessons and one-click personal lessons carry a hint, so they do not count."""
    target = (lesson.core_target or "").strip()
    if target and not target.startswith(PLACEHOLDER_PREFIXES):
        return True
    try:
        return bool(_lines(json.loads(lesson.examples_json or "[]")))
    except Exception:  # noqa: BLE001
        return False


_FIGURE_URL = re.compile(r"data:image/(?:jpeg|png);base64,[A-Za-z0-9+/]+={0,2}")
MAX_FIGURE_DATA_URL = 700_000


def _question_figure(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or str(value.get("type") or "").lower() != "uploaded_image":
        return {}
    url = str(value.get("data_url") or "")
    if len(url) > MAX_FIGURE_DATA_URL or not _FIGURE_URL.fullmatch(url):
        return {}
    figure = {"type": "uploaded_image", "data_url": url, "alt": str(value.get("alt") or "原卷插图")[:80]}
    # Preserve PDF layout provenance; the AI-written question stem may omit its number.
    try:
        question_no = int(value.get("question_no"))
    except (TypeError, ValueError):
        question_no = 0
    if 1 <= question_no <= 999:
        figure["question_no"] = question_no
    return figure


def _stored_figure(q: Any) -> dict[str, Any]:
    try:
        return _question_figure(json.loads(getattr(q, "figure_json", "") or "{}"))
    except (TypeError, ValueError):
        return {}


def _attach_figures(data: Any, figures: list[dict[str, Any]]) -> int:
    """Attach only when the question text matches a uniquely positioned PDF figure.

    The model's figureImage index is untrusted and ignored. PDFs without reliable
    question geometry (and Office images without layout metadata) stay unattached.
    """
    if not isinstance(data, dict) or not figures:
        return 0

    def normalized(value: Any) -> str:
        return "".join(char.casefold() for char in str(value or "") if char.isalnum())

    questions = [q for key in ("questions", "writtenQuestions")
                 for q in (data.get(key) or []) if isinstance(q, dict)]
    candidates: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for q in questions:
        # Never accept model-provided URLs or indexes as evidence of ownership.
        q.pop("figureImage", None)
        q.pop("figure", None)
        qtext = normalized(" ".join((str(q.get("stem") or ""), str(q.get("material") or ""))))
        if len(qtext) < 8:
            continue
        for figure in figures:
            source = normalized(figure.get("question_source_text"))
            if figure.get("question_no") is not None and source and qtext in source:
                candidates.append((q, figure))

    # Both directions must be unique; duplicate stems or repeated image placements
    # are left for teacher review instead of being guessed.
    q_counts: dict[int, int] = {}
    f_counts: dict[int, int] = {}
    for q, f in candidates:
        q_counts[id(q)] = q_counts.get(id(q), 0) + 1
        f_counts[id(f)] = f_counts.get(id(f), 0) + 1
    attached = 0
    for q, figure in candidates:
        if q_counts[id(q)] == 1 and f_counts[id(figure)] == 1:
            q["figure"] = {"type": "uploaded_image", "data_url": figure["data_url"], "alt": "原卷插图",
                            "question_no": figure.get("question_no")}
            attached += 1
    return attached


def _valid_questions(raw: Any) -> list[dict[str, Any]]:
    qs = []
    for q in raw if isinstance(raw, list) else []:
        try:
            opts = [str(x).strip() for x in q.get("options")][:4]
            ci = int(q.get("correctIndex"))
        except (TypeError, ValueError, AttributeError):
            continue
        if str(q.get("stem") or "").strip() and len(opts) >= 2 and all(opts) and 0 <= ci < len(opts):
            qs.append({"stem": str(q["stem"]).strip()[:300], "options": opts, "ci": ci, "exp": str(q.get("explanation") or "")[:300], "kp": str(q.get("knowledge") or "")[:160],
                       "fig": _question_figure(q.get("figure"))})
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
    from changying.web.weekend_courseware import register_courseware_table, invalidate_courseware_on_reimport
    courseware_table = register_courseware_table(implementation)
    versions = history.register_history(implementation.Base.metadata)
    sched = register_plan_tables(implementation)
    workflow_tables = register_weekend_course_type_tables(implementation)
    workflows = workflow_tables["config"]
    example_reviews = register_example_review_table(implementation)
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

    def example_rows(db: Any, lesson_id: int) -> dict[int, Any]:
        rows = db.execute(select(example_reviews).where(example_reviews.c.lesson_id == lesson_id)).all()
        return {int(r.page_index): r for r in rows}

    def example_items(db: Any, lesson: Any) -> list[dict[str, Any]]:
        """每道例题 + 审核状态。旧课（上线前就在、一直没审过）按“历史·已通过”显示。"""
        rows = example_rows(db, lesson.id)
        legacy = (not rows and lesson.updated_at is not None and lesson.updated_at < EXAMPLE_REVIEW_LEGACY_BEFORE)
        out = []
        for index, example in enumerate(lesson_worked_examples(lesson)):
            row = rows.get(index)
            if row is None:
                status = "legacy" if legacy else "pending"
            elif row.stem_hash == example_review_hash(example["stem"]):
                status = "approved"
            else:
                status = "changed"
            reviewed = row.reviewed_at if (row is not None and status == "approved") else None
            out.append({"label": example["label"], "stem": example["stem"], "pageIndex": index,
                        "status": status, "statusText": EXAMPLE_REVIEW_STATUS[status],
                        "reviewedAt": reviewed.isoformat() if reviewed else None})
        return out

    def practice_ready(db: Any, u: Any, lesson: Any) -> int:
        """第4环节实际能发放的题数：与例题重复的题不发，所以和大屏用同一套判断先算一遍。"""
        examples = lesson_worked_examples(lesson)
        ready = 0
        rows = db.scalars(select(TQ).where(TQ.lesson_id == lesson.id, TQ.stage != REMOVED_STAGE, TQ.active.is_(True))).all()
        for q in rows:
            if not duplicate_of(q.stem, question_options(q), examples, []):
                ready += 1
        for q in written_templates(db, written, u.school_id, u.id, lesson.id):
            if template_meta(q).get("approved") and not duplicate_of(str(q.stem).split("\n\n")[-1].strip(), [], examples, []):
                ready += 1
        return ready

    def practice_summary(db: Any, u: Any, lesson: Any) -> dict[str, Any]:
        """习题审核页顶部：例题、可用练习、待审核各多少，外加课件审核状态（两套审核分开显示）。"""
        status = lesson_status(db, u, lesson)
        cw_status = str(db.scalar(select(courseware_table.c.status).where(courseware_table.c.lesson_id == lesson.id)) or "")
        return {"exampleCount": status["exampleCount"], "exampleApproved": status["exampleApproved"],
                "examplePending": status["examplePending"], "practiceApproved": status["approvedQuestions"],
                "practiceDraft": status["draftQuestions"], "practiceReady": status["practiceReady"],
                "coursewareStatus": cw_status, "coursewareApproved": status["coursewareApproved"],
                "courseType": status.get("courseType"), "canStart": status.get("canStart"),
                "startReasons": status.get("startReasons", [])}

    def lesson_status(db: Any, u: Any, lesson: Any) -> dict[str, Any]:
        approved = db.scalar(select(func.count()).select_from(TQ).where(TQ.lesson_id == lesson.id, TQ.stage != REMOVED_STAGE, TQ.active.is_(True))) or 0
        draft = db.scalar(select(func.count()).select_from(TQ).where(TQ.lesson_id == lesson.id, TQ.stage != REMOVED_STAGE, TQ.active.is_(False))) or 0
        templates = written_templates(db, written, u.school_id, u.id, lesson.id)
        written_approved = sum(bool(template_meta(q).get("approved")) for q in templates)
        approved += written_approved
        draft += len(templates) - written_approved
        ran = db.scalar(select(func.count()).select_from(sessions).where(sessions.c.lesson_id == lesson.id, sessions.c.teacher_id == u.id, sessions.c.status != "planned")) or 0
        examples = example_items(db, lesson)
        example_approved = sum(1 for e in examples if e["status"] in ("approved", "legacy"))
        cw_status = str(db.scalar(select(courseware_table.c.status).where(courseware_table.c.lesson_id == lesson.id)) or "")
        readiness = {}
        if lesson.subject == "语文":
            from changying.services.chinese_lesson_readiness import chinese_lesson_readiness
            readiness = chinese_lesson_readiness(implementation, db, lesson, u.id)
        return {"lessonId": lesson.id, "title": lesson.title, "hasPlan": has_real_plan(lesson),
                "approvedQuestions": int(approved), "draftQuestions": int(draft), "taught": bool(ran),
                "exampleCount": len(examples), "exampleApproved": example_approved,
                "examplePending": len(examples) - example_approved, "practiceReady": practice_ready(db, u, lesson),
                "coursewareStatus": cw_status, "coursewareApproved": cw_status == "approved", **readiness}


    @router.get("/v1/weekend-plan", include_in_schema=False)
    def page():
        return HTMLResponse(plan_page_html(), headers={"Cache-Control": "no-store"})

    @router.get("/teacher/weekend/schedule")
    def get_schedule(subject: str = "数学", u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "teacher")
        check_subject(subject)
        p = program(db, int(u.school_id))
        rows = {int(r.lesson_no): r for r in db.execute(select(sched).where(sched.c.teacher_id == u.id, sched.c.subject == subject)).all()}
        lessons = {int(l.lesson_no): l for l in db.scalars(select(Lesson).where(Lesson.school_id == u.school_id, Lesson.program_id == p.id, Lesson.subject == subject)).all()}
        configured = {int(w.lesson_no): w for w in db.execute(select(workflows).where(
            workflows.c.school_id == u.school_id, workflows.c.program_id == p.id,
            workflows.c.subject == subject,
        )).all()}
        pending_materials = {}
        if subject == "\u8bed\u6587":
            pending_materials = {int(lesson_id): int(count) for lesson_id, count in db.execute(
                select(workflow_tables["materials"].c.lesson_id, func.count(workflow_tables["materials"].c.id))
                .where(workflow_tables["materials"].c.school_id == int(u.school_id),
                       workflow_tables["materials"].c.status == "pending")
                .group_by(workflow_tables["materials"].c.lesson_id)
            ).all()}
        out = []
        for n in range(1, LESSONS + 1):
            r, l = rows.get(n), lessons.get(n)
            item = {"lessonNo": n, "schoolWeek": r.school_week if r else None, "schoolUnit": r.school_unit if r else "", "plannedDate": r.planned_date if r else "", "note": r.note if r else ""}
            item.update(lesson_status(db, u, l) if l else {
                "lessonId": None, "title": "", "hasPlan": False, "approvedQuestions": 0, "draftQuestions": 0,
                "taught": False, "practiceReady": 0, "coursewareStatus": "", "coursewareApproved": False,
            })
            wf = configured.get(n)
            item["courseType"] = "math" if subject == "数学" else (str(wf.course_type) if wf else None)
            item["workflowRevision"] = int(wf.revision) if wf else 0
            item["workflowLabel"] = {"math": "数学七环节", "reading": "阅读课", "writing": "作文课"}.get(item["courseType"], "待选择课型")
            item["pendingMaterials"] = pending_materials.get(int(l.id), 0) if l else 0
            out.append(item)
        return {"subject": subject, "items": out}

    @router.put("/teacher/weekend/schedule/{subject}/{lesson_no}/course-type")
    def save_course_type(subject: str, lesson_no: int, b: CourseTypeBody,
                         u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "teacher")
        check_subject(subject)
        if subject != "语文":
            raise HTTPException(400, "数学课程继续使用原有七环节，不需要选择语文课型")
        if not 1 <= lesson_no <= LESSONS:
            raise HTTPException(400, f"课次需要在 1–{LESSONS} 之间")
        p = program(db, int(u.school_id))
        lesson = db.scalar(select(Lesson).where(
            Lesson.school_id == u.school_id, Lesson.program_id == p.id,
            Lesson.subject == subject, Lesson.lesson_no == lesson_no,
        ))
        old_type = course_type_for(db, implementation, lesson) if lesson is not None else None
        now = datetime.utcnow()
        try:
            revision = compare_and_set_course_type(
                db, implementation, school_id=int(u.school_id), program_id=int(p.id),
                lesson_no=lesson_no, lesson_id=int(lesson.id) if lesson else None,
                course_type=b.courseType, expected_revision=b.expectedRevision,
                updated_by=int(u.id), updated_at=now,
            )
        except WorkflowRevisionConflict as exc:
            raise HTTPException(409, "课型已被其他页面修改，请刷新后重新选择") from exc
        if lesson is not None and old_type and old_type != b.courseType:
            invalidate_courseware_on_reimport(db, courseware_table, lesson.id)
        db.commit()
        return {"lessonNo": lesson_no, "courseType": b.courseType, "workflowRevision": revision,
                "workflowLabel": "阅读课" if b.courseType == "reading" else "作文课"}

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
        """Approved questions of the lesson plus its examples: new drafts must not repeat either."""
        stems = [q.stem for q in db.scalars(select(TQ).where(TQ.lesson_id == lesson.id, TQ.stage != REMOVED_STAGE, TQ.active.is_(True)))]
        stems += [q.stem.split("\n")[-1] for q in written_templates(db, written, u.school_id, u.id, lesson.id) if template_meta(q).get("approved")]
        from changying.services.weekend_presentation import lesson_deck
        stems += lesson_deck({
            "reading_plan": lesson.reading_plan or "",
            "examples_json": lesson.examples_json or "",
        }, 3)
        return merge_example_stems(stems, lesson)

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
                _reject(413, "文件不能超过 20MB，请拆分后导入")
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

    def plan_state(db, u, lesson):
        state = history.capture(db, lesson, TQ.__table__, written, courseware_table, REMOVED_STAGE)
        if any(row["teacher_id"] != u.id for key in ("written", "courseware") for row in state[key]):
            raise HTTPException(409, "这份教案包含其他老师的习题或课件，无法覆盖或恢复。")
        return state

    def latest_version(db, lesson, *, with_content=False):
        query = select(versions) if with_content else select(versions.c.id, versions.c.teacher_id)
        return db.execute(query.where(versions.c.lesson_id == lesson.id,
            versions.c.school_id == lesson.school_id).order_by(versions.c.id.desc()).limit(1)).mappings().first()

    @router.post("/teacher/weekend/lessons/{lid}/import-history/{version_id}/restore")
    def restore_import(lid: int, version_id: int, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "teacher")
        lesson = db.scalar(select(Lesson).where(Lesson.id == lid, Lesson.school_id == u.school_id).with_for_update())
        if lesson is None or lesson.subject not in SUBJECTS:
            raise HTTPException(404, "没有找到这节课")
        saved = latest_version(db, lesson, with_content=True)
        if not saved or saved["id"] != version_id or saved["teacher_id"] != u.id:
            raise HTTPException(409, "可恢复的版本已变化，请刷新教案。")
        _assert_lesson_not_in_use(db, lesson)
        current = plan_state(db, u, lesson)
        if history.digest(current) != saved["after_hash"]:
            raise HTTPException(409, "重新导入后教案、习题或课件已有修改，已保留当前内容。")
        history.restore_content(db, lesson, json.loads(saved["before_json"]), current, TQ.__table__, written, courseware_table)
        db.execute(delete(versions).where(versions.c.id == version_id))
        db.commit()
        return lesson_status(db, u, lesson)

    def _apply_lesson_plan(db: Any, u: Any, subject: str, lessonNo: int, data: dict[str, Any], source_text: str,
                           *, slides_hint: list[str] | None = None, use_literal: bool = True, overwrite: bool = False,
                           courseware_pages: list[Any] | None = None,
                           courseware_replace_existing: bool = False,
                           source_materials: list[dict[str, Any]] | None = None,
                           source_file: str = "") -> dict[str, Any]:
        """Write one structured lesson plan plus its draft questions, then commit.

        Shared by the AI import, the structured JSON import and the Markdown import, so all
        three keep exactly the same validation and write behaviour.
        """
        p = program(db, int(u.school_id))
        wf = db.execute(select(workflows).where(
            workflows.c.school_id == u.school_id, workflows.c.program_id == p.id,
            workflows.c.subject == subject, workflows.c.lesson_no == lessonNo,
        ).with_for_update()).first()
        declared_type = str(data.get("courseType") or "").strip()
        if subject == "语文":
            if wf is None and declared_type in COURSE_TYPES:
                db.execute(insert(workflows).values(
                    school_id=u.school_id, program_id=p.id, subject=subject, lesson_no=lessonNo,
                    lesson_id=None, course_type=declared_type, revision=1, updated_by=u.id, updated_at=datetime.utcnow(),
                ))
                wf = db.execute(select(workflows).where(
                    workflows.c.school_id == u.school_id, workflows.c.program_id == p.id,
                    workflows.c.subject == subject, workflows.c.lesson_no == lessonNo,
                ).with_for_update()).first()
            if wf is None or str(wf.course_type) not in COURSE_TYPES:
                raise HTTPException(409, "请先在本课工作栏选择并保存“阅读课”或“作文课”，再导入教案。")
            if declared_type and declared_type != str(wf.course_type):
                raise HTTPException(409, "整包声明的课型与工作栏已保存的课型不一致，请先核对后再导入。")
        lesson = db.scalar(select(Lesson).where(Lesson.school_id == u.school_id, Lesson.program_id == p.id, Lesson.subject == subject, Lesson.lesson_no == lessonNo).with_for_update().execution_options(populate_existing=True))
        slides = slides_hint or _content_lines(data.get("ppt"))
        original_examples = literal_numbered_questions(source_text) if use_literal else []
        row = db.execute(select(sched).where(sched.c.teacher_id == u.id, sched.c.subject == subject, sched.c.lesson_no == lessonNo)).first()
        now = datetime.utcnow()
        fields = dict(title=(str(data.get("title") or "").strip() or f"{subject}第{lessonNo}课")[:180], core_target=str(data.get("coreTarget") or "")[:1000],
                      teacher_plan=str(data.get("teacherPlan") or ""),
                      reading_plan=str(data.get("readingPlan") or source_text),
                      ppt_json=json.dumps(slides, ensure_ascii=False),
                      examples_json=json.dumps(original_examples or _content_lines(data.get("examples")), ensure_ascii=False),
                      closure_training=_homework_from_source(source_text, str(data.get("closureTraining") or "")),
                      unit=(row.school_unit if row and row.school_unit else "")[:120] or "待配置单元", published=False, updated_at=now)
        if not fields["core_target"].strip() and not _lines(data.get("examples")):
            fields["core_target"] = fields["title"]            # a real (non-placeholder) target, so the lesson counts as prepared
        before = None
        if lesson is None:
            lesson = Lesson(school_id=u.school_id, program_id=p.id, subject=subject, lesson_no=lessonNo, duration_min=120,
                            writing_plan=str(data.get("writingPlan") or ""), **fields)
            db.add(lesson)
            db.flush()
        else:
            if has_real_plan(lesson) and not overwrite:
                raise HTTPException(409, "这节课已有教案，请确认覆盖后重新导入。")
            _assert_lesson_not_in_use(db, lesson)
            before = plan_state(db, u, lesson)
            if not (courseware_pages and courseware_replace_existing):
                invalidate_courseware_on_reimport(db, courseware_table, lesson.id)  # preserve drafts, revoke stale approvals
            for k, v in fields.items():
                setattr(lesson, k, v)
            if "writingPlan" in data:
                lesson.writing_plan = str(data.get("writingPlan") or "")
            db.execute(delete(TQ).where(TQ.lesson_id == lesson.id, TQ.stage != REMOVED_STAGE, TQ.active.is_(False)))
        qs = _valid_questions(data.get("questions"))
        wqs = valid_written_questions(data.get("writtenQuestions"))
        literal = literal_written_questions(source_text) if use_literal else []
        if literal:
            # Literal paper questions take priority; retain model references only
            # when the original question text matches, never by array position.
            for q in literal:
                question = q["stem"].split("\n")[-1]
                matches = [a for a in wqs if a["stem"].split("\n")[-1].strip() == question.strip()]
                match = matches[0] if len(matches) == 1 else None
                if match:
                    q["reference"] = q["reference"] or match["reference"]
                    q["hints"] = match["hints"]
                    q["figure"] = match["figure"]
            wqs = valid_written_questions(literal)
        replace_written_drafts(db, written, u.school_id, u.id, lesson.id, wqs)
        for i, q in enumerate(qs[:12]):
            db.add(TQ(school_id=u.school_id, program_id=p.id, lesson_id=lesson.id, stage="lesson", subject=subject, level=LEVELS[min(i, len(LEVELS) - 1)], knowledge=q["kp"],
                      stem=q["stem"], options_json=json.dumps(q["options"], ensure_ascii=False), correct_index=q["ci"], explanation=q["exp"], active=False,
                      figure_json=json.dumps(q["fig"], ensure_ascii=False)))
        if courseware_pages:
            # The lesson, every draft question and all pre-authored courseware
            # share one transaction. Both question approval and courseware
            # approval remain separate teacher decisions afterwards.
            import_prepared_courseware(
                implementation, db, u, lesson, courseware_pages,
                dry_run=False,
                replace_existing=courseware_replace_existing,
                allow_pending_practice=True,
                commit=False,
                audit_detail=f"lesson={lesson.id}:pages={len(courseware_pages)}:bundle=1",
                keep_previous_draft=not courseware_replace_existing,
                revoke_existing_approvals=courseware_replace_existing,
                prune_unselected=courseware_replace_existing,
            )
        elif subject == "语文":
            auto_populate_courseware(
                implementation, db, u, lesson,
                replace_existing=True, approve=False, commit=False,
            )
        if before is not None:
            # Keep at most 2 undo snapshots per lesson (the newly inserted row plus one
            # prior snapshot) so restoring an overwrite returns the previous state's
            # previousImportId while bounding Postgres storage across repeated re-imports.
            keep_ids = list(db.scalars(
                select(versions.c.id)
                .where(versions.c.school_id == u.school_id, versions.c.lesson_id == lesson.id)
                .order_by(versions.c.id.desc())
                .limit(1)
            ))
            prune_stmt = delete(versions).where(
                versions.c.school_id == u.school_id,
                versions.c.lesson_id == lesson.id,
            )
            if keep_ids:
                prune_stmt = prune_stmt.where(versions.c.id.notin_(keep_ids))
            db.execute(prune_stmt)
            db.execute(insert(versions).values(school_id=u.school_id, teacher_id=u.id, lesson_id=lesson.id,
                before_json=history.serialize(before), after_hash=history.digest(plan_state(db, u, lesson))))
        if wf is not None:
            db.execute(update(workflows).where(workflows.c.id == wf.id).values(lesson_id=lesson.id, updated_at=now))
        pending_materials = store_pending_materials(
            db, implementation, school_id=int(u.school_id), lesson_id=int(lesson.id),
            source_file=source_file or "pasted-text", created_by=int(u.id), figures=source_materials or [],
        )
        if data.get("writingPackage"):
            from changying.web.weekend_writing import store_writing_package
            store_writing_package(implementation, db, u, lesson, data["writingPackage"])
        db.commit()
        return {"lessonId": lesson.id, "status": lesson_status(db, u, lesson), "slides": len(slides), "questionsFound": len(qs) + len(wqs), "writtenQuestionsFound": len(wqs),
                "coursewarePagesFound": len(courseware_pages or []),
                "materialsPending": pending_materials,
                "sourceChars": len(source_text), "message": f"原文 {len(source_text)} 字已完整保留（含阅读材料及非选择题）。已导入：{len(slides)} 页 PPT 内容、{len(qs)} 道选择题、{len(wqs)} 道简答/写作题（草稿，需你审核）。没有习题的话，点“AI 出习题（保留教案）”。"}

    def _apply_lesson_extract(db: Any, u: Any, subject: str, lessonNo: int, force: str, extracted: dict[str, Any], *, source_file: str = "") -> dict[str, Any]:
        """AI tidies the extracted text into one lesson plus its draft questions, then commits."""
        p = program(db, int(u.school_id))
        lesson = db.scalar(select(Lesson).where(Lesson.school_id == u.school_id, Lesson.program_id == p.id, Lesson.subject == subject, Lesson.lesson_no == lessonNo))
        if lesson is not None and force != "1" and has_real_plan(lesson):
            raise HTTPException(409, "这节课已经有教案了。导入会覆盖教案文字（已通过的习题保留）。")
        plan = _markdown_plan(extracted)
        if plan is not None:
            got = _apply_lesson_plan(db, u, subject, lessonNo, plan, extracted["text"], use_literal=False, overwrite=force == "1",
                                     source_materials=extracted.get("images") or [], source_file=source_file)
            got["engine"] = "markdown"
            return got
        if subject == "语文":
            # Chinese originals stay on the server, but their paper questions must
            # still become reviewable drafts: keep the teacher's own references and
            # use the source text's line order to find each article for its question.
            paper = literal_written_questions(extracted["text"])
            lines = [line.strip() for line in extracted["text"].splitlines()]
            headings = [(index, line) for index, line in enumerate(lines)
                        if len(line) >= 8 and "。" not in line and not _PAPER_QUESTION.search(line)
                        and not line.startswith(_PAPER_ANSWER)]
            answers = [(index, line) for index, line in enumerate(lines) if line.startswith(_PAPER_ANSWER)]
            for question in paper:
                # The source is read top-down, so the last heading before a question
                # names the article or section that question belongs to.
                body = question["stem"].split("\n")[-1].strip()
                position = next((index for index, line in enumerate(lines) if line and line in question["stem"]), 0)
                after = [line for index, line in reversed(headings) if index <= position]
                article = after[0] if after and len(after[0]) >= 12 else ""
                source_answer = [line for index, line in answers if index > position]
                # valid_written_questions() re-joins material and stem, so the stem
                # must not repeat the heading itself.
                question["material"] = article
                question["stem"] = body
                if source_answer and not question.get("reference"):
                    question["reference"] = source_answer[0][len(_PAPER_ANSWER):].strip()
            note = (f"原文已在本地保存为草稿，并从中拆出 {len(paper)} 道简答/写作题（待审核，参考答案按原文逐行对应）。"
                    if paper else "原文已在本地保存为草稿，尚未自动拆分习题或匹配图片；请核对原文及待确认素材。")
            plan = {"title": f"{subject}第{lessonNo}课", "teacherPlan": extracted["text"],
                    "courseType": extracted.get("courseType") or "", "questions": [], "writtenQuestions": paper}
            got = _apply_lesson_plan(db, u, subject, lessonNo, plan, extracted["text"],
                                     slides_hint=extracted.get("slides") or None, use_literal=False,
                                     overwrite=force == "1", source_materials=extracted.get("images") or [],
                                     source_file=source_file)
            got.update(engine="local", importMode="local", message=note)
            return got
        if not teaching_document_ai_egress_approved():
            got = _apply_lesson_plan(db, u, subject, lessonNo,
                {"title": f"{subject}第{lessonNo}课", "teacherPlan": extracted["text"]},
                extracted["text"], slides_hint=extracted.get("slides") or None,
                use_literal=False, overwrite=force == "1",
                source_materials=extracted.get("images") or [], source_file=source_file)
            got.update(engine="local", importMode="local",
                message="教案原文已在本地保存为草稿，未外发。请核对原文、补充题目并审核素材；学生数据开关不能代替教案外发授权。")
            return got
        figures = extracted.get("images") or []
        figure_note = ""
        if figures:
            verified = [f for f in figures if f.get("question_no")]
            pages = "、".join(str(f["page"]) for f in verified if f.get("page"))
            mappings = "；".join(f"第 {f['question_no']} 题（第 {f['page']} 页）" for f in verified)
            figure_note = (
                f"文档里另外带了 {len(figures)} 张原图，以附图形式一并给你。系统根据原 PDF 版面位置独立核对图片与题号；"
                + (f"已核对：{mappings}。" if mappings else "当前版面无法唯一核对题号。")
                + "不要猜图片所属题目，也不要输出 figureImage 字段。\n"
            )
        prompt = (
            f"下面是一位小学{p.grade}年级{subject}老师自己写的周末课教案内容。请只整理、归类里面已有的内容，不要编造新内容；文档里没有的字段留空。\n"
            f"---教案内容开始---\n{extracted['text']}\n---教案内容结束---\n"
            + figure_note +
            '只输出 JSON：{"title":"课题","coreTarget":"本节目标","teacherPlan":"教学流程(300字内)","ppt":["完整讲解页：标题＋原文中的方法步骤＋示例，每页用\\n换行，不得把每一行拆成一页；禁止放入教师参考答案或评分细则"],'
            '"examples":["文档里的例题和解答，原文照录"],"closureTraining":"课后练习",'
            '"questions":[{"stem":"文档里已有的选择题","options":["A","B","C"],"correctIndex":0,"explanation":"解析","knowledge":"知识点名"}],"writtenQuestions":[{"type":"short_answer或final_answer或composition","material":"对应完整阅读文章，不含教师答案","stem":"原有题目，不得改题型或漏题","reference":"原文对应参考答案及评分要点","hints":[]}]}'
            "（questions 只放原有选择题，writtenQuestions放全部原有简答、填空、复述、写作和挑战题，不要编造新题。阅读文章和非选择题不可省略；原文由系统完整保存。closureTraining 必须包含全部课后题，不能只列前几题。"
            "图片由系统依据原 PDF 位置和原题文字匹配，AI 不负责给图片编号。）"
        )
        data = implementation._ai_json(implementation._ai_call(
            db, u, AI_FEATURE, prompt, images=[f["data_url"] for f in figures] or None,
            timeout=150 if figures else 90,
        ))
        attached_figures = _attach_figures(data, figures)
        if extracted.get("courseType") and isinstance(data, dict):
            data["courseType"] = extracted["courseType"]
        if not isinstance(data, dict) or not (str(data.get("title") or "").strip() or str(data.get("coreTarget") or "").strip() or _lines(data.get("examples"))):
            raise HTTPException(502, "AI 没能整理出教案，请再试一次，或在“审改”里手动填写")
        got = _apply_lesson_plan(db, u, subject, lessonNo, data, extracted["text"], slides_hint=extracted["slides"] or None, overwrite=force == "1",
                                 source_materials=figures, source_file=source_file)
        if figures and attached_figures < len(figures):
            unmatched = len(figures) - attached_figures
            got["figureWarning"] = f"有 {unmatched} 张原卷图未能与题目唯一核对，系统没有自动挂到题目上，请老师复核。"
            got["message"] = str(got.get("message") or "") + " " + got["figureWarning"]
        got["engine"] = "ai"
        return got

    @router.post("/teacher/weekend/lessons/import")
    def import_lesson(subject: str = Form(...), lessonNo: int = Form(...), force: str = Form("0"), text: str = Form(""), courseType: str = Form(""), file: UploadFile | None = File(None),
                            u: Any = Depends(current_user), db: Any = Depends(get_db)):
        """Import one lesson file; a JSON bundle can carry the plan, questions and courseware together."""
        need(u, "teacher")
        check_subject(subject)
        if not 1 <= lessonNo <= LESSONS:
            raise HTTPException(400, f"课次需要在 1–{LESSONS} 之间")
        filename = (file.filename or "").strip() if file is not None else ""
        extension = ("." + filename.rsplit(".", 1)[-1]).lower() if "." in filename else ""
        # Read once, then rewind for the ordinary document extractor. The structured
        # bundle is local-only and must not fall through to the external-AI import path
        # just because a downloaded file lost its .json suffix.
        raw = file.file.read(MAX_FILE_BYTES + 1) if file is not None else b""
        if len(raw) > MAX_FILE_BYTES:
            raise HTTPException(413, "文件不能超过 20MB，请压缩图片或拆分后重试")
        if file is not None:
            file.file.seek(0)

        bundle_payload = None
        try:
            candidate = json.loads(raw.decode("utf-8-sig"))
            if isinstance(candidate, dict) and "schemaVersion" in candidate and "items" in candidate:
                bundle_payload = candidate
        except (UnicodeDecodeError, json.JSONDecodeError):
            pass

        if extension == ".json" or bundle_payload is not None:
            if (isinstance(bundle_payload, dict) and len(bundle_payload.get('items',[])) == 1
                    and bundle_payload['items'][0].get('writingPackage') is not None):
                item = bundle_payload['items'][0]
                if subject != '语文':
                    raise HTTPException(422, f'作文整包只能导入语文课程；当前工作栏为“{subject}”第 {lessonNo} 次')
                bundle_subject = str(bundle_payload.get('subject') or '未填写')
                if bundle_subject != subject:
                    raise HTTPException(422, f'文件标记学科为“{bundle_subject}”，当前工作栏为“{subject}”第 {lessonNo} 次；请在语文课次导入')
                bundle_lesson_no = item.get('lessonNo')
                if bundle_lesson_no != lessonNo:
                    label = bundle_lesson_no if bundle_lesson_no is not None else '未填写'
                    raise HTTPException(422, f'文件标记第 {label} 次课，当前工作栏是第 {lessonNo} 次课；请回到匹配的课次行导入')
                from changying.services.writing_lesson import writing_inventory
                try:
                    package = writing_inventory(raw, 'writing.json')
                except (ValueError, KeyError, TypeError) as exc:
                    raise HTTPException(422, '作文整包内容无效：'+str(exc)) from exc
                source = '\n'.join(n.get('text','') for n in package['nodes'])
                if len(source)>MAX_TEXT_CHARS: raise HTTPException(413,'作文整包文字超限')
                return _apply_lesson_plan(db,u,subject,lessonNo,
                    {'title':package['title'],'teacherPlan':source,'courseType':'writing','writingPackage':package},
                    source,use_literal=False,overwrite=force=='1',source_file=filename)
            try:
                payload = bundle_payload if bundle_payload is not None else json.loads(raw.decode("utf-8-sig"))
                body = StructuredImportBody.model_validate(payload)
            except (UnicodeDecodeError, json.JSONDecodeError, ValidationError) as exc:
                raise HTTPException(422, "JSON 整包格式不正确，请使用网站导出的单文件整包") from exc
            finally:
                raw = b""
                bundle_payload = None
                payload = None
            if body.subject != subject:
                raise HTTPException(422, f"整包学科是“{body.subject}”，与当前“{subject}”不一致")
            if len(body.items) != 1 or body.items[0].lessonNo != lessonNo:
                raise HTTPException(422, f"整包必须只含当前第 {lessonNo} 次课；请在该课次行导入")
            body.dryRun = False
            body.onConflict = "overwrite" if force == "1" else "ask"
            result = _import_structured_body(body, u, db)
            item = result["items"][0]
            if not item.get("ok"):
                raise HTTPException(409, item.get("error") or result.get("message") or "整包导入失败")
            return {
                **item,
                "message": f"整包已导入：教案、{item.get('questionsFound', 0)} 道随堂题、"
                           f"{item.get('coursewarePagesFound', 0)} 页互动课件草稿。"
                           "题目与课件仍需分别逐题审核。",
            }
        # Keep the established AI-assisted extraction path when its feature gate allows it.
        # If the guardian-consent guard explicitly denies this unregistered feature, preserve
        # the source locally as a draft instead of sending it to an external service.
        extracted = _extract_upload(file, text)
        selected_type = courseType
        if subject == "语文" and not selected_type:
            p = program(db, int(u.school_id))
            existing = db.scalar(select(Lesson).where(Lesson.school_id == u.school_id,
                Lesson.program_id == p.id, Lesson.subject == subject, Lesson.lesson_no == lessonNo))
            selected_type = course_type_for(db, implementation, existing) if existing else ""
        if subject == "语文" and selected_type == "writing":
            from changying.services.writing_lesson import writing_inventory
            try:
                package = writing_inventory(raw, filename or "pasted-text", extracted["text"])
            except (ValueError, KeyError) as exc:
                raise HTTPException(422, str(exc)) from exc
            plan = {"title": f"作文第{lessonNo}课", "teacherPlan": extracted["text"],
                    "courseType": "writing", "writingPackage": package, "questions": [], "writtenQuestions": []}
            result = _apply_lesson_plan(db, u, subject, lessonNo, plan, extracted["text"],
                use_literal=False, overwrite=force == "1", source_file=filename)
            result.update(importMode="local", engine="local", message="作文素材已本地提取，未外发。请进入作文素材审核，核对范文、图片、方法与主题；缺项不能开课。")
            return result
        if courseType:
            if courseType not in COURSE_TYPES:
                raise HTTPException(422, "无效的语文课型")
            extracted["courseType"] = courseType
        try:
            result = _apply_lesson_extract(db, u, subject, lessonNo, force, extracted, source_file=filename or "pasted-text")
            visible_images = len(extracted.get("images") or [])
            omitted_images = int(extracted.get("omittedImages") or 0)
            if omitted_images or (visible_images and result.get("engine") != "ai"):
                result["imageReviewRequired"] = visible_images + omitted_images
                if result.get("engine") == "ai":
                    detail = f"有 {omitted_images} 张图片超出当前单图预算，未送入整理流程；请核对原始文件。"
                else:
                    detail = (f"检测到 {visible_images + omitted_images} 张图片（其中 {omitted_images} 张未提取）；"
                              f"{result.get('materialsPending', 0)} 张已保存为待确认预览，请逐张确认用途；原始文件未修改。")
                result["message"] = str(result.get("message") or "") + " 图片检查：" + detail
            return result
        except HTTPException as exc:
            denied = str(exc.detail).strip()
            if exc.status_code != 403 or denied not in (
                "未登记或未证明无学生数据的 AI 功能，默认拒绝向外部 AI 发送数据",
                TEACHING_DOCUMENT_EGRESS_DENIED_DETAIL,
            ):
                raise
        plan = {
            "title": f"{subject}第{lessonNo}课",
            "coreTarget": "",
            "teacherPlan": extracted["text"],
            "ppt": [],
            "examples": [],
            "closureTraining": "",
            "questions": [],
            "writtenQuestions": [],
            "courseType": courseType,
        }
        result = _apply_lesson_plan(
            db, u, subject, lessonNo, plan, extracted["text"],
            slides_hint=extracted.get("slides") or None,
            use_literal=False,
            overwrite=force == "1",
            source_materials=extracted.get("images") or [], source_file=filename or "pasted-text",
        )
        result["importMode"] = "local"
        result["message"] = (
            "教案原文已在本地保存为草稿。"
            "系统没有自动拆分习题或匹配图片；请在“审改”中核对并补充，"
            "或上传结构化 JSON 整包。"
        )
        visible_images = len(extracted.get("images") or [])
        omitted_images = int(extracted.get("omittedImages") or 0)
        if visible_images or omitted_images:
            result["imageReviewRequired"] = visible_images + omitted_images
            result["message"] += (
                f" 图片检查：检测到 {visible_images + omitted_images} 张图片（其中 {omitted_images} 张超出当前单图预算）；"
                f"其中 {result['materialsPending']} 张已保存为待确认预览，请在导入素材审核中核对；未提取的图片请对照原文件。原始文件未修改。"
            )
        return result

    @router.post("/teacher/weekend/lessons/{lid}/practice/import")
    def import_practice(lid: int, text: str = Form(""), file: UploadFile | None = File(None),
                        u: Any = Depends(current_user), db: Any = Depends(get_db)):
        """只导入随堂练习：单独上传或粘贴第4环节的题，进“随堂练习候选”，不动教案和例题。"""
        need(u, "teacher")
        lesson = my_lesson(db, u, lid)
        subject = lesson.subject
        extracted = _extract_upload(file, text)
        figures = extracted.get("images") or []
        figure_note = ""
        if figures:
            figure_note = f"材料里另外带了 {len(figures)} 张原图，以附图形式一并给你；图片由系统按原题文字匹配，不要猜图片属于哪道题，也不要输出 figureImage 字段。\n"
        p = program(db, int(u.school_id))
        prompt = (
            f"下面是一位小学{p.grade}年级{subject}老师单独发来的随堂练习材料（第4环节用）。请只整理材料里已有的题目，不要编造新题，也不要写成教案。\n"
            f"---练习材料开始---\n{extracted['text']}\n---练习材料结束---\n" + figure_note +
            '只输出 JSON：{"questions":[{"stem":"材料里原有的选择题","options":["A","B","C"],"correctIndex":0,"explanation":"解析","knowledge":"知识点名"}],'
            '"writtenQuestions":[{"type":"short_answer或final_answer或composition","material":"对应完整阅读文章，不含答案","stem":"原有题目，不得改题型或漏题","reference":"参考答案","hints":[]}]}'
            "（本身是选择题的放 questions；填空、判断、计算、简答、阅读、写作放进 writtenQuestions，不要改题型或漏题。答案只写在 explanation/reference 里，不要写进题干。）"
        )
        data = implementation._ai_json(implementation._ai_call(
            db, u, AI_FEATURE, prompt, images=[f["data_url"] for f in figures] or None,
            timeout=150 if figures else 90,
        ))
        attached = _attach_figures(data, figures)
        raw = data if isinstance(data, dict) else {}
        cand = _valid_questions(raw.get("questions"))
        wcand = valid_written_questions(raw.get("writtenQuestions"))
        if not cand and not wcand:
            raise HTTPException(502, "没有从这份材料里识别出题目。请检查文字是否完整，或换一份文件再试。")
        examples = lesson_worked_examples(lesson)
        existing = db.scalars(select(TQ).where(TQ.lesson_id == lesson.id, TQ.stage != REMOVED_STAGE)).all()
        seen = [(q.stem, question_options(q)) for q in existing]
        dropped, kept = 0, []
        for i, q in enumerate(cand):
            if duplicate_of(q["stem"], q["options"], examples, seen):
                dropped += 1
                continue
            seen.append((q["stem"], q["options"]))
            kept.append((i, q))
        for i, q in kept:
            db.add(TQ(school_id=u.school_id, program_id=lesson.program_id, lesson_id=lesson.id, stage="lesson", subject=subject,
                      level=LEVELS[min(i, len(LEVELS) - 1)], knowledge=q["kp"], stem=q["stem"][:300],
                      options_json=json.dumps(q["options"], ensure_ascii=False), correct_index=q["ci"], explanation=q["exp"],
                      active=False, figure_json=json.dumps(q["fig"] or {}, ensure_ascii=False)))
        written_stems = {str(q.stem) for q in written_templates(db, written, u.school_id, u.id, lesson.id)}
        written_dropped = written_kept = 0
        for q in wcand:
            stem = str(q["stem"])
            if stem in written_stems or duplicate_of(stem.split("\n\n")[-1].strip(), [], examples, []):
                written_dropped += 1
                continue
            written_stems.add(stem)
            db.execute(insert(written).values(
                school_id=u.school_id, teacher_id=u.id, lesson_id=lesson.id, session_id=0, stem=stem, reference=q["reference"],
                hints_json=json.dumps({**q.get("extra", {}), "approved": False, "type": q["type"], "hints": q["hints"],
                                       "figure": q.get("figure") or {}}, ensure_ascii=False)))
            written_kept += 1
        db.commit()
        message = f"已导入 {len(kept)} 道选择题、{written_kept} 道填空/简答/写作题，全部是“待审核”，逐题通过后才会在第4环节发放。这节课的教案和例题没有改动。"
        if dropped + written_dropped:
            message += f" 有 {dropped + written_dropped} 道与本节例题或已有题目重复，已自动略过。"
        if figures and attached < len(figures):
            message += f" 有 {len(figures) - attached} 张原图未能与题目唯一核对，没有自动挂上，请老师复核图示。"
        return {"message": message, "choices": len(kept), "written": written_kept,
                "droppedDuplicate": dropped + written_dropped, "attachedFigures": attached,
                "status": lesson_status(db, u, lesson), "summary": practice_summary(db, u, lesson)}

    @router.post("/teacher/weekend/lessons/{lid}/materials/preview")
    def preview_materials(lid: int, text: str = Form(""), file: UploadFile | None = File(None),
                          u: Any = Depends(current_user), db: Any = Depends(get_db)):
        """识别混合资料并按标题/题号提出例题或随堂练习分组建议；不确定条目标为待定，不写入数据库。"""
        need(u, "teacher")
        my_lesson(db, u, lid)
        extracted = _extract_upload(file, text)
        items = suggest_material_groups(extracted["text"])
        if not items:
            raise HTTPException(400, "没有从材料里拆出可识别的条目，请检查内容是否为空")
        counts = {role: sum(1 for item in items if item["role"] == role) for role in ("example", "practice", "pending")}
        return {"items": items, "counts": counts}

    @router.post("/teacher/weekend/lessons/{lid}/materials/apply")
    def apply_materials(lid: int, b: MaterialApplyBody, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        """确认分组后分别写入例题讲解或随堂练习草稿；待定条目绝不默默塞入练习或直接过审。"""
        need(u, "teacher")
        lesson = my_lesson(db, u, lid)
        existing_examples = _lines(lesson.examples_json)
        example_keys = {qg.question_key(x) for x in existing_examples if qg.question_key(x)}
        examples_list = lesson_worked_examples(lesson)
        existing_tq = db.scalars(select(TQ).where(TQ.lesson_id == lesson.id, TQ.stage != REMOVED_STAGE)).all()
        seen_tq = [(q.stem, question_options(q)) for q in existing_tq]
        written_stems = {str(q.stem) for q in written_templates(db, written, u.school_id, u.id, lesson.id)}
        added_examples = added_choices = added_written = dropped_dup = skipped_pending = 0
        for item in b.items:
            txt = str(item.text or "").strip()
            if not txt:
                continue
            if item.role == "pending":
                skipped_pending += 1
                continue
            if item.role == "example":
                key = qg.question_key(txt)
                if key and key in example_keys:
                    dropped_dup += 1
                    continue
                if key:
                    example_keys.add(key)
                existing_examples.append(txt)
                examples_list.append({"label": f"例{len(existing_examples)}", "stem": _worked_example_match_text(txt)})
                added_examples += 1
                continue
            opts = [str(o).strip() for o in (item.options or []) if str(o).strip()]
            if len(opts) >= 2 and item.correctIndex is not None and 0 <= int(item.correctIndex) < len(opts):
                if duplicate_of(txt, opts, examples_list, seen_tq):
                    dropped_dup += 1
                    continue
                seen_tq.append((txt, opts))
                db.add(TQ(
                    school_id=u.school_id, program_id=lesson.program_id, lesson_id=lesson.id,
                    stage="lesson", subject=lesson.subject, level=LEVELS[min(added_choices, len(LEVELS) - 1)],
                    knowledge=(item.knowledge or suggest_knowledge(txt))[:120], stem=txt[:300],
                    options_json=json.dumps(opts, ensure_ascii=False), correct_index=int(item.correctIndex),
                    explanation=item.explanation or "", active=False, figure_json="{}",
                ))
                added_choices += 1
            else:
                if txt in written_stems or duplicate_of(txt.split("\n\n")[-1].strip(), [], examples_list, []):
                    dropped_dup += 1
                    continue
                written_stems.add(txt)
                db.execute(insert(written).values(
                    school_id=u.school_id, teacher_id=u.id, lesson_id=lesson.id, session_id=0,
                    stem=txt, reference=item.reference or "",
                    hints_json=json.dumps({"approved": False, "type": "short_answer", "hints": [], "figure": {}}, ensure_ascii=False),
                ))
                added_written += 1
        if added_examples:
            lesson.examples_json = json.dumps(existing_examples, ensure_ascii=False)
            lesson.updated_at = datetime.utcnow()
        db.commit()
        parts = []
        if added_examples:
            parts.append(f"加入例题讲解 {added_examples} 道（待逐题核对通过）")
        if added_choices + added_written:
            parts.append(f"加入随堂练习草稿 {added_choices + added_written} 道（待逐题审核通过）")
        if skipped_pending:
            parts.append(f"保留待定 {skipped_pending} 条（未写入练习或例题）")
        if dropped_dup:
            parts.append(f"跳过重复 {dropped_dup} 条")
        return {
            "message": "；".join(parts) or "没有可导入的条目。",
            "addedExamples": added_examples,
            "addedChoices": added_choices,
            "addedWritten": added_written,
            "skippedPending": skipped_pending,
            "droppedDuplicate": dropped_dup,
            "status": lesson_status(db, u, lesson),
            "summary": practice_summary(db, u, lesson),
        }

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
    def import_lessons(subject: str = Form(...), force: str = Form("0"), courseType: str = Form(""), files: list[UploadFile] = File(...),
                            u: Any = Depends(current_user), db: Any = Depends(get_db)):
        """Import several lesson plans in one go: each file's 课次 comes from its name (第03课 / lesson-03).
        One bad file never stops the others and every file reports its own result."""
        need(u, "teacher")
        check_subject(subject)
        if subject == "语文" and courseType not in COURSE_TYPES:
            raise HTTPException(409, "语文批量导入请先选择课型；同一批次仅导入同一课型。")
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
                extracted = _extract_upload(item, "")
                if courseType:
                    extracted["courseType"] = courseType
                got = _apply_lesson_extract(db, u, subject, lesson_no, force, extracted, source_file=name)
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
                            "reference": w.reference.strip(), "hints": hints,
                            "figure": w.figure.model_dump(exclude_none=True) if w.figure else {}})
        plan = {"title": item.title.strip(), "coreTarget": item.coreTarget.strip(), "teacherPlan": item.teacherPlan,
                "courseType": item.courseType, "readingPlan": item.readingPlan, "writingPlan": item.writingPlan,
                "ppt": [str(x) for x in item.ppt], "examples": [str(x) for x in item.examples],
                "closureTraining": item.closureTraining, "questions": questions, "writtenQuestions": written}
        if not (plan["title"] or plan["coreTarget"] or plan["examples"] or plan["ppt"] or questions or written):
            raise HTTPException(422, "这一节没有任何内容（title / coreTarget / examples / ppt / 题目 全空）")
        return plan

    def _plan_fingerprint(plan: dict[str, Any]) -> str:
        """Content hash of the payload only; the identity (subject / lessonNo) stays out of it."""
        payload = json.dumps({k: plan.get(k) for k in ("title", "coreTarget", "teacherPlan", "courseType", "readingPlan", "writingPlan", "ppt", "examples",
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
                got = _apply_lesson_plan(
                    db, u, subject, int(job["lessonNo"]), plan, source_text,
                    use_literal=False,
                    overwrite=on_conflict == "overwrite",
                    courseware_pages=job.get("coursewarePages") or [],
                    courseware_replace_existing=True,
                )
                implementation.audit(db, u, "weekend.lessons.import_structured",
                                     f"lesson={job['lessonNo']}:hash={fingerprint[:16]}:chars={len(source_text)}")
                imported += 1
                results.append({**base, "ok": True, "status": "imported", "lessonId": got["lessonId"],
                                "contentHash": fingerprint, "questionsFound": got["questionsFound"],
                                "coursewarePagesFound": got.get("coursewarePagesFound", 0)})
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

    def _import_structured_body(b: StructuredImportBody, u: Any, db: Any) -> dict[str, Any]:
        """Validate one structured envelope, including its optional courseware bundle."""
        check_subject(b.subject)
        if b.schemaVersion != 1:
            raise HTTPException(422, "schemaVersion 只支持 1")
        courseware_pages = b.courseware.pages if b.courseware else []
        if courseware_pages and len(b.items) != 1:
            raise HTTPException(422, "带互动课件的整包一次只能导入一节课")
        jobs: list[dict[str, Any]] = []
        for item in b.items:
            try:
                jobs.append({
                    "lessonNo": item.lessonNo,
                    "plan": _plan_from_body(item),
                    "sourceText": "",
                    "coursewarePages": courseware_pages,
                })
            except HTTPException as exc:
                jobs.append({"lessonNo": item.lessonNo, "plan": None, "error": str(exc.detail)})
        return _import_plans(db, u, b.subject, jobs, dry_run=b.dryRun, on_conflict=b.onConflict)

    @router.post("/teacher/weekend/lessons/import/structured")
    def import_structured(b: StructuredImportBody, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        """Import already-structured lesson plans: no model call, deterministic fields."""
        need(u, "teacher")
        return _import_structured_body(b, u, db)

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

    def debug_classrooms(db: Any, u: Any, lid: int, include_with_records: bool = False) -> list[Any]:
        # Lock before checking evidence. Student submissions use the same session lock.
        rows = db.execute(select(sessions).where(sessions.c.lesson_id == lid)
                          .order_by(sessions.c.id).with_for_update()).all()
        disposable = {"weekend_stage_log", "weekend_slide_state", "weekend_class_rosters", "weekend_written_questions", "weekend_session_questions", "weekend_open_questions"}
        md = implementation.Base.metadata
        for row in rows:
            if row.school_id != u.school_id or row.teacher_id != u.id:
                raise HTTPException(409, "其他老师也有这节课的课堂，不能代为撤销")
            if row.status not in ("planned", "running", "finished"):
                raise HTTPException(409, "课堂状态无法核对，不能按调试课堂撤销")
            if include_with_records:
                continue
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
    def preview_debug_classrooms(lid: int, includeAll: bool = False, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "teacher")
        my_lesson(db, u, lid)
        rows = debug_classrooms(db, u, lid, include_with_records=includeAll)
        return {"items": [{"id": r.id, "title": r.title, "status": r.status} for r in rows]}

    @router.post("/teacher/weekend/lessons/{lid}/cancel-debug-classrooms")
    def cancel_debug_classrooms(lid: int, b: CancelDebugBody, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "teacher")
        lesson = my_lesson(db, u, lid)
        db.execute(select(Lesson.id).where(Lesson.id == lid).with_for_update()).first()
        if not b.confirmed or b.subject != lesson.subject or b.lessonNo != lesson.lesson_no:
            raise HTTPException(400, "请核对学科和课次，并确认没有实际上课，仅为调试")
        rows = debug_classrooms(db, u, lid, include_with_records=b.force)
        ids = [r.id for r in rows]
        if sorted(set(b.sessionIds)) != ids:
            raise HTTPException(409, "课堂列表已变化，请重新预览后确认撤销")
        if not ids:
            return {"message": "没有需要撤销的调试课堂；教案保持不变", "cancelled": 0}
        # Keep a recovery snapshot in the audit log; do not delete lesson templates.
        snapshot = {"lessonId": lid, "force": b.force, "sessions": [dict(r._mapping) for r in rows], "related": {}}
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
        if b.force:
            md = implementation.Base.metadata
            written_subs = md.tables.get("weekend_written_submissions")
            prechecks = md.tables.get("weekend_written_prechecks")
            if written_subs is not None and prechecks is not None:
                sub_ids = db.scalars(select(written_subs.c.id).where(written_subs.c.session_id.in_(ids))).all()
                if sub_ids:
                    snapshot["related"]["weekend_written_prechecks"] = [
                        dict(r._mapping) for r in db.execute(select(prechecks).where(prechecks.c.submission_id.in_(sub_ids)))
                    ]
                    db.execute(delete(prechecks).where(prechecks.c.submission_id.in_(sub_ids)))
            for name, table in md.tables.items():
                if (name.startswith("weekend_") or name.startswith("classroom_")) and "session_id" in table.c:
                    snapshot["related"][name] = [dict(r._mapping) for r in db.execute(select(table).where(table.c.session_id.in_(ids)))]
                    db.execute(delete(table).where(table.c.session_id.in_(ids)))
            reports = md.tables.get("weekend_reports")
            if reports is not None:
                id_strs = {str(sid) for sid in ids}
                rep_rows = db.execute(select(reports).where(reports.c.school_id == u.school_id)).all()
                matched_rep_ids = []
                for rr in rep_rows:
                    parts = [p for p in str(rr.session_key or "").split(",") if p]
                    if any(p in id_strs for p in parts):
                        remaining_parts = [p for p in parts if p not in id_strs]
                        if not remaining_parts:
                            matched_rep_ids.append(rr.id)
                        else:
                            db.execute(update(reports).where(reports.c.id == rr.id).values(session_key=",".join(remaining_parts)))
                if matched_rep_ids:
                    snapshot["related"]["weekend_reports"] = [
                        dict(r._mapping) for r in db.execute(select(reports).where(reports.c.id.in_(matched_rep_ids)))
                    ]
                    db.execute(delete(reports).where(reports.c.id.in_(matched_rep_ids)))
        else:
            for name in ("weekend_stage_log", "weekend_slide_state", "weekend_class_rosters", "weekend_written_questions", "weekend_session_questions", "weekend_open_questions"):
                table = implementation.Base.metadata.tables.get(name)
                if table is not None:
                    snapshot["related"][name] = [dict(r._mapping) for r in db.execute(select(table).where(table.c.session_id.in_(ids)))]
                    db.execute(delete(table).where(table.c.session_id.in_(ids)))
        db.execute(delete(sessions).where(sessions.c.id.in_(ids)))
        implementation.audit(db, u, "weekend.cancel_debug_classrooms", json.dumps(snapshot, ensure_ascii=False, default=str))
        db.commit()
        label = "测试课堂（含作答与反馈记录）" if b.force else "调试课堂"
        return {"message": f"已撤销 {len(ids)} 个{label}，教案和已审核习题保留；现在可以删除教案、重新导入或重新开课", "cancelled": len(ids)}

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
        saved = latest_version(db, lesson)
        return {"previousImportId": saved["id"] if saved and saved["teacher_id"] == u.id else None,
                "id": lesson.id, "title": lesson.title, "coreTarget": lesson.core_target, "teacherPlan": lesson.teacher_plan, "sourceText": lesson.reading_plan or "", "closureTraining": lesson.closure_training,
                "examples": lst(lesson.examples_json), "ppt": lst(lesson.ppt_json)}

    @router.get("/teacher/weekend/lessons/{lid}/imported-materials")
    def imported_materials(lid: int, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        """Teacher-only review queue for embedded source images; students never receive this data."""
        need(u, "teacher")
        lesson = my_lesson(db, u, lid)
        table = workflow_tables["materials"]
        rows = db.execute(select(table).where(
            table.c.school_id == int(u.school_id), table.c.lesson_id == int(lesson.id),
        ).order_by(table.c.sort_order, table.c.id)).all()
        return {"courseType": course_type_for(db, implementation, lesson),
                "items": [{"id": int(row.id), "sourceFile": row.source_file, "sourcePart": row.source_part,
                           "sourceSha256": row.source_sha256, "sourceFormat": row.source_format,
                           "mediaType": row.media_type, "dataUrl": row.data_url, "status": row.status,
                           "relationship": row.relationship, "stageNo": row.stage_no,
                           "sortOrder": int(row.sort_order), "revision": int(row.revision)} for row in rows]}

    @router.put("/teacher/weekend/lessons/{lid}/imported-materials/{material_id}")
    def review_imported_material(lid: int, material_id: int, b: ImportedMaterialReviewBody,
                                 u: Any = Depends(current_user), db: Any = Depends(get_db)):
        """Explicitly bind or ignore an imported picture with optimistic concurrency."""
        need(u, "teacher")
        lesson = my_lesson(db, u, lid)
        if lesson.subject != "语文":
            raise HTTPException(409, "仅语文课使用语文素材关系审核")
        course_type = course_type_for(db, implementation, lesson)
        if course_type not in COURSE_TYPES:
            raise HTTPException(409, "请先选择并保存阅读课或作文课型")
        allowed = {"reading": {1, 2, 3, 4, 5, 6}, "writing": {1, 2, 3, 4, 5, 6}}[course_type]
        if b.status == "confirmed" and (b.stageNo not in allowed or b.relationship == "other"):
            raise HTTPException(422, "确认素材前必须选择流程环节和素材关系")
        if b.status == "confirmed" and course_type == "reading" and b.relationship in {"model_essay", "picture_writing", "writing_method"}:
            raise HTTPException(422, "该素材关系属于作文课")
        if b.status == "confirmed" and course_type == "writing" and b.relationship in {"short_reading", "long_reading", "article_illustration"}:
            raise HTTPException(422, "该素材关系属于阅读课")
        table = workflow_tables["materials"]
        result = db.execute(update(table).where(
            table.c.id == int(material_id), table.c.school_id == int(u.school_id),
            table.c.lesson_id == int(lesson.id), table.c.revision == int(b.expectedRevision),
        ).values(status=b.status, relationship=b.relationship if b.status == "confirmed" else "",
                 stage_no=b.stageNo if b.status == "confirmed" else None, sort_order=b.sortOrder,
                 revision=table.c.revision + 1, reviewed_by=int(u.id), reviewed_at=datetime.utcnow()))
        if result.rowcount != 1:
            db.rollback()
            raise HTTPException(409, "素材审核记录已变化或不存在，请刷新后重试")
        db.commit()
        return {"id": int(material_id), "status": b.status, "revision": int(b.expectedRevision) + 1}

    @router.get("/teacher/weekend/lessons/{lid}/imported-materials/review", response_class=HTMLResponse)
    def imported_materials_review_page(lid: int, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "teacher")
        my_lesson(db, u, lid)
        return HTMLResponse("""<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>导入素材审核</title><main style="max-width:980px;margin:24px auto;padding:16px;font:16px system-ui;color:#172b4d">
<h1>导入素材审核</h1><p id="state">正在读取素材…</p><section id="items"></section></main>
<script>(function(){'use strict';var lid=LOCATION_ID,root=document.getElementById('items'),state=document.getElementById('state');
function node(tag,text){var n=document.createElement(tag);if(text)n.textContent=text;return n}
function api(url,method,body){return fetch(url,{method:method||'GET',credentials:'same-origin',headers:body?{'Content-Type':'application/json'}:{},body:body?JSON.stringify(body):undefined}).then(function(r){return r.json().then(function(d){if(!r.ok)throw Error(d.detail||r.statusText);return d})})}
function load(){api('/teacher/weekend/lessons/'+lid+'/imported-materials').then(function(d){root.textContent='';state.textContent='课型：'+(d.courseType==='reading'?'阅读课':d.courseType==='writing'?'作文课':'待选择课型')+'；素材 '+d.items.length+' 项。待确认素材不会进入学生端。';d.items.forEach(function(x){var card=node('article');card.style.cssText='border:1px solid #d7dee8;border-radius:10px;padding:14px;margin:12px 0';card.appendChild(node('strong',x.sourceFile+' / '+x.sourcePart));card.appendChild(node('p','状态：'+x.status+'；来源 SHA-256：'+x.sourceSha256));var img=node('img');img.src=x.dataUrl;img.alt='导入素材预览';img.style.cssText='display:block;max-width:100%;max-height:440px;margin:10px 0';card.appendChild(img);var rel=node('select');[['short_reading','短文/文章配图'],['long_reading','长文/文章配图'],['article_illustration','阅读文章配图'],['model_essay','范文配图'],['picture_writing','看图写话图片'],['writing_method','写作方法配图'],['task','任务素材'],['question_figure','题目配图']].forEach(function(v){var o=node('option',v[1]);o.value=v[0];rel.appendChild(o)});var stage=node('select');for(var i=1;i<=6;i++){var o=node('option','第'+i+'环节');o.value=String(i);stage.appendChild(o)}var order=node('input');order.type='number';order.min='0';order.max='999';order.value=String(x.sortOrder);order.setAttribute('aria-label','排序');var confirm=node('button','确认绑定');confirm.type='button';confirm.onclick=function(){confirm.disabled=true;api('/teacher/weekend/lessons/'+lid+'/imported-materials/'+x.id,'PUT',{status:'confirmed',relationship:rel.value,stageNo:Number(stage.value),sortOrder:Number(order.value)||0,expectedRevision:x.revision}).then(load).catch(function(e){state.textContent=e.message;confirm.disabled=false})};var ignore=node('button','忽略');ignore.type='button';ignore.style.marginLeft='8px';ignore.onclick=function(){ignore.disabled=true;api('/teacher/weekend/lessons/'+lid+'/imported-materials/'+x.id,'PUT',{status:'ignored',expectedRevision:x.revision}).then(load).catch(function(e){state.textContent=e.message;ignore.disabled=false})};card.appendChild(rel);card.appendChild(stage);card.appendChild(order);card.appendChild(confirm);card.appendChild(ignore);root.appendChild(card)})}).catch(function(e){state.textContent='素材读取失败：'+e.message})}load()})();</script>""".replace("LOCATION_ID", str(int(lid))))

    @router.get("/teacher/weekend/lessons/{lid}/questions")
    def lesson_questions(lid: int, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "teacher")
        lesson = my_lesson(db, u, lid)
        rows = db.scalars(select(TQ).where(TQ.lesson_id == lesson.id, TQ.stage != REMOVED_STAGE).order_by(TQ.id)).all()
        examples = lesson_worked_examples(lesson)
        out = []
        for q in rows:
            opts = question_options(q)
            others = [(o.stem, question_options(o)) for o in rows if o.id != q.id]
            fig = _stored_figure(q)
            out.append({"id": q.id, "stem": q.stem, "options": opts, "correctIndex": q.correct_index, "explanation": q.explanation, "knowledge": q.knowledge,
                        "figure": fig, "mentionsFigure": mentions_figure(q.stem), **lesson_question_number(lesson.reading_plan or "", q.stem), "active": bool(q.active), "level": qg.CODE_LEVEL.get(q.level, ""), "verified": str(q.explanation or "").startswith("验算："),
                        "duplicateOf": duplicate_of(q.stem, opts, examples, others)})
        return {"items": out, "workedExamples": example_items(db, lesson), "summary": practice_summary(db, u, lesson)}

    @router.post("/teacher/weekend/lessons/{lid}/questions")
    def decide_questions(lid: int, b: ApproveBody, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "teacher")
        lesson = my_lesson(db, u, lid)
        if b.approve:
            targets = list(db.scalars(select(TQ).where(TQ.lesson_id == lesson.id, TQ.stage != REMOVED_STAGE, TQ.id.in_(b.approve))))
            examples = lesson_worked_examples(lesson)
            approved = db.scalars(select(TQ).where(TQ.lesson_id == lesson.id, TQ.stage != REMOVED_STAGE,
                                                 TQ.active.is_(True), TQ.id.notin_(b.approve))).all()
            seen = [(q.stem, question_options(q)) for q in approved]
            for q in targets:
                if mentions_figure(q.stem) and not has_figure(_stored_figure(q)) and not b.confirmMissingFigure:
                    raise HTTPException(409, "这道题题干提到了图示（如“如图”），但目前没有配图。请先核对/补充配图，或勾选“确认无配图仍通过”后再通过。")
                dup = duplicate_of(q.stem, question_options(q), examples, seen)
                if dup.startswith("例"):
                    raise HTTPException(409, f"这道随堂练习与本课例题重复（来源：{dup}），请换一道同考点新题后再通过")
                if dup:
                    raise HTTPException(409, "这道随堂练习与本课已通过的习题重复（来源：本课习题），请换一道同考点新题后再通过")
                seen.append((q.stem, question_options(q)))
            db.execute(update(TQ).where(TQ.lesson_id == lesson.id, TQ.stage != REMOVED_STAGE, TQ.id.in_(b.approve)).values(active=True))
        if b.retract:
            # 撤回通过：题留在备课里，但不再进入课堂。第4环节的选择题是每次现查“已通过”的题，
            # 所以正在上的课会当场少一道题、后面题号和已公布答案的序号一起前移；这种情况必须先拦下。
            live = db.scalar(select(sessions.c.id).where(sessions.c.lesson_id == lesson.id,
                                                         sessions.c.status == "running").limit(1))
            if live:
                raise HTTPException(409, "这节课正在上课，撤回会让题目当场从第4环节消失、并打乱已公布答案的顺序。"
                                         "请下课后在审改页撤回，正在上课时请先不要改动已通过的题。")
            db.execute(update(TQ).where(TQ.lesson_id == lesson.id, TQ.stage != REMOVED_STAGE, TQ.id.in_(b.retract)).values(active=False))
        if b.remove:
            db.execute(delete(TQ).where(TQ.lesson_id == lesson.id, TQ.stage != REMOVED_STAGE, TQ.id.in_(b.remove), TQ.active.is_(False)))   # an approved question is never deleted here
        db.commit()
        return lesson_status(db, u, lesson)

    @router.post("/teacher/weekend/lessons/{lid}/examples/review")
    def review_examples(lid: int, b: ExampleReviewBody, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        """例题逐题审核：核对题干、答案、配图后通过；改过内容的题会回到待重新审核。"""
        need(u, "teacher")
        lesson = my_lesson(db, u, lid)
        examples = lesson_worked_examples(lesson)
        targets = set(range(len(examples))) if b.approveAll else set(b.approve)
        retract = set(b.retract) - targets
        if any(not 0 <= int(i) < len(examples) for i in targets | retract):
            raise HTTPException(400, "例题序号超出范围，请刷新页面后重试")
        rows = example_rows(db, lesson.id)
        now = datetime.utcnow()
        for index in sorted(targets):
            values = dict(school_id=u.school_id, lesson_id=lesson.id, teacher_id=u.id, page_index=index,
                          stem_hash=example_review_hash(examples[index]["stem"]), reviewed_at=now)
            if index in rows:
                db.execute(update(example_reviews).where(example_reviews.c.id == rows[index].id).values(**values))
            else:
                db.execute(insert(example_reviews).values(**values))
        for index in sorted(retract):
            if index in rows:
                db.execute(delete(example_reviews).where(example_reviews.c.id == rows[index].id))
        db.commit()
        return {"status": lesson_status(db, u, lesson), "summary": practice_summary(db, u, lesson),
                "workedExamples": example_items(db, lesson),
                "message": f"已更新 {len(targets) + len(retract)} 道例题的审核状态；课件审核与例题审核分开记录。"}

    @router.get("/teacher/weekend/lessons/{lid}/written/questions")
    def lesson_written(lid: int, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "teacher")
        lesson = my_lesson(db, u, lid)
        examples = lesson_worked_examples(lesson)
        choices = db.scalars(select(TQ).where(TQ.lesson_id == lesson.id, TQ.stage != REMOVED_STAGE,
                                               TQ.active.is_(True))).all()
        seen = [(q.stem, question_options(q)) for q in choices]
        items = []
        for q in written_templates(db, written, u.school_id, u.id, lid):
            stem = q.stem.split("\n\n")[-1].strip()
            duplicate = duplicate_of(stem, [], examples, seen)
            meta = template_meta(q)
            items.append({"id": q.id, "stem": q.stem, "reference": q.reference,
                          **lesson_question_number(lesson.reading_plan or "", q.stem),
                          "mentionsFigure": mentions_figure(q.stem),
                          "suggestedKnowledge": suggest_knowledge(q.stem), "duplicateOf": duplicate,
                          **meta})
            seen.append((stem, []))
        return {"goals": lesson_goals(lesson.core_target or ""), "workedExamples": examples, "items": items}

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
        templates = written_templates(db, written, u.school_id, u.id, lid)
        if b.approve:
            examples = lesson_worked_examples(lesson)
            choices = db.scalars(select(TQ).where(TQ.lesson_id == lesson.id, TQ.stage != REMOVED_STAGE,
                                                   TQ.active.is_(True))).all()
            seen = [(q.stem, question_options(q)) for q in choices]
            seen += [(q.stem.split("\n\n")[-1].strip(), [])
                     for q in templates if q.id not in b.approve and template_meta(q).get("approved")]
            for q in templates:
                if q.id not in b.approve:
                    continue
                meta = template_meta(q)
                if mentions_figure(q.stem) and not has_figure(meta.get("figure")) and not b.confirmMissingFigure:
                    raise HTTPException(409, "这道题题干提到了图示（如“如图”），但目前没有配图。请先核对/补充配图，或勾选“确认无配图仍通过”后再通过。")
                stem = q.stem.split("\n\n")[-1].strip()
                duplicate = duplicate_of(stem, [], examples, seen)
                if duplicate.startswith("例"):
                    raise HTTPException(409, f"这道随堂练习与本课例题重复（来源：{duplicate}），请换一道同考点新题后再通过")
                if duplicate:
                    raise HTTPException(409, "这道随堂练习与本课已通过的题目重复，请换一道同考点新题后再通过")
                seen.append((stem, []))
        for q in templates:
            meta = template_meta(q)
            if q.id in b.approve:
                meta["approved"] = True
                db.execute(update(written).where(written.c.id == q.id).values(hints_json=json.dumps(meta, ensure_ascii=False)))
            elif q.id in b.retract and meta.get("approved"):
                meta["approved"] = False
                db.execute(update(written).where(written.c.id == q.id).values(hints_json=json.dumps(meta, ensure_ascii=False)))
            elif q.id in b.remove and not meta.get("approved"):
                db.execute(delete(written).where(written.c.id == q.id))
        db.commit()
        return lesson_status(db, u, lesson)

    @router.get("/teacher/weekend/next")
    def next_up(u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "teacher")
        p = program(db, int(u.school_id))
        out = []
        for subject in SUBJECTS:
            lessons = {int(l.lesson_no): l for l in db.scalars(select(Lesson).where(Lesson.school_id == u.school_id, Lesson.subject == subject)).all()}
            rows = {int(r.lesson_no): r for r in db.execute(select(sched).where(sched.c.teacher_id == u.id, sched.c.subject == subject)).all()}
            configured = {int(w.lesson_no): w for w in db.execute(select(workflows).where(
                workflows.c.school_id == u.school_id, workflows.c.program_id == p.id,
                workflows.c.subject == subject,
            )).all()}
            pending_materials = {}
            if subject == "语文":
                pending_materials = {int(lesson_id): int(count) for lesson_id, count in db.execute(
                    select(workflow_tables["materials"].c.lesson_id, func.count(workflow_tables["materials"].c.id))
                    .where(workflow_tables["materials"].c.school_id == int(u.school_id),
                           workflow_tables["materials"].c.status == "pending")
                    .group_by(workflow_tables["materials"].c.lesson_id)
                ).all()}
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
            st = lesson_status(db, u, l) if l else {
                "lessonId": None, "title": "", "hasPlan": False, "approvedQuestions": 0, "draftQuestions": 0,
                "taught": False, "practiceReady": 0, "coursewareStatus": "", "coursewareApproved": False,
            }
            tips = []
            if not st["hasPlan"]:
                tips.append("还没有教案：可以用 AI 备课草稿")
            if st["approvedQuestions"] == 0 and subject != "语文":
                tips.append("还没有审核通过的习题")
            wf = configured.get(nxt)
            item_course_type = "math" if subject == "数学" else (str(wf.course_type) if wf else None)
            out.append({"subject": subject, "lessonNo": nxt, "schoolWeek": r.school_week if r else None, "schoolUnit": r.school_unit if r else "", "plannedDate": r.planned_date if r else "",
                        **st, "weakKnowledge": weak_knowledge(db, u, subject), "tips": tips,
                        "courseType": item_course_type,
                        "workflowRevision": int(wf.revision) if wf else 0,
                        "workflowLabel": {"math": "数学七环节", "reading": "阅读课", "writing": "作文课"}.get(item_course_type, "待选择课型"),
                        "pendingMaterials": pending_materials.get(int(l.id), 0) if l else 0})
        return {"items": out}

    app.include_router(router)
    app.state.weekend_plan_installed = True
    app.state.weekend_plan_router = router
    return router


__all__ = ["install_weekend_plan", "register_plan_tables", "register_example_review_table", "example_review_hash"]


