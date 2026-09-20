"""Teacher-confirmed rubric grading and explicit learning-evidence closure.

The legacy product already supports non-choice AI questions as photo/video
assignments and requires teacher confirmation before a score is final.  This
module makes that path structurally reliable:

* non-choice question reference answers and scoring points are stored in
  Question.answer_json instead of living only in free-form explanation text;
* AI grading receives the actual question-level rubric;
* teacher confirmation creates/updates a score-bearing Submission for media
  assignments, archives rubric-specific gaps, and appends explicit performance
  evidence to the continuous student record.

The AI remains advisory.  No score or rubric result is considered final until
the teacher confirms the grading review.
"""

from __future__ import annotations

from datetime import datetime
from functools import wraps
import json
import re
from types import ModuleType
from typing import Any

from fastapi import HTTPException


MANUAL_QUESTION_TYPES = frozenset({"non_choice"})
AUTO_QUESTION_TYPES = frozenset(
    {"single_choice", "choice", "true_false", "fill_blank", "calculation", "short_answer"}
)


def _json_object(raw: Any) -> dict[str, Any]:
    try:
        value = json.loads(raw or "{}")
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def _clean_points(value: Any) -> list[str]:
    if isinstance(value, str):
        value = re.split(r"[\n；;]+", value)
    if not isinstance(value, list):
        return []
    return [str(x).strip()[:1000] for x in value if str(x).strip()][:12]


def math_step_credit(
    scoring_points: Any,
    met_points: Any,
    missed_points: Any,
) -> dict[str, Any] | None:
    """Derive deterministic equal-weight partial credit from teacher-authored steps.

    A ratio is emitted only when every rubric point has been classified as met
    or missed. Unresolved steps stay explicitly pending teacher confirmation,
    so AI uncertainty can never silently become score credit.
    """
    points = _clean_points(scoring_points)
    if not points:
        return None
    met_set = set(_clean_points(met_points))
    missed_set = set(_clean_points(missed_points)) - met_set
    met = [point for point in points if point in met_set]
    missed = [point for point in points if point in missed_set]
    unresolved = [point for point in points if point not in met_set and point not in missed_set]
    ratio = None if unresolved else round(len(met) / len(points), 4)
    return {
        "earnedSteps": len(met),
        "totalSteps": len(points),
        "missedSteps": len(missed),
        "unresolvedSteps": len(unresolved),
        "unresolvedPoints": unresolved,
        "ratio": ratio,
        "weightPolicy": "equal",
    }


def manual_question_meta(question: Any) -> dict[str, Any]:
    """Return structured rubric metadata with a legacy explanation fallback."""
    data = _json_object(getattr(question, "answer_json", "{}"))
    reference = str(
        data.get("reference_answer")
        or data.get("referenceAnswer")
        or ""
    ).strip()
    points = _clean_points(data.get("scoring_points") or data.get("scoringPoints"))
    grading = str(data.get("grading") or "").strip()

    explanation = str(getattr(question, "explanation", "") or "")
    if not reference:
        match = re.search(
            r"参考答案[:：]\s*(.*?)(?=\n评分要点[:：]|\n解析[:：]|$)",
            explanation,
            flags=re.DOTALL,
        )
        if match:
            reference = match.group(1).strip()
    if not points:
        match = re.search(
            r"评分要点[:：]\s*(.*?)(?=\n解析[:：]|$)",
            explanation,
            flags=re.DOTALL,
        )
        if match:
            points = _clean_points(match.group(1))

    qtype = str(getattr(question, "question_type", "") or "").strip().lower()
    if not qtype:
        try:
            options = json.loads(getattr(question, "options_json", "") or "[]")
        except Exception:
            options = []
        if not options and int(getattr(question, "correct_index", -1)) < 0:
            qtype = "non_choice"

    return {
        "manual": qtype in MANUAL_QUESTION_TYPES or bool(reference or points),
        "question_type": qtype or "non_choice",
        "reference_answer": reference,
        "scoring_points": points,
        "grading": grading or ("teacher_review" if reference or points else ""),
    }


