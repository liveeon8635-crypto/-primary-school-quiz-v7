"""Sequential per-question releases, persisted with the existing slide cursor.

Old nonnegative stage-4 cursors mean all answers were already released. New
cursors store a released prefix and page index in one bounded integer. Reading
or paging never increases the released prefix.
"""
import hashlib
import json
import re
from sqlalchemy import insert, select, update

from changying.services.weekend_question_gen import question_key


def _gate_table(implementation):
    return implementation.Base.metadata.tables['weekend_open_questions']


def _read_gate(db, table, session):
    return db.execute(select(table.c.opened_question_ids).where(table.c.session_id == session.id,
        table.c.school_id == session.school_id)).scalar_one_or_none()


def _insert_gate_if_missing(db, table, session):
    """Create the gate row once, even when two requests create it at the same time."""
    from sqlalchemy.dialects.postgresql import insert as postgres_insert
    from sqlalchemy.dialects.sqlite import insert as sqlite_insert
    dialect = db.get_bind().dialect.name
    values = {"session_id": session.id, "school_id": session.school_id, "opened_question_ids": "[]"}
    if dialect == "postgresql":
        db.execute(postgres_insert(table).values(**values).on_conflict_do_nothing(index_elements=["session_id"]))
    elif dialect == "sqlite":
        db.execute(sqlite_insert(table).values(**values).on_conflict_do_nothing(index_elements=["session_id"]))
    else:  # Unknown dialect: the caller already holds the classroom row lock.
        db.execute(insert(table).values(**values))


def open_practice_question(implementation, db, session, ordinal):
    """Open one practice question and never drop a question another request opened.

    Two requests can read the same released list at once (the teacher taps twice,
    or two devices drive one classroom). Writing the list back blind made the
    later write erase the earlier question, so every write names the value it
    read and retries when somebody else moved the row first.
    """
    items = practice_items(implementation, db, session)
    if not 1 <= ordinal <= len(items):
        return
    item = items[ordinal - 1]
    key = f"{item['kind']}:{item['id']}"
    table = _gate_table(implementation)
    _insert_gate_if_missing(db, table, session)
    for _attempt in range(8):
        current = _read_gate(db, table, session)
        opened = json.loads(current) if current else []
        if key in opened:
            return
        opened.append(key)
        changed = db.execute(update(table).where(table.c.session_id == session.id,
            table.c.school_id == session.school_id, table.c.opened_question_ids == current,
        ).values(opened_question_ids=json.dumps(opened)))
        if changed.rowcount:
            return
    raise RuntimeError("随堂练习开放状态被同时修改多次，请刷新后重试")


def question_is_open(implementation, db, session, kind, question_id):
    table = _gate_table(implementation)
    value = _read_gate(db, table, session)
    # Existing classrooms without an explicit gate retain the historical workflow.
    if not value:
        from changying.services.weekend_course_types import frozen_session
        frozen = frozen_session(db, implementation, int(session.id), metadata=getattr(implementation, "Base", None) and implementation.Base.metadata)
        return not frozen or frozen.get("courseType") not in ("reading", "writing")
    opened = json.loads(value)
    if f'{kind}:{question_id}' in opened:
        return True
    # 文字题的板书序号按“选择题在前、文字题在后”排，但老师在大屏上点的那一题序号属于当堂那次点名；
    # 点名记录（weekend_open_questions.ordinal）保存的就是这次点名的来源，和文字题自己记录的来源号一致。
    # 否则阅读/作文课的随堂练习永远只开放得了一题，其余文字题学生永远提交不了。
    return kind == "written" and f'choice:{question_id}' in opened

_LABEL = re.compile(r'^\s*[A-Da-d]\s*[．.、:：)）]\s*')

_IMPORTED_QUESTION_PREFIX = re.compile(
    r'^\s*(?:第\s*\d{1,3}\s*题'
    r'(?:\s*[（(][^）)]{1,20}[）)])?'
    r'(?:\s*\d+(?:\.\d+)?\s*分)?'
    r'|(?:选择题|文字\s*[／/]\s*照片题)\s*\d{1,3}\s*[：:]?)'
    r'\s*[：:、.．|｜—-]?\s*'
)


def _question_key(value) -> str:
    """Normalize question text so different database IDs cannot bypass role separation.

    与“习题审核”的查重共用同一套归一化（weekend_question_gen.question_key），
    这样同一道题不会出现“审核说重复、大屏又发出去”或反过来的情况。
    """
    return question_key(display_stem(value))


