from __future__ import annotations
import importlib.util
import sys
from pathlib import Path
from changying.services.weekend_presentation import presentation_pages

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('weekend_flow_helpers',ROOT/'tests/test_homework_solve.py')
helpers=importlib.util.module_from_spec(spec);sys.modules[spec.name]=helpers;spec.loader.exec_module(helpers)


def test_presentation_keeps_full_text_and_groups_fragmented_word_decks():
    lines=['方法'+str(i)+'：代入人物，梳理情节，理解心理。' for i in range(26)]
    pages=presentation_pages(lines)
    assert 1<len(pages)<26
    assert '\n\n'.join(pages)=='\n\n'.join(lines)
    long='阅读材料\n'+('完整段落，不得截断。'*200)
    assert ''.join(presentation_pages([long]))==long
    assert all(len(p)<=360 for p in presentation_pages([long]))
    assert presentation_pages(lines,preserve_pages=True)==lines
    source='单元高频考点讲解\n方法1 代入角色\n梳理关键情节，理解人物心理，再使用第一人称。\n学生随堂试卷\n问题\n教师专用答案：秘密'
    actual=presentation_pages(lines,source=source)
    assert '梳理关键情节' in '\n'.join(actual) and '秘密' not in '\n'.join(actual)
    assert '问题' not in '\n'.join(actual)
    imported=['旧标题'+str(i) for i in range(12)]+['学生随堂试卷','阅读文章','第一题','教师参考答案与采分点','秘密答案']
    examples='\n'.join(presentation_pages(imported,example_mode=True))
    assert '阅读文章' in examples and '第一题' in examples and '秘密答案' not in examples and '旧标题' not in examples
    assert presentation_pages([{'title':'例题','question':'问题','answer':'解法'}])==['例题\n问题\n答案：解法']
    assert presentation_pages([{'title':'例题','question':'问题','answer':'参考答案：5m'}])==['例题\n问题\n参考答案：5m']