def structured_manual_answer_json(question_body: Any) -> str:
    points = _clean_points(getattr(question_body, "scoring_points", []))
    reference = str(getattr(question_body, "reference_answer", "") or "").strip()
    return json.dumps(
        {
            "grading": "teacher_review",
            "reference_answer": reference,
            "scoring_points": points,
        },
        ensure_ascii=False,
    )


def _route(implementation: ModuleType, path: str, method: str):
    for route in implementation.app.routes:
        if getattr(route, "path", None) == path and method in getattr(route, "methods", set()):
            return route
    raise RuntimeError(f"route not found: {method} {path}")


def _enrich_saved_non_choice_questions(
    implementation: ModuleType,
    db: Any,
    bodies: list[Any],
    question_ids: list[Any],
) -> None:
    for body, qid in zip(bodies, question_ids):
        qtype = str(getattr(body, "question_type", "") or "").strip().lower()
        if qtype != "non_choice":
            continue
        # IDs are returned by the already-authorized save/assign route.
        row = db.get(implementation.Question, int(qid))
        if row is None:
            continue
        row.question_type = "non_choice"
        row.answer_json = structured_manual_answer_json(body)



def _paper_questions(implementation: ModuleType, db: Any, assignment: Any) -> list[Any]:
    paper = db.get(implementation.Paper, int(assignment.paper_id))
    if paper is None:
        return []
    try:
        qids = [int(x) for x in json.loads(paper.question_ids_json or "[]")]
    except Exception:
        qids = []
    if not qids:
        return []
    rows = db.scalars(
        implementation.select(implementation.Question).where(
            implementation.Question.school_id == assignment.school_id,
            implementation.Question.id.in_(qids),
        )
    ).all()
    mapping = {int(row.id): row for row in rows}
    return [mapping[qid] for qid in qids if qid in mapping]


def _rubric_context(questions: list[Any]) -> list[dict[str, Any]]:
    result = []
    for question in questions:
        meta = manual_question_meta(question)
        if not meta["manual"]:
            continue
        result.append(
            {
                "question_id": int(question.id),
                "subject": str(question.subject or ""),
                "knowledge": str(question.knowledge or ""),
                "question": str(question.text or ""),
                "reference_answer": meta["reference_answer"],
                "scoring_points": meta["scoring_points"],
            }
        )
    return result


def _quiz_context(implementation: ModuleType, questions: list[Any], submission: Any) -> list[dict[str, Any]]:
    if submission is None:
        return []
    qmap = {int(q.id): q for q in questions}
    try:
        answers = json.loads(submission.answers_json or "[]")
    except Exception:
        answers = []
    result = []
    for answer in answers:
        if not isinstance(answer, dict):
            continue
        question = qmap.get(int(answer.get("question_id") or 0))
        if question is None:
            continue
        qtype = implementation.question_type_of(question)
        if qtype in {"single_choice", "choice", "true_false"}:
            try:
                options = json.loads(question.options_json or "[]")
            except Exception:
                options = []
            try:
                selected_index = int(answer.get("selected_index", -1))
            except Exception:
                selected_index = -1
            selected = (
                options[selected_index]
                if isinstance(options, list) and 0 <= selected_index < len(options)
                else "未答"
            )
            correct = (
                options[question.correct_index]
                if isinstance(options, list) and 0 <= question.correct_index < len(options)
                else ""
            )
        else:
            selected = str(answer.get("text_answer") or "")
            meta = implementation.question_answer_meta(question)
            correct = meta.get("answer") or ""
        result.append(
            {
                "question_id": int(question.id),
                "knowledge": str(question.knowledge or ""),
                "question": str(question.text or ""),
                "student_answer": selected,
                "reference_answer": correct,
                "auto_correct": answer.get("correct"),
                "explanation": str(question.explanation or ""),
            }
        )
    return result