def _lesson_example_texts(db, implementation, session) -> list[str]:
    lesson = db.get(implementation.TeachingLesson, int(session.lesson_id))
    if lesson is None:
        return []
    # 第3环节的页面带着“第3题（基础）（4分）”“原题｜”“例23（讲解用）”这类版面信息。审核页比对前由
    # lesson_worked_examples 去掉，课堂这边也必须走同一个函数，否则会出现
    # “审核页说与例3重复、第4环节又把这道题发给学生”。
    from changying.web.weekend_plan_views import lesson_worked_examples
    return [item["stem"] for item in lesson_worked_examples(lesson) if item["stem"]]


def _duplicates_example(stem, examples: list[str]) -> bool:
    """这道练习是不是本节某道例题的翻版（允许两边差一点版面标注、讲解）。"""
    from changying.services.weekend_question_gen import same_question_text
    return any(same_question_text(stem, example) for example in examples)


def display_stem(value):
    """Remove an imported paper number before adding the classroom-local number."""
    return _IMPORTED_QUESTION_PREFIX.sub('', str(value or ''), count=1).strip()



def option_text(value):
    """Imported options often carry their own letter ("A．8ab"); the screen adds the letter once."""
    return _LABEL.sub('', str(value), count=1)


def choice_courseware_binding(stem, options):
    """Options are part of a choice question's identity, not just its stem."""
    return str(stem or '').strip() + '\n选项：' + json.dumps(options, ensure_ascii=False, sort_keys=True)


def courseware_answer_binding(kind, answer, explanation=''):
    """Bind a reviewed slide to the source answer without exposing it in the question text."""
    value = [str(kind), str(answer if answer is not None else '').strip(), str(explanation or '').strip()]
    return hashlib.sha256(json.dumps(value, ensure_ascii=False).encode('utf-8')).hexdigest()

CURSOR_VERSION = 1_000_000
CURSOR_PAGES = 10_000


def session_question_ids(db, implementation, session_id: int) -> set[int] | None:
    """Return snapshotted TeachingQuestion IDs for a session, or None for legacy unsnapshotted sessions."""
    table = implementation.Base.metadata.tables.get("weekend_session_questions")
    if table is None:
        return None
    rows = db.scalars(select(table.c.question_id).where(table.c.session_id == int(session_id))).all()
    if not rows:
        return None
    return {int(qid) for qid in rows if int(qid) > 0}


def count_practice_ready(db, implementation, school_id: int, teacher_id: int, lesson) -> int:
    """第4环节实际能发放的题数：与例题重复的题不发，和大屏/审核页共用同一套判断。"""
    from changying.services.lesson_written import template_meta, written_templates
    from changying.web.weekend_plan_views import duplicate_of, lesson_worked_examples, question_options
    from changying.web.weekend_written import register_written_tables

    examples = lesson_worked_examples(lesson)
    ready = 0
    TQ = implementation.TeachingQuestion
    rows = db.scalars(select(TQ).where(TQ.lesson_id == lesson.id, TQ.stage != "removed", TQ.active.is_(True))).all()
    for q in rows:
        if not duplicate_of(q.stem, question_options(q), examples, []):
            ready += 1
    written = register_written_tables(implementation)["questions"]
    for q in written_templates(db, written, school_id, teacher_id, lesson.id):
        if template_meta(q).get("approved") and not duplicate_of(str(q.stem).split("\n\n")[-1].strip(), [], examples, []):
            ready += 1
    return ready


