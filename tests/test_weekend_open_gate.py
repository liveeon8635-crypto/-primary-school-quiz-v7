"""Regression tests for teacher-controlled visibility of practice questions."""
import importlib.util
import sys
from pathlib import Path


spec = importlib.util.spec_from_file_location('open_gate_helpers', Path(__file__).with_name('test_weekend_backup.py'))
backup = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = backup
spec.loader.exec_module(backup)


SETUP = r'''
with TestClient(app) as client:
    th, sh, student, school, lid, qid, wid, sid, base, body = prepare(client)
    with legacy.SessionLocal() as db:
        first = db.get(legacy.TeachingQuestion, qid)
        second = legacy.TeachingQuestion(school_id=school, program_id=first.program_id, lesson_id=lid,
            subject='数学', stage='lesson', level='B', knowledge='图形',
            stem='第二选择题秘密题干', options_json='["第二题秘密选项甲", "第二题秘密选项乙"]',
            correct_index=0, explanation='解析', active=True)
        db.add(second); db.flush()
        sq = legacy.Base.metadata.tables.get('weekend_session_questions')
        if sq is not None:
            db.execute(sq.insert().values(school_id=school, session_id=sid, question_id=second.id, added_at=datetime.utcnow()))
        db.commit(); second_id = second.id
    r = client.post(base+'/written/questions', headers=th, json={
        'stem':'第二文字题秘密题干', 'reference':'答案',
        'hints':['第二文字题秘密提示一','第二文字题秘密提示二','第二文字题秘密提示三']})
    assert r.status_code == 200, r.text
    written_second = r.json()['id']
    assert client.post(base+'/start', headers=th).status_code == 200
    assert client.post(base+'/goto', headers=th, json={'stage':4}).status_code == 200
    assert client.post(base+'/practice-question', headers=th, json={'question':1}).status_code == 200
'''


def test_closed_second_question_is_not_returned_or_accessible(tmp_path):
    backup.helpers.run_isolated(tmp_path, backup.COMMON + SETUP + r'''
    choice = client.get('/student/weekend/current', headers=sh)
    written = client.get(f'/student/weekend/sessions/{sid}/written', headers=sh)
    assert choice.status_code == 200 and written.status_code == 200
    assert '第二选择题秘密题干' not in choice.text, '响应中出现了第2题的题干'
    assert '第二题秘密选项甲' not in choice.text, '响应中出现了第2题的选项'
    assert '第二文字题秘密题干' not in written.text, '文字题响应中出现了未开放题干'
    assert '第二文字题秘密提示一' not in written.text, '文字题响应中出现了未开放提示'
    assert client.post('/student/weekend/hint', headers=sh, json={'sessionId':sid, 'questionId':second_id}).status_code == 404
    assert client.post('/student/weekend/answer', headers=sh, json={'sessionId':sid, 'questionId':second_id, 'selected':0}).status_code == 404
    assert client.post(f'/student/weekend/sessions/{sid}/written/{written_second}/hint', headers=sh).status_code == 404
    assert client.post(f'/student/weekend/sessions/{sid}/written/{written_second}', headers=sh, data={'text':'未开放抢答'}).status_code == 404
    print('OK')
''')


def test_teacher_can_open_second_question(tmp_path):
    backup.helpers.run_isolated(tmp_path, backup.COMMON + SETUP + r'''
    r = client.post(base+'/practice-question', headers=th, json={'question':2})
    assert r.status_code == 200, r.text
    choice = client.get('/student/weekend/current', headers=sh)
    assert choice.status_code == 200
    assert '第二选择题秘密题干' in choice.text
    assert '第二题秘密选项甲' in choice.text
    assert client.post('/student/weekend/answer', headers=sh, json={'sessionId':sid, 'questionId':second_id, 'selected':0}).status_code == 200
    r = client.post(base+'/practice-question', headers=th, json={'question':4})
    assert r.status_code == 200, r.text
    written = client.get(f'/student/weekend/sessions/{sid}/written', headers=sh)
    assert written.status_code == 200
    assert '第二文字题秘密题干' in written.text
    assert client.post(f'/student/weekend/sessions/{sid}/written/{written_second}/hint', headers=sh).status_code == 200
    assert client.post(f'/student/weekend/sessions/{sid}/written/{written_second}', headers=sh, data={'text':'已开放作答'}).status_code == 200
    print('OK')
''')


def test_new_classroom_is_closed_before_first_teacher_selection(tmp_path):
    before_selection = SETUP.replace(
        "    assert client.post(base+'/practice-question', headers=th, json={'question':1}).status_code == 200\n", "")
    backup.helpers.run_isolated(tmp_path, backup.COMMON + before_selection + r'''
    # Entering practice or refreshing either role must not implicitly open a question.
    for _ in range(2):
        assert client.get(base, headers=th).status_code == 200
        choice = client.get('/student/weekend/current', headers=sh)
        written = client.get(f'/student/weekend/sessions/{sid}/written', headers=sh)
        assert choice.status_code == 200 and choice.json()['questions'] == [], choice.text
        assert written.status_code == 200 and written.json()['questions'] == [], written.text
    for question_id in (qid, second_id):
        assert client.post('/student/weekend/hint', headers=sh,
            json={'sessionId':sid, 'questionId':question_id}).status_code == 404
        assert client.post('/student/weekend/answer', headers=sh,
            json={'sessionId':sid, 'questionId':question_id, 'selected':0}).status_code == 404
    for question_id in (wid, written_second):
        assert client.post(f'/student/weekend/sessions/{sid}/written/{question_id}/hint',
            headers=sh).status_code == 404
        assert client.post(f'/student/weekend/sessions/{sid}/written/{question_id}',
            headers=sh, data={'text':'premature answer'}).status_code == 404
    with legacy.SessionLocal() as db:
        gate = legacy.Base.metadata.tables['weekend_open_questions']
        value = db.scalar(select(gate.c.opened_question_ids).where(
            gate.c.session_id == sid, gate.c.school_id == school))
        assert value == '[]', value
    assert client.post(base+'/practice-question', headers=th, json={'question':1}).status_code == 200
    visible = client.get('/student/weekend/current', headers=sh).json()['questions']
    assert [q['id'] for q in visible] == [qid]
    assert client.post('/student/weekend/answer', headers=sh,
        json={'sessionId':sid,'questionId':qid,'selected':0}).status_code == 200
    print('OK')
''')


def test_classroom_creation_persists_empty_gate_and_legacy_without_gate_remains_compatible(tmp_path):
    backup.helpers.run_isolated(tmp_path, backup.COMMON + r'''
with TestClient(app) as client:
    th, sh, student, school, lid, qid, wid, sid, base, body = prepare(client)
    with legacy.SessionLocal() as db:
        gate = legacy.Base.metadata.tables['weekend_open_questions']
        value = db.scalar(select(gate.c.opened_question_ids).where(
            gate.c.session_id == sid, gate.c.school_id == school))
        assert value == '[]', value
        # A synthetic pre-upgrade classroom has no gate record.
        db.execute(gate.delete().where(gate.c.session_id == sid))
        db.commit()
    assert client.post(base+'/start', headers=th).status_code == 200
    assert client.post(base+'/goto', headers=th, json={'stage':4}).status_code == 200
    assert [q['id'] for q in client.get('/student/weekend/current', headers=sh).json()['questions']] == [qid]
    assert [q['id'] for q in client.get(f'/student/weekend/sessions/{sid}/written', headers=sh).json()['questions']] == [wid]
    print('OK')
''')
