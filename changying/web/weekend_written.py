"""Teacher-reviewed classroom short answers; originals stay private to the class."""

from __future__ import annotations

from changying.services.weekend_answers import answers_published, practice_release
from changying.services.weekend_submissions import submission_attempts, record_submission, require_unsettled

import json
from datetime import datetime
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import Column, DateTime, Integer, LargeBinary, String, Table, Text, UniqueConstraint, func, insert, select, update
from sqlalchemy.exc import IntegrityError
from changying.web.weekend_precheck import WrittenPrechecks, register_precheck_table


class WrittenQuestionBody(BaseModel):
    stem: str = Field(min_length=1, max_length=4000)
    reference: str = Field(default="", max_length=4000)
    hints: list[str] = Field(default_factory=list, max_length=3)


class WrittenReviewBody(BaseModel):
    revision: int = Field(ge=1)
    result: str
    comment: str = Field(default="", max_length=1000)
    precheckId: int | None = None
    precheckToken: str = Field(default="", max_length=64)


class ReviewItem(WrittenReviewBody):
    id: int


class ReviewBatch(BaseModel):
    items: list[ReviewItem] = Field(min_length=1, max_length=1000)


def register_written_tables(implementation: Any) -> dict[str, Table]:
    md = implementation.Base.metadata
    if "weekend_written_questions" not in md.tables:
        Table("weekend_written_questions", md,
              Column("id", Integer, primary_key=True),
              Column("school_id", Integer, nullable=False, index=True),
              Column("lesson_id", Integer, nullable=False, index=True),
              Column("session_id", Integer, nullable=False, index=True),
              Column("teacher_id", Integer, nullable=False),
              Column("stem", Text, nullable=False), Column("reference", Text, nullable=False),
              Column("hints_json", Text, nullable=False))
    if "weekend_written_submissions" not in md.tables:
        Table("weekend_written_submissions", md,
              Column("id", Integer, primary_key=True),
              Column("school_id", Integer, nullable=False, index=True),
              Column("session_id", Integer, nullable=False, index=True),
              Column("question_id", Integer, nullable=False),
              Column("student_id", Integer, nullable=False),
              Column("answer_text", Text, nullable=False),
              Column("photo", LargeBinary, nullable=True), Column("photo_type", String(30), nullable=False),
              Column("revision", Integer, nullable=False),
              Column("result", String(20), nullable=False), Column("comment", Text, nullable=False),
              Column("submitted_at", DateTime, nullable=False), Column("reviewed_at", DateTime, nullable=True),
              UniqueConstraint("session_id", "question_id", "student_id", name="uq_weekend_written_student"))
    if "weekend_written_hint_log" not in md.tables:
        Table("weekend_written_hint_log", md,
              Column("id", Integer, primary_key=True),
              Column("school_id", Integer, nullable=False), Column("session_id", Integer, nullable=False),
              Column("student_id", Integer, nullable=False), Column("question_id", Integer, nullable=False),
              Column("level", Integer, nullable=False), Column("created_at", DateTime, nullable=False),
              UniqueConstraint("session_id", "question_id", "student_id", "level", name="uq_weekend_written_hint"))
    register_precheck_table(implementation)
    return {"questions": md.tables["weekend_written_questions"], "submissions": md.tables["weekend_written_submissions"],
            "hint_log": md.tables["weekend_written_hint_log"]}


