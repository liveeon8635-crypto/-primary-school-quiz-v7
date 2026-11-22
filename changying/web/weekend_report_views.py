"""周末课 课后总结与个人学情反馈.

teacher  GET  /teacher/weekend/sessions/{sid}/summary      class summary, per-pupil question detail, report states (writes nothing)
         GET  /teacher/weekend/report-sessions?date=        my weekend lessons started on one school-local day (to combine subjects)
         POST /teacher/weekend/reports                      {studentId, sessionIds, useAi?, replace?, revision?} create / regenerate a draft
         GET  /teacher/weekend/reports/{rid}                live facts, saved draft, published version and state
         PUT  /teacher/weekend/reports/{rid}                {revision, sections, comment} save the teacher's edits
         POST /teacher/weekend/reports/{rid}/publish        {revision} release the saved draft to the linked parents
         GET  /teacher/weekend/reports/{rid}/report.docx    ?version=draft|published, A4 Word for printing
parent   GET  /parent/children/{sid}/weekend-briefs         (weekend_scoring_views) also returns the published reports

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
from changying.services.lesson_written import lesson_goals, suggest_knowledge

AI_FEATURE = "weekend_report"
PRACTICE_FEATURE = "weekend_practice"
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
    evidence: list[dict[str, Any]] | None = Field(default=None, max_length=200)


class PracticeGenerateBody(BaseModel):
    revision: int = Field(ge=1)
    groupKeys: list[str] = Field(default_factory=list, max_length=40)
    counts: dict[str, int] = Field(default_factory=dict)


class PracticeSaveBody(BaseModel):
    revision: int = Field(ge=1)
    groups: list[dict[str, Any]] = Field(min_length=1, max_length=40)


class PracticeAssignBody(BaseModel):
    revision: int = Field(ge=1)
    dueDate: str = Field(default="", max_length=20)


class PublishBody(BaseModel):
    revision: int = Field(ge=1)


def _normalize_practice_figure(raw: Any) -> dict[str, Any]:
    """Convert PNG uploaded_image figures into <=700k-char JPEG so student assignments render them."""
    if not isinstance(raw, dict):
        return {}
    if str(raw.get("type") or "").strip().lower() != "uploaded_image":
        return raw
    url = str(raw.get("data_url") or "")
    if url.startswith("data:image/jpeg;base64,") and len(url) <= 700_000:
        return raw
    if not url.startswith("data:image/png;base64,"):
        return {}
    try:
        import base64
        import io
        from PIL import Image
        raw_bytes = base64.b64decode(url.split(",", 1)[1], validate=True)
        with Image.open(io.BytesIO(raw_bytes)) as im:
            rgb = im.convert("RGB")
            for quality in (92, 82, 70):
                buf = io.BytesIO()
                rgb.save(buf, format="JPEG", quality=quality, subsampling=0, optimize=True)
                out_url = "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode("ascii")
                if len(out_url) <= 700_000:
                    return {"type": "uploaded_image", "data_url": out_url, "alt": str(raw.get("alt") or "题目插图")[:80]}
    except Exception:
        return {}
    return {}


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


def live_practice(implementation: Any, db: Any, practice: dict[str, Any] | None, student_id: int) -> dict[str, Any]:
    """Practice with the live state of each assigned homework, read from the original submissions."""
    practice = dict(practice or {})
    assignments = []
    for a in practice.get("assignments") or []:
        sub = db.scalar(select(implementation.Submission).where(implementation.Submission.assignment_id == a["assignmentId"],
                                                                implementation.Submission.student_id == student_id).limit(1))
        assignments.append({**a, "state": "graded" if sub else "assigned", "correct": sub.correct if sub else None,
                            "total": sub.total if sub else None,
                            "submittedAt": wr.local_dt(implementation, sub.submitted_at).strftime("%Y-%m-%d %H:%M") if sub else ""})
    practice["assignments"] = assignments
    if assignments and practice.get("state") == "assigned" and all(a["state"] == "graded" for a in assignments):
        practice["state"] = "graded"
    elif not assignments and practice.get("groups") and practice.get("state") != "assigning":
        practice["state"] = "review"
    return practice


def published_reports(implementation: Any, db: Any, school_id: int, student_id: int) -> list[dict[str, Any]]:
    """Parent-safe published versions only; drafts and teacher-only data never leave here."""
    t = register_report_table(implementation)
    out = []
    for r in db.execute(select(t).where(t.c.school_id == school_id, t.c.student_id == student_id, t.c.published_json.isnot(None))
                        .order_by(t.c.report_date.desc(), t.c.id.desc()).limit(60)):
        body = json.loads(r.published_json)
        facts = json.loads(r.published_facts_json or "[]")
        out.append({"id": r.id, "date": r.report_date, "subjects": [f["subject"] for f in facts], "facts": facts,
                    "sections": body["sections"], "comment": body.get("comment", ""), "titles": wr.SECTION_TITLES, "glance": body.get("glance", []),
                    "version": int(r.published_version), "publishedAt": wr.local_dt(implementation, r.published_at).strftime("%Y-%m-%d %H:%M"),
                    "sessionIds": [int(x) for x in r.session_key.split(",")],
                    "practice": wr.practice_view(live_practice(implementation, db, json.loads(r.draft_json).get("practice"), student_id), "parent")})
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
        row = db.execute(select(sessions).where(sessions.c.id == sid, sessions.c.school_id == u.school_id, sessions.c.teacher_id == u.id).with_for_update()).first()
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

    def with_compare(db: Any, u: Any, r: Any, parts: list[dict[str, Any]], evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """The report's glance, each lesson compared with the pupil's own previous published lesson of that subject."""
        out = wr.glance(parts, evidence)
        ids = {p["sessionId"] for p in parts}
        earlier = db.execute(select(reports.c.published_facts_json).where(
            reports.c.school_id == u.school_id, reports.c.student_id == r.student_id, reports.c.id != r.id,
            reports.c.published_json.isnot(None), reports.c.report_date <= r.report_date)
            .order_by(reports.c.report_date.desc(), reports.c.id.desc()).limit(20)).all()
        for g, part in zip(out, parts):
            for row in earlier:
                before = next((f for f in json.loads(row.published_facts_json or "[]")
                               if f.get("subject") == part["subject"] and f.get("sessionId") not in ids), None)
                if before is not None:
                    g["compare"] = wr.compare_text(before, wr.parent_facts(part))
                    break
        return out

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
        draft["evidence"] = draft.get("evidence") or wr.evidence_items(parts)
        draft["practice"] = live_practice(implementation, db, draft.get("practice"), int(r.student_id))
        return {"id": r.id, "studentId": int(r.student_id), "studentName": parts[0]["name"], "date": r.report_date, "sessionIds": ids,
                "practiceGroups": wr.practice_groups(draft["evidence"]), "practiceLabels": wr.PRACTICE_LABEL,
                "parentPractice": wr.practice_view(draft["practice"], "parent"),
                "state": state, "stateLabel": STATE_LABEL[state], "facts": parts, "parentFacts": [wr.parent_facts(p) for p in parts],
                "draft": {**draft, "revision": int(r.draft_revision), "savedAt": wr.local_dt(implementation, r.draft_saved_at).strftime("%Y-%m-%d %H:%M"),
                          "factsChanged": r.draft_hash != live,
                          "unpublishedEdits": r.published_revision is None or int(r.published_revision) != int(r.draft_revision)},
                "glance": with_compare(db, u, r, parts, draft["evidence"]),
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
        # 考点 / 课后题 marks of the written questions, editable here; they live on the lesson template (习题审核).
        marks = [{"no": q["no"], "templateId": q["templateId"], "knowledge": q["knowledge"], "afterClass": q["afterClass"],
                  "suggestedKnowledge": suggest_knowledge(q["full"])} for q in facts["questions"] if q["kind"] == "written" and q.get("templateId")]
        return {**{k: facts[k] for k in ("sessionId", "title", "status", "date", "subject", "lessonTitle", "unit", "coreTarget", "className", "settled", "cutoff")},
                "summary": wr.class_summary(facts), "students": students, "statusLabels": wr.STATUS_LABEL,
                "lessonId": int(row.lesson_id), "goals": lesson_goals(facts["coreTarget"]), "marks": marks}

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

    def sources_for(db: Any, u: Any, parts: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {}
        for p in parts:
            out.update(wr.source_questions(wr.session_facts(implementation, db, my_session(db, u, p["sessionId"]))))
        return out

    def course_figures_for(db: Any, u: Any, parts: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        """Collect normalized figures from TeachingQuestion.figure_json and Stage-4 courseware stepFigures[0]."""
        from changying.web.weekend_courseware import items_of, register_courseware_table
        by_stem: dict[str, dict[str, Any]] = {}
        TQ = implementation.TeachingQuestion
        cw_table = register_courseware_table(implementation)
        for p in parts:
            s = my_session(db, u, p["sessionId"])
            for tq in db.scalars(select(TQ).where(TQ.lesson_id == s.lesson_id, TQ.school_id == u.school_id)).all():
                try:
                    fig = _normalize_practice_figure(json.loads(getattr(tq, "figure_json", "") or "{}"))
                except Exception:
                    fig = {}
                if fig:
                    by_stem[wr._norm(tq.stem)] = fig
            cw_row = db.execute(select(cw_table).where(cw_table.c.lesson_id == s.lesson_id, cw_table.c.school_id == u.school_id)).first()
            if cw_row is not None:
                for it in items_of(cw_row):
                    if int(it.get("stage") or 0) != 4:
                        continue
                    prm = it.get("approved") or it.get("params") or {}
                    sfs = prm.get("stepFigures") or []
                    cand = sfs[0] if sfs else (prm.get("figure") or {})
                    fig = _normalize_practice_figure(cand)
                    key_text = wr._norm(it.get("pageText") or prm.get("problem") or "")
                    if fig and key_text and key_text not in by_stem:
                        by_stem[key_text] = fig
        return by_stem

    def enrich_practice_figure(raw: dict[str, Any], group: dict[str, Any], sources: dict[str, dict[str, Any]], course_figs: dict[str, dict[str, Any]]) -> dict[str, Any]:
        if group.get("subject") != "数学":
            return raw
        item = dict(raw)
        existing = _normalize_practice_figure(item.get("figure") or {})
        if existing:
            item["figure"] = existing
            return item
        from changying.web.reinforcement_quality import infer_reinforcement_figure
        inferred = infer_reinforcement_figure({
            "subject": "数学",
            "knowledge": item.get("knowledge") or group.get("knowledge") or "",
            "text": item.get("text") or "",
        })
        if inferred:
            item["figure"] = inferred
            return item
        for e in group.get("items") or []:
            src_key = str(e.get("key") or "").split(":", 1)[-1]
            src_full = wr._norm((sources.get(src_key) or {}).get("full") or "")
            if not src_full:
                continue
            for stem_norm, fig in course_figs.items():
                if stem_norm == src_full or (len(stem_norm) >= 12 and (stem_norm in src_full or src_full in stem_norm)):
                    item["figure"] = fig
                    return item
        return item

    def ai_allowed(db: Any, u: Any) -> bool:
        cfg = implementation.ai_config_for(db, u.school_id, False)
        return bool(cfg and cfg.enabled and cfg.allow_student_data)

    def study_hints(db: Any, u: Any, student_id: int, groups: list[dict[str, Any]]) -> list[str]:
        """Where else the product can help with this lesson's weak points: the pupil's published knowledge map
        (a 3—5 question quick check of the same point) and his after-school AI help record. Never raises."""
        from changying.services import knowledge_maps as km
        from changying.services.homework_knowledge import match_knowledge
        from changying.services.homework_knowledge_flags import knowledge_flags
        from changying.web.knowledge_map_views import knowledge_map_enabled, register_knowledge_map_table
        topics = [g["knowledge"] for g in groups if g.get("knowledge")]
        if not topics:
            return []
        lines: list[str] = []
        try:
            pupil = db.get(implementation.User, student_id)
            maps = register_knowledge_map_table(implementation)
            row = None
            if knowledge_map_enabled() and pupil is not None and pupil.grade is not None:
                row = db.execute(select(maps).where(maps.c.school_id == u.school_id, maps.c.grade == int(pupil.grade),
                                                    maps.c.published_json.isnot(None)).order_by(maps.c.published_at.desc())).first()
            if row is not None:
                m = json.loads(row.published_json)
                nodes = [n for n in m["nodes"] if km.assessed(m, n)]
                for t in topics:
                    hit = match_knowledge(t, [(n["key"], n["name"]) for n in nodes])
                    if hit:
                        lines.append(f"订正后，在“我的知识地图”里做「{hit[0]} {hit[1]}」的 3～5 题小测，看看是不是真的会了（只算第一次作答）。")
            open_flags = [f["knowledge"] for f in knowledge_flags(implementation, db, int(u.school_id), int(student_id))["flags"] if f["state"] == "open"]
            for t in topics:
                if open_flags and match_knowledge(t, [("", k) for k in open_flags]):
                    lines.append(f"「{t}」孩子晚托写作业时也请 AI 讲过，还没巩固，这周请重点练。")
        except Exception:  # noqa: BLE001 - extra hints must never stop a report
            db.rollback()
            return []
        return list(dict.fromkeys(lines))[:4]

    def generated(db: Any, u: Any, parts: list[dict[str, Any]], use_ai: bool,
                  previous: list[dict[str, Any]] | None = None) -> tuple[list[dict[str, str]], list[dict[str, Any]], str]:
        evidence = wr.evidence_items(parts, previous)
        source = "template"
        if use_ai:
            try:
                if not ai_allowed(db, u):
                    source = "ai_not_allowed"
                else:
                    sids = tuple(dict.fromkeys(int(p["studentId"]) for p in parts if p.get("studentId")))
                    data = implementation._ai_json(implementation._ai_call(
                        db, u, AI_FEATURE, wr.suggestion_prompt(parts, evidence, sources_for(db, u, parts)), timeout=45, student_ids=sids))
                    wr.apply_suggestions(evidence, data)
                    source = "ai"
            except Exception:  # noqa: BLE001 - the factual template is always usable without AI
                evidence, source = wr.evidence_items(parts, previous), "ai_failed"
        sections = []
        for p in parts:
            sec = wr.draft_section(p, evidence)
            extra = study_hints(db, u, int(p["studentId"]), wr.weak_groups([e for e in evidence if e["sessionId"] == p["sessionId"]]))
            if extra:
                lines = sec["homework"].split("\n")
                sec["homework"] = "\n".join(lines[:-1] + extra + lines[-1:])      # before the closing line for parents
            sections.append(sec)
        return sections, evidence, source

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
        old = json.loads(existing.draft_json) if existing is not None else {}
        sections, evidence, source = generated(db, u, parts, b.useAi, old.get("evidence"))
        # The AI call may commit usage accounting and release the session locks.
        for session_id in sorted(b.sessionIds):
            my_session(db, u, session_id)
        now = datetime.utcnow()
        if existing is None:
            body = {"sections": [{**s, "sessionId": p["sessionId"]} for s, p in zip(sections, parts)], "comment": "", "evidence": evidence}
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
        # Regenerating replaces only the system-written sections; the teacher's observation, comment,
        # confirmed knowledge points and the targeted practice stay.
        kept = {int(s.get("sessionId", 0)): s.get("observation", "") for s in old.get("sections", [])}
        body = {**old, "sections": [{**s, "sessionId": p["sessionId"], "observation": kept.get(p["sessionId"], "")} for s, p in zip(sections, parts)],
                "comment": old.get("comment", ""), "evidence": evidence}
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

    @router.get("/teacher/weekend/reports/{rid}/practice/{aid}/answers")
    def practice_answers(rid: int, aid: int, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        """Read this report pupil's recorded results; never regrade against mutable question-bank content."""
        need(u, "teacher")
        r = report_row(db, u, rid)
        practice = (json.loads(r.draft_json).get("practice") or {})
        if not any(a.get("assignmentId") == aid for a in practice.get("assignments") or []):
            raise HTTPException(404, "该作业不属于这份报告的针对性练习")
        assignment, _ = implementation._teacher_assignment_student(db, u, aid, int(r.student_id))
        sub = db.scalar(select(implementation.Submission).where(
            implementation.Submission.school_id == u.school_id,
            implementation.Submission.assignment_id == aid,
            implementation.Submission.student_id == r.student_id
        ).order_by(implementation.Submission.id.desc()).limit(1))
        paper = db.scalar(select(implementation.Paper).where(
            implementation.Paper.id == assignment.paper_id, implementation.Paper.school_id == u.school_id))
        def read_list(raw: str) -> list:
            try:
                value = json.loads(raw or "[]")
                return value if isinstance(value, list) else []
            except (ValueError, TypeError):
                return []
        recorded = {a["question_id"]: a for a in read_list(sub.answers_json if sub else "[]")
                    if isinstance(a, dict) and isinstance(a.get("question_id"), int)}
        ids = list(dict.fromkeys([i for i in read_list(paper.question_ids_json if paper else "[]") if isinstance(i, int)] + list(recorded)))
        questions = {q.id: q for q in db.scalars(select(implementation.Question).where(
            implementation.Question.school_id == u.school_id, implementation.Question.id.in_(ids))).all()} if ids else {}
        items = []
        for qid in ids:
            q, answer = questions.get(qid), recorded.get(qid, {})
            selected = answer.get("selected_index")
            choice = isinstance(selected, int) and not isinstance(selected, bool) and 0 <= selected < 26
            items.append({"questionId": qid, "text": q.text if q else "题目已不可用",
                          "options": read_list(q.options_json) if q else [],
                          "knowledge": q.knowledge if q else "", "questionAvailable": q is not None,
                          "studentAnswer": (chr(65 + selected) + ".（记录的选项序号）") if choice else str(answer.get("text_answer") or ""),
                          "correct": answer.get("correct") if isinstance(answer.get("correct"), bool) else None})
        return {"assignmentId": aid, "studentId": int(r.student_id), "state": "submitted" if sub else "assigned",
                "correct": sub.correct if sub else None, "total": sub.total if sub else None,
                "helpStatus": "unknown", "items": items,
                "questionNotice": "题干、选项和考点为当前题库内容，提交时版本未保存；对错沿用提交记录，不重新判分。帮助情况未知，不能据此判断独立完成或已经掌握。"}

    @router.put("/teacher/weekend/reports/{rid}")
    def save_report(rid: int, b: SaveBody, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "teacher")
        r = report_row(db, u, rid)
        parts, _ = report_parts(db, u, int(r.student_id), [int(x) for x in r.session_key.split(",")])
        try:
            sections = wr.clean_sections(b.sections, parts)
        except ValueError as e:
            raise HTTPException(400, str(e))
        old = json.loads(r.draft_json)
        body = {**old, "sections": sections, "comment": b.comment.replace("\r\n", "\n").strip()}
        if b.evidence is not None:
            body["evidence"] = wr.apply_teacher_evidence(old.get("evidence") or wr.evidence_items(parts), b.evidence)
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
            published_json=json.dumps({"sections": draft["sections"], "comment": draft.get("comment", ""),
                                       "glance": with_compare(db, u, r, parts, draft.get("evidence") or wr.evidence_items(parts))}, ensure_ascii=False),
            published_facts_json=json.dumps([wr.parent_facts(p) for p in parts], ensure_ascii=False),
            published_hash=wr.fingerprint(parts), published_revision=b.revision, published_version=int(r.published_version) + 1,
            published_at=datetime.utcnow()))
        if changed.rowcount != 1:
            db.rollback()
            raise HTTPException(409, "草稿已更新，请先核对最新内容再发布")
        db.commit()
        return describe(db, u, report_row(db, u, rid))

    def save_draft(db: Any, rid: int, revision: int, body: dict[str, Any], message: str) -> None:
        changed = db.execute(update(reports).where(reports.c.id == rid, reports.c.draft_revision == revision).values(
            draft_json=json.dumps(body, ensure_ascii=False), draft_revision=revision + 1, draft_saved_at=datetime.utcnow()))
        if changed.rowcount != 1:
            db.rollback()
            raise HTTPException(409, message)
        db.commit()

    def practice_context(db: Any, u: Any, r: Any, revision: int, retry: bool = False) -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, Any]]]:
        if int(r.draft_revision) != revision:
            raise HTTPException(409, "报告已在别处更新，请刷新核对后再操作练习")
        parts, _ = report_parts(db, u, int(r.student_id), [int(x) for x in r.session_key.split(",")])
        draft = json.loads(r.draft_json)
        state = (draft.get("practice") or {}).get("state")
        if state in ("assigning", "assigned") or (state == "partial" and not retry):
            raise HTTPException(409, "针对性练习已布置，不能再修改；如需调整请在作业中处理")
        return parts, draft, draft.get("evidence") or wr.evidence_items(parts)

    @router.post("/teacher/weekend/reports/{rid}/practice/generate")
    def generate_practice(rid: int, b: PracticeGenerateBody, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        """New variants of this pupil's own wrong and partly right answers, for the teacher to review. Assigns nothing."""
        need(u, "teacher")
        r = report_row(db, u, rid)
        parts, draft, evidence = practice_context(db, u, r, b.revision)
        groups = wr.practice_groups(evidence, b.counts)
        if not groups:
            raise HTTPException(400, "这份报告没有需订正或部分正确的题，不需要生成针对性练习")
        targets = [g for g in groups if not b.groupKeys or g["key"] in b.groupKeys]
        if not targets:
            raise HTTPException(400, "请选择要生成的薄弱点")
        if not ai_allowed(db, u):
            raise HTTPException(400, "学校未开启 AI 或未允许发送学生学习数据，无法自动出新题；已有报告和题目未改动，可手动添加题目")
        sources = sources_for(db, u, parts)
        course_figs = course_figures_for(db, u, parts)
        stu = db.get(implementation.User, int(r.student_id))
        grade = int(getattr(stu, "grade", 0) or 5)
        try:
            data = implementation._ai_json(implementation._ai_call(db, u, PRACTICE_FEATURE, wr.practice_prompt(targets, sources, grade), timeout=90, student_ids=(int(r.student_id),)))
            returned = {str(g.get("key")): g for g in (data.get("groups") or []) if isinstance(g, dict)} if isinstance(data, dict) else {}
        except Exception as e:  # noqa: BLE001 - nothing is saved; the existing report and questions stay
            detail = getattr(e, "detail", "") or "AI 服务不可用"
            raise HTTPException(502, f"生成失败：{detail}。已有报告和题目未改动，请稍后重试或手动添加题目")
        old_groups = {g["key"]: g for g in (draft.get("practice") or {}).get("groups") or []}
        problems, made = [], 0
        new_groups = []
        for g in groups:
            entry = {k: g[k] for k in ("key", "sessionId", "subject", "topic", "knowledge", "count", "basis")}
            entry["sourceNos"] = [e["no"] for e in g["items"]]
            entry["questions"] = list(old_groups.get(g["key"], {}).get("questions") or [])
            if g in targets:
                valid, reasons = [], []
                for raw in (returned.get(g["key"]) or {}).get("questions") or []:
                    try:
                        enriched = enrich_practice_figure(raw, g, sources, course_figs) if isinstance(raw, dict) else raw
                        q = wr.clean_question(enriched, g, sources, implementation._sanitize_figure)
                    except ValueError as err:
                        reasons.append(str(err))
                        continue
                    if all(wr._norm(q["text"]) != wr._norm(x["text"]) for x in valid):
                        valid.append(q)
                valid = valid[: g["count"]]
                if valid:
                    entry["questions"], made = valid, made + len(valid)
                    if len(valid) < g["count"]:
                        problems.append(f"{g['topic']}：只得到 {len(valid)} 道合格新题（{'；'.join(dict.fromkeys(reasons)) or 'AI 返回不足'}）")
                else:
                    problems.append(f"{g['topic']}：生成失败（{'；'.join(dict.fromkeys(reasons)) or 'AI 没有返回这个薄弱点的题'}），保留原有题目")
            new_groups.append(entry)
        if not made:
            raise HTTPException(502, "生成失败：" + "；".join(problems) + "。已有报告和题目未改动")
        draft["practice"] = {"state": "review", "groups": new_groups, "generatedAt": wr.local_dt(implementation, datetime.utcnow()).strftime("%Y-%m-%d %H:%M"),
                             "assignments": (draft.get("practice") or {}).get("assignments") or []}
        draft["evidence"] = evidence
        save_draft(db, rid, b.revision, draft, "报告已在别处更新，请刷新核对后再生成")
        implementation.audit(db, u, "weekend.report.practice.generate", f"report={rid}:student={r.student_id}:questions={made}")
        db.commit()
        return {"report": describe(db, u, report_row(db, u, rid)), "problems": problems}

    @router.put("/teacher/weekend/reports/{rid}/practice")
    def save_practice(rid: int, b: PracticeSaveBody, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        """Teacher edits or deletes reviewed variants; the same rules as generated questions apply."""
        need(u, "teacher")
        r = report_row(db, u, rid)
        parts, draft, evidence = practice_context(db, u, r, b.revision)
        sources = sources_for(db, u, parts)
        current = {g["key"]: g for g in (draft.get("practice") or {}).get("groups") or []}
        weak = {g["key"]: g for g in wr.practice_groups(evidence)}
        out = []
        for edit in b.groups:
            key = str(edit.get("key") or "")
            if key not in weak:
                raise HTTPException(400, "练习题对应的薄弱点已不存在，请刷新后重试")
            g = weak[key]
            questions = []
            for i, raw in enumerate(edit.get("questions") or [], 1):
                try:
                    normalized = {**raw, "figure": _normalize_practice_figure(raw.get("figure") or {})} if isinstance(raw, dict) else raw
                    questions.append(wr.clean_question(normalized, g, sources, implementation._sanitize_figure))
                except ValueError as err:
                    raise HTTPException(400, f"{g['topic']} 第{i}题：{err}")
            base = current.get(key) or {k: g[k] for k in ("key", "sessionId", "subject", "topic", "knowledge", "count", "basis")}
            out.append({**base, "sourceNos": [e["no"] for e in g["items"]], "questions": questions[:5]})
        draft["practice"] = {**(draft.get("practice") or {}), "state": "review", "groups": out}
        save_draft(db, rid, b.revision, draft, "报告已在别处更新，本次修改未保存；请刷新核对")
        return describe(db, u, report_row(db, u, rid))

    @router.post("/teacher/weekend/reports/{rid}/practice/assign")
    def assign_practice(rid: int, b: PracticeAssignBody, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        """After review, assign through the existing targeted-practice homework, only to this pupil, once."""
        need(u, "teacher")
        r = report_row(db, u, rid)
        parts, draft, evidence = practice_context(db, u, r, b.revision, retry=True)
        practice = draft.get("practice") or {}
        groups = [g for g in practice.get("groups") or [] if g.get("questions")]
        if not groups:
            raise HTTPException(400, "还没有审核过的练习题，请先生成或添加题目")
        # Mark first under the revision check, so a second click or another tab cannot assign twice.
        practice["state"] = "assigning"
        draft["practice"] = practice
        save_draft(db, rid, b.revision, draft, "练习已在布置或报告已更新，请刷新查看，避免重复布置")
        stu = db.get(implementation.User, int(r.student_id))
        cls = implementation.current_class_for(db, stu.id, u.school_id)
        grade = int(stu.grade or (cls.grade if cls else 5) or 5)
        textbook = {"数学": "人教版", "语文": "统编版（人民教育出版社）"}
        done = {a["subject"] for a in practice.get("assignments") or []}
        assigned, error = list(practice.get("assignments") or []), ""
        for subject in dict.fromkeys(g["subject"] for g in groups):
            if subject in done:
                continue
            mine = [q for g in groups if g["subject"] == subject for q in g["questions"]]
            unit = next((p["unit"] for p in parts if p["subject"] == subject), "")
            title = f"{stu.name} · {r.report_date} {subject}周末课针对性练习"
            body = implementation.AIReinforcementAssignBody(
                questions=[{"grade": grade, "subject": subject, "textbook": textbook.get(subject, ""), "semester": "上册", "unit": unit,
                            "knowledge": q["knowledge"], "text": q["text"], "options": q["options"], "correct_index": q["correct_index"],
                            "explanation": q["explanation"], "question_type": q["question_type"], "answer": q["answer"],
                            "accepted_answers": q["accepted_answers"], "figure": _normalize_practice_figure(q.get("figure") or {})} for q in mine],
                title=title, due_date=b.dueDate.strip(), wrong_ids=[],
                instructions="根据周末课错题生成的针对性练习，请独立完成后提交。")
            try:
                res = implementation.teacher_reinforcement_assign(int(r.student_id), body, u, db)
            except Exception as e:  # noqa: BLE001 - record what was assigned; never leave the report locked
                db.rollback()
                error = f"{subject}：{getattr(e, 'detail', '') or '布置失败'}"
                break
            assigned.append({"subject": subject, "assignmentId": int(res["assignment"]["id"]), "title": title,
                             "dueDate": res["assignment"].get("due_date") or res["assignment"].get("dueDate") or b.dueDate,
                             "questionCount": len(mine)})
        fresh = report_row(db, u, rid)
        draft = json.loads(fresh.draft_json)
        all_subjects = set(g["subject"] for g in groups)
        draft["practice"] = {**practice, "assignments": assigned,
                             "state": "assigned" if {a["subject"] for a in assigned} >= all_subjects else ("partial" if assigned else "review"),
                             "assignedAt": wr.local_dt(implementation, datetime.utcnow()).strftime("%Y-%m-%d %H:%M") if assigned else ""}
        save_draft(db, rid, int(fresh.draft_revision), draft, "布置结果保存冲突，请刷新查看")
        if error:
            raise HTTPException(409, f"布置未全部完成（{error}）；已布置的科目不会重复布置，请处理后重试")
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
                                "comment": body.get("comment", ""), "titles": titles, "stateLabel": label, "practice": d["parentPractice"]})
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


