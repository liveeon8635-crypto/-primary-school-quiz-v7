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


def language_question_text(question: Any) -> str:
    text = str(getattr(question, "text", "") or "").strip()
    subject = str(getattr(question, "subject", "") or "").strip()
    qtype = str(getattr(question, "question_type", "") or "").strip().lower()

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
        payload["text"] = language_question_text(question)
        return payload

    @wraps(original_teacher)
    def teacher_question(question):
        payload = dict(original_teacher(question))
        payload["text"] = language_question_text(question)
        return payload

    implementation.qj_public = public_question
    implementation.qj = teacher_question
    app.state.language_question_quality_installed = True


__all__ = ["install_language_question_quality", "language_question_text"]
