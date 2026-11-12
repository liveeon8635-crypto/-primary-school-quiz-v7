"""Lesson-level written drafts in the existing written-question table.

session_id=0 denotes a preparation template, never a student-visible session.
Its hints_json stores approval/type metadata; classroom snapshots store only the
existing hint list so the student submission and review contract stays unchanged.
"""
from __future__ import annotations

import json
import re
from typing import Any

from sqlalchemy import delete, insert, select



def lesson_question_number(source: str, stem: str) -> dict[str, int | None]:
    """Read a printed main number and sub-number without changing stored question IDs.

    A sub-question such as （2） receives its parent number only when its
    wording matches a unique location under a numbered heading in the original
    lesson. Ambiguous/missing source text is deliberately left unnumbered.
    """
    raw = str(stem or "").strip()
    last = raw.split("\n")[-1].strip()
    direct = re.match(r"^第\s*(\d{1,3})\s*题", raw) or re.match(r"^第\s*(\d{1,3})\s*题", last)
    sub_text = re.sub(r"^第\s*\d{1,3}\s*题\s*(?:\d+(?:\.\d+)?\s*分)?\s*[｜|]?\s*", "", last)
    part_match = re.match(r"^[（(]\s*(\d{1,2})\s*[）)]", sub_text)
    part = int(part_match.group(1)) if part_match else None
    if direct:
        return {"originalNumber": int(direct.group(1)), "partNumber": part, "sourcePosition": None}

    text = re.sub(r"\s+", "", str(source or ""))
    sample = re.sub(r"\s+", "", last)
    if len(sample) < 14 or not text:
        return {"originalNumber": None, "partNumber": part, "sourcePosition": None}
    headings = [(m.start(), int(m.group(1))) for m in re.finditer(r"第(\d{1,3})题", text)]
    if not headings:
        return {"originalNumber": None, "partNumber": part, "sourcePosition": None}
    found: list[tuple[int, int]] = []
    for offset in range(0, min(120, len(sample) - 13), 7):
        fragment = sample[offset:offset + 18]
        if len(fragment) < 14:
            continue
        at = text.find(fragment)
        if at < 0 or text.find(fragment, at + 1) >= 0:
            continue
        earlier = [number for pos, number in headings if pos < at]
        if earlier:
            found.append((earlier[-1], at))
    numbers = {number for number, _ in found}
    if len(numbers) != 1:
        return {"originalNumber": None, "partNumber": part, "sourcePosition": None}
    return {"originalNumber": numbers.pop(), "partNumber": part, "sourcePosition": min(pos for _, pos in found)}


def numbered_student_stem(source: str, stem: str) -> str:
    """Present a verified lesson number without changing the stored question."""
    raw = str(stem or "")
    number = lesson_question_number(source, raw)
    main = number["originalNumber"]
    if main is None or re.match(r"^\s*第\s*\d{1,3}\s*题", raw):
        return raw
    label = f"第{main}题" + (f"（{number['partNumber']}）" if number["partNumber"] else "")
    if "\n\n" in raw:
        material, question = raw.rsplit("\n\n", 1)
        return material + "\n\n" + label + "　" + question
    return label + "　" + raw

def template_meta(row: Any) -> dict[str, Any]:
    data = json.loads(row.hints_json or '{}')
    return data if isinstance(data, dict) else {}


def written_templates(db: Any, table: Any, school_id: int, teacher_id: int, lesson_id: int) -> list[Any]:
    return db.execute(select(table).where(table.c.school_id == school_id, table.c.teacher_id == teacher_id,
        table.c.lesson_id == lesson_id, table.c.session_id == 0).order_by(table.c.id)).all()


def literal_written_questions(text: str) -> list[dict[str, Any]]:
    """Read numbered questions under passage headings, stopping before teacher answers.

    For unstructured documents AI handles extraction; the complete source remains
    available to the teacher. This path guarantees the structured reading-paper
    questions are not replaced by unrelated model-generated multiple choice.
    """
    body = re.split(r'(?m)^\s*(?:[一二三四五六七八九十]+[、．.])?\s*参考答案', text, maxsplit=1)[0]
    answer_match = re.search(r'(?m)^\s*(?:[一二三四五六七八九十]+[、．.])?\s*参考答案', text)
    answers = text[answer_match.start():] if answer_match else ''
    group, material, out, in_questions = '', [], [], False
    passages = {}
    for raw in body.splitlines():
        line = raw.strip()
        if re.match(r'^(?:篇目[一二三四五六七八九十]|挑战题)', line):
            if material:
                passages[group] = '\n'.join(material)
            group, material, in_questions = line, [], False
            continue
        numbered = re.match(r'^(?:\d+|C\d+)[.．、]\s*', line)
        writing = bool(re.search('练笔|写作|读写', group)) and bool(re.match(r'^题目\s*[：:]', line))
        if group and (numbered or writing):
            kind = 'composition' if writing or any(w in line for w in ('扩写', '缩写', '复述')) else 'short_answer'
            passage = '\n'.join(material).strip()
            if group.startswith('挑战题'):
                passage = '\n\n'.join(passages.values())
            stem = group + '\n' + (passage + '\n\n' if passage else '') + line
            out.append({'stem': stem, 'type': kind, 'reference': '', 'hints': []})
            in_questions = True
        elif group and not in_questions and line:
            material.append(line)
    for q in out:
        heading = q['stem'].split('\n')[0]
        key = '挑战题' if heading.startswith('挑战题') else heading.split('：')[0]
        if '小练笔' in heading:
            match = re.search(r'(?m)^.*小练笔评分量规', answers)
        else:
            match = re.search(r'(?m)^' + re.escape(key) + r'\s*$', answers)
        if match:
            ref = answers[match.start():]
            end = re.search(r'(?m)^(?:篇目[一二三四五六七八九十]|挑战题|[六七八九十]+[、．.])', ref[1:])
            if end:
                ref = ref[:end.start()+1]
            if len(ref) <= 4000:
                q['reference'] = ref.strip()
    return out


