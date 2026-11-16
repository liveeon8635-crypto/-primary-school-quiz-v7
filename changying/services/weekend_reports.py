"""Weekend lesson facts and per-student learning reports.

Facts are computed deterministically from the original weekend tables and never
written back. Report texts are drafts a teacher edits; parents only read the
version the teacher published. Counting rules (see the teacher page):

- the denominator is every question of the lesson (choice + written), per pupil;
- an unanswered question is "未提交", a submitted but unreviewed one "待批" and
  neither is counted as wrong; "部分正确" stays separate and is never converted
  into a score;
- a question the teacher marked 课后题 and nobody has handed in yet is "课后题未交", outside the denominator;
- one question counts once however often it was resubmitted; the original rows
  keep only the final answer, so first and revised answers are not distinguished;
- hints and submission times are reported as recorded, never as "不独立" or time spent;
- weekend points are ledger points, not marks, and only shown once settled.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select

from changying.services.weekend_answers import option_text

STATUS_LABEL = {"unsubmitted": "未提交", "pending": "待批", "correct": "正确", "partial": "部分正确", "revise": "需订正",
                "later": "课后题未交"}
# Sections the system writes; "observation" and the report comment are the teacher's own words.
AUTO_SECTIONS = ("content", "completion", "mastery", "issues", "consolidation", "homework", "followup")
SECTION_TITLES = {
    "content": "本节学习内容与训练目标", "completion": "作业完成情况及批改结果", "mastery": "已表现出的掌握点",
    "issues": "最需要改进的问题", "consolidation": "课堂订正与巩固", "observation": "教师课堂观察",
    "homework": "课后任务", "followup": "下节课跟进计划",
}
SECTION_KEYS = AUTO_SECTIONS[:5] + ("observation",) + AUTO_SECTIONS[5:]
TEXT_LIMIT = 1500


def local_dt(impl: Any, value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=timezone.utc).astimezone(impl.SCHOOL_TZ)


def local_date(impl: Any, row: Any) -> str:
    started = local_dt(impl, row.started_at)
    return started.strftime("%Y-%m-%d") if started else ""


def unit_text(unit: str | None) -> str:
    """The lesson unit, without the placeholder new weekend lessons start with."""
    unit = str(unit or "").strip()
    return "" if unit == "待配置单元" else unit


WORK_STATUS_LABEL = {"submitted": "已交", "unsubmitted": "未交", "pending": "待批改"}


def week_window(day: str) -> tuple[str, str]:
    """The natural Monday..Sunday window of a report day; the week a lesson belongs to."""
    try:
        start = datetime.strptime(str(day or ""), "%Y-%m-%d").date() - timedelta(days=datetime.strptime(str(day or ""), "%Y-%m-%d").weekday())
    except ValueError:
        start = datetime.now(timezone.utc).date()
        start = start - timedelta(days=start.weekday())
    return start.isoformat(), (start + timedelta(days=6)).isoformat()


def week_work_map(impl: Any, db: Any, *, school_id: int, student_ids: list[int], day: str) -> dict[int, dict[str, Any]]:
    """Ordinary assignments each pupil received in the report's week (Mon..Sun); read-only, two queries.

    An assignment counts when the pupil is a recipient of it and its due date (or, without
    one, its creation date) falls inside the window. The latest submission decides the state:
    no submission "未交", a submission with nothing graded "待批改", otherwise "已交" with the
    share of correct questions. Ordinary homework is never attached to a lesson.
    """
    start, end = week_window(day)
    ids = sorted({int(s) for s in student_ids})
    out = {sid: {"weekStart": start, "weekEnd": end, "items": [], "counts": {"total": 0, "submitted": 0, "unsubmitted": 0, "pending": 0}, "rate": None}
           for sid in ids}
    if not ids:
        return out
    recipient, assignment, submission = impl.AssignmentRecipient, impl.Assignment, impl.Submission
    latest: dict[tuple[int, int], Any] = {}
    for s in db.execute(select(submission.assignment_id, submission.student_id, submission.correct, submission.total, submission.submitted_at)
                        .where(submission.school_id == school_id, submission.student_id.in_(ids), submission.assignment_id.isnot(None))
                        .order_by(submission.submitted_at, submission.id)):
        latest[(int(s.student_id), int(s.assignment_id))] = s
    rows = db.execute(select(recipient.student_id, assignment.id, assignment.title, assignment.due_date, assignment.created_at)
                      .select_from(recipient).join(assignment, assignment.id == recipient.assignment_id)
                      .where(recipient.school_id == school_id, recipient.student_id.in_(ids))
                      .order_by(assignment.due_date, assignment.id))
    for row in rows:
        due = str(row.due_date or "")[:10]
        created = local_dt(impl, row.created_at)
        day_key = due or (created.strftime("%Y-%m-%d") if created is not None else "")
        if not (start <= day_key <= end):
            continue
        block = out[int(row.student_id)]
        s = latest.get((int(row.student_id), int(row.id)))
        total = int(getattr(s, "total", 0) or 0) if s is not None else 0
        correct = int(getattr(s, "correct", 0) or 0) if s is not None else 0
        status = "unsubmitted" if s is None else ("pending" if not total else "submitted")
        when = local_dt(impl, s.submitted_at) if s is not None else None
        block["items"].append({"assignmentId": int(row.id), "title": str(row.title or ""), "due": due, "status": status,
                               "statusLabel": WORK_STATUS_LABEL[status], "correct": correct, "total": total,
                               "rate": round(correct * 100 / total) if total else None,
                               "submittedAt": when.strftime("%m-%d %H:%M") if when is not None else ""})
    for block in out.values():
        items = block["items"]
        block["counts"] = {"total": len(items), "submitted": sum(1 for i in items if i["status"] != "unsubmitted"),
                           "unsubmitted": sum(1 for i in items if i["status"] == "unsubmitted"),
                           "pending": sum(1 for i in items if i["status"] == "pending")}
        graded = [i for i in items if i["rate"] is not None]
        block["rate"] = round(sum(i["correct"] for i in graded) * 100 / sum(i["total"] for i in graded)) if graded else None
    return out


def parent_week_work(block: dict[str, Any]) -> dict[str, Any]:
    """What a parent may see of the week's ordinary homework: completion and accuracy, never the questions."""
    return {"weekStart": block["weekStart"], "weekEnd": block["weekEnd"], "counts": block["counts"], "rate": block["rate"],
            "items": [{k: i[k] for k in ("title", "status", "statusLabel", "rate", "due")} for i in block["items"]]}


