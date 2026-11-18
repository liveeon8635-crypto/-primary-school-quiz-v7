"""Automatic learning-point fusion for every question workflow.

Rule:
* completing an objective/auto-graded submission earns one learning point per
  question (so a student who answers everything but misses every question still
  gets a record instead of zero);
* every correct answer earns one additional learning point;
* teacher-confirmed subjective work earns one point per rubric item whose
  confirmed completion ratio is at least 0.6;
* if no rubric result is available, the confirmed overall score is converted
  to the equivalent number of one-point subjective questions.

Learning points are written into the existing PointLedger.  Assigned quizzes
cannot be submitted twice, self-practice keeps one ledger record per distinct
submission, and repeated subjective grading confirmation only appends the
delta needed to reach the latest confirmed target.
"""

from __future__ import annotations

from functools import wraps
import json
from types import ModuleType
from typing import Any

from sqlalchemy.exc import IntegrityError

from changying.services.homework_learning_points import (
    award_homework_practice_points,
    is_late_care_practice,
)


LEARNING_SUBMISSION_SOURCE = "learning_submission"
LEARNING_GRADING_SOURCE = "learning_grading"
LEARNING_POINT_CATEGORY = "learning"
POINTS_PER_QUESTION = 1
COMPLETION_POINTS_PER_QUESTION = 1
CORRECT_POINTS_PER_QUESTION = 1
QUESTION_MAX_POINTS = COMPLETION_POINTS_PER_QUESTION + CORRECT_POINTS_PER_QUESTION
SUBJECTIVE_PASS_RATIO = 0.6


def _route(implementation: ModuleType, path: str, method: str):
    for route in implementation.app.routes:
        if getattr(route, "path", None) == path and method in getattr(route, "methods", set()):
            return route
    raise RuntimeError(f"route not found: {method} {path}")


def _class_id_for_submission(implementation: ModuleType, db: Any, submission: Any) -> int | None:
    assignment_id = getattr(submission, "assignment_id", None)
    if assignment_id is not None:
        assignment = db.get(implementation.Assignment, int(assignment_id))
        if assignment is not None and assignment.class_id is not None:
            return int(assignment.class_id)
    current = implementation.current_class_for(
        db,
        int(submission.student_id),
        int(submission.school_id),
    )
    return int(current.id) if current is not None else None


def _existing_submission_points(implementation: ModuleType, db: Any, submission: Any):
    return db.scalar(
        implementation.select(implementation.PointLedger).where(
            implementation.PointLedger.school_id == int(submission.school_id),
            implementation.PointLedger.student_id == int(submission.student_id),
            implementation.PointLedger.source == LEARNING_SUBMISSION_SOURCE,
            implementation.PointLedger.related_id == int(submission.id),
        ).limit(1)
    )


def award_submission_learning_points(
    implementation: ModuleType,
    db: Any,
    *,
    submission: Any,
    actor: Any,
) -> dict[str, int]:
    if submission is None or actor is None:
        return {"awarded": 0, "maximum": 0}

    if is_late_care_practice(implementation, db, submission):
        return award_homework_practice_points(
            implementation,
            db,
            submission=submission,
            actor=actor,
        )

    total = max(0, int(getattr(submission, "total", 0) or 0))
    correct = min(max(0, int(getattr(submission, "correct", 0) or 0)), total)
    maximum = total * QUESTION_MAX_POINTS
    awarded = (
        total * COMPLETION_POINTS_PER_QUESTION
        + correct * CORRECT_POINTS_PER_QUESTION
    )

    if _existing_submission_points(implementation, db, submission) is not None:
        # Assignment retries reuse the same Submission id. The existing ledger
        # row is the award; this response must not claim the points were added again.
        return {"awarded": 0, "maximum": maximum}

    if awarded > 0:
        row = implementation.PointLedger(
            school_id=int(submission.school_id),
            student_id=int(submission.student_id),
            class_id=_class_id_for_submission(implementation, db, submission),
            actor_id=None,
            rule_id=None,
            category=LEARNING_POINT_CATEGORY,
            points=awarded,
            reason=f"答题积分：{str(getattr(submission, 'title', '') or '学习练习')[:140]}",
            note=(
                f"完成{total}题×{COMPLETION_POINTS_PER_QUESTION}分"
                f" + 答对{correct}题×{CORRECT_POINTS_PER_QUESTION}分"
            ),
            source=LEARNING_SUBMISSION_SOURCE,
            related_id=int(submission.id),
            idempotency_key=f"{LEARNING_SUBMISSION_SOURCE}:{int(submission.id)}",
        )
        try:
            with db.begin_nested():
                db.add(row)
                db.flush()
        except IntegrityError:
            # Another request awarded this same submission between our check and
            # insert. The saved ledger row is the award; do not add it twice.
            return {"awarded": 0, "maximum": maximum}
        implementation.reconcile_auto_rewards(
            db,
            int(submission.school_id),
            [int(submission.student_id)],
            getattr(actor, "id", None),
        )

    return {"awarded": awarded, "maximum": maximum}


