"""Assessment feedback bridge for student-specific AI reinforcement.

The bridge deliberately reuses existing submissions, questions, papers,
assignment-recipient sources and wrong-question records.  No parallel mastery
store is introduced: the student's continuous learning record remains the
single source of truth.
"""

from __future__ import annotations

from collections import defaultdict
import json
from typing import Any

from sqlalchemy import select


AUTO_ASSESSMENT_SOURCES = {
    "student_comprehensive_test": "comprehensive",
    "student_module_practice": "module",
}
LEARNING_FEEDBACK_SOURCES = {
    **AUTO_ASSESSMENT_SOURCES,
    "ai_reinforcement": "reinforcement",
}


def _json_list(raw: Any) -> list[Any]:
    try:
        value = json.loads(raw or "[]")
    except Exception:
        return []
    return value if isinstance(value, list) else []


def _question_type(question: Any) -> str:
    raw = str(getattr(question, "question_type", "") or "").strip().lower()
    if raw:
        return raw
    options = _json_list(getattr(question, "options_json", "[]"))
    return "single_choice" if options and int(getattr(question, "correct_index", -1)) >= 0 else "non_choice"


def _answer_meta(question: Any) -> dict[str, Any]:
    raw = getattr(question, "answer_json", "{}")
    try:
        value = json.loads(raw or "{}")
    except Exception:
        value = {}
    if not isinstance(value, dict):
        value = {}
    return {
        "answer": str(value.get("answer") or ""),
        "accepted": [str(x) for x in (value.get("accepted") or []) if str(x).strip()],
    }


def _question_map(
    db: Any,
    Question: Any,
    *,
    school_id: int,
    question_ids: list[int],
) -> dict[int, Any]:
    ids = list(dict.fromkeys(int(x) for x in question_ids if int(x) > 0))
    if not ids:
        return {}
    rows = list(
        db.scalars(
            select(Question).where(
                Question.school_id == school_id,
                Question.id.in_(ids),
            )
        ).all()
    )
    return {int(row.id): row for row in rows}


def archive_objective_assessment_wrong_answers(
    db: Any,
    *,
    AssignmentRecipient: Any,
    Question: Any,
    WrongQuestionRecord: Any,
    school_id: int,
    student_id: int,
    assignment_id: int,
    answers: list[dict[str, Any]],
) -> list[Any]:
    """Persist objectively wrong answers from supported learning-feedback quizzes.

    Comprehensive tests, module practice and teacher-approved AI reinforcement
    all feed the same continuous student record. The helper is idempotent per
    assignment/question and never touches teacher-confirmed wrong-question
    records from other workflows.
    """

    recipient = db.scalar(
        select(AssignmentRecipient).where(
            AssignmentRecipient.school_id == school_id,
            AssignmentRecipient.assignment_id == assignment_id,
            AssignmentRecipient.student_id == student_id,
        )
    )
    if not recipient or recipient.source not in LEARNING_FEEDBACK_SOURCES:
        return []

    wrong_answers = [
        item
        for item in (answers or [])
        if isinstance(item, dict)
        and item.get("correct") is False
        and int(item.get("question_id") or 0) > 0
    ]
    if not wrong_answers:
        return []

    qmap = _question_map(
        db,
        Question,
        school_id=school_id,
        question_ids=[int(x["question_id"]) for x in wrong_answers],
    )
    existing = list(
        db.scalars(
            select(WrongQuestionRecord).where(
                WrongQuestionRecord.school_id == school_id,
                WrongQuestionRecord.student_id == student_id,
                WrongQuestionRecord.assignment_id == assignment_id,
                WrongQuestionRecord.source == "assessment",
            )
        ).all()
    )
    existing_by_question = {
        int(row.question_id): row
        for row in existing
        if row.question_id is not None
    }

    created_or_updated: list[Any] = []
    for answer in wrong_answers:
        qid = int(answer["question_id"])
        question = qmap.get(qid)
        if not question:
            continue
        qtype = _question_type(question)
        options = _json_list(question.options_json)
        if qtype in ("fill_blank", "calculation", "short_answer"):
            wrong_text = str(answer.get("text_answer") or "").strip() or "未答"
            meta = _answer_meta(question)
            correct_text = meta["answer"]
        else:
            selected_raw = answer.get("selected_index")
            selected_index = int(selected_raw) if isinstance(selected_raw, int) else -1
            wrong_text = (
                str(options[selected_index])
                if 0 <= selected_index < len(options)
                else "未答"
            )
            correct_index = int(question.correct_index)
            correct_text = (
                str(options[correct_index])
                if 0 <= correct_index < len(options)
                else ""
            )

        row = existing_by_question.get(qid)
        if row is None:
            row = WrongQuestionRecord(
                school_id=school_id,
                student_id=student_id,
                assignment_id=assignment_id,
                question_id=qid,
                source="assessment",
            )
            db.add(row)
            existing_by_question[qid] = row

        row.subject = str(question.subject or "")
        row.knowledge = str(question.knowledge or question.unit or "")
        row.problem_text = str(question.text or "")
        row.wrong_answer = wrong_text
        row.correct_answer = correct_text
        row.analysis = str(question.explanation or "")
        row.teacher_feedback = ""
        row.status = "active"
        row.mastered_at = None
        db.flush()
        created_or_updated.append(row)

    return created_or_updated