def material_title(material: str) -> str:
    """A short name for a reading passage so parents know which text a task refers to."""
    first = next((line.strip() for line in str(material or "").splitlines() if line.strip()), "")
    first = first.strip("《》「」 ")
    return first if len(first) <= 18 else first[:18] + "…"


def _short(text: str, limit: int = 60) -> str:
    line = " ".join(str(text or "").split("\n\n")[-1].split())
    return line if len(line) <= limit else line[:limit] + "…"


def _attempts(impl: Any, db: Any, row: Any) -> dict[tuple[int, str, int], int]:
    """Latest audited attempt count per (pupil, kind, question); see weekend_submissions."""
    log = impl.AuditLog
    out: dict[tuple[int, str, int], int] = {}
    pattern = re.compile(r"^weekend\.submit\.(choice|written)\.(\d+)\.(\d+)$")
    for uid, action, detail in db.execute(select(log.user_id, log.action, log.detail).where(
            log.school_id == row.school_id, log.action.like(f"weekend.submit.%.{int(row.id)}.%")).order_by(log.id)):
        found = pattern.match(str(action or ""))
        if not found or int(found.group(2)) != int(row.id):
            continue
        try:
            out[(int(uid), found.group(1), int(found.group(3)))] = int(json.loads(detail)["attempt"])
        except Exception:  # noqa: BLE001 - an unreadable audit detail leaves the count unknown
            continue
    return out


