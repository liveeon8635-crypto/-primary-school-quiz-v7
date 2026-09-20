"""Language-question wording quality repair.

Some mixed-type variants are derived from reviewed multiple-choice items. This
module keeps those variants usable without rewriting historical question rows:
- generic option-dependent fill prompts are converted into a real cloze when
  the stored standard answer makes that possible;
- generated judgement wording is made natural while keeping the same truth
  value and answer key.

The repair only changes serialized question text, never grading data.
"""

from __future__ import annotations

import json
import re
from functools import wraps
from types import ModuleType
from typing import Any

from changying.services.builtin_question_bank_chinese import grade5_chinese_specs


_CHINESE_CHOICE_LIKE_KNOWLEDGE = {
    "字形辨析",
    "病句辨析",
    "标点符号",
    "句子衔接",
    "概括主要内容",
    "阅读推断",
    "资料整合",
    "习作修改",
}


def chinese_choice_repair(question: Any) -> dict[str, Any] | None:
    """Restore choice controls for Chinese variants whose stems still ask for a choice."""

    if str(getattr(question, "subject", "") or "").strip() != "语文":
        return None
    if str(getattr(question, "question_type", "") or "").strip().lower() != "fill_blank":
        return None
    knowledge = str(getattr(question, "knowledge", "") or "").strip()
    if knowledge not in _CHINESE_CHOICE_LIKE_KNOWLEDGE:
        return None

    text = str(getattr(question, "text", "") or "").strip()
    prefix = "请直接填写答案："
    core = text[len(prefix):].strip() if text.startswith(prefix) else text
    for row in grade5_chinese_specs():
        if str(row.get("knowledge") or "").strip() != knowledge:
            continue
        if str(row.get("text") or "").strip() != core:
            continue
        options = [str(x) for x in (row.get("options") or [])]
        correct_index = int(row.get("correct_index", -1))
        if len(options) >= 2 and 0 <= correct_index < len(options):
            return {
                "text": core,
                "options": options,
                "correct_index": correct_index,
            }
    return None


_ENGLISH_AUX = {
    "am", "is", "are", "was", "were", "do", "does", "did",
    "have", "has", "had", "can", "could", "should", "would",
    "will", "may", "must",
}


def _answer(question: Any) -> str:
    try:
        data = json.loads(getattr(question, "answer_json", "{}") or "{}")
    except Exception:
        data = {}
    return str(data.get("answer") or "").strip() if isinstance(data, dict) else ""


def _english_cloze_from_answer(answer: str) -> str:
    words = re.findall(r"[A-Za-z]+(?:'[A-Za-z]+)?|[^A-Za-z\s]+", answer)
    alpha_positions = [i for i, token in enumerate(words) if re.fullmatch(r"[A-Za-z]+(?:'[A-Za-z]+)?", token)]
    if len(alpha_positions) < 2:
        return ""

    blank_at = None
    for i in alpha_positions:
        if words[i].lower() in _ENGLISH_AUX:
            blank_at = i
            break
    if blank_at is None:
        blank_at = alpha_positions[-1]

    words[blank_at] = "____"
    text = " ".join(words)
    text = re.sub(r"\s+([,.!?;:])", r"\1", text)
    return text





def _option_dependent_chinese_stem(stem: str) -> bool:
    text = str(stem or "").strip()
    markers = (
        "下列",
        "哪项",
        "哪一项",
        "一项是",
        "最恰当的一项",
        "最符合",
        "选择最",
    )
    return any(marker in text for marker in markers)


def _chinese_source_options(stem: str, knowledge: str = "") -> list[str]:
    target = str(stem or "").strip()
    target_knowledge = str(knowledge or "").strip()
    for row in grade5_chinese_specs():
        if str(row.get("text") or "").strip() != target:
            continue
        if target_knowledge and str(row.get("knowledge") or "").strip() != target_knowledge:
            continue
        options = row.get("options")
        if isinstance(options, list) and len(options) >= 2:
            return [str(x) for x in options]
    return []


def _inline_candidates(options: list[str]) -> str:
    labels = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    return "；".join(
        f"{labels[i]}. {value}" for i, value in enumerate(options[: len(labels)])
    )

