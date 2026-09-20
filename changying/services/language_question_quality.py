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
from changying.services.builtin_question_bank_english import grade5_english_specs


def _derived_fill_core(subject: str, text: str) -> str:
    raw = str(text or "").strip()
    if subject == "语文":
        candidate_prefix = "请从备选答案中选择，并输入完整答案："
        if raw.startswith(candidate_prefix):
            core = raw[len(candidate_prefix):].strip()
            return re.split(r"\s*备选答案：", core, maxsplit=1)[0].strip()
        prefixes = ("请直接填写答案：",)
    else:
        prefixes = ("Write the answer:", "Complete with the correct answer:")
    for prefix in prefixes:
        if raw.lower().startswith(prefix.lower()):
            return raw[len(prefix):].strip()
    return raw


def _safe_exact_english_fill(stem: str, answer: str) -> bool:
    """Allow free typing only when the missing token has an objective boundary."""
    text = str(stem or "").strip()
    value = str(answer or "").strip()
    if "____" not in text:
        return False
    if text.startswith("—"):
        return False
    return bool(re.fullmatch(r"[A-Za-z]+(?:'[A-Za-z]+)?", value))


def language_choice_repair(question: Any) -> dict[str, Any] | None:
    """Restore choice controls for unsafe fills mechanically derived from language MCQs.

    A mechanically-derived language fill must not become exact-string grading
    when the original item was reviewed as multiple choice. Chinese baseline
    fills are therefore restored to their original choice shape. English keeps
    only objective one-token cloze items as free text; semantic responses,
    dialogue completions and sentence-level answers are restored to choices.
    Genuine teacher/AI free-text questions that do not match the reviewed bank
    remain untouched.
    """

    subject = str(getattr(question, "subject", "") or "").strip()
    if subject not in {"语文", "英语"}:
        return None
    if str(getattr(question, "question_type", "") or "").strip().lower() != "fill_blank":
        return None

    knowledge = str(getattr(question, "knowledge", "") or "").strip()
    core = _derived_fill_core(
        subject,
        str(getattr(question, "text", "") or "").strip(),
    )
    stored_answer = _answer(question)
    specs = grade5_chinese_specs() if subject == "语文" else grade5_english_specs()

    for row in specs:
        if str(row.get("knowledge") or "").strip() != knowledge:
            continue
        if str(row.get("text") or "").strip() != core:
            continue
        options = [str(x) for x in (row.get("options") or [])]
        correct_index = int(row.get("correct_index", -1))
        if len(options) < 2 or not (0 <= correct_index < len(options)):
            continue
        if stored_answer and options[correct_index].strip() != stored_answer:
            continue
        if subject == "英语" and _safe_exact_english_fill(core, stored_answer):
            return None
        return {
            "text": core,
            "options": options,
            "correct_index": correct_index,
        }
    return None


def chinese_choice_repair(question: Any) -> dict[str, Any] | None:
    """Backward-compatible Chinese-only wrapper used by existing tests/callers."""
    if str(getattr(question, "subject", "") or "").strip() != "语文":
        return None
    return language_choice_repair(question)


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


def _normalized_family_text(value: Any) -> str:
    text = re.sub(r"\s+", " ", str(value or "").strip())
    return text.rstrip("?？").strip()


def _family_signature(
    subject: str,
    knowledge: str,
    text: str,
    options: list[str],
) -> str:
    return "|".join(
        [
            str(subject or "").strip(),
            str(knowledge or "").strip(),
            _normalized_family_text(text),
            json.dumps([str(x).strip() for x in options], ensure_ascii=False),
        ]
    )


def _baseline_rows(subject: str) -> list[dict[str, Any]]:
    if subject == "语文":
        return grade5_chinese_specs()
    if subject == "英语":
        return grade5_english_specs()
    return []


