"""应试专项（第 1 期）：考试目标、模拟卷、失分点.

teacher  GET  /teacher/exam-goals                                   my exam goals
         POST /teacher/exam-goals                                   {mapId, classId, title, examDate, unitKeys}
         GET  /teacher/exam-goals/{gid}                             goal, scope and its mock papers
         POST /teacher/exam-goals/{gid}/mock                        {count, timeLimit, dueDate} one mock paper for the class
         GET  /teacher/exam-goals/{gid}/papers/{pid}/analysis       per pupil score and the points that lost the most
page     /v1/exam-prep

Built on the published knowledge map: the exam covers some of its units and the mock paper is drawn from the
points' reviewed questions (and the bank questions named by the points). The mock is an ordinary class
assignment, so pupils do it in their usual homework list and it is graded by the existing engine. Behind the
``KNOWLEDGE_MAP`` flag like the map itself.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from sqlalchemy import Column, DateTime, Integer, String, Table, Text, desc, insert, select

from changying.services import exam_prep as ep
from changying.services import knowledge_maps as km
from changying.web.knowledge_map_views import NO_CACHE, knowledge_map_enabled, register_knowledge_map_table


class GoalBody(BaseModel):
    mapId: int
    classId: int
    title: str = Field(min_length=1, max_length=60)
    examDate: str = Field(max_length=10)
    unitKeys: list[str] = Field(min_length=1, max_length=20)


class MockBody(BaseModel):
    count: int = Field(default=20, ge=ep.MOCK_MIN, le=ep.MOCK_MAX)
    timeLimit: int = Field(default=60, ge=10, le=120)
    dueDate: str | None = Field(default=None, max_length=10)


DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def register_exam_prep_tables(implementation: Any) -> tuple[Table, Table]:
    md = implementation.Base.metadata
    if "exam_goals" not in md.tables:
        Table("exam_goals", md,
              Column("id", Integer, primary_key=True),
              Column("school_id", Integer, nullable=False, index=True),
              Column("teacher_id", Integer, nullable=False, index=True),
              Column("map_id", Integer, nullable=False),
              Column("class_id", Integer, nullable=False, index=True),
              Column("title", String(60), nullable=False),
              Column("exam_date", String(10), nullable=False),
              Column("unit_keys_json", Text, nullable=False),
              Column("created_at", DateTime, nullable=False))
    if "exam_goal_papers" not in md.tables:
        Table("exam_goal_papers", md,
              Column("id", Integer, primary_key=True),
              Column("school_id", Integer, nullable=False, index=True),
              Column("goal_id", Integer, nullable=False, index=True),
              Column("assignment_id", Integer, nullable=False, index=True),
              Column("kind", String(10), nullable=False),               # mock (later: retest)
              Column("plan_json", Text, nullable=False),                # [[point key, question id], ...] in paper order
              Column("time_limit_min", Integer, nullable=False),
              Column("created_at", DateTime, nullable=False))
    return md.tables["exam_goals"], md.tables["exam_goal_papers"]


def install_exam_prep_views(implementation: Any) -> APIRouter:
    app = implementation.app
    if getattr(app.state, "exam_prep_installed", False):
        return app.state.exam_prep_router
    goals, papers = register_exam_prep_tables(implementation)
    maps = register_knowledge_map_table(implementation)
    I = implementation
    current_user, get_db, need = I.current_user, I.get_db, I.need
    router = APIRouter()

    def teacher(u: Any) -> None:
        if not knowledge_map_enabled():
            raise HTTPException(404, "Not Found")
        need(u, "teacher")

    def own_class(db: Any, u: Any, cid: int) -> Any:
        cls = db.scalar(select(I.SchoolClass).where(I.SchoolClass.id == cid, I.SchoolClass.school_id == u.school_id,
                                                    I.SchoolClass.teacher_id == u.id))
        if cls is None:
            raise HTTPException(404, "没有找到这个班级")
        return cls

    def published(db: Any, u: Any, mid: int) -> tuple[Any, dict[str, Any]]:
        row = db.execute(select(maps).where(maps.c.id == mid, maps.c.school_id == u.school_id)).first()
        if row is None:
            raise HTTPException(404, "没有找到这份知识地图")
        if row.published_json is None:
            raise HTTPException(409, "知识地图还没有发布，发布后才能做应试专项")
        return row, json.loads(row.published_json)

    def my_goal(db: Any, u: Any, gid: int) -> Any:
        g = db.execute(select(goals).where(goals.c.id == gid, goals.c.school_id == u.school_id,
                                           goals.c.teacher_id == u.id)).first()
        if g is None:
            raise HTTPException(404, "没有找到这个考试目标")
        return g

    def days_left(exam_date: str) -> int:
        today = datetime.now(I.SCHOOL_TZ).date()
        return (datetime.strptime(exam_date, "%Y-%m-%d").date() - today).days

    def handed_in(db: Any, u: Any, aid: int) -> dict[int, dict[int, bool]]:
        """Each pupil's last hand-in for the paper: question id -> correct."""
        out: dict[int, dict[int, bool]] = {}
        for sid, raw in db.execute(select(I.Submission.student_id, I.Submission.answers_json).where(
                I.Submission.school_id == u.school_id, I.Submission.assignment_id == aid).order_by(I.Submission.submitted_at, I.Submission.id)):
            try:
                rows = json.loads(raw or "[]")
            except ValueError:
                continue
            out[sid] = {int(a["question_id"]): a["correct"] for a in rows if isinstance(a, dict)
                        and str(a.get("question_id", "")).isdigit() and isinstance(a.get("correct"), bool)}
        return out

    def goal_json(db: Any, u: Any, g: Any, detail: bool = False) -> dict[str, Any]:
        cls = db.get(I.SchoolClass, g.class_id)
        out: dict[str, Any] = {"id": g.id, "title": g.title, "examDate": g.exam_date, "daysLeft": days_left(g.exam_date),
                               "classId": g.class_id, "className": cls.name if cls else "", "mapId": g.map_id,
                               "unitKeys": json.loads(g.unit_keys_json)}
        rows = db.execute(select(papers).where(papers.c.goal_id == g.id, papers.c.school_id == u.school_id)
                          .order_by(desc(papers.c.id))).all()
        out["papers"] = []
        for p in rows:
            a = db.get(I.Assignment, p.assignment_id)
            out["papers"].append({"id": p.id, "kind": p.kind, "assignmentId": p.assignment_id, "title": a.title if a else "",
                                  "dueDate": a.due_date if a else "", "questionCount": len(json.loads(p.plan_json)),
                                  "timeLimit": p.time_limit_min, "handedIn": len(handed_in(db, u, p.assignment_id)),
                                  "createdAt": p.created_at.isoformat(timespec="minutes")})
        if detail:
            row, m = published(db, u, g.map_id)
            keys = set(out["unitKeys"])
            out["units"] = [{"key": x["key"], "name": x["name"]} for x in m["units"] if x["key"] in keys]
            out["points"] = [{"key": n["key"], "name": n["name"], "unit": n["unit"]} for n in ep.scope_nodes(m, keys)]
            out["mapTitle"] = row.title
        return out

    def pools(db: Any, u: Any, row: Any, nodes: list[dict[str, Any]]) -> dict[str, list[tuple[int, str]]]:
        """Usable questions per point: its reviewed questions with their level, then bank questions named by it (medium)."""
        ids = {int(q) for n in nodes for q in n["levels"]}
        names = {b for n in nodes for b in n["bankKeys"]}
        Q = I.Question
        rows = list(db.scalars(select(Q).where(Q.school_id == u.school_id, Q.id.in_(list(ids))))) if ids else []
        if names:
            rows += list(db.scalars(select(Q).where(Q.school_id == u.school_id, Q.grade == row.grade, Q.subject == row.subject,
                                                    Q.knowledge.in_(list(names))).order_by(Q.id).limit(600)))
        usable = {q.id: q for q in rows if I.question_type_of(q) in I.AUTO_GRADED_QUESTION_TYPES
                  and (not I.question_figure(q) or I.question_figure(q).get("type") in km.SHOWN_FIGURES)}
        out: dict[str, list[tuple[int, str]]] = {}
        for n in nodes:
            got = [(int(q), lv) for q, lv in n["levels"].items() if int(q) in usable]
            have = {q for q, _ in got}
            got += [(q.id, "medium") for q in usable.values() if q.knowledge in n["bankKeys"] and q.id not in have]
            out[n["key"]] = got
        return out

    @router.get("/v1/exam-prep", include_in_schema=False)
    def page():
        if not knowledge_map_enabled():
            raise HTTPException(404, "Not Found")
        from changying.web.exam_prep_pages import exam_prep_page_html
        return HTMLResponse(exam_prep_page_html(), headers=NO_CACHE)

    @router.get("/teacher/exam-goals")
    def list_goals(u: Any = Depends(current_user), db: Any = Depends(get_db)):
        teacher(u)
        rows = db.execute(select(goals).where(goals.c.school_id == u.school_id, goals.c.teacher_id == u.id)
                          .order_by(desc(goals.c.id))).all()
        classes = db.scalars(select(I.SchoolClass).where(I.SchoolClass.school_id == u.school_id, I.SchoolClass.teacher_id == u.id)
                             .order_by(I.SchoolClass.id)).all()
        found = db.execute(select(maps.c.id, maps.c.title, maps.c.published_json).where(maps.c.school_id == u.school_id)
                           .order_by(maps.c.id)).all()
        return {"items": [goal_json(db, u, g) for g in rows],
                "classes": [{"id": c.id, "name": c.name, "grade": c.grade} for c in classes],
                "maps": [{"id": r.id, "title": r.title, "units": [{"key": x["key"], "name": x["name"]} for x in json.loads(r.published_json)["units"]]}
                         for r in found if r.published_json]}

    @router.post("/teacher/exam-goals")
    def create_goal(b: GoalBody, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        teacher(u)
        own_class(db, u, b.classId)
        _, m = published(db, u, b.mapId)
        if not DATE.match(b.examDate):
            raise HTTPException(400, "考试日期格式应为 2026-01-15")
        try:
            datetime.strptime(b.examDate, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(400, "考试日期不存在")
        keys = list(dict.fromkeys(b.unitKeys))
        known = {x["key"] for x in m["units"]}
        if any(k not in known for k in keys):
            raise HTTPException(400, "考试范围里有知识地图上没有的单元")
        if not ep.scope_nodes(m, keys):
            raise HTTPException(400, "所选单元里没有可以出题的知识点")
        gid = db.execute(insert(goals).values(school_id=u.school_id, teacher_id=u.id, map_id=b.mapId, class_id=b.classId,
                                               title=b.title.strip(), exam_date=b.examDate, unit_keys_json=json.dumps(keys),
                                               created_at=datetime.utcnow())).inserted_primary_key[0]
        I.audit(db, u, "exam_prep.goal.create", f"goal={gid}:class={b.classId}:map={b.mapId}:units={','.join(keys)}")
        db.commit()
        return goal_json(db, u, my_goal(db, u, gid), detail=True)

    @router.get("/teacher/exam-goals/{gid}")
    def get_goal(gid: int, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        teacher(u)
        return goal_json(db, u, my_goal(db, u, gid), detail=True)

    @router.post("/teacher/exam-goals/{gid}/mock")
    def make_mock(gid: int, b: MockBody, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        teacher(u)
        g = my_goal(db, u, gid)
        cls = own_class(db, u, g.class_id)
        row, m = published(db, u, g.map_id)
        nodes = ep.scope_nodes(m, json.loads(g.unit_keys_json))
        plan = ep.compose(nodes, pools(db, u, row, nodes), b.count)
        if len(plan) < ep.MOCK_MIN:
            raise HTTPException(409, f"考试范围里能用的题只有 {len(plan)} 道，至少要 {ep.MOCK_MIN} 道；请先在知识地图里给知识点补题")
        due = b.dueDate or (datetime.now(I.SCHOOL_TZ).date() + timedelta(days=3)).isoformat()
        if not DATE.match(due):
            raise HTTPException(400, "截止日期格式应为 2026-01-15")
        n = len(db.execute(select(papers.c.id).where(papers.c.goal_id == g.id)).all()) + 1
        title = f"{g.title} · 模拟卷 {n}"[:160]
        first = db.get(I.Question, plan[0][1])
        p = I.Paper(school_id=u.school_id, title=title, grade=row.grade, subject=row.subject, textbook=first.textbook or "",
                    unit="应试专项", question_ids_json=json.dumps([q for _, q in plan]), teacher_id=u.id)
        db.add(p)
        db.flush()
        a = I.Assignment(school_id=u.school_id, title=title, class_id=cls.id, paper_id=p.id, due_date=due)
        db.add(a)
        db.flush()
        db.add(I.AssignmentSubmissionSetting(school_id=u.school_id, assignment_id=a.id, mode="quiz",
                                             instructions=f"{g.title}模拟卷：共 {len(plan)} 题，建议限时 {b.timeLimit} 分钟，一次做完，不翻书、不问人。"))
        kids = db.scalars(select(I.ClassStudent.student_id).join(I.User, I.User.id == I.ClassStudent.student_id).where(
            I.ClassStudent.class_id == cls.id, I.User.school_id == u.school_id, I.User.role == "student", I.User.active == True)).all()  # noqa: E712
        for sid in kids:
            I.ensure_recipient(db, a, sid, "exam_prep")
        pid = db.execute(insert(papers).values(school_id=u.school_id, goal_id=g.id, assignment_id=a.id, kind="mock",
                                                plan_json=json.dumps(plan), time_limit_min=b.timeLimit,
                                                created_at=datetime.utcnow())).inserted_primary_key[0]
        I.audit(db, u, "exam_prep.mock.create", f"goal={g.id}:paper={pid}:assignment={a.id}:questions={len(plan)}:recipients={len(kids)}")
        db.commit()
        return {"id": pid, "assignmentId": a.id, "title": title, "questionCount": len(plan), "recipients": len(kids),
                "short": len(plan) < b.count}

    @router.get("/teacher/exam-goals/{gid}/papers/{pid}/analysis")
    def analysis(gid: int, pid: int, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        teacher(u)
        g = my_goal(db, u, gid)
        p = db.execute(select(papers).where(papers.c.id == pid, papers.c.goal_id == g.id, papers.c.school_id == u.school_id)).first()
        if p is None:
            raise HTTPException(404, "没有找到这份模拟卷")
        _, m = published(db, u, g.map_id)
        plan = [(k, int(q)) for k, q in json.loads(p.plan_json)]
        names = {n["key"]: n["name"] for n in m["nodes"]}
        order = [n["key"] for n in m["nodes"]]
        done = handed_in(db, u, p.assignment_id)
        kids = db.scalars(select(I.User).join(I.ClassStudent, I.ClassStudent.student_id == I.User.id).where(
            I.ClassStudent.class_id == g.class_id, I.User.school_id == u.school_id, I.User.role == "student",
            I.User.active == True).order_by(I.User.name, I.User.id)).all()  # noqa: E712
        pupils = []
        for k in kids:
            if k.id not in done:
                pupils.append({"studentId": k.id, "name": k.name, "handedIn": False})
                continue
            per = ep.losses(plan, done[k.id])
            pupils.append({"studentId": k.id, "name": k.name, "handedIn": True, "score": ep.score(plan, done[k.id]),
                           "focus": [{"key": key, "name": names.get(key, key), "lost": per[key]["lost"], "asked": per[key]["asked"]}
                                     for key in ep.top_losses(per, order)]})
        total = ep.class_points(plan, [done[k.id] for k in kids if k.id in done])
        points = sorted(({"key": key, "name": names.get(key, key), "lost": v["lost"], "asked": v["asked"],
                          "rate": round(100 * v["lost"] / v["asked"]) if v["asked"] else 0} for key, v in total.items()),
                        key=lambda x: (-x["rate"], order.index(x["key"]) if x["key"] in order else 0))
        return {"paper": {"id": p.id, "questionCount": len(plan), "timeLimit": p.time_limit_min}, "pupils": pupils, "points": points,
                "handedIn": sum(1 for x in pupils if x["handedIn"]), "classSize": len(pupils)}

    app.include_router(router)
    app.state.exam_prep_installed = True
    app.state.exam_prep_router = router
    return router


__all__ = ["install_exam_prep_views", "register_exam_prep_tables"]
