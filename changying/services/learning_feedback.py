# Learning-feedback context for evidence-driven AI reinforcement.
#
# Formal test submissions are converted into a compact, privacy-preserving
# context. No parallel mastery table is created: the existing assignment /
# submission / question chain remains the source of truth.

from __future__ import annotations

from collections import defaultdict
import json
from typing import Any

from sqlalchemy import select


LEARNING_EVIDENCE_SOURCES = {
    "student_comprehensive_test": "综合测试",
    "student_module_practice": "知识模块练习",
    "ai_reinforcement": "AI针对性练习",
}


def _options(row: Any) -> list[str]:
    try:
        values = json.loads(row.options_json or "[]")
    except Exception:
        return []
    return [str(x) for x in values] if isinstance(values, list) else []


def _answers(row: Any) -> list[dict[str, Any]]:
    try:
        values = json.loads(row.answers_json or "[]")
    except Exception:
        return []
    return values if isinstance(values, list) else []


def _accuracy(correct: int, total: int) -> int:
    return round(correct / total * 100) if total else 0


def collect_student_learning_feedback(
    db: Any,
    *,
    school_id: int,
    student_id: int,
    Assignment: Any,
    AssignmentRecipient: Any,
    Paper: Any,
    Submission: Any,
    Question: Any,
    assignment_id: int | None = None,
    limit: int = 8,
) -> dict[str, Any]:
    limit = max(1, min(int(limit or 8), 20))
    query = (
        select(Submission)
        .where(
            Submission.school_id == school_id,
            Submission.student_id == student_id,
            Submission.assignment_id.is_not(None),
        )
        .order_by(Submission.submitted_at.desc(), Submission.id.desc())
    )
    if assignment_id is not None:
        query = query.where(Submission.assignment_id == int(assignment_id))
    else:
        query = query.limit(max(limit * 4, 20))

    submissions = list(db.scalars(query).all())
    tests: list[dict[str, Any]] = []
    wrong_items: list[dict[str, Any]] = []
    knowledge: dict[tuple[str, str, str], dict[str, Any]] = defaultdict(
        lambda: {
            "correct": 0,
            "total": 0,
            "wrong": 0,
            "assignmentIDs": [],
            "sources": set(),
            "latest": "",
        }
    )

    for submission in submissions:
        aid = int(submission.assignment_id or 0)
        if not aid:
            continue
        assignment = db.scalar(
            select(Assignment).where(
                Assignment.id == aid,
                Assignment.school_id == school_id,
            )
        )
        if assignment is None:
            continue
        recipient = db.scalar(
            select(AssignmentRecipient).where(
                AssignmentRecipient.school_id == school_id,
                AssignmentRecipient.assignment_id == aid,
                AssignmentRecipient.student_id == student_id,
            )
        )
        if recipient is None:
            continue
        source = str(recipient.source or "").strip()
        if assignment_id is None and source not in LEARNING_EVIDENCE_SOURCES:
            continue

        paper = db.scalar(
            select(Paper).where(
                Paper.id == assignment.paper_id,
                Paper.school_id == school_id,
            )
        )
        if paper is None:
            continue

        answers = _answers(submission)
        qids: list[int] = []
        for answer in answers:
            try:
                qid = int(answer.get("question_id") or 0)
            except Exception:
                qid = 0
            if qid > 0:
                qids.append(qid)
        qmap = {}
        if qids:
            qmap = {
                row.id: row
                for row in db.scalars(
                    select(Question).where(
                        Question.school_id == school_id,
                        Question.id.in_(qids),
                    )
                ).all()
            }

        test_knowledge: dict[str, list[int]] = defaultdict(lambda: [0, 0])
        test_wrong = 0
        for answer in answers:
            try:
                qid = int(answer.get("question_id") or 0)
                selected_index = int(answer.get("selected_index", -1))
            except Exception:
                continue
            question = qmap.get(qid)
            if question is None:
                continue
            opts = _options(question)
            if not opts or selected_index not in range(len(opts)):
                continue
            correct_index = int(question.correct_index)
            is_correct = selected_index == correct_index
            knowledge_name = (
                str(question.knowledge or "").strip()
                or str(question.unit or "").strip()
                or "综合"
            )
            subject = str(question.subject or paper.subject or "").strip()
            textbook = str(question.textbook or paper.textbook or "").strip()
            key = (subject, textbook, knowledge_name)
            item = knowledge[key]
            item["total"] += 1
            item["correct"] += 1 if is_correct else 0
            item["wrong"] += 0 if is_correct else 1
            if aid not in item["assignmentIDs"]:
                item["assignmentIDs"].append(aid)
            if source:
                item["sources"].add(source)
            stamp = getattr(submission, "submitted_at", None)
            stamp_text = stamp.isoformat() if stamp else ""
            if stamp_text > item["latest"]:
                item["latest"] = stamp_text

            test_knowledge[knowledge_name][1] += 1
            test_knowledge[knowledge_name][0] += 1 if is_correct else 0
            if is_correct:
                continue

            test_wrong += 1
            correct_text = opts[correct_index] if correct_index in range(len(opts)) else ""
            wrong_items.append(
                {
                    "assignmentID": aid,
                    "assignmentTitle": assignment.title,
                    "source": source,
                    "sourceName": LEARNING_EVIDENCE_SOURCES.get(
                        source, source or "正式测试"
                    ),
                    "questionID": question.id,
                    "grade": int(question.grade or paper.grade or 0),
                    "subject": subject,
                    "textbook": textbook,
                    "unit": str(question.unit or paper.unit or "").strip(),
                    "knowledge": knowledge_name,
                    "problem": str(question.text or "").strip(),
                    "wrongAnswer": opts[selected_index],
                    "correctAnswer": correct_text,
                    "analysis": str(question.explanation or "").strip(),
                }
            )

        submitted_at = getattr(submission, "submitted_at", None)
        tests.append(
            {
                "assignmentID": aid,
                "title": assignment.title,
                "source": source,
                "sourceName": LEARNING_EVIDENCE_SOURCES.get(
                    source, source or "正式测试"
                ),
                "grade": int(paper.grade or 0),
                "subject": str(paper.subject or "").strip(),
                "textbook": str(paper.textbook or "").strip(),
                "unit": str(paper.unit or "").strip(),
                "score": int(submission.score or 0),
                "correct": int(submission.correct or 0),
                "total": int(submission.total or 0),
                "wrong": test_wrong,
                "submittedAt": submitted_at.isoformat() if submitted_at else "",
                "knowledge": [
                    {
                        "knowledge": name,
                        "correct": values[0],
                        "total": values[1],
                        "accuracy": _accuracy(values[0], values[1]),
                    }
                    for name, values in sorted(test_knowledge.items())
                ],
            }
        )
        if len(tests) >= limit:
            break

    knowledge_rows: list[dict[str, Any]] = []
    for (subject, textbook, knowledge_name), values in knowledge.items():
        knowledge_rows.append(
            {
                "subject": subject,
                "textbook": textbook,
                "knowledge": knowledge_name,
                "correct": values["correct"],
                "total": values["total"],
                "wrong": values["wrong"],
                "accuracy": _accuracy(values["correct"], values["total"]),
                "assignmentIDs": values["assignmentIDs"][:8],
                "sources": sorted(values["sources"]),
                "latest": values["latest"],
            }
        )

    knowledge_rows.sort(
        key=lambda x: (
            x["accuracy"],
            -x["wrong"],
            -x["total"],
            x["knowledge"],
        )
    )
    weak = [
        row for row in knowledge_rows
        if row["wrong"] > 0 or row["accuracy"] < 80
    ][:10]
    wrong_items = wrong_items[:30]

    primary: dict[str, Any] = {}
    if tests:
        newest = tests[0]
        primary = {
            "grade": newest["grade"],
            "subject": newest["subject"],
            "textbook": newest["textbook"],
            "unit": newest["unit"],
        }
        if weak:
            primary["knowledge"] = weak[0]["knowledge"]

    return {
        "hasEvidence": bool(tests),
        "tests": tests,
        "weakKnowledge": weak,
        "wrongQuestions": wrong_items,
        "sourceAssignmentIDs": [row["assignmentID"] for row in tests],
        "primary": primary,
    }


