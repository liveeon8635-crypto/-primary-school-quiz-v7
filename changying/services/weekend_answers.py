"""Teacher-controlled answer slides, persisted in the existing slide cursor.

Stage 4 negative cursors are question pages (-1 means page 0); nonnegative
cursors are published answer pages. No publication occurs by reading a page.
"""
from sqlalchemy import select


def answers_published(implementation, db, session):
    table = implementation.Base.metadata.tables['weekend_slide_state']
    cursor = db.execute(select(table).where(table.c.session_id == session.id,
        table.c.school_id == session.school_id)).first()
    return bool(cursor is not None and cursor.stage_no == 4 and cursor.idx >= 0)


def practice_pages(implementation, db, session, *, answers=False):
    from changying.services.weekend_presentation import presentation_pages
    from changying.web.weekend_written import register_written_tables
    question = implementation.TeachingQuestion
    pages = []
    for index, q in enumerate(db.scalars(select(question).where(question.school_id == session.school_id,
            question.lesson_id == session.lesson_id, question.active.is_(True)).order_by(question.id)), 1):
        import json
        options = json.loads(q.options_json or '[]')
        text = f'选择题 {index}：{q.stem}'
        if answers:
            correct = int(q.correct_index)
            answer = f'{chr(65+correct)}. {options[correct]}' if 0 <= correct < len(options) else '请老师核对参考答案'
            text += f'\n正确答案：{answer}\n解析：{q.explanation or "请听老师讲解"}'
        else:
            text += '\n' + '\n'.join(f'{chr(65+i)}. {value}' for i, value in enumerate(options))
        pages.append(text)
    written = register_written_tables(implementation)['questions']
    for index, q in enumerate(db.execute(select(written).where(written.c.session_id == session.id,
            written.c.school_id == session.school_id, written.c.teacher_id == session.teacher_id).order_by(written.c.id)), 1):
        text = f'文字／照片题 {index}：{q.stem.split(chr(10)+chr(10))[-1]}'
        if answers:
            text += '\n参考答案／评分要点：' + (q.reference.strip() or '本题未填写参考答案，请听老师讲评。')
        pages.append(text)
    return presentation_pages(pages, preserve_pages=True)
