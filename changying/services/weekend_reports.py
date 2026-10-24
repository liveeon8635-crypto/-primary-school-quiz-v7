"""Weekend lesson facts and per-student learning reports.

Facts are computed deterministically from the original weekend tables and never
written back. Report texts are drafts a teacher edits; parents only read the
version the teacher published. Counting rules (see the teacher page):

- the denominator is every question of the lesson (choice + written), per pupil;
- an unanswered question is "未提交", a submitted but unreviewed one "待批" and
  neither is counted as wrong; "部分正确" stays separate and is never converted
  into a score;
- one question counts once however often it was resubmitted; the original rows
  keep only the final answer, so first and revised answers are not distinguished;
- hints and submission times are reported as recorded, never as "不独立" or time spent;
- weekend points are ledger points, not marks, and only shown once settled.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select

STATUS_LABEL = {"unsubmitted": "未提交", "pending": "待批", "correct": "正确", "partial": "部分正确", "revise": "需订正"}
FOCUS = {
    "语文": "理解题意、从文中找依据、答全要点、表达完整",
    "数学": "概念理解、方法选择、计算过程、单位与作答完整",
}
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
            options = [str(x) for x in json.loads(q.options_json or "[]")]
        except Exception:  # noqa: BLE001
            options = []
        questions.append({"key": f"c{q.id}", "kind": "choice", "id": int(q.id), "stem": _short(q.stem),
                          "knowledge": str(q.knowledge or "").strip(), "options": options, "correctIndex": int(q.correct_index)})
    for q in db.execute(select(written_q).where(written_q.c.session_id == row.id, written_q.c.school_id == row.school_id,
                                                written_q.c.teacher_id == row.teacher_id).order_by(written_q.c.id)):
        # Written questions carry no per-question knowledge point; the lesson goal is not substituted for it.
        questions.append({"key": f"w{q.id}", "kind": "written", "id": int(q.id), "stem": _short(q.stem), "knowledge": ""})
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
                    item["status"] = "unsubmitted"
                else:
                    item.update(status=a.result if a.result in ("pending", "correct", "partial", "revise") else "pending",
                                attempts=attempts.get((sid, "written", q["id"]), 1), answer=str(a.answer_text or ""),
                                hasPhoto=bool(a.has_photo), submissionId=int(a.id), comment=str(a.comment or ""),
                                revision=int(a.revision), submittedAt=a.submitted_at, reviewedAt=a.reviewed_at)
            items.append(item)
        counts = {k: sum(1 for i in items if i["status"] == k) for k in STATUS_LABEL}
        counts["total"] = len(items)
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
        per_question.append({"no": q["no"], "kind": q["kind"], "stem": q["stem"], "knowledge": q["knowledge"] or "未标注考点",
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
        "questions": [{k: q[k] for k in ("key", "no", "kind", "stem", "knowledge")} for q in facts["questions"]],
        **{k: pupil[k] for k in ("studentId", "name", "participated", "counts", "explained", "followups", "points")},
        "items": [{k: i[k] for k in ("key", "no", "kind", "status", "attempts", "hint", "knowledge")} for i in pupil["items"]]}


def fingerprint(parts: list[dict[str, Any]]) -> str:
    """Changes when an answer, review, hint, follow-up or award changes; not on the cutoff time."""
    stable = [{k: v for k, v in p.items() if k != "cutoff"} for p in parts]
    return hashlib.sha256(json.dumps(stable, ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest()


def parent_facts(part: dict[str, Any]) -> dict[str, Any]:
    """What a parent may see: their child's own counts per section, no answers, references, photos or class data."""
    out = {k: part[k] for k in ("sessionId", "date", "subject", "lessonTitle", "unit", "counts")}
    if part["points"]["settled"]:
        out["points"] = part["points"]["total"]
    return out


def _label(item: dict[str, Any]) -> str:
    return f"第{item['no']}题（{item['knowledge'] or '未标注考点'}）"


