"""Class-level practice review aggregation for one teaching session.

An Assignment is the data anchor for a classroom exercise: it already binds the
class, paper, questions, recipients and submissions.  This module only derives
teacher-facing facts from those records; it does not infer long-term mastery.
"""

from __future__ import annotations

from collections import Counter, defaultdict
import json
from typing import Any


def _json_list(raw: Any) -> list[Any]:
    try:
        value = json.loads(raw or "[]")
    except Exception:
        return []
    return value if isinstance(value, list) else []


def _json_object(raw: Any) -> dict[str, Any]:
    try:
        value = json.loads(raw or "{}")
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def _question_type(question: Any) -> str:
    raw = str(getattr(question, "question_type", "") or "").strip().lower()
    if raw == "choice":
        return "single_choice"
    if raw:
        return raw
    return "single_choice" if _json_list(getattr(question, "options_json", "[]")) else "fill_blank"


def _answer_text(question: Any, answer: dict[str, Any]) -> str:
    qtype = _question_type(question)
    if qtype in {"fill_blank", "calculation", "short_answer"}:
        return str(answer.get("text_answer") or "").strip() or "未答"
    options = [str(x) for x in _json_list(getattr(question, "options_json", "[]"))]
    raw = answer.get("selected_index")
    selected = int(raw) if isinstance(raw, int) else -1
    return options[selected] if 0 <= selected < len(options) else "未答"


def _correct_text(question: Any) -> str:
    qtype = _question_type(question)
    if qtype in {"fill_blank", "calculation", "short_answer"}:
        return str(_json_object(getattr(question, "answer_json", "{}")).get("answer") or "").strip()
    options = [str(x) for x in _json_list(getattr(question, "options_json", "[]"))]
    try:
        index = int(getattr(question, "correct_index", -1))
    except Exception:
        index = -1
    return options[index] if 0 <= index < len(options) else ""


