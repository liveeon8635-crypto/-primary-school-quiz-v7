"""Stage 6 (课堂互动) per-question mastery check and student doubt/question feedback.

teacher  GET  /teacher/weekend/sessions/{sid}/stage6-checks   list questions still needing mastery confirmation + student doubts
         POST /teacher/weekend/sessions/{sid}/stage6-checks   mark question mastered or leave for after-class homework
student  GET  /student/weekend/sessions/{sid}/stage6-checks   list stage-6 questions (with figures) for current student
         POST /student/weekend/sessions/{sid}/stage6-checks   mark understood or raise doubt/question for after-class practice
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import Column, DateTime, Integer, String, Table, Text, UniqueConstraint, insert, select, update

from changying.services.weekend_answers import practice_items, practice_question_figures
from changying.services.weekend_roster import current_student_session, session_roster, student_in_session


class TeacherStage6CheckBody(BaseModel):
    questionKey: str
    status: str  # "mastered" | "homework" | "pending"


class StudentStage6CheckBody(BaseModel):
    questionKey: str
    status: str  # "understood" | "doubt"
    note: str = ""


def register_stage6_table(implementation: Any) -> Table:
    md = implementation.Base.metadata
    tbl = md.tables.get("weekend_stage6_checks")
    if tbl is None:
        tbl = Table(
            "weekend_stage6_checks",
            md,
            Column("id", Integer, primary_key=True),
            Column("school_id", Integer, nullable=False, index=True),
            Column("session_id", Integer, nullable=False, index=True),
            Column("question_key", String(40), nullable=False),
            Column("student_id", Integer, nullable=False, default=0),  # 0 = teacher class decision; >0 = student feedback
            Column("status", String(20), nullable=False, default="pending"),
            Column("note", Text, nullable=False, default=""),
            Column("updated_at", DateTime, nullable=False, default=datetime.utcnow),
            UniqueConstraint("session_id", "question_key", "student_id", name="uq_weekend_stage6_check"),
        )
    return tbl


def stage6_check_map(implementation: Any, db: Any, session_id: int) -> dict[str, Any]:
    """Return teacher decisions and student feedback for a session's stage 6 checks."""
    tbl = register_stage6_table(implementation)
    try:
        rows = db.execute(select(tbl).where(tbl.c.session_id == int(session_id))).all()
    except Exception:  # noqa: BLE001 - safe fallback on legacy test DBs before table creation
        return {"teacher": {}, "student": {}}
    teacher: dict[str, str] = {}
    student: dict[tuple[str, int], dict[str, str]] = {}
    for r in rows:
        qkey = str(r.question_key)
        if int(r.student_id) == 0:
            teacher[qkey] = str(r.status)
        else:
            student[(qkey, int(r.student_id))] = {"status": str(r.status), "note": str(r.note or "")}
    return {"teacher": teacher, "student": student}