def _grading_assist_call(implementation: ModuleType):
    # Parameter names intentionally match the already-built FastAPI dependant
    # for the legacy route (b, u, db).
    def grade_assist(b, u, db):
        body = b
        implementation.need(u, "teacher")
        cfg = implementation.ai_config_for(db, u.school_id, False)
        if not cfg or not cfg.allow_student_data:
            raise HTTPException(
                403,
                "学校管理员尚未允许将学生作业内容发送到已配置的 AI 服务商",
            )
        assignment = db.scalar(
            implementation.select(implementation.Assignment)
            .join(
                implementation.SchoolClass,
                implementation.Assignment.class_id == implementation.SchoolClass.id,
            )
            .where(
                implementation.Assignment.id == body.assignment_id,
                implementation.Assignment.school_id == u.school_id,
                implementation.SchoolClass.teacher_id == u.id,
            )
        )
        if assignment is None:
            raise HTTPException(404, "作业不存在或无权限")
        if not db.scalar(
            implementation.select(implementation.AssignmentRecipient.id).where(
                implementation.AssignmentRecipient.assignment_id == assignment.id,
                implementation.AssignmentRecipient.student_id == body.student_id,
                implementation.AssignmentRecipient.school_id == u.school_id,
            )
        ):
            raise HTTPException(404, "学生不在该作业接收名单")

        questions = _paper_questions(implementation, db, assignment)
        submission = db.scalar(
            implementation.select(implementation.Submission)
            .where(
                implementation.Submission.school_id == u.school_id,
                implementation.Submission.assignment_id == assignment.id,
                implementation.Submission.student_id == body.student_id,
            )
            .order_by(implementation.Submission.id.desc())
            .limit(1)
        )
        quiz = _quiz_context(implementation, questions, submission)
        rubrics = _rubric_context(questions)
        images = implementation._ai_images_for_homework(
            db,
            u.school_id,
            assignment.id,
            body.student_id,
        )
        mode = implementation.assignment_submission_mode(db, assignment)
        if not quiz and not images:
            raise HTTPException(400, "该学生还没有可供 AI 分析的在线答题或照片作业")

        prompt = f"""你是小学教师的“批改辅助”助手，不是最终评分者。请基于以下作业信息和评分点给老师建议。不得根据姓名、性别、家庭等身份信息推断能力；不要输出敏感个人信息。
作业：{assignment.title}；提交方式：{implementation.assignment_mode_name(mode)}。
在线答题数据（可能为空）：{json.dumps(quiz, ensure_ascii=False)}
非选择题评分依据（可能为空）：{json.dumps(rubrics, ensure_ascii=False)}
教师补充：{body.teacher_note or '无'}
另外附带 {len(images)} 张学生作业照片（如有）。

要求：
1. 对每道有评分依据的非选择题，按 reference_answer 与 scoring_points 逐点核对；看不清或无法确认的点必须写“需教师确认”，不得猜测。
2. rubric_results 中每题必须保留 question_id、knowledge；met_points / missed_points 只能来自给定 scoring_points，不能自行虚构评分点。
3. suggested_ratio 为 0-1 之间的小数，表示该题评分点完成程度；若无法判断则为 null。
4. suggested_score 仅为整份作业 0-100 的建议分或 null，最终成绩必须由教师确认。
5. 只返回 JSON，不要 Markdown：
{{"summary":"","strengths":[""],"issues":[{{"problem":"","knowledge":"","suggestion":"","confidence":"高/中/低"}}],"rubric_results":[{{"question_id":0,"knowledge":"","met_points":[""],"missed_points":[""],"suggested_ratio":null,"needs_teacher_review":[""]}}],"suggested_score":null,"feedback_to_student":"","needs_teacher_review":[""]}}。
"""
        data = implementation._ai_json(
            implementation._ai_call(
                db,
                u,
                "grading_assist",
                prompt,
                images=images,
                timeout=120,
            )
        )
        if not isinstance(data, dict):
            raise HTTPException(502, "AI 批改建议格式无效")
        suggested = data.get("suggested_score")
        try:
            suggested = int(suggested) if suggested is not None else None
        except Exception:
            suggested = None
        if suggested is not None:
            suggested = max(0, min(100, suggested))

        # Sanitize rubric results against the actual teacher-reviewed rubric.
        rubric_by_id = {int(x["question_id"]): x for x in rubrics}
        cleaned_results = []
        for raw in data.get("rubric_results") or []:
            if not isinstance(raw, dict):
                continue
            try:
                qid = int(raw.get("question_id"))
            except Exception:
                continue
            rubric = rubric_by_id.get(qid)
            if rubric is None:
                continue
            allowed = set(rubric.get("scoring_points") or [])
            met = [str(x) for x in raw.get("met_points") or [] if str(x) in allowed]
            missed = [str(x) for x in raw.get("missed_points") or [] if str(x) in allowed and str(x) not in met]
            ratio = raw.get("suggested_ratio")
            try:
                ratio = float(ratio) if ratio is not None else None
            except Exception:
                ratio = None
            if ratio is not None:
                ratio = max(0.0, min(1.0, ratio))

            review_notes = [
                str(x)[:500]
                for x in (raw.get("needs_teacher_review") or [])
                if str(x).strip()
            ][:8]
            step_credit = None
            if "数学" in str(rubric.get("subject") or "") and allowed:
                step_credit = math_step_credit(
                    rubric.get("scoring_points") or [],
                    met,
                    missed,
                )
                if step_credit is not None:
                    # For math calculation/application rubrics, the completion
                    # ratio must come from the actual teacher-authored steps,
                    # not a free-form AI percentage.
                    ratio = step_credit["ratio"]
                    for point in step_credit.get("unresolvedPoints") or []:
                        note = f"评分点待教师确认：{point}"[:500]
                        if note not in review_notes and len(review_notes) < 8:
                            review_notes.append(note)

            cleaned = {
                "question_id": qid,
                "knowledge": rubric.get("knowledge") or "",
                "met_points": met,
                "missed_points": missed,
                "suggested_ratio": ratio,
                "needs_teacher_review": review_notes,
            }
            if step_credit is not None:
                cleaned["step_credit"] = step_credit
            cleaned_results.append(cleaned)
        data["rubric_results"] = cleaned_results

        review = db.scalar(
            implementation.select(implementation.AIGradingReview).where(
                implementation.AIGradingReview.school_id == u.school_id,
                implementation.AIGradingReview.assignment_id == assignment.id,
                implementation.AIGradingReview.student_id == body.student_id,
            )
        )
        now = datetime.utcnow()
        if review is None:
            review = implementation.AIGradingReview(
                school_id=u.school_id,
                assignment_id=assignment.id,
                student_id=body.student_id,
                teacher_id=u.id,
            )
            db.add(review)
        review.teacher_id = u.id
        review.ai_result_json = json.dumps(data, ensure_ascii=False)
        review.suggested_score = suggested
        review.status = "draft"
        review.updated_at = now
        review.confirmed_at = None
        implementation.audit(
            db,
            u,
            "ai.grade.assist",
            f"assignment={assignment.id}:student={body.student_id}:images={len(images)}:quiz={len(quiz)}:rubrics={len(rubrics)}",
        )
        db.commit()
        db.refresh(review)
        return {
            "result": data,
            "review": implementation._grading_review_payload(review),
            "reviewRequired": True,
            "notice": "AI只按教师已审核的参考答案和评分要点提供建议；数学计算/应用题按评分点等权折算步骤部分得分，存在未确认步骤时不自动形成完成度；最终成绩、错题与学习证据必须由教师确认。",
            "imagesUsed": len(images),
            "quizItemsUsed": len(quiz),
            "rubricItemsUsed": len(rubrics),
        }

    return grade_assist


