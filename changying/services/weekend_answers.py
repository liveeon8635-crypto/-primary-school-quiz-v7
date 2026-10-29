"""Sequential per-question releases, persisted with the existing slide cursor.

Old nonnegative stage-4 cursors mean all answers were already released. New
cursors store a released prefix and page index in one bounded integer. Reading
or paging never increases the released prefix.
"""
import json
import re
from sqlalchemy import select

_LABEL = re.compile(r'^\s*[A-Da-d]\s*[．.、:：)）]\s*')


def option_text(value):
    """Imported options often carry their own letter ("A．8ab"); the screen adds the letter once."""
    return _LABEL.sub('', str(value), count=1)

CURSOR_VERSION = 1_000_000
CURSOR_PAGES = 10_000


def practice_items(implementation, db, session):
    from changying.web.weekend_written import register_written_tables
    question = implementation.TeachingQuestion
    items = []
    for index, q in enumerate(db.scalars(select(question).where(question.school_id == session.school_id,
            question.lesson_id == session.lesson_id, question.active.is_(True)).order_by(question.id).limit(30)), 1):
        options = json.loads(q.options_json or '[]')
        stem = f'选择题 {index}：{q.stem}\n' + '\n'.join(f'{chr(65+i)}. {option_text(value)}' for i, value in enumerate(options))
        correct = int(q.correct_index)
        answer = f'{chr(65+correct)}. {option_text(options[correct])}' if 0 <= correct < len(options) else '请老师核对参考答案'
        items.append({'kind': 'choice', 'id': q.id, 'question': stem,
            'answer': stem + f'\n正确答案：{answer}\n解析：{q.explanation or "请听老师讲解"}'})
    written = register_written_tables(implementation)['questions']
    for index, q in enumerate(db.execute(select(written).where(written.c.session_id == session.id,
            written.c.school_id == session.school_id, written.c.teacher_id == session.teacher_id).order_by(written.c.id)), 1):
        stem = f'文字／照片题 {index}：{q.stem.split(chr(10)+chr(10))[-1]}'
        items.append({'kind': 'written', 'id': q.id, 'question': stem,
            'answer': stem + '\n参考答案／评分要点：' + (q.reference.strip() or '本题未填写参考答案，请听老师讲评。')})
    return items


def practice_release(implementation, db, session):
    table = implementation.Base.metadata.tables['weekend_slide_state']
    cursor = db.execute(select(table).where(table.c.session_id == session.id,
        table.c.school_id == session.school_id)).first()
    items = practice_items(implementation, db, session)
    count, page = 0, 0
    if cursor is not None and cursor.stage_no == 4:
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
