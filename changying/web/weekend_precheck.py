"""Persistent, teacher-only suggestions. Formal results are written by existing review routes."""
from __future__ import annotations

from datetime import datetime, timedelta
import hashlib
import json
import logging
from typing import Any
from types import SimpleNamespace

from fastapi import BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import Column, DateTime, Integer, String, Table, Text, UniqueConstraint, insert, select, update
from sqlalchemy.exc import IntegrityError

from changying.services import written_precheck as rules
from changying.services.homework_limits import ai_slot, check_student_call, require_student_ai
from changying.services.homework_vision import VISION_FAILURE_MESSAGES, VisionFailure, recognize_image, vision_enabled

logger = logging.getLogger(__name__)


class PrecheckRequest(BaseModel):
    revision: int = Field(ge=1)
    retry: bool = False


class Correction(BaseModel):
    key: str = Field(max_length=10)
    question: str = Field(max_length=4000)
    answers: list[str] = Field(max_length=20)
    confidence: float = Field(ge=0, le=1)


class CorrectTranscription(BaseModel):
    revision: int = Field(ge=1)
    token: str = Field(max_length=64)
    items: list[Correction] = Field(max_length=40)


def register_precheck_table(implementation: Any) -> Table:
    md = implementation.Base.metadata
    if "weekend_written_prechecks" not in md.tables:
        Table("weekend_written_prechecks", md,
              Column("id", Integer, primary_key=True),
              Column("school_id", Integer, nullable=False, index=True),
              Column("submission_id", Integer, nullable=False, index=True),
              Column("revision", Integer, nullable=False),
              Column("question_hash", String(64), nullable=False),
              Column("status", String(20), nullable=False),
              Column("payload_json", Text, nullable=False),
              Column("updated_at", DateTime, nullable=False),
              UniqueConstraint("submission_id", "revision", "question_hash", name="uq_written_precheck_version"))
    return md.tables["weekend_written_prechecks"]