def stage6_unresolved_items(implementation: Any, db: Any, row: Any) -> list[dict[str, Any]]:
    """Collect questions that still have unresolved wrong/revise/partial answers after Stage 4 & 5."""
    from changying.web.weekend_practice import register_practice_tables
    from changying.web.weekend_written import register_written_tables

    roster_rows = session_roster(implementation, db, row)
    names = {int(sid): str(info[0]) for sid, info in roster_rows.items()}
    all_items = practice_items(implementation, db, row)
    ans_t = register_practice_tables(implementation)["answers"]
    wt_subs = register_written_tables(implementation)["submissions"]

    wrong_choice: dict[int, list[int]] = {}
    for a in db.execute(select(ans_t).where(ans_t.c.session_id == int(row.id), ans_t.c.correct.is_(False))).all():
        sid_int = int(a.student_id)
        if sid_int in names:
            wrong_choice.setdefault(int(a.question_id), []).append(sid_int)

    wrong_written: dict[int, list[int]] = {}
    for a in db.execute(select(wt_subs).where(wt_subs.c.session_id == int(row.id), wt_subs.c.result.in_(("revise", "partial")))).all():
        sid_int = int(a.student_id)
        if sid_int in names:
            wrong_written.setdefault(int(a.question_id), []).append(sid_int)

    checks = stage6_check_map(implementation, db, int(row.id))
    teacher_map = checks["teacher"]
    student_map = checks["student"]

    out: list[dict[str, Any]] = []
    for no, it in enumerate(all_items, 1):
        kind = str(it["kind"])
        qid = int(it["id"])
        qkey = f"{kind}:{qid}"
        wrong_sids = wrong_choice.get(qid, []) if kind == "choice" else wrong_written.get(qid, [])
        # Also keep questions that already have a stage-6 check or student doubt.
        has_feedback = any(k[0] == qkey for k in student_map) or (qkey in teacher_map)
        if not wrong_sids and not has_feedback:
            continue
        feedback_list = []
        for (fk, stu_id), fb in student_map.items():
            if fk == qkey and stu_id in names:
                feedback_list.append({
                    "studentId": stu_id,
                    "name": names[stu_id],
                    "status": fb["status"],
                    "note": fb["note"],
                })
        out.append({
            "no": no,
            "questionKey": qkey,
            "questionType": kind,
            "questionId": qid,
            "stem": str(it.get("bindingStem") or it.get("question") or "").strip(),
            "wrongStudentIds": wrong_sids,
            "wrongStudents": [names[s] for s in wrong_sids],
            "wrongCount": len(wrong_sids),
            "isCommonError": len(wrong_sids) >= 2,
            "teacherStatus": teacher_map.get(qkey, "pending"),
            "studentFeedback": feedback_list,
            "_rawItem": it,
        })
    out.sort(key=lambda item: (-int(item["wrongCount"]), int(item["no"])))
    return out


