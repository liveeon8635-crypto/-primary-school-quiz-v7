"""Question selection helpers for teacher-created student tests and practice."""

from __future__ import annotations

import json
from collections import defaultdict
from typing import Any, Iterable


def is_online_question(question: Any) -> bool:
    """Return whether a legacy Question can be answered by the online quiz UI."""
    try:
        options = json.loads(question.options_json or "[]")
        correct_index = int(question.correct_index)
    except (TypeError, ValueError, json.JSONDecodeError):
        return False
    return (
        isinstance(options, list)
        and len(options) >= 2
        and 0 <= correct_index < len(options)
    )


def valid_online_questions(rows: Iterable[Any]) -> list[Any]:
    return [row for row in rows if is_online_question(row)]


def question_catalog(rows: Iterable[Any]) -> list[dict[str, Any]]:
    """Summarize available online questions by grade, subject, and knowledge module."""
    grouped: dict[tuple[int, str], list[Any]] = defaultdict(list)
    for row in valid_online_questions(rows):
        grouped[(int(row.grade), str(row.subject or "").strip())].append(row)

    catalog: list[dict[str, Any]] = []
    for (grade, subject), questions in sorted(grouped.items()):
        module_counts: dict[str, int] = defaultdict(int)
        for question in questions:
            name = str(question.knowledge or "").strip()
            if name:
                module_counts[name] += 1
        catalog.append(
            {
                "grade": grade,
                "subject": subject,
                "questionCount": len(questions),
                "modules": [
                    {"name": name, "questionCount": count}
                    for name, count in sorted(module_counts.items())
                ],
            }
        )
    return catalog


def select_auto_practice_questions(
    rows: Iterable[Any],
    *,
    mode: str,
    count: int,
    knowledge: str = "",
) -> list[Any]:
    """Select deterministic questions, balancing comprehensive tests across modules."""
    count = max(1, min(int(count), 30))
    questions = sorted(valid_online_questions(rows), key=lambda row: int(row.id))
    mode = (mode or "").strip().lower()

    if mode == "knowledge":
        target = (knowledge or "").strip()
        if not target:
            return []
        return [
            row
            for row in questions
            if str(row.knowledge or "").strip() == target
        ][:count]

    if mode != "comprehensive":
        return []

    buckets: dict[str, list[Any]] = defaultdict(list)
    for row in questions:
        key = (
            str(row.knowledge or "").strip()
            or str(row.unit or "").strip()
            or "综合"
        )
        buckets[key].append(row)

    selected: list[Any] = []
    keys = sorted(buckets)
    index = 0
    while len(selected) < count and keys:
        next_keys: list[str] = []
        for key in keys:
            bucket = buckets[key]
            if index < len(bucket):
                selected.append(bucket[index])
                if len(selected) >= count:
                    break
            if index + 1 < len(bucket):
                next_keys.append(key)
        if len(selected) >= count:
            break
        index += 1
        keys = next_keys

    return selected


__all__ = [
    "is_online_question",
    "question_catalog",
    "select_auto_practice_questions",
    "valid_online_questions",
]