def session_facts(impl: Any, db: Any, row: Any) -> dict[str, Any]:
    """Everything the class summary and the reports need for one weekend lesson; read-only."""
    from changying.services.lesson_written import template_marks
    from changying.services.weekend_roster import session_class, session_roster
    md = impl.Base.metadata
    answers_t, written_q, written_s = md.tables["weekend_answers"], md.tables["weekend_written_questions"], md.tables["weekend_written_submissions"]
    hint_t, peer_t, awards_t = md.tables["weekend_written_hint_log"], md.tables["weekend_peer_help"], md.tables["weekend_awards"]
    TQ = impl.TeachingQuestion
    lesson = db.get(impl.TeachingLesson, row.lesson_id)
    bound = session_class(impl, db, row)
    members = session_roster(impl, db, row)

    questions: list[dict[str, Any]] = []
    choice_rows = db.scalars(select(TQ).where(TQ.school_id == row.school_id, TQ.lesson_id == row.lesson_id,
                                              TQ.active.is_(True)).order_by(TQ.id)).all()
    for q in choice_rows:
        try:
            options = [option_text(x) for x in json.loads(q.options_json or "[]")]
        except Exception:  # noqa: BLE001
            options = []
        ci = int(q.correct_index)
        questions.append({"key": f"c{q.id}", "kind": "choice", "id": int(q.id), "stem": _short(q.stem),
                          "knowledge": str(q.knowledge or "").strip(), "options": options, "correctIndex": ci,
                          "task": _short(q.stem, 80), "material": "", "full": str(q.stem or ""),
                          "reference": options[ci] if 0 <= ci < len(options) else "", "explanation": str(q.explanation or "")})
    # Written questions take the 考点 / 课后题 marks the teacher set once on the lesson's template (习题审改);
    # the lesson goal is never substituted for a missing one.
    marks = template_marks(db, written_q, row.school_id, row.teacher_id, row.lesson_id)
    for q in db.execute(select(written_q).where(written_q.c.session_id == row.id, written_q.c.school_id == row.school_id,
                                                written_q.c.teacher_id == row.teacher_id).order_by(written_q.c.id)):
        material, _, line = str(q.stem or "").rpartition("\n\n")
        mark = marks.get(str(q.stem or ""), {})
        questions.append({"key": f"w{q.id}", "kind": "written", "id": int(q.id), "stem": _short(q.stem), "knowledge": mark.get("knowledge", ""),
                          "task": _short(line, 80), "material": material_title(material), "full": str(q.stem or ""),
                          "reference": str(q.reference or ""), "explanation": "", "afterClass": bool(mark.get("afterClass")),
                          "templateId": mark.get("id")})
    for no, q in enumerate(questions, 1):
        q["no"] = no

    def member(student_id: int) -> bool:
        return bound is None or student_id in members

    choice = {(int(a.student_id), int(a.question_id)): a for a in db.execute(
        select(answers_t).where(answers_t.c.session_id == row.id, answers_t.c.school_id == row.school_id)) if member(int(a.student_id))}
    written = {(int(a.student_id), int(a.question_id)): a for a in db.execute(
        select(written_s.c.id, written_s.c.student_id, written_s.c.question_id, written_s.c.answer_text, written_s.c.result,
               written_s.c.comment, written_s.c.revision, written_s.c.submitted_at, written_s.c.reviewed_at,
               (written_s.c.photo.isnot(None)).label("has_photo"))
        .where(written_s.c.session_id == row.id, written_s.c.school_id == row.school_id)) if member(int(a.student_id))}
    hints = {(int(s), int(q)): int(level) for s, q, level in db.execute(
        select(hint_t.c.student_id, hint_t.c.question_id, func.max(hint_t.c.level))
        .where(hint_t.c.session_id == row.id, hint_t.c.school_id == row.school_id).group_by(hint_t.c.student_id, hint_t.c.question_id))}
    attempts = _attempts(impl, db, row)
    peers = list(db.execute(select(peer_t).where(peer_t.c.session_id == row.id, peer_t.c.school_id == row.school_id).order_by(peer_t.c.id)))
    awards: dict[int, dict[str, int]] = {}
    for a in db.execute(select(awards_t).where(awards_t.c.session_id == row.id, awards_t.c.school_id == row.school_id)):
        awards.setdefault(int(a.student_id), {})[str(a.kind)] = int(a.points)
    settled = bool(awards)
    no_of = {q["key"]: q["no"] for q in questions}

    student_ids = set(members) | {s for s, _ in choice} | {s for s, _ in written}
    week = week_work_map(impl, db, school_id=int(row.school_id), student_ids=[int(s) for s in student_ids], day=local_date(impl, row))
    students: dict[int, dict[str, Any]] = {}
    for sid in sorted(student_ids, key=lambda x: (members.get(x, ("学生",))[0], x)):
        items = []
        for q in questions:
            item: dict[str, Any] = {"key": q["key"], "no": q["no"], "kind": q["kind"], "knowledge": q["knowledge"], "attempts": 0, "hint": 0}
            if q["kind"] == "choice":
                a = choice.get((sid, q["id"]))
                if a is None:
                    item["status"] = "unsubmitted"
                else:
                    sel = int(a.selected)
                    item.update(status="correct" if a.correct else "revise", hint=int(a.max_hint or 0),
                                attempts=attempts.get((sid, "choice", q["id"]), 1),
                                answer=(chr(65 + sel) + ". " + q["options"][sel]) if 0 <= sel < len(q["options"]) else str(sel),
                                submittedAt=a.created_at)
            else:
                a = written.get((sid, q["id"]))
                item["hint"] = hints.get((sid, q["id"]), 0)
                if a is None:
                    item["status"] = "later" if q.get("afterClass") else "unsubmitted"
                else:
                    item.update(status=a.result if a.result in ("pending", "correct", "partial", "revise") else "pending",
                                attempts=attempts.get((sid, "written", q["id"]), 1), answer=str(a.answer_text or ""),
                                hasPhoto=bool(a.has_photo), submissionId=int(a.id), comment=str(a.comment or ""),
                                revision=int(a.revision), submittedAt=a.submitted_at, reviewedAt=a.reviewed_at)
            items.append(item)
        counts = {k: sum(1 for i in items if i["status"] == k) for k in STATUS_LABEL}
        counts["total"] = len(items) - counts["later"]
        counts["submitted"] = counts["total"] - counts["unsubmitted"]
        explained, followups = [], []
        for p in peers:
            key = f"w{-int(p.question_id)}" if int(p.question_id) < 0 else f"c{int(p.question_id)}"
            if key not in no_of:
                continue
            if int(p.tutor_id) == sid and no_of[key] not in explained:
                explained.append(no_of[key])
            if int(p.question_id) > 0 and int(p.tutee_id) == sid and p.followup_json:
                followups.append({"no": no_of[key], "correct": p.followup_correct})
        participated = bool(counts["submitted"] or explained or followups or any(i["hint"] for i in items))
        parts = awards.get(sid, {})
        students[sid] = {"studentId": sid, "name": members.get(sid, ("学生",))[0], "participated": participated, "items": items,
                         "counts": counts, "explained": sorted(explained), "followups": followups,
                         "weekWork": week.get(sid, {"weekStart": "", "weekEnd": "", "items": [], "counts": {"total": 0, "submitted": 0, "unsubmitted": 0, "pending": 0}, "rate": None}),
                         "points": {"settled": settled, "total": sum(parts.values()), "parts": parts}}
    return {"sessionId": int(row.id), "title": row.title, "status": row.status, "date": local_date(impl, row),
            "subject": lesson.subject if lesson else "", "lessonTitle": lesson.title if lesson else row.title,
            "unit": unit_text(lesson.unit if lesson else ""), "coreTarget": (lesson.core_target or "") if lesson else "",
            "className": bound.class_name if bound is not None else "", "settled": settled, "questions": questions,
            "students": students, "cutoff": datetime.now(impl.SCHOOL_TZ).strftime("%Y-%m-%d %H:%M")}