def install_weekend_written(implementation: Any) -> APIRouter:
    app = implementation.app
    if getattr(app.state, "weekend_written_installed", False):
        return app.state.weekend_written_router
    from changying.web.weekend_views import register_weekend_tables
    t = register_written_tables(implementation)
    questions, submissions, hint_log = t["questions"], t["submissions"], t["hint_log"]
    sessions = register_weekend_tables(implementation)["sessions"]
    User, CS, SC = implementation.User, implementation.ClassStudent, implementation.SchoolClass
    current_user, get_db, need = implementation.current_user, implementation.get_db, implementation.need
    router = APIRouter()
    prechecks = WrittenPrechecks(implementation, t)

    def teacher_session(db: Any, u: Any, sid: int) -> Any:
        need(u, "teacher")
        row = db.execute(select(sessions).where(sessions.c.id == sid, sessions.c.school_id == u.school_id,
                                               sessions.c.teacher_id == u.id)).first()
        if row is None:
            raise HTTPException(404, "没有找到这节课堂")
        return row

    def student_session(db: Any, u: Any, sid: int) -> Any:
        need(u, "student")
        row = db.execute(select(sessions).where(sessions.c.id == sid, sessions.c.school_id == u.school_id).with_for_update()).first()
        from changying.services.weekend_roster import student_in_session
        if row is None or not student_in_session(implementation, db, row, u.id):
            raise HTTPException(404, "没有找到这节课堂")
        return row

    def question_rows(db: Any, row: Any) -> list[Any]:
        return db.execute(select(questions).where(questions.c.school_id == row.school_id,
            questions.c.session_id == row.id, questions.c.teacher_id == row.teacher_id).order_by(questions.c.id)).all()

    def submission_dict(a: Any) -> dict[str, Any]:
        return {"id": a.id, "studentId": a.student_id, "questionId": a.question_id, "text": a.answer_text,
                "hasPhoto": a.photo is not None, "revision": a.revision, "result": a.result, "comment": a.comment}

    @router.post("/teacher/weekend/sessions/{sid}/written/questions")
    def add_question(sid: int, b: WrittenQuestionBody, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        row = teacher_session(db, u, sid)
        if row.status != "planned":
            raise HTTPException(409, "请在开课前添加题目")
        stem = b.stem.strip()
        levels = [h.strip() for h in b.hints]
        if not stem or (levels and (len(levels) != 3 or not all(levels) or any(len(h) > 300 for h in levels))):
            raise HTTPException(400, "请填写题目；提示需填写完整的三级，每级不超过300字")
        qid = db.execute(insert(questions).values(school_id=u.school_id, lesson_id=row.lesson_id, session_id=sid, teacher_id=u.id,
            stem=stem, reference=b.reference.strip(), hints_json=json.dumps(levels, ensure_ascii=False))).inserted_primary_key[0]
        db.commit()
        return {"id": qid}

    @router.get("/teacher/weekend/sessions/{sid}/written")
    def teacher_list(sid: int, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        row = teacher_session(db, u, sid)
        qs = question_rows(db, row)
        ans = db.execute(select(submissions).where(submissions.c.session_id == sid, submissions.c.school_id == u.school_id)).all()
        names = dict(db.execute(select(User.id, User.name).where(User.school_id == u.school_id)).all())
        from changying.services.weekend_roster import session_roster
        members = session_roster(implementation, db, row)
        roster = set(members)
        names = {i: n for i, (n, _) in members.items()}
        ans = [a for a in ans if a.student_id in roster]
        total = len(qs) * len(roster | {a.student_id for a in ans})
        return {"status": row.status, "students": [{"id":i,"name":n} for i,n in names.items()], "total": total, "submissionRate": round(100 * len(ans) / total) if total else 0,
                "questions": [{"id": q.id, "stem": q.stem, "reference": q.reference} for q in qs],
                "items": [{**submission_dict(a), "name": names.get(a.student_id, "学生"),
                           "precheck": prechecks.view(db, a) if a.result == "pending" else None} for a in ans],
                "submitted": len(ans), "reviewed": sum(a.result != "pending" for a in ans),
                "correct": sum(a.result == "correct" for a in ans),
                "partial": sum(a.result == "partial" for a in ans),
                "pending": sum(a.result == "pending" for a in ans)}

    @router.get("/student/weekend/sessions/{sid}/written")
    def student_list(sid: int, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        row = student_session(db, u, sid)
        if row.status == "planned":
            return {"questions": [], "canSubmit": False, "status": row.status, "stage": row.current_stage}
        ans = {a.question_id: a for a in db.execute(select(submissions).where(submissions.c.session_id == sid,
            submissions.c.student_id == u.id, submissions.c.school_id == u.school_id)).all()}
        used = dict(db.execute(select(hint_log.c.question_id, func.max(hint_log.c.level)).where(
            hint_log.c.session_id == sid, hint_log.c.student_id == u.id).group_by(hint_log.c.question_id)).all())
        release_items, release_count, _ = practice_release(implementation, db, row)
        released = {q["id"] for q in release_items[:release_count] if q["kind"] == "written"}
        all_released = bool(release_items) and release_count == len(release_items)
        return {"status": row.status, "stage": row.current_stage, "canSubmit": row.status == "running" and row.current_stage == 4 and not all_released,
                "answersPublished": all_released,
                "questions": [{"id": q.id, "answersPublished": q.id in released, "canSubmit": row.status == "running" and row.current_stage == 4 and q.id not in released, "stem": q.stem, "hasHints": bool(json.loads(q.hints_json)), "hintUsed": used.get(q.id, 0),
                               "hintTexts": json.loads(q.hints_json)[:used.get(q.id, 0)],
                               "submission": ({**submission_dict(ans[q.id]), 'attempts':submission_attempts(implementation,db,u,sid,'written',q.id,True), **({} if q.id in released else {"result": "pending", "comment": ""})}) if q.id in ans else None} for q in question_rows(db, row)]}

    @router.post("/student/weekend/sessions/{sid}/written/{qid}/hint")
    def student_hint(sid: int, qid: int, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        row = student_session(db, u, sid)
        if row.status != "running" or row.current_stage != 4 or answers_published(implementation, db, row, qid, "written"):
            raise HTTPException(409, "现在不是随堂练习时间")
        q = next((q for q in question_rows(db, row) if q.id == qid), None)
        if q is None:
            raise HTTPException(404, "没有找到这道题")
        answered = db.execute(select(submissions.c.id).where(submissions.c.session_id == sid,
            submissions.c.student_id == u.id, submissions.c.question_id == qid)).first()
        if answered:
            raise HTTPException(409, "已提交答案，请查看老师评语")
        level = int(db.scalar(select(func.max(hint_log.c.level)).where(hint_log.c.session_id == sid,
            hint_log.c.student_id == u.id, hint_log.c.question_id == qid)) or 0) + 1
        levels = json.loads(q.hints_json)
        if not 1 <= level <= len(levels):
            raise HTTPException(404, "请举手向老师提问")
        try:
            db.execute(insert(hint_log).values(school_id=u.school_id, session_id=sid, student_id=u.id,
                question_id=qid, level=level, created_at=datetime.utcnow()))
            db.commit()
        except IntegrityError:
            db.rollback()
            raise HTTPException(409, "提示已更新，请刷新后重试")
        # Reference answers are never included in student payloads.
        return {"level": level, "text": levels[level - 1]}

    @router.post("/student/weekend/sessions/{sid}/written/{qid}")
    async def submit(sid: int, qid: int, tasks: BackgroundTasks, text: str = Form(""), revision: int = Form(0),
                     photo: UploadFile | None = File(None), removePhoto: bool = Form(False), u: Any = Depends(current_user), db: Any = Depends(get_db)):
        row = student_session(db, u, sid)
        if row.status != "running" or row.current_stage != 4 or answers_published(implementation, db, row, qid, "written"):
            raise HTTPException(409, "现在不是随堂练习时间")
        if not any(q.id == qid for q in question_rows(db, row)):
            raise HTTPException(404, "没有找到这道题")
        require_unsettled(implementation, db, sid)
        text = text.strip()
        if len(text) > 4000:
            raise HTTPException(400, "文字不能超过4000字")
        data, mime = None, ""
        if photo is not None:
            data = await photo.read(3 * 1024 * 1024 + 1)
            if len(data) > 3 * 1024 * 1024:
                raise HTTPException(413, "照片不能超过3MB，请裁剪后重试")
            if data.startswith(b"\xff\xd8\xff") and data.endswith(b"\xff\xd9"):
                mime = "image/jpeg"
            elif data.startswith(b"\x89PNG\r\n\x1a\n") and data.endswith(b"IEND\xaeB`\x82"):
                mime = "image/png"
            else:
                raise HTTPException(400, "请上传有效的JPEG或PNG照片")
        old = db.execute(select(submissions).where(submissions.c.session_id == sid, submissions.c.question_id == qid,
            submissions.c.student_id == u.id)).first()
        if old and photo is None and not removePhoto:
            data, mime = old.photo, old.photo_type
        if not text and not data: raise HTTPException(400,'请填写答案或拍照提交')
        attempts = submission_attempts(implementation, db, u, sid, 'written', qid, old is not None)
        if old and old.answer_text == text and old.photo == data:
            response = {"submitted":True,"revision":old.revision,"attempts":attempts,"submission":{**submission_dict(old),"result":"pending","comment":""}}
            db.rollback()
            if old.result == "pending": tasks.add_task(prechecks.run, old.id, old.revision)
            return response
        if attempts >= 3: raise HTTPException(409, '本题已提交3次，不能继续修改')
        values = dict(answer_text=text, photo=data, photo_type=mime, result="pending", comment="",
                      revision=revision + 1, submitted_at=datetime.utcnow(), reviewed_at=None)
        if old:
            if old.revision != revision:
                raise HTTPException(409, "答案已更新，请刷新后重试")
            changed = db.execute(update(submissions).where(submissions.c.id == old.id,
                submissions.c.revision == revision, submissions.c.result == old.result).values(**values))
            if changed.rowcount != 1:
                db.rollback()
                raise HTTPException(409, "答案已更新，请刷新后重试")
        else:
            if revision != 0:
                raise HTTPException(409, "答案版本不匹配，请刷新")
            try:
                db.execute(insert(submissions).values(school_id=u.school_id, session_id=sid, question_id=qid, student_id=u.id, **values))
            except IntegrityError:
                db.rollback()
                raise HTTPException(409, "答案已经提交，请刷新查看")
        record_submission(implementation, db, u, sid, 'written', qid, attempts+1)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise HTTPException(409, "答案已经提交，请刷新查看")
        saved = db.execute(select(submissions).where(submissions.c.session_id==sid,submissions.c.question_id==qid,submissions.c.student_id==u.id)).first()
        response = {"submitted": True, "revision":saved.revision, "attempts":attempts+1, "submission":{**submission_dict(saved),"result":"pending","comment":""}, "result": "pending"}
        db.rollback()
        tasks.add_task(prechecks.run, saved.id, saved.revision)
        return response

    def apply_reviews(sid, items, u, db):
        teacher_session(db, u, sid)
        db.execute(select(sessions.c.id).where(sessions.c.id==sid).with_for_update()).first()
        require_unsettled(implementation, db, sid)
        if len({item.id for item in items}) != len(items): raise HTTPException(400, '批改列表包含重复答案')
        if any(item.result not in ('correct','partial','revise') for item in items): raise HTTPException(400,'请选择批改结果')
        saved=[]
        for item in items:
            if item.precheckId is not None:
                answer = db.execute(select(submissions).where(submissions.c.id == item.id,
                    submissions.c.session_id == sid, submissions.c.school_id == u.school_id)).first()
                if answer is None or answer.revision != item.revision or answer.result != "pending":
                    db.rollback()
                    raise HTTPException(409, "答案已更新，请重新核验预批")
                view = prechecks.validate(db, answer, item.precheckId, item.precheckToken)
                if item.result != view["suggestedResult"]:
                    raise HTTPException(400, "修改预批结果后请使用手工批改保存")
            changed=db.execute(update(submissions).where(submissions.c.id==item.id,submissions.c.session_id==sid,
                submissions.c.school_id==u.school_id,submissions.c.revision==item.revision).values(result=item.result,
                comment=item.comment.strip(),reviewed_at=datetime.utcnow(),revision=item.revision+1))
            if changed.rowcount != 1:
                db.rollback()
                raise HTTPException(409, '学生答案已更新，本批未保存；请刷新后重新核对')
            saved.append({'id':item.id,'revision':item.revision+1,'result':item.result,'comment':item.comment.strip()})
        db.commit()
        return {'reviewed':True,'items':saved}

    @router.post('/teacher/weekend/sessions/{sid}/written/review-batch')
    def review_batch(sid: int, b: ReviewBatch, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        return apply_reviews(sid,b.items,u,db)

    @router.post("/teacher/weekend/sessions/{sid}/written/{aid}/review")
    def review(sid: int, aid: int, b: WrittenReviewBody, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        return apply_reviews(sid,[ReviewItem(id=aid,**b.model_dump())],u,db)

    @router.get("/weekend/written/submissions/{aid}/photo")
    def read_photo(aid: int, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        a = db.execute(select(submissions).where(submissions.c.id == aid, submissions.c.school_id == u.school_id)).first()
        if a is None:
            raise HTTPException(404, "没有找到照片")
        row = db.execute(select(sessions).where(sessions.c.id == a.session_id)).first()
        if row is None or not ((u.role == "teacher" and row.teacher_id == u.id) or (u.role == "student" and a.student_id == u.id)):
            raise HTTPException(404, "没有找到照片")
        if a.photo is None:
            raise HTTPException(404, "没有找到照片")
        return Response(content=a.photo, media_type=a.photo_type,
                        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})

    prechecks.install(router, teacher_session)
    app.include_router(router)
    app.state.weekend_written_installed = True
    app.state.weekend_written_router = router
    return router
