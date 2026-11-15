"""周末课 随堂练习 + 阶梯提示 (阶段 3b).

teacher  GET  /teacher/weekend/sessions/{id}/questions    the lesson's questions + hint status
         POST /teacher/weekend/hints/generate             {questionId} AI drafts the 3 hint levels (draft)
         PUT  /teacher/weekend/hints/{questionId}         {levels:[3 texts], approve} edit / approve
         GET  /teacher/weekend/sessions/{id}/progress     per student: answered, correct, completion rate, hint use
student  GET  /student/weekend/current                    the running class of the student's teacher (questions only in 随堂练习)
         POST /student/weekend/hint                       {sessionId, questionId} next hint level (1 -> 3)
         POST /student/weekend/answer                     {sessionId, questionId, selected} at most three saved submissions per question
page     /v1/weekend-practice

Hint levels (数学) 1 方向 · 2 第一步 · 3 完整讲解; (语文) 1 找关键句 · 2 概括段意 · 3 完整思路.
Levels 1–2 never state the answer. Teacher-approved hints are used; when a question has none the AI writes them
on the spot and they are stored as "auto" (visible to students, flagged for teacher review).
"""

from __future__ import annotations

from changying.services.weekend_answers import answers_published, practice_release
from changying.services.lesson_written import numbered_student_stem
from changying.services.weekend_submissions import submission_attempts, record_submission, require_unsettled

import json
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy import Boolean, Column, DateTime, Integer, String, Table, Text, UniqueConstraint, func, insert, select, update

from changying.web.weekend_pages import practice_page_html

HINT_FEATURE = "weekend_hint"
LEVEL_NAMES = {
    "语文": ("找关键句", "概括段意", "完整思路"),
    "default": ("思考方向", "第一步", "完整讲解"),
}
PRACTICE_STAGE = 4
NO_CACHE = {"Cache-Control": "no-store"}


class GenBody(BaseModel):
    questionId: int


class HintBody(BaseModel):
    levels: list[str]
    approve: bool = False


class StudentHintBody(BaseModel):
    sessionId: int
    questionId: int


class AnswerBody(BaseModel):
    sessionId: int
    questionId: int
    selected: int
    attempt: int = 0


def register_practice_tables(implementation: Any) -> dict[str, Table]:
    md = implementation.Base.metadata
    hints = md.tables.get("weekend_hints")
    if hints is None:
        hints = Table(
            "weekend_hints", md,
            Column("id", Integer, primary_key=True),
            Column("school_id", Integer, nullable=False, index=True),
            Column("question_id", Integer, nullable=False, index=True),
            Column("level", Integer, nullable=False),
            Column("text", Text, nullable=False, default=""),
            Column("status", String(12), nullable=False, default="draft"),  # draft | approved | auto
            Column("updated_at", DateTime, nullable=False, default=datetime.utcnow),
            UniqueConstraint("school_id", "question_id", "level", name="uq_weekend_hint_level"),
        )
    log = md.tables.get("weekend_hint_log")
    if log is None:
        log = Table(
            "weekend_hint_log", md,
            Column("id", Integer, primary_key=True),
            Column("school_id", Integer, nullable=False, index=True),
            Column("session_id", Integer, nullable=False, index=True),
            Column("student_id", Integer, nullable=False, index=True),
            Column("question_id", Integer, nullable=False, index=True),
            Column("level", Integer, nullable=False),
            Column("created_at", DateTime, nullable=False, default=datetime.utcnow),
        )
    answers = md.tables.get("weekend_answers")
    if answers is None:
        answers = Table(
            "weekend_answers", md,
            Column("id", Integer, primary_key=True),
            Column("school_id", Integer, nullable=False, index=True),
            Column("session_id", Integer, nullable=False, index=True),
            Column("student_id", Integer, nullable=False, index=True),
            Column("question_id", Integer, nullable=False, index=True),
            Column("selected", Integer, nullable=False),
            Column("correct", Boolean, nullable=False, default=False),
            Column("max_hint", Integer, nullable=False, default=0),
            Column("created_at", DateTime, nullable=False, default=datetime.utcnow),
            UniqueConstraint("session_id", "student_id", "question_id", name="uq_weekend_answer_once"),
        )
    return {"hints": hints, "log": log, "answers": answers}