def _evidence_context(marker: str, **payload: Any) -> str:
    data = {"marker": marker, **payload}
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _active_event_for_key(
    implementation: ModuleType,
    db: Any,
    *,
    school_id: int,
    student_id: int,
    source_type: str,
    marker: str,
    review_id: int,
    question_id: int | None = None,
):
    rows = db.scalars(
        implementation.select(implementation.LearningEvidenceEvent).where(
            implementation.LearningEvidenceEvent.school_id == school_id,
            implementation.LearningEvidenceEvent.student_id == student_id,
        )
    ).all()
    retracted = {
        int(row.target_event_id)
        for row in rows
        if row.event_kind == "retract" and row.target_event_id is not None
    }
    for row in reversed(rows):
        if (
            row.event_kind != "record"
            or row.source_type != source_type
            or int(row.id) in retracted
        ):
            continue
        data = _json_object(row.context)
        if data.get("marker") != marker:
            continue
        try:
            if int(data.get("reviewID")) != int(review_id):
                continue
        except Exception:
            continue
        if question_id is not None:
            try:
                if int(data.get("questionID")) != int(question_id):
                    continue
            except Exception:
                continue
        return row
    return None


def _replace_event_if_needed(
    implementation: ModuleType,
    db: Any,
    teacher: Any,
    *,
    student_id: int,
    source_type: str,
    marker: str,
    review_id: int,
    context: str,
    question_id: int | None = None,
) -> bool:
    existing = _active_event_for_key(
        implementation,
        db,
        school_id=int(teacher.school_id),
        student_id=int(student_id),
        source_type=source_type,
        marker=marker,
        review_id=review_id,
        question_id=question_id,
    )
    if existing is None:
        return True
    if (existing.context or "") == context:
        return False
    db.add(
        implementation.LearningEvidenceEvent(
            school_id=int(teacher.school_id),
            student_id=int(student_id),
            actor_id=int(teacher.id),
            event_kind="retract",
            target_event_id=int(existing.id),
            evidence_type=existing.evidence_type,
            subject=existing.subject or "",
            knowledge_key=existing.knowledge_key or "",
            success=existing.success,
            note="教师重新确认评分，旧学习证据失效",
            context=existing.context or "",
            source_type=source_type + "_retraction",
            occurred_at=datetime.utcnow(),
        )
    )
    return True


