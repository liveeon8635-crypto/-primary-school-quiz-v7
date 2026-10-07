"""Server-side paper composition for online assignments.

Feedback (刘麦迪, 2026-10-05): "题目全都是一个题型". The production model,
grading and student pages already support single_choice, true_false,
fill_blank, calculation and short_answer, but both assignment forms (Classic
and v1) picked questions client-side with ``options.length >= 2``, which
silently dropped every fill/calculation/short-answer question, and v1 took the
first N rows. Composition now happens here: only online auto-graded questions
are eligible, and picks are spread across question types.
"""

from __future__ import annotations

import json
import random
from typing import Any, Iterable

AUTO_GRADED_TYPES = ("single_choice", "true_false", "fill_blank", "calculation", "short_answer")
CHOICE_TYPES = frozenset({"single_choice", "true_false"})
TEXT_TYPES = frozenset({"fill_blank", "calculation", "short_answer"})
TYPE_LABELS = {
    "single_choice": "单选",
    "true_false": "判断",
    "fill_blank": "填空",
    "calculation": "计算",
    "short_answer": "简答",
}
MIX_MODES = frozenset({"mixed", "choice"})


def _options(row: Any) -> list[Any]:
    try:
        value = json.loads(getattr(row, "options_json", None) or "[]")
    except (TypeError, ValueError):
        return []
    return value if isinstance(value, list) else []


def online_question_type(row: Any, *, question_type_of: Any, answer_meta: Any) -> str | None:
    """The row's type if a student can answer it online and the server can grade it."""

    qtype = str(question_type_of(row) or "")
    if qtype in CHOICE_TYPES:
        options = _options(row)
        try:
            correct = int(getattr(row, "correct_index", -1))
        except (TypeError, ValueError):
            return None
        return qtype if len(options) >= 2 and 0 <= correct < len(options) else None
    if qtype in TEXT_TYPES:
        meta = answer_meta(row) or {}
        return qtype if str(meta.get("answer") or "").strip() else None
    return None


def compose_question_ids(
    typed_rows: Iterable[tuple[int, str]],
    count: int,
    *,
    mix: str = "mixed",
    rng: random.Random | None = None,
    required_first: Iterable[int] = (),
) -> list[int]:
    """Pick ``count`` question ids, round-robin across question types.

    ``typed_rows`` are ``(question_id, question_type)`` pairs of eligible rows.
    ``mix="choice"`` keeps only single_choice/true_false (the old behaviour, now
    explicit). ``required_first`` ids (e.g. a teacher's photo question) lead.
    """

    rng = rng or random.Random()
    mode = mix if mix in MIX_MODES else "mixed"
    count = max(0, int(count or 0))
    chosen = [int(x) for x in required_first][:count]
    taken = set(chosen)
    groups: dict[str, list[int]] = {}
    for qid, qtype in typed_rows:
        qid = int(qid)
        if qid in taken or qtype not in AUTO_GRADED_TYPES:
            continue
        if mode == "choice" and qtype not in CHOICE_TYPES:
            continue
        groups.setdefault(qtype, []).append(qid)
    for ids in groups.values():
        rng.shuffle(ids)
    order = [t for t in AUTO_GRADED_TYPES if groups.get(t)]
    rng.shuffle(order)
    while len(chosen) < count and any(groups.get(t) for t in order):
        for qtype in order:
            if len(chosen) >= count:
                break
            if groups.get(qtype):
                qid = groups[qtype].pop()
                if qid not in taken:
                    chosen.append(qid)
                    taken.add(qid)
    return chosen


def type_distribution(type_by_id: dict[int, str], ids: Iterable[int]) -> dict[str, int]:
    out: dict[str, int] = {}
    for qid in ids:
        qtype = type_by_id.get(int(qid))
        if qtype:
            out[qtype] = out.get(qtype, 0) + 1
    return {t: out[t] for t in AUTO_GRADED_TYPES if t in out}


def distribution_text(distribution: dict[str, int]) -> str:
    return " · ".join(f"{TYPE_LABELS.get(t, t)}{n}" for t, n in distribution.items())
