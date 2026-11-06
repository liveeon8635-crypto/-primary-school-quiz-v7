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


def _submission_stats_by_subject(
    implementation: Any, db: Any, answers: list[Any], school_id: int
) -> dict[tuple[str, str], tuple[int, int]]:
    qids = [
        item.get("question_id")
        for item in answers
        if isinstance(item, dict) and item.get("question_id") is not None
    ]
    if not qids:
        return {}
    question_model = implementation.Question
    subject_by_qid = {
        int(qid): str(subj or "").strip()
        for qid, subj in db.execute(
            select(question_model.id, question_model.subject).where(
                question_model.school_id == school_id,
                question_model.id.in_(qids),
            )
        ).all()
    }
    by_subject: dict[str, list[dict[str, Any]]] = {}
    for item in answers:
        if not isinstance(item, dict):
            continue
        qid = item.get("question_id")
        subj = subject_by_qid.get(int(qid), "") if isinstance(qid, int) else ""
        if not subj:
            continue
        by_subject.setdefault(subj, []).append(item)
    out: dict[tuple[str, str], tuple[int, int]] = {}
    for subj, sub_answers in by_subject.items():
        stats, _valid = implementation.normalized_answer_stats(db, sub_answers, school_id)
        for know, pair in stats.items():
            key = str(know or "").strip()
            if key:
                out[(subj, key)] = pair
    return out


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
        subject = str(item["subject"] or "").strip()
        knowledge_key = str(item["knowledge_key"] or "").strip()
        if item["matched"] and subject and knowledge_key:
            groups.setdefault((subject, knowledge_key), []).append(item)
        else:
            unmatched.append({"knowledge": item["raw_knowledge"], "at": _iso(item["created_at"]), "question": item["question_excerpt"]})

    scans: list[tuple[int, Any, dict[tuple[str, str], tuple[int, int]]]] = []
    if groups:
        earliest = min(g[0]["created_at"] for g in groups.values())
        subs = db.scalars(
            select(implementation.Submission)
            .where(
                implementation.Submission.school_id == school_id,
                implementation.Submission.student_id == student_id,
                implementation.Submission.submitted_at > earliest,
            )
            .order_by(implementation.Submission.submitted_at.asc(), implementation.Submission.id.asc())
            .limit(MAX_SUBMISSIONS_SCANNED)
        ).all()
        for sub in subs:
            try:
                answers = json.loads(sub.answers_json or "[]")
            except Exception:  # noqa: BLE001 - a damaged old row must not break the page
                answers = []
            if not isinstance(answers, list):
                answers = []
            stats_by_subject = _submission_stats_by_subject(implementation, db, answers, school_id)
            scans.append((int(sub.id), sub.submitted_at, stats_by_subject))

    flags = []
    for (subject, knowledge), items in groups.items():
        last = max(i["created_at"] for i in items)
        cleared_at = None
        cleared_sub_id: int | None = None
        last_sub_id: int | None = None
        last_sub_when = None
        sub_count = 0
        cum_hits = 0
        cum_total = 0
        max_sub_total = 0
        for sub_id, when, stats in scans:
            if when > last and (subject, knowledge) in stats:
                hit, total = stats[(subject, knowledge)]
                if total <= 0:
                    continue
                sub_count += 1
                cum_hits += int(hit)
                cum_total += int(total)
                max_sub_total = max(max_sub_total, int(total))
                last_sub_id = sub_id
                last_sub_when = when
                if cleared_at is None and total >= limits["minQuestions"] and hit * 100 >= limits["passPercent"] * total:
                    cleared_at = when
                    cleared_sub_id = sub_id
        if (
            cleared_at is None
            and max_sub_total < limits["minQuestions"]
            and cum_total >= limits["minQuestions"]
            and cum_hits * 100 >= limits["passPercent"] * cum_total
        ):
            cleared_at = last_sub_when
            cleared_sub_id = last_sub_id
        if cleared_at is not None:
            verification = "后续练习达到条件"
            verification_state = "passed"
        elif cum_total == 0:
            verification = "尚无后续作答"
            verification_state = "no_submission"
        elif cum_total < limits["minQuestions"]:
            verification = "题量不足待补充"
            verification_state = "insufficient_questions"
        else:
            verification = "已有结果尚未达标"
            verification_state = "below_threshold"
        flags.append(
            {
                "subject": subject,
                "knowledge": knowledge,
                "count": len(items),
                "firstAt": _iso(min(i["created_at"] for i in items)),
                "lastAt": _iso(last),
                "state": "cleared" if cleared_at else "open",
                "clearedAt": _iso(cleared_at) if cleared_at else "",
                "verification": verification,
                "verificationState": verification_state,
                "submissionID": cleared_sub_id if cleared_sub_id is not None else last_sub_id,
                "submissionCount": sub_count,
                "hits": cum_hits,
                "total": cum_total,
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