def _manual_questions(implementation: ModuleType, db: Any, assignment: Any) -> list[Any]:
    if assignment is None or assignment.paper_id is None:
        return []
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
            implementation.Question.school_id == int(assignment.school_id),
            implementation.Question.id.in_(qids),
        )
    ).all()
    qmap = {int(row.id): row for row in rows}
    ordered = [qmap[qid] for qid in qids if qid in qmap]
    return [
        question
        for question in ordered
        if implementation.manual_question_meta(question).get("manual")
    ]


def _subjective_target_points(
    implementation: ModuleType,
    db: Any,
    assignment: Any,
    review: Any,
) -> tuple[int, int]:
    questions = _manual_questions(implementation, db, assignment)
    maximum = len(questions) * POINTS_PER_QUESTION
    if maximum <= 0:
        return 0, 0

    qids = {int(question.id) for question in questions}
    try:
        ai_result = json.loads(review.ai_result_json or "{}")
    except Exception:
        ai_result = {}

    seen = set()
    passed = 0
    for raw in ai_result.get("rubric_results") or []:
        if not isinstance(raw, dict):
            continue
        try:
            qid = int(raw.get("question_id"))
        except Exception:
            continue
        if qid not in qids or qid in seen:
            continue
        seen.add(qid)
        ratio = raw.get("suggested_ratio")
        try:
            ratio = float(ratio) if ratio is not None else None
        except Exception:
            ratio = None
        if ratio is not None and ratio >= SUBJECTIVE_PASS_RATIO:
            passed += 1

    if seen:
        return passed * POINTS_PER_QUESTION, maximum

    score = getattr(review, "confirmed_score", None)
    if score is None:
        return 0, maximum
    score = max(0, min(100, int(score)))
    # Integer half-up conversion from a 0-100 score into one-point questions.
    target = (score * maximum + 50) // 100
    return int(target), maximum


def award_subjective_learning_points(
    implementation: ModuleType,
    db: Any,
    *,
    assignment: Any,
    student: Any,
    review: Any,
    actor: Any,
) -> dict[str, int]:
    target, maximum = _subjective_target_points(
        implementation,
        db,
        assignment,
        review,
    )
    rows = db.scalars(
        implementation.select(implementation.PointLedger).where(
            implementation.PointLedger.school_id == int(assignment.school_id),
            implementation.PointLedger.student_id == int(student.id),
            implementation.PointLedger.source == LEARNING_GRADING_SOURCE,
            implementation.PointLedger.related_id == int(review.id),
        )
    ).all()
    current = sum(int(row.points or 0) for row in rows)
    delta = int(target - current)

    if delta:
        db.add(
            implementation.PointLedger(
                school_id=int(assignment.school_id),
                student_id=int(student.id),
                class_id=int(assignment.class_id) if assignment.class_id is not None else None,
                actor_id=None,
                rule_id=None,
                category=LEARNING_POINT_CATEGORY,
                points=delta,
                reason=(
                    f"主观题积分：{str(assignment.title or '主观题作业')[:132]}"
                    if delta > 0
                    else f"主观题积分调整：{str(assignment.title or '主观题作业')[:128]}"
                ),
                note=(
                    f"教师确认后折算为{target}/{maximum}学习积分；"
                    f"本次调整{delta:+d}"
                ),
                source=LEARNING_GRADING_SOURCE,
                related_id=int(review.id),
            )
        )
        db.flush()
        implementation.reconcile_auto_rewards(
            db,
            int(assignment.school_id),
            [int(student.id)],
            getattr(actor, "id", None),
        )

    return {"delta": delta, "total": target, "maximum": maximum}