def _append_teacher_confirmed_evidence(
    implementation: ModuleType,
    db: Any,
    teacher: Any,
    assignment: Any,
    student_id: int,
    review: Any,
) -> int:
    paper = db.get(implementation.Paper, int(assignment.paper_id))
    subject = str(paper.subject if paper else "")
    review_context = _evidence_context(
        "teacher_confirmed_grading",
        assignmentID=int(assignment.id),
        reviewID=int(review.id),
        score=review.confirmed_score,
    )
    added = 0
    if _replace_event_if_needed(
        implementation,
        db,
        teacher,
        student_id=int(student_id),
        source_type="teacher_confirmed_grading",
        marker="teacher_confirmed_grading",
        review_id=int(review.id),
        context=review_context,
    ):
        db.add(
            implementation.LearningEvidenceEvent(
                school_id=int(teacher.school_id),
                student_id=int(student_id),
                actor_id=int(teacher.id),
                event_kind="record",
                target_event_id=None,
                evidence_type="performance",
                subject=subject,
                knowledge_key="",
                success=None,
                note=(review.teacher_feedback or "教师确认主观题批改")[:1000],
                context=review_context,
                source_type="teacher_confirmed_grading",
                occurred_at=review.confirmed_at or datetime.utcnow(),
            )
        )
        added += 1

    try:
        ai_result = json.loads(review.ai_result_json or "{}")
    except Exception:
        ai_result = {}
    questions = _paper_questions(implementation, db, assignment)
    qmap = {int(q.id): q for q in questions}
    for raw in ai_result.get("rubric_results") or []:
        if not isinstance(raw, dict):
            continue
        try:
            qid = int(raw.get("question_id"))
        except Exception:
            continue
        question = qmap.get(qid)
        if question is None:
            continue
        ratio = raw.get("suggested_ratio")
        try:
            ratio = float(ratio) if ratio is not None else None
        except Exception:
            ratio = None
        success = None if ratio is None else bool(ratio >= 0.6)
        context = _evidence_context(
            "teacher_confirmed_rubric",
            assignmentID=int(assignment.id),
            reviewID=int(review.id),
            questionID=qid,
            ratio=ratio,
            met=raw.get("met_points") or [],
            missed=raw.get("missed_points") or [],
            stepCredit=raw.get("step_credit") or {},
        )
        if not _replace_event_if_needed(
            implementation,
            db,
            teacher,
            student_id=int(student_id),
            source_type="teacher_confirmed_rubric",
            marker="teacher_confirmed_rubric",
            review_id=int(review.id),
            context=context,
            question_id=qid,
        ):
            continue
        db.add(
            implementation.LearningEvidenceEvent(
                school_id=int(teacher.school_id),
                student_id=int(student_id),
                actor_id=int(teacher.id),
                event_kind="record",
                target_event_id=None,
                evidence_type="performance",
                subject=str(question.subject or subject),
                knowledge_key=str(question.knowledge or ""),
                success=success,
                note=("；".join(str(x) for x in (raw.get("missed_points") or [])))[:1000],
                context=context,
                source_type="teacher_confirmed_rubric",
                occurred_at=review.confirmed_at or datetime.utcnow(),
            )
        )
        added += 1
    return added