def install_weekend_stage6(implementation: Any) -> APIRouter:
    app = implementation.app
    if getattr(app.state, "weekend_stage6_installed", False):
        return app.state.weekend_stage6_router
    from changying.web.weekend_views import register_weekend_tables

    sessions = register_weekend_tables(implementation)["sessions"]
    tbl = register_stage6_table(implementation)
    current_user, get_db, need = implementation.current_user, implementation.get_db, implementation.need
    router = APIRouter()

    def _teacher_session(db: Any, u: Any, sid: int) -> Any:
        row = db.execute(select(sessions).where(
            sessions.c.id == sid, sessions.c.school_id == u.school_id, sessions.c.teacher_id == u.id
        )).first()
        if row is None:
            raise HTTPException(404, "没有找到这节课堂")
        return row

    def _upsert(db: Any, school_id: int, sid: int, qkey: str, student_id: int, status: str, note: str) -> None:
        now = datetime.utcnow()
        existing = db.execute(select(tbl.c.id).where(
            tbl.c.session_id == sid, tbl.c.question_key == qkey, tbl.c.student_id == student_id
        )).first()
        if existing is not None:
            db.execute(update(tbl).where(tbl.c.id == existing.id).values(status=status, note=note, updated_at=now))
        else:
            db.execute(insert(tbl).values(
                school_id=school_id, session_id=sid, question_key=qkey,
                student_id=student_id, status=status, note=note, updated_at=now,
            ))
        db.commit()

    def _pending_review_count(db: Any, row: Any) -> int:
        from sqlalchemy import func
        from changying.web.weekend_written import register_written_tables
        written_s = register_written_tables(implementation)["submissions"]
        return int(db.execute(
            select(func.count()).select_from(written_s).where(
                written_s.c.session_id == int(row.id),
                written_s.c.school_id == int(row.school_id),
                written_s.c.result == "pending",
            )
        ).scalar() or 0)

    def _summary(db: Any, row: Any, items: list[dict[str, Any]]) -> dict[str, Any]:
        public_items = [{k: v for k, v in it.items() if k != "_rawItem"} for it in items]
        return {
            "total": len(public_items),
            "mastered": sum(1 for it in public_items if it["teacherStatus"] == "mastered"),
            "homework": sum(1 for it in public_items if it["teacherStatus"] == "homework"),
            "pending": sum(1 for it in public_items if it["teacherStatus"] not in ("mastered", "homework")),
            "doubtCount": sum(1 for it in public_items for fb in it["studentFeedback"] if fb["status"] == "doubt"),
            "pendingReview": _pending_review_count(db, row),
            "items": public_items,
        }

    @router.get("/teacher/weekend/sessions/{sid}/stage6-checks")
    def teacher_list(sid: int, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "teacher")
        row = _teacher_session(db, u, sid)
        return _summary(db, row, stage6_unresolved_items(implementation, db, row))

    @router.post("/teacher/weekend/sessions/{sid}/stage6-checks")
    def teacher_mark(sid: int, b: TeacherStage6CheckBody, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "teacher")
        if b.status not in ("mastered", "homework", "pending"):
            raise HTTPException(400, "请选择有效的达标状态")
        row = _teacher_session(db, u, sid)
        valid_keys = {f"{it['kind']}:{int(it['id'])}" for it in practice_items(implementation, db, row)}
        if b.questionKey not in valid_keys:
            raise HTTPException(404, "没有找到这道题")
        _upsert(db, int(u.school_id), int(sid), b.questionKey, 0, b.status, "")
        return _summary(db, row, stage6_unresolved_items(implementation, db, row))

    @router.get("/student/weekend/sessions/{sid}/stage6-checks")
    def student_list(sid: int, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "student")
        row = current_student_session(implementation, db, u)
        if row is None or int(row.id) != int(sid) or not student_in_session(implementation, db, row, u.id):
            raise HTTPException(404, "现在没有正在上的课")
        items = stage6_unresolved_items(implementation, db, row)
        mine = [it for it in items if int(u.id) in it["wrongStudentIds"] or any(fb["studentId"] == int(u.id) for fb in it["studentFeedback"])]
        if not mine:
            mine = items
        fig_map = practice_question_figures(implementation, db, row, [it["_rawItem"] for it in mine])
        checks = stage6_check_map(implementation, db, int(row.id))["student"]
        out = []
        for it in mine:
            fb = checks.get((it["questionKey"], int(u.id)), {})
            out.append({
                "no": it["no"],
                "questionKey": it["questionKey"],
                "questionType": it["questionType"],
                "questionId": it["questionId"],
                "stem": it["stem"],
                "figure": fig_map.get((it["questionType"], int(it["questionId"])), {}),
                "teacherStatus": it["teacherStatus"],
                "myStatus": fb.get("status", ""),
                "myNote": fb.get("note", ""),
            })
        return {"sessionId": int(row.id), "stage": int(row.current_stage), "items": out}

    @router.post("/student/weekend/sessions/{sid}/stage6-checks")
    def student_mark(sid: int, b: StudentStage6CheckBody, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "student")
        if b.status not in ("understood", "doubt"):
            raise HTTPException(400, "请选择“已听懂”或“还有疑问”")
        row = current_student_session(implementation, db, u)
        if row is None or int(row.id) != int(sid) or not student_in_session(implementation, db, row, u.id):
            raise HTTPException(404, "现在没有正在上的课")
        valid_keys = {f"{it['kind']}:{int(it['id'])}" for it in practice_items(implementation, db, row)}
        if b.questionKey not in valid_keys:
            raise HTTPException(404, "没有找到这道题")
        note = b.note.strip()[:300]
        _upsert(db, int(u.school_id), int(sid), b.questionKey, int(u.id), b.status, note)
        return {"ok": True, "questionKey": b.questionKey, "status": b.status, "note": note}

    app.include_router(router)
    app.state.weekend_stage6_installed = True
    app.state.weekend_stage6_router = router
    return router
