"""Deterministic mixed question metadata for built-in online practice.

The baseline bank historically stored every generated item as multiple choice.
This module upgrades the Grade 5 math pack into the online auto-graded question
types already supported by the student quiz flow without changing curriculum
scope or database schema.
"""

from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from typing import Any

AUTO_GRADED_TYPES = (
    "single_choice",
    "true_false",
    "fill_blank",
    "calculation",
    "short_answer",
)


def _answer_from_choice(spec: dict[str, Any]) -> str:
    options = list(spec.get("options") or [])
    try:
        index = int(spec.get("correct_index", -1))
    except Exception:
        index = -1
    if 0 <= index < len(options):
        return str(options[index])
    return ""


def enrich_grade5_math_specs(specs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return curriculum-identical specs with deterministic mixed online types.

    Each knowledge module cycles through the five supported online types. This
    keeps comprehensive and module practice varied while retaining exact source
    answers and explanations.
    """

    counters: dict[str, int] = defaultdict(int)
    enriched: list[dict[str, Any]] = []

    for original in specs:
        item = deepcopy(original)
        knowledge = str(item.get("knowledge") or "")
        offset = counters[knowledge]
        counters[knowledge] += 1
        question_type = AUTO_GRADED_TYPES[offset % len(AUTO_GRADED_TYPES)]
        source_answer = _answer_from_choice(item)

        item["question_type"] = question_type
        item["answer"] = source_answer
        item["accepted_answers"] = [source_answer] if source_answer else []
        item["figure"] = {}

        if question_type == "single_choice":
            enriched.append(item)
            continue

        if question_type == "true_false":
            options = list(item.get("options") or [])
            correct_index = int(item.get("correct_index", 0))
            use_correct = (offset // len(AUTO_GRADED_TYPES)) % 2 == 0
            proposed = source_answer
            if not use_correct and options:
                proposed = str(options[(correct_index + 1) % len(options)])
            stem = str(item.get("text") or "").rstrip("？?")
            item["text"] = f"{stem}。判断：结果为 {proposed}。"
            item["options"] = ["正确", "错误"]
            item["correct_index"] = 0 if use_correct else 1
            item["answer"] = "正确" if use_correct else "错误"
            item["accepted_answers"] = [item["answer"]]
            enriched.append(item)
            continue

        item["options"] = []
        item["correct_index"] = -1
        if question_type == "fill_blank":
            item["text"] = f"{str(item.get('text') or '').rstrip('？?')}（填空）"
        elif question_type == "calculation":
            item["text"] = f"{str(item.get('text') or '').rstrip('？?')}（写出计算结果）"
        else:
            item["text"] = f"{str(item.get('text') or '').rstrip('？?')}（写出答案）"
        enriched.append(item)

    return enriched


__all__ = ["AUTO_GRADED_TYPES", "enrich_grade5_math_specs"]