def class_summary(facts: dict[str, Any]) -> dict[str, Any]:
    pupils = list(facts["students"].values())
    total = {k: sum(p["counts"][k] for p in pupils) for k in ("total", "submitted", *STATUS_LABEL)}
    per_question = []
    for q in facts["questions"]:
        states = [next(i for i in p["items"] if i["key"] == q["key"])["status"] for p in pupils]
        per_question.append({"no": q["no"], "kind": q["kind"], "stem": q["stem"], "knowledge": q["knowledge"] or f"「{q['task']}」（考点待教师补充）",
                             **{k: states.count(k) for k in STATUS_LABEL}})
    knowledge: dict[str, dict[str, Any]] = {}
    for q in per_question:
        k = knowledge.setdefault(q["knowledge"], {"knowledge": q["knowledge"], "questions": [], **{s: 0 for s in STATUS_LABEL}})
        k["questions"].append(q["no"])
        for s in STATUS_LABEL:
            k[s] += q[s]
    return {"pupils": len(pupils), "participated": sum(1 for p in pupils if p["participated"]), "counts": total,
            "questions": per_question, "knowledge": list(knowledge.values()),
            "pendingReview": total["pending"], "hintUses": sum(1 for p in pupils for i in p["items"] if i["hint"]),
            "explained": sum(len(p["explained"]) for p in pupils),
            "followups": {"done": sum(1 for p in pupils for f in p["followups"] if f["correct"] is not None),
                          "correct": sum(1 for p in pupils for f in p["followups"] if f["correct"]),
                          "open": sum(1 for p in pupils for f in p["followups"] if f["correct"] is None)}}


def student_facts(facts: dict[str, Any], student_id: int) -> dict[str, Any] | None:
    pupil = facts["students"].get(student_id)
    if pupil is None:
        return None
    return {k: facts[k] for k in ("sessionId", "date", "subject", "lessonTitle", "unit", "coreTarget", "className", "settled", "cutoff")} | {
        "questions": [{k: q[k] for k in ("key", "no", "kind", "stem", "knowledge", "task", "material")} for q in facts["questions"]],
        **{k: pupil[k] for k in ("studentId", "name", "participated", "counts", "explained", "followups", "points", "weekWork")},
        "items": [{k: i.get(k, "") for k in ("key", "no", "kind", "status", "attempts", "hint", "knowledge", "answer", "comment")} for i in pupil["items"]]}