def install_weekend_practice(implementation: Any) -> APIRouter:
    app = implementation.app
    if getattr(app.state, "weekend_practice_installed", False):
        return app.state.weekend_practice_router
    from changying.web.weekend_views import register_weekend_tables

    wt = register_weekend_tables(implementation)
    sessions = wt["sessions"]
    pt = register_practice_tables(implementation)
    hints, hlog, answers = pt["hints"], pt["log"], pt["answers"]
    TQ, Lesson = implementation.TeachingQuestion, implementation.TeachingLesson
    User, ClassStudent, SchoolClass = implementation.User, implementation.ClassStudent, implementation.SchoolClass
    current_user, get_db, need = implementation.current_user, implementation.get_db, implementation.need
    router = APIRouter()

    def my_session(db: Any, u: Any, sid: int) -> Any:
        row = db.execute(select(sessions).where(sessions.c.id == sid, sessions.c.school_id == u.school_id, sessions.c.teacher_id == u.id).with_for_update()).first()
        if row is None:
            raise HTTPException(404, "没有找到这节课堂")
        return row

    def lesson_questions(db: Any, school_id: int, lesson_id: int, session_id: int | None = None) -> list[Any]:
        from changying.services.weekend_answers import session_question_ids
        stmt = select(TQ).where(TQ.school_id == school_id, TQ.lesson_id == lesson_id, TQ.stage != "removed", TQ.active.is_(True))
        if session_id is not None:
            snap_ids = session_question_ids(db, implementation, session_id)
            if snap_ids is not None:
                stmt = stmt.where(TQ.id.in_(snap_ids)) if snap_ids else stmt.where(TQ.id == -1)
        return list(db.scalars(stmt.order_by(TQ.id).limit(30)).all())

    def figure_of(q: Any) -> dict[str, Any]:
        """The picture imported with this question, if any (validated when it was written)."""
        try:
            fig = json.loads(getattr(q, "figure_json", "") or "{}")
        except (TypeError, ValueError):
            return {}
        if not isinstance(fig, dict) or fig.get("type") != "uploaded_image":
            return {}
        return fig if str(fig.get("data_url") or "").startswith("data:image/jpeg;base64,") else {}

    def level_names(subject: str) -> tuple[str, str, str]:
        return LEVEL_NAMES.get(subject, LEVEL_NAMES["default"])

    def options(q: Any) -> list[str]:
        try:
            raw = json.loads(q.options_json or "[]")
        except Exception:  # noqa: BLE001
            raw = []
        return [str(x) for x in raw] if isinstance(raw, list) else []

    def hint_rows(db: Any, school_id: int, qid: int) -> dict[int, Any]:
        return {int(r.level): r for r in db.execute(select(hints).where(hints.c.school_id == school_id, hints.c.question_id == qid)).all()}

    def draft_with_ai(db: Any, u: Any, q: Any) -> list[str]:
        names = level_names(q.subject)
        letters = "ABCDEFGH"
        opts = "；".join(f"{letters[i]}. {t}" for i, t in enumerate(options(q)))
        prompt = (
            f"你是小学{q.subject}老师，学生做题卡住了，请为下面这道题写 3 级递进提示。\n"
            f"题目：{q.stem}\n选项：{opts}\n正确答案：{letters[int(q.correct_index)] if 0 <= int(q.correct_index) < 8 else ''}\n"
            f"第1级【{names[0]}】：只给方向，不要说出答案或具体算式；第2级【{names[1]}】：指出第一步怎么做，仍不能说出最终答案；"
            f"第3级【{names[2]}】：完整讲解并给出答案。每级不超过 60 字，用小学生能懂的话。\n"
            '只输出 JSON：{"levels":["第1级","第2级","第3级"]}'
        )
        raw = implementation._ai_call(db, u, HINT_FEATURE, prompt, timeout=45)
        data = implementation._ai_json(raw)
        levels = data.get("levels") if isinstance(data, dict) else None
        if not isinstance(levels, list) or len(levels) != 3 or not all(str(x).strip() for x in levels):
            raise HTTPException(502, "AI 这次没有给出可用的提示，请再试一次")
        return [" ".join(str(x).split())[:300] for x in levels]

    def save_levels(db: Any, school_id: int, qid: int, levels: list[str], status: str) -> None:
        now = datetime.utcnow()
        existing = hint_rows(db, school_id, qid)
        for i, text in enumerate(levels, start=1):
            if i in existing:
                db.execute(update(hints).where(hints.c.id == existing[i].id).values(text=text, status=status, updated_at=now))
            else:
                db.execute(insert(hints).values(school_id=school_id, question_id=qid, level=i, text=text, status=status, updated_at=now))

    # ------------------------------------------------------------------ teacher
    @router.get("/teacher/weekend/sessions/{sid}/questions")
    def teacher_questions(sid: int, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "teacher")
        row = my_session(db, u, sid)
        lesson = db.get(implementation.TeachingLesson, row.lesson_id)
        source = lesson.reading_plan if lesson is not None else ""
        out = []
        for q in lesson_questions(db, int(u.school_id), int(row.lesson_id), int(row.id)):
            hs = hint_rows(db, int(u.school_id), q.id)
            status = "none" if len(hs) < 3 else ("approved" if all(h.status == "approved" for h in hs.values()) else ("auto" if any(h.status == "auto" for h in hs.values()) else "draft"))
            out.append({"id": q.id, "stem": numbered_student_stem(source, q.stem), "knowledge": q.knowledge, "subject": q.subject, "levelNames": level_names(q.subject),
                        "hints": [hs[i].text if i in hs else "" for i in (1, 2, 3)], "hintStatus": status})
        return {"items": out}

    @router.post("/teacher/weekend/hints/generate")
    def generate(b: GenBody, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "teacher")
        q = db.get(TQ, b.questionId)
        if q is None or int(q.school_id) != int(u.school_id):
            raise HTTPException(404, "没有找到这道题")
        levels = draft_with_ai(db, u, q)
        save_levels(db, int(u.school_id), q.id, levels, "draft")
        db.commit()
        return {"questionId": q.id, "hints": levels, "hintStatus": "draft"}

    @router.put("/teacher/weekend/hints/{qid}")
    def edit_hints(qid: int, b: HintBody, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "teacher")
        q = db.get(TQ, qid)
        if q is None or int(q.school_id) != int(u.school_id):
            raise HTTPException(404, "没有找到这道题")
        levels = [" ".join(str(x).split())[:300] for x in b.levels]
        if len(levels) != 3 or not all(levels):
            raise HTTPException(400, "需要填写 3 级提示")
        save_levels(db, int(u.school_id), qid, levels, "approved" if b.approve else "draft")
        db.commit()
        return {"questionId": qid, "hints": levels, "hintStatus": "approved" if b.approve else "draft"}

    @router.get("/teacher/weekend/sessions/{sid}/progress")
    def progress(sid: int, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "teacher")
        row = my_session(db, u, sid)
        qs = lesson_questions(db, int(u.school_id), int(row.lesson_id), int(row.id))
        qids = [q.id for q in qs]
        from changying.services.weekend_roster import session_roster
        names = {i: n for i, (n, _) in session_roster(implementation, db, row).items()}
        ans = db.execute(select(answers).where(answers.c.session_id == sid)).all()
        ans = [a for a in ans if int(a.student_id) in names]
        items = []
        for stu, name in sorted(names.items(), key=lambda kv: kv[1]):
            mine = [a for a in ans if int(a.student_id) == stu]
            done = len(mine)
            ok = sum(1 for a in mine if a.correct)
            hint_levels = [int(a.max_hint) for a in mine]
            items.append({
                "studentId": stu, "name": name, "answered": done, "correct": ok, "total": len(qids),
                "completionRate": round(100 * ok / len(qids)) if qids else 0,
                "hintAvg": round(sum(hint_levels) / done, 1) if done else 0, "hintMax": max(hint_levels) if hint_levels else 0,
            })
        rate = round(sum(i["completionRate"] for i in items if i["answered"]) / max(1, sum(1 for i in items if i["answered"])))
        return {"items": items, "classCompletionRate": rate, "questionCount": len(qids)}

    # ------------------------------------------------------------------ student
    def running_session_for(db: Any, u: Any) -> Any:
        from changying.services.weekend_roster import current_student_session
        return current_student_session(implementation, db, u)

    def student_session(db: Any, u: Any, sid: int) -> Any:
        row = running_session_for(db, u)
        if row is None or int(row.id) != sid:
            raise HTTPException(404, "现在没有正在上的课")
        row = db.execute(select(sessions).where(sessions.c.id == sid, sessions.c.school_id == u.school_id).with_for_update()).first()
        if row is None or row.status != "running":
            raise HTTPException(404, "现在没有正在上的课")
        from changying.services.weekend_roster import student_in_session
        if not student_in_session(implementation, db, row, u.id):
            raise HTTPException(404, "现在没有正在上的课")
        if int(row.current_stage) != PRACTICE_STAGE:
            raise HTTPException(409, "现在不是随堂练习时间")
        return row

    @router.get("/v1/weekend-practice", include_in_schema=False)
    def page():
        return HTMLResponse(practice_page_html(), headers=NO_CACHE)

    @router.get("/student/weekend/current")
    def current(u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "student")
        row = running_session_for(db, u)
        if row is None:
            return {"active": False, "message": "现在没有正在上的课"}
        from changying.services.weekend_stages import stage_by_no
        from changying.services.weekend_roster import session_class
        stage = stage_by_no(int(row.current_stage))
        bound = session_class(implementation, db, row)
        base = {"active": True, "sessionId": row.id, "title": row.title, "stage": int(row.current_stage),
                "stageName": stage["name"] if stage else "", "className": bound.class_name if bound else ""}
        if int(row.current_stage) != PRACTICE_STAGE:
            return {**base, "practice": False, "message": "还没到随堂练习，请看大屏听老师讲" if int(row.current_stage) < PRACTICE_STAGE else "随堂练习已关闭，可查看已提交答案与老师反馈"}
        lesson = db.get(implementation.TeachingLesson, row.lesson_id)
        source = lesson.reading_plan if lesson is not None else ""
        mine = {int(a.question_id): a for a in db.execute(select(answers).where(answers.c.session_id == row.id, answers.c.student_id == u.id)).all()}
        used = {}
        for qid, lvl in db.execute(select(hlog.c.question_id, func.max(hlog.c.level)).where(hlog.c.session_id == row.id, hlog.c.student_id == u.id).group_by(hlog.c.question_id)).all():
            used[int(qid)] = int(lvl)
        release_items, release_count, _ = practice_release(implementation, db, row)
        released_choices = {q["id"] for q in release_items[:release_count] if q["kind"] == "choice"}
        published = bool(release_items) and release_count == len(release_items)
        qs = []
        for q in lesson_questions(db, int(u.school_id), int(row.lesson_id), int(row.id)):
            a = mine.get(q.id)
            item = {"id": q.id, "stem": numbered_student_stem(source, q.stem), "options": options(q), "figure": figure_of(q), "answersPublished": q.id in released_choices, "canSubmit": q.id not in released_choices, "hintUsed": used.get(q.id, 0), "levelNames": level_names(q.subject)}
            if used.get(q.id):
                hs = hint_rows(db, int(u.school_id), q.id)
                item["hintTexts"] = [hs[i].text for i in range(1, used[q.id] + 1) if i in hs]
            if a is not None:
                item.update({"answered": True, "selected": int(a.selected), "attempts":submission_attempts(implementation,db,u,row.id,'choice',q.id,True)})
            qs.append(item)
        return {**base, "publishedWrittenQuestionIds": [q["id"] for q in release_items[:release_count] if q["kind"] == "written"], "practice": True, "canSubmit": not published, "answersPublished": published, "questions": qs}

    @router.post("/student/weekend/hint")
    def student_hint(b: StudentHintBody, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "student")
        row = student_session(db, u, b.sessionId)
        q = db.get(TQ, b.questionId)
        if q is None or int(q.school_id) != int(u.school_id) or int(q.lesson_id or 0) != int(row.lesson_id):
            raise HTTPException(404, "没有找到这道题")
        if answers_published(implementation, db, row, q.id):
            raise HTTPException(409, "老师已公布本题答案，停止提交")
        if db.execute(select(answers.c.id).where(answers.c.session_id == b.sessionId, answers.c.student_id == u.id, answers.c.question_id == q.id)).first():
            raise HTTPException(409, "这道题已经作答了")
        used = db.scalar(select(func.max(hlog.c.level)).where(hlog.c.session_id == b.sessionId, hlog.c.student_id == u.id, hlog.c.question_id == q.id)) or 0
        if used >= 3:
            raise HTTPException(409, "提示已经用完了，可以举手问老师")
        hs = hint_rows(db, int(u.school_id), q.id)
        usable = {i: h for i, h in hs.items() if h.status in ("approved", "auto")}
        if len(usable) < 3:
            levels = draft_with_ai(db, u, q)            # raises 502 with a readable message; nothing is recorded then
            save_levels(db, int(u.school_id), q.id, levels, "auto")
            db.commit()
            usable = hint_rows(db, int(u.school_id), q.id)
        level = int(used) + 1
        # AI generation commits its usage log; recheck after reacquiring the lock.
        student_session(db, u, b.sessionId)
        db.execute(insert(hlog).values(school_id=u.school_id, session_id=b.sessionId, student_id=u.id, question_id=q.id, level=level, created_at=datetime.utcnow()))
        db.commit()
        return {"level": level, "name": level_names(q.subject)[level - 1], "text": usable[level].text, "last": level >= 3}

    @router.post("/student/weekend/answer")
    def student_answer(b: AnswerBody, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "student")
        row = student_session(db, u, b.sessionId)
        q = db.get(TQ, b.questionId)
        if q is None or int(q.school_id) != int(u.school_id) or int(q.lesson_id or 0) != int(row.lesson_id):
            raise HTTPException(404, "没有找到这道题")
        if answers_published(implementation, db, row, q.id):
            raise HTTPException(409, "老师已公布本题答案，停止提交")
        if not 0 <= int(b.selected) < len(options(q)):
            raise HTTPException(400, "没有这个选项")
        require_unsettled(implementation, db, b.sessionId)
        old = db.execute(select(answers).where(answers.c.session_id==b.sessionId,answers.c.student_id==u.id,answers.c.question_id==q.id)).first()
        attempts = submission_attempts(implementation,db,u,b.sessionId,'choice',q.id,old is not None)
        if old and old.selected == b.selected:
            return {'submitted':True,'attempts':attempts,'selected':old.selected,'message':'答案已保存'}
        if b.attempt != attempts: raise HTTPException(409,'答案已更新，请刷新核对后重试')
        if attempts >= 3: raise HTTPException(409,'本题已提交3次，不能继续修改')
        used = db.scalar(select(func.max(hlog.c.level)).where(hlog.c.session_id==b.sessionId,hlog.c.student_id==u.id,hlog.c.question_id==q.id)) or 0
        values=dict(selected=b.selected,correct=b.selected==q.correct_index,max_hint=max(int(used),int(old.max_hint) if old else 0))
        if old: db.execute(update(answers).where(answers.c.id==old.id).values(**values))
        else: db.execute(insert(answers).values(school_id=u.school_id,session_id=b.sessionId,student_id=u.id,question_id=q.id,created_at=datetime.utcnow(),**values))
        record_submission(implementation,db,u,b.sessionId,'choice',q.id,attempts+1)
        db.commit()
        return {"submitted": True, "attempts":attempts+1, "selected":b.selected, "hintUsed": int(used), "message": "已提交，请等待老师在大屏公布答案"}

    from changying.web.weekend_written import install_weekend_written
    install_weekend_written(implementation)
    app.include_router(router)
    app.state.weekend_practice_installed = True
    app.state.weekend_practice_router = router
    return router


__all__ = ["install_weekend_practice", "register_practice_tables"]