def practice_items(implementation, db, session):
    from changying.web.weekend_written import register_written_tables
    question = implementation.TeachingQuestion
    example_texts = _lesson_example_texts(db, implementation, session)
    items = []
    snap_ids = session_question_ids(db, implementation, session.id)
    stmt = select(question).where(
        question.school_id == session.school_id,
        question.lesson_id == session.lesson_id,
        question.active.is_(True),
    )
    if snap_ids is not None:
        stmt = stmt.where(question.id.in_(snap_ids)) if snap_ids else stmt.where(question.id == -1)
    reviewed_choices = list(db.scalars(stmt.order_by(question.id).limit(30)))
    reviewed_choices = [q for q in reviewed_choices if not _duplicates_example(q.stem, example_texts)]
    for index, q in enumerate(reviewed_choices, 1):
        options = json.loads(q.options_json or '[]')
        stem = f'选择题 {index}：{display_stem(q.stem)}\n' + '\n'.join(f'{chr(65+i)}. {option_text(value)}' for i, value in enumerate(options))
        correct = int(q.correct_index)
        answer = f'{chr(65+correct)}. {option_text(options[correct])}' if 0 <= correct < len(options) else '请老师核对参考答案'
        items.append({'kind': 'choice', 'id': q.id, 'source': 'reviewed_question', 'question': stem,
            'bindingStem': choice_courseware_binding(q.stem, options),
            'answerBinding': courseware_answer_binding('choice', correct, q.explanation),
            'answer': stem + f'\n正确答案：{answer}\n解析：{q.explanation or "请听老师讲解"}'})
    written = register_written_tables(implementation)['questions']
    reviewed_written = list(db.execute(select(written).where(written.c.session_id == session.id,
            written.c.school_id == session.school_id, written.c.teacher_id == session.teacher_id).order_by(written.c.id)))
    reviewed_written = [q for q in reviewed_written
                       if not _duplicates_example(q.stem.split(chr(10)+chr(10))[-1], example_texts)]
    for index, q in enumerate(reviewed_written, 1):
        stem = f'文字／照片题 {index}：{display_stem(q.stem.split(chr(10)+chr(10))[-1])}'
        items.append({'kind': 'written', 'id': q.id, 'source': 'reviewed_question', 'question': stem,
            'bindingStem': q.stem.split(chr(10)+chr(10))[-1].strip(),
            'answerBinding': courseware_answer_binding('written', q.reference),
            'answer': stem + '\n参考答案／评分要点：' + (q.reference.strip() or '本题未填写参考答案，请听老师讲评。')})
    return items


def practice_question_availability(implementation, db, session):
    items = practice_items(implementation, db, session)
    counts = {}
    for kind in ("choice", "written"):
        matching = [item for item in items if item["kind"] == kind]
        counts[kind] = {
            "total": len(matching),
            "open": sum(1 for item in matching if question_is_open(implementation, db, session, kind, item["id"])),
        }
    total = sum(item["total"] for item in counts.values())
    opened = sum(item["open"] for item in counts.values())
    state = "available" if opened else "waiting_for_teacher" if total else "review_or_sync"
    return {"state": state, "total": total, "open": opened, **counts}


def practice_release(implementation, db, session):
    from changying.services.weekend_course_types import frozen_session, practice_stage

    table = implementation.Base.metadata.tables['weekend_slide_state']
    cursor = db.execute(select(table).where(table.c.session_id == session.id,
        table.c.school_id == session.school_id)).first()
    items = practice_items(implementation, db, session)
    count, page = 0, 0
    if cursor is not None and cursor.stage_no == practice_stage((frozen_session(db, implementation, session.id, metadata=getattr(implementation, "Base", None) and implementation.Base.metadata) or {}).get("courseType")):
        value = int(cursor.idx)
        if value >= CURSOR_VERSION:
            count, page = divmod(value-CURSOR_VERSION, CURSOR_PAGES)
        elif value >= 0:  # already-published classrooms from the previous version
            count, page = len(items), value
        else:
            page = -value-1
    return items, min(count, len(items)), page


def practice_cursor(count, page):
    if not 0 <= page < CURSOR_PAGES or not 0 <= count < 1000:
        raise ValueError('Classroom slide cursor exceeds supported question/page count')
    return CURSOR_VERSION + count*CURSOR_PAGES + page


def answers_published(implementation, db, session, question_id=None, kind='choice'):
    items, count, _ = practice_release(implementation, db, session)
    if question_id is None:
        return bool(items) and count == len(items)
    return any(item['id'] == question_id and item['kind'] == kind for item in items[:count])


def practice_deck(implementation, db, session):
    from changying.services.weekend_presentation import presentation_pages
    items, count, page = practice_release(implementation, db, session)
    deck = []
    for index, item in enumerate(items):
        for text in presentation_pages([item['answer'] if index < count else item['question']], preserve_pages=True):
            deck.append({'text': text, 'question': index+1, 'published': index < count})
    return deck, count, min(page, max(0, len(deck)-1)), len(items)


def _valid_question_figure(fig):
    """Return a clean student-safe question figure dict, or {} if empty/invalid."""
    if not isinstance(fig, dict) or not fig.get("type"):
        return {}
    if fig.get("type") == "uploaded_image":
        url = str(fig.get("data_url") or "")
        if not url.startswith(("data:image/jpeg;base64,", "data:image/png;base64,")):
            return {}
        return {"type": "uploaded_image", "data_url": url, "alt": str(fig.get("alt") or "题目插图")[:80]}
    return dict(fig)


