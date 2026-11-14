"""Sequential per-question releases, persisted with the existing slide cursor.

Old nonnegative stage-4 cursors mean all answers were already released. New
cursors store a released prefix and page index in one bounded integer. Reading
or paging never increases the released prefix.
"""
import json
import re
from sqlalchemy import select

_LABEL = re.compile(r'^\s*[A-Da-d]\s*[．.、:：)）]\s*')

_IMPORTED_QUESTION_PREFIX = re.compile(
    r'^\s*(?:第\s*\d{1,3}\s*题'
    r'(?:\s*[（(][^）)]{1,20}[）)])?'
    r'(?:\s*\d+(?:\.\d+)?\s*分)?'
    r'|(?:选择题|文字\s*[／/]\s*照片题)\s*\d{1,3}\s*[：:]?)'
    r'\s*[：:、.．|｜—-]?\s*'
)


def _question_key(value) -> str:
    """Normalize question text so different database IDs cannot bypass role separation."""
    text = display_stem(value)
    return re.sub(r"[\s\u3000，。,、:：;；!！?？（）()“”\"'「」『』]+", "", text).lower()


def _lesson_example_keys(db, implementation, session) -> set[str]:
    lesson = db.get(implementation.TeachingLesson, int(session.lesson_id))
    if lesson is None:
        return set()
    # Stage 3 uses numbered exercises from reading_plan when available;
    # using examples_json alone misses the actual worked examples shown.
    from changying.services.weekend_presentation import lesson_deck
    pages = lesson_deck({
        "reading_plan": getattr(lesson, "reading_plan", "") or "",
        "examples_json": getattr(lesson, "examples_json", "") or "",
    }, 3)
    return {_question_key(page) for page in pages if _question_key(page)}


def display_stem(value):
    """Remove an imported paper number before adding the classroom-local number."""
    return _IMPORTED_QUESTION_PREFIX.sub('', str(value or ''), count=1).strip()



def option_text(value):
    """Imported options often carry their own letter ("A．8ab"); the screen adds the letter once."""
    return _LABEL.sub('', str(value), count=1)

CURSOR_VERSION = 1_000_000
CURSOR_PAGES = 10_000


def practice_items(implementation, db, session):
    from changying.web.weekend_written import register_written_tables
    question = implementation.TeachingQuestion
    example_keys = _lesson_example_keys(db, implementation, session)
    items = []
    reviewed_choices = list(db.scalars(select(question).where(question.school_id == session.school_id,
            question.lesson_id == session.lesson_id, question.active.is_(True)).order_by(question.id).limit(30)))
    reviewed_choices = [q for q in reviewed_choices if _question_key(q.stem) not in example_keys]
    for index, q in enumerate(reviewed_choices, 1):
        options = json.loads(q.options_json or '[]')
        stem = f'选择题 {index}：{display_stem(q.stem)}\n' + '\n'.join(f'{chr(65+i)}. {option_text(value)}' for i, value in enumerate(options))
        correct = int(q.correct_index)
        answer = f'{chr(65+correct)}. {option_text(options[correct])}' if 0 <= correct < len(options) else '请老师核对参考答案'
        items.append({'kind': 'choice', 'id': q.id, 'source': 'reviewed_question', 'question': stem,
            'answer': stem + f'\n正确答案：{answer}\n解析：{q.explanation or "请听老师讲解"}'})
    written = register_written_tables(implementation)['questions']
    reviewed_written = list(db.execute(select(written).where(written.c.session_id == session.id,
            written.c.school_id == session.school_id, written.c.teacher_id == session.teacher_id).order_by(written.c.id)))
    reviewed_written = [q for q in reviewed_written if _question_key(q.stem.split(chr(10)+chr(10))[-1]) not in example_keys]
    for index, q in enumerate(reviewed_written, 1):
        stem = f'文字／照片题 {index}：{display_stem(q.stem.split(chr(10)+chr(10))[-1])}'
        items.append({'kind': 'written', 'id': q.id, 'source': 'reviewed_question', 'question': stem,
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
