"""应试专项：考试目标、模拟卷、失分点、专项练习、再测对比、限时作答、家长提分报告.

teacher  GET  /teacher/exam-goals                                   my exam goals (+ classes, maps, sample papers)
         POST /teacher/exam-goals                                   {mapId, classId, title, examDate, unitKeys}
         GET  /teacher/exam-goals/{gid}                             goal, scope, countdown advice and its papers
         POST /teacher/exam-goals/{gid}/mock                        {count, timeLimit, dueDate, samplePaperId} a mock paper
         GET  /teacher/exam-goals/{gid}/papers/{pid}/analysis       per pupil: marks, time used, top lost points, drill,
                                                                    and for a retest the change on those points
         POST /teacher/exam-goals/{gid}/papers/{pid}/drill          {perPoint, dueDate} practice on each pupil's lost points
         POST /teacher/exam-goals/{gid}/papers/{pid}/retest         {timeLimit, dueDate} same points, fresh questions
         GET  /teacher/exam-goals/{gid}/trend                       each pupil's marks paper by paper
         POST /teacher/exam-goals/{gid}/papers/{pid}/reports        draft a parent report for every pupil who handed in
         PUT  /teacher/exam-reports/{rid}                           {note} the teacher's words
         POST /teacher/exam-reports/{rid}/publish                   parents see the published copy
student  GET  /student/exam-papers                                  my mock and retest papers
         POST /student/exam-papers/{aid}/start                      start the clock (first time only)
parent   GET  /parent/children/{sid}/exam-reports                   published reports for my child
pages    /v1/exam-prep (teacher)  /v1/exam-paper (pupil, timed)  /v1/exam-report (parent)

Built on the published knowledge map: the exam covers some of its units and papers are drawn from the points'
reviewed questions (and the bank questions named by the points). Papers and practice are ordinary assignments,
graded by the existing engine. Marks follow the question type (TYPE_POINTS). The time limit is shown as a countdown
and the time used is recorded; handing in late is allowed and reported, nothing is cut off. Pupils are only compared
with themselves. Behind the ``KNOWLEDGE_MAP`` flag like the map itself.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from changying.services.exam_prep_evidence import EVIDENCE_DISCLAIMER, collect_exam_prep_evidence
from sqlalchemy import Column, DateTime, Integer, String, Table, Text, UniqueConstraint, desc, insert, select, update

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
    samplePaperId: int | None = None


class DrillBody(BaseModel):
    perPoint: int = Field(default=4, ge=1, le=6)
    dueDate: str | None = Field(default=None, max_length=10)


class RetestBody(BaseModel):
    timeLimit: int = Field(default=60, ge=10, le=120)
    dueDate: str | None = Field(default=None, max_length=10)


class NoteBody(BaseModel):
    note: str = Field(default="", max_length=600)


DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def register_exam_prep_tables(implementation: Any) -> dict[str, Table]:
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
              Column("kind", String(10), nullable=False),               # mock | retest (a retest follows the mock before it)
              Column("plan_json", Text, nullable=False),                # [[point key, question id], ...] in paper order
              Column("time_limit_min", Integer, nullable=False),
              Column("created_at", DateTime, nullable=False))
    if "exam_goal_drills" not in md.tables:
        Table("exam_goal_drills", md,
              Column("id", Integer, primary_key=True),
              Column("school_id", Integer, nullable=False, index=True),
              Column("goal_id", Integer, nullable=False, index=True),
              Column("paper_id", Integer, nullable=False, index=True),   # the paper whose lost points it practises
              Column("student_id", Integer, nullable=False, index=True),
              Column("assignment_id", Integer, nullable=False),
              Column("plan_json", Text, nullable=False),
              Column("created_at", DateTime, nullable=False),
              UniqueConstraint("paper_id", "student_id", name="uq_exam_goal_drills_pupil"))
    if "exam_attempts" not in md.tables:
        Table("exam_attempts", md,
              Column("id", Integer, primary_key=True),
              Column("school_id", Integer, nullable=False, index=True),
              Column("assignment_id", Integer, nullable=False, index=True),
              Column("student_id", Integer, nullable=False, index=True),
              Column("started_at", DateTime, nullable=False),
              UniqueConstraint("assignment_id", "student_id", name="uq_exam_attempts_pupil"))
    if "exam_reports" not in md.tables:
        Table("exam_reports", md,
              Column("id", Integer, primary_key=True),
              Column("school_id", Integer, nullable=False, index=True),
              Column("goal_id", Integer, nullable=False, index=True),
              Column("paper_id", Integer, nullable=False, index=True),
              Column("student_id", Integer, nullable=False, index=True),
              Column("draft_json", Text, nullable=False),
              Column("note", Text, nullable=False),
              Column("published_json", Text, nullable=True),            # what the parents see
              Column("published_at", DateTime, nullable=True),
              Column("updated_at", DateTime, nullable=False),
              UniqueConstraint("paper_id", "student_id", name="uq_exam_reports_pupil"))
    names = ("exam_goals", "exam_goal_papers", "exam_goal_drills", "exam_attempts", "exam_reports")
    return {n: md.tables[n] for n in names}


def install_exam_prep_views(implementation: Any) -> APIRouter:
    app = implementation.app
    if getattr(app.state, "exam_prep_installed", False):
        return app.state.exam_prep_router
    t = register_exam_prep_tables(implementation)
    goals, papers, drills, attempts, reports = (t["exam_goals"], t["exam_goal_papers"], t["exam_goal_drills"],
                                                t["exam_attempts"], t["exam_reports"])
    maps = register_knowledge_map_table(implementation)
    I = implementation
    current_user, get_db, need = I.current_user, I.get_db, I.need
    router = APIRouter()

    def enabled() -> None:
        if not knowledge_map_enabled():
            raise HTTPException(404, "Not Found")

    def teacher(u: Any) -> None:
        enabled()
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
            if row.template_key == "rj2026-g5-math-up":
                # Teachers may plan an exam from the platform's Grade 5 base;
                # this does not publish a pupil's knowledge map.
                return row, json.loads(row.map_json)
            raise HTTPException(409, "知识地图还没有发布，发布后才能做应试专项")
        return row, json.loads(row.published_json)

    def my_goal(db: Any, u: Any, gid: int) -> Any:
        g = db.execute(select(goals).where(goals.c.id == gid, goals.c.school_id == u.school_id,
                                           goals.c.teacher_id == u.id)).first()
        if g is None:
            raise HTTPException(404, "没有找到这个考试目标")
        return g

    def my_paper(db: Any, u: Any, g: Any, pid: int) -> Any:
        p = db.execute(select(papers).where(papers.c.id == pid, papers.c.goal_id == g.id, papers.c.school_id == u.school_id)).first()
        if p is None:
            raise HTTPException(404, "没有找到这份卷子")
        return p

    def plan_of(p: Any) -> list[tuple[str, int]]:
        return [(k, int(q)) for k, q in json.loads(p.plan_json)]

    def days_left(exam_date: str) -> int:
        today = datetime.now(I.SCHOOL_TZ).date()
        return (datetime.strptime(exam_date, "%Y-%m-%d").date() - today).days

    def due_date(value: str | None) -> str:
        due = value or (datetime.now(I.SCHOOL_TZ).date() + timedelta(days=3)).isoformat()
        if not DATE.match(due):
            raise HTTPException(400, "截止日期格式应为 2026-01-15")
        return due

    def submissions(db: Any, u: Any, aid: int) -> dict[int, Any]:
        """Each pupil's hand-in for an assignment (the last one)."""
        out: dict[int, Any] = {}
        for s in db.scalars(select(I.Submission).where(I.Submission.school_id == u.school_id, I.Submission.assignment_id == aid)
                            .order_by(I.Submission.submitted_at, I.Submission.id)):
            out[s.student_id] = s
        return out

    def correct_map(sub: Any) -> dict[int, bool]:
        try:
            rows = json.loads(sub.answers_json or "[]")
        except ValueError:
            return {}
        return {int(a["question_id"]): a["correct"] for a in rows if isinstance(a, dict)
                and str(a.get("question_id", "")).isdigit() and isinstance(a.get("correct"), bool)}

    def handed_in(db: Any, u: Any, aid: int) -> dict[int, dict[int, bool]]:
        return {sid: correct_map(s) for sid, s in submissions(db, u, aid).items()}

    def marks_of(db: Any, u: Any, qids: list[int]) -> dict[int, int]:
        rows = db.scalars(select(I.Question).where(I.Question.school_id == u.school_id, I.Question.id.in_(qids))) if qids else []
        return {q.id: ep.TYPE_POINTS.get(I.question_type_of(q), 1) for q in rows}

    def pupils_of(db: Any, u: Any, cid: int) -> list[Any]:
        return list(db.scalars(select(I.User).join(I.ClassStudent, I.ClassStudent.student_id == I.User.id).where(
            I.ClassStudent.class_id == cid, I.User.school_id == u.school_id, I.User.role == "student",
            I.User.active == True).order_by(I.User.name, I.User.id)))  # noqa: E712

    def earlier_mock(db: Any, g: Any, p: Any) -> Any:
        """The mock paper a retest follows: the latest mock sent before it."""
        return db.execute(select(papers).where(papers.c.goal_id == g.id, papers.c.kind == "mock", papers.c.id < p.id)
                          .order_by(desc(papers.c.id)).limit(1)).first()

    def used_questions(db: Any, g: Any) -> set[int]:
        used: set[int] = set()
        for row in db.execute(select(papers.c.plan_json).where(papers.c.goal_id == g.id)).all():
            used |= {int(q) for _, q in json.loads(row.plan_json)}
        for row in db.execute(select(drills.c.plan_json).where(drills.c.goal_id == g.id)).all():
            used |= {int(q) for _, q in json.loads(row.plan_json)}
        return used

    def seen_by(db: Any, u: Any, sid: int) -> set[int]:
        """Questions a pupil has answered anywhere, plus those in work still open for them."""
        seen: set[int] = set()
        for raw in db.scalars(select(I.Submission.answers_json).where(I.Submission.school_id == u.school_id, I.Submission.student_id == sid)):
            try:
                seen |= {int(a["question_id"]) for a in json.loads(raw or "[]") if isinstance(a, dict) and str(a.get("question_id", "")).isdigit()}
            except ValueError:
                continue
        kid = db.get(I.User, sid)
        return seen | (I.protected_question_ids_for_student(db, kid) if kid else set())

    def pools(db: Any, u: Any, row: Any, nodes: list[dict[str, Any]]) -> dict[str, list[tuple[int, str, str]]]:
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
        out: dict[str, list[tuple[int, str, str]]] = {}
        for n in nodes:
            got = [(int(q), lv, I.question_type_of(usable[int(q)])) for q, lv in n["levels"].items() if int(q) in usable]
            have = {q for q, _, _ in got}
            # The G5 pilot has no reviewed question pack, even after publication:
            # only questions explicitly assigned a level by the teacher may be sent.
            if row.template_key != "rj2026-g5-math-up":
                got += [(q.id, "medium", I.question_type_of(q)) for q in usable.values()
                        if q.knowledge in n["bankKeys"] and q.id not in have]
            out[n["key"]] = got
        return out

    def scope(db: Any, u: Any, g: Any) -> tuple[Any, dict[str, Any], list[dict[str, Any]]]:
        row, m = published(db, u, g.map_id)
        return row, m, ep.scope_nodes(m, json.loads(g.unit_keys_json))

    def send(db: Any, u: Any, row: Any, cls: Any, title: str, qids: list[int], due: str, instructions: str,
             students: list[int], source: str) -> Any:
        first = db.get(I.Question, qids[0])
        p = I.Paper(school_id=u.school_id, title=title[:160], grade=row.grade, subject=row.subject, textbook=first.textbook or "",
                    unit="应试专项", question_ids_json=json.dumps(qids), teacher_id=u.id)
        db.add(p)
        db.flush()
        a = I.Assignment(school_id=u.school_id, title=title[:160], class_id=cls.id, paper_id=p.id, due_date=due)
        db.add(a)
        db.flush()
        db.add(I.AssignmentSubmissionSetting(school_id=u.school_id, assignment_id=a.id, mode="quiz", instructions=instructions[:2000]))
        for sid in students:
            I.ensure_recipient(db, a, sid, source)
        return a

    def paper_json(db: Any, u: Any, p: Any) -> dict[str, Any]:
        a = db.get(I.Assignment, p.assignment_id)
        return {"id": p.id, "kind": p.kind, "kindName": "再测卷" if p.kind == "retest" else "模拟卷", "assignmentId": p.assignment_id,
                "title": a.title if a else "", "dueDate": a.due_date if a else "", "questionCount": len(json.loads(p.plan_json)),
                "timeLimit": p.time_limit_min, "handedIn": len(submissions(db, u, p.assignment_id)),
                "drills": len(db.execute(select(drills.c.id).where(drills.c.paper_id == p.id)).all()),
                "createdAt": I.school_local_iso(p.created_at)}

    def goal_json(db: Any, u: Any, g: Any, detail: bool = False) -> dict[str, Any]:
        cls = db.get(I.SchoolClass, g.class_id)
        days = days_left(g.exam_date)
        out: dict[str, Any] = {"id": g.id, "title": g.title, "examDate": g.exam_date, "daysLeft": days, "plan": ep.countdown(days),
                               "classId": g.class_id, "className": cls.name if cls else "", "mapId": g.map_id,
                               "unitKeys": json.loads(g.unit_keys_json)}
        rows = db.execute(select(papers).where(papers.c.goal_id == g.id, papers.c.school_id == u.school_id)
                          .order_by(desc(papers.c.id))).all()
        out["papers"] = [paper_json(db, u, p) for p in rows]
        if detail:
            row, m = published(db, u, g.map_id)
            keys = set(out["unitKeys"])
            out["units"] = [{"key": x["key"], "name": x["name"]} for x in m["units"] if x["key"] in keys]
            out["points"] = [{"key": n["key"], "name": n["name"], "unit": n["unit"]} for n in ep.scope_nodes(m, keys)]
            out["mapTitle"] = row.title
        return out

    def pupil_result(plan: list[tuple[str, int]], answers: dict[int, bool], marks: dict[int, int], names: dict[str, str],
                     order: list[str]) -> dict[str, Any]:
        per = ep.losses(plan, answers, marks)
        return {"score": ep.score(plan, answers, marks), "per": per,
                "focus": [{"key": k, "name": names.get(k, k), "lost": per[k]["lost"], "asked": per[k]["asked"],
                           "lostMarks": per[k]["lostMarks"], "marks": per[k]["marks"]} for k in ep.top_losses(per, order)]}

    def analyse(db: Any, u: Any, g: Any, p: Any) -> dict[str, Any]:
        _, m = published(db, u, g.map_id)
        plan = plan_of(p)
        marks = marks_of(db, u, [q for _, q in plan])
        names = {n["key"]: n["name"] for n in m["nodes"]}
        order = [n["key"] for n in m["nodes"]]
        subs = submissions(db, u, p.assignment_id)
        starts = {r.student_id: r.started_at for r in db.execute(select(attempts).where(attempts.c.assignment_id == p.assignment_id)).all()}
        base = earlier_mock(db, g, p) if p.kind == "retest" else None
        base_plan = plan_of(base) if base else []
        base_marks = marks_of(db, u, [q for _, q in base_plan]) if base else {}
        base_subs = submissions(db, u, base.assignment_id) if base else {}
        drill_rows = {r.student_id: r for r in db.execute(select(drills).where(drills.c.paper_id == p.id)).all()}
        class_pupils = pupils_of(db, u, g.class_id)
        ev_map = collect_exam_prep_evidence(db, I, u.school_id, g.map_id, m, [k.id for k in class_pupils])
        out = []
        for k in class_pupils:
            item: dict[str, Any] = {"studentId": k.id, "name": k.name, "handedIn": k.id in subs}
            d = drill_rows.get(k.id)
            if d:
                dsub = submissions(db, u, d.assignment_id).get(k.id)
                item["drill"] = {"assignmentId": d.assignment_id, "questionCount": len(json.loads(d.plan_json)),
                                 "handedIn": dsub is not None, "correct": dsub.correct if dsub else None}
            if k.id in subs:
                res = pupil_result(plan, correct_map(subs[k.id]), marks, names, order)
                item["score"], item["focus"] = res["score"], res["focus"]
                if res["focus"]:
                    stu_ev = ev_map.get(k.id, {})
                    item["pointEvidence"] = {f["key"]: stu_ev.get(f["key"], []) for f in res["focus"] if stu_ev.get(f["key"])}
                if k.id in starts:
                    used = int((subs[k.id].submitted_at - starts[k.id]).total_seconds() // 60)
                    item["minutes"] = max(used, 0)
                    item["overtime"] = max(used - p.time_limit_min, 0)
                if base and k.id in base_subs:
                    before = pupil_result(base_plan, correct_map(base_subs[k.id]), base_marks, names, order)
                    item["before"] = before["score"]
                    item["change"] = ep.compare(before["per"], res["per"], [f["key"] for f in before["focus"]])
                    for c in item["change"]:
                        c["name"] = names.get(c["key"], c["key"])
            out.append(item)
        total = ep.class_points(plan, [correct_map(subs[k]) for k in subs], marks)
        points = sorted(({"key": key, "name": names.get(key, key), "lost": v["lost"], "asked": v["asked"],
                          "rate": round(100 * v["lostMarks"] / v["marks"]) if v["marks"] else 0} for key, v in total.items()),
                        key=lambda x: (-x["rate"], order.index(x["key"]) if x["key"] in order else 0))
        return {"paper": {"id": p.id, "kind": p.kind, "questionCount": len(plan), "timeLimit": p.time_limit_min,
                          "totalMarks": sum(marks.values()), "basePaperId": base.id if base else None},
                "pupils": out, "points": points, "handedIn": sum(1 for x in out if x["handedIn"]), "classSize": len(out),
                "evidenceDisclaimer": EVIDENCE_DISCLAIMER}

    # ---------------------------------------------------------------- pages
    @router.get("/v1/exam-prep", include_in_schema=False)
    def page():
        enabled()
        from changying.web.exam_prep_pages import exam_prep_page_html
        return HTMLResponse(exam_prep_page_html(), headers=NO_CACHE)

    @router.get("/v1/exam-paper", include_in_schema=False)
    def pupil_page():
        enabled()
        from changying.web.exam_prep_pages import exam_paper_page_html
        return HTMLResponse(exam_paper_page_html(), headers=NO_CACHE)

    @router.get("/v1/exam-report", include_in_schema=False)
    def parent_page():
        enabled()
        from changying.web.exam_prep_pages import exam_report_page_html
        return HTMLResponse(exam_report_page_html(), headers=NO_CACHE)

    # ---------------------------------------------------------------- teacher
    @router.get("/teacher/exam-goals")
    def list_goals(u: Any = Depends(current_user), db: Any = Depends(get_db)):
        teacher(u)
        rows = db.execute(select(goals).where(goals.c.school_id == u.school_id, goals.c.teacher_id == u.id)
                          .order_by(desc(goals.c.id))).all()
        classes = db.scalars(select(I.SchoolClass).where(I.SchoolClass.school_id == u.school_id, I.SchoolClass.teacher_id == u.id)
                             .order_by(I.SchoolClass.id)).all()
        found = db.execute(select(maps.c.id, maps.c.title, maps.c.grade, maps.c.template_key,
                                  maps.c.published_json, maps.c.map_json).where(maps.c.school_id == u.school_id)
                           .order_by(maps.c.id)).all()
        samples = db.scalars(select(I.Paper).where(I.Paper.school_id == u.school_id, I.Paper.teacher_id == u.id,
                                                   I.Paper.unit != "应试专项").order_by(desc(I.Paper.id)).limit(30)).all()
        return {"items": [goal_json(db, u, g) for g in rows],
                "classes": [{"id": c.id, "name": c.name, "grade": c.grade} for c in classes],
                "maps": [{"id": r.id, "title": r.title, "grade": r.grade, "published": bool(r.published_json),
                          "units": [{"key": x["key"], "name": x["name"]}
                                    for x in json.loads(r.published_json or r.map_json)["units"]]}
                         for r in found if r.published_json or r.template_key == "rj2026-g5-math-up"],
                "baseline": None if any(r.grade == 5 for r in found) else {
                    "title": km.TEMPLATES["rj2026-g5-math-up"]["label"],
                    "units": [{"key": x["key"], "name": x["name"]}
                              for x in km.template("rj2026-g5-math-up")["units"]]},
                "samplePapers": [{"id": p.id, "title": p.title, "questionCount": len(json.loads(p.question_ids_json or "[]"))}
                                 for p in samples if json.loads(p.question_ids_json or "[]")]}

    @router.post("/teacher/exam-goals")
    def create_goal(b: GoalBody, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        teacher(u)
        cls = own_class(db, u, b.classId)
        row, m = published(db, u, b.mapId)
        if row.grade != cls.grade:
            raise HTTPException(400, "班级年级与知识地图不一致")
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
        row, _, nodes = scope(db, u, g)
        targets = None
        if b.samplePaperId is not None:
            sample = db.scalar(select(I.Paper).where(I.Paper.id == b.samplePaperId, I.Paper.school_id == u.school_id))
            if sample is None:
                raise HTTPException(404, "没有找到这份样卷")
            ids = [int(x) for x in json.loads(sample.question_ids_json or "[]")]
            kinds = [I.question_type_of(q) for q in db.scalars(select(I.Question).where(I.Question.school_id == u.school_id, I.Question.id.in_(ids)))] if ids else []
            targets = ep.type_targets(kinds, b.count) or None
        plan = ep.compose(nodes, pools(db, u, row, nodes), b.count, targets)
        if len(plan) < ep.MOCK_MIN:
            raise HTTPException(409, f"考试范围里能用的题只有 {len(plan)} 道，至少要 {ep.MOCK_MIN} 道；请先在知识地图里给知识点补题")
        due = due_date(b.dueDate)
        n = len(db.execute(select(papers.c.id).where(papers.c.goal_id == g.id, papers.c.kind == "mock")).all()) + 1
        kids = [k.id for k in pupils_of(db, u, cls.id)]
        a = send(db, u, row, cls, f"{g.title} · 模拟卷 {n}", [q for _, q in plan], due,
                 f"{g.title}模拟卷：共 {len(plan)} 题，限时 {b.timeLimit} 分钟。请从首页的“限时模拟卷”进入，开始后计时；一次做完，不翻书、不问人。",
                 kids, "exam_prep")
        pid = db.execute(insert(papers).values(school_id=u.school_id, goal_id=g.id, assignment_id=a.id, kind="mock",
                                                plan_json=json.dumps(plan), time_limit_min=b.timeLimit,
                                                created_at=datetime.utcnow())).inserted_primary_key[0]
        I.audit(db, u, "exam_prep.mock.create", f"goal={g.id}:paper={pid}:assignment={a.id}:questions={len(plan)}:recipients={len(kids)}")
        db.commit()
        return {"id": pid, "assignmentId": a.id, "title": a.title, "questionCount": len(plan), "recipients": len(kids),
                "short": len(plan) < b.count, "typeTargets": targets or {}}

    @router.get("/teacher/exam-goals/{gid}/papers/{pid}/analysis")
    def analysis(gid: int, pid: int, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        teacher(u)
        g = my_goal(db, u, gid)
        return analyse(db, u, g, my_paper(db, u, g, pid))

    @router.post("/teacher/exam-goals/{gid}/papers/{pid}/drill")
    def drill(gid: int, pid: int, b: DrillBody, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        teacher(u)
        g = my_goal(db, u, gid)
        p = my_paper(db, u, g, pid)
        cls = own_class(db, u, g.class_id)
        row, _, nodes = scope(db, u, g)
        pool = pools(db, u, row, nodes)
        result = analyse(db, u, g, p)
        due = due_date(b.dueDate)
        done = {r.student_id for r in db.execute(select(drills.c.student_id).where(drills.c.paper_id == p.id)).all()}
        paper_qids = {q for _, q in plan_of(p)}
        out = []
        for x in result["pupils"]:
            if not x["handedIn"]:
                out.append({"studentId": x["studentId"], "name": x["name"], "ok": False, "reason": "还没交卷"})
                continue
            if x["studentId"] in done:
                out.append({"studentId": x["studentId"], "name": x["name"], "ok": False, "reason": "已经布置过这份卷子的专项练习"})
                continue
            focus = [f["key"] for f in x["focus"]]
            if not focus:
                out.append({"studentId": x["studentId"], "name": x["name"], "ok": False, "reason": "全对，不需要专项练习"})
                continue
            picks = ep.drill_picks(focus, pool, paper_qids | seen_by(db, u, x["studentId"]), b.perPoint)
            if not picks:
                out.append({"studentId": x["studentId"], "name": x["name"], "ok": False, "reason": "这些知识点没有他没做过的题，请先在知识地图里补题"})
                continue
            names = "、".join(f["name"] for f in x["focus"])
            a = send(db, u, row, cls, f"{g.title} · 专项练习（{names}）", [q for _, q in picks], due,
                     f"针对模拟卷里失分最多的知识点：{names}。先做基础题，再做提高题；做完老师会再发一次再测。", [x["studentId"]], "exam_prep")
            db.execute(insert(drills).values(school_id=u.school_id, goal_id=g.id, paper_id=p.id, student_id=x["studentId"],
                                             assignment_id=a.id, plan_json=json.dumps(picks), created_at=datetime.utcnow()))
            I.audit(db, u, "exam_prep.drill.create", f"goal={g.id}:paper={p.id}:student={x['studentId']}:assignment={a.id}:questions={len(picks)}")
            out.append({"studentId": x["studentId"], "name": x["name"], "ok": True, "assignmentId": a.id, "questionCount": len(picks)})
        db.commit()
        return {"results": out}

    @router.post("/teacher/exam-goals/{gid}/papers/{pid}/retest")
    def retest(gid: int, pid: int, b: RetestBody, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        teacher(u)
        g = my_goal(db, u, gid)
        p = my_paper(db, u, g, pid)
        if p.kind != "mock":
            raise HTTPException(409, "再测要对着模拟卷出；请在模拟卷上点“发再测卷”")
        cls = own_class(db, u, g.class_id)
        row, _, nodes = scope(db, u, g)
        plan = ep.retest_plan(plan_of(p), pools(db, u, row, nodes), used_questions(db, g))
        if len(plan) < ep.MOCK_MIN:
            raise HTTPException(409, f"还没用过的题只有 {len(plan)} 道，至少要 {ep.MOCK_MIN} 道；请先在知识地图里给这些知识点补题")
        kids = [k.id for k in pupils_of(db, u, cls.id)]
        n = len(db.execute(select(papers.c.id).where(papers.c.goal_id == g.id, papers.c.kind == "retest")).all()) + 1
        a = send(db, u, row, cls, f"{g.title} · 再测卷 {n}", [q for _, q in plan], due_date(b.dueDate),
                 f"{g.title}再测卷：和模拟卷考同样的知识点，题目都是新的。共 {len(plan)} 题，限时 {b.timeLimit} 分钟，请从首页的“限时模拟卷”进入。",
                 kids, "exam_prep")
        rid = db.execute(insert(papers).values(school_id=u.school_id, goal_id=g.id, assignment_id=a.id, kind="retest",
                                                plan_json=json.dumps(plan), time_limit_min=b.timeLimit,
                                                created_at=datetime.utcnow())).inserted_primary_key[0]
        I.audit(db, u, "exam_prep.retest.create", f"goal={g.id}:paper={rid}:base={p.id}:assignment={a.id}:questions={len(plan)}")
        db.commit()
        return {"id": rid, "assignmentId": a.id, "title": a.title, "questionCount": len(plan), "recipients": len(kids),
                "short": len(plan) < len(plan_of(p))}

    @router.get("/teacher/exam-goals/{gid}/trend")
    def trend(gid: int, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        teacher(u)
        g = my_goal(db, u, gid)
        rows = db.execute(select(papers).where(papers.c.goal_id == g.id).order_by(papers.c.id)).all()
        heads, scores = [], {}
        for p in rows:
            plan = plan_of(p)
            marks = marks_of(db, u, [q for _, q in plan])
            a = db.get(I.Assignment, p.assignment_id)
            heads.append({"id": p.id, "title": a.title if a else "", "kind": p.kind})
            for sid, ans in handed_in(db, u, p.assignment_id).items():
                scores.setdefault(sid, {})[str(p.id)] = ep.score(plan, ans, marks)
        return {"papers": heads, "pupils": [{"studentId": k.id, "name": k.name, "scores": [scores.get(k.id, {}).get(str(h["id"])) for h in heads]}
                                            for k in pupils_of(db, u, g.class_id)]}

    def report_json(r: Any, name: str) -> dict[str, Any]:
        return {"id": r.id, "studentId": r.student_id, "name": name, "draft": json.loads(r.draft_json), "note": r.note,
                "published": r.published_json is not None, "publishedAt": I.school_local_iso(r.published_at) if r.published_at else None,
                "changedSincePublish": r.published_json is not None and json.loads(r.published_json) != {**json.loads(r.draft_json), "note": r.note}}

    @router.post("/teacher/exam-goals/{gid}/papers/{pid}/reports")
    def draft_reports(gid: int, pid: int, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        teacher(u)
        g = my_goal(db, u, gid)
        p = my_paper(db, u, g, pid)
        res = analyse(db, u, g, p)
        a = db.get(I.Assignment, p.assignment_id)
        plan = ep.countdown(days_left(g.exam_date))
        now = datetime.utcnow()
        out = []
        for x in res["pupils"]:
            if not x["handedIn"]:
                continue
            content = ep.report(x["name"], a.title if a else "", {"score": x["score"]},
                                {"score": x["before"]} if "before" in x else None, x["focus"], x.get("drill"), plan, g.title)
            if x.get("change"):
                content["change"] = [{"name": c["name"], "verdict": c["verdict"]} for c in x["change"]]
            old = db.execute(select(reports).where(reports.c.paper_id == p.id, reports.c.student_id == x["studentId"])).first()
            if old:
                db.execute(update(reports).where(reports.c.id == old.id).values(draft_json=json.dumps(content, ensure_ascii=False), updated_at=now))
            else:
                db.execute(insert(reports).values(school_id=u.school_id, goal_id=g.id, paper_id=p.id, student_id=x["studentId"],
                                                  draft_json=json.dumps(content, ensure_ascii=False), note="", updated_at=now))
        I.audit(db, u, "exam_prep.reports.draft", f"goal={g.id}:paper={p.id}")
        db.commit()
        names = {k.id: k.name for k in pupils_of(db, u, g.class_id)}
        for r in db.execute(select(reports).where(reports.c.paper_id == p.id).order_by(reports.c.id)).all():
            out.append(report_json(r, names.get(r.student_id, "")))
        return {"items": out}

    def my_report(db: Any, u: Any, rid: int) -> Any:
        r = db.execute(select(reports).where(reports.c.id == rid, reports.c.school_id == u.school_id)).first()
        if r is None:
            raise HTTPException(404, "没有找到这份报告")
        my_goal(db, u, r.goal_id)
        return r

    @router.put("/teacher/exam-reports/{rid}")
    def save_note(rid: int, b: NoteBody, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        teacher(u)
        r = my_report(db, u, rid)
        db.execute(update(reports).where(reports.c.id == r.id).values(note=b.note.strip(), updated_at=datetime.utcnow()))
        db.commit()
        r = my_report(db, u, rid)
        return report_json(r, db.get(I.User, r.student_id).name)

    @router.post("/teacher/exam-reports/{rid}/publish")
    def publish(rid: int, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        teacher(u)
        r = my_report(db, u, rid)
        snap = {**json.loads(r.draft_json), "note": r.note}
        db.execute(update(reports).where(reports.c.id == r.id).values(published_json=json.dumps(snap, ensure_ascii=False),
                                                                     published_at=datetime.utcnow()))
        I.audit(db, u, "exam_prep.report.publish", f"report={r.id}:student={r.student_id}")
        db.commit()
        r = my_report(db, u, rid)
        return report_json(r, db.get(I.User, r.student_id).name)

    # ---------------------------------------------------------------- pupil
    def pupil_papers(db: Any, u: Any) -> list[tuple[Any, Any]]:
        rows = db.execute(select(papers).join(I.AssignmentRecipient, I.AssignmentRecipient.assignment_id == papers.c.assignment_id).where(
            papers.c.school_id == u.school_id, I.AssignmentRecipient.student_id == u.id).order_by(desc(papers.c.id))).all()
        return [(p, db.get(I.Assignment, p.assignment_id)) for p in rows]

    @router.get("/student/exam-papers")
    def my_papers(u: Any = Depends(current_user), db: Any = Depends(get_db)):
        enabled()
        need(u, "student")
        out = []
        for p, a in pupil_papers(db, u):
            if a is None:
                continue
            sub = db.scalar(select(I.Submission).where(I.Submission.assignment_id == a.id, I.Submission.student_id == u.id).limit(1))
            st = db.execute(select(attempts.c.started_at).where(attempts.c.assignment_id == a.id, attempts.c.student_id == u.id)).first()
            out.append({"assignmentId": a.id, "paperId": a.paper_id, "title": a.title, "kind": p.kind, "dueDate": a.due_date,
                        "timeLimit": p.time_limit_min, "questionCount": len(json.loads(p.plan_json)),
                        "startedAt": st.started_at.isoformat() + "Z" if st else None, "handedIn": sub is not None,
                        "score": ep.score(plan_of(p), correct_map(sub), marks_of(db, u, [q for _, q in plan_of(p)])) if sub else None})
        return {"items": out, "now": datetime.utcnow().isoformat() + "Z"}

    @router.post("/student/exam-papers/{aid}/start")
    def start(aid: int, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        enabled()
        need(u, "student")
        mine = {a.id: p for p, a in pupil_papers(db, u) if a is not None}
        if aid not in mine:
            raise HTTPException(404, "没有找到这份卷子")
        if db.scalar(select(I.Submission.id).where(I.Submission.assignment_id == aid, I.Submission.student_id == u.id).limit(1)):
            raise HTTPException(409, "这份卷子已经交了")
        st = db.execute(select(attempts.c.started_at).where(attempts.c.assignment_id == aid, attempts.c.student_id == u.id)).first()
        if st is None:
            now = datetime.utcnow()
            db.execute(insert(attempts).values(school_id=u.school_id, assignment_id=aid, student_id=u.id, started_at=now))
            db.commit()
            started = now
        else:
            started = st.started_at
        return {"startedAt": started.isoformat() + "Z", "timeLimit": mine[aid].time_limit_min, "now": datetime.utcnow().isoformat() + "Z"}

    # ---------------------------------------------------------------- parent
    @router.get("/parent/children/{sid}/exam-reports")
    def child_reports(sid: int, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        enabled()
        need(u, "parent")
        if not db.scalar(select(I.ParentStudent.id).where(I.ParentStudent.parent_id == u.id, I.ParentStudent.student_id == sid)):
            raise HTTPException(404, "没有找到这个孩子")
        kid = db.get(I.User, sid)
        if kid is None or kid.school_id != u.school_id:
            raise HTTPException(404, "没有找到这个孩子")
        rows = db.execute(select(reports).where(reports.c.student_id == sid, reports.c.school_id == u.school_id,
                                                reports.c.published_json.is_not(None)).order_by(desc(reports.c.published_at))).all()
        return {"child": {"id": kid.id, "name": kid.name},
                "items": [{"id": r.id, "publishedAt": I.school_local_iso(r.published_at), **json.loads(r.published_json)} for r in rows]}

    app.include_router(router)
    app.state.exam_prep_installed = True
    app.state.exam_prep_router = router
    return router


__all__ = ["install_exam_prep_views", "register_exam_prep_tables"]