def valid_written_questions(raw: Any) -> list[dict[str, Any]]:
    out = []
    for q in raw if isinstance(raw, list) else []:
        if not isinstance(q, dict):
            continue
        stem = str(q.get('stem') or '').strip()
        material = str(q.get('material') or '').strip()
        if material:
            stem = material + '\n\n' + stem
        reference = str(q.get('reference') or q.get('explanation') or '').strip()
        hints = q.get('hints') or []
        if not stem or len(stem) > 20000 or len(reference) > 4000:
            continue
        if not isinstance(hints, list) or len(hints) != 3 or any(not isinstance(h, str) or not h.strip() or len(h) > 300 for h in hints):
            hints = []
        out.append({'stem': stem, 'reference': reference, 'hints': hints, 'figure': _figure(q.get('figure')),
                    'type': q.get('type') if q.get('type') in ('short_answer', 'final_answer', 'composition') else 'short_answer'})
    return out[:30]


_FIGURE_URL = re.compile(r"data:image/jpeg;base64,[A-Za-z0-9+/]+={0,2}")


def _figure(value: Any) -> dict[str, Any]:
    """A written question may keep the picture that came with it; anything else is dropped."""
    if not isinstance(value, dict) or value.get('type') != 'uploaded_image':
        return {}
    url = str(value.get('data_url') or '')
    if len(url) > 700000 or not _FIGURE_URL.fullmatch(url):
        return {}
    figure = {'type': 'uploaded_image', 'data_url': url, 'alt': str(value.get('alt') or '原卷插图')[:80]}
    # Keep PDF-verified provenance through written-question validation and storage.
    try:
        question_no = int(value.get('question_no'))
    except (TypeError, ValueError):
        question_no = 0
    if 1 <= question_no <= 999:
        figure['question_no'] = question_no
    return figure


def replace_written_drafts(db: Any, table: Any, school_id: int, teacher_id: int, lesson_id: int, questions: list[dict[str, Any]]) -> None:
    existing = written_templates(db, table, school_id, teacher_id, lesson_id)
    approved_stems = {q.stem for q in existing if template_meta(q).get('approved')}
    for row in existing:
        if not template_meta(row).get('approved'):
            db.execute(delete(table).where(table.c.id == row.id))
    for q in questions:
        if q['stem'] in approved_stems:
            continue
        db.execute(insert(table).values(school_id=school_id, teacher_id=teacher_id, lesson_id=lesson_id, session_id=0,
            stem=q['stem'], reference=q['reference'], hints_json=json.dumps({**q.get('extra', {}), 'approved': False, 'type': q['type'], 'hints': q['hints'], 'figure': q.get('figure') or {}}, ensure_ascii=False)))


# 考点：题目小标题（“例题 1 | 省略乘号 …”）里竖线后的第一个词就是教案写好的考点；只写题型的不算。
_HEADING = re.compile(r"^[^\n|｜]{1,16}[|｜]\s*([^\s（(:：|｜]{2,20})")
_TYPE_WORDS = ("填空", "判断", "选择", "计算", "口算", "简答", "解答", "解决问题", "应用题", "连线", "作图", "画图", "写作", "阅读")
_GOAL = re.compile(r"[（(]\s*\d+\s*[)）]")
MAX_KNOWLEDGE = 40


def suggest_knowledge(stem: str) -> str:
    """The knowledge point the lesson plan already names in the question heading, or ''."""
    line = str(stem or "").strip().split("\n\n")[-1].strip()
    m = _HEADING.match(line)
    if not m:
        return ""
    word = m.group(1).strip("。，,.")
    return "" if any(word.startswith(t) for t in _TYPE_WORDS) or word.startswith("第") else word[:MAX_KNOWLEDGE]


def lesson_goals(core_target: str) -> list[str]:
    """The numbered training goals of a lesson (“（1）… （2）…”), for picking a knowledge point."""
    parts = [p.strip(" 。；;") for p in _GOAL.split(str(core_target or "")) if p.strip(" 。；;")]
    return [re.split(r"[，,]", p)[0][:MAX_KNOWLEDGE] for p in parts] if len(parts) > 1 else []


def template_marks(db: Any, table: Any, school_id: int, teacher_id: int, lesson_id: int) -> dict[str, dict[str, Any]]:
    """The teacher's 考点 and 课后题 marks by question text, for classroom copies of the lesson's templates."""
    out = {}
    for row in written_templates(db, table, school_id, teacher_id, lesson_id):
        meta = template_meta(row)
        out[str(row.stem)] = {"id": int(row.id), "knowledge": str(meta.get("knowledge") or "")[:MAX_KNOWLEDGE],
                              "afterClass": bool(meta.get("afterClass"))}
    return out


def snapshot_written_questions(db: Any, table: Any, school_id: int, teacher_id: int, lesson_id: int, session_id: int) -> None:
    for row in written_templates(db, table, school_id, teacher_id, lesson_id):
        meta = template_meta(row)
        if meta.get('approved'):
            db.execute(insert(table).values(school_id=school_id, teacher_id=teacher_id, lesson_id=lesson_id, session_id=session_id,
                stem=row.stem, reference=row.reference, hints_json=json.dumps(meta.get('hints', []), ensure_ascii=False)))
