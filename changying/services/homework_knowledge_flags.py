"""Which knowledge points a student needed AI help with, and whether a later submission has cleared them.

A knowledge point stays flagged ("AI 辅助过·待巩固") from the student's latest AI-assisted question until a LATER
submission contains at least ``HOMEWORK_FLAG_MIN_QUESTIONS`` (default 3) questions of that knowledge point
answered at ``HOMEWORK_FLAG_PASS_PERCENT`` (default 80) percent or better. Per-knowledge accuracy is computed
with the product's own ``normalized_answer_stats``, i.e. exactly the statistics the rest of the 学情 uses; only the
source of the flag (AI help in the after-school assistant) is new. Nothing here writes anything.
"""

from __future__ import annotations

import json
import os
from typing import Any

from sqlalchemy import select

from changying.services.homework_knowledge import register_homework_knowledge_table

MAX_SUBMISSIONS_SCANNED = 200


def thresholds() -> dict[str, int]:
    def read(name: str, default: int, low: int, high: int) -> int:
        try:
            return max(low, min(high, int(os.getenv(name, str(default)))))
        except ValueError:
            return default

    return {
        "minQuestions": read("HOMEWORK_FLAG_MIN_QUESTIONS", 3, 1, 50),
        "passPercent": read("HOMEWORK_FLAG_PASS_PERCENT", 80, 1, 100),
    }


def _iso(value: Any) -> str:
    return value.strftime("%Y-%m-%d %H:%M") if hasattr(value, "strftime") else ""


def knowledge_flags(implementation: Any, db: Any, school_id: int, student_id: int) -> dict[str, Any]:
    table = register_homework_knowledge_table(implementation)
    rows = db.execute(
        select(table).where(table.c.school_id == school_id, table.c.student_id == student_id).order_by(table.c.created_at, table.c.id)
    ).all()
    limits = thresholds()
    groups: dict[tuple[str, str], list[Any]] = {}
    unmatched: list[dict[str, Any]] = []
    for row in rows:
        item = row._mapping
        if item["matched"]:
            groups.setdefault((item["subject"], item["knowledge_key"]), []).append(item)
        else:
            unmatched.append({"knowledge": item["raw_knowledge"], "at": _iso(item["created_at"]), "question": item["question_excerpt"]})

    scans: list[tuple[Any, dict[str, tuple[int, int]]]] = []
    if groups:
        earliest = min(g[0]["created_at"] for g in groups.values())
        subs = db.scalars(
            select(implementation.Submission)
            .where(
                implementation.Submission.school_id == school_id,
                implementation.Submission.student_id == student_id,
                implementation.Submission.submitted_at > earliest,
            )
            .order_by(implementation.Submission.submitted_at.asc())
            .limit(MAX_SUBMISSIONS_SCANNED)
        ).all()
        for sub in subs:
            try:
                answers = json.loads(sub.answers_json or "[]")
            except Exception:  # noqa: BLE001 - a damaged old row must not break the page
                answers = []
            stats, _valid = implementation.normalized_answer_stats(db, answers, school_id)
            scans.append((sub.submitted_at, stats))

    flags = []
    for (subject, knowledge), items in groups.items():
        last = max(i["created_at"] for i in items)
        cleared_at = None
        for when, stats in scans:
            if when > last and knowledge in stats:
                hit, total = stats[knowledge]
                if total >= limits["minQuestions"] and hit * 100 >= limits["passPercent"] * total:
                    cleared_at = when
                    break
        flags.append(
            {
                "subject": subject,
                "knowledge": knowledge,
                "count": len(items),
                "firstAt": _iso(min(i["created_at"] for i in items)),
                "lastAt": _iso(last),
                "state": "cleared" if cleared_at else "open",
                "clearedAt": _iso(cleared_at) if cleared_at else "",
                "_sort": last,
            }
        )
    flags.sort(key=lambda f: (f["state"] != "open", -f["_sort"].timestamp()))
    for flag in flags:
        flag.pop("_sort")
    return {
        "flags": flags,
        "open": sum(1 for f in flags if f["state"] == "open"),
        "unmatched": unmatched[-10:],
        "assists": len(rows),
        "rule": limits,
    }


__all__ = ["knowledge_flags", "thresholds"]
