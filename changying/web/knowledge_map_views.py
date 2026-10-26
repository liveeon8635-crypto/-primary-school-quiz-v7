"""知识地图（教师端）：维护单元、知识点、前置关系，并给每个知识点的题目分档.

teacher  GET  /v1/knowledge-map                                  page
         GET  /knowledge-map/config                              {enabled} (404 when the flag is off)
         GET  /teacher/knowledge-maps                            the school's maps and the templates not used yet
         POST /teacher/knowledge-maps                            {template} create a draft from a reviewed template
         GET  /teacher/knowledge-maps/{mid}                      draft + coverage per node + published state
         PUT  /teacher/knowledge-maps/{mid}                      {map, revision} save the draft (validated)
         GET  /teacher/knowledge-maps/{mid}/nodes/{key}/questions  questions of the bank matching the node
         PUT  /teacher/knowledge-maps/{mid}/nodes/{key}/levels   {levels, revision} question levels of one node
         POST /teacher/knowledge-maps/{mid}/publish              {revision} the draft becomes the published map
         GET  /teacher/knowledge-maps/{mid}/classes              the teacher's classes
         GET  /teacher/knowledge-maps/{mid}/classes/{cid}        mastery of every pupil of the class (published map)
         POST /teacher/knowledge-maps/{mid}/classes/{cid}/reinforce  {nodeKey, studentIds, count} one consolidation
                                                                    homework per pupil from the node's levelled questions

Everything sits behind the ``KNOWLEDGE_MAP`` environment flag (default off; 404 when off). One map per school,
grade, subject and term; teachers of the school share it. Students and diagnosis (later PRs) only read the
published copy, so editing the draft never changes what pupils see until the teacher publishes again.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from sqlalchemy import Column, DateTime, Integer, String, Table, Text, UniqueConstraint, func, insert, select, update

from changying.services import knowledge_maps as km

KNOWLEDGE_MAP_FLAG = "KNOWLEDGE_MAP"
NO_CACHE = {"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"}


def knowledge_map_enabled() -> bool:
    return os.getenv(KNOWLEDGE_MAP_FLAG, "").strip().lower() in {"1", "true", "yes", "on"}


class CreateBody(BaseModel):
    template: str = Field(max_length=40)


class SaveBody(BaseModel):
    map: dict[str, Any]
    revision: int = Field(ge=0)


class LevelsBody(BaseModel):
    levels: dict[str, str | None]
    revision: int = Field(ge=0)


class PublishBody(BaseModel):
    revision: int = Field(ge=0)


class ReinforceBody(BaseModel):
    nodeKey: str = Field(max_length=12)
    studentIds: list[int] = Field(max_length=60)
    count: int = Field(default=4, ge=1, le=10)
    dueDate: str | None = Field(default=None, max_length=20)


def register_knowledge_map_table(implementation: Any) -> Table:
    md = implementation.Base.metadata
    if "knowledge_maps" not in md.tables:
        Table("knowledge_maps", md,
              Column("id", Integer, primary_key=True),
              Column("school_id", Integer, nullable=False, index=True),
              Column("grade", Integer, nullable=False),
              Column("subject", String(30), nullable=False),
              Column("term", String(20), nullable=False),
              Column("textbook", String(80), nullable=False),
              Column("title", String(120), nullable=False),
              Column("template_key", String(40), nullable=False),
              Column("map_json", Text, nullable=False),                # the teacher's draft
              Column("revision", Integer, nullable=False),             # bumps on every save; stale saves get 409
              Column("published_json", Text, nullable=True),           # what diagnosis and students read
              Column("published_revision", Integer, nullable=True),
              Column("published_at", DateTime, nullable=True),
              Column("updated_by", Integer, nullable=False),
              Column("updated_at", DateTime, nullable=False),
              UniqueConstraint("school_id", "grade", "subject", "term", name="uq_knowledge_maps_school_term"))
    return md.tables["knowledge_maps"]


def install_knowledge_map_views(implementation: Any) -> APIRouter:
    app = implementation.app
    if getattr(app.state, "knowledge_map_installed", False):
        return app.state.knowledge_map_router
    t = register_knowledge_map_table(implementation)
    Question = implementation.Question
    current_user, get_db, need = implementation.current_user, implementation.get_db, implementation.need
    router = APIRouter()

    def require_enabled() -> None:
        if not knowledge_map_enabled():
            raise HTTPException(404, "Not Found")

    def teacher(u: Any) -> None:
        require_enabled()
        need(u, "teacher")

    def my_map(db: Any, u: Any, mid: int, lock: bool = False) -> Any:
        q = select(t).where(t.c.id == mid, t.c.school_id == u.school_id)
        row = db.execute(q.with_for_update() if lock else q).first()
        if row is None:
            raise HTTPException(404, "没有找到这份知识地图")
        return row

    def fresh(row: Any, revision: int) -> None:
        if int(row.revision) != int(revision):
            raise HTTPException(409, "知识地图已被其他老师修改，请刷新后再改")

    def cleaned(raw: Any) -> dict[str, Any]:
        try:
            return km.clean_map(raw)
        except ValueError as e:
            raise HTTPException(400, str(e))

    def bank(db: Any, row: Any, names: list[str]) -> list[Any]:
        if not names:
            return []
        return list(db.scalars(select(Question).where(Question.school_id == row.school_id, Question.grade == row.grade,
                                                      Question.subject == row.subject, Question.knowledge.in_(names))
                               .order_by(Question.id).limit(300)))

    def existing_ids(db: Any, row: Any, m: dict[str, Any]) -> set[int]:
        ids = {int(q) for n in m["nodes"] for q in n["levels"]}
        if not ids:
            return set()
        return set(db.scalars(select(Question.id).where(Question.school_id == row.school_id, Question.id.in_(ids))))

    def detail(db: Any, row: Any) -> dict[str, Any]:
        m = json.loads(row.map_json)
        alive = existing_ids(db, row, m)
        names = sorted({b for n in m["nodes"] for b in n["bankKeys"]})
        per_name = dict(db.execute(select(Question.knowledge, func.count(Question.id)).where(
            Question.school_id == row.school_id, Question.grade == row.grade, Question.subject == row.subject,
            Question.knowledge.in_(names)).group_by(Question.knowledge)).all()) if names else {}
        nodes = []
        for n in m["nodes"]:
            nodes.append({**n, "assessed": km.assessed(m, n), "coverage": km.coverage(n, alive),
                          "bankCount": sum(int(per_name.get(b, 0)) for b in n["bankKeys"]) if n["kind"] != "display" else 0})
        ready = {n["key"]: n["coverage"]["ready"] for n in nodes}
        return {"id": row.id, "title": row.title, "grade": row.grade, "subject": row.subject, "term": row.term, "textbook": row.textbook,
                "revision": int(row.revision), "map": {**m, "nodes": nodes}, "dependents": km.dependents(m),
                "summary": km.summary(m, ready), "unitKinds": km.UNIT_KINDS, "nodeKinds": km.NODE_KINDS, "levels": km.LEVELS,
                "minPerLevel": km.MIN_PER_LEVEL, "minPerNode": km.MIN_PER_NODE,
                "published": None if row.published_revision is None else {
                    "revision": int(row.published_revision), "upToDate": int(row.published_revision) == int(row.revision),
                    "at": row.published_at.replace(tzinfo=None).isoformat(timespec="minutes") if row.published_at else None},
                "updatedAt": row.updated_at.isoformat(timespec="minutes")}

    def save(db: Any, u: Any, row: Any, m: dict[str, Any]) -> None:
        db.execute(update(t).where(t.c.id == row.id).values(map_json=json.dumps(m, ensure_ascii=False), revision=int(row.revision) + 1,
                                                            updated_by=u.id, updated_at=datetime.utcnow()))
        db.commit()

    @router.get("/knowledge-map/config")
    def config():
        require_enabled()
        return {"enabled": True}

    @router.get("/v1/knowledge-map", include_in_schema=False)
    def page():
        require_enabled()
        from changying.web.knowledge_map_pages import knowledge_map_page_html
        return HTMLResponse(knowledge_map_page_html(), headers=NO_CACHE)

    @router.get("/teacher/knowledge-maps")
    def list_maps(u: Any = Depends(current_user), db: Any = Depends(get_db)):
        teacher(u)
        rows = db.execute(select(t).where(t.c.school_id == u.school_id).order_by(t.c.grade, t.c.subject, t.c.term)).all()
        used = {(r.grade, r.subject, r.term) for r in rows}
        return {"items": [{"id": r.id, "title": r.title, "revision": int(r.revision), "published": r.published_revision is not None,
                           "upToDate": r.published_revision is not None and int(r.published_revision) == int(r.revision)} for r in rows],
                "templates": [{"key": k, "label": v["label"]} for k, v in km.TEMPLATES.items()
                              if (v["grade"], v["subject"], v["term"]) not in used]}

    @router.post("/teacher/knowledge-maps")
    def create(b: CreateBody, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        teacher(u)
        if b.template not in km.TEMPLATES:
            raise HTTPException(400, "没有这个知识地图模板")
        meta = km.TEMPLATES[b.template]
        if db.execute(select(t.c.id).where(t.c.school_id == u.school_id, t.c.grade == meta["grade"], t.c.subject == meta["subject"],
                                           t.c.term == meta["term"])).first():
            raise HTTPException(409, "本校这个年级学期已经有知识地图了")
        m = km.clean_map(km.template(b.template))
        db.execute(insert(t).values(school_id=u.school_id, grade=meta["grade"], subject=meta["subject"], term=meta["term"],
                                    textbook=meta["textbook"], title=meta["label"], template_key=b.template,
                                    map_json=json.dumps(m, ensure_ascii=False), revision=0, updated_by=u.id, updated_at=datetime.utcnow()))
        db.commit()
        row = db.execute(select(t).where(t.c.school_id == u.school_id, t.c.grade == meta["grade"], t.c.subject == meta["subject"],
                                         t.c.term == meta["term"])).first()
        return detail(db, row)

    @router.get("/teacher/knowledge-maps/{mid}")
    def get_map(mid: int, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        teacher(u)
        return detail(db, my_map(db, u, mid))

    @router.put("/teacher/knowledge-maps/{mid}")
    def put_map(mid: int, b: SaveBody, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        teacher(u)
        row = my_map(db, u, mid, lock=True)
        fresh(row, b.revision)
        m = cleaned(b.map)
        # Question levels are only changed through the levels endpoint; a structure edit keeps them for kept nodes.
        old = {n["key"]: n["levels"] for n in json.loads(row.map_json)["nodes"]}
        for n in m["nodes"]:
            n["levels"] = old.get(n["key"], {}) if n["kind"] != "display" else {}
        save(db, u, row, m)
        return detail(db, my_map(db, u, mid))

    @router.get("/teacher/knowledge-maps/{mid}/nodes/{key}/questions")
    def node_questions(mid: int, key: str, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        teacher(u)
        row = my_map(db, u, mid)
        m = json.loads(row.map_json)
        node = next((n for n in m["nodes"] if n["key"] == key), None)
        if node is None or node["kind"] == "display":
            raise HTTPException(404, "没有找到这个知识点")
        found = {q.id: q for q in bank(db, row, node["bankKeys"])}
        # Questions already levelled stay listed even if their knowledge name was changed later.
        extra = [int(q) for q in node["levels"] if int(q) not in found]
        if extra:
            found.update({q.id: q for q in db.scalars(select(Question).where(Question.school_id == row.school_id, Question.id.in_(extra)))})
        items = [{"id": q.id, "text": q.text, "type": q.question_type or "single_choice", "knowledge": q.knowledge, "unit": q.unit,
                  "level": node["levels"].get(str(q.id))} for q in sorted(found.values(), key=lambda q: q.id)]
        return {"key": key, "name": node["name"], "bankKeys": node["bankKeys"], "items": items, "revision": int(row.revision)}

    @router.put("/teacher/knowledge-maps/{mid}/nodes/{key}/levels")
    def put_levels(mid: int, key: str, b: LevelsBody, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        teacher(u)
        row = my_map(db, u, mid, lock=True)
        fresh(row, b.revision)
        m = json.loads(row.map_json)
        node = next((n for n in m["nodes"] if n["key"] == key), None)
        if node is None or node["kind"] == "display":
            raise HTTPException(404, "没有找到这个知识点")
        ids = {int(q) for q in b.levels if str(q).isdigit()}
        if len(ids) != len(b.levels):
            raise HTTPException(400, "题目编号不对")
        owned = set(db.scalars(select(Question.id).where(Question.school_id == row.school_id, Question.id.in_(ids)))) if ids else set()
        if owned != ids:
            raise HTTPException(400, "只能给本校题库里的题目分档")
        for qid, level in b.levels.items():
            if level is None:
                node["levels"].pop(str(int(qid)), None)
            elif level in km.LEVELS:
                node["levels"][str(int(qid))] = level
            else:
                raise HTTPException(400, "难度档只能是基础、中等或提高")
        save(db, u, row, cleaned(m))
        return detail(db, my_map(db, u, mid))

    @router.post("/teacher/knowledge-maps/{mid}/publish")
    def publish(mid: int, b: PublishBody, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        teacher(u)
        row = my_map(db, u, mid, lock=True)
        fresh(row, b.revision)
        m = cleaned(json.loads(row.map_json))
        if not any(km.assessed(m, n) for n in m["nodes"]):
            raise HTTPException(400, "还没有标记为已学的单元，发布后无法诊断")
        db.execute(update(t).where(t.c.id == row.id).values(published_json=json.dumps(m, ensure_ascii=False), published_revision=int(row.revision),
                                                            published_at=datetime.utcnow()))
        db.commit()
        return detail(db, my_map(db, u, mid))

    @router.get("/teacher/knowledge-maps/{mid}/classes")
    def classes(mid: int, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        teacher(u)
        row = my_map(db, u, mid)
        SC = implementation.SchoolClass
        rows = db.scalars(select(SC).where(SC.school_id == u.school_id, SC.teacher_id == u.id).order_by(SC.name, SC.id)).all()
        return {"items": [{"id": c.id, "name": c.name, "grade": c.grade, "sameGrade": int(c.grade or 0) == int(row.grade),
                           "studentCount": len(pupils(db, u, c.id))} for c in rows]}

    def pupils(db: Any, u: Any, cid: int) -> list[Any]:
        User, CS = implementation.User, implementation.ClassStudent
        return list(db.scalars(select(User).join(CS, CS.student_id == User.id).where(
            CS.class_id == cid, User.school_id == u.school_id, User.role == "student", User.active == True)  # noqa: E712
            .order_by(User.name, User.id)))

    def answers_of(db: Any, u: Any, ids: list[int]) -> dict[int, list[Any]]:
        """Every pupil's submissions in order (oldest first), read in one query."""
        Submission = implementation.Submission
        answers: dict[int, list[Any]] = {i: [] for i in ids}
        if ids:
            for sid, raw in db.execute(select(Submission.student_id, Submission.answers_json).where(
                    Submission.school_id == u.school_id, Submission.student_id.in_(ids)).order_by(Submission.submitted_at, Submission.id)):
                try:
                    answers[sid].append(json.loads(raw or "[]"))
                except ValueError:
                    continue
        return answers

    def own_class(db: Any, u: Any, cid: int) -> Any:
        SC = implementation.SchoolClass
        cls = db.scalar(select(SC).where(SC.id == cid, SC.school_id == u.school_id, SC.teacher_id == u.id))
        if cls is None:
            raise HTTPException(404, "没有找到这个班级")
        return cls

    @router.get("/teacher/knowledge-maps/{mid}/classes/{cid}")
    def class_mastery(mid: int, cid: int, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        teacher(u)
        row = my_map(db, u, mid)
        cls = own_class(db, u, cid)
        if row.published_json is None:
            raise HTTPException(409, "知识地图还没有发布，发布后才能查看全班掌握情况")
        from changying.web.knowledge_map_student import register_knowledge_map_run_table
        runs = register_knowledge_map_run_table(implementation)
        m = json.loads(row.published_json)
        kids = pupils(db, u, cls.id)
        ids = [k.id for k in kids]
        answers = answers_of(db, u, ids)
        diag = {r.student_id: r for r in db.execute(select(runs).where(runs.c.map_id == row.id, runs.c.school_id == u.school_id,
                                                                         runs.c.student_id.in_(ids)))} if ids else {}
        students = []
        for k in kids:
            node_m, unit_m = km.mastery_view(m, km.first_attempts(answers[k.id]))
            r = diag.get(k.id)
            students.append({"id": k.id, "name": k.name, "nodes": node_m, "units": unit_m,
                             "diagnosis": {"status": "new"} if r is None else {"status": r.status, "count": len(json.loads(r.items_json)),
                                                                                 "correct": r.correct}})
        nodes = [{"key": n["key"], "unit": n["unit"], "name": n["name"]} for n in m["nodes"] if km.assessed(m, n)]
        tally = {}
        for n in nodes:
            c = {"weak": 0, "pass": 0, "fluent": 0, "insufficient": 0}
            for st in students:
                c[st["nodes"][n["key"]]["level"] or "insufficient"] += 1
            tally[n["key"]] = c
        return {"classId": cls.id, "className": cls.name, "title": row.title, "publishedRevision": int(row.published_revision),
                "units": [x for x in m["units"] if any(n["unit"] == x["key"] for n in nodes)], "nodes": nodes, "tally": tally,
                "students": students, "masteryLabels": km.MASTERY_LABELS, "confidenceLabels": km.CONFIDENCE_LABELS}

    @router.post("/teacher/knowledge-maps/{mid}/classes/{cid}/reinforce")
    def reinforce(mid: int, cid: int, b: ReinforceBody, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        teacher(u)
        row = my_map(db, u, mid)
        cls = own_class(db, u, cid)
        if row.published_json is None:
            raise HTTPException(409, "知识地图还没有发布")
        m = json.loads(row.published_json)
        node = next((n for n in m["nodes"] if n["key"] == b.nodeKey and km.assessed(m, n)), None)
        if node is None:
            raise HTTPException(404, "这个知识点现在不参加诊断，不能布置巩固")
        kids = {k.id: k for k in pupils(db, u, cls.id)}
        wanted = list(dict.fromkeys(b.studentIds))
        if not wanted or any(s not in kids for s in wanted):
            raise HTTPException(400, "只能给本班学生布置")
        I = implementation
        levelled = {int(q): lv for q, lv in node["levels"].items()}
        bank = {q.id: q for q in db.scalars(select(Question).where(Question.school_id == u.school_id, Question.id.in_(list(levelled))))} if levelled else {}
        usable = [q for q in bank.values() if I.question_type_of(q) in I.AUTO_GRADED_QUESTION_TYPES
                  and (not I.question_figure(q) or I.question_figure(q).get("type") == "uploaded_image")]
        title = f"知识地图巩固 · {node['name']}"[:160]
        answers = answers_of(db, u, wanted)
        order = {"basic": 0, "medium": 1, "hard": 2}
        results = []
        for sid in wanted:
            kid = kids[sid]
            open_one = db.scalar(select(I.Assignment.id).join(I.AssignmentRecipient, I.AssignmentRecipient.assignment_id == I.Assignment.id).where(
                I.Assignment.school_id == u.school_id, I.Assignment.title == title, I.AssignmentRecipient.student_id == sid,
                ~select(I.Submission.id).where(I.Submission.assignment_id == I.Assignment.id, I.Submission.student_id == sid).exists()).limit(1))
            if open_one:
                results.append({"studentId": sid, "name": kid.name, "ok": False, "reason": "已有未完成的这项巩固练习"})
                continue
            seen = set(km.first_attempts(answers[sid])) | I.protected_question_ids_for_student(db, kid)
            # Questions the pupil has never answered, easiest first: their answers count as first attempts.
            picks = sorted((q for q in usable if q.id not in seen), key=lambda q: (order[levelled[q.id]], q.id))[: b.count]
            if not picks:
                results.append({"studentId": sid, "name": kid.name, "ok": False, "reason": "没有这名学生没做过的题，请先给这个知识点补题"})
                continue
            p = I.Paper(school_id=u.school_id, title=title, grade=row.grade, subject=row.subject, textbook=picks[0].textbook or "",
                        unit=picks[0].unit or "", question_ids_json=json.dumps([q.id for q in picks]), teacher_id=u.id)
            db.add(p); db.flush()
            due = (b.dueDate or (datetime.now(I.SCHOOL_TZ).date() + timedelta(days=3)).isoformat())[:20]
            a = I.Assignment(school_id=u.school_id, title=title, class_id=cls.id, paper_id=p.id, due_date=due)
            db.add(a); db.flush()
            db.add(I.AssignmentSubmissionSetting(school_id=u.school_id, assignment_id=a.id, mode="quiz",
                                                 instructions=f"知识地图巩固：{node['name']}。认真完成，每道题都按第一次作答记入掌握情况。"))
            I.ensure_recipient(db, a, sid, "knowledge_map")
            I.audit(db, u, "knowledge_map.reinforce", f"map={row.id}:node={node['key']}:student={sid}:assignment={a.id}:questions={len(picks)}")
            results.append({"studentId": sid, "name": kid.name, "ok": True, "assignmentId": a.id, "questionCount": len(picks)})
        db.commit()
        return {"node": {"key": node["key"], "name": node["name"]}, "results": results}

    app.include_router(router)
    app.state.knowledge_map_installed = True
    app.state.knowledge_map_router = router
    return router


__all__ = ["install_knowledge_map_views", "knowledge_map_enabled", "register_knowledge_map_table"]