def compact_feedback_for_ai(feedback: dict[str, Any]) -> dict[str, Any]:
    return {
        "sourceAssignments": [
            {
                "assignmentID": row.get("assignmentID"),
                "sourceName": row.get("sourceName"),
                "grade": row.get("grade"),
                "subject": row.get("subject"),
                "textbook": row.get("textbook"),
                "unit": row.get("unit"),
                "score": row.get("score"),
                "correct": row.get("correct"),
                "total": row.get("total"),
                "knowledge": row.get("knowledge", [])[:10],
            }
            for row in (feedback.get("tests") or [])[:6]
        ],
        "weakKnowledge": (feedback.get("weakKnowledge") or [])[:8],
        "wrongQuestions": [
            {
                "assignmentID": row.get("assignmentID"),
                "sourceName": row.get("sourceName"),
                "grade": row.get("grade"),
                "subject": row.get("subject"),
                "textbook": row.get("textbook"),
                "unit": row.get("unit"),
                "knowledge": row.get("knowledge"),
                "problem": row.get("problem"),
                "wrongAnswer": row.get("wrongAnswer"),
                "correctAnswer": row.get("correctAnswer"),
                "analysis": row.get("analysis"),
            }
            for row in (feedback.get("wrongQuestions") or [])[:16]
        ],
    }


__all__ = [
    "LEARNING_EVIDENCE_SOURCES",
    "collect_student_learning_feedback",
    "compact_feedback_for_ai",
]
