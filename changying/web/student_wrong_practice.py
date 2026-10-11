"""Student-initiated "same-knowledge re-practice" from the wrong-question book.

Reuses the existing pipeline end to end and calls no large model:

* questions are picked from the school's question bank with the same selector the
  teacher-side automatic practice uses (``select_student_practice_questions``);
* the practice is a normal single-recipient Paper -> Assignment -> Recipient chain,
  linked to the wrong-question record through ``ReinforcementLink``;
* grading and mastery stay exactly as they are: the student submits through
  ``/student/assignments/{aid}/submit`` and the installed
  ``_reinforcement_mastery_update`` decides ``active``/``mastered``.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select

from changying.web.v1_student_practice import select_student_practice_questions

STUDENT_REINFORCEMENT_SOURCE = "student_self_reinforcement"
PRACTICE_QUESTION_COUNT = 5
# Learning points are awarded per submission, so cap self-started rounds per school day.
MAX_NEW_PRACTICES_PER_DAY = 10
STUDENT_WRONG_PRACTICE_MARKER = "changying_student_wrong_practice_v1"

_ITEM_BADGE = (
    '<span class="badge ${x.status==="mastered"?"green":"amber"}">'
    '${x.status==="mastered"?"已掌握":"待巩固"}</span></div>'
)
_ITEM_BADGE_WITH_BUTTON = (
    '<span class="badge ${x.status==="mastered"?"green":"amber"}">'
    '${x.status==="mastered"?"已掌握":"待巩固"}</span>'
    '${x.status!=="mastered"&&x.questionID?`<button class="btn secondary" '
    'data-rewid="${x.id}" style="margin-left:8px;white-space:nowrap" '
    'title="连续两次全部答对才算掌握">再练 ${x.reinforcementCount||0}/2</button>`:""}</div>'
)
_WRONGBOOK_TAIL = '暂无错题记录。老师确认批改后会自动归档到这里。</div>"}</div>`;\n}'
_WRONGBOOK_TAIL_WITH_HANDLER = (
    '暂无错题记录。老师确认批改后会自动归档到这里。</div>"}</div>`;\n'
    ' $$("[data-rewid]").forEach(b=>b.onclick=async()=>{'
    "b.disabled=true;"
    "try{const r=await api(\"/student/wrong-questions/\"+b.dataset.rewid+\"/practice\","
    '{method:"POST"});await startAssignment(r.assignmentID)}'
    "catch(e){toast(e.message);b.disabled=false}});\n}"
)


def patch_wrongbook_html(html: str) -> str:
    """Add a per-item re-practice button to the student wrong-question page."""
    if STUDENT_WRONG_PRACTICE_MARKER in html:
        return html
    start = html.find("async function wrongbook(){")
    end = html.find("async function analytics(){", start)
    if start < 0 or end < 0:
        raise RuntimeError("student wrong-question page anchor not found")
    body = html[start:end]
    if _ITEM_BADGE not in body or _WRONGBOOK_TAIL not in body:
        raise RuntimeError("student wrong-question page item anchor not found")
    body = body.replace(_ITEM_BADGE, _ITEM_BADGE_WITH_BUTTON, 1)
    body = body.replace(_WRONGBOOK_TAIL, _WRONGBOOK_TAIL_WITH_HANDLER, 1)
    patched = html[:start] + body + html[end:]
    marker = f'<meta name="{STUDENT_WRONG_PRACTICE_MARKER}" content="1">'
    if "</head>" in patched:
        return patched.replace("</head>", marker + "</head>", 1)
    return marker + patched


def pick_practice_questions(
    rows: list[Any],
    *,
    source_question: Any,
    knowledge: str,
    blocked_ids: set[int],
    rotation: int,
    count: int = PRACTICE_QUESTION_COUNT,
) -> list[Any]:
    """Same-knowledge questions, never the original one, rotated between rounds."""
    chosen = select_student_practice_questions(
        rows,
        kind="module",
        knowledge=knowledge,
        count=50,
        textbook=str(source_question.textbook or ""),
    )
    pool = [
        q
        for q in chosen
        if int(q.id) != int(source_question.id) and int(q.id) not in blocked_ids
    ]
    if not pool:
        return []
    shift = (max(0, int(rotation)) * count) % len(pool)
    rotated = pool[shift:] + pool[:shift]
    return rotated[:count]


def install_student_wrong_practice(implementation: Any) -> None:
    app = implementation.app
    if getattr(app.state, "student_wrong_practice_installed", False):
        return

    WrongQuestionRecord = implementation.WrongQuestionRecord
    Question = implementation.Question
    Paper = implementation.Paper
    Assignment = implementation.Assignment
    AssignmentSubmissionSetting = implementation.AssignmentSubmissionSetting
    AssignmentRecipient = implementation.AssignmentRecipient
    ReinforcementLink = implementation.ReinforcementLink
    SchoolClass = implementation.SchoolClass
    current_user = implementation.current_user
    get_db = implementation.get_db
    router = APIRouter()

    def open_practice_for(db: Any, student_id: int, school_id: int, wid: int):
        links = db.scalars(
            select(ReinforcementLink).where(
                ReinforcementLink.school_id == school_id,
                ReinforcementLink.student_id == student_id,
                ReinforcementLink.completed_at.is_(None),
            )
        ).all()
        for link in links:
            try:
                linked = [int(x) for x in json.loads(link.wrong_ids_json or "[]")]
            except Exception:
                continue
            if wid not in linked:
                continue
            recipient = db.scalar(
                select(AssignmentRecipient).where(
                    AssignmentRecipient.assignment_id == link.assignment_id,
                    AssignmentRecipient.student_id == student_id,
                    AssignmentRecipient.source == STUDENT_REINFORCEMENT_SOURCE,
                )
            )
            if recipient:
                return db.get(Assignment, link.assignment_id)
        return None

    @router.post("/student/wrong-questions/{wid}/practice")
    def start_wrong_question_practice(
        wid: int,
        u: Any = Depends(current_user),
        db: Any = Depends(get_db),
    ):
        implementation.need(u, "student")
        record = db.scalar(
            select(WrongQuestionRecord).where(
                WrongQuestionRecord.id == wid,
                WrongQuestionRecord.school_id == u.school_id,
                WrongQuestionRecord.student_id == u.id,
            )
        )
        if not record:
            raise HTTPException(404, "错题记录不存在")
        if record.status != "active":
            raise HTTPException(400, "这道错题已经掌握，不需要再练")
        if not record.question_id:
            raise HTTPException(400, "这条错题没有对应的题库题目，暂不支持自助再练")

        existing = open_practice_for(db, u.id, u.school_id, wid)
        if existing is not None:
            paper = db.get(Paper, existing.paper_id)
            return {
                "ok": True,
                "reused": True,
                "assignmentID": existing.id,
                "paperID": existing.paper_id,
                "questionCount": len(
                    json.loads(paper.question_ids_json or "[]") if paper else []
                ),
            }

        source = db.scalar(
            select(Question).where(
                Question.id == record.question_id,
                Question.school_id == u.school_id,
            )
        )
        if not source:
            raise HTTPException(400, "原题已不在题库中，暂不支持自助再练")
        knowledge = (source.knowledge or source.unit or "").strip()
        if not knowledge:
            raise HTTPException(400, "这道题没有知识点信息，暂不支持自助再练")

        local_midnight = datetime.now(implementation.SCHOOL_TZ).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        day_start_utc = local_midnight.astimezone(timezone.utc).replace(tzinfo=None)
        started_today = db.scalar(
            select(func.count())
            .select_from(AssignmentRecipient)
            .where(
                AssignmentRecipient.school_id == u.school_id,
                AssignmentRecipient.student_id == u.id,
                AssignmentRecipient.source == STUDENT_REINFORCEMENT_SOURCE,
                AssignmentRecipient.assigned_at >= day_start_utc,
            )
        ) or 0
        if started_today >= MAX_NEW_PRACTICES_PER_DAY:
            raise HTTPException(429, "今天的错题再练次数已用完，明天再来继续吧")

        class_row = implementation.current_class_for(db, u.id, u.school_id)
        if not class_row or not class_row.teacher_id:
            raise HTTPException(400, "没有找到你当前所在的班级，请联系老师")

        rows = list(
            db.scalars(
                select(Question)
                .where(
                    Question.school_id == u.school_id,
                    Question.grade == source.grade,
                    Question.subject == source.subject,
                    Question.textbook == source.textbook,
                )
                .order_by(Question.id)
            ).all()
        )
        chosen = pick_practice_questions(
            rows,
            source_question=source,
            knowledge=knowledge,
            blocked_ids=implementation.protected_question_ids_for_student(db, u),
            rotation=int(record.reinforcement_count or 0),
        )
        if not chosen:
            raise HTTPException(400, "题库里暂时没有同一知识点的其他题目可以再练")

        question_ids = [int(q.id) for q in chosen]
        title = f"{knowledge} · 错题再练"[:160]
        paper = Paper(
            school_id=u.school_id,
            title=title,
            grade=int(source.grade),
            subject=str(source.subject or "")[:30],
            textbook=str(source.textbook or "")[:80],
            unit=str(source.unit or "")[:100],
            question_ids_json=json.dumps(question_ids),
            teacher_id=class_row.teacher_id,
        )
        db.add(paper)
        db.flush()
        due_date = (
            datetime.now(implementation.SCHOOL_TZ) + timedelta(days=3)
        ).date().isoformat()
        assignment = Assignment(
            school_id=u.school_id,
            title=title,
            class_id=class_row.id,
            paper_id=paper.id,
            due_date=due_date,
        )
        db.add(assignment)
        db.flush()
        db.add(
            AssignmentSubmissionSetting(
                school_id=u.school_id,
                assignment_id=assignment.id,
                mode="quiz",
                instructions="同一知识点的再练，连续两次全部答对才算掌握这道错题。",
            )
        )
        implementation.ensure_recipient(
            db, assignment, u.id, STUDENT_REINFORCEMENT_SOURCE
        )
        db.add(
            ReinforcementLink(
                school_id=u.school_id,
                assignment_id=assignment.id,
                student_id=u.id,
                wrong_ids_json=json.dumps([int(record.id)]),
            )
        )
        implementation.audit(
            db,
            u,
            "student.wrong_question.practice",
            f"wrong={record.id}:assignment={assignment.id}:questions={len(question_ids)}",
        )
        db.commit()
        db.refresh(assignment)
        return {
            "ok": True,
            "reused": False,
            "assignmentID": assignment.id,
            "paperID": paper.id,
            "questionCount": len(question_ids),
        }

    app.include_router(router)
    implementation.INDEX_HTML = patch_wrongbook_html(implementation.INDEX_HTML)
    app.state.student_wrong_practice_installed = True


__all__ = [
    "MAX_NEW_PRACTICES_PER_DAY",
    "PRACTICE_QUESTION_COUNT",
    "STUDENT_REINFORCEMENT_SOURCE",
    "STUDENT_WRONG_PRACTICE_MARKER",
    "install_student_wrong_practice",
    "patch_wrongbook_html",
    "pick_practice_questions",
]