def student_assessment_context(
    db: Any,
    *,
    AssignmentRecipient: Any,
    Assignment: Any,
    Submission: Any,
    Paper: Any,
    Question: Any,
    school_id: int,
    student_id: int,
    assignment_id: int | None = None,
    limit: int = 6,
    textbook_filter: str | None = None,
) -> dict[str, Any]:
    """Build recent test/practice/reinforcement evidence for AI reinforcement.

    When a textbook filter is set, only feedback from that exact textbook line
    is eligible. This prevents historical work from another publisher from
    contaminating current targeted-practice feedback.
    """

    query = select(AssignmentRecipient).where(
        AssignmentRecipient.school_id == school_id,
        AssignmentRecipient.student_id == student_id,
        AssignmentRecipient.source.in_(tuple(LEARNING_FEEDBACK_SOURCES)),
    )
    if assignment_id:
        query = query.where(AssignmentRecipient.assignment_id == assignment_id)
    requested_limit = max(1, min(int(limit or 6), 12))
    scan_limit = min(48, max(requested_limit, requested_limit * 4))
    recipients = list(
        db.scalars(
            query.order_by(
                AssignmentRecipient.assigned_at.desc(),
                AssignmentRecipient.id.desc(),
            ).limit(scan_limit)
        ).all()
    )

    assessments: list[dict[str, Any]] = []
    aggregate: dict[tuple[str, str, str], list[int]] = defaultdict(lambda: [0, 0])
    for recipient in recipients:
        assignment = db.scalar(
            select(Assignment).where(
                Assignment.id == recipient.assignment_id,
                Assignment.school_id == school_id,
            )
        )
        if not assignment:
            continue
        submission = db.scalar(
            select(Submission)
            .where(
                Submission.school_id == school_id,
                Submission.assignment_id == assignment.id,
                Submission.student_id == student_id,
            )
            .order_by(Submission.submitted_at.desc(), Submission.id.desc())
            .limit(1)
        )
        if not submission:
            continue
        paper = db.scalar(
            select(Paper).where(
                Paper.id == assignment.paper_id,
                Paper.school_id == school_id,
            )
        )
        if not paper:
            continue
        if textbook_filter and str(paper.textbook or "").strip() != str(textbook_filter).strip():
            continue

        answers = _json_list(submission.answers_json)
        question_ids = [
            int(item.get("question_id") or 0)
            for item in answers
            if isinstance(item, dict) and int(item.get("question_id") or 0) > 0
        ]
        qmap = _question_map(
            db,
            Question,
            school_id=school_id,
            question_ids=question_ids,
        )

        knowledge_stats: dict[str, list[int]] = defaultdict(lambda: [0, 0])
        wrong_items: list[dict[str, Any]] = []
        for item in answers:
            if not isinstance(item, dict):
                continue
            qid = int(item.get("question_id") or 0)
            question = qmap.get(qid)
            if not question:
                continue
            knowledge = str(question.knowledge or question.unit or "综合").strip() or "综合"
            is_correct = item.get("correct") is True
            knowledge_stats[knowledge][1] += 1
            if is_correct:
                knowledge_stats[knowledge][0] += 1

            agg_key = (
                str(paper.subject or question.subject or ""),
                str(paper.textbook or question.textbook or ""),
                knowledge,
            )
            aggregate[agg_key][1] += 1
            if is_correct:
                aggregate[agg_key][0] += 1

            if not is_correct and len(wrong_items) < 12:
                qtype = _question_type(question)
                options = _json_list(question.options_json)
                if qtype in ("fill_blank", "calculation"):
                    wrong_value = str(item.get("text_answer") or "").strip() or "未答"
                    correct_value = _answer_meta(question)["answer"]
                else:
                    selected_raw = item.get("selected_index")
                    selected_index = int(selected_raw) if isinstance(selected_raw, int) else -1
                    correct_index = int(question.correct_index)
                    wrong_value = (
                        str(options[selected_index])
                        if 0 <= selected_index < len(options)
                        else "未答"
                    )
                    correct_value = (
                        str(options[correct_index])
                        if 0 <= correct_index < len(options)
                        else ""
                    )
                wrong_items.append(
                    {
                        "questionID": qid,
                        "knowledge": knowledge,
                        "problem": str(question.text or ""),
                        "wrongAnswer": wrong_value,
                        "correctAnswer": correct_value,
                        "analysis": str(question.explanation or ""),
                    }
                )

        stats = [
            {
                "knowledge": knowledge,
                "correct": values[0],
                "answered": values[1],
                "accuracy": round(values[0] / values[1] * 100) if values[1] else 0,
            }
            for knowledge, values in knowledge_stats.items()
        ]
        stats.sort(key=lambda x: (x["accuracy"], -x["answered"], x["knowledge"]))
        assessments.append(
            {
                "assignmentID": int(assignment.id),
                "title": str(assignment.title or ""),
                "kind": LEARNING_FEEDBACK_SOURCES.get(recipient.source, "assessment"),
                "source": str(recipient.source or ""),
                "grade": int(paper.grade or 0),
                "subject": str(paper.subject or ""),
                "textbook": str(paper.textbook or ""),
                "unit": str(paper.unit or ""),
                "score": int(submission.score or 0),
                "correct": int(submission.correct or 0),
                "total": int(submission.total or 0),
                "submittedAt": (
                    submission.submitted_at.isoformat(timespec="minutes")
                    if submission.submitted_at
                    else ""
                ),
                "knowledge": stats,
                "wrongItems": wrong_items,
            }
        )
        if len(assessments) >= requested_limit:
            break

    assessments.sort(key=lambda x: x.get("submittedAt", ""), reverse=True)
    weak_knowledge = [
        {
            "subject": subject,
            "textbook": textbook,
            "knowledge": knowledge,
            "correct": values[0],
            "answered": values[1],
            "accuracy": round(values[0] / values[1] * 100) if values[1] else 0,
        }
        for (subject, textbook, knowledge), values in aggregate.items()
    ]
    weak_knowledge.sort(
        key=lambda x: (x["accuracy"], -x["answered"], x["knowledge"])
    )

    primary = {}
    if assessments:
        first = assessments[0]
        primary = {
            "assignmentID": first["assignmentID"],
            "grade": first["grade"],
            "subject": first["subject"],
            "textbook": first["textbook"],
            "unit": first["unit"],
            "kind": first["kind"],
            "score": first["score"],
        }

    return {
        "assessmentCount": len(assessments),
        "sourceAssignmentIDs": [x["assignmentID"] for x in assessments],
        "primary": primary,
        "weakKnowledge": weak_knowledge[:10],
        "assessments": assessments,
    }


def assessment_context_notice(context: dict[str, Any]) -> str:
    count = int(context.get("assessmentCount") or 0)
    if not count:
        return ""
    weak = [
        item
        for item in (context.get("weakKnowledge") or [])
        if int(item.get("answered") or 0) > 0
    ][:4]
    focus = "、".join(
        f"{item.get('knowledge') or '知识点'} {int(item.get('accuracy') or 0)}%"
        for item in weak
    )
    primary = context.get("primary") or {}
    prefix = f"已关联最近 {count} 次测试/练习反馈"
    if primary.get("textbook"):
        prefix += f"（{primary['textbook']}）"
    return prefix + (f"；优先关注：{focus}" if focus else "")


__all__ = [
    "AUTO_ASSESSMENT_SOURCES",
    "LEARNING_FEEDBACK_SOURCES",
    "archive_objective_assessment_wrong_answers",
    "assessment_context_notice",
    "student_assessment_context",
]
