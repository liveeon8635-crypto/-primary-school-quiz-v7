"""Consolidation practice from AI-assisted after-school questions (晚托作业助手 → 巩固练习).

teacher  GET  /teacher/homework/students/{sid}/practice-sources   the pupil's recent AI-explained questions, flags, earlier practice
         POST /teacher/homework/students/{sid}/practice/generate  {helpIds, counts, subjects} new variants for review (nothing saved)
         POST /teacher/homework/students/{sid}/practice/assign    {requestId, groups, dueDate} assign reviewed questions once

Assigning goes through the existing targeted-practice homework (teacher_reinforcement_assign: only this pupil);
the pupil answers in 作业 and the result enters the usual submissions, which also clear the knowledge flags.
Behind the HOMEWORK_ASSISTANT flag like the rest of the assistant.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from changying.services import homework_practice as hp
from changying.services.homework_knowledge import register_homework_knowledge_table
from changying.services.homework_knowledge_flags import knowledge_flags
from changying.web.homework_assistant import require_enabled

AI_FEATURE = "homework_practice_generate"
SOURCE_DAYS = 30
ASSIGN_ACTION = "homework.practice.assign"


class GenerateBody(BaseModel):
    helpIds: list[int] = Field(min_length=1, max_length=30)
    counts: dict[str, int] = Field(default_factory=dict)
    subjects: dict[str, str] = Field(default_factory=dict)


class AssignBody(BaseModel):
    requestId: str = Field(pattern=r"^[A-Za-z0-9-]{8,64}$")
    groups: list[dict[str, Any]] = Field(min_length=1, max_length=20)
    dueDate: str = Field(default="", max_length=20)


def install_homework_practice_views(implementation: Any) -> APIRouter:
    app = implementation.app
    if getattr(app.state, "homework_practice_views_installed", False):
        return app.state.homework_practice_views_router
    helps = app.state.homework_tables["help_requests"]
    knowledge = register_homework_knowledge_table(implementation)
    User, SchoolClass, ClassStudent = implementation.User, implementation.SchoolClass, implementation.ClassStudent
    AuditLog, Submission = implementation.AuditLog, implementation.Submission
    current_user, get_db, need = implementation.current_user, implementation.get_db, implementation.need
    router = APIRouter(dependencies=[Depends(require_enabled)])

    def my_student(db: Any, u: Any, sid: int) -> Any:
        need(u, "teacher")
        stu = db.scalar(select(User).join(ClassStudent, ClassStudent.student_id == User.id).join(SchoolClass, SchoolClass.id == ClassStudent.class_id)
                        .where(User.id == sid, User.school_id == u.school_id, SchoolClass.teacher_id == u.id, SchoolClass.school_id == u.school_id).limit(1))
        if stu is None:
            raise HTTPException(403, "该学生不在你管理的班级中")
        return stu

    def rows_for(db: Any, u: Any, sid: int, ids: list[int] | None = None) -> list[dict[str, Any]]:
        since = datetime.utcnow() - timedelta(days=SOURCE_DAYS)
        q = (select(helps.c.id.label("help_id"), helps.c.question_text, helps.c.ai_json, helps.c.state, helps.c.grade, helps.c.created_at,
                    helps.c.verify_status, knowledge.c.knowledge_key, knowledge.c.raw_knowledge, knowledge.c.matched, knowledge.c.subject)
             .select_from(helps.join(knowledge, knowledge.c.help_id == helps.c.id))
             .where(helps.c.school_id == u.school_id, helps.c.student_id == sid, helps.c.state.in_(("answered", "resolved")),
                    helps.c.created_at >= since).order_by(helps.c.created_at.desc(), helps.c.id.desc()).limit(60))
        if ids is not None:
            q = q.where(helps.c.id.in_(ids))
        out = []
        for r in db.execute(q):
            try:
                ai = json.loads(r.ai_json or "{}")
            except Exception:  # noqa: BLE001
                ai = {}
            if ai.get("hidden"):
                continue
            out.append({**r._mapping, "answer": str(ai.get("answer") or ""), "steps": ai.get("steps") if isinstance(ai.get("steps"), list) else []})
        return out

    def earlier_practice(db: Any, u: Any, sid: int) -> list[dict[str, Any]]:
        out = []
        for detail, at in db.execute(select(AuditLog.detail, AuditLog.created_at).where(
                AuditLog.school_id == u.school_id, AuditLog.action == ASSIGN_ACTION).order_by(AuditLog.id.desc()).limit(200)):
            try:
                d = json.loads(detail)
            except Exception:  # noqa: BLE001
                continue
            if int(d.get("studentId") or 0) != sid:
                continue
            for a in d.get("assignments") or []:
                sub = db.scalar(select(Submission).where(Submission.assignment_id == a["assignmentId"], Submission.student_id == sid).limit(1))
                out.append({**a, "helpIds": d.get("helpIds") or [], "assignedAt": at.replace(tzinfo=timezone.utc).astimezone(implementation.SCHOOL_TZ).strftime("%Y-%m-%d %H:%M"),
                            "state": "graded" if sub else "assigned", "correct": sub.correct if sub else None, "total": sub.total if sub else None})
        return out

    @router.get("/teacher/homework/students/{sid}/practice-sources")
    def practice_sources(sid: int, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        stu = my_student(db, u, sid)
        rows = rows_for(db, u, sid)
        flags = {(f["subject"], f["knowledge"]): f["state"] for f in knowledge_flags(implementation, db, int(u.school_id), sid)["flags"]}
        practice = earlier_practice(db, u, sid)
        practised = {h for p in practice for h in p["helpIds"]}
        return {"studentId": sid, "studentName": stu.name, "days": SOURCE_DAYS, "practice": practice,
                "items": [{"helpId": r["help_id"], "question": r["question_text"], "knowledge": (r["knowledge_key"] if r["matched"] else r["raw_knowledge"]) or "",
                           "matched": bool(r["matched"]), "groupKey": hp.group_key(r), "createdAt": r["created_at"].strftime("%Y-%m-%d %H:%M"),
                           "flag": flags.get((r["subject"], r["knowledge_key"]), "") if r["matched"] else "",
                           "verify": r["verify_status"], "practised": r["help_id"] in practised} for r in rows]}

    @router.post("/teacher/homework/students/{sid}/practice/generate")
    def generate(sid: int, b: GenerateBody, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        """Review-only: returns new variants for the teacher; nothing is saved or assigned."""
        my_student(db, u, sid)
        rows = rows_for(db, u, sid, list(dict.fromkeys(b.helpIds)))
        if not rows:
            raise HTTPException(400, "请选择这名学生近期由 AI 讲解过的题")
        cfg = implementation.ai_config_for(db, u.school_id, False)
        if not cfg or not cfg.enabled or not cfg.allow_student_data:
            raise HTTPException(400, "学校未开启 AI 或未允许发送学生学习数据，无法自动出巩固题")
        groups = hp.build_groups(rows, b.counts, b.subjects)
        src = hp.sources(groups)
        try:
            data = implementation._ai_json(implementation._ai_call(db, u, AI_FEATURE, hp.prompt(groups), timeout=90))
            returned = {str(g.get("key")): g for g in (data.get("groups") or []) if isinstance(g, dict)} if isinstance(data, dict) else {}
        except Exception as e:  # noqa: BLE001
            raise HTTPException(502, f"生成失败：{getattr(e, 'detail', '') or 'AI 服务不可用'}。请稍后重试")
        out, problems, seen = [], [], set()
        for g in groups:
            valid, reasons = [], []
            for raw in (returned.get(g["key"]) or {}).get("questions") or []:
                try:
                    q = hp.clean(raw, g, src, implementation._sanitize_figure)
                except ValueError as err:
                    reasons.append(str(err))
                    continue
                if hp.text_key(q["text"]) not in seen:          # one practice never repeats a question across knowledge points
                    seen.add(hp.text_key(q["text"]))
                    valid.append(q)
                if len(valid) == g["count"]:
                    break
            if len(valid) < g["count"]:
                problems.append(f"{g['topic']}：得到 {len(valid)}/{g['count']} 道合格新题" + (f"（{'；'.join(dict.fromkeys(reasons))}）" if reasons else ""))
            out.append({"key": g["key"], "subject": g["subject"], "knowledge": g["knowledge"], "topic": g["topic"], "matched": g["matched"],
                        "count": g["count"], "helpIds": [i["helpId"] for i in g["items"]],
                        "basis": [i["question"] for i in g["items"]], "questions": valid})
        if not any(g["questions"] for g in out):
            raise HTTPException(502, "生成失败：" + "；".join(problems))
        return {"groups": out, "problems": problems, "minQuestions": hp.thresholds()["minQuestions"]}

    @router.post("/teacher/homework/students/{sid}/practice/assign")
    def assign(sid: int, b: AssignBody, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        """After review: one homework per subject, only to this pupil, through the existing targeted practice."""
        stu = my_student(db, u, sid)
        action = f"{ASSIGN_ACTION}.request.{b.requestId}"
        db.execute(select(User.id).where(User.id == stu.id).with_for_update()).first()
        if db.scalar(select(AuditLog.id).where(AuditLog.school_id == u.school_id, AuditLog.action == action).limit(1)):
            raise HTTPException(409, "这组练习已经布置过了，没有重复布置")
        help_ids = sorted({int(h) for g in b.groups for h in (g.get("helpIds") or [])})
        rows = rows_for(db, u, sid, help_ids)
        groups = {g["key"]: g for g in hp.build_groups(rows, None, {str(g.get("key")): str(g.get("subject") or "") for g in b.groups})}
        by_subject: dict[str, list[dict[str, Any]]] = {}
        for edit in b.groups:
            g = groups.get(str(edit.get("key") or ""))
            if g is None:
                raise HTTPException(400, "练习对应的提问已不存在，请重新生成")
            src = hp.sources([g])
            for i, raw in enumerate(edit.get("questions") or [], 1):
                try:
                    by_subject.setdefault(g["subject"], []).append(hp.clean(raw, g, src, implementation._sanitize_figure))
                except ValueError as err:
                    raise HTTPException(400, f"{g['topic']} 第{i}题：{err}")
        if not by_subject:
            raise HTTPException(400, "请至少保留一道题")
        implementation.audit(db, u, action, json.dumps({"studentId": sid}))
        db.commit()
        grade = int(stu.grade or next((r["grade"] for r in rows if r["grade"]), 0) or 5)
        textbook = {"数学": "人教版", "语文": "统编版（人民教育出版社）", "英语": "人教版（PEP·当前最新版）"}
        assigned, error = [], ""
        for subject, questions in by_subject.items():
            title = f"{stu.name} · 晚托提问巩固练习（{subject}）"
            body = implementation.AIReinforcementAssignBody(
                questions=[{"grade": grade, "subject": subject, "textbook": textbook.get(subject, ""), "semester": "上册", "unit": "",
                            **{k: q[k] for k in ("knowledge", "text", "options", "correct_index", "explanation", "question_type",
                                                 "answer", "accepted_answers", "figure")}} for q in questions],
                title=title, due_date=b.dueDate.strip(), wrong_ids=[], instructions="根据你在晚托时问过的题出的巩固练习，请独立完成后提交。")
            try:
                res = implementation.teacher_reinforcement_assign(sid, body, u, db)
            except Exception as e:  # noqa: BLE001 - keep what was assigned; report the rest
                db.rollback()
                error = f"{subject}：{getattr(e, 'detail', '') or '布置失败'}"
                break
            assigned.append({"subject": subject, "assignmentId": int(res["assignment"]["id"]), "title": title, "questionCount": len(questions)})
        if assigned:
            implementation.audit(db, u, ASSIGN_ACTION, json.dumps({"studentId": sid, "helpIds": help_ids, "assignments": assigned}, ensure_ascii=False))
            db.commit()
        if error:
            raise HTTPException(409, f"布置未全部完成（{error}）" + ("；已布置：" + "、".join(a["subject"] for a in assigned) if assigned else ""))
        return {"assigned": assigned}

    app.include_router(router)
    app.state.homework_practice_views_installed = True
    app.state.homework_practice_views_router = router
    return router


__all__ = ["install_homework_practice_views"]