def install_learning_points(implementation: ModuleType) -> None:
    app = implementation.app
    if getattr(app.state, "learning_points_installed", False):
        return

    original_public = implementation.qj_public

    @wraps(original_public)
    def question_public_with_learning_points(question):
        payload = dict(original_public(question))
        payload["learningPoints"] = QUESTION_MAX_POINTS
        return payload

    implementation.qj_public = question_public_with_learning_points

    original_period_points = implementation.student_period_points

    @wraps(original_period_points)
    def student_period_points_with_learning(db, student_id, school_id, days=7):
        payload = dict(original_period_points(db, student_id, school_id, days))
        cutoff, _ = implementation.period_cutoff_utc(days)
        stats = implementation.point_period_summary(
            db,
            student_id=student_id,
            school_id=school_id,
            cutoff=cutoff,
            reason_limit=5,
        )
        payload["learning"] = int(stats.get("learning", 0) or 0)
        return payload

    implementation.student_period_points = student_period_points_with_learning

    html = implementation.INDEX_HTML
    html = html.replace(
        'head("积分奖励","课堂表现积分、奖励商城与奖励记录；自动奖励不扣积分")',
        'head("积分奖励","课堂与学习积分、奖励商城与奖励记录；自动奖励不扣积分")',
    )
    html = html.replace(
        '${stat(s.available,"可用积分")}${stat(s.earned,"累计发放")}${stat(s.activity,"课堂活动")}${stat(s.discipline,"守纪积分")}',
        '${stat(s.available,"可用积分")}${stat(s.earned,"累计发放")}${stat(s.learning||0,"学习积分")}${stat(s.activity,"课堂活动")}${stat(s.discipline,"守纪积分")}',
    )
    html = html.replace(
        '${stat(w.earned||0,"本周发放")}${stat(w.net||0,"本周净表现")}${stat(w.activity||0,"本周活动")}${stat(w.discipline||0,"本周守纪")}',
        '${stat(w.earned||0,"本周发放")}${stat(w.net||0,"本周净表现")}${stat(w.learning||0,"本周学习")}${stat(w.activity||0,"本周活动")}${stat(w.discipline||0,"本周守纪")}',
    )
    html = html.replace(
        '${stat(w.earned||0,"本周发放")}${stat(w.net||0,"净表现")}${stat(w.activity||0,"活动积分")}${stat(w.discipline||0,"守纪积分")}',
        '${stat(w.earned||0,"本周发放")}${stat(w.net||0,"净表现")}${stat(w.learning||0,"学习积分")}${stat(w.activity||0,"活动积分")}${stat(w.discipline||0,"守纪积分")}',
    )
    html = html.replace(
        'head(`${esc(d.student.name)}的课堂表现`,"课堂积分、每周表现与奖励记录",chooser)',
        'head(`${esc(d.student.name)}的积分表现`,"课堂与学习积分、每周表现与奖励记录",chooser)',
    )
    html = html.replace(
        '课堂活动${w.activity||0}分，守纪${w.discipline||0}分',
        '学习积分${w.learning||0}分，课堂活动${w.activity||0}分，守纪${w.discipline||0}分',
    )
    html = html.replace(
        '活动 ${x.activity} · 守纪 ${x.discipline} · 净表现 ${x.net}',
        '学习 ${x.learning||0} · 活动 ${x.activity} · 守纪 ${x.discipline} · 净表现 ${x.net}',
    )
    implementation.INDEX_HTML = html

    for path in (
        "/student/assignments/{aid}/submit",
        "/student/practice-submit",
    ):
        route = _route(implementation, path, "POST")
        original = route.dependant.call

        @wraps(original)
        def scored_submission(*args: Any, __original=original, __path=path, **kwargs: Any):
            result = __original(*args, **kwargs)
            db = kwargs.get("db")
            actor = kwargs.get("u")
            if db is None or actor is None or not isinstance(result, dict):
                return result
            if __path == "/student/assignments/{aid}/submit" and not result.get("pointsEligible", result.get("completed")):
                payload = dict(result)
                payload["learningPointsAwarded"] = 0
                payload["learningPointMax"] = int(result.get("total", 0) or 0)
                return payload
            submission_id = result.get("id")
            submission = (
                db.get(implementation.Submission, int(submission_id))
                if submission_id is not None
                else None
            )
            points = award_submission_learning_points(
                implementation,
                db,
                submission=submission,
                actor=actor,
            )
            is_homework = points.get("source") == "homework_practice"
            implementation.audit(
                db,
                actor,
                "points.homework.submission" if is_homework else "points.learning.submission",
                (
                    f"submission={submission_id}:points={points.get('points', points.get('awarded'))}:"
                    f"maximum={points['maximum']}"
                ),
            )
            db.commit()
            payload = dict(result)
            if is_homework:
                payload["learningPointsAwarded"] = 0
                payload["learningPointMax"] = 0
                payload["homeworkPointsAwarded"] = points["points"]
                payload["homeworkPointMax"] = points["maximum"]
                payload["homeworkPointsDetail"] = points
                payload["homeworkPointsRule"] = "晚托巩固练习：按时 +3，正确率 60% 中点上下各 3 分，扣到 0 为止"
            else:
                payload["learningPointsAwarded"] = points["awarded"]
                payload["learningPointMax"] = points["maximum"]
                payload["learningPointRule"] = (
                    f"每题完成得{COMPLETION_POINTS_PER_QUESTION}分，"
                    f"答对再加{CORRECT_POINTS_PER_QUESTION}分"
                )
            return payload

        route.dependant.call = scored_submission
        route.endpoint = scored_submission

    confirm_route = _route(
        implementation,
        "/teacher/assignments/{aid}/students/{sid}/grading-confirm",
        "POST",
    )
    original_confirm = confirm_route.dependant.call

    @wraps(original_confirm)
    def scored_subjective(*args: Any, __original=original_confirm, **kwargs: Any):
        aid = int(kwargs.get("aid") if "aid" in kwargs else args[0])
        sid = int(kwargs.get("sid") if "sid" in kwargs else args[1])
        actor = kwargs.get("u")
        db = kwargs.get("db")
        result = __original(*args, **kwargs)
        if db is None or actor is None or not isinstance(result, dict):
            return result

        assignment, student = implementation._teacher_assignment_student(
            db,
            actor,
            aid,
            sid,
        )
        review = db.scalar(
            implementation.select(implementation.AIGradingReview).where(
                implementation.AIGradingReview.school_id == int(actor.school_id),
                implementation.AIGradingReview.assignment_id == aid,
                implementation.AIGradingReview.student_id == sid,
            )
        )
        if review is None or review.status != "confirmed":
            return result

        points = award_subjective_learning_points(
            implementation,
            db,
            assignment=assignment,
            student=student,
            review=review,
            actor=actor,
        )
        implementation.audit(
            db,
            actor,
            "points.learning.subjective",
            (
                f"assignment={aid}:student={sid}:review={review.id}:"
                f"delta={points['delta']}:total={points['total']}:"
                f"maximum={points['maximum']}"
            ),
        )
        db.commit()
        payload = dict(result)
        payload["learningPointsDelta"] = points["delta"]
        payload["learningPointsTotal"] = points["total"]
        payload["learningPointMax"] = points["maximum"]
        payload["learningPointRule"] = (
            f"每道主观题{POINTS_PER_QUESTION}积分，教师确认评分点后自动折算"
        )
        return payload

    confirm_route.dependant.call = scored_subjective
    confirm_route.endpoint = scored_subjective
    app.state.learning_points_installed = True


__all__ = [
    "LEARNING_GRADING_SOURCE",
    "LEARNING_POINT_CATEGORY",
    "LEARNING_SUBMISSION_SOURCE",
    "POINTS_PER_QUESTION",
    "SUBJECTIVE_PASS_RATIO",
    "award_submission_learning_points",
    "award_subjective_learning_points",
    "install_learning_points",
]