class WrittenPrechecks:
    def __init__(self, implementation: Any, tables: dict[str, Table]):
        self.impl, self.table = implementation, register_precheck_table(implementation)
        self.questions, self.submissions = tables["questions"], tables["submissions"]

    def current(self, db, answer):
        return db.execute(select(self.questions).where(self.questions.c.id == answer.question_id,
                         self.questions.c.school_id == answer.school_id)).first()

    def key(self, answer, question):
        t = self.table
        return (t.c.submission_id == answer.id, t.c.revision == answer.revision,
                t.c.question_hash == rules.fingerprint(question.stem, question.reference), t.c.school_id == answer.school_id)

    def view(self, db, answer):
        question = self.current(db, answer)
        if question is None: return None
        row = db.execute(select(self.table).where(*self.key(answer, question))).first()
        if row is None: return None
        body = json.loads(row.payload_json)
        return {"id": row.id, "revision": row.revision, "status": row.status,
                "token": hashlib.sha256(row.payload_json.encode()).hexdigest(), **body}

    def validate(self, db, answer, job_id, token):
        view = self.view(db, answer)
        if not view or view["id"] != job_id or view["token"] != token or view["status"] != "ready" or not view.get("suggestedResult"):
            raise HTTPException(409, "预批依据已更新或仍需人工核验，请刷新后检查")
        return view

    def run(self, aid: int, revision: int, retry: bool = False):
        # Separate transaction/session: OCR failure cannot roll back a student's saved work.
        impl, t = self.impl, self.table
        with impl.SessionLocal() as db:
            answer = db.execute(select(self.submissions).where(self.submissions.c.id == aid)).first()
            if answer is None or answer.revision != revision or answer.result != "pending": return
            question = self.current(db, answer)
            if question is None: return
            key = self.key(answer, question)
            old = db.execute(select(t).where(*key)).first()
            if old is not None:
                if old.status in ("ready", "manual"): return
                if old.status == "working" and old.updated_at > datetime.utcnow() - timedelta(minutes=2): return
                if not retry and old.status in ("failed", "disabled"): return
                claim = db.execute(update(t).where(t.c.id == old.id, t.c.updated_at == old.updated_at)
                    .values(status="working", payload_json='{"message":"正在识别并核对，请稍候","requiresTeacher":true}', updated_at=datetime.utcnow()))
                if claim.rowcount != 1: db.rollback(); return
                job_id = old.id
            else:
                try:
                    job_id = db.execute(insert(t).values(school_id=answer.school_id, submission_id=aid,
                        revision=revision, question_hash=rules.fingerprint(question.stem, question.reference),
                        status="working", payload_json='{}', updated_at=datetime.utcnow())).inserted_primary_key[0]
                except IntegrityError:
                    db.rollback(); return
            db.commit()
            status, payload = "manual", {"message": "请老师核验", "items": [], "suggestedResult": None, "requiresTeacher": True}
            try:
                if not question.reference.strip():
                    payload["message"] = "本题尚无参考答案，请老师补充或手工批改"
                elif answer.photo:
                    user = db.get(impl.User, answer.student_id)
                    require_student_ai(impl, db, user)
                    if not vision_enabled():
                        raise HTTPException(503, "unconfigured")
                    with ai_slot():
                        check_student_call(impl, db, user)
                        # Release the pooled connection while the external recognizer runs.
                        # The recognizer opens a short transaction only to record usage later.
                        actor = SimpleNamespace(id=user.id, school_id=user.school_id)
                        db.rollback()
                        read = recognize_image(impl, db, actor, answer.photo,
                            feature="homework_help_written_precheck_ocr", prompt=rules.transcription_prompt())
                    try:
                        parsed = impl._ai_json(read["text"])
                    except HTTPException:
                        raise VisionFailure(502, "invalid transcription", "invalid_transcription") from None
                    observed = parsed.get("items") if isinstance(parsed, dict) else None
                    if not isinstance(observed, list):
                        raise VisionFailure(502, "invalid transcription", "invalid_transcription")
                    # Overall image uncertainty must also veto per-item comparisons.
                    if not isinstance(read.get("confidence"), (float, int)) or not .9 <= read["confidence"] <= 1:
                        observed = [{**i, "confidence": 0} for i in observed if isinstance(i, dict)]
                    payload = rules.preview(question.stem, question.reference, observed)
                    status = "ready" if payload["suggestedResult"] else "manual"
                else:
                    payload = rules.preview(question.stem, question.reference, rules.typed_observations(question.stem, answer.answer_text))
                    status = "ready" if payload["suggestedResult"] else "manual"
            except HTTPException as exc:
                db.rollback()
                status = "disabled" if exc.status_code in (403, 503) else "failed"
                if isinstance(exc, VisionFailure):
                    # Provider 403/503 remains an upstream failure, not a school permission denial.
                    status = "failed"
                    payload.update(code=exc.reason, message=VISION_FAILURE_MESSAGES[exc.reason])
                    if exc.upstream_status is not None:
                        payload["upstreamStatus"] = exc.upstream_status
                elif exc.status_code == 429:
                    payload.update(code="busy_or_limited", message="识别繁忙或调用次数已达限制，请稍后重试；仍可手工批改")
                elif exc.status_code == 504:
                    payload.update(code="timeout", message="本次识别超时，请重试；仍可手工批改")
                elif status == "disabled":
                    payload.update(code="not_enabled", message="识别未开启或未获学校授权，仍可手工批改")
                else:
                    payload.update(code="service_error", message="识别服务暂时不可用，请稍后重试；仍可手工批改")
                logger.warning("written_precheck_failed code=%s http_status=%s upstream_status=%s",
                               payload["code"], exc.status_code, payload.get("upstreamStatus", "none"))
            except Exception:
                db.rollback()
                status, payload["message"] = "failed", "无法可靠读取答案，可重试或手工批改"
                payload["code"] = "processing_error"
                logger.warning("written_precheck_failed code=processing_error")
            # The student or teacher may have changed the answer while recognition ran.
            db.expire_all()
            latest = db.execute(select(self.submissions).where(self.submissions.c.id == aid)).first()
            latest_q = self.current(db, latest) if latest is not None else None
            if latest is None or latest.revision != revision or latest.result != "pending" or latest_q is None or rules.fingerprint(latest_q.stem, latest_q.reference) != rules.fingerprint(question.stem, question.reference):
                status, payload = "stale", {"message": "答案或参考答案已更新，旧预批不再可用"}
            db.execute(update(t).where(t.c.id == job_id).values(status=status,
                payload_json=json.dumps(payload, ensure_ascii=False), updated_at=datetime.utcnow()))
            db.commit()

    def install(self, router, teacher_session):
        impl = self.impl

        def context(db, user, sid, aid, revision):
            session = teacher_session(db, user, sid)
            answer = db.execute(select(self.submissions).where(self.submissions.c.id == aid,
                self.submissions.c.school_id == user.school_id, self.submissions.c.session_id == sid)).first()
            from changying.services.weekend_roster import session_roster
            if answer is None or answer.student_id not in session_roster(impl, db, session):
                raise HTTPException(404, "没有找到这份答案")
            if answer.revision != revision or answer.result != "pending":
                raise HTTPException(409, "学生答案或批改结果已更新，请刷新")
            return answer

        @router.post("/teacher/weekend/sessions/{sid}/written/{aid}/precheck")
        def request_precheck(sid: int, aid: int, b: PrecheckRequest, tasks: BackgroundTasks,
                             u: Any = Depends(impl.current_user), db: Any = Depends(impl.get_db)):
            answer = context(db, u, sid, aid, b.revision)
            # Publish the queued state before returning the response. Otherwise the
            # first poll can still see the previous failure before the task starts.
            question = self.current(db, answer)
            if question is not None and b.retry:
                db.execute(update(self.table).where(*self.key(answer, question),
                    self.table.c.status.in_(("failed", "disabled", "stale"))).values(
                    status="queued", payload_json='{"message":"已排队，正在等待识别","requiresTeacher":true}',
                    updated_at=datetime.utcnow()))
                db.commit()
            # Yield dependencies stay alive until BackgroundTasks finish. Do not keep
            # the authentication/context connection checked out for that whole time.
            db.rollback()
            tasks.add_task(self.run, aid, b.revision, b.retry)
            return {"queued": True, "revision": b.revision}

        @router.get("/teacher/weekend/sessions/{sid}/written/{aid}/precheck")
        def precheck_status(sid: int, aid: int, revision: int,
                            u: Any = Depends(impl.current_user), db: Any = Depends(impl.get_db)):
            answer = context(db, u, sid, aid, revision)
            return {"revision": answer.revision, "precheck": self.view(db, answer)}

        @router.post("/teacher/weekend/sessions/{sid}/written/{aid}/precheck/transcription")
        def correct_transcription(sid: int, aid: int, b: CorrectTranscription,
                                  u: Any = Depends(impl.current_user), db: Any = Depends(impl.get_db)):
            # Lock the classroom as review/submit do: recheck the original revision inside the transaction.
            session_table = impl.Base.metadata.tables["weekend_sessions"]
            teacher_session(db, u, sid)
            db.execute(select(session_table.c.id).where(session_table.c.id == sid).with_for_update()).first()
            answer = context(db, u, sid, aid, b.revision)
            view = self.view(db, answer)
            if not view or view["token"] != b.token or view["status"] not in ("manual", "ready"):
                raise HTTPException(409, "预批已更新，请刷新")
            question = self.current(db, answer)
            payload = rules.preview(question.stem, question.reference, [i.model_dump() for i in b.items])
            payload["transcriptionReviewed"] = True
            encoded = json.dumps(payload, ensure_ascii=False)
            db.execute(update(self.table).where(self.table.c.id == view["id"]).values(
                status="ready" if payload["suggestedResult"] else "manual", payload_json=encoded, updated_at=datetime.utcnow()))
            db.commit()
            return {"precheck": self.view(db, answer)}