def language_semantic_family_fields(
    *,
    subject: str,
    knowledge: str,
    text: str,
    options: list[str] | None = None,
    correct_index: int = -1,
    question_type: str = "",
    answer: str = "",
) -> str:
    """Return a source-aware content family for language-practice de-duplication.

    Generic stems such as “下列句子没有语病的一项是？” are not enough to identify
    content: different option sets are genuinely different questions. Derived
    fill / true-false variants are mapped back to the exact reviewed source item
    when possible, so only re-skinned copies of the same source are mutually
    exclusive inside one paper.
    """

    subject = str(subject or "").strip()
    knowledge = str(knowledge or "").strip()
    text = str(text or "").strip()
    values = [str(x) for x in (options or [])]
    qtype = str(question_type or "").strip().lower()
    try:
        correct_index = int(correct_index)
    except Exception:
        correct_index = -1

    if subject not in {"语文", "英语"}:
        suffix = values or ([f"answer:{str(answer or '').strip()}"] if str(answer or "").strip() else [])
        return _family_signature(subject, knowledge, text, suffix)

    baseline = _baseline_rows(subject)

    if qtype == "fill_blank":
        core = _derived_fill_core(subject, text)
        stored = str(answer or "").strip()
        for row in baseline:
            if str(row.get("knowledge") or "").strip() != knowledge:
                continue
            if _normalized_family_text(row.get("text")) != _normalized_family_text(core):
                continue
            source_options = [str(x) for x in (row.get("options") or [])]
            source_correct = int(row.get("correct_index", -1))
            if not (0 <= source_correct < len(source_options)):
                continue
            if stored and source_options[source_correct].strip() != stored:
                continue
            return _family_signature(subject, knowledge, str(row.get("text") or ""), source_options)

    claimed = ""
    source_stem = ""
    if qtype == "true_false":
        if subject == "语文":
            prefix = "判断下面的作答是否正确："
            if text.startswith(prefix) and "——" in text[len(prefix):]:
                source_stem, claimed = text[len(prefix):].rsplit("——", 1)
            else:
                match = re.fullmatch(r"判断正误：题目“(.+)”的答案是“(.+)”。", text)
                if match:
                    source_stem, claimed = match.group(1), match.group(2)
        else:
            prefix = "Is this answer correct?"
            if text.startswith(prefix) and "—" in text[len(prefix):]:
                source_stem, claimed = text[len(prefix):].rsplit("—", 1)
            else:
                match = re.fullmatch(
                    r'True or false:\s*For\s+"(.+)",\s*the answer is\s*"(.+)"\.',
                    text,
                    flags=re.IGNORECASE,
                )
                if match:
                    source_stem, claimed = match.group(1), match.group(2)

        if source_stem and claimed:
            source_stem = source_stem.strip()
            claimed = claimed.strip().rstrip("。")
            truth_is_correct = None
            if correct_index in (0, 1):
                truth_is_correct = correct_index == 0
            for row in baseline:
                if str(row.get("knowledge") or "").strip() != knowledge:
                    continue
                if _normalized_family_text(row.get("text")) != _normalized_family_text(source_stem):
                    continue
                source_options = [str(x) for x in (row.get("options") or [])]
                source_correct = int(row.get("correct_index", -1))
                for index, value in enumerate(source_options):
                    if value.strip().rstrip("。") != claimed:
                        continue
                    claim_is_correct = index == source_correct
                    if truth_is_correct is not None and claim_is_correct != truth_is_correct:
                        continue
                    return _family_signature(
                        subject,
                        knowledge,
                        str(row.get("text") or ""),
                        source_options,
                    )

    if values:
        return _family_signature(subject, knowledge, text, values)
    stored = str(answer or "").strip()
    return _family_signature(
        subject,
        knowledge,
        text,
        [f"answer:{stored}"] if stored else [],
    )