def classroom_review_summary(
    *,
    assignment: Any,
    class_row: Any,
    paper: Any,
    recipients: list[Any],
    submissions: list[Any],
    questions: list[Any],
) -> dict[str, Any]:
    """Aggregate one classroom exercise without changing individual records."""

    qmap = {int(q.id): q for q in questions}
    latest_by_student: dict[int, Any] = {}
    for sub in sorted(
        submissions,
        key=lambda row: (
            getattr(row, "submitted_at", None),
            int(getattr(row, "id", 0) or 0),
        ),
    ):
        latest_by_student[int(sub.student_id)] = sub

    recipient_ids = {int(row.id) for row in recipients}
    completed = [sub for sid, sub in latest_by_student.items() if sid in recipient_ids]
    scores = [int(getattr(sub, "score", 0) or 0) for sub in completed]

    knowledge = defaultdict(lambda: {"correct": 0, "answered": 0, "students": set()})
    question_stats: dict[int, dict[str, Any]] = {}
    student_rows: list[dict[str, Any]] = []

    for student in recipients:
        sid = int(student.id)
        sub = latest_by_student.get(sid)
        student_rows.append(
            {
                "studentID": sid,
                "studentName": str(getattr(student, "name", "") or ""),
                "completed": bool(sub),
                "score": int(sub.score) if sub is not None else None,
                "correct": int(sub.correct) if sub is not None else None,
                "total": int(sub.total) if sub is not None else None,
                "submittedAt": (
                    sub.submitted_at.isoformat(timespec="minutes")
                    if sub is not None and getattr(sub, "submitted_at", None)
                    else ""
                ),
            }
        )
        if sub is None:
            continue

        for answer in _json_list(getattr(sub, "answers_json", "[]")):
            if not isinstance(answer, dict):
                continue
            qid = int(answer.get("question_id") or 0)
            question = qmap.get(qid)
            if not question:
                continue
            key = str(
                getattr(question, "knowledge", "")
                or getattr(question, "unit", "")
                or "综合"
            ).strip() or "综合"
            ok = answer.get("correct") is True
            knowledge[key]["answered"] += 1
            knowledge[key]["students"].add(sid)
            if ok:
                knowledge[key]["correct"] += 1

            row = question_stats.setdefault(
                qid,
                {
                    "questionID": qid,
                    "knowledge": key,
                    "problem": str(getattr(question, "text", "") or ""),
                    "questionType": _question_type(question),
                    "correctAnswer": _correct_text(question),
                    "answered": 0,
                    "correct": 0,
                    "wrongAnswers": Counter(),
                },
            )
            row["answered"] += 1
            if ok:
                row["correct"] += 1
            else:
                row["wrongAnswers"][_answer_text(question, answer)] += 1

    knowledge_rows = []
    for key, values in knowledge.items():
        answered = int(values["answered"])
        correct = int(values["correct"])
        accuracy = round(correct / answered * 100) if answered else 0
        knowledge_rows.append(
            {
                "knowledge": key,
                "correct": correct,
                "answered": answered,
                "studentCount": len(values["students"]),
                "accuracy": accuracy,
                "reviewPriority": (
                    "重点讲解建议"
                    if accuracy < 60
                    else "简要巩固建议"
                    if accuracy < 80
                    else "本次表现较稳定"
                ),
            }
        )
    knowledge_rows.sort(key=lambda x: (x["accuracy"], -x["answered"], x["knowledge"]))

    common_errors = []
    for row in question_stats.values():
        answered = int(row["answered"])
        wrong = answered - int(row["correct"])
        if not answered or not wrong:
            continue
        common_errors.append(
            {
                "questionID": row["questionID"],
                "knowledge": row["knowledge"],
                "problem": row["problem"],
                "questionType": row["questionType"],
                "correctAnswer": row["correctAnswer"],
                "answered": answered,
                "wrong": wrong,
                "wrongRate": round(wrong / answered * 100),
                "wrongAnswerDistribution": [
                    {"answer": answer, "count": count}
                    for answer, count in row["wrongAnswers"].most_common(5)
                ],
            }
        )
    common_errors.sort(
        key=lambda x: (-x["wrongRate"], -x["wrong"], x["questionID"])
    )

    student_rows.sort(
        key=lambda x: (
            0 if not x["completed"] else 1,
            x["score"] if x["score"] is not None else -1,
            x["studentName"],
        )
    )
    recipient_count = len(recipients)
    completed_count = len(completed)
    return {
        "assignment": {
            "id": int(assignment.id),
            "title": str(getattr(assignment, "title", "") or ""),
            "dueDate": str(getattr(assignment, "due_date", "") or ""),
            "createdAt": (
                assignment.created_at.isoformat(timespec="minutes")
                if getattr(assignment, "created_at", None)
                else ""
            ),
        },
        "class": {
            "id": int(class_row.id),
            "name": str(getattr(class_row, "name", "") or ""),
            "grade": int(getattr(class_row, "grade", 0) or 0),
        },
        "paper": {
            "id": int(paper.id),
            "title": str(getattr(paper, "title", "") or ""),
            "subject": str(getattr(paper, "subject", "") or ""),
            "textbook": str(getattr(paper, "textbook", "") or ""),
            "unit": str(getattr(paper, "unit", "") or ""),
            "questionCount": len(qmap),
        },
        "recipientCount": recipient_count,
        "completedCount": completed_count,
        "pendingCount": max(0, recipient_count - completed_count),
        "completionRate": (
            round(completed_count / recipient_count * 100) if recipient_count else 0
        ),
        "averageScore": round(sum(scores) / len(scores), 1) if scores else None,
        "highestScore": max(scores) if scores else None,
        "lowestScore": min(scores) if scores else None,
        "knowledgeStats": knowledge_rows,
        "commonErrors": common_errors[:12],
        "students": student_rows,
        "handoutReady": completed_count > 0,
        "dataNotice": (
            "全体接收学生均已完成，可进行完整课堂复盘。"
            if recipient_count and completed_count == recipient_count
            else f"当前已完成 {completed_count}/{recipient_count}；教师可先查看阶段数据，也可等待更多学生完成后再生成讲义。"
        ),
    }



def _row_value(row: Any, key: str, default: Any = None) -> Any:
    if row is None:
        return default
    mapping = getattr(row, "_mapping", None)
    if mapping is not None:
        return mapping.get(key, default)
    if isinstance(row, dict):
        return row.get(key, default)
    return getattr(row, key, default)


def _iso_minute(value: Any) -> str:
    if not value:
        return ""
    try:
        return value.isoformat(timespec="minutes")
    except Exception:
        return str(value)


