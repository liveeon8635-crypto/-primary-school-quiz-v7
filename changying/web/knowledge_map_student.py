"""知识地图（学生端）：二维地图 + 12 题首次作答诊断.

student  GET  /v1/my-knowledge-map                         page
         GET  /student/knowledge-map                       published map of the pupil's grade, mastery per node, diagnosis state
         POST /student/knowledge-map/diagnosis             start (or resume) the 12-question diagnosis; questions without answers
         POST /student/knowledge-map/diagnosis/submit      {answers} graded by the existing engine, saved as a practice submission

Behind the ``KNOWLEDGE_MAP`` flag like the teacher side. Pupils only ever see the published map. Mastery uses the
first answer the pupil gave to each levelled question in any submission (homework, practice or this diagnosis), so
the diagnosis is one more piece of evidence in the same long-term record, not a separate score. Each pupil takes the
diagnosis once per map; the questions avoid unfinished formal homework and ones the pupil has already answered.
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy import Column, DateTime, Integer, String, Table, Text, UniqueConstraint, insert, select, update

from changying.services import knowledge_maps as km
from changying.web.knowledge_map_views import NO_CACHE, knowledge_map_enabled, register_knowledge_map_table

DIAGNOSIS_TITLE = "知识地图诊断"


class DiagnosisAnswer(BaseModel):
    question_id: int
    selected_index: int | None = None
    text_answer: str = Field(default="", max_length=500)


class DiagnosisBody(BaseModel):
    answers: list[DiagnosisAnswer]


def register_knowledge_map_run_table(implementation: Any) -> Table:
    md = implementation.Base.metadata
    if "knowledge_map_runs" not in md.tables:
        Table("knowledge_map_runs", md,
              Column("id", Integer, primary_key=True),
              Column("school_id", Integer, nullable=False, index=True),
              Column("map_id", Integer, nullable=False, index=True),
              Column("student_id", Integer, nullable=False, index=True),
              Column("map_revision", Integer, nullable=False),
              Column("items_json", Text, nullable=False),               # [[node key, question id], ...]
              Column("status", String(12), nullable=False),             # open | submitted
              Column("submission_id", Integer, nullable=True),
              Column("correct", Integer, nullable=True),
              Column("created_at", DateTime, nullable=False),
              Column("submitted_at", DateTime, nullable=True),
              UniqueConstraint("map_id", "student_id", name="uq_knowledge_map_runs_student"))
    return md.tables["knowledge_map_runs"]


def install_knowledge_map_student(implementation: Any) -> APIRouter:
    app = implementation.app
    if getattr(app.state, "knowledge_map_student_installed", False):
        return app.state.knowledge_map_student_router
    maps = register_knowledge_map_table(implementation)
    runs = register_knowledge_map_run_table(implementation)
    Question, Submission = implementation.Question, implementation.Submission
    current_user, get_db, need = implementation.current_user, implementation.get_db, implementation.need
    router = APIRouter()

    def pupil(u: Any) -> None:
        if not knowledge_map_enabled():
            raise HTTPException(404, "Not Found")
        need(u, "student")

    def published_map(db: Any, u: Any) -> Any:
        q = select(maps).where(maps.c.school_id == u.school_id, maps.c.published_json.is_not(None))
        rows = db.execute(q.order_by(maps.c.published_at.desc(), maps.c.id.desc())).all()
        if u.grade is not None:
            rows = [r for r in rows if int(r.grade) == int(u.grade)]
        elif len({int(r.grade) for r in rows}) > 1:
            rows = []
        if not rows:
            raise HTTPException(404, "老师还没有发布你的知识地图")
        return rows[0]

    def first_answers(db: Any, u: Any) -> dict[int, bool]:
        rows = db.scalars(select(Submission.answers_json).where(Submission.school_id == u.school_id, Submission.student_id == u.id)
                          .order_by(Submission.submitted_at, Submission.id))
        lists = []
        for raw in rows:
            try:
                lists.append(json.loads(raw or "[]"))
            except ValueError:
                continue
        return km.first_attempts(lists)

    def run_of(db: Any, u: Any, row: Any, lock: bool = False) -> Any:
        q = select(runs).where(runs.c.map_id == row.id, runs.c.student_id == u.id, runs.c.school_id == u.school_id)
        return db.execute(q.with_for_update() if lock else q).first()

    def usable_questions(db: Any, u: Any, m: dict[str, Any]) -> dict[int, Any]:
        ids = {int(q) for n in m["nodes"] if km.assessed(m, n) for q in n["levels"]}
        if not ids:
            return {}
        protected = implementation.protected_question_ids_for_student(db, u)
        out = {}
        for q in db.scalars(select(Question).where(Question.school_id == u.school_id, Question.id.in_(ids))):
            figure = implementation.question_figure(q)
            if q.id in protected or implementation.question_type_of(q) not in implementation.AUTO_GRADED_QUESTION_TYPES:
                continue
            if figure and figure.get("type") not in km.SHOWN_FIGURES:
                continue            # other drawn figures are drawn only by the classic app
            out[q.id] = q
        return out

    def public(q: Any) -> dict[str, Any]:
        d = implementation.qj_public(q)
        return {k: d[k] for k in ("id", "text", "options", "questionType", "figure")}

    def payload(db: Any, u: Any, row: Any) -> dict[str, Any]:
        m = json.loads(row.published_json)
        first = first_answers(db, u)
        units = {x["key"]: x for x in m["units"]}
        node_m, unit_m = km.mastery_view(m, first)
        nodes = [{"key": n["key"], "unit": n["unit"], "name": n["name"], "detail": n["detail"], "kind": n["kind"],
                  "prereqs": n["prereqs"], "learned": bool(units[n["unit"]]["learned"]), "assessed": n["key"] in node_m,
                  "mastery": node_m.get(n["key"])} for n in m["nodes"]]
        unit_rows = [{**x, "mastery": unit_m[x["key"]]} for x in m["units"]]
        r = run_of(db, u, row)
        diagnosis = {"status": "new"} if r is None else {"status": r.status, "count": len(json.loads(r.items_json)),
                                                           "correct": r.correct}
        return {"title": row.title, "units": unit_rows, "nodes": nodes, "unitKinds": km.UNIT_KINDS, "nodeKinds": km.NODE_KINDS,
                "masteryLabels": km.MASTERY_LABELS, "confidenceLabels": km.CONFIDENCE_LABELS, "diagnosis": diagnosis}

    @router.get("/v1/my-knowledge-map", include_in_schema=False)
    def page():
        if not knowledge_map_enabled():
            raise HTTPException(404, "Not Found")
        from changying.web.knowledge_map_pages import student_map_page_html
        return HTMLResponse(student_map_page_html(), headers=NO_CACHE)

    @router.get("/student/knowledge-map")
    def my_map(u: Any = Depends(current_user), db: Any = Depends(get_db)):
        pupil(u)
        return payload(db, u, published_map(db, u))

    @router.post("/student/knowledge-map/diagnosis")
    def start(u: Any = Depends(current_user), db: Any = Depends(get_db)):
        pupil(u)
        row = published_map(db, u)
        r = run_of(db, u, row)
        if r is not None and r.status == "submitted":
            raise HTTPException(409, "你已经完成过这次诊断了")
        if r is None:
            m = json.loads(row.published_json)
            usable = usable_questions(db, u, m)
            picked = km.pick_diagnosis(m, set(usable), set(first_answers(db, u)), int(u.id))
            if len(picked) < km.DIAGNOSIS_MIN:
                raise HTTPException(409, "老师还在准备诊断题目，请稍后再来")
            try:
                db.execute(insert(runs).values(school_id=u.school_id, map_id=row.id, student_id=u.id, map_revision=int(row.published_revision),
                                               items_json=json.dumps(picked), status="open", created_at=datetime.utcnow()))
                db.commit()
            except IntegrityError:                   # a second tab started at the same moment: use its run
                db.rollback()
            r = run_of(db, u, row)
        items = [(k, int(q)) for k, q in json.loads(r.items_json)]
        found = {q.id: q for q in db.scalars(select(Question).where(Question.school_id == u.school_id, Question.id.in_([q for _, q in items])))}
        questions = [public(found[q]) for _, q in items if q in found]
        return {"count": len(questions), "questions": questions}

    @router.post("/student/knowledge-map/diagnosis/submit")
    def submit(b: DiagnosisBody, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        pupil(u)
        row = published_map(db, u)
        r = run_of(db, u, row, lock=True)
        if r is None:
            raise HTTPException(404, "请先开始诊断")
        if r.status == "submitted":
            raise HTTPException(409, "你已经提交过这次诊断了")
        items = [(k, int(q)) for k, q in json.loads(r.items_json)]
        alive = set(db.scalars(select(Question.id).where(Question.school_id == u.school_id, Question.id.in_([q for _, q in items]))))
        allowed = [q for _, q in items if q in alive]
        answers = [implementation.AnswerItem(question_id=a.question_id, selected_index=a.selected_index, text_answer=a.text_answer)
                   for a in b.answers]
        normalized, correct, total, score = implementation.grade_answers(db, u, answers, allowed_question_ids=allowed, require_all=True)
        sub = implementation.save_sub(db, u, None, DIAGNOSIS_TITLE, normalized, correct, total, score)
        db.execute(update(runs).where(runs.c.id == r.id).values(status="submitted", submission_id=sub.id, correct=correct,
                                                                submitted_at=datetime.utcnow()))
        db.commit()
        ok = {int(a["question_id"]): a["correct"] for a in normalized}
        names = {n["key"]: n["name"] for n in json.loads(row.published_json)["nodes"]}
        per: dict[str, dict[str, Any]] = {}
        for key, q in items:
            if q in ok:
                x = per.setdefault(key, {"key": key, "name": names.get(key, key), "right": 0, "total": 0})
                x["total"] += 1
                x["right"] += 1 if ok[q] else 0
        return {"correct": correct, "total": total, "nodes": list(per.values()), "map": payload(db, u, row)}

    app.include_router(router)
    app.state.knowledge_map_student_installed = True
    app.state.knowledge_map_student_router = router
    return router


__all__ = ["install_knowledge_map_student", "register_knowledge_map_run_table"]