def language_question_text(question: Any) -> str:
    text = str(getattr(question, "text", "") or "").strip()
    subject = str(getattr(question, "subject", "") or "").strip()
    qtype = str(getattr(question, "question_type", "") or "").strip().lower()

    if subject == "语文" and qtype == "fill_blank":
        prefix = "请直接填写答案："
        if text.startswith(prefix):
            core = text[len(prefix):].strip()
            if _option_dependent_chinese_stem(core):
                options = _chinese_source_options(
                    core,
                    str(getattr(question, "knowledge", "") or ""),
                )
                if options:
                    return (
                        f"请从备选答案中选择，并输入完整答案：{core} "
                        f"备选答案：{_inline_candidates(options)}"
                    )

    if subject == "英语" and qtype == "fill_blank":
        prefix = "Complete with the correct answer:"
        if text.lower().startswith(prefix.lower()):
            core = text[len(prefix):].strip()
            if core.lower().rstrip(".") in {
                "choose the correct sentence",
                "choose the correct answer",
            }:
                cloze = _english_cloze_from_answer(_answer(question))
                if cloze:
                    return f"Complete the sentence: {cloze}"

    if subject == "英语" and qtype == "true_false":
        match = re.fullmatch(
            r'True or false:\s*For\s+"(.+)",\s*the answer is\s*"(.+)"\.',
            text,
            flags=re.IGNORECASE,
        )
        if match:
            stem, claimed = match.group(1).strip(), match.group(2).strip()
            return f"Is this answer correct? {stem} — {claimed}"

    if subject == "语文" and qtype == "true_false":
        match = re.fullmatch(r"判断正误：题目“(.+)”的答案是“(.+)”。", text)
        if match:
            stem, claimed = match.group(1).strip(), match.group(2).strip()
            return f"判断下面的作答是否正确：{stem} —— {claimed}"

    return text


def install_language_question_quality(implementation: ModuleType) -> None:
    app = implementation.app
    if getattr(app.state, "language_question_quality_installed", False):
        return

    original_public = implementation.qj_public
    original_teacher = implementation.qj

    @wraps(original_public)
    def public_question(question):
        payload = dict(original_public(question))
        repaired = chinese_choice_repair(question)
        if repaired:
            payload["text"] = repaired["text"]
            payload["options"] = repaired["options"]
            payload["questionType"] = "single_choice"
        else:
            payload["text"] = language_question_text(question)
        return payload

    @wraps(original_teacher)
    def teacher_question(question):
        payload = dict(original_teacher(question))
        repaired = chinese_choice_repair(question)
        if repaired:
            payload["text"] = repaired["text"]
            payload["options"] = repaired["options"]
            payload["questionType"] = "single_choice"
            payload["correctIndex"] = repaired["correct_index"]
        else:
            payload["text"] = language_question_text(question)
        return payload

    original_grade_answers = implementation.grade_answers

    @wraps(original_grade_answers)
    def grade_answers(db, user, answers, allowed_question_ids=None, require_all=False):
        transformed = []
        for answer in answers:
            question = db.scalar(
                implementation.select(implementation.Question).where(
                    implementation.Question.id == answer.question_id,
                    implementation.Question.school_id == user.school_id,
                )
            )
            repaired = chinese_choice_repair(question) if question is not None else None
            if repaired and answer.selected_index is not None:
                idx = int(answer.selected_index)
                if idx < 0 or idx >= len(repaired["options"]):
                    raise implementation.HTTPException(400, "答案选项无效")
                transformed.append(
                    answer.model_copy(
                        update={
                            "selected_index": None,
                            "text_answer": repaired["options"][idx],
                        }
                    )
                )
            else:
                transformed.append(answer)
        return original_grade_answers(
            db,
            user,
            transformed,
            allowed_question_ids=allowed_question_ids,
            require_all=require_all,
        )

    implementation.qj_public = public_question
    implementation.qj = teacher_question
    implementation.grade_answers = grade_answers
    app.state.language_question_quality_installed = True


__all__ = ["chinese_choice_repair", "install_language_question_quality", "language_question_text"]
