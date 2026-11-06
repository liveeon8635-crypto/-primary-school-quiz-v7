"""周末课 强带弱、进步分、团队分 (阶段 3c).

teacher  GET  /teacher/weekend/sessions/{id}/peer-suggest     who could explain, who needs it (only the teacher sees this)
         POST /teacher/weekend/sessions/{id}/peer-help        {tutorId, tuteeId, questionId} -> AI writes a same-method follow-up question
         POST /teacher/weekend/peer-help/{pid}/result         {correct} when the follow-up is done on paper / AI failed
         GET  /teacher/weekend/sessions/{id}/settle-preview   the points this lesson would give, and why (writes nothing)
         POST /teacher/weekend/sessions/{id}/settle           write the points once (points ledger, category weekend_*)
student  GET  /student/weekend/followup                       my open follow-up question (if the teacher asked a classmate to explain)
         POST /student/weekend/followup                       {peerHelpId, selected}

archive  GET  /teacher/weekend/sessions/{id}/archive          one lesson: timeline, attendance, per-student results, peer help, points
         GET  /teacher/weekend/sessions/{id}/briefs           parent brief drafts (what a parent would read; no ranking)
         POST /teacher/weekend/sessions/{id}/briefs/publish   {texts?: {studentId: edited text}} release to the linked parents
         GET  /teacher/weekend/term-summary?subject=          per student across lessons: trend of completion / hint use, points
parent   GET  /parent/children/{sid}/weekend-briefs           published briefs of a linked child only

Rules are in changying/services/weekend_scoring.py (see docs/weekend-course/3-口径文档.md). Every award keeps its
inputs in ``basis_json`` so it can be recomputed and audited.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, Table, Text, UniqueConstraint, func, insert, select, update

from fastapi.responses import HTMLResponse

from changying.services.weekend_roster import current_student_session
from changying.services.weekend_scoring import (
    Answer, History, Student, class_post_rate, completion_bonus, completion_rate, hint_dependence, progress_points,
    team_points, tutor_points,
)

AI_FEATURE = "weekend_followup"
SOURCE = "classroom"          # counted by the existing points summaries; category tells the weekend kinds apart
CATEGORY = {"progress": "weekend_progress", "completion": "weekend_completion", "tutor": "weekend_tutor", "team": "weekend_team"}
REASON = {"progress": "周末课进步分", "completion": "周末课完成率奖励", "tutor": "周末课小老师奖励", "team": "周末课团队目标"}
BASELINE_LESSONS = 3


class PairBody(BaseModel):
    tutorId: int
    tuteeId: int
    questionId: int


class ResultBody(BaseModel):
    correct: bool


class ExplainBody(BaseModel):
    tutorId: int
    questionId: int
    questionType: str = "choice"


class BriefBody(BaseModel):
    texts: dict[str, str] = {}


class FollowBody(BaseModel):
    peerHelpId: int
    selected: int


def register_scoring_tables(implementation: Any) -> dict[str, Table]:
    md = implementation.Base.metadata
    peer = md.tables.get("weekend_peer_help")
    if peer is None:
        peer = Table(
            "weekend_peer_help", md,
            Column("id", Integer, primary_key=True),
            Column("school_id", Integer, nullable=False, index=True),
            Column("session_id", Integer, nullable=False, index=True),
            Column("tutor_id", Integer, nullable=False, index=True),
            Column("tutee_id", Integer, nullable=False, index=True),
            Column("question_id", Integer, nullable=False),
            Column("followup_json", Text, nullable=False, default=""),   # {"stem","options","correctIndex","explanation"}
            Column("followup_correct", Boolean, nullable=True),
            Column("created_at", DateTime, nullable=False, default=datetime.utcnow),
        )
    awards = md.tables.get("weekend_awards")
    if awards is None:
        awards = Table(
            "weekend_awards", md,
            Column("id", Integer, primary_key=True),
            Column("school_id", Integer, nullable=False, index=True),
            Column("session_id", Integer, nullable=False, index=True),
            Column("student_id", Integer, nullable=False, index=True),
            Column("kind", String(12), nullable=False),
            Column("points", Integer, nullable=False, default=0),
            Column("basis_json", Text, nullable=False, default="{}"),
            Column("ledger_id", Integer, nullable=True),
            Column("created_at", DateTime, nullable=False, default=datetime.utcnow),
            UniqueConstraint("session_id", "student_id", "kind", name="uq_weekend_award"),
        )
    metrics = md.tables.get("weekend_metrics")
    if metrics is None:
        metrics = Table(
            "weekend_metrics", md,
            Column("id", Integer, primary_key=True),
            Column("school_id", Integer, nullable=False, index=True),
            Column("session_id", Integer, nullable=False, unique=True),
            Column("pre_rate", Float, nullable=False, default=0),
            Column("post_rate", Float, nullable=False, default=0),
            Column("created_at", DateTime, nullable=False, default=datetime.utcnow),
        )
    briefs = md.tables.get("weekend_briefs")
    if briefs is None:
        briefs = Table(
            "weekend_briefs", md,
            Column("id", Integer, primary_key=True),
            Column("school_id", Integer, nullable=False, index=True),
            Column("session_id", Integer, nullable=False, index=True),
            Column("student_id", Integer, nullable=False, index=True),
            Column("text", Text, nullable=False, default=""),
            Column("created_at", DateTime, nullable=False, default=datetime.utcnow),
            UniqueConstraint("session_id", "student_id", name="uq_weekend_brief"),
        )
    return {"peer": peer, "awards": awards, "metrics": metrics, "briefs": briefs}


def install_weekend_scoring(implementation: Any) -> APIRouter:
    app = implementation.app
    if getattr(app.state, "weekend_scoring_installed", False):
        return app.state.weekend_scoring_router
    from changying.web.weekend_practice import register_practice_tables
    from changying.web.weekend_views import register_weekend_tables

    sessions = register_weekend_tables(implementation)["sessions"]
    pt = register_practice_tables(implementation)
    answers_t = pt["answers"]
    st = register_scoring_tables(implementation)
    peer, awards, metrics, briefs = st["peer"], st["awards"], st["metrics"], st["briefs"]
    log_t = register_weekend_tables(implementation)["log"]
    ParentStudent = implementation.ParentStudent
    TQ, Lesson = implementation.TeachingQuestion, implementation.TeachingLesson
    User, ClassStudent, SchoolClass = implementation.User, implementation.ClassStudent, implementation.SchoolClass
    PointLedger = implementation.PointLedger
    current_user, get_db, need = implementation.current_user, implementation.get_db, implementation.need
    router = APIRouter()

    def my_session(db: Any, u: Any, sid: int) -> Any:
        row = db.execute(select(sessions).where(sessions.c.id == sid, sessions.c.school_id == u.school_id, sessions.c.teacher_id == u.id).with_for_update()).first()
        if row is None:
            raise HTTPException(404, "没有找到这节课堂")
        return row

    def roster(db: Any, u: Any, row: Any = None) -> dict[int, tuple[str, int | None]]:
        if row is not None:
            from changying.services.weekend_roster import session_roster
            return session_roster(implementation, db, row)
        rows = db.execute(
            select(User.id, User.name, SchoolClass.id).join(ClassStudent, ClassStudent.student_id == User.id).join(SchoolClass, SchoolClass.id == ClassStudent.class_id)
            .where(SchoolClass.teacher_id == u.id, SchoolClass.school_id == u.school_id, User.school_id == u.school_id)).all()
        return {int(i): (str(n), int(c)) for i, n, c in rows}

    def session_answers(db: Any, sid: int) -> dict[int, list[Any]]:
        """Per student who answered at least once: one Answer per core question of the lesson; a question not answered counts as not done."""
        out: dict[int, list[Any]] = {}
        sess = db.execute(select(sessions).where(sessions.c.id == sid)).first()
        if sess is None:
            return out
        from changying.services.weekend_roster import session_roster, session_class
        members = session_roster(implementation, db, sess)
        bound = session_class(implementation, db, sess)
        questions = db.execute(select(TQ.id, TQ.knowledge).where(TQ.school_id == sess.school_id, TQ.lesson_id == sess.lesson_id, TQ.active.is_(True)).order_by(TQ.id)).all()
        knowledge = {int(i): str(k or "") for i, k in questions}
        done: dict[int, dict[int, Any]] = {}
        for a in db.execute(select(answers_t).where(answers_t.c.session_id == sid).order_by(answers_t.c.id)).all():
            if bound is not None and int(a.student_id) not in members:
                continue
            done.setdefault(int(a.student_id), {})[int(a.question_id)] = Answer(bool(a.correct), int(a.max_hint), knowledge.get(int(a.question_id), ""))
        from changying.web.weekend_written import register_written_tables
        wt = register_written_tables(implementation)
        written = db.execute(select(wt['questions']).where(wt['questions'].c.session_id == sid,
            wt['questions'].c.school_id == sess.school_id)).all()
        target = (db.get(Lesson, sess.lesson_id).core_target or '')
        knowledge.update({-int(q.id): target for q in written})
        hints = {(int(a.student_id), int(a.question_id)):int(a.used) for a in db.execute(
            select(wt['hint_log'].c.student_id, wt['hint_log'].c.question_id, func.max(wt['hint_log'].c.level).label('used'))
            .where(wt['hint_log'].c.session_id == sid).group_by(wt['hint_log'].c.student_id,wt['hint_log'].c.question_id))}
        for a in db.execute(select(wt['submissions']).where(wt['submissions'].c.session_id == sid,
                wt['submissions'].c.school_id == sess.school_id, wt['submissions'].c.result != 'pending')):
            if bound is not None and int(a.student_id) not in members: continue
            done.setdefault(int(a.student_id), {})[-int(a.question_id)] = Answer(a.result == 'correct',
                hints.get((int(a.student_id),int(a.question_id)),0),target)
        for stu, mine in done.items():
            out[stu] = [mine.get(qid) or Answer(False, 0, knowledge[qid]) for qid in knowledge] or list(mine.values())
        return out

    def peer_rows(db: Any, sid: int) -> list[Any]:
        return list(db.execute(select(peer).where(peer.c.session_id == sid, peer.c.question_id > 0).order_by(peer.c.id)).all())

    def student_for_scoring(db: Any, row: Any, stu: int, name: str, ans: list[Answer], tutee_ok: bool | None) -> Student:
        # history = the same student's last lessons of the same teacher and subject that came before this one
        prior = db.execute(
            select(sessions.c.id).join(Lesson, Lesson.id == sessions.c.lesson_id)
            .where(sessions.c.school_id == row.school_id, sessions.c.teacher_id == row.teacher_id, sessions.c.id < row.id,
                   Lesson.subject == db.get(Lesson, row.lesson_id).subject).order_by(sessions.c.id.desc()).limit(BASELINE_LESSONS * 2)).all()
        hist: list[History] = []
        for (psid,) in prior:
            a = session_answers(db, int(psid)).get(stu)
            if a:
                hist.append(History(completion_rate(a), hint_dependence(a)))
            if len(hist) >= BASELINE_LESSONS:
                break
        hist.reverse()
        return Student(name=name, attended=bool(ans), answers=ans, history=hist, flagged=weak_flags(db, row, stu), followup_correct=tutee_ok)

    def weak_flags(db: Any, row: Any, stu: int) -> set[str]:
        try:
            from changying.services.homework_knowledge_flags import knowledge_flags
            from changying.web.homework_assistant import homework_enabled
            if not homework_enabled():
                return set()
            data = knowledge_flags(implementation, db, int(row.school_id), stu)
            return {f["knowledge"] for f in data["flags"] if f["state"] == "open"}
        except Exception:  # noqa: BLE001 - flags are a bonus input; scoring must not fail without them
            return set()

    def compute(db: Any, u: Any, row: Any) -> dict[str, Any]:
        names = roster(db, u, row)
        by_stu = session_answers(db, int(row.id))
        pairs = peer_rows(db, int(row.id))
        ok_by_tutee = {int(p.tutee_id): p.followup_correct for p in pairs if p.followup_correct is not None}
        students: dict[int, Student] = {}
        for stu, ans in by_stu.items():
            name = names.get(stu, ("学生", None))[0]
            students[stu] = student_for_scoring(db, row, stu, name, ans, ok_by_tutee.get(stu))
        pre = [completion_rate(s.answers) for s in students.values() if s.attended and s.answers]
        pre_rate = round(sum(pre) / len(pre), 1) if pre else 0.0
        post_rate = round(class_post_rate(list(students.values())), 1)
        prev_query = select(metrics.c.post_rate).join(sessions, sessions.c.id == metrics.c.session_id).where(
            sessions.c.teacher_id == row.teacher_id, sessions.c.school_id == row.school_id, sessions.c.id < row.id)
        from changying.services.weekend_roster import session_class, register_roster_table
        bound = session_class(implementation, db, row)
        if bound is not None:
            rt = register_roster_table(implementation)
            prev_query = prev_query.join(rt, rt.c.session_id == sessions.c.id).where(rt.c.class_id == bound.class_id)
        prev = db.execute(prev_query.order_by(sessions.c.id.desc()).limit(1)).first()
        prev_post = float(prev.post_rate) if prev else None
        team = team_points(prev_post, post_rate)
        items = []
        for stu, s in students.items():
            if not s.attended:
                continue
            prog = progress_points(s)
            parts = {
                "progress": (prog["points"], {"reason": prog["reason"], "completion": round(completion_rate(s.answers)), "hintDependence": round(hint_dependence(s.answers), 2),
                                               "baseline": [[round(h.accuracy), round(h.hint_dep, 2)] for h in s.history], "flagged": sorted(s.flagged)}),
                "completion": (completion_bonus(s), {"completion": round(completion_rate(s.answers))}),
                "tutor": (0, {}),
                "team": (team, {"postRate": post_rate, "prevPostRate": prev_post}),
            }
            items.append({"studentId": stu, "name": s.name, "parts": parts})
        for p in pairs:
            tutee = students.get(int(p.tutee_id))
            pts = tutor_points(tutee) if tutee else 0
            for it in items:
                if it["studentId"] == int(p.tutor_id):
                    old = it["parts"]["tutor"]
                    it["parts"]["tutor"] = (old[0] + pts, {"helped": (old[1].get("helped", []) + [{"tuteeId": int(p.tutee_id), "followupCorrect": p.followup_correct}])})
        for it in items:
            it["total"] = sum(v[0] for v in it["parts"].values())
        items.sort(key=lambda x: x["name"])
        return {"items": items, "preRate": pre_rate, "postRate": post_rate, "prevPostRate": prev_post, "teamPoints": team,
                "pendingFollowups": sum(1 for p in pairs if p.followup_json and p.followup_correct is None),
                "settled": bool(db.scalar(select(func.count()).select_from(awards).where(awards.c.session_id == row.id)))}

    def public(result: dict[str, Any]) -> dict[str, Any]:
        out = dict(result)
        out["pendingFollowups"] = result.get("pendingFollowups", 0)
        out["items"] = [{"studentId": i["studentId"], "name": i["name"], "total": i["total"],
                         "parts": {k: v[0] for k, v in i["parts"].items()}, "why": {k: v[1] for k, v in i["parts"].items()}} for i in result["items"]]
        return out

    # ------------------------------------------------------------------ teacher
    def gen_followup(db: Any, u: Any, q: Any) -> str:
        follow = ""
        try:
            letters = "ABCD"
            opts = "；".join(f"{letters[i]}. {t}" for i, t in enumerate(json.loads(q.options_json or "[]")[:4]))
            prompt = (f"原题：{q.stem}\n选项：{opts}\n正确答案：{letters[int(q.correct_index)] if 0 <= int(q.correct_index) < 4 else ''}\n"
                      "请出一道考查同一个方法、但数字或情境不同的选择题（3 个选项，只有一个正确，难度不高于原题）。"
                      '只输出 JSON：{"stem":"题目","options":["A选项","B选项","C选项"],"correctIndex":0,"explanation":"一句话解析"}')
            data = implementation._ai_json(implementation._ai_call(db, u, AI_FEATURE, prompt, timeout=45))
            options = [str(x).strip() for x in (data.get("options") or [])][:4]
            ci = int(data.get("correctIndex"))
            if str(data.get("stem") or "").strip() and len(options) >= 2 and all(options) and 0 <= ci < len(options):
                follow = json.dumps({"stem": str(data["stem"]).strip()[:300], "options": options, "correctIndex": ci,
                                     "explanation": str(data.get("explanation") or "")[:200]}, ensure_ascii=False)
        except Exception:  # noqa: BLE001 - no follow-up question: the teacher records the result by hand
            follow = ""
        return follow

    def written_suggestions(db: Any, row: Any, names: dict) -> list[dict]:
        from changying.web.weekend_written import register_written_tables
        wt = register_written_tables(implementation)
        submissions = db.execute(select(wt['submissions']).where(wt['submissions'].c.session_id == row.id,
            wt['submissions'].c.school_id == row.school_id)).all()
        asked = {(int(p.question_id), int(p.tutor_id)) for p in db.execute(select(peer).where(peer.c.session_id == row.id, peer.c.question_id < 0))}
        items = []
        for no, q in enumerate(db.execute(select(wt['questions']).where(wt['questions'].c.session_id == row.id,
                wt['questions'].c.school_id == row.school_id, wt['questions'].c.teacher_id == row.teacher_id).order_by(wt['questions'].c.id)), 1):
            mine = [{'studentId': int(a.student_id), 'name': names[int(a.student_id)][0], 'result': a.result,
                     'asked': (-int(q.id), int(a.student_id)) in asked}
                    for a in submissions if a.question_id == q.id and int(a.student_id) in names]
            if mine:
                items.append({'questionType':'written', 'questionId':q.id, 'no':no,
                              'stem':q.stem.split('\n\n')[-1], 'submitted':mine, 'right':[], 'wrong':[]})
        return items

    @router.get("/teacher/weekend/sessions/{sid}/peer-suggest")
    def suggest(sid: int, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        """Question-first, like the interactive classroom: for each question some pupils got right and some did not, who could explain it."""
        need(u, "teacher")
        row = my_session(db, u, sid)
        names = roster(db, u, row)
        written = written_suggestions(db, row, names)
        written_message = "文字／照片题已收到提交，可按批改状态选择同学讲思路；待批改不等于没作答。"
        by_stu = session_answers(db, sid)
        if written and not by_stu:
            return {"mode":"peer", "message":written_message, "questions":written}
        if not by_stu:
            return {"mode": "none", "message": "还没有学生作答", "questions": []}
        rates = [completion_rate(a) for a in by_stu.values()]
        if all(r >= 100 for r in rates):
            return {"mode": "peer" if written else "challenge", "message": written_message if written else "全员全对：可以出一道挑战题，团队目标改成全员独立完成", "questions": written}
        if all(r == 0 for r in rates):
            return {"mode": "peer" if written else "teacher", "message": written_message if written else "这几题大家都没做对：建议老师集中讲，只记参与", "questions": written}
        qs = {int(q.id): q for q in db.scalars(select(TQ).where(TQ.school_id == u.school_id, TQ.lesson_id == row.lesson_id, TQ.active.is_(True)).order_by(TQ.id)).all()}
        asked = {(int(p.question_id), int(p.tutor_id)) for p in peer_rows(db, sid)}
        right: dict[int, list[dict[str, Any]]] = {}
        wrong: dict[int, list[dict[str, Any]]] = {}
        for a in db.execute(select(answers_t).where(answers_t.c.session_id == sid).order_by(answers_t.c.id)).all():
            if int(a.student_id) not in names:
                continue
            who = {"studentId": int(a.student_id), "name": names.get(int(a.student_id), ("学生",))[0]}
            (right if a.correct else wrong).setdefault(int(a.question_id), []).append(who)
        items = []
        for no, (qid, q) in enumerate(qs.items(), start=1):
            if right.get(qid) and wrong.get(qid):
                items.append({"questionId": qid, "no": no, "stem": q.stem, "right": [dict(w, asked=(qid, w["studentId"]) in asked) for w in right[qid]], "wrong": wrong[qid]})
        return {"mode": "peer", "message": "选一道题，请做对的同学来讲；讲完，没做对的同学会收到一道类似的小题。", "questions": items + written}

    @router.post("/teacher/weekend/sessions/{sid}/explain")
    def explain(sid: int, b: ExplainBody, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        """Ask one pupil who got the question right to explain it to the class; everyone who got it wrong gets the same follow-up later."""
        need(u, "teacher")
        row = my_session(db, u, sid)
        names = roster(db, u, row)
        if b.tutorId not in names:
            raise HTTPException(400, "请选择你班级里的学生")
        if b.questionType not in ("choice", "written"):
            raise HTTPException(400, "请选择有效题型")
        if b.questionType == "written":
            from changying.web.weekend_written import register_written_tables
            wt = register_written_tables(implementation)
            q = db.execute(select(wt['questions']).where(wt['questions'].c.id == b.questionId,
                wt['questions'].c.session_id == sid, wt['questions'].c.school_id == u.school_id,
                wt['questions'].c.teacher_id == u.id)).first()
            a = db.execute(select(wt['submissions']).where(wt['submissions'].c.session_id == sid,
                wt['submissions'].c.question_id == b.questionId, wt['submissions'].c.student_id == b.tutorId)).first()
            if q is None or a is None:
                raise HTTPException(400, "请选择已提交本题答案的同学")
            if row.status != "running":
                raise HTTPException(409, "请在上课期间邀请同学讲解")
            # Negative IDs namespace written invitations. These are not peer-help
            # scoring pairs and never create follow-ups or automatic tutor points.
            db.execute(select(sessions.c.id).where(sessions.c.id == sid).with_for_update()).first()
            exists = db.execute(select(peer.c.id).where(peer.c.session_id == sid,
                peer.c.question_id == -q.id, peer.c.tutor_id == b.tutorId)).first()
            if not exists:
                db.execute(insert(peer).values(school_id=u.school_id, session_id=sid, tutor_id=b.tutorId,
                    tutee_id=b.tutorId, question_id=-q.id, followup_json="", created_at=datetime.utcnow()))
                db.commit()
            return {"followup":False, "tutees":0, "message":f"已请 {names[b.tutorId][0]} 同学讲解本题思路；大屏和学生页面会收到邀请。"}

        q = db.get(TQ, b.questionId)
        if q is None or int(q.school_id) != int(u.school_id) or int(q.lesson_id or 0) != int(row.lesson_id):
            raise HTTPException(404, "没有找到这道题")
        mine = {int(a.student_id): a for a in db.execute(select(answers_t).where(answers_t.c.session_id == sid, answers_t.c.question_id == q.id)).all()}
        if b.tutorId not in mine or not mine[b.tutorId].correct:
            raise HTTPException(400, "请选在这道题上做对的同学来讲")
        tutees = [s for s, a in mine.items() if not a.correct and s in names]
        if not tutees:
            raise HTTPException(400, "这道题大家都做对了，不需要再安排讲解")
        if db.execute(select(peer.c.id).where(peer.c.session_id == sid, peer.c.question_id == q.id, peer.c.tutor_id == b.tutorId)).first():
            raise HTTPException(409, "已经请这位同学讲过这道题了")
        follow = gen_followup(db, u, q)
        now = datetime.utcnow()
        for t in tutees:
            if not db.execute(select(peer.c.id).where(peer.c.session_id == sid, peer.c.tutee_id == t, peer.c.question_id == q.id)).first():
                db.execute(insert(peer).values(school_id=u.school_id, session_id=sid, tutor_id=b.tutorId, tutee_id=t, question_id=q.id, followup_json=follow, created_at=now))
        db.commit()
        return {"followup": bool(follow), "tutees": len(tutees), "message": f"已请 {names[b.tutorId][0]} 同学来讲这道题：大屏会显示，TA 的页面会收到题目和解析。" +
                ("讲完后，没做对的同学会收到一道类似的小题。" if follow else "AI 没能出类似的小题，讲完后请你手动记录结果。")}

    @router.get("/student/weekend/explain")
    def my_explain(sessionId: int | None = None, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        """The question(s) the teacher asked me to explain to the class (I answered them correctly)."""
        need(u, "student")
        current = current_student_session(implementation, db, u)
        if current is None or current.current_stage not in (4, 5) or (sessionId is not None and sessionId != current.id):
            return {"sessionId": current.id if current else None, "items": []}
        rows = db.execute(select(peer).where(peer.c.school_id == u.school_id, peer.c.tutor_id == u.id,
            peer.c.session_id == current.id).order_by(peer.c.id.desc())).all()
        seen: set[int] = set()
        items = []
        for p in rows:
            if int(p.question_id) in seen:
                continue
            seen.add(int(p.question_id))
            if int(p.question_id) < 0:
                from changying.web.weekend_written import register_written_tables
                from changying.services.weekend_answers import answers_published
                from changying.services.weekend_roster import student_in_session
                wt = register_written_tables(implementation)
                row = db.execute(select(sessions).where(sessions.c.id == p.session_id)).first()
                if row is None or not student_in_session(implementation, db, row, u.id):
                    continue
                q = db.execute(select(wt['questions']).where(wt['questions'].c.id == -p.question_id,
                    wt['questions'].c.session_id == p.session_id, wt['questions'].c.school_id == u.school_id)).first()
                a = db.execute(select(wt['submissions']).where(wt['submissions'].c.session_id == p.session_id,
                    wt['submissions'].c.question_id == -p.question_id, wt['submissions'].c.student_id == u.id)).first()
                if q is not None and a is not None:
                    item = {"questionType":"written", "questionId":q.id, "stem":q.stem,
                            "answerText":a.answer_text, "submission":{"id":a.id,"hasPhoto":a.photo is not None}}
                    if answers_published(implementation, db, row, q.id, "written"):
                        item['reference'] = q.reference
                    items.append(item)
                continue
            q = db.get(TQ, int(p.question_id))
            if q is None or q.school_id != u.school_id or q.lesson_id != current.lesson_id:
                continue
            try:
                opts = json.loads(q.options_json or "[]")
            except Exception:  # noqa: BLE001
                opts = []
            items.append({"questionId": q.id, "stem": q.stem, "options": opts, "correctIndex": int(q.correct_index), "explanation": q.explanation or ""})
        return {"sessionId": current.id, "items": items}

    @router.post("/teacher/weekend/sessions/{sid}/peer-help")
    def pair(sid: int, b: PairBody, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "teacher")
        row = my_session(db, u, sid)
        names = roster(db, u, row)
        if b.tutorId == b.tuteeId or b.tutorId not in names or b.tuteeId not in names:
            raise HTTPException(400, "请选择你班级里的两位不同的学生")
        q = db.get(TQ, b.questionId)
        if q is None or int(q.school_id) != int(u.school_id) or int(q.lesson_id or 0) != int(row.lesson_id):
            raise HTTPException(404, "没有找到这道题")
        mine = {int(a.student_id): a for a in db.execute(select(answers_t).where(answers_t.c.session_id == sid, answers_t.c.question_id == q.id)).all()}
        if b.tutorId not in mine or not mine[b.tutorId].correct:
            raise HTTPException(400, "小老师需要在这道题上做对")
        if b.tuteeId not in mine or mine[b.tuteeId].correct:
            raise HTTPException(400, "被讲的同学需要在这道题上做错")
        if db.execute(select(peer.c.id).where(peer.c.session_id == sid, peer.c.tutee_id == b.tuteeId, peer.c.question_id == q.id)).first():
            raise HTTPException(409, "这道题已经安排过讲解了")
        follow = gen_followup(db, u, q)
        pid = int(db.execute(insert(peer).values(school_id=u.school_id, session_id=sid, tutor_id=b.tutorId, tutee_id=b.tuteeId, question_id=q.id,
                                                  followup_json=follow, created_at=datetime.utcnow())).inserted_primary_key[0])
        db.commit()
        return {"id": pid, "followup": bool(follow), "message": "已安排。讲完后被讲同学会在自己的页面看到一道换数字的巩固题。" if follow
                else "已安排。AI 没能出巩固题，讲完后请你在这里手动记录结果。"}

    @router.post("/teacher/weekend/peer-help/{pid}/result")
    def result(pid: int, b: ResultBody, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "teacher")
        p = db.execute(select(peer).where(peer.c.id == pid, peer.c.school_id == u.school_id)).first()
        if p is None or p.question_id < 0:
            raise HTTPException(404, "没有找到这条记录")
        my_session(db, u, int(p.session_id))
        db.execute(update(peer).where(peer.c.id == pid).values(followup_correct=bool(b.correct)))
        db.commit()
        return {"id": pid, "followupCorrect": bool(b.correct)}

    @router.get("/teacher/weekend/sessions/{sid}/peer-help")
    def list_pairs(sid: int, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "teacher")
        row = my_session(db, u, sid)
        names = roster(db, u, row)
        return {"items": [{"id": p.id, "tutor": names.get(int(p.tutor_id), ("学生",))[0], "tutee": names.get(int(p.tutee_id), ("学生",))[0], "questionId": p.question_id,
                           "hasFollowup": bool(p.followup_json), "followupCorrect": p.followup_correct} for p in peer_rows(db, sid)]}

    @router.get("/teacher/weekend/sessions/{sid}/settle-preview")
    def preview(sid: int, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "teacher")
        return public(compute(db, u, my_session(db, u, sid)))

    @router.post("/teacher/weekend/sessions/{sid}/settle")
    def settle(sid: int, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "teacher")
        row = my_session(db, u, sid)
        db.execute(select(sessions.c.id).where(sessions.c.id == sid).with_for_update()).first()
        from changying.web.weekend_written import register_written_tables
        written = register_written_tables(implementation)['submissions']
        members = roster(db, u, row)
        if db.scalar(select(func.count()).select_from(written).where(written.c.session_id == sid,
                written.c.student_id.in_(list(members)), written.c.result == 'pending')):
            raise HTTPException(409, '还有文字／照片答案待批改，请核对纸质补录后再结算')
        if db.scalar(select(func.count()).select_from(awards).where(awards.c.session_id == sid)):
            raise HTTPException(409, "这节课已经结算过了")
        result = compute(db, u, row)
        if not result["items"]:
            raise HTTPException(400, "还没有学生作答，没有可结算的内容")
        names = roster(db, u, row)
        now = datetime.utcnow()
        try:
            for it in result["items"]:
                for kind, (pts, basis) in it["parts"].items():
                    ledger_id = None
                    if pts > 0:
                        led = PointLedger(school_id=u.school_id, student_id=it["studentId"], class_id=names.get(it["studentId"], ("", None))[1], actor_id=u.id,
                                          category=CATEGORY[kind], points=int(pts), reason=REASON[kind], note=f"周末课 {row.title}", source=SOURCE, related_id=sid, created_at=now)
                        db.add(led)
                        db.flush()
                        ledger_id = int(led.id)
                    db.execute(insert(awards).values(school_id=u.school_id, session_id=sid, student_id=it["studentId"], kind=kind, points=int(pts),
                                                      basis_json=json.dumps(basis, ensure_ascii=False), ledger_id=ledger_id, created_at=now))
            db.execute(insert(metrics).values(school_id=u.school_id, session_id=sid, pre_rate=result["preRate"], post_rate=result["postRate"], created_at=now))
            db.commit()
        except IntegrityError:
            db.rollback()
            raise HTTPException(409, "原课堂已被另一请求结算，请刷新核对；未重复发分")
        return public(compute(db, u, row))

    # ------------------------------------------------------------------ student
    @router.get("/student/weekend/followup")
    def my_followup(u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "student")
        current = current_student_session(implementation, db, u)
        if current is None or current.current_stage not in (4, 5): return {"active": False}
        p = db.execute(select(peer).where(peer.c.school_id == u.school_id, peer.c.tutee_id == u.id, peer.c.followup_correct.is_(None), peer.c.followup_json != "", peer.c.session_id == current.id)
                       .order_by(peer.c.id.desc()).limit(1)).first()
        if p is None:
            return {"active": False}
        sess = db.execute(select(sessions.c.status).where(sessions.c.id == p.session_id)).first()
        if sess is None or sess.status != "running":
            return {"active": False}
        data = json.loads(p.followup_json)
        return {"active": True, "sessionId":current.id, "peerHelpId": p.id, "stem": data["stem"], "options": data["options"]}

    @router.post("/student/weekend/followup")
    def answer_followup(b: FollowBody, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "student")
        p = db.execute(select(peer).where(peer.c.id == b.peerHelpId, peer.c.school_id == u.school_id, peer.c.tutee_id == u.id, peer.c.question_id > 0)).first()
        current = current_student_session(implementation, db, u)
        if current is None or current.current_stage not in (4, 5) or p is None or p.session_id != current.id:
            raise HTTPException(404, "不是当前课堂的巩固题")
        if p is None or not p.followup_json:
            raise HTTPException(404, "没有找到这道题")
        if p.followup_correct is not None:
            raise HTTPException(409, "这道题已经作答了")
        data = json.loads(p.followup_json)
        if not 0 <= int(b.selected) < len(data["options"]):
            raise HTTPException(400, "没有这个选项")
        ok = int(b.selected) == int(data["correctIndex"])
        db.execute(update(peer).where(peer.c.id == p.id).values(followup_correct=ok))
        db.commit()
        return {"correct": ok, "correctIndex": int(data["correctIndex"]), "explanation": data.get("explanation", "")}

    @router.get("/v1/weekend-brief", include_in_schema=False)
    def brief_page():
        from changying.web.weekend_pages import brief_page_html
        return HTMLResponse(brief_page_html(), headers={"Cache-Control": "no-store"})

    # ------------------------------------------------------------------ archive / briefs
    def lesson_info(db: Any, row: Any) -> Any:
        return db.get(Lesson, row.lesson_id)

    def wrong_knowledge(db: Any, sid: int, stu: int) -> list[str]:
        rows = db.execute(select(TQ.knowledge).join(answers_t, answers_t.c.question_id == TQ.id)
                          .where(answers_t.c.session_id == sid, answers_t.c.student_id == stu, answers_t.c.correct.is_(False))).all()
        out: list[str] = []
        for (k,) in rows:
            if k and k not in out:
                out.append(str(k))
        from changying.web.weekend_written import register_written_tables
        written = register_written_tables(implementation)['submissions']
        if db.scalar(select(func.count()).select_from(written).where(written.c.session_id == sid,
                written.c.student_id == stu, written.c.result.in_(['partial', 'revise']))):
            # Written questions carry no knowledge point; the lesson goal is not a stand-in for it.
            out.append("文字／照片题（未标注考点）")
        return out

    def student_line(db: Any, row: Any, stu: int, ans: list[Any], points: dict[str, int], helped: int) -> dict[str, Any]:
        return {"completionRate": round(completion_rate(ans)), "correct": sum(1 for a in ans if a.correct), "total": len(ans),
                "hintAvg": round(hint_dependence(ans), 1), "wrongKnowledge": wrong_knowledge(db, int(row.id), stu), "points": points, "helped": helped}

    def award_map(db: Any, sid: int) -> dict[int, dict[str, int]]:
        out: dict[int, dict[str, int]] = {}
        for a in db.execute(select(awards).where(awards.c.session_id == sid)).all():
            out.setdefault(int(a.student_id), {})[a.kind] = int(a.points)
        return out

    @router.get("/teacher/weekend/sessions/{sid}/archive")
    def archive(sid: int, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "teacher")
        row = my_session(db, u, sid)
        names = roster(db, u, row)
        by_stu = session_answers(db, sid)
        pts = award_map(db, sid)
        pairs = peer_rows(db, sid)
        timeline = []
        for g in db.execute(select(log_t).where(log_t.c.session_id == sid).order_by(log_t.c.id)).all():
            secs = int(((g.ended_at or datetime.utcnow()) - g.started_at).total_seconds())
            timeline.append({"stage": int(g.stage_no), "plannedMin": int(g.planned_min) + int(g.extend_min), "actualMin": round(secs / 60, 1)})
        students = []
        for stu in sorted(set(names) | set(by_stu), key=lambda x: names.get(x, ("学生",))[0]):
            ans = by_stu.get(stu)
            helped = sum(1 for p in pairs if int(p.tutor_id) == stu)
            item = {"studentId": stu, "name": names.get(stu, ("学生",))[0], "attended": bool(ans)}
            if ans:
                item.update(student_line(db, row, stu, ans, pts.get(stu, {}), helped))
            students.append(item)
        lesson = lesson_info(db, row)
        met = db.execute(select(metrics).where(metrics.c.session_id == sid)).first()
        return {"id": row.id, "title": row.title, "status": row.status, "subject": lesson.subject if lesson else "", "unit": lesson.unit if lesson else "",
                "startedAt": row.started_at.strftime("%Y-%m-%d %H:%M") if row.started_at else "", "timeline": timeline, "students": students,
                "attendance": {"present": sum(1 for x in students if x["attended"]), "total": len(students)},
                "peerHelp": [{"tutor": names.get(int(p.tutor_id), ("学生",))[0], "tutee": names.get(int(p.tutee_id), ("学生",))[0], "followupCorrect": p.followup_correct} for p in pairs],
                "classRates": {"pre": met.pre_rate, "post": met.post_rate} if met else None, "settled": bool(pts)}

    def brief_text(row: Any, lesson: Any, name: str, line: dict[str, Any]) -> str:
        parts = [f"{name}本节{lesson.subject if lesson else ''}课《{lesson.title if lesson else row.title}》：已批改做对 {line['correct']} 题（本节共 {line['total']} 题）。"]
        if line["hintAvg"] > 0:
            parts.append(f"做题时有需要提示的地方（平均提示 {line['hintAvg']} 级），能在提示下完成，继续练习会更独立。")
        else:
            parts.append("基本能独立完成。")
        if line["helped"]:
            parts.append(f"今天还当了小老师，给同学讲了 {line['helped']} 道题，值得表扬。")
        gained = sum(line["points"].values()) if line["points"] else 0
        if gained:
            parts.append(f"本节课获得积分 {gained} 分。")
        if line["wrongKnowledge"]:
            parts.append("回家可以复习：" + "、".join(line["wrongKnowledge"][:3]) + "。")
        else:
            parts.append("本节没有需要重点补的知识点。")
        return "".join(parts)

    def drafts(db: Any, u: Any, row: Any) -> list[dict[str, Any]]:
        names = roster(db, u, row)
        by_stu = session_answers(db, int(row.id))
        pts = award_map(db, int(row.id))
        pairs = peer_rows(db, int(row.id))
        lesson = lesson_info(db, row)
        saved = {int(b.student_id): b for b in db.execute(select(briefs).where(briefs.c.session_id == row.id)).all()}
        out = []
        for stu, ans in sorted(by_stu.items(), key=lambda kv: names.get(kv[0], ("学生",))[0]):
            line = student_line(db, row, stu, ans, pts.get(stu, {}), sum(1 for p in pairs if int(p.tutor_id) == stu))
            out.append({"studentId": stu, "name": names.get(stu, ("学生",))[0],
                        "text": saved[stu].text if stu in saved else brief_text(row, lesson, names.get(stu, ("学生",))[0], line), "published": stu in saved})
        return out

    @router.get("/teacher/weekend/sessions/{sid}/briefs")
    def brief_drafts(sid: int, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "teacher")
        return {"items": drafts(db, u, my_session(db, u, sid))}

    @router.post("/teacher/weekend/sessions/{sid}/briefs/publish")
    def publish_briefs(sid: int, b: BriefBody, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "teacher")
        row = my_session(db, u, sid)
        now = datetime.utcnow()
        count = 0
        for d in drafts(db, u, row):
            text = " ".join((b.texts.get(str(d["studentId"])) or d["text"]).split())[:800]
            existing = db.execute(select(briefs.c.id).where(briefs.c.session_id == sid, briefs.c.student_id == d["studentId"])).first()
            if existing:
                db.execute(update(briefs).where(briefs.c.id == existing.id).values(text=text, created_at=now))
            else:
                db.execute(insert(briefs).values(school_id=u.school_id, session_id=sid, student_id=d["studentId"], text=text, created_at=now))
            count += 1
        db.commit()
        return {"published": count}

    @router.get("/parent/children/{cid}/weekend-briefs")
    def child_briefs(cid: int, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "parent")
        linked = db.scalar(select(ParentStudent.id).where(ParentStudent.parent_id == u.id, ParentStudent.student_id == cid).limit(1))
        child = db.scalar(select(User).where(User.id == cid, User.school_id == u.school_id, User.role == "student"))
        if not linked or child is None:
            raise HTTPException(404, "没有找到这个孩子")
        rows = db.execute(select(briefs.c.text, briefs.c.created_at, sessions.c.title).join(sessions, sessions.c.id == briefs.c.session_id)
                          .where(briefs.c.student_id == cid, briefs.c.school_id == u.school_id).order_by(briefs.c.id.desc()).limit(30)).all()
        from changying.web.weekend_report_views import published_reports
        # Both parent entries (孩子课程 and 孩子学情) read this one endpoint, so they show the same published data.
        return {"childName": child.name, "items": [{"title": r.title, "text": r.text, "at": r.created_at.strftime("%Y-%m-%d")} for r in rows],
                "reports": published_reports(implementation, db, int(u.school_id), cid)}

    @router.get("/teacher/weekend/term-summary")
    def term_summary(subject: str = "", u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "teacher")
        names = roster(db, u)
        q = select(sessions.c.id, sessions.c.lesson_id).join(Lesson, Lesson.id == sessions.c.lesson_id).where(
            sessions.c.school_id == u.school_id, sessions.c.teacher_id == u.id, sessions.c.status != "planned")
        if subject:
            q = q.where(Lesson.subject == subject)
        sess = db.execute(q.order_by(sessions.c.id)).all()
        trend: dict[int, list[dict[str, Any]]] = {}
        for sid_, _ in sess:
            for stu, ans in session_answers(db, int(sid_)).items():
                trend.setdefault(stu, []).append({"sessionId": int(sid_), "completionRate": round(completion_rate(ans)), "hintAvg": round(hint_dependence(ans), 1)})
        points: dict[int, int] = {}
        for a in db.execute(select(awards.c.student_id, func.sum(awards.c.points)).where(awards.c.school_id == u.school_id,
                                                                                           awards.c.session_id.in_([int(x[0]) for x in sess] or [0])).group_by(awards.c.student_id)).all():
            points[int(a[0])] = int(a[1] or 0)
        tutor = {}
        for p in db.execute(select(peer.c.tutor_id, func.count()).where(peer.c.school_id == u.school_id, peer.c.question_id > 0, peer.c.session_id.in_([int(x[0]) for x in sess] or [0])).group_by(peer.c.tutor_id)).all():
            tutor[int(p[0])] = int(p[1])
        return {"lessons": len(sess), "students": [{"studentId": s, "name": names.get(s, ("学生",))[0], "attended": len(t), "trend": t, "points": points.get(s, 0), "tutoredTimes": tutor.get(s, 0)}
                                                  for s, t in sorted(trend.items(), key=lambda kv: names.get(kv[0], ("学生",))[0])]}

    app.include_router(router)
    app.state.weekend_scoring_installed = True
    app.state.weekend_scoring_router = router
    return router


__all__ = ["install_weekend_scoring", "register_scoring_tables"]