def _ensure_media_score_submission(
    implementation: ModuleType,
    db: Any,
    assignment: Any,
    student: Any,
    confirmed_score: int | None,
):
    if confirmed_score is None:
        return None
    existing = db.scalar(
        implementation.select(implementation.Submission)
        .where(
            implementation.Submission.school_id == assignment.school_id,
            implementation.Submission.assignment_id == assignment.id,
            implementation.Submission.student_id == student.id,
        )
        .order_by(implementation.Submission.id.desc())
        .limit(1)
    )
    if existing is not None:
        existing.score = int(confirmed_score)
        return existing
    row = implementation.Submission(
        school_id=int(assignment.school_id),
        assignment_id=int(assignment.id),
        student_id=int(student.id),
        title=str(assignment.title or "主观题作业")[:160],
        score=int(confirmed_score),
        correct=0,
        total=0,
        answers_json="[]",
        submitted_at=datetime.utcnow(),
    )
    db.add(row)
    db.flush()
    return row


def _archive_rubric_gaps(
    implementation: ModuleType,
    db: Any,
    teacher: Any,
    assignment: Any,
    student: Any,
    review: Any,
) -> int:
    try:
        ai_result = json.loads(review.ai_result_json or "{}")
    except Exception:
        ai_result = {}
    questions = _paper_questions(implementation, db, assignment)
    qmap = {int(q.id): q for q in questions}
    added = 0
    for raw in ai_result.get("rubric_results") or []:
        if not isinstance(raw, dict):
            continue
        missed = [str(x).strip() for x in (raw.get("missed_points") or []) if str(x).strip()]
        if not missed:
            continue
        try:
            qid = int(raw.get("question_id"))
        except Exception:
            continue
        question = qmap.get(qid)
        if question is None:
            continue
        existing = db.scalar(
            implementation.select(implementation.WrongQuestionRecord).where(
                implementation.WrongQuestionRecord.school_id == teacher.school_id,
                implementation.WrongQuestionRecord.student_id == student.id,
                implementation.WrongQuestionRecord.assignment_id == assignment.id,
                implementation.WrongQuestionRecord.question_id == qid,
            )
        )
        meta = manual_question_meta(question)
        if existing is None:
            existing = implementation.WrongQuestionRecord(
                school_id=int(teacher.school_id),
                student_id=int(student.id),
                assignment_id=int(assignment.id),
                question_id=qid,
                source="ai",
                subject=str(question.subject or ""),
                knowledge=str(question.knowledge or ""),
                problem_text=str(question.text or ""),
                status="active",
            )
            db.add(existing)
            added += 1
        existing.wrong_answer = "见教师确认的主观题作答"
        existing.correct_answer = meta["reference_answer"]
        existing.analysis = ("未达到评分要点：" + "；".join(missed))[:3000]
        existing.teacher_feedback = (review.teacher_feedback or "")[:3000]
        existing.status = "active"
        existing.mastered_at = None
    return added


