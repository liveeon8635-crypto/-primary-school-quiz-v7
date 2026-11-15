"""Student help flow of the after-school homework assistant (behind the same ``HOMEWORK_ASSISTANT`` flag).

Photo -> recognised text -> the student confirms or edits the text -> a ``help_requests`` row.
The photo only ever exists in memory while it is recognised; nothing in this module stores it.

The answer is a guide the pupil works through himself (see ``services/homework_guidance``): it starts from what his
published knowledge map says he already knows, and how far he got on his own is kept with the request for the
teacher (``/progress``; the first report wins, like every first answer in the product).
"""

from __future__ import annotations

import json
import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, insert, select, update

from changying.services import knowledge_maps as km
from changying.services.homework_guidance import check_steps, exam_line, guide_layer, map_lines, pick_node
from changying.services.homework_circle_support import CircleSupportBody, circle_area_question, circle_prompt_context, circle_support_record, circle_support_summary

from changying.services.homework_limits import (
    ai_slot,
    check_new_help_request,
    check_student_call,
    require_student_ai,
)
from changying.services.homework_knowledge import record_ai_help
from changying.services.homework_math_check import MISMATCH, OK, check_solution
from changying.services.homework_prompts import AI_WARNING, MAX_STEPS, build_solve_prompt, clean_solution
from changying.services.homework_vision import QUESTION_PROMPT, read_image_body, recognize_image
from changying.web.exam_prep_views import register_exam_prep_tables
from changying.web.homework_assistant import require_enabled
from changying.web.knowledge_map_views import knowledge_map_enabled, register_knowledge_map_table

LOGGER = logging.getLogger(__name__)
MAX_QUESTION_CHARS = 1000
VISION_FEATURE = "homework_help_vision"
SOLVE_FEATURE = "homework_help_solve"
SOLVE_TIMEOUT_SECONDS = 45  # a guide (a question, a hint and an explanation per step) is longer than a plain answer
SOLVE_CLAIM_TTL_SECONDS = 120
_CLAIM_LOCK = threading.Lock()
_CLAIMS: dict[int, float] = {}
NO_CONFIDENCE = "这道题我没有把握，已请老师帮忙。"
HELP_RETENTION_DAYS = 90  # the conversation; the knowledge-level record (homework_ai_knowledge) is permanent
PURGE_BATCH = 200
REASON_LABELS = {
    "verify_mismatch": "AI 的答案没有通过核对",
    "student_request": "学生请求老师帮忙",
}


class EscalateBody(BaseModel):
    note: str = ""


class ResolveBody(BaseModel):
    note: str = ""


class ProgressBody(BaseModel):
    selfSolved: bool = False
    revealed: bool = False
    finalChecked: bool = False
    wrongTries: int = Field(default=0, ge=0, le=99)
    stepsAnswered: int = Field(default=0, ge=0, le=MAX_STEPS)


class HelpBody(BaseModel):
    questionText: str
    grade: int | None = None
    noticeID: int | None = None
    itemSeq: int | None = None


def _mapping(row: Any) -> dict[str, Any]:
    if row is None:
        return {}
    return dict(row._mapping) if hasattr(row, "_mapping") else dict(row)


def _iso(value: Any) -> str:
    return value.strftime("%Y-%m-%d %H:%M") if hasattr(value, "strftime") else ""


def _json_obj(raw: Any) -> dict[str, Any]:
    try:
        value = json.loads(raw or "{}")
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


class FollowUpShownBody(BaseModel):
    """老师确实看到这些建议时回传的 helpID 列表。"""
    helpIDs: list[int] = []


FOLLOW_UP_DAILY_LIMIT = 5


def _local_day() -> str:
    """按学校时区（UTC+8）取日期，预算按天重置。"""
    return (datetime.utcnow() + timedelta(hours=8)).strftime("%Y-%m-%d")


def _item_key(item: dict[str, Any]) -> str:
    return str(item.get("itemKey") or f"homework:{item['helpID']}")


def follow_up_state(db: Any, teacher: Any) -> dict[str, set[Any]]:
    """读这位老师的展示/处理/暂缓记录。

    dismissed 永久生效（不限窗口）；shown/snoozed 只看当天。
    dismissedStudents 只含"今天"处理过的学生（当天不再推该学生的其它求助）。
    """
    from app_v924 import AuditLog  # 延迟导入：本模块由 app_v924 装载

    day = _local_day()
    out: dict[str, set[Any]] = {
        "shown": set(), "dismissed": set(), "snoozed": set(),
        "shownKeys": set(), "dismissedKeys": set(), "snoozedKeys": set(),
        "shownStudents": set(), "dismissedStudents": set(), "snoozedStudents": set(),
    }

    def load(detail: Any) -> dict[str, Any]:
        try:
            return json.loads(detail or "{}")
        except ValueError:
            return {}

    def key_of(d: dict[str, Any]) -> str | None:
        if isinstance(d.get("itemKey"), str) and d["itemKey"]:
            return d["itemKey"]
        if isinstance(d.get("helpID"), int):
            return f"homework:{d['helpID']}"
        return None

    # 永久：dismissed 不分窗口
    for (detail,) in db.execute(
        select(AuditLog.detail).where(
            AuditLog.school_id == teacher.school_id,
            AuditLog.user_id == teacher.id,
            AuditLog.action == "follow_up_dismissed",
        )
    ).all():
        d = load(detail)
        hid = d.get("helpID")
        k = key_of(d)
        if isinstance(hid, int):
            out["dismissed"].add(hid)
        if k:
            out["dismissedKeys"].add(k)
        if (isinstance(hid, int) or k) and d.get("day") == day and isinstance(d.get("studentID"), int):
            out["dismissedStudents"].add(d["studentID"])

    # 当天：shown / snoozed
    for action, detail in db.execute(
        select(AuditLog.action, AuditLog.detail).where(
            AuditLog.school_id == teacher.school_id,
            AuditLog.user_id == teacher.id,
            AuditLog.action.in_(("follow_up_shown", "follow_up_snoozed")),
            AuditLog.created_at >= datetime.utcnow() - timedelta(days=1),
        )
    ).all():
        d = load(detail)
        if d.get("day") != day:
            continue
        hid = d.get("helpID")
        sid = d.get("studentID")
        k = key_of(d)
        if not isinstance(hid, int) and not k:
            continue
        if action == "follow_up_shown":
            if isinstance(hid, int):
                out["shown"].add(hid)
            if k:
                out["shownKeys"].add(k)
            if isinstance(sid, int):
                out["shownStudents"].add(sid)
        else:
            if isinstance(hid, int):
                out["snoozed"].add(hid)
            if k:
                out["snoozedKeys"].add(k)
            if isinstance(sid, int):
                out["snoozedStudents"].add(sid)
    return out


