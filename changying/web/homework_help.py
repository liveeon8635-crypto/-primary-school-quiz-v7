"""Student help flow of the after-school homework assistant (behind the same ``HOMEWORK_ASSISTANT`` flag).

Photo -> recognised text -> the student confirms or edits the text -> a ``help_requests`` row.
The photo only ever exists in memory while it is recognised; nothing in this module stores it.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import insert, select, update

from changying.services.homework_limits import (
    ai_slot,
    check_new_help_request,
    check_student_call,
    require_student_ai,
)
from changying.services.homework_math_check import MISMATCH, check_solution
from changying.services.homework_prompts import AI_WARNING, build_solve_prompt, clean_solution
from changying.services.homework_vision import MAX_IMAGE_BYTES, recognize_image
from changying.web.homework_assistant import require_enabled

MAX_QUESTION_CHARS = 600
VISION_FEATURE = "homework_help_vision"
SOLVE_FEATURE = "homework_help_solve"
SOLVE_TIMEOUT_SECONDS = 30
NO_CONFIDENCE = "这道题我没有把握，已请老师帮忙。"


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

    def own_help(db: Any, user: Any, help_id: int) -> dict[str, Any]:
        row = db.execute(
            select(helps).where(
                helps.c.id == help_id, helps.c.student_id == user.id, helps.c.school_id == user.school_id
            )
        ).first()
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
                "steps": data["steps"],
                "answer": data.get("answer", ""),
                "knowledgePoint": data.get("knowledgePoint", ""),
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
        }

    @router.post("/student/homework/recognize")
    async def recognize(
        file: UploadFile = File(...),
        u: Any = Depends(current_user),
        db: Any = Depends(get_db),
    ):
        need(u, "student")
        require_student_ai(implementation, db, u)
        data = await file.read(MAX_IMAGE_BYTES + 1)
        if len(data) > MAX_IMAGE_BYTES:
            raise HTTPException(413, "图片太大，请重新拍一张")
        check_student_call(implementation, db, u)
        with ai_slot():
            result = recognize_image(implementation, db, u, data, feature=VISION_FEATURE, timeout=20)
        del data
        return result

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
                select(recipients.c.id)
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
        if row["state"] != "confirmed":
            return student_help_json(row)  # already answered / escalated: never pay for a second answer

        def student_rate_check(_db: Any, _school_id: int) -> None:
            check_student_call(implementation, _db, u)

        def attempt(recheck: bool) -> dict[str, Any]:
            prompt = build_solve_prompt(row["grade"], row["question_text"], recheck=recheck)
            with ai_slot():
                raw = implementation._ai_call(
                    db, u, SOLVE_FEATURE, prompt, timeout=SOLVE_TIMEOUT_SECONDS, rate_check=student_rate_check
                )
            try:
                return clean_solution(implementation._ai_json(raw))
            except HTTPException:
                return {}

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
        now = datetime.utcnow()
        if final["verify"]["status"] == MISMATCH:
            values = {
                "state": "escalated",
                "verify_status": "mismatch",
                "escalate_reason": "verify_mismatch",
                "escalated_at": now,
                "ai_json": json.dumps({"hidden": True, "attempts": attempts}, ensure_ascii=False),
            }
        else:
            data = dict(final["solution"], verify=final["verify"], hidden=False)
            if len(attempts) > 1:
                data["recheck"] = True
            values = {
                "state": "answered",
                "verify_status": final["verify"]["status"],
                "ai_json": json.dumps(data, ensure_ascii=False),
            }
        db.execute(update(helps).where(helps.c.id == help_id).values(**values))
        db.commit()
        return student_help_json(own_help(db, u, help_id))

    @router.get("/student/homework/help/{help_id}")
    def get_help(help_id: int, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "student")
        return student_help_json(own_help(db, u, help_id))

    app.include_router(router)
    app.state.homework_help_installed = True
    app.state.homework_help_router = router
    return router


__all__ = ["install_homework_help"]