def draft_section(part: dict[str, Any]) -> dict[str, str]:
    """Deterministic draft for one lesson; only states what the records show."""
    c, items = part["counts"], part["items"]
    focus = FOCUS.get(part["subject"], "审题、方法和作答完整")
    content = f"《{part['lessonTitle']}》" + (f"（{part['unit']}）" if part["unit"] else "") + "。"
    content += f"训练目标：{part['coreTarget']}。" if part["coreTarget"] else "训练目标以课堂安排为准。"
    completion = (f"本节应做 {c['total']} 题，已提交 {c['submitted']} 题，未提交 {c['unsubmitted']} 题。"
                  f"已批改结果：正确 {c['correct']} 题，部分正确 {c['partial']} 题，需订正 {c['revise']} 题；"
                  f"待老师批改 {c['pending']} 题（待批改不算错误）。")
    right = [i for i in items if i["status"] == "correct"]
    mastery = ("、".join(_label(i) for i in right[:4]) + " 作答正确。") if right else "本节已批改的题目中暂时没有完全正确的作答，掌握情况需要后续练习确认。"
    if c["pending"]:
        mastery += f"另有 {c['pending']} 题待批改，批改后再确认。"
    wrong = [i for i in items if i["status"] == "revise"] + [i for i in items if i["status"] == "partial"]
    if wrong:
        issues = "；".join(_label(i) + ("需订正" if i["status"] == "revise" else "部分正确") for i in wrong[:2]) + f"。订正时请重点核对：{focus}。"
    else:
        issues = "本节已批改的题目中没有需要订正的题。" if c["submitted"] > c["pending"] else "暂无已批改结果，批改后补充。"
    consolidation = []
    if part["followups"]:
        consolidation += [f"第{f['no']}题讲解后的同类巩固题" + ("做对" if f["correct"] else "未做对" if f["correct"] is False else "尚未完成")
                          for f in part["followups"]]
    if part["explained"]:
        consolidation.append("受老师邀请为同学讲解第" + "、".join(str(n) for n in part["explained"]) + "题的思路")
    homework = []
    for i in wrong[:2]:
        homework.append(f"订正第{i['no']}题，写出依据或过程；再完成同类练习 3 题，约 15 分钟。")
    unsubmitted = [i for i in items if i["status"] == "unsubmitted"]
    if unsubmitted:
        homework.append("补做未提交的第" + "、".join(str(i["no"]) for i in unsubmitted) + "题，约 10 分钟。")
    if not homework:
        homework.append("复习本节内容，完成同类练习 3 题，约 10 分钟。")
    homework.append("家长配合：请孩子讲一讲订正或解题思路，家长只听和提问，不代写答案。")
    targets = "、".join(dict.fromkeys(i["knowledge"] or f"第{i['no']}题" for i in wrong[:2]))
    followup = (f"下节课先用 1—2 道同类题检查{targets}的订正情况。" if targets else "下节课在新内容前用 1 道题回顾本节方法。")
    return {"content": content, "completion": completion, "mastery": mastery, "issues": issues,
            "consolidation": "；".join(consolidation) + ("。" if consolidation else ""), "observation": "",
            "homework": "\n".join(homework), "followup": followup}


def ai_prompt(parts: list[dict[str, Any]], drafts: list[dict[str, str]]) -> str:
    """Anonymised: no names, class names or answers; the model may only reword the given facts."""
    facts = [{"科目": p["subject"], "课题": p["lessonTitle"], "训练目标": p["coreTarget"], "统计": p["counts"],
              "题目": [{"题号": i["no"], "考点": i["knowledge"] or "未标注", "结果": STATUS_LABEL[i["status"]], "提示级数": i["hint"]} for i in p["items"]],
              "巩固": p["followups"], "讲解题号": p["explained"]} for p in parts]
    return ("你是小学老师，帮忙把下面的课堂事实整理成给家长看的简洁反馈。只能使用给出的事实，不得编造分数、排名、进步幅度、"
            "行为评价（如认真、注意力）或未提供的题目；待批改不算错误；使用提示不等于不独立。称呼学生为“孩子”。\n"
            "事实：" + json.dumps(facts, ensure_ascii=False) + "\n草稿：" + json.dumps(drafts, ensure_ascii=False) +
            '\n只输出 JSON：{"sections":[{"mastery":"","issues":"","homework":"","followup":""}]}，数组顺序与事实一致，每项不超过200字。')


def apply_ai(drafts: list[dict[str, str]], data: Any) -> list[dict[str, str]]:
    items = data.get("sections") if isinstance(data, dict) else None
    if not isinstance(items, list) or len(items) != len(drafts):
        raise ValueError("AI sections do not match the lessons")
    out = []
    for draft, item in zip(drafts, items):
        merged = dict(draft)
        for key in ("mastery", "issues", "homework", "followup"):
            text = str((item or {}).get(key) or "").strip()
            if text:
                merged[key] = text[:400]
        out.append(merged)
    return out


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