def install_homework_help(implementation: Any) -> APIRouter:
    app = implementation.app
    if getattr(app.state, "homework_help_installed", False):
        return app.state.homework_help_router

    tables = app.state.homework_tables
    notices, recipients, helps = tables["homework_notices"], tables["homework_recipients"], tables["help_requests"]

    current_user = implementation.current_user
    get_db = implementation.get_db
    need = implementation.need
    router = APIRouter(dependencies=[Depends(require_enabled)])

    def own_help(db: Any, user: Any, help_id: int, *, lock: bool = False) -> dict[str, Any]:
        query = select(helps).where(
                helps.c.id == help_id, helps.c.student_id == user.id, helps.c.school_id == user.school_id
            )
        row = db.execute(query.with_for_update() if lock else query).first()
        if row is None:
            raise HTTPException(404, "没有这条求助")
        return _mapping(row)

    def student_help_json(row: dict[str, Any]) -> dict[str, Any]:
        data = _json_obj(row["ai_json"])
        solution = None
        message = ""
        if row["state"] in ("answered", "resolved") and data.get("steps") and not data.get("hidden"):
            solution = {
                "method": data.get("method", ""),
                "steps": [{k: v for k, v in step.items() if k != "expression"} for step in data["steps"]],
                "answer": data.get("answer", ""),
                "knowledgePoint": data.get("knowledgePoint", ""),
                "start": data.get("start", ""),
                "life": data.get("life", ""),
                "finalCheck": data.get("finalCheck"),
                "layer": data.get("layer"),
                "warning": AI_WARNING,
            }
        elif row["state"] == "escalated":
            message = NO_CONFIDENCE if row["escalate_reason"] == "verify_mismatch" else "已请老师帮忙。"
        return {
            "id": row["id"],
            "grade": row["grade"],
            "questionText": row["question_text"],
            "state": row["state"],
            "verifyStatus": row["verify_status"],
            "studentNote": row["student_note"],
            "createdAt": _iso(row["created_at"]),
            "solution": solution,
            "message": message,
            "warning": AI_WARNING,
            "circleEligible": circle_area_question(row["question_text"], row["grade"]),
            "circleSupport": circle_support_record(data.get("circleSupport")),
        }

    User = implementation.User
    SchoolClass = implementation.SchoolClass
    ClassStudent = implementation.ClassStudent
    maps = register_knowledge_map_table(implementation)
    goals = register_exam_prep_tables(implementation)["exam_goals"]

    def map_context(db: Any, u: Any, grade: int) -> dict[str, Any] | None:
        """The published knowledge map of this grade with the pupil's first-answer mastery, if the school has one."""
        if not knowledge_map_enabled():
            return None
        row = db.execute(
            select(maps).where(maps.c.school_id == u.school_id, maps.c.grade == int(grade), maps.c.published_json.is_not(None))
            .order_by(maps.c.published_at.desc(), maps.c.id.desc())
        ).first()
        if row is None:
            return None
        lists = []
        for raw in db.scalars(select(implementation.Submission.answers_json).where(
                implementation.Submission.school_id == u.school_id, implementation.Submission.student_id == u.id)
                .order_by(implementation.Submission.submitted_at, implementation.Submission.id)):
            try:
                lists.append(json.loads(raw or "[]"))
            except ValueError:
                continue
        m = json.loads(row.published_json)
        first = km.first_attempts(lists)
        return {"id": row.id, "grade": int(grade), "map": m, "first": first, "mastery": km.mastery_view(m, first)[0]}

    def optional(db: Any, work: Any) -> Any:
        """The map only enriches the guide: a problem reading it must never cost the pupil his answer."""
        try:
            return work()
        except Exception:  # noqa: BLE001
            db.rollback()       # only reads happened; the claimed request is already committed
            LOGGER.exception("homework_help_map_context_failed")
            return None

    def layer_of(db: Any, u: Any, ctx: dict[str, Any], solution: dict[str, Any]) -> dict[str, Any] | None:
        m = ctx["map"]
        node = pick_node(m, solution.get("nodeKey", ""), solution.get("knowledgePoint", ""))
        if node is None:
            return None
        names = {n["key"]: n for n in m["nodes"]}
        right = [int(q) for key in [node["key"], *node["prereqs"]] if key in names for q in names[key]["levels"]
                 if ctx["first"].get(int(q)) is True]
        texts = {}
        if right:
            for q in db.scalars(select(implementation.Question).where(
                    implementation.Question.school_id == u.school_id, implementation.Question.id.in_(right))):
                if not implementation.question_figure(q):      # a question that needs its figure says little as text
                    texts[q.id] = str(implementation.qj_public(q)["text"] or "")
        exam = ""
        classes = select(ClassStudent.class_id).where(ClassStudent.student_id == u.id)
        today = datetime.now(implementation.SCHOOL_TZ).date()
        for g in db.execute(select(goals).where(goals.c.school_id == u.school_id, goals.c.map_id == ctx["id"],
                                                goals.c.class_id.in_(classes)).order_by(goals.c.exam_date)):
            if node["unit"] in json.loads(g.unit_keys_json or "[]") and g.exam_date >= today.isoformat():
                exam = exam_line(g.title, g.exam_date, today)
                break
        layer = guide_layer(m, node, ctx["mastery"], ctx["first"], texts, exam)
        # A published point alone does not guarantee a usable set of fresh quiz questions.
        node_ids = [int(qid) for qid in node["levels"]]
        available = set(db.scalars(select(implementation.Question.id).where(
            implementation.Question.school_id == u.school_id, implementation.Question.grade == ctx["grade"],
            implementation.Question.id.in_(node_ids))).all()) if node_ids else set()
        layer["quiz"] = bool(layer["quiz"] and km.pick_node_quiz(node, available, set(ctx["first"])))
        return layer

    # The body is the raw picture (see ``read_image_body``): it is only ever held in memory. Waiting for
    # the recognition service (up to 20 s) happens in the worker thread pool, never on the event loop.
    @router.post("/student/homework/recognize")
    async def recognize(
        request: Request,
        u: Any = Depends(current_user),
        db: Any = Depends(get_db),
    ):
        need(u, "student")
        await run_in_threadpool(require_student_ai, implementation, db, u)
        data = await read_image_body(request)

        def work() -> dict[str, Any]:
            check_student_call(implementation, db, u)
            with ai_slot():
                return recognize_image(implementation, db, u, data, feature=VISION_FEATURE, timeout=20, prompt=QUESTION_PROMPT)

        return await run_in_threadpool(work)

    @router.post("/student/homework/help")
    def create_help(b: HelpBody, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "student")
        require_student_ai(implementation, db, u)
        text = (b.questionText or "").strip()
        if not text:
            raise HTTPException(400, "请先写下或拍下题目")
        if len(text) > MAX_QUESTION_CHARS:
            raise HTTPException(400, f"题目太长，请控制在 {MAX_QUESTION_CHARS} 字以内")
        grade = b.grade if b.grade is not None else u.grade
        if grade is None or not 1 <= int(grade) <= 6:
            raise HTTPException(400, "请选择年级（一到六年级）")
        item_idx = None
        if b.noticeID is not None:
            linked = db.execute(
                select(recipients.c.id, notices.c.items_json)
                .join(notices, notices.c.id == recipients.c.notice_id)
                .where(
                    recipients.c.notice_id == b.noticeID,
                    recipients.c.student_id == u.id,
                    recipients.c.school_id == u.school_id,
                    notices.c.status == "published",
                )
            ).first()
            if linked is None:
                raise HTTPException(404, "没有这份作业")
            if b.itemSeq is not None:
                try:
                    valid = {int(item.get("seq", 0)) for item in json.loads(linked.items_json or "[]")}
                except (TypeError, ValueError):
                    valid = set()
                if b.itemSeq not in valid:
                    raise HTTPException(400, "没有这条作业")
            item_idx = b.itemSeq
        check_new_help_request(db, helps, u)
        result = db.execute(
            insert(helps).values(
                school_id=u.school_id,
                student_id=u.id,
                grade=int(grade),
                notice_id=b.noticeID,
                item_idx=item_idx,
                question_text=text,
                ai_json="{}",
                verify_status="skipped",
                state="confirmed",
                student_note="",
                teacher_note="",
                escalate_reason="",
                created_at=datetime.utcnow(),
            )
        )
        db.commit()
        return student_help_json(own_help(db, u, int(result.inserted_primary_key[0])))

    @router.post("/student/homework/help/{help_id}/solve")
    def solve(help_id: int, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "student")
        require_student_ai(implementation, db, u)
        row = own_help(db, u, help_id)
        if row["state"] not in ("confirmed", "solving"):
            return student_help_json(row)  # already answered / escalated: never pay for a second answer
        # Claim the request atomically: a double tap or two devices can never trigger two paid answers.
        with _CLAIM_LOCK:
            started = _CLAIMS.get(help_id)
            if row["state"] == "solving" and (started is None or time.monotonic() - started > SOLVE_CLAIM_TTL_SECONDS):
                # A "solving" row nobody in this process is working on (restart, crash, hung call): hand it back.
                db.execute(update(helps).where(helps.c.id == help_id, helps.c.state == "solving").values(state="confirmed"))
                db.commit()
            claimed = db.execute(
                update(helps).where(helps.c.id == help_id, helps.c.state == "confirmed").values(state="solving")
            )
            db.commit()
            if claimed.rowcount != 1:
                raise HTTPException(409, "AI 正在解答这道题，请稍等几秒")
            _CLAIMS[help_id] = time.monotonic()

        def student_rate_check(_db: Any, _school_id: int) -> None:
            check_student_call(implementation, _db, u)

        ctx = optional(db, lambda: map_context(db, u, row["grade"]))
        known_map = map_lines(ctx["map"], ctx["mastery"]) if ctx else ""
        support = circle_support_record(_json_obj(row["ai_json"]).get("circleSupport"))
        learning_context = circle_prompt_context(row["question_text"], row["grade"], support)

        def attempt(recheck: bool) -> dict[str, Any]:
            prompt = build_solve_prompt(row["grade"], row["question_text"], recheck=recheck, known_map=known_map, learning_context=learning_context)
            with ai_slot():
                raw = implementation._ai_call(
                    db, u, SOLVE_FEATURE, prompt, timeout=SOLVE_TIMEOUT_SECONDS, rate_check=student_rate_check
                )
            try:
                return clean_solution(implementation._ai_json(raw))
            except HTTPException:
                return {}

        recorded: dict[str, str] = {}

        def compute() -> dict[str, Any]:
            first = attempt(False)
            if not first:
                raise HTTPException(502, "AI 这次没有给出可用的解答，请再试一次，或者点“求助老师”")
            attempts = [{"solution": first, "verify": check_solution(first["expression"], first["answer"])}]
            if attempts[0]["verify"]["status"] == MISMATCH:
                # One re-check; a failure of the re-check (limit, timeout, junk) counts as "still not sure".
                try:
                    second = attempt(True)
                except HTTPException:
                    second = {}
                if second:
                    attempts.append({"solution": second, "verify": check_solution(second["expression"], second["answer"])})
            final = attempts[-1]
            recorded["knowledge"] = str(final["solution"].get("knowledgePoint") or attempts[0]["solution"].get("knowledgePoint") or "")
            recorded["verify"] = str(final["verify"]["status"])
            now = datetime.utcnow()
            # A first answer that failed the check is only ever replaced by an answer that passes it.
            if final["verify"]["status"] == MISMATCH or (len(attempts) > 1 and final["verify"]["status"] != OK):
                values = {
                    "state": "escalated",
                    "verify_status": "mismatch",
                    "escalate_reason": "verify_mismatch",
                    "escalated_at": now,
                    "ai_json": json.dumps({"hidden": True, "attempts": attempts}, ensure_ascii=False),
                }
            else:
                data = dict(check_steps(final["solution"], final["verify"]["status"] == OK), verify=final["verify"], hidden=False)
                data["layer"] = optional(db, lambda: layer_of(db, u, ctx, data)) if ctx else None
                if len(attempts) > 1:
                    data["recheck"] = True
                values = {
                    "state": "answered",
                    "verify_status": final["verify"]["status"],
                    "ai_json": json.dumps(data, ensure_ascii=False),
                }
            if support:
                annotated = _json_obj(values["ai_json"])
                annotated["circleSupport"] = support
                values["ai_json"] = json.dumps(annotated, ensure_ascii=False)
            return values

        try:
            try:
                values = compute()
            finally:
                _CLAIMS.pop(help_id, None)
        except BaseException:
            # Nothing usable came back (model error, limit, junk): hand the request back so it can be retried.
            db.rollback()
            db.execute(update(helps).where(helps.c.id == help_id, helps.c.state == "solving").values(state="confirmed"))
            db.commit()
            raise
        # Only finish a request that is still ours: if the student asked the teacher meanwhile, that wins.
        result = db.execute(update(helps).where(helps.c.id == help_id, helps.c.state == "solving").values(**values))
        db.commit()
        if result.rowcount == 1:
            record_ai_help(
                implementation, db,
                school_id=int(u.school_id), student_id=int(u.id), help_id=int(help_id), grade=row["grade"],
                knowledge_point=recorded.get("knowledge", ""), question_text=row["question_text"],
                verify_status=recorded.get("verify", "skipped"),
            )
        return student_help_json(own_help(db, u, help_id))

    @router.get("/student/homework/help/{help_id}")
    def get_help(help_id: int, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "student")
        return student_help_json(own_help(db, u, help_id))

    @router.post("/student/homework/help/{help_id}/progress")
    def progress(help_id: int, b: ProgressBody, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        """How far the pupil got through the guide on his own; only the first time counts."""
        need(u, "student")
        row = own_help(db, u, help_id, lock=True)
        data = _json_obj(row["ai_json"])
        if not data.get("steps") or data.get("hidden"):
            raise HTTPException(409, "这道题还没有讲解")
        if not data.get("progress"):
            data["progress"] = {**b.model_dump(), "at": _iso(datetime.utcnow())}
            db.execute(update(helps).where(helps.c.id == help_id).values(ai_json=json.dumps(data, ensure_ascii=False)))
            db.commit()
        return {"progress": data["progress"]}

    @router.post("/student/homework/help/{help_id}/circle-support")
    def circle_support(help_id: int, b: CircleSupportBody, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        """Conversation annotation only: never writes a Submission or mastery evidence."""
        need(u, "student")
        row = own_help(db, u, help_id, lock=True)
        if not circle_area_question(row["question_text"], row["grade"]):
            raise HTTPException(409, "这条求助不属于本次圆面积辅导试点")
        if row["state"] not in ("confirmed", "answered", "escalated"):
            raise HTTPException(409, "求助状态已更新，请刷新后继续")
        data = _json_obj(row["ai_json"])
        data["circleSupport"] = circle_support_record(b.model_dump())
        db.execute(update(helps).where(helps.c.id == help_id).values(ai_json=json.dumps(data, ensure_ascii=False)))
        db.commit()
        return {"circleSupport": data["circleSupport"]}

    # ---------------------------------------------------------------- escalate (student)
    @router.post("/student/homework/help/{help_id}/escalate")
    def escalate(help_id: int, b: EscalateBody, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "student")
        row = own_help(db, u, help_id)
        if row["state"] in ("escalated", "resolved"):
            return student_help_json(row)
        db.execute(
            update(helps)
            .where(helps.c.id == help_id)
            .values(
                state="escalated",
                escalate_reason="student_request",
                student_note=(b.note or "").strip()[:300],
                escalated_at=datetime.utcnow(),
            )
        )
        db.commit()
        return student_help_json(own_help(db, u, help_id))

    # ---------------------------------------------------------------- teacher side
    def teacher_student_ids(db: Any, teacher: Any) -> set[int]:
        rows = db.scalars(
            select(ClassStudent.student_id)
            .join(SchoolClass, SchoolClass.id == ClassStudent.class_id)
            .where(SchoolClass.teacher_id == teacher.id, SchoolClass.school_id == teacher.school_id)
        ).all()
        return {int(x) for x in rows}

    def teacher_student_classes(db: Any, teacher: Any) -> dict[int, set[int]]:
        """每个学生属于这位老师的哪些班：班级维度的每日预算按这份关系扣。"""
        rows = db.execute(
            select(ClassStudent.student_id, ClassStudent.class_id)
            .join(SchoolClass, SchoolClass.id == ClassStudent.class_id)
            .where(SchoolClass.teacher_id == teacher.id, SchoolClass.school_id == teacher.school_id)
        ).all()
        out: dict[int, set[int]] = {}
        for student_id, class_id in rows:
            out.setdefault(int(student_id), set()).add(int(class_id))
        return out

    def _shown_by_class(class_members: dict[int, set[int]], shown_students: set[int]) -> dict[int, set[int]]:
        """当天已展示的学生按班归集；已处理/暂缓/已验证移出列表的学生仍然占名额。"""
        out: dict[int, set[int]] = {}
        for student_id in shown_students:
            for class_id in class_members.get(student_id, ()):
                out.setdefault(class_id, set()).add(student_id)
        return out

    def _annotate_verification(implementation: Any, db: Any, teacher: Any, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """按真实提交标注后续练习状态（school + student + subject + knowledge）；匹配不上或依赖异常单独标注。"""
        from changying.services.homework_knowledge import register_homework_knowledge_table
        from changying.services.homework_knowledge_flags import knowledge_flags, thresholds

        table = register_homework_knowledge_table(implementation)
        default_rule = thresholds()
        states: dict[int, dict[tuple[str, str], dict[str, Any]]] = {}
        rules: dict[int, dict[str, int]] = {}
        undecided: set[int] = set()
        for item in items:
            student_id = item.get("studentID")
            if student_id is None:
                item["verification"] = "无法判定"
                item["verificationDetail"] = {
                    "state": "undecided",
                    "label": "无法判定",
                    "subject": "",
                    "knowledge": "",
                    "submissionID": None,
                    "count": 0,
                    "hits": 0,
                    "total": 0,
                    "threshold": dict(default_rule),
                }
                continue
            if student_id not in states and student_id not in undecided:
                try:
                    result = knowledge_flags(implementation, db, teacher.school_id, student_id)
                except Exception:  # noqa: BLE001 - 这名学生的判定失败，只影响他本人
                    undecided.add(student_id)
                else:
                    if not isinstance(result, dict):
                        undecided.add(student_id)
                    else:
                        raw_flags = result.get("flags", [])
                        rule_obj = result.get("rule")
                        rules[student_id] = dict(rule_obj) if isinstance(rule_obj, dict) else dict(default_rule)
                        by_key: dict[tuple[str, str], dict[str, Any]] = {}
                        for f in raw_flags:
                            if not isinstance(f, dict):
                                continue
                            subj = str(f.get("subject") or "").strip()
                            know = str(f.get("knowledge") or "").strip()
                            if subj and know:
                                by_key[(subj, know)] = f
                        states[student_id] = by_key
            rule = rules.get(student_id, default_rule)
            if student_id in undecided:
                item["verification"] = "无法判定"
                item["verificationDetail"] = {
                    "state": "undecided",
                    "label": "无法判定",
                    "subject": "",
                    "knowledge": "",
                    "submissionID": None,
                    "count": 0,
                    "hits": 0,
                    "total": 0,
                    "threshold": dict(rule),
                }
                continue
            row = db.execute(
                select(table.c.subject, table.c.knowledge_key, table.c.matched).where(
                    table.c.school_id == teacher.school_id,
                    table.c.student_id == student_id,
                    table.c.help_id == item["helpID"],
                )
            ).first()
            subject = str(row.subject or "").strip() if row is not None else ""
            knowledge_key = str(row.knowledge_key or "").strip() if row is not None else ""
            if row is None or not row.matched or not subject or not knowledge_key:
                item["verification"] = "无法匹配知识点"
                item["verificationDetail"] = {
                    "state": "unmatched",
                    "label": "无法匹配知识点",
                    "subject": subject,
                    "knowledge": knowledge_key,
                    "submissionID": None,
                    "count": 0,
                    "hits": 0,
                    "total": 0,
                    "threshold": dict(rule),
                }
                continue
            flag = states[student_id].get((subject, knowledge_key))
            if flag is None:
                item["verification"] = "无法匹配知识点"
                item["verificationDetail"] = {
                    "state": "unmatched",
                    "label": "无法匹配知识点",
                    "subject": subject,
                    "knowledge": knowledge_key,
                    "submissionID": None,
                    "count": 0,
                    "hits": 0,
                    "total": 0,
                    "threshold": dict(rule),
                }
                continue
            label = str(flag.get("verification") or "")
            v_state = str(flag.get("verificationState") or "")
            hits = int(flag.get("hits") or 0)
            total = int(flag.get("total") or 0)
            sub_count = int(flag.get("submissionCount") or 0)
            sub_id = flag.get("submissionID")
            if not label:
                if flag.get("state") == "cleared":
                    label, v_state = "后续练习达到条件", "passed"
                elif total == 0:
                    label, v_state = "尚无后续作答", "no_submission"
                elif total < int(rule.get("minQuestions", 3)):
                    label, v_state = "题量不足待补充", "insufficient_questions"
                else:
                    label, v_state = "已有结果尚未达标", "below_threshold"
            item["verification"] = label
            item["verificationDetail"] = {
                "state": v_state,
                "label": label,
                "subject": subject,
                "knowledge": knowledge_key,
                "submissionID": int(sub_id) if isinstance(sub_id, int) else None,
                "count": sub_count,
                "hits": hits,
                "total": total,
                "threshold": dict(rule),
            }
        return items


    def purge_expired(db: Any, teacher: Any) -> None:
        """Lazy 90-day retention of the conversations: opening the list clears expired help requests of the school."""
        cutoff = datetime.utcnow() - timedelta(days=HELP_RETENTION_DAYS)
        ids = db.scalars(
            select(helps.c.id)
            .where(helps.c.school_id == teacher.school_id, helps.c.created_at < cutoff)
            .order_by(helps.c.id)
            .limit(PURGE_BATCH)
        ).all()
        if ids:
            db.execute(delete(helps).where(helps.c.id.in_(ids)))
            db.commit()

    def teacher_item(db: Any, teacher: Any, help_id: int) -> dict[str, Any]:
        row = db.execute(
            select(helps, User.name.label("student_name"))
            .join(User, User.id == helps.c.student_id)
            .where(helps.c.id == help_id, helps.c.school_id == teacher.school_id)
        ).first()
        data = _mapping(row)
        if not data or data["student_id"] not in teacher_student_ids(db, teacher):
            raise HTTPException(404, "没有这条求助")
        return data

    def summary(data: dict[str, Any]) -> dict[str, Any]:
        since = data["escalated_at"] or data["created_at"]
        waited = max(0, int((datetime.utcnow() - since).total_seconds() // 60)) if since else 0
        return {
            "id": data["id"],
            "studentID": data["student_id"],
            "studentName": data["student_name"],
            "grade": data["grade"],
            "questionText": data["question_text"],
            "state": data["state"],
            "reason": data["escalate_reason"],
            "reasonLabel": REASON_LABELS.get(data["escalate_reason"], "学生请求老师帮忙"),
            "studentNote": data["student_note"],
            "verifyStatus": data["verify_status"],
            "createdAt": _iso(data["created_at"]),
            "escalatedAt": _iso(data["escalated_at"]),
            "resolvedAt": _iso(data["resolved_at"]),
            "waitMinutes": waited,
        }

    def solution_text(solution: dict[str, Any]) -> str:
        steps = "\n".join(f"{x.get('n')}. " + (f"问：{x['ask']} 讲：" if x.get("ask") and x.get("kind") != "read" else "") + str(x.get("text"))
                          for x in solution.get("steps", []))
        head = f"解法：{solution.get('method')}\n" if solution.get("method") else ""
        if solution.get("start"):
            head += f"开头：{solution['start']}\n"
        return f"{head}{steps}\n答案：{solution.get('answer', '')}"

    def progress_text(p: dict[str, Any], assisted: bool = False) -> str:
        if p.get("selfSolved"):
            head = "借助圆面积图示辅导算出了答案" if assisted else "自己算出了答案"
        elif p.get("revealed") and p.get("finalChecked"):
            head = "没有算对，看了答案"
        elif p.get("revealed"):
            head = "写好后对了答案（这道题程序没法核对）"
        else:
            head = "没有做完引导"
        return f"（引导结果）{head}；回答了 {p.get('stepsAnswered', 0)} 个小问题，答错 {p.get('wrongTries', 0)} 次"

    def conversation(data: dict[str, Any]) -> list[dict[str, str]]:
        ai = _json_obj(data["ai_json"])
        talk = [{"role": "student", "text": data["question_text"]}]
        if ai.get("attempts"):
            for index, attempt in enumerate(ai["attempts"], start=1):
                verify = attempt.get("verify") or {}
                label = "（核对未通过：" + str(verify.get("detail", "")) + "）" if verify.get("status") == MISMATCH else ""
                talk.append({"role": "ai", "text": f"第{index}次解答{label}\n" + solution_text(attempt.get("solution") or {})})
        elif ai.get("steps"):
            verify = ai.get("verify") or {}
            note = {"ok": "（程序核对：通过）", "skipped": "（程序未能核对）"}.get(verify.get("status"), "")
            talk.append({"role": "ai", "text": solution_text(ai) + "\n" + note})
            if ai.get("progress"):
                talk.append({"role": "student", "text": progress_text(ai["progress"], bool(circle_support_record(ai.get("circleSupport"))))})
        support_summary = circle_support_summary(ai.get("circleSupport"))
        if support_summary:
            talk.append({"role": "student", "text": "（本次圆面积辅导，不计分）" + support_summary})
        if data["student_note"]:
            talk.append({"role": "student", "text": data["student_note"]})
        if data["teacher_note"]:
            talk.append({"role": "teacher", "text": data["teacher_note"]})
        return talk

    @router.get("/teacher/homework/help")
    def teacher_list(status: str = "open", u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "teacher")
        purge_expired(db, u)
        mine = teacher_student_ids(db, u)
        if not mine:
            return {"items": [], "open": 0}
        states = {"open": ("escalated",), "resolved": ("resolved",)}.get(status, ("escalated", "resolved"))
        rows = db.execute(
            select(helps, User.name.label("student_name"))
            .join(User, User.id == helps.c.student_id)
            .where(helps.c.school_id == u.school_id, helps.c.student_id.in_(mine), helps.c.state.in_(states))
            .order_by(helps.c.escalated_at.asc(), helps.c.id.asc())
            .limit(100)
        ).all()
        open_count = db.scalar(
            select(func.count()).select_from(helps).where(
                helps.c.school_id == u.school_id, helps.c.student_id.in_(mine), helps.c.state == "escalated"
            )
        )
        return {"items": [summary(_mapping(r)) for r in rows], "open": int(open_count or 0)}

    @router.get("/teacher/homework/follow-ups")
    def teacher_follow_ups(u: Any = Depends(current_user), db: Any = Depends(get_db)):
        """只读预览：按同样规则算一遍候选，但不记展示、不占当天名额。

        页面不再直接展示这里的结果；正式展示走 POST /claim，先确认名额再渲染。
        """
        need(u, "teacher")
        mine = teacher_student_ids(db, u)
        if not mine:
            return {"items": [], "note": "还没有可见学生"}
        items = _follow_up_candidates(db, u, mine)
        keep, state = _admit_follow_ups(db, u, items)
        return {
            "items": keep[:50],
            "shownToday": sorted(state["shown"]),
            "dismissedToday": sorted(state["dismissed"]),
            "snoozedToday": sorted(state["snoozed"]),
            "dailyLimit": FOLLOW_UP_DAILY_LIMIT,
            "note": "已展示过的今天继续可见；新的按每天每班 %d 条补入" % FOLLOW_UP_DAILY_LIMIT,
        }

    @router.post("/teacher/homework/follow-ups/claim")
    def follow_ups_claim(u: Any = Depends(current_user), db: Any = Depends(get_db)):
        """老师打开待跟进列表时调用：先原子确认当天名额，再把获准的建议交给页面展示。

        提交后名额即被占用（页面随后关闭或断网也不返还），所以这个口径叫"服务端已确认/预留的
        展示名额"，不等于老师实际看见。两台设备同时打开也只按同一份当天展示历史记账，
        页面只渲染这里返回的条目，所以"先展示、后记账"的超额展示不会再出现。
        """
        need(u, "teacher")
        mine = teacher_student_ids(db, u)
        if not mine:
            return {"items": [], "shownToday": [], "recorded": [], "dailyLimit": FOLLOW_UP_DAILY_LIMIT,
                    "note": "还没有可见学生"}
        # 先锁老师这一行，再读预算：两个设备同时来确认也会排队，后来者能看到前者刚记下的名额。
        db.execute(
            select(implementation.User.id)
            .where(implementation.User.id == u.id)
            .with_for_update()
        ).first()
        items = _follow_up_candidates(db, u, mine)
        keep, state = _admit_follow_ups(db, u, items)
        day = _local_day()
        recorded = []
        recorded_keys = []
        for item in keep:
            hid = item.get("helpID")
            ikey = _item_key(item)
            if ikey in state["shownKeys"]:
                continue
            payload: dict[str, Any] = {
                "itemKey": ikey,
                "studentID": item["studentID"],
                "teacherID": u.id,
                "day": day,
            }
            if hid is not None:
                payload["helpID"] = hid
            if item.get("peerHelpID") is not None:
                payload["peerHelpID"] = item["peerHelpID"]
            db.add(implementation.AuditLog(
                school_id=u.school_id, user_id=u.id, action="follow_up_shown",
                detail=json.dumps(payload, ensure_ascii=False)[:1000],
            ))
            state["shownKeys"].add(ikey)
            if hid is not None:
                state["shown"].add(hid)
                recorded.append(hid)
            recorded_keys.append(ikey)
        db.commit()
        return {
            "items": keep[:50],
            "shownToday": sorted(state["shown"]),
            "recorded": recorded,
            "recordedKeys": recorded_keys,
            "dailyLimit": FOLLOW_UP_DAILY_LIMIT,
            "note": "每个班每天最多 %d 条；返回的条目已占用当天的「已确认展示名额」，关闭页面也不返还" % FOLLOW_UP_DAILY_LIMIT,
        }

    def _follow_up_candidates(db: Any, teacher: Any, mine: set[int]) -> list[dict[str, Any]]:
        """列出可见学生的待跟进候选，并标注独立验证状态（不涉及名额）。"""
        rows = db.execute(
            select(helps, User.name.label("student_name"))
            .join(User, User.id == helps.c.student_id)
            .where(
                helps.c.school_id == teacher.school_id,
                helps.c.student_id.in_(mine),
                helps.c.state.in_(("escalated", "resolved")),
            )
            .order_by(helps.c.escalated_at.asc(), helps.c.id.asc())
            .limit(200)
        ).all()

        def _reason(row):
            if row["state"] == "resolved":
                return "已讲解，尚无独立巩固结果"
            if row["escalate_reason"] == "verify_mismatch":
                return "AI 解答验算未通过，已转给老师"
            return "学生主动求助"

        items = []
        for raw in rows:
            row = _mapping(raw)
            reason = _reason(row)
            items.append({
                "helpID": row["id"],
                "studentID": row["student_id"],
                "studentName": row["student_name"],
                "reason": reason,
                "evidence": {
                    "helpID": row["id"],
                    "state": row["state"],
                    "escalatedAt": _iso(row["escalated_at"]),
                    "resolvedAt": _iso(row["resolved_at"]),
                    "question": (row["question_text"] or "")[:80],
                },
                "next": {
                    "label": "查看求助并接着讲" if row["state"] == "escalated" else "查看并布置巩固",
                    "route": "/v1/homework",
                    # 带上定位参数：已讲解的还要带学生 ID，布置巩固时才能直接定位到这个学生。
                    "params": {"helpID": row["id"], "studentID": row["student_id"]},
                },
                # 排序权重：数字越小越靠前
                "rank": 0 if reason == "学生主动求助" else 1 if reason == "两轮补救后仍卡住" else 2,
            })
        items.sort(key=lambda x: (x["rank"], x["evidence"]["escalatedAt"] or "", x["helpID"]))

        # P1-A：求助要看后续有没有达到练习条件。匹配不上写"无法匹配知识点"，依赖异常写"无法判定"，
        # 绝不因为算不出来就把学生藏起来（漏报比误报代价大）。
        try:
            items = _annotate_verification(implementation, db, teacher, items)
        except Exception:  # noqa: BLE001 - 判定失败不能影响列表本身
            try:
                from changying.services.homework_knowledge_flags import thresholds as _thresholds
                fallback_rule = _thresholds()
            except Exception:  # noqa: BLE001 - 连阈值都读不到时给 default
                fallback_rule = {"minQuestions": 3, "passPercent": 80}
            for item in items:
                item["verification"] = "无法判定"
                item["verificationDetail"] = {
                    "state": "undecided",
                    "label": "无法判定",
                    "subject": "",
                    "knowledge": "",
                    "submissionID": None,
                    "count": 0,
                    "hits": 0,
                    "total": 0,
                    "threshold": dict(fallback_rule),
                }
        else:
            # 后续练习已达到条件的求助不再需要跟进，从当天列表移出（名额仍不返还）。
            items = [x for x in items if x.get("verification") != "后续练习达到条件"]

        # 合并周末课同桌讲题巩固未达标/未完成条目，共享每日每班 5 条、每生 1 条上限（晚托求助优先）。
        peer = implementation.Base.metadata.tables.get("weekend_peer_help")
        if peer is not None:
            peer_rows = db.execute(
                select(peer, User.name.label("student_name"))
                .join(User, User.id == peer.c.tutee_id)
                .where(
                    peer.c.school_id == teacher.school_id,
                    peer.c.tutee_id.in_(mine),
                    peer.c.followup_json != "",
                    (peer.c.followup_correct.is_(None)) | (peer.c.followup_correct == False),  # noqa: E712
                )
                .order_by(peer.c.created_at.asc(), peer.c.id.asc())
                .limit(100)
            ).all()
            for raw in peer_rows:
                row = _mapping(raw)
                stem = ""
                try:
                    stem = str(json.loads(row.get("followup_json") or "{}").get("stem") or "")
                except ValueError:
                    stem = ""
                wrong = row.get("followup_correct") is False
                items.append({
                    "source": "weekend",
                    "itemKey": f"weekend:{row['id']}",
                    "peerHelpID": row["id"],
                    "helpID": None,
                    "studentID": row["tutee_id"],
                    "studentName": row["student_name"],
                    "reason": "周末课巩固题未做对" if wrong else "周末课巩固题待完成",
                    "verification": "待周末课巩固",
                    "evidence": {
                        "peerHelpID": row["id"],
                        "state": "followup_wrong" if wrong else "followup_open",
                        "escalatedAt": _iso(row["created_at"]),
                        "resolvedAt": "",
                        "question": stem[:80],
                    },
                    "next": {
                        "label": "去周末课查看",
                        "route": "/v1/weekend",
                        "params": {"studentID": row["tutee_id"]},
                    },
                    "rank": 3 if wrong else 4,
                })
            items.sort(key=lambda x: (x["rank"], x["evidence"]["escalatedAt"] or "", _item_key(x)))
        return items

    def _admit_follow_ups(db: Any, teacher: Any, items: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """按当天展示历史和每班名额挑出这一次能展示的建议（不写库）。"""
        # 每天每班最多 5 条：已展示过的继续显示，新的只补到预算内。
        # 预算按当天完整展示历史扣（每班各自 5 条），已处理、暂缓或已验证移出列表都不返还名额。
        state = follow_up_state(db, teacher)
        shown_keys = state["shownKeys"]
        blocked_students = state["dismissedStudents"] | state["snoozedStudents"]
        eligible = []
        for item in items:
            ikey = _item_key(item)
            sid = item["studentID"]
            if ikey in state["dismissedKeys"] or ikey in state["snoozedKeys"]:
                continue
            if sid in blocked_students:
                continue  # 该学生今天已处理/暂缓过，当天不再推它的其它求助
            eligible.append(item)

        class_members = teacher_student_classes(db, teacher)
        shown_students = state["shownStudents"]
        shown_by_class = _shown_by_class(class_members, shown_students)
        keep: list[dict[str, Any]] = []
        kept_students: set[int] = set()
        # 今天已经展示过的先放回；同一学生只保留一条，并占用当天的名额
        for item in eligible:
            if _item_key(item) not in shown_keys:
                continue
            student_id = item["studentID"]
            if student_id in kept_students:
                continue
            kept_students.add(student_id)
            keep.append(item)
        for item in eligible:
            if _item_key(item) in shown_keys:
                continue
            student_id = item["studentID"]
            if student_id is None or student_id in kept_students or student_id in shown_students:
                continue  # 同一学生当天最多 1 条
            classes = class_members.get(student_id, set())
            if not classes:
                continue
            if any(len(shown_by_class.get(class_id, ())) >= FOLLOW_UP_DAILY_LIMIT for class_id in classes):
                continue  # 所在班当天的 5 条已经用完
            for class_id in classes:
                shown_by_class.setdefault(class_id, set()).add(student_id)
            kept_students.add(student_id)
            keep.append(item)
        return keep, state

    @router.get("/teacher/homework/follow-ups/stats")
    def follow_ups_stats(days: int = 10, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        """试点的耗时基线：从"建议首次出现"到"老师处理/暂缓"用了多久。

        只统计本人，按天聚合；不记录、不返回学生姓名。
        """
        need(u, "teacher")
        from app_v924 import AuditLog

        window = max(1, min(int(days), 60))
        since = datetime.utcnow() - timedelta(days=window)
        rows = db.execute(
            select(AuditLog.action, AuditLog.detail, AuditLog.created_at).where(
                AuditLog.school_id == u.school_id,
                AuditLog.user_id == u.id,
                AuditLog.action.in_(("follow_up_shown", "follow_up_dismissed", "follow_up_snoozed")),
                AuditLog.created_at >= since,
            ).order_by(AuditLog.created_at.asc())
        ).all()

        shown_at: dict[int, datetime] = {}
        per_day: dict[str, dict[str, Any]] = {}

        def bucket(day: str) -> dict[str, Any]:
            return per_day.setdefault(day, {"day": day, "shown": 0, "handled": 0,
                                            "minutes": []})

        for action, detail, created in rows:
            try:
                data = json.loads(detail or "{}")
            except ValueError:
                continue
            hid = data.get("helpID")
            day = data.get("day") or (created + timedelta(hours=8)).strftime("%Y-%m-%d")
            if not isinstance(hid, int):
                continue
            if action == "follow_up_shown":
                bucket(day)["shown"] += 1
                shown_at.setdefault(hid, created)
            else:
                slot = bucket(day)
                slot["handled"] += 1
                first = shown_at.get(hid)
                if first is not None and created >= first:
                    slot["minutes"].append(int((created - first).total_seconds() // 60))

        out = []
        for day in sorted(per_day):
            slot = per_day[day]
            minutes = sorted(slot["minutes"])
            out.append({
                "day": day,
                "shown": slot["shown"],
                "handled": slot["handled"],
                "handledWithTiming": len(minutes),
                "medianMinutes": minutes[len(minutes) // 2] if minutes else None,
                "maxMinutes": minutes[-1] if minutes else None,
            })
        all_minutes = sorted(m for slot in per_day.values() for m in slot["minutes"])
        return {
            "days": window,
            "perDay": out,
            "overall": {
                "handledWithTiming": len(all_minutes),
                "medianMinutes": all_minutes[len(all_minutes) // 2] if all_minutes else None,
            },
            "note": "只统计本人在本页处理过的建议；直接去求助列表处理的不会计入",
        }

    @router.post("/teacher/homework/follow-ups/shown")
    def follow_ups_shown(b: FollowUpShownBody, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        """老师确实看到这些建议时调用；同一学生同一天只计一次预算。"""
        need(u, "teacher")
        mine = teacher_student_ids(db, u)
        ids = [int(x) for x in (b.helpIDs or [])]
        # 先锁老师这一行，再读预算：两台设备同时确认也不会超过每天上限。
        # （与积分兑换用的是同一把锁；SQLite 忽略 FOR UPDATE，PostgreSQL 生效。）
        db.execute(
            select(implementation.User.id)
            .where(implementation.User.id == u.id)
            .with_for_update()
        ).first()
        state = follow_up_state(db, u)
        class_members = teacher_student_classes(db, u)
        counted_students = set(state["shownStudents"])
        shown_by_class = _shown_by_class(class_members, counted_students)
        recorded = []
        for hid in ids:
            if hid in state["shown"]:
                continue
            owned = db.execute(
                select(helps.c.id, helps.c.student_id).where(
                    helps.c.id == hid, helps.c.school_id == u.school_id,
                    helps.c.student_id.in_(mine) if mine else False,
                )
            ).first()
            if owned is None:
                continue
            student_id = int(owned.student_id)
            if student_id in counted_students:
                continue  # 同一学生当天只记 1 条，和列表的展示规则一致
            classes = class_members.get(student_id, set())
            if not classes:
                continue
            if any(len(shown_by_class.get(class_id, ())) >= FOLLOW_UP_DAILY_LIMIT for class_id in classes):
                continue  # 该学生所在班的每日名额已经用完
            db.add(implementation.AuditLog(
                school_id=u.school_id, user_id=u.id, action="follow_up_shown",
                detail=json.dumps({"helpID": hid, "studentID": owned.student_id,
                                   "teacherID": u.id, "day": _local_day()}, ensure_ascii=False)[:1000],
            ))
            state["shown"].add(hid)
            counted_students.add(student_id)
            for class_id in classes:
                shown_by_class.setdefault(class_id, set()).add(student_id)
            recorded.append(hid)
        db.commit()
        return {"recorded": recorded, "shownToday": sorted(state["shown"]),
                "dailyLimit": FOLLOW_UP_DAILY_LIMIT}

    @router.post("/teacher/homework/follow-ups/{help_id}/{action}")
    def follow_ups_mark(help_id: int, action: str, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        """dismiss=建议已处理（不改求助结论）；snooze=当天暂缓。"""
        need(u, "teacher")
        if action not in ("dismiss", "snooze"):
            raise HTTPException(404, "没有这个操作")
        mine = teacher_student_ids(db, u)
        owned = db.execute(
            select(helps.c.id, helps.c.student_id).where(
                helps.c.id == help_id, helps.c.school_id == u.school_id,
                helps.c.student_id.in_(mine) if mine else False,
            )
        ).first()
        if owned is None:
            raise HTTPException(404, "没有这条求助")
        db.add(implementation.AuditLog(
            school_id=u.school_id, user_id=u.id,
            action="follow_up_" + ("dismissed" if action == "dismiss" else "snoozed"),
            detail=json.dumps({"helpID": help_id, "studentID": owned.student_id,
                               "teacherID": u.id, "day": _local_day()}, ensure_ascii=False)[:1000],
        ))
        db.commit()
        # 明确：只关闭/暂缓这条建议，求助本身的状态没有改变。
        return {"helpID": help_id, "action": action, "helpStateUnchanged": True}

    @router.post("/teacher/homework/follow-ups/weekend/{peer_id}/{action}")
    def follow_ups_mark_weekend(peer_id: int, action: str, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        """dismiss=周末课巩固建议已收起；snooze=当天暂缓。"""
        need(u, "teacher")
        if action not in ("dismiss", "snooze"):
            raise HTTPException(404, "没有这个操作")
        peer = implementation.Base.metadata.tables.get("weekend_peer_help")
        if peer is None:
            raise HTTPException(404, "没有这条跟进建议")
        mine = teacher_student_ids(db, u)
        owned = db.execute(
            select(peer.c.id, peer.c.tutee_id).where(
                peer.c.id == peer_id, peer.c.school_id == u.school_id,
                peer.c.tutee_id.in_(mine) if mine else False,
            )
        ).first()
        if owned is None:
            raise HTTPException(404, "没有这条跟进建议")
        db.add(implementation.AuditLog(
            school_id=u.school_id, user_id=u.id,
            action="follow_up_" + ("dismissed" if action == "dismiss" else "snoozed"),
            detail=json.dumps({"itemKey": f"weekend:{peer_id}", "peerHelpID": peer_id,
                               "studentID": owned.tutee_id, "teacherID": u.id, "day": _local_day()},
                              ensure_ascii=False)[:1000],
        ))
        db.commit()
        return {"peerHelpID": peer_id, "action": action, "helpStateUnchanged": True}

    @router.get("/teacher/homework/help/{help_id}")
    def teacher_detail(help_id: int, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "teacher")
        data = teacher_item(db, u, help_id)
        out = summary(data)
        out["conversation"] = conversation(data)
        out["teacherNote"] = data["teacher_note"]
        return out

    @router.post("/teacher/homework/help/{help_id}/resolve")
    def teacher_resolve(help_id: int, b: ResolveBody, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "teacher")
        data = teacher_item(db, u, help_id)
        if data["state"] != "escalated":
            raise HTTPException(409, "这条求助现在不需要处理")
        result = db.execute(
            update(helps)
            .where(helps.c.id == help_id, helps.c.state == "escalated")
            .values(state="resolved", teacher_note=(b.note or "").strip()[:500], resolved_at=datetime.utcnow())
        )
        if result.rowcount != 1:
            db.rollback()
            raise HTTPException(409, "这条求助现在不需要处理")
        implementation.audit(db, u, "homework.help.resolve", f"help={help_id}")
        db.commit()
        return summary(teacher_item(db, u, help_id))

    app.include_router(router)
    app.state.homework_help_installed = True
    app.state.homework_help_router = router
    return router


__all__ = ["install_homework_help"]
