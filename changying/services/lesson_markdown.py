"""Deterministic parser for the teacher-facing weekend-plan Markdown convention.

Eight markers only, and no model call anywhere::

    # 第03课：圆的面积        optional; supplies the lesson number and the title
    ## 本节目标
    ## 教学流程
    ## 例题                  worked examples (teacher-facing; pupils never answer them)
    ## 课后练习              becomes choice questions and written questions
    1. 题干 / C1. 题干       starts a question
    【答案】 / 【解析】      block anchors inside a question

A question with two or more option lines (``A.`` / ``B.`` …) is a choice question;
anything else is a written question. Lines outside the convention are kept as text,
so one stray line never rejects the whole file.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any

_HEADING = re.compile(r"^(#{1,6})\s*(.+?)\s*$")
_LESSON = re.compile(r"第\s*(\d{1,2})\s*课")
_OPTION_LINE = re.compile(r"^([A-Ha-h])\s*[.．、]\s*(.*)$")
_NUMBER_LINE = re.compile(r"^(?:C)?(\d{1,2})\s*[.．、]\s*(.*)$")
_ANSWER = re.compile(r"^【\s*答案\s*】\s*(.*)$")
_EXPLAIN = re.compile(r"^【\s*解析\s*】\s*(.*)$")
_ANSWER_LETTER = re.compile(r"^\s*([A-Ha-h])")

SECTION_FIELDS = {"本节目标": "core", "教学流程": "flow", "例题": "examples", "课后练习": "practice"}


def normalize(text: str) -> str:
    """Unified newlines and zero-width characters removed. Punctuation is left alone.

    NFKC is deliberately NOT applied here: it turns 全角，： into ,: and would rewrite the
    teacher's own text. It is only used by ``canonical`` for hashing.
    """
    clean = str(text or "").replace("\r\n", "\n").replace("\r", "\n")
    for invisible in ("\u200b", "\u200c", "\u200d", "\ufeff"):
        clean = clean.replace(invisible, "")
    return clean


def canonical(text: str) -> str:
    """Fold full-width forms and collapse whitespace; for content hashing only."""
    return " ".join(unicodedata.normalize("NFKC", normalize(text)).split())


def _render(stem: str, options: list[str], answer: str, explanation: str) -> str:
    lines = [stem]
    lines.extend(f"{chr(ord('A') + i)}. {option}" for i, option in enumerate(options))
    if answer:
        lines.append("【答案】" + answer)
    if explanation:
        lines.append("【解析】" + explanation)
    return "\n".join(lines)


def _choice_index(answer: str) -> int:
    match = _ANSWER_LETTER.match(answer or "")
    if not match:
        raise ValueError("选择题的【答案】要写选项字母（A / B / C …）")
    return ord(match.group(1).upper()) - ord("A")


def parse(text: str, *, max_lesson: int = 18) -> dict[str, Any]:
    """Parse one lesson plan. Raises ``ValueError`` (Chinese message) when unusable."""
    body = normalize(text)
    if len(body.strip()) < 20:
        raise ValueError("内容不足 20 字，没法解析")

    lesson_no: int | None = None
    title = ""
    core: list[str] = []
    flow: list[str] = []
    practice: list[str] = []
    examples: list[str] = []
    questions: list[dict[str, Any]] = []
    written: list[dict[str, Any]] = []
    prose: list[str] = []

    section: str | None = None
    question: dict[str, Any] | None = None
    bucket = "stem"

    def flush_question() -> None:
        nonlocal question
        if question is None:
            return
        stem = question["stem"].strip()
        options = question["options"]
        answer = question["answer"].strip()
        explanation = question["explanation"].strip()
        question = None
        if not stem:
            return
        if len(options) >= 2:
            index = _choice_index(answer)
            if index >= len(options):
                raise ValueError(f"【答案】里的 {chr(ord('A') + index)} 不在本题选项内（共 {len(options)} 个）：{stem[:30]}")
            if section == "practice":
                questions.append({"stem": stem, "options": options, "correctIndex": index,
                                  "explanation": explanation, "knowledge": ""})
            else:
                examples.append(_render(stem, options, chr(ord("A") + index), explanation))
            return
        if options:
            raise ValueError(f"选择题至少要两个选项：{stem[:30]}")
        if section == "practice":
            written.append({"type": "short_answer", "material": "", "stem": stem,
                            "reference": answer or explanation, "hints": []})
        else:
            examples.append(_render(stem, [], answer, explanation))

    def flush_section() -> None:
        flush_question()
        if section == "examples" and prose and not examples:
            merged = "\n".join(x for x in prose if x).strip()
            if merged:
                examples.append(merged)
        prose.clear()

    for raw in body.splitlines():
        line = raw.strip()
        heading = _HEADING.match(line)
        if heading:
            flush_section()
            level, name = len(heading.group(1)), heading.group(2).strip()
            if level == 1:
                match = _LESSON.search(name)
                if match:
                    value = int(match.group(1))
                    if 1 <= value <= max_lesson:
                        lesson_no = value
                    name = _LESSON.sub("", name).lstrip("：:、 ")
                title = name.strip() or title
                section = None
            else:
                section = next((SECTION_FIELDS[key] for key in SECTION_FIELDS if name.startswith(key)), None)
                if section == "practice":
                    practice.append(name)
            continue

        if section == "core":
            core.append(line)
            continue
        if section == "flow":
            flow.append(line)
            continue
        if section == "practice":
            practice.append(line)
        if section not in ("examples", "practice"):
            continue

        answer = _ANSWER.match(line)
        if answer:
            if question is None:
                raise ValueError("【答案】前面没有题目")
            bucket = "answer"
            question["answer"] = answer.group(1)
            continue
        explain = _EXPLAIN.match(line)
        if explain:
            if question is None:
                raise ValueError("【解析】前面没有题目")
            bucket = "explanation"
            question["explanation"] = explain.group(1)
            continue
        option = _OPTION_LINE.match(line)
        if option and question is not None and bucket == "stem":
            question["options"].append(option.group(2).strip())
            continue
        numbered = _NUMBER_LINE.match(line)
        if numbered:
            flush_question()
            question = {"stem": numbered.group(2).strip(), "options": [], "answer": "", "explanation": ""}
            bucket = "stem"
            continue
        if question is not None and line:
            if bucket == "stem":
                question["stem"] += "\n" + line
            elif bucket in ("answer", "explanation"):
                question[bucket] += "\n" + line
            continue
        if line:
            prose.append(line)

    flush_section()

    plan: dict[str, Any] = {
        "lessonNo": lesson_no,
        "title": title,
        "coreTarget": "\n".join(x for x in core if x).strip(),
        "teacherPlan": "\n".join(x for x in flow if x).strip(),
        "examples": examples,
        "closureTraining": "\n".join(x for x in practice if x).strip(),
        "questions": questions,
        "writtenQuestions": written,
    }
    if not (plan["coreTarget"] or plan["teacherPlan"] or plan["examples"] or plan["questions"] or plan["writtenQuestions"]):
        raise ValueError("没识别出任何标准小节（本节目标 / 教学流程 / 例题 / 课后练习），请按约定书写")
    return plan