def practice_question_figures(implementation, db, session, items):
    """Batch-resolve question-only diagrams (never steps/answers) for practice items.

    Loads lesson written templates and approved stage-4 courseware at most ONCE per
    request so sessions with 20+ questions never repeat heavy JSON/base64 parsing.
    """
    valid_items = [it for it in (items or []) if it and it.get("kind") and it.get("id") is not None]
    if not valid_items:
        return {}

    out = {}
    choice_ids = [int(it["id"]) for it in valid_items if it.get("kind") == "choice"]
    if choice_ids:
        TQ = implementation.TeachingQuestion
        for tq in db.scalars(select(TQ).where(TQ.id.in_(choice_ids))).all():
            try:
                fig = _valid_question_figure(json.loads(getattr(tq, "figure_json", "") or "{}"))
            except (TypeError, ValueError):
                fig = {}
            if fig:
                out[("choice", int(tq.id))] = fig

    written_items = [it for it in valid_items if it.get("kind") == "written"]
    if written_items:
        from changying.services.lesson_written import template_meta, written_templates
        from changying.web.weekend_written import register_written_tables
        written_t = register_written_tables(implementation)["questions"]
        tpl_by_exact = {}
        tpl_by_key = {}
        for tpl in written_templates(db, written_t, session.school_id, session.teacher_id, session.lesson_id):
            fig = _valid_question_figure(template_meta(tpl).get("figure"))
            if not fig:
                continue
            tpl_stem = str(tpl.stem or "").split("\n\n")[-1].strip()
            if tpl_stem and tpl_stem not in tpl_by_exact:
                tpl_by_exact[tpl_stem] = fig
            k = question_key(tpl_stem) if tpl_stem else ""
            if k and k not in tpl_by_key:
                tpl_by_key[k] = fig
        for it in written_items:
            binding_stem = str(it.get("bindingStem") or "").strip()
            fig = tpl_by_exact.get(binding_stem) or (tpl_by_key.get(question_key(binding_stem)) if binding_stem else None)
            if fig:
                out[("written", int(it["id"]))] = fig

    missing = [it for it in valid_items if (it["kind"], int(it["id"])) not in out]
    if not missing:
        return out

    # Fallback: load approved stage-4 courseware ONCE and match remaining items in memory.
    from changying.services.weekend_course_types import frozen_session, practice_stage
    from changying.web.weekend_courseware import items_of, register_courseware_table, _repair_courseware_visual, _courseware_visual_text
    frozen = frozen_session(db, implementation, int(session.id), metadata=getattr(implementation, "Base", None) and implementation.Base.metadata)
    practice_no = practice_stage((frozen or {}).get("courseType"))
    cw_t = register_courseware_table(implementation)
    cw_row = db.execute(select(cw_t).where(
        cw_t.c.school_id == session.school_id,
        cw_t.c.lesson_id == session.lesson_id,
        cw_t.c.approved_json.isnot(None),
    )).first()
    if cw_row is None:
        return out
    approved = [i for i in items_of(cw_row) if i.get("approved") is not None and int(i.get("stage") or 0) == practice_no and i.get("page") is not None]
    if not approved:
        return out

    exact_map: dict[str, list[dict]] = {}
    key_map: dict[str, list[dict]] = {}
    for cw_item in approved:
        txt = str(cw_item.get("approvedPageText", cw_item.get("pageText")) or "").strip()
        if not txt:
            continue
        exact_map.setdefault(txt, []).append(cw_item)
        k = question_key(txt)
        if k:
            key_map.setdefault(k, []).append(cw_item)

    for it in missing:
        stem = str(it.get("bindingStem") or "").strip()
        if not stem:
            continue
        matches = exact_map.get(stem) or []
        if len(matches) != 1:
            k = question_key(stem)
            matches = key_map.get(k) or [] if k else []
        if len(matches) != 1:
            continue
        matched = matches[0]
        params = _repair_courseware_visual(matched["approved"], _courseware_visual_text(matched, matched["approved"], matched.get("pageText") or ""))
        candidates = [params.get("sourceFigure")]
        step_figs = params.get("stepFigures")
        if isinstance(step_figs, list) and step_figs:
            candidates.append(step_figs[0])
        candidates.append(params.get("figure"))
        for cand in candidates:
            fig = _valid_question_figure(cand)
            if fig:
                out[(it["kind"], int(it["id"]))] = fig
                break
    return out


def practice_question_figure(implementation, db, session, item):
    """Resolve the question-only diagram (never steps/answers) for a single practice item."""
    if not item or not item.get("kind") or item.get("id") is None:
        return {}
    return practice_question_figures(implementation, db, session, [item]).get((item["kind"], int(item["id"])), {})
