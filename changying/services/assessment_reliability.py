"""Runtime reliability patch for auto-graded assessment feedback.

Keeps the legacy route surface stable while replacing two fragile behaviours:
1) free-text grading now uses semantic numeric/unit matching;
2) reinforcement mastery is decided from evidence for the linked knowledge point,
   never from the total paper score.

A linked wrong record needs two successful reinforcement cycles for the same
knowledge point before it is marked mastered. Any later failed reinforcement
for that knowledge resets the confirmation count.
"""

from __future__ import annotations

from datetime import datetime
import json
import re
from types import ModuleType
from typing import Any

from fastapi import HTTPException

from changying.services.answer_semantics import answer_matches


AUTO_TEXT_TYPES = frozenset({"fill_blank", "calculation", "short_answer"})


def _knowledge_key(value: Any) -> str:
    return re.sub(r"[\s·—_\-（）()]+", "", str(value or "")).strip().lower()


def _knowledge_matches(left: str, right: str) -> bool:
    a, b = _knowledge_key(left), _knowledge_key(right)
    if not a or not b:
        return False
    return a == b or (len(a) >= 4 and a in b) or (len(b) >= 4 and b in a)


def mastery_transition(
    *,
    previous_count: int,
    demonstrated: bool | None,
    confirmations_required: int = 2,
) -> tuple[int, str, bool]:
    """Return (new_count, status, mastered_now) for one linked misconception."""
    previous = max(0, int(previous_count or 0))
    if demonstrated is None:
        return previous, "active", False
    if demonstrated is False:
        return 0, "active", False
    count = previous + 1
    mastered = count >= max(1, int(confirmations_required or 2))
    return count, ("mastered" if mastered else "active"), mastered


