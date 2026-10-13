"""Read-only views of the AI-assisted knowledge record (晚托作业助手).

student  GET /student/homework/knowledge          own flags
         GET /student/homework/history            own recent AI-assisted questions (90 days)
parent   GET /parent/children/{sid}/homework-knowledge   flags of a linked child only (no question text)
teacher  GET /teacher/homework/knowledge-summary  flags per student of the teacher's own classes
         GET /teacher/homework/ai-assists         recent AI-assisted questions of those students, with the AI's result

Everything is GET and behind the HOMEWORK_ASSISTANT flag (404 when it is off).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from changying.services.homework_knowledge import register_homework_knowledge_table
from changying.services.homework_knowledge_flags import knowledge_flags, thresholds
from changying.web.homework_assistant import require_enabled

LIST_LIMIT = 50


def _iso(value: Any) -> str:
    return value.strftime("%Y-%m-%d %H:%M") if hasattr(value, "strftime") else ""


def install_homework_knowledge_views(implementation: Any) -> APIRouter:
    app = implementation.app
    if getattr(app.state, "homework_knowledge_views_installed", False):
        return app.state.homework_knowledge_views_router

    helps = app.state.homework_tables["help_requests"]
    knowledge = register_homework_knowledge_table(implementation)
    User = implementation.User
    SchoolClass = implementation.SchoolClass
    ClassStudent = implementation.ClassStudent
    ParentStudent = implementation.ParentStudent
    current_user = implementation.current_user
    get_db = implementation.get_db
    need = implementation.need
    router = APIRouter(dependencies=[Depends(require_enabled)])

    def teacher_students(db: Any, teacher: Any) -> dict[int, str]:
        rows = db.execute(
            select(User.id, User.name)
            .join(ClassStudent, ClassStudent.student_id == User.id)
            .join(SchoolClass, SchoolClass.id == ClassStudent.class_id)
            .where(SchoolClass.teacher_id == teacher.id, SchoolClass.school_id == teacher.school_id, User.school_id == teacher.school_id)
        ).all()
        return {int(r[0]): str(r[1]) for r in rows}

    def state_label(raw: str | None) -> str:
        return {"answered": "AI 已讲解", "escalated": "已转老师", "resolved": "老师已处理", "confirmed": "未得到解答", "solving": "解答中"}.get(raw or "", "对话已过期")

    @router.get("/student/homework/knowledge")
    def my_knowledge(u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "student")
        return knowledge_flags(implementation, db, int(u.school_id), int(u.id))

    @router.get("/student/homework/history")
    def my_history(u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "student")
        rows = db.execute(
            select(helps.c.id, helps.c.question_text, helps.c.state, helps.c.verify_status, helps.c.created_at, knowledge.c.knowledge_key, knowledge.c.matched)
            .select_from(helps.outerjoin(knowledge, knowledge.c.help_id == helps.c.id))
            .where(helps.c.student_id == u.id, helps.c.school_id == u.school_id, helps.c.state.in_(("answered", "escalated", "resolved")))
            .order_by(helps.c.created_at.desc(), helps.c.id.desc())
            .limit(LIST_LIMIT)
        ).all()
        return {
            "items": [
                {"id": r.id, "questionText": r.question_text, "state": r.state, "stateLabel": state_label(r.state),
                 "knowledge": r.knowledge_key or "", "createdAt": _iso(r.created_at)}
                for r in rows
            ],
            "retentionDays": 90,
        }

    @router.get("/parent/children/{sid}/homework-knowledge")
    def child_knowledge(sid: int, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "parent")
        linked = db.scalar(select(ParentStudent.id).where(ParentStudent.parent_id == u.id, ParentStudent.student_id == sid).limit(1))
        child = db.scalar(select(User).where(User.id == sid, User.school_id == u.school_id, User.role == "student"))
        if not linked or child is None:
            raise HTTPException(404, "没有找到这个孩子")
        data = knowledge_flags(implementation, db, int(u.school_id), int(sid))
        data["unmatched"] = []        # parents see knowledge points only, never the child's questions
        data["childName"] = child.name
        return data

    @router.get("/teacher/homework/knowledge-summary")
    def class_knowledge(u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "teacher")
        students = teacher_students(db, u)
        out = []
        for student_id, name in sorted(students.items(), key=lambda kv: kv[1]):
            data = knowledge_flags(implementation, db, int(u.school_id), student_id)
            if data["assists"]:
                out.append({"studentId": student_id, "studentName": name, "assists": data["assists"], "open": data["open"], "flags": data["flags"]})
        out.sort(key=lambda r: (-r["open"], r["studentName"]))
        return {"students": out, "rule": thresholds()}

    @router.get("/teacher/homework/ai-assists")
    def class_assists(studentId: int | None = None, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "teacher")
        students = teacher_students(db, u)
        if studentId is not None:
            if studentId not in students:
                raise HTTPException(403, "该学生不在你管理的班级中")
            allowed = [studentId]
        else:
            allowed = list(students)
        if not allowed:
            return {"items": []}
        rows = db.execute(
            select(knowledge, helps.c.question_text, helps.c.state)
            .select_from(knowledge.outerjoin(helps, helps.c.id == knowledge.c.help_id))
            .where(knowledge.c.school_id == u.school_id, knowledge.c.student_id.in_(allowed))
            .order_by(knowledge.c.created_at.desc(), knowledge.c.id.desc())
            .limit(LIST_LIMIT)
        ).all()
        return {
            "items": [
                {
                    "studentId": r.student_id, "studentName": students.get(int(r.student_id), ""),
                    "helpId": r.help_id, "knowledge": r.knowledge_key, "matched": bool(r.matched),
                    "verify": r.verify_status, "state": r.state or "", "stateLabel": state_label(r.state),
                    "questionText": r.question_text or r.question_excerpt, "createdAt": _iso(r.created_at),
                }
                for r in rows
            ]
        }

    app.include_router(router)
    app.state.homework_knowledge_views_installed = True
    app.state.homework_knowledge_views_router = router
    return router


__all__ = ["install_homework_knowledge_views"]