def classroom_interaction_summary(
    *,
    session: Any,
    segments: list[Any],
    quick_checks: list[Any],
    responses: list[Any],
    presenter_turns: list[Any],
    presentation_reviews: list[Any],
) -> dict[str, Any]:
    """Aggregate one classroom execution without exposing student identities."""

    sid = int(_row_value(session, "id", 0) or 0)
    responses_by_check: dict[int, list[Any]] = defaultdict(list)
    for row in responses:
        responses_by_check[int(_row_value(row, "check_id", 0) or 0)].append(row)

    checks_by_segment: dict[int, list[Any]] = defaultdict(list)
    for row in quick_checks:
        checks_by_segment[int(_row_value(row, "segment_id", 0) or 0)].append(row)
    for rows in checks_by_segment.values():
        rows.sort(
            key=lambda x: (
                _row_value(x, "created_at"),
                int(_row_value(x, "id", 0) or 0),
            )
        )

    turns_by_segment: dict[int, list[Any]] = defaultdict(list)
    for row in presenter_turns:
        turns_by_segment[int(_row_value(row, "segment_id", 0) or 0)].append(row)

    reviews_by_segment: dict[int, list[Any]] = defaultdict(list)
    for row in presentation_reviews:
        reviews_by_segment[int(_row_value(row, "segment_id", 0) or 0)].append(row)

    segment_rows: list[dict[str, Any]] = []
    total_rounds = 0
    total_reteach = 0
    total_presentations = 0
    total_reviews = 0
    total_teacher_points = 0

    ordered_segments = sorted(
        segments,
        key=lambda x: (
            int(_row_value(x, "order_no", 0) or 0),
            int(_row_value(x, "id", 0) or 0),
        ),
    )
    for seg in ordered_segments:
        seg_id = int(_row_value(seg, "id", 0) or 0)
        rounds = []
        for check in checks_by_segment.get(seg_id, []):
            check_id = int(_row_value(check, "id", 0) or 0)
            check_responses = responses_by_check.get(check_id, [])
            response_count = len(check_responses)
            correct_count = sum(
                1 for row in check_responses if _row_value(row, "is_correct") is True
            )
            accuracy = (
                round(correct_count / response_count * 100)
                if response_count
                else None
            )
            decision = str(_row_value(check, "decision", "") or "")
            if decision == "reteach":
                total_reteach += 1
            rounds.append(
                {
                    "round": len(rounds) + 1,
                    "questionType": str(_row_value(check, "question_type", "") or ""),
                    "questionText": str(_row_value(check, "question_text", "") or ""),
                    "status": str(_row_value(check, "status", "") or ""),
                    "decision": decision,
                    "responseCount": response_count,
                    "correctCount": correct_count,
                    "accuracy": accuracy,
                }
            )
        total_rounds += len(rounds)

        completed_turns = [
            row
            for row in turns_by_segment.get(seg_id, [])
            if str(_row_value(row, "status", "") or "") == "completed"
        ]
        reviews = reviews_by_segment.get(seg_id, [])
        total_presentations += len(completed_turns)
        total_reviews += len(reviews)
        granted_points = sum(int(_row_value(row, "granted_points", 0) or 0) for row in reviews)
        total_teacher_points += granted_points

        def avg(field: str) -> float | None:
            values = [
                int(_row_value(row, field, 0) or 0)
                for row in reviews
                if int(_row_value(row, field, 0) or 0) > 0
            ]
            return round(sum(values) / len(values), 1) if values else None

        segment_rows.append(
            {
                "segmentID": seg_id,
                "knowledge": str(_row_value(seg, "knowledge_key", "") or ""),
                "title": str(_row_value(seg, "title", "") or ""),
                "orderNo": int(_row_value(seg, "order_no", 0) or 0),
                "mode": str(_row_value(seg, "mode", "") or ""),
                "status": str(_row_value(seg, "status", "") or ""),
                "baselineAccuracy": _row_value(seg, "baseline_accuracy"),
                "postcheckAccuracy": _row_value(seg, "postcheck_accuracy"),
                "quickCheckRounds": rounds,
                "roundCount": len(rounds),
                "reteachCount": sum(1 for row in rounds if row["decision"] == "reteach"),
                "presentationCount": len(completed_turns),
                "presentationReviewCount": len(reviews),
                "presentationAverages": {
                    "accuracy": avg("accuracy_rating"),
                    "clarity": avg("clarity_rating"),
                    "interaction": avg("interaction_rating"),
                },
                "teacherGrantedPoints": granted_points,
            }
        )

    return {
        "session": {
            "id": sid,
            "title": str(_row_value(session, "title", "") or ""),
            "status": str(_row_value(session, "status", "") or ""),
            "startedAt": _iso_minute(_row_value(session, "started_at")),
            "completedAt": _iso_minute(_row_value(session, "completed_at")),
        },
        "quickCheckRoundCount": total_rounds,
        "reteachCount": total_reteach,
        "presentationCount": total_presentations,
        "presentationReviewCount": total_reviews,
        "teacherGrantedPoints": total_teacher_points,
        "segments": segment_rows,
    }


