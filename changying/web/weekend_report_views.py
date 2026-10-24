"""周末课 课后总结与个人学情反馈.

teacher  GET  /teacher/weekend/sessions/{sid}/summary      class summary, per-pupil question detail, report states (writes nothing)
         GET  /teacher/weekend/report-sessions?date=        my weekend lessons started on one school-local day (to combine subjects)
         POST /teacher/weekend/reports                      {studentId, sessionIds, useAi?, replace?, revision?} create / regenerate a draft
         GET  /teacher/weekend/reports/{rid}                live facts, saved draft, published version and state
         PUT  /teacher/weekend/reports/{rid}                {revision, sections, comment} save the teacher's edits
         POST /teacher/weekend/reports/{rid}/publish        {revision} release the saved draft to the linked parents
         GET  /teacher/weekend/reports/{rid}/report.docx    ?version=draft|published, A4 Word for printing
parent   GET  /parent/children/{cid}/weekend-briefs         (weekend_scoring_views) also returns the published reports

Facts come from changying/services/weekend_reports.py. Nothing here settles points, releases answers or
publishes without the teacher's explicit publish request; original answers and reviews are only read.
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy import Column, DateTime, Integer, String, Table, Text, UniqueConstraint, insert, select, update
from sqlalchemy.exc import IntegrityError

from changying.services import weekend_reports as wr

AI_FEATURE = "weekend_report"
MAX_LESSONS = 4
STATE_LABEL = {"none": "未生成", "draft": "草稿", "published": "已发布", "stale": "发布后有新数据"}


class ReportBody(BaseModel):
    studentId: int = Field(gt=0)
    sessionIds: list[int] = Field(min_length=1, max_length=MAX_LESSONS)
    useAi: bool = False
    replace: bool = False
    revision: int | None = None


class SaveBody(BaseModel):
    revision: int = Field(ge=1)
    sections: list[dict[str, Any]] = Field(min_length=1, max_length=MAX_LESSONS)
    comment: str = Field(default="", max_length=wr.TEXT_LIMIT)


class PublishBody(BaseModel):
    revision: int = Field(ge=1)


def register_report_table(implementation: Any) -> Table:
    md = implementation.Base.metadata
    if "weekend_reports" not in md.tables:
        Table("weekend_reports", md,
              Column("id", Integer, primary_key=True),
              Column("school_id", Integer, nullable=False, index=True),
              Column("teacher_id", Integer, nullable=False, index=True),
              Column("student_id", Integer, nullable=False, index=True),
              Column("report_date", String(10), nullable=False),
              Column("session_key", String(120), nullable=False),        # sorted weekend session ids, "12,13"
              Column("draft_json", Text, nullable=False),
              Column("draft_revision", Integer, nullable=False),
              Column("draft_hash", String(64), nullable=False),          # facts the draft was generated from
              Column("draft_saved_at", DateTime, nullable=False),
              Column("published_json", Text, nullable=True),
              Column("published_facts_json", Text, nullable=True),
              Column("published_hash", String(64), nullable=True),
              Column("published_revision", Integer, nullable=True),      # draft revision that was published
              Column("published_version", Integer, nullable=False),
              Column("published_at", DateTime, nullable=True),
              Column("created_at", DateTime, nullable=False),
              UniqueConstraint("school_id", "teacher_id", "student_id", "session_key", name="uq_weekend_report"))
    return md.tables["weekend_reports"]


def published_reports(implementation: Any, db: Any, school_id: int, student_id: int) -> list[dict[str, Any]]:
    """Parent-safe published versions only; drafts and teacher-only data never leave here."""
    t = register_report_table(implementation)
    out = []
    for r in db.execute(select(t).where(t.c.school_id == school_id, t.c.student_id == student_id, t.c.published_json.isnot(None))
                        .order_by(t.c.report_date.desc(), t.c.id.desc()).limit(60)):
        body = json.loads(r.published_json)
        facts = json.loads(r.published_facts_json or "[]")
        out.append({"id": r.id, "date": r.report_date, "subjects": [f["subject"] for f in facts], "facts": facts,
                    "sections": body["sections"], "comment": body.get("comment", ""), "titles": wr.SECTION_TITLES,
                    "version": int(r.published_version), "publishedAt": wr.local_dt(implementation, r.published_at).strftime("%Y-%m-%d %H:%M"),
                    "sessionIds": [int(x) for x in r.session_key.split(",")]})
    return out


def install_weekend_reports(implementation: Any) -> APIRouter:
    app = implementation.app
    if getattr(app.state, "weekend_reports_installed", False):
        return app.state.weekend_reports_router
    from changying.web.weekend_views import register_weekend_tables

    sessions = register_weekend_tables(implementation)["sessions"]
    reports = register_report_table(implementation)
    current_user, get_db, need = implementation.current_user, implementation.get_db, implementation.need
    router = APIRouter()

    def my_session(db: Any, u: Any, sid: int) -> Any:
        row = db.execute(select(sessions).where(sessions.c.id == sid, sessions.c.school_id == u.school_id, sessions.c.teacher_id == u.id)).first()
        if row is None:
            raise HTTPException(404, "没有找到这节课堂")
        return row

    def report_parts(db: Any, u: Any, student_id: int, session_ids: list[int]) -> tuple[list[dict[str, Any]], str]:
        """The pupil's facts per lesson, in session-id order (the order of report sections)."""
        ids = sorted(set(session_ids))
        rows = [my_session(db, u, sid) for sid in ids]
        if any(r.started_at is None for r in rows):
            raise HTTPException(400, "所选课堂还没有开始上课，没有可总结的记录")
        days = {wr.local_date(implementation, r) for r in rows}
        if len(days) != 1:
            raise HTTPException(400, "合并报告只能选择同一天的课堂")
        parts = []
        for r in rows:
            part = wr.student_facts(wr.session_facts(implementation, db, r), student_id)
            if part is None or not part["participated"]:
                raise HTTPException(400, f"这位学生在《{r.title}》没有作答记录，不能生成这节课的反馈")
            parts.append(part)
        subjects = [p["subject"] for p in parts]
        if len(set(subjects)) != len(subjects):
            raise HTTPException(400, "同一份报告里每个科目只选一节课")
        return parts, days.pop()

    def report_row(db: Any, u: Any, rid: int) -> Any:
        r = db.execute(select(reports).where(reports.c.id == rid, reports.c.school_id == u.school_id, reports.c.teacher_id == u.id)).first()
        if r is None:
            raise HTTPException(404, "没有找到这份报告")
        return r

    def state_of(r: Any, live_hash: str) -> str:
        if r is None:
            return "none"
        if r.published_json is None:
            return "draft"
        return "stale" if r.published_hash != live_hash else "published"

    def describe(db: Any, u: Any, r: Any) -> dict[str, Any]:
        ids = [int(x) for x in r.session_key.split(",")]
        parts, _ = report_parts(db, u, int(r.student_id), ids)
        live = wr.fingerprint(parts)
        draft = json.loads(r.draft_json)
        state = state_of(r, live)
        published = None
        if r.published_json is not None:
            body = json.loads(r.published_json)
            published = {"sections": body["sections"], "comment": body.get("comment", ""), "facts": json.loads(r.published_facts_json),
                         "version": int(r.published_version), "revision": int(r.published_revision),
                         "at": wr.local_dt(implementation, r.published_at).strftime("%Y-%m-%d %H:%M")}
        return {"id": r.id, "studentId": int(r.student_id), "studentName": parts[0]["name"], "date": r.report_date, "sessionIds": ids,
                "state": state, "stateLabel": STATE_LABEL[state], "facts": parts, "parentFacts": [wr.parent_facts(p) for p in parts],
                "draft": {**draft, "revision": int(r.draft_revision), "savedAt": wr.local_dt(implementation, r.draft_saved_at).strftime("%Y-%m-%d %H:%M"),
                          "factsChanged": r.draft_hash != live,
                          "unpublishedEdits": r.published_revision is None or int(r.published_revision) != int(r.draft_revision)},
                "published": published, "titles": wr.SECTION_TITLES, "sectionKeys": list(wr.SECTION_KEYS), "autoSections": list(wr.AUTO_SECTIONS)}

    @router.get("/v1/weekend-report", include_in_schema=False)
    def report_page():
        from changying.web.weekend_pages import report_page_html
        return HTMLResponse(report_page_html(), headers={"Cache-Control": "no-store"})

    @router.get("/teacher/weekend/sessions/{sid}/summary")
    def summary(sid: int, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "teacher")
        row = my_session(db, u, sid)
        facts = wr.session_facts(implementation, db, row)
        states: dict[int, dict[str, Any]] = {}
        for r in db.execute(select(reports).where(reports.c.school_id == u.school_id, reports.c.teacher_id == u.id)):
            ids = [int(x) for x in r.session_key.split(",")]
            if sid not in ids or int(r.student_id) not in facts["students"]:
                continue
            try:
                parts, _ = report_parts(db, u, int(r.student_id), ids)
                state = state_of(r, wr.fingerprint(parts))
            except HTTPException:
                state = "draft" if r.published_json is None else "stale"
            states[int(r.student_id)] = {"reportId": r.id, "state": state, "stateLabel": STATE_LABEL[state], "sessionIds": ids}
        students = []
        for pupil in facts["students"].values():
            items = []
            for q, i in zip(facts["questions"], pupil["items"]):
                item = {k: v for k, v in i.items() if k not in ("submittedAt", "reviewedAt")}
                item.update(stem=q["stem"], statusLabel=wr.STATUS_LABEL[i["status"]],
                            submittedAt=(wr.local_dt(implementation, i["submittedAt"]).strftime("%H:%M") if i.get("submittedAt") else ""))
                if q["kind"] == "choice" and 0 <= q["correctIndex"] < len(q["options"]):
                    item["reference"] = chr(65 + q["correctIndex"]) + ". " + q["options"][q["correctIndex"]]
                if i.get("hasPhoto"):
                    item["photoUrl"] = f"/weekend/written/submissions/{i['submissionId']}/photo"
                items.append(item)
            students.append({**{k: pupil[k] for k in ("studentId", "name", "participated", "counts", "explained", "followups", "points")},
                             "items": items, "report": states.get(pupil["studentId"], {"state": "none", "stateLabel": STATE_LABEL["none"]})})
        return {**{k: facts[k] for k in ("sessionId", "title", "status", "date", "subject", "lessonTitle", "unit", "coreTarget", "className", "settled", "cutoff")},
                "summary": wr.class_summary(facts), "students": students, "statusLabels": wr.STATUS_LABEL}

    @router.get("/teacher/weekend/report-sessions")
    def report_sessions(date: str = "", u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "teacher")
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
            raise HTTPException(400, "请选择日期")
        out = []
        for r in db.execute(select(sessions).where(sessions.c.school_id == u.school_id, sessions.c.teacher_id == u.id,
                                                   sessions.c.started_at.isnot(None)).order_by(sessions.c.id)):
            if wr.local_date(implementation, r) != date:
                continue
            facts = wr.session_facts(implementation, db, r)
            out.append({"sessionId": r.id, "title": r.title, "status": r.status, "subject": facts["subject"], "className": facts["className"],
                        "participants": [{"studentId": p["studentId"], "name": p["name"]} for p in facts["students"].values() if p["participated"]]})
        return {"date": date, "items": out}

    def generated(db: Any, u: Any, parts: list[dict[str, Any]], use_ai: bool) -> tuple[list[dict[str, str]], str]:
        drafts = [wr.draft_section(p) for p in parts]
        if not use_ai:
            return drafts, "template"
        try:
            cfg = implementation.ai_config_for(db, u.school_id, False)
            if not cfg or not cfg.enabled or not cfg.allow_student_data:
                return drafts, "ai_not_allowed"
            data = implementation._ai_json(implementation._ai_call(db, u, AI_FEATURE, wr.ai_prompt(parts, drafts), timeout=45))
            return wr.apply_ai(drafts, data), "ai"
        except Exception:  # noqa: BLE001 - the factual template is always usable without AI
            return drafts, "ai_failed"

    @router.post("/teacher/weekend/reports")
    def create_report(b: ReportBody, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "teacher")
        parts, day = report_parts(db, u, b.studentId, b.sessionIds)
        key = ",".join(str(p["sessionId"]) for p in parts)
        existing = db.execute(select(reports).where(reports.c.school_id == u.school_id, reports.c.teacher_id == u.id,
                                                    reports.c.student_id == b.studentId, reports.c.session_key == key)).first()
        if existing is not None and not b.replace:
            # Never overwrite the teacher's edits silently; the page opens the saved draft instead.
            return {"id": existing.id, "created": False, "source": "existing", "report": describe(db, u, existing)}
        sections, source = generated(db, u, parts, b.useAi)
        now = datetime.utcnow()
        if existing is None:
            body = {"sections": [{**s, "sessionId": p["sessionId"]} for s, p in zip(sections, parts)], "comment": ""}
            try:
                rid = db.execute(insert(reports).values(school_id=u.school_id, teacher_id=u.id, student_id=b.studentId, report_date=day,
                    session_key=key, draft_json=json.dumps(body, ensure_ascii=False), draft_revision=1, draft_hash=wr.fingerprint(parts),
                    draft_saved_at=now, published_version=0, created_at=now)).inserted_primary_key[0]
                db.commit()
            except IntegrityError:
                db.rollback()
                raise HTTPException(409, "这份报告刚刚已生成，请刷新后打开")
            return {"id": rid, "created": True, "source": source, "report": describe(db, u, report_row(db, u, rid))}
        if b.revision != int(existing.draft_revision):
            raise HTTPException(409, "草稿已被修改，请刷新核对后再重新生成")
        # Regenerating replaces only the system-written sections; the teacher's observation and comment stay.
        old = json.loads(existing.draft_json)
        kept = {int(s.get("sessionId", 0)): s.get("observation", "") for s in old.get("sections", [])}
        body = {"sections": [{**s, "sessionId": p["sessionId"], "observation": kept.get(p["sessionId"], "")} for s, p in zip(sections, parts)],
                "comment": old.get("comment", "")}
        changed = db.execute(update(reports).where(reports.c.id == existing.id, reports.c.draft_revision == existing.draft_revision).values(
            draft_json=json.dumps(body, ensure_ascii=False), draft_revision=existing.draft_revision + 1, draft_hash=wr.fingerprint(parts), draft_saved_at=now))
        if changed.rowcount != 1:
            db.rollback()
            raise HTTPException(409, "草稿已被修改，请刷新核对后再重新生成")
        db.commit()
        return {"id": existing.id, "created": False, "source": source, "report": describe(db, u, report_row(db, u, existing.id))}

    @router.get("/teacher/weekend/reports/{rid}")
    def get_report(rid: int, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "teacher")
        return describe(db, u, report_row(db, u, rid))

    @router.put("/teacher/weekend/reports/{rid}")
    def save_report(rid: int, b: SaveBody, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "teacher")
        r = report_row(db, u, rid)
        parts, _ = report_parts(db, u, int(r.student_id), [int(x) for x in r.session_key.split(",")])
        try:
            sections = wr.clean_sections(b.sections, parts)
        except ValueError as e:
            raise HTTPException(400, str(e))
        body = {"sections": sections, "comment": b.comment.replace("\r\n", "\n").strip()}
        changed = db.execute(update(reports).where(reports.c.id == rid, reports.c.draft_revision == b.revision).values(
            draft_json=json.dumps(body, ensure_ascii=False), draft_revision=b.revision + 1, draft_saved_at=datetime.utcnow()))
        if changed.rowcount != 1:
            db.rollback()
            raise HTTPException(409, "草稿已在别处更新，本次未保存；请复制你的修改后刷新核对")
        db.commit()
        return describe(db, u, report_row(db, u, rid))

    @router.post("/teacher/weekend/reports/{rid}/publish")
    def publish_report(rid: int, b: PublishBody, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "teacher")
        r = report_row(db, u, rid)
        if int(r.draft_revision) != b.revision:
            raise HTTPException(409, "草稿已更新，请先核对最新内容再发布")
        parts, _ = report_parts(db, u, int(r.student_id), [int(x) for x in r.session_key.split(",")])
        draft = json.loads(r.draft_json)
        changed = db.execute(update(reports).where(reports.c.id == rid, reports.c.draft_revision == b.revision).values(
            published_json=json.dumps({"sections": draft["sections"], "comment": draft.get("comment", "")}, ensure_ascii=False),
            published_facts_json=json.dumps([wr.parent_facts(p) for p in parts], ensure_ascii=False),
            published_hash=wr.fingerprint(parts), published_revision=b.revision, published_version=int(r.published_version) + 1,
            published_at=datetime.utcnow()))
        if changed.rowcount != 1:
            db.rollback()
            raise HTTPException(409, "草稿已更新，请先核对最新内容再发布")
        db.commit()
        return describe(db, u, report_row(db, u, rid))

    @router.get("/teacher/weekend/reports/{rid}/report.docx")
    def report_docx(rid: int, version: str = "draft", u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "teacher")
        from changying.services.weekend_handouts import report_document
        d = describe(db, u, report_row(db, u, rid))
        if version == "published":
            if d["published"] is None:
                raise HTTPException(404, "这份报告还没有发布")
            body, facts, label = d["published"], d["published"]["facts"], f"已发布第{d['published']['version']}版 {d['published']['at']}"
        elif version == "draft":
            body, facts, label = d["draft"], d["parentFacts"], "草稿（未发布）"
        else:
            raise HTTPException(400, "请选择草稿或已发布版本")
        titles = [(k, wr.SECTION_TITLES[k]) for k in wr.SECTION_KEYS]
        data = report_document({"studentName": d["studentName"], "date": d["date"], "facts": facts, "sections": body["sections"],
                                "comment": body.get("comment", ""), "titles": titles, "stateLabel": label})
        from urllib.parse import quote
        name = f"{d['studentName']}-{d['date']}-周末课学情反馈.docx"
        return Response(data, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        headers={"Content-Disposition": f"attachment; filename=weekend-report-{rid}-{d['date']}.docx; filename*=UTF-8''{quote(name)}",
                                 "Cache-Control": "no-store"})

    app.include_router(router)
    app.state.weekend_reports_installed = True
    app.state.weekend_reports_router = router
    return router


__all__ = ["install_weekend_reports", "published_reports", "register_report_table"]