def install_rubric_evidence_closure(implementation: ModuleType) -> None:
    app = implementation.app
    if getattr(app.state, "rubric_evidence_closure_installed", False):
        return

    # Enrich AI non-choice questions immediately after their existing audited
    # save/assign route succeeds.
    for path in ("/ai/questions/save", "/ai/questions/assign"):
        route = _route(implementation, path, "POST")
        original = route.dependant.call

        @wraps(original)
        def enriched(*args: Any, __original=original, **kwargs: Any):
            result = __original(*args, **kwargs)
            body = kwargs.get("b") or (args[0] if args else None)
            db = kwargs.get("db")
            if db is None or body is None or not isinstance(result, dict):
                return result
            qids = result.get("questionIDs")
            if qids is None:
                qids = [x.get("id") for x in result.get("items") or [] if isinstance(x, dict)]
            _enrich_saved_non_choice_questions(
                implementation,
                db,
                list(getattr(body, "questions", []) or []),
                [int(x) for x in (qids or []) if x is not None],
            )
            db.commit()
            return result

        route.dependant.call = enriched
        route.endpoint = enriched

    # Replace only the grading-assist callable; route contract remains unchanged.
    grade_route = _route(implementation, "/ai/homework/grade-assist", "POST")
    grade_call = _grading_assist_call(implementation)
    grade_route.dependant.call = grade_call
    grade_route.endpoint = grade_call

    # Keep the mature confirmation route, then close score/evidence/rubric gaps.
    confirm_route = _route(
        implementation,
        "/teacher/assignments/{aid}/students/{sid}/grading-confirm",
        "POST",
    )
    original_confirm = confirm_route.dependant.call

    @wraps(original_confirm)
    def confirmed(*args: Any, __original=original_confirm, **kwargs: Any):
        aid = int(kwargs.get("aid") if "aid" in kwargs else args[0])
        sid = int(kwargs.get("sid") if "sid" in kwargs else args[1])
        teacher = kwargs.get("u")
        db = kwargs.get("db")
        result = __original(*args, **kwargs)
        if db is None or teacher is None:
            return result
        assignment, student = implementation._teacher_assignment_student(
            db,
            teacher,
            aid,
            sid,
        )
        review = db.scalar(
            implementation.select(implementation.AIGradingReview).where(
                implementation.AIGradingReview.school_id == teacher.school_id,
                implementation.AIGradingReview.assignment_id == aid,
                implementation.AIGradingReview.student_id == sid,
            )
        )
        if review is None or review.status != "confirmed":
            return result

        submission = _ensure_media_score_submission(
            implementation,
            db,
            assignment,
            student,
            review.confirmed_score,
        )
        rubric_wrong = _archive_rubric_gaps(
            implementation,
            db,
            teacher,
            assignment,
            student,
            review,
        )
        evidence_added = _append_teacher_confirmed_evidence(
            implementation,
            db,
            teacher,
            assignment,
            sid,
            review,
        )
        implementation.audit(
            db,
            teacher,
            "grading.evidence.close",
            f"assignment={aid}:student={sid}:submission={getattr(submission,'id',None)}:rubricWrong={rubric_wrong}:evidence={evidence_added}",
        )
        db.commit()
        if isinstance(result, dict):
            payload = dict(result)
            payload["learningEvidenceAdded"] = evidence_added
            payload["rubricWrongArchived"] = rubric_wrong
            payload["scoreRecordedInProgress"] = submission is not None
            payload["notice"] = (
                "教师确认已保存；主观题评分点、成绩和薄弱知识已进入学生连续学习记录。"
            )
            return payload
        return result

    confirm_route.dependant.call = confirmed
    confirm_route.endpoint = confirmed
    app.state.rubric_evidence_closure_installed = True


__all__ = [
    "MANUAL_QUESTION_TYPES",
    "install_rubric_evidence_closure",
    "manual_question_meta",
    "math_step_credit",
    "structured_manual_answer_json",
]