def source_questions(facts: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Teacher-only originals (full stem, options, reference) for generating variants; never sent to parents."""
    return {q["key"]: {k: q.get(k) for k in ("kind", "full", "options", "reference", "explanation", "knowledge", "task", "material")}
            for q in facts["questions"]}


def fingerprint(parts: list[dict[str, Any]]) -> str:
    """Changes when an answer, review, hint, follow-up or award changes; not on the cutoff time."""
    stable = [{k: v for k, v in p.items() if k != "cutoff"} for p in parts]
    return hashlib.sha256(json.dumps(stable, ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest()


def parent_facts(part: dict[str, Any]) -> dict[str, Any]:
    """What a parent may see: their child's own counts per section, no answers, references, photos or class data."""
    out = {k: part[k] for k in ("sessionId", "date", "subject", "lessonTitle", "unit", "counts")}
    if part["points"]["settled"]:
        out["points"] = part["points"]["total"]
    out["weekWork"] = parent_week_work(part["weekWork"])
    return out


def evidence_items(parts: list[dict[str, Any]], previous: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """One entry per reviewed question: the knowledge point, the task, what the pupil did and why (when known).

    Knowledge comes from the question itself or from the teacher. AI suggestions are kept apart
    (``knowledgeSource == "ai"``) and are not used in parent text until the teacher confirms them.
    """
    kept = {e["key"]: e for e in (previous or []) if isinstance(e, dict) and e.get("key")}
    out = []
    for part in parts:
        questions = {q["key"]: q for q in part["questions"]}
        for item in part["items"]:
            if item["status"] not in ("correct", "partial", "revise"):
                continue
            q = questions[item["key"]]
            key = f"{part['sessionId']}:{item['key']}"
            e = {"key": key, "sessionId": part["sessionId"], "subject": part["subject"], "no": item["no"], "kind": item["kind"],
                 "status": item["status"], "task": q.get("task") or q["stem"], "material": q.get("material") or "",
                 "answer": str(item.get("answer") or "")[:300], "comment": str(item.get("comment") or "")[:300],
                 "knowledge": item["knowledge"], "knowledgeSource": "question" if item["knowledge"] else "none",
                 "cause": "", "causeSource": ""}
            old = kept.get(key)
            if old:
                if e["knowledgeSource"] == "none" and old.get("knowledgeSource") in ("teacher", "ai") and old.get("knowledge"):
                    e["knowledge"], e["knowledgeSource"] = str(old["knowledge"])[:80], old["knowledgeSource"]
                if old.get("causeSource") in ("teacher", "ai") and old.get("cause") and item["status"] != "correct":
                    e["cause"], e["causeSource"] = str(old["cause"])[:200], old["causeSource"]
            out.append(e)
    return out


def topic(e: dict[str, Any]) -> str:
    """The confirmed knowledge point, or the concrete task when none is confirmed; never a bare question number."""
    if e.get("knowledge") and e.get("knowledgeSource") in ("question", "teacher"):
        return str(e["knowledge"])
    return f"「{e['task']}」"


def describe(e: dict[str, Any]) -> str:
    """A sentence a parent understands without the paper: knowledge, task, performance, cause (or that it needs checking)."""
    confirmed = e.get("knowledge") and e.get("knowledgeSource") in ("question", "teacher")
    head = (f"{e['knowledge']}（题目任务：{e['task']}）" if confirmed else f"题目任务「{e['task']}」")
    if e.get("material") and e.get("subject") == "语文":
        head = f"阅读材料《{e['material']}》—" + head
    if e["status"] == "correct":
        tail = "作答正确"
        if e.get("comment"):
            tail += f"，老师批注：{e['comment']}"
    else:
        if e["kind"] == "choice":
            tail = f"选择了「{e['answer']}」，未选出正确答案" if e.get("answer") else "选择有误"
        else:
            tail = "答对了一部分" if e["status"] == "partial" else "答案需要订正"
        if e.get("causeSource") == "teacher" and e.get("cause"):
            tail += f"；{e['cause']}"
        elif e.get("comment"):
            tail += f"；老师批注：{e['comment']}"
        else:
            tail += "；具体错因需教师核实"
    return f"{head}（第{e['no']}题）：{tail}。"


def weak_groups(evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Wrong and partly right answers merged by lesson and knowledge point, so one weakness is practised once."""
    groups: dict[str, dict[str, Any]] = {}
    for e in sorted(evidence, key=lambda x: (x["status"] != "revise", x["sessionId"], x["no"])):
        if e["status"] not in ("revise", "partial"):
            continue
        confirmed = e.get("knowledge") and e.get("knowledgeSource") in ("question", "teacher")
        gkey = f"{e['sessionId']}:" + (f"k:{e['knowledge']}" if confirmed else f"q:{e['key']}")
        g = groups.setdefault(gkey, {"key": gkey, "sessionId": e["sessionId"], "subject": e["subject"], "topic": topic(e),
                                     "knowledge": e["knowledge"] if confirmed else "", "items": []})
        g["items"].append(e)
    return list(groups.values())


def glance(parts: list[dict[str, Any]], evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Per lesson, the confirmed points the pupil got right and the points to work on, for the top of the report."""
    out = []
    for part in parts:
        mine = [e for e in evidence if e["sessionId"] == part["sessionId"]]
        weak = [g["topic"] for g in weak_groups(mine)]
        good: list[str] = []
        for e in mine:
            k = e.get("knowledge")
            if e["status"] == "correct" and k and e.get("knowledgeSource") in ("question", "teacher") and k not in good and k not in weak:
                good.append(k)
        out.append({"subject": part["subject"], "good": good[:6], "weak": weak[:4], "compare": ""})
    return out


def compare_text(before: dict[str, Any], now: dict[str, Any]) -> str:
    """The pupil against his own previous published lesson of the subject; never against other pupils."""
    b, n = before.get("counts") or {}, now.get("counts") or {}
    if not b.get("submitted") or not n.get("submitted"):
        return ""
    fix_b, fix_n = b.get("revise", 0) + b.get("partial", 0), n.get("revise", 0) + n.get("partial", 0)
    return (f"和孩子自己上次（{before.get('date', '')}《{before.get('lessonTitle', '')}》）比：完全正确 {b.get('correct', 0)}/{b['submitted']} 题 → "
            f"{n.get('correct', 0)}/{n['submitted']} 题；需要订正或补全 {fix_b} 题 → {fix_n} 题。")


def draft_section(part: dict[str, Any], evidence: list[dict[str, Any]] | None = None) -> dict[str, str]:
    """Deterministic draft for one lesson; only states what the records show."""
    c, items = part["counts"], part["items"]
    mine = [e for e in (evidence if evidence is not None else evidence_items([part])) if e["sessionId"] == part["sessionId"]]
    content = f"《{part['lessonTitle']}》" + (f"（{part['unit']}）" if part["unit"] else "") + "。"
    content += f"训练目标：{part['coreTarget']}。" if part["coreTarget"] else "训练目标以课堂安排为准。"
    completion = (f"本节应做 {c['total']} 题，已提交 {c['submitted']} 题，未提交 {c['unsubmitted']} 题。"
                  f"已批改结果：正确 {c['correct']} 题，部分正确 {c['partial']} 题，需订正 {c['revise']} 题；"
                  f"待老师批改 {c['pending']} 题（待批改不算错误）。")
    if c.get("later"):
        completion += f"另有 {c['later']} 道课后题还没交，不算在本节应做题里，交了以后再更新。"
    right = [e for e in mine if e["status"] == "correct"]
    mastery = "\n".join(describe(e) for e in right[:6]) if right else "本节已批改的题目中暂时没有完全正确的作答，掌握情况需要后续练习确认。"
    if c["pending"]:
        mastery += f"\n另有 {c['pending']} 题待批改，批改后再确认。"
    groups = weak_groups(mine)
    if groups:
        issues = "\n".join(describe(e) for g in groups[:2] for e in g["items"])
        if len(groups) > 2:
            issues += "\n其余需订正的内容：" + "、".join(g["topic"] for g in groups[2:]) + "。"
    else:
        issues = "本节已批改的题目中没有需要订正的题。" if c["submitted"] > c["pending"] else "暂无已批改结果，批改后补充。"
    consolidation = []
    if part["followups"]:
        consolidation += [f"第{f['no']}题讲解后的同类巩固题" + ("做对" if f["correct"] else "未做对" if f["correct"] is False else "尚未完成")
                          for f in part["followups"]]
    if part["explained"]:
        consolidation.append("受老师邀请为同学讲解第" + "、".join(str(n) for n in part["explained"]) + "题的思路")
    homework = [f"订正{g['topic']}：对照老师批注重新完成原题，写出依据或过程。" for g in groups]
    if groups:
        homework.append("针对性练习：老师会按上面的薄弱点出新题，审核后布置到孩子的“作业”里，完成情况见下方“针对性练习”。")
    tasks = {q["key"]: q.get("task") or q["stem"] for q in part["questions"]}
    unsubmitted = [i for i in items if i["status"] == "unsubmitted"]
    if unsubmitted:
        homework.append("补做未提交的题目：" + "；".join(f"「{tasks[i['key']]}」（第{i['no']}题）" for i in unsubmitted) + "。")
    later = [i for i in items if i["status"] == "later"]
    if later:
        homework.append("完成课后题并交给老师：" + "；".join(f"「{tasks[i['key']]}」（第{i['no']}题）" for i in later) + "。")
    if not homework:
        homework.append(f"回顾《{part['lessonTitle']}》课堂例题的方法，下节课前讲给家长听。")
    week = part.get("weekWork") or {}
    if week.get("items"):
        wc = week.get("counts") or {}
        line = (f"本周普通作业（{week['weekStart']} 至 {week['weekEnd']}）：应做 {wc.get('total', 0)} 份，"
                f"已交 {wc.get('submitted', 0)} 份，未交 {wc.get('unsubmitted', 0)} 份，待批改 {wc.get('pending', 0)} 份")
        line += f"，已批改的正确率 {week['rate']}%。" if week.get("rate") is not None else "。"
        missed = [i for i in week["items"] if i["status"] == "unsubmitted"]
        if missed:
            line += "未交：" + "、".join(f"「{i['title']}」" for i in missed[:6]) + ("等" if len(missed) > 6 else "") + "，请在本周内补齐。"
        homework.insert(max(0, len(homework) - 1), line)
    homework.append("家长配合：请孩子讲一讲订正或解题思路，家长只听和提问，不代写答案。")
    targets = "、".join(g["topic"] for g in groups[:2])
    followup = (f"下节课先用同类题检查{targets}的订正情况。" if targets else "下节课在新内容前用 1 道题回顾本节方法。")
    return {"content": content, "completion": completion, "mastery": mastery, "issues": issues,
            "consolidation": "；".join(consolidation) + ("。" if consolidation else ""), "observation": "",
            "homework": "\n".join(homework), "followup": followup}


def suggestion_prompt(parts: list[dict[str, Any]], evidence: list[dict[str, Any]], sources: dict[str, dict[str, Any]]) -> str:
    """Anonymised: no names or class names. Asks only for knowledge points and evidenced causes for the teacher to check."""
    need = [e for e in evidence if e["knowledgeSource"] == "none" or (e["status"] != "correct" and not e["cause"])]
    rows = []
    for e in need:
        src = sources.get(e["key"].split(":", 1)[1], {})
        rows.append({"key": e["key"], "科目": e["subject"], "原题": str(src.get("full") or "")[:1500], "选项": src.get("options") or [],
                     "参考答案或评分要点": str(src.get("reference") or "")[:600], "学生答案": e["answer"], "批改结果": STATUS_LABEL[e["status"]],
                     "教师批注": e["comment"], "已有考点": e["knowledge"] if e["knowledgeSource"] == "question" else ""})
    return ("你是小学教研员。根据下列原题、参考答案、学生答案和教师批注，为每题给出：\n"
            "1. knowledge：这道题考查的具体知识或能力（如“旋转后对应点的位置判断”“结合人物言行概括人物品质”），不能写课程总目标或“阅读理解”这类笼统说法；已有考点时原样返回。\n"
            "2. cause：只有学生答案或教师批注能直接支持时，写一句具体错因（如“缺少原文依据”）；证据不足写空字符串，不要猜测。答对的题 cause 为空。\n"
            "不得评价学生态度或行为。\n题目：" + json.dumps(rows, ensure_ascii=False) +
            '\n只输出 JSON：{"items":[{"key":"","knowledge":"","cause":""}]}')


def apply_suggestions(evidence: list[dict[str, Any]], data: Any) -> int:
    """Store AI suggestions as unconfirmed; teacher and question knowledge are never replaced."""
    items = data.get("items") if isinstance(data, dict) else None
    if not isinstance(items, list):
        raise ValueError("AI suggestions missing")
    by_key = {e["key"]: e for e in evidence}
    used = 0
    for item in items:
        e = by_key.get(str((item or {}).get("key") or ""))
        if e is None:
            continue
        knowledge = str(item.get("knowledge") or "").strip()[:80]
        cause = str(item.get("cause") or "").strip()[:200]
        if knowledge and e["knowledgeSource"] == "none":
            e["knowledge"], e["knowledgeSource"] = knowledge, "ai"
            used += 1
        if cause and e["status"] != "correct" and e["causeSource"] not in ("teacher",):
            e["cause"], e["causeSource"] = cause, "ai"
            used += 1
    return used


def apply_teacher_evidence(evidence: list[dict[str, Any]], edits: Any) -> list[dict[str, Any]]:
    """Teacher-confirmed knowledge points and causes; an unconfirmed edit stays a suggestion."""
    by_key = {e["key"]: dict(e) for e in evidence}
    for edit in edits if isinstance(edits, list) else []:
        if not isinstance(edit, dict) or str(edit.get("key") or "") not in by_key:
            continue
        e = by_key[str(edit["key"])]
        if not edit.get("confirmed"):
            continue
        knowledge = str(edit.get("knowledge") or "").strip()[:80]
        cause = str(edit.get("cause") or "").strip()[:200]
        if e["knowledgeSource"] != "question":
            e["knowledge"], e["knowledgeSource"] = (knowledge, "teacher") if knowledge else ("", "none")
        if e["status"] != "correct":
            e["cause"], e["causeSource"] = (cause, "teacher") if cause else ("", "")
    return [by_key[e["key"]] for e in evidence]


def clean_sections(sections: Any, parts: list[dict[str, Any]]) -> list[dict[str, str]]:
    if not isinstance(sections, list) or len(sections) != len(parts):
        raise ValueError("每节课需要一份内容")
    out = []
    for section, part in zip(sections, parts):
        if not isinstance(section, dict):
            raise ValueError("内容格式不正确")
        clean = {k: str(section.get(k) or "").replace("\r\n", "\n").strip()[:TEXT_LIMIT] for k in SECTION_KEYS}
        clean["sessionId"] = part["sessionId"]
        out.append(clean)
    return out


# ---------------------------------------------------------------- targeted practice (variants of the pupil's own mistakes)
PRACTICE_TYPES = ("single_choice", "true_false", "fill_blank", "calculation", "short_answer")
PRACTICE_LABEL = {"none": "未生成", "review": "待教师审核", "assigning": "正在布置", "partial": "部分已布置",
                  "assigned": "已布置", "submitted": "已提交", "graded": "已批改"}
FIGURE_WORDS = ("如图", "下图", "图中", "看图")


def _norm(text: str) -> str:
    return re.sub(r"[\s，。、；：！？,.;:!?（）()「」“”\"'《》【】\[\]_—-]", "", str(text or ""))


def default_count(group: dict[str, Any]) -> int:
    return 3 if len(group["items"]) > 1 else 2


def practice_prompt(groups: list[dict[str, Any]], sources: dict[str, dict[str, Any]], grade: int) -> str:
    """One pupil's own mistakes, anonymised; the model writes new variants, never the original question."""
    rows = []
    for g in groups:
        rows.append({"key": g["key"], "科目": g["subject"], "年级": grade, "薄弱点": g["knowledge"] or "（未确认，请根据原题判断具体考点）",
                     "题数": g["count"], "错题依据": [{
                         "原题": str(sources.get(e["key"].split(":", 1)[1], {}).get("full") or "")[:2000],
                         "原题选项": sources.get(e["key"].split(":", 1)[1], {}).get("options") or [],
                         "参考答案或评分要点": str(sources.get(e["key"].split(":", 1)[1], {}).get("reference") or "")[:600],
                         "学生答案": e["answer"], "批改结果": STATUS_LABEL[e["status"]], "教师批注": e["comment"],
                         "已核实错因": e["cause"] if e["causeSource"] == "teacher" else ""} for e in g["items"]]})
    return ("你是小学老师，为一名学生的错题出针对性变式题。每个薄弱点按“题数”出题，要求：\n"
            "1. 保留原题的训练目标和考查方法，但不得照抄原题，也不能只把数字换掉：至少改变情境、问法或条件之一；难度由易到难递进（level 1、2、3）。\n"
            "2. 针对该学生的具体错误设计，例如学生选错的干扰项、批注指出的缺漏；不要出与错误无关的泛化练习。\n"
            "3. 语文阅读类题目：text 中必须包含完成题目所需的完整阅读材料（新写的短文或片段，不少于80字），再写问题；开放赏析改成单选、判断，或把所有等价答案列入 accepted_answers。\n"
            "4. 数学涉及图形时提供 figure（type 只允许 coordinate_grid、geometry、line_segment、bar_chart、object_group），或在 text 中写全所有数据和位置条件；不要写“如图”却不给图。\n"
            "5. question_type 只允许 single_choice（4个选项，correct_index 0-3）、true_false（[\"正确\",\"错误\"]）、fill_blank、calculation、short_answer（语文不用 calculation/short_answer）；非选择题必须给简洁可判分的 answer。\n"
            "6. 每题写 explanation（给老师看的解析），knowledge 写具体考点。不要出现学生姓名。\n"
            "薄弱点与错题依据：" + json.dumps(rows, ensure_ascii=False) +
            '\n只输出 JSON：{"groups":[{"key":"","knowledge":"","questions":[{"question_type":"single_choice","level":1,"knowledge":"","text":"",'
            '"options":["","","",""],"correct_index":0,"answer":"","accepted_answers":[],"figure":{},"explanation":""}]}]}')


def clean_question(raw: Any, group: dict[str, Any], sources: dict[str, dict[str, Any]], sanitize_figure: Any) -> dict[str, Any]:
    """Validate one variant against the existing targeted-practice rules; raise ValueError with a teacher-readable reason."""
    if not isinstance(raw, dict):
        raise ValueError("题目格式不正确")
    text = str(raw.get("text") or "").strip()
    if not text:
        raise ValueError("题目内容为空")
    qt = str(raw.get("question_type") or "single_choice").strip().lower()
    qt = "single_choice" if qt == "choice" else qt
    if qt not in PRACTICE_TYPES or (group["subject"] != "数学" and qt in ("calculation", "short_answer")):
        raise ValueError("题型不在可自动判分范围内")
    options = [str(x).strip() for x in (raw.get("options") or [])]
    try:
        ci = int(raw.get("correct_index", -1))
    except Exception:  # noqa: BLE001
        ci = -1
    answer = str(raw.get("answer") or "").strip()
    accepted = [str(x).strip() for x in (raw.get("accepted_answers") or []) if str(x).strip()][:8]
    if qt == "single_choice":
        if len(options) != 4 or not all(options) or ci not in range(4):
            raise ValueError("单选题需要4个选项和1个正确答案")
        answer, accepted = "", []
    elif qt == "true_false":
        options = ["正确", "错误"]
        if ci not in range(2):
            raise ValueError("判断题需要标明正确或错误")
        answer, accepted = "", []
    else:
        options, ci = [], -1
        if not answer:
            raise ValueError("非选择题需要可判分的答案")
    figure = sanitize_figure(raw.get("figure") or {}) if group["subject"] == "数学" else {}
    if any(w in text for w in FIGURE_WORDS) and not figure:
        raise ValueError("题目提到图形但没有可用图示")
    originals = [sources.get(e["key"].split(":", 1)[1], {}) for e in group["items"]]
    mine = _norm(text)
    for src in originals:
        full = _norm(src.get("full") or "")
        line = _norm(str(src.get("full") or "").split("\n\n")[-1])
        if mine == full or (line and mine == line) or (line and line in mine and len(mine) - len(line) < 6):
            raise ValueError("与原题相同，没有改编")
        if re.sub(r"\d+", "", mine) == re.sub(r"\d+", "", line or full):
            raise ValueError("只替换了数字，没有改变情境或问法")
    if group["subject"] == "语文" and any(src.get("material") for src in originals) and len(text) < 80:
        raise ValueError("阅读题缺少完成题目所需的阅读材料")
    try:
        level = max(1, min(3, int(raw.get("level") or 1)))
    except Exception:  # noqa: BLE001
        level = 1
    return {"question_type": qt, "level": level, "knowledge": (str(raw.get("knowledge") or "").strip() or group["knowledge"] or group["topic"])[:120],
            "text": text[:4000], "options": options, "correct_index": ci, "answer": answer[:300], "accepted_answers": accepted,
            "figure": figure, "explanation": str(raw.get("explanation") or "").strip()[:1000]}


def group_basis(group: dict[str, Any]) -> str:
    return "；".join(describe(e) for e in group["items"])


def practice_groups(evidence: list[dict[str, Any]], counts: dict[str, int] | None = None) -> list[dict[str, Any]]:
    out = []
    for g in weak_groups(evidence):
        n = (counts or {}).get(g["key"])
        g["count"] = max(1, min(5, int(n))) if n else default_count(g)
        g["basis"] = group_basis(g)
        out.append(g)
    return out


def practice_view(practice: dict[str, Any] | None, audience: str) -> dict[str, Any]:
    """Teacher sees everything; parents only see assigned question texts and the status, never answers or explanations."""
    practice = practice or {}
    groups = practice.get("groups") or []
    out: dict[str, Any] = {"state": practice.get("state") or ("review" if groups else "none")}
    if audience == "teacher":
        return {**practice, **out}
    out["label"] = PRACTICE_LABEL.get(out["state"], "")
    if out["state"] in ("partial", "assigned", "submitted", "graded"):
        out["assignments"] = [{k: a.get(k) for k in ("subject", "title", "dueDate", "state", "correct", "total", "submittedAt")}
                              for a in practice.get("assignments") or []]
        out["groups"] = [{"subject": g.get("subject"), "topic": g.get("topic"),
                          "questions": [{"text": q.get("text"), "options": q.get("options") or []} for q in g.get("questions") or []]}
                         for g in groups]
    return out

