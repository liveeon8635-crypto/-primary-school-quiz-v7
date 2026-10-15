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
                passage = '\n\n'.join(value for key, value in passages.items()
                    if ('阿木' in line and '神泉' in key) or ('鲁班' in line and '鲁班' in key))
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
        out.append({'stem': stem, 'reference': reference, 'hints': hints,
                    'type': q.get('type') if q.get('type') in ('short_answer', 'final_answer', 'composition') else 'short_answer'})
    return out[:30]


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
            stem=q['stem'], reference=q['reference'], hints_json=json.dumps({'approved': False, 'type': q['type'], 'hints': q['hints']}, ensure_ascii=False)))


def snapshot_written_questions(db: Any, table: Any, school_id: int, teacher_id: int, lesson_id: int, session_id: int) -> None:
    for row in written_templates(db, table, school_id, teacher_id, lesson_id):
        meta = template_meta(row)
        if meta.get('approved'):
            db.execute(insert(table).values(school_id=school_id, teacher_id=teacher_id, lesson_id=lesson_id, session_id=session_id,
                stem=row.stem, reference=row.reference, hints_json=json.dumps(meta.get('hints', []), ensure_ascii=False)))
