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
from changying.services import circle_ladder
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
            # 地图已发布且定位到节点时，按掌握度决定从第几级开始；没地图就从第 1 级起
            "circleNodeKey": (((data.get("layer") or {}).get("node") or {}).get("key") or ""),
            "circleStartRank": circle_ladder.start_rank(
                ((data.get("layer") or {}).get("node") or {}).get("state")),
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
        db.execute(update(helps).where(helps.c.id == help_id, helps.c.state == "solving").values(**values))
        db.commit()
        # The AI really helped with this knowledge point: keep that fact permanently (the conversation expires).
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
        db.execute(
            update(helps)
            .where(helps.c.id == help_id)
            .values(state="resolved", teacher_note=(b.note or "").strip()[:500], resolved_at=datetime.utcnow())
        )
        implementation.audit(db, u, "homework.help.resolve", f"help={help_id}")
        db.commit()
        return summary(teacher_item(db, u, help_id))

    app.include_router(router)
    app.state.homework_help_installed = True
    app.state.homework_help_router = router
    return router


__all__ = ["install_homework_help"]
