from __future__ import annotations
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('per_question_helpers', ROOT/'tests/test_homework_solve.py')
helpers = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = helpers
spec.loader.exec_module(helpers)


def test_submit_publish_then_continue_three_questions_without_releasing_later_answers(tmp_path):
    helpers.run_isolated(tmp_path, helpers.COMMON+r'''
with TestClient(app) as client:
    th, sh, student_id, school_id = setup(client)
    with legacy.SessionLocal() as db:
        p = db.scalar(select(legacy.TeachingProgram).where(legacy.TeachingProgram.school_id == school_id))
        l = legacy.TeachingLesson(school_id=school_id,program_id=p.id,subject='语文',lesson_no=94,title='逐题讲评')
        db.add(l);db.commit();lid=l.id
    sid=client.post('/teacher/weekend/sessions',headers=th,json={'lessonId':lid}).json()['id']
    base=f'/teacher/weekend/sessions/{sid}'
    student=f'/student/weekend/sessions/{sid}/written'
    ids=[]
    for i in range(3):
        r=client.post(base+'/written/questions',headers=th,json={'stem':f'第{i+1}题','reference':f'唯一参考答案{i+1}'})
        assert r.status_code==200,r.text
        ids.append(r.json()['id'])
    client.post(base+'/start',headers=th);client.post(base+'/goto',headers=th,json={'stage':4})
    assert client.post(base+'/practice-question', headers=th, json={'question':1}).status_code == 200
    control=client.get('/v1/weekend').text
    assert "post('publish-answers',{question:current})" in control and '继续第 ' in control
    assert client.post(base+'/publish-answers',headers=th,json={'question':2}).status_code==409
    for i,qid in enumerate(ids):
        before=client.get(student,headers=sh).json()
        assert before['questions'][i]['canSubmit']
        sent=client.post(student+f'/{qid}',headers=sh,data={'text':f'我的第{i+1}题答案'})
        assert sent.status_code==200,sent.text
        assert f'唯一参考答案{i+1}' not in client.get(base+'/board',headers=th).text
        r=client.post(base+'/publish-answers',headers=th,json={'question':i+1})
        assert r.status_code==200,r.text
        assert r.json()['answerRelease']['published']==i+1
        board=client.get(base+'/board',headers=th).text
        assert f'唯一参考答案{i+1}' in board
        for later in range(i+2,4):assert f'唯一参考答案{later}' not in board
        now=client.get(student,headers=sh).json()
        assert not now['questions'][i]['canSubmit']
        assert [q['id'] for q in now['questions']] == ids[:i+1]
        assert all(not q['canSubmit'] for q in now['questions'])
        assert now['canSubmit']==(i<2)
        assert client.post(student+f'/{qid}',headers=sh,data={'text':'看答案后改交','revision':1}).status_code==409
        # Retry the same release and refresh the page: no accidental next release.
        assert client.post(base+'/publish-answers',headers=th,json={'question':i+1}).json()['answerRelease']['published']==i+1
        assert client.get(base,headers=th).json()['answerRelease']['published']==i+1
        if i<2:
            nextq=client.post(base+'/practice-question',headers=th,json={'question':i+2})
            assert nextq.status_code==200,nextq.text
            assert nextq.json()['answerRelease']['currentQuestion']==i+2
            assert '唯一参考答案' not in client.get(base+'/board',headers=th).text
    # The previous release format retains already-public answers across deployment.
    from sqlalchemy import update
    with legacy.SessionLocal() as db:
        t=legacy.Base.metadata.tables['weekend_slide_state']
        db.execute(update(t).where(t.c.session_id==sid).values(stage_no=4,idx=0));db.commit()
    assert client.get(base,headers=th).json()['answerRelease']['published']==3
    assert client.get(student,headers=sh).json()['canSubmit'] is False
print('OK')
''')