def build_anonymized_handout_prompt(
    summary: dict[str, Any],
    *,
    selected_knowledge: list[str],
    selected_question_ids: list[int],
    teacher_notes: str = "",
) -> str:
    """Build an aggregate-only prompt. Student names/IDs/scores are excluded."""

    wanted_knowledge = {str(x).strip() for x in selected_knowledge if str(x).strip()}
    wanted_questions = {int(x) for x in selected_question_ids if int(x) > 0}
    knowledge = [
        row
        for row in summary.get("knowledgeStats", [])
        if not wanted_knowledge or row.get("knowledge") in wanted_knowledge
    ]
    errors = [
        row
        for row in summary.get("commonErrors", [])
        if not wanted_questions or int(row.get("questionID") or 0) in wanted_questions
    ]
    aggregate = {
        "class": summary.get("class", {}),
        "paper": summary.get("paper", {}),
        "recipientCount": summary.get("recipientCount", 0),
        "completedCount": summary.get("completedCount", 0),
        "completionRate": summary.get("completionRate", 0),
        "averageScore": summary.get("averageScore"),
        "knowledgeStats": knowledge,
        "commonErrors": errors,
    }
    interaction = summary.get("classroomInteraction") or {}
    if interaction:
        selected_segments = [
            row
            for row in interaction.get("segments", [])
            if not wanted_knowledge or row.get("knowledge") in wanted_knowledge
        ]
        aggregate["classroomInteraction"] = {
            "sessionStatus": (interaction.get("session") or {}).get("status"),
            "quickCheckRoundCount": interaction.get("quickCheckRoundCount", 0),
            "reteachCount": interaction.get("reteachCount", 0),
            "presentationCount": interaction.get("presentationCount", 0),
            "presentationReviewCount": interaction.get("presentationReviewCount", 0),
            "teacherGrantedPoints": interaction.get("teacherGrantedPoints", 0),
            "segments": [
                {
                    "knowledge": row.get("knowledge"),
                    "mode": row.get("mode"),
                    "rounds": [
                        {
                            "round": q.get("round"),
                            "questionType": q.get("questionType"),
                            "responseCount": q.get("responseCount"),
                            "correctCount": q.get("correctCount"),
                            "accuracy": q.get("accuracy"),
                            "decision": q.get("decision"),
                        }
                        for q in row.get("quickCheckRounds", [])
                    ],
                    "reteachCount": row.get("reteachCount", 0),
                    "presentationCount": row.get("presentationCount", 0),
                    "presentationReviewCount": row.get("presentationReviewCount", 0),
                    "presentationAverages": row.get("presentationAverages", {}),
                    "teacherGrantedPoints": row.get("teacherGrantedPoints", 0),
                }
                for row in selected_segments
            ],
        }
    return f"""你是中国小学教师的课堂复盘讲义助手。
请根据下面的匿名化班级练习统计与互动课堂反馈，为教师生成一份“课堂练习情况讲义草稿”。

硬约束：
1. 不出现学生姓名、账号、学生ID、个人排名或任何可识别个人的信息。
2. 只讨论班级共性数据；互动课堂检测、补讲轨迹和讲解评价只作为本堂课反馈，不得据此推断学生长期能力。
3. 讲义面向教师课堂讲解使用，不是成绩通报。
4. 必须包含：本课练习概况、需要重点讲解的知识点、典型错误及原因、正确思路/方法、1-2个变式例题、课堂讲解建议、课后巩固建议。
5. 若完成率不足100%，明确标注“当前为阶段性数据”，不要把未完成学生当作低分学生。
6. 教师补充意见必须优先遵循，但不能泄露个人信息。
7. 只返回中文讲义正文，不要 JSON，不要 Markdown 代码块。

匿名化练习与互动课堂统计：
{json.dumps(aggregate, ensure_ascii=False)}

教师补充：
{teacher_notes.strip() or "无"}
"""


__all__ = [
    "build_anonymized_handout_prompt",
    "classroom_interaction_summary",
    "classroom_review_summary",
]