def test_class_snapshot_limits_questions_progress_grading_and_awards(tmp_path):
    helpers.run_isolated(tmp_path,helpers.COMMON+r'''
from sqlalchemy import insert,update,delete
with TestClient(app) as client:
    th,sh,student_id,school_id=setup(client)
    with legacy.SessionLocal() as db:
        teacher=db.scalar(select(legacy.User).where(legacy.User.username=='teacher1'))
        p=db.scalar(select(legacy.TeachingProgram).where(legacy.TeachingProgram.school_id==school_id))
        a=legacy.SchoolClass(school_id=school_id,name='五年级语文甲班',grade=5,teacher_id=teacher.id)
        b=legacy.SchoolClass(school_id=school_id,name='五年级语文乙班',grade=5,teacher_id=teacher.id)
        empty=legacy.SchoolClass(school_id=school_id,name='空班',grade=5,teacher_id=teacher.id)
        db.add_all([a,b,empty]);db.flush();aid,bid,eid=a.id,b.id,empty.id
        db.add(legacy.ClassStudent(class_id=aid,student_id=student_id))
        # A second pupil belongs to the same teacher but a different class.
        other=legacy.User(school_id=school_id,username='class_b_pupil',name='乙班同学',role='student',grade=5,password_hash=teacher.password_hash)
        db.add(other);db.flush();other_id=other.id
        db.add(legacy.ClassStudent(class_id=bid,student_id=other_id))
        l=legacy.TeachingLesson(school_id=school_id,program_id=p.id,subject='语文',lesson_no=12,title='阅读',ppt_json=json.dumps(['长文第'+str(i)+'页' for i in range(132)]),examples_json=json.dumps(['例题讲解第'+str(i)+'行' for i in range(132)]),reading_plan=json.dumps(['短文'+str(i) for i in range(3)],ensure_ascii=False))
        db.add(l);db.flush();lid=l.id
        q=legacy.TeachingQuestion(school_id=school_id,program_id=p.id,level='C',lesson_id=lid,subject='语文',stem='概括',options_json='["甲","乙"]',correct_index=0,active=True,knowledge='概括')
        db.add(q);db.flush();qid=q.id;db.commit()
    configured=client.put('/teacher/weekend/schedule/语文/12/course-type',headers=th,json={'courseType':'reading','expectedRevision':0})
    assert configured.status_code==200,configured.text
    listed=client.get('/teacher/weekend/classes',headers=th)
    assert listed.status_code==200 and any(c['id']==aid and c['studentCount']==1 for c in listed.json()['items'])
    assert client.get('/teacher/weekend/classes',headers=sh).status_code==403
    assert client.post('/teacher/weekend/sessions',headers=th,json={'lessonId':lid,'classId':999999}).status_code==404
    assert client.post('/teacher/weekend/sessions',headers=th,json={'lessonId':lid,'classId':eid}).status_code==400
    created=client.post('/teacher/weekend/sessions',headers=th,json={'lessonId':lid,'classId':aid})
    assert created.status_code==200,created.text
    session=created.json()['id'];base=f'/teacher/weekend/sessions/{session}'
    assert created.json()['class']=={'id':aid,'name':'五年级语文甲班','studentCount':1}
    w=client.post(base+'/written/questions',headers=th,json={'stem':'阅读文章\n回答问题','reference':'教师秘密'})
    assert w.status_code==200,w.text
    wid=w.json()['id']
    client.post(base+'/start',headers=th);client.post(base+'/goto',headers=th,json={'stage':2})
    board=client.get(base+'/board',headers=th).json()
    assert board['deck']['total']==3 and board['content']==['短文0']
    short2=client.post(base+'/slide',headers=th,json={'delta':1}).json()
    assert short2['content']==['短文1']
    client.post(base+'/goto',headers=th,json={'stage':3})
    example=client.get(base+'/board',headers=th).json()
    assert example['deck']['total']==132 and example['content']==['长文第0页']
    client.post(base+'/slide',headers=th,json={'delta':1})
    assert client.get(base+'/board',headers=th).json()['content']==['长文第1页']
    changed=client.post(base+'/slide',headers=th,json={'delta':1}).json()
    second_screen=client.get(base+'/board',headers=th).json()
    assert second_screen['deck']==changed['deck'] and second_screen['content']==changed['content']
    client.post(base+'/goto',headers=th,json={'stage':5})
    rel=client.post(base+'/practice-question', headers=th, json={'question':1}); assert rel.status_code == 200, (rel.text, client.get(base,headers=th).json())
    progress=client.get(base+'/progress',headers=th).json()['items']
    assert [i['studentId'] for i in progress]==[student_id]
    assert client.get(base+'/written',headers=th).json()['total']==1
    # Same-school, same-teacher other-class pupil cannot view or submit.
    with legacy.SessionLocal() as db:
        other=db.get(legacy.User,other_id)
        sec=legacy.security_for(db,other);sec.must_change_password=False;db.commit()
        token=legacy.make_token(other,sec)
    oh={'Authorization':'Bearer '+token}
    assert client.get('/student/weekend/current',headers=oh).json()['active'] is False
    assert client.get(f'/student/weekend/sessions/{session}/written',headers=oh).status_code==404
    assert client.post('/student/weekend/answer',headers=oh,json={'sessionId':session,'questionId':qid,'selected':0}).status_code==404
    assert client.post(f'/student/weekend/sessions/{session}/written/{wid}',headers=oh,data={'text':'越班答案'}).status_code==404
    # Snapshot survives changing class membership after the session was made.
    with legacy.SessionLocal() as db:
        db.execute(delete(legacy.ClassStudent).where(legacy.ClassStudent.class_id==aid))
        db.commit()
    assert client.get('/student/weekend/current',headers=sh).json()['sessionId']==session
    assert client.post('/student/weekend/answer',headers=sh,json={'sessionId':session,'questionId':qid,'selected':0}).status_code==200
    assert client.put(base+'/class',headers=th,json={'classId':bid}).status_code==409
    assert client.get(base+'/archive',headers=th).json()['students'][0]['studentId']==student_id
    assert all(i['studentId']==student_id for i in client.get(base+'/settle-preview',headers=th).json()['items'])
    assert client.get(base+'/written',headers=th).json()['total']==1
    html=client.get('/v1/weekend').text
    assert '选择本次上课的班级' in html and 'createWeekendClassroom(x.lessonId)' in html
    assert '学生作答与批改' in html and '临时补充一道题（仅开课前）' in html
    assert 'currentStatus||d.status' in html
    assert 'createWeekendClassroom(r.lessonId)' in client.get('/v1/weekend-plan').text
print('OK')
''')