def install_assessment_reliability(implementation: ModuleType) -> None:
    app = implementation.app
    if getattr(app.state, "assessment_reliability_installed", False):
        return

    Question = implementation.Question
    Submission = implementation.Submission
    WrongQuestionRecord = implementation.WrongQuestionRecord
    ReinforcementLink = implementation.ReinforcementLink
    select = implementation.select

    def semantic_grade_answers(
        db,
        u,
        answers,
        allowed_question_ids=None,
        require_all=False,
    ):
        if not answers:
            raise HTTPException(400, "没有答题记录")
        if len(answers) > 100:
            raise HTTPException(400, "单次提交题量过多")
        allowed = set(allowed_question_ids) if allowed_question_ids is not None else None
        seen: set[int] = set()
        normalized: list[dict[str, Any]] = []
        correct = 0

        for item in answers:
            qid = int(item.question_id)
            if qid in seen:
                raise HTTPException(400, "答题记录包含重复题目")
            seen.add(qid)
            if allowed is not None and qid not in allowed:
                raise HTTPException(400, "答题记录包含不属于本试卷的题目")
            question = db.scalar(
                select(Question).where(
                    Question.id == qid,
                    Question.school_id == u.school_id,
                )
            )
            if question is None:
                raise HTTPException(400, "题目不存在或无权限")

            qtype = implementation.question_type_of(question)
            if qtype in ("single_choice", "true_false"):
                try:
                    options = json.loads(question.options_json or "[]")
                    option_count = len(options) if isinstance(options, list) else 0
                except Exception:
                    option_count = 0
                if (
                    item.selected_index is None
                    or item.selected_index < 0
                    or item.selected_index >= option_count
                ):
                    raise HTTPException(400, "答案选项无效")
                ok = item.selected_index == question.correct_index
                normalized_item = {
                    "question_id": qid,
                    "selected_index": item.selected_index,
                    "text_answer": "",
                    "correct": bool(ok),
                }
            elif qtype in AUTO_TEXT_TYPES:
                text_answer = str(item.text_answer or "").strip()
                if not text_answer:
                    raise HTTPException(400, "请填写答案后再提交")
                meta = implementation.question_answer_meta(question)
                if not meta["answer"]:
                    raise HTTPException(500, "题目标准答案缺失")
                ok = answer_matches(
                    question,
                    text_answer,
                    meta["answer"],
                    meta["accepted"],
                )
                normalized_item = {
                    "question_id": qid,
                    "selected_index": None,
                    "text_answer": text_answer,
                    "correct": bool(ok),
                }
            else:
                raise HTTPException(400, "该题型不支持在线自动判分")

            correct += 1 if ok else 0
            normalized.append(normalized_item)

        if require_all and allowed is not None and seen != allowed:
            raise HTTPException(400, "请完成试卷全部题目后再提交")
        total = len(normalized)
        score = round(correct / total * 100) if total else 0
        return normalized, correct, total, score

    def semantic_normalized_answer_stats(db, answers, school_id):
        knowledge: dict[str, tuple[int, int]] = {}
        valid = 0
        for item in answers:
            if not isinstance(item, dict):
                continue
            qid = item.get("question_id")
            question = (
                db.scalar(
                    select(Question).where(
                        Question.id == qid,
                        Question.school_id == school_id,
                    )
                )
                if qid is not None
                else None
            )
            if question is None:
                continue
            ok = item.get("correct")
            if not isinstance(ok, bool):
                qtype = implementation.question_type_of(question)
                if qtype in ("single_choice", "true_false"):
                    selected = item.get("selected_index")
                    if not isinstance(selected, int):
                        continue
                    ok = selected == question.correct_index
                elif qtype in AUTO_TEXT_TYPES:
                    value = str(item.get("text_answer") or "")
                    if not value.strip():
                        continue
                    meta = implementation.question_answer_meta(question)
                    ok = answer_matches(
                        question,
                        value,
                        meta["answer"],
                        meta["accepted"],
                    )
                else:
                    continue
            hit, total = knowledge.get(question.knowledge, (0, 0))
            knowledge[question.knowledge] = (hit + (1 if ok else 0), total + 1)
            valid += 1
        return knowledge, valid

    def evidence_based_mastery_update(db, assignment_id, student_id, score):
        link = db.scalar(
            select(ReinforcementLink).where(
                ReinforcementLink.assignment_id == assignment_id,
                ReinforcementLink.student_id == student_id,
            )
        )
        if link is None:
            return 0
        link.result_score = score
        link.completed_at = datetime.utcnow()

        try:
            linked_ids = [int(x) for x in json.loads(link.wrong_ids_json or "[]")]
        except Exception:
            linked_ids = []
        if not linked_ids:
            return 0

        submission = db.scalar(
            select(Submission)
            .where(
                Submission.school_id == link.school_id,
                Submission.assignment_id == assignment_id,
                Submission.student_id == student_id,
            )
            .order_by(Submission.id.desc())
            .limit(1)
        )
        if submission is None:
            return 0
        try:
            answers = json.loads(submission.answers_json or "[]")
        except Exception:
            answers = []

        qids = [
            int(x.get("question_id"))
            for x in answers
            if isinstance(x, dict) and x.get("question_id") is not None
        ]
        qmap = {}
        if qids:
            rows = db.scalars(
                select(Question).where(
                    Question.school_id == link.school_id,
                    Question.id.in_(qids),
                )
            ).all()
            qmap = {int(row.id): row for row in rows}

        evidence_by_knowledge: dict[str, list[bool]] = {}
        display_by_key: dict[str, str] = {}
        for item in answers:
            if not isinstance(item, dict):
                continue
            question = qmap.get(int(item.get("question_id") or 0))
            if question is None:
                continue
            key = _knowledge_key(question.knowledge)
            if not key:
                continue
            evidence_by_knowledge.setdefault(key, []).append(bool(item.get("correct")))
            display_by_key[key] = question.knowledge or ""

        wrong_rows = db.scalars(
            select(WrongQuestionRecord).where(
                WrongQuestionRecord.id.in_(linked_ids),
                WrongQuestionRecord.student_id == student_id,
                WrongQuestionRecord.school_id == link.school_id,
            )
        ).all()

        mastered_now = 0
        for row in wrong_rows:
            matching: list[bool] = []
            for key, results in evidence_by_knowledge.items():
                if _knowledge_matches(row.knowledge or "", display_by_key.get(key, key)):
                    matching.extend(results)
            if not matching:
                # This reinforcement did not actually test the linked knowledge.
                continue
            demonstrated = all(matching)
            previous_status = row.status
            count, status, mastered = mastery_transition(
                previous_count=int(row.reinforcement_count or 0),
                demonstrated=demonstrated,
                confirmations_required=2,
            )
            row.reinforcement_count = count
            row.status = status
            if mastered:
                if previous_status != "mastered":
                    mastered_now += 1
                row.mastered_at = datetime.utcnow()
            else:
                row.mastered_at = None

        return mastered_now

    implementation.grade_answers = semantic_grade_answers
    implementation.normalized_answer_stats = semantic_normalized_answer_stats
    implementation._reinforcement_mastery_update = evidence_based_mastery_update
    app.state.assessment_reliability_installed = True


__all__ = [
    "install_assessment_reliability",
    "mastery_transition",
]