def language_semantic_family(question: Any) -> str:
    try:
        options = json.loads(getattr(question, "options_json", "[]") or "[]")
    except Exception:
        options = []
    if not isinstance(options, list):
        options = []
    return language_semantic_family_fields(
        subject=str(getattr(question, "subject", "") or ""),
        knowledge=str(getattr(question, "knowledge", "") or ""),
        text=str(getattr(question, "text", "") or ""),
        options=[str(x) for x in options],
        correct_index=int(getattr(question, "correct_index", -1) or -1),
        question_type=str(getattr(question, "question_type", "") or ""),
        answer=_answer(question),
    )


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


def _fill_chinese_blanks(stem: str, claimed: str) -> str:
    text = str(stem or "").strip()
    value = str(claimed or "").strip()
    blanks = re.findall(r"_{2,}", text)
    parts = [part.strip() for part in re.split(r"…{2,}|\.{3,}", value) if part.strip()]
    if len(blanks) >= 2 and len(parts) >= len(blanks):
        for part in parts[: len(blanks)]:
            text = re.sub(r"_{2,}", part, text, count=1)
        return text
    return re.sub(r"_{2,}", value, text, count=1)


def _natural_chinese_true_false(stem: str, claimed: str, knowledge: str = "") -> str:
    """Turn a derived MCQ claim into a standalone judgement statement."""
    source = str(stem or "").strip().rstrip("?？")
    claim = str(claimed or "").strip().rstrip("。")
    topic = str(knowledge or "").strip()

    if "书写完全正确" in source:
        return f"判断：“{claim}”中的词语书写全部正确。"

    if "没有语病" in source:
        return f"判断：句子“{claim}”没有语病。"

    if "标点使用正确" in source:
        return f"判断：句子“{claim}”的标点使用正确。"

    if "主要运用了什么修辞手法" in source:
        example = source.split("主要运用了什么修辞手法", 1)[0].strip()
        return f"判断：{example}主要运用了“{claim}”的修辞手法。"

    if "正确读音是" in source:
        prefix = source.split("的正确读音是", 1)[0].strip()
        return f"判断：{prefix}读作“{claim}”。"

    if "填入最恰当的成语是" in source or topic == "成语运用":
        base = re.sub(r"[。.]?\s*填入最恰当的成语是\s*$", "", source).strip()
        filled = _fill_chinese_blanks(base, claim).rstrip("。")
        return f"判断：句子“{filled}。”中的成语使用恰当。"

    if any(marker in source for marker in ("最连贯的一项", "选择最连贯", "选择最恰当的一句", "填在横线上")):
        return f"判断：将“{claim}”填入横线后，上下文衔接连贯。"

    if "____" in source:
        filled = _fill_chinese_blanks(source, claim)
        return f"判断：补充后的表达“{filled}”正确。"

    if "意思" in source:
        quoted = re.findall(r"“([^”]+)”", source)
        term = quoted[-1] if quoted else ""
        if term:
            return f"判断：在题目语境中，“{term}”的意思是“{claim}”。"

    return f"判断：针对“{source}”，结论“{claim}”成立。"


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
        legacy = re.fullmatch(r"判断正误：题目“(.+)”的答案是“(.+)”。", text)
        if legacy:
            stem, claimed = legacy.group(1).strip(), legacy.group(2).strip()
            return _natural_chinese_true_false(
                stem,
                claimed,
                str(getattr(question, "knowledge", "") or ""),
            )
        prefix = "判断下面的作答是否正确："
        if text.startswith(prefix) and "——" in text[len(prefix):]:
            stem, claimed = text[len(prefix):].rsplit("——", 1)
            return _natural_chinese_true_false(
                stem.strip(),
                claimed.strip(),
                str(getattr(question, "knowledge", "") or ""),
            )

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
        repaired = language_choice_repair(question)
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
        repaired = language_choice_repair(question)
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
            repaired = language_choice_repair(question) if question is not None else None
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


__all__ = [
    "chinese_choice_repair",
    "language_choice_repair",
    "language_semantic_family",
    "language_semantic_family_fields",
    "install_language_question_quality",
    "language_question_text",
]
