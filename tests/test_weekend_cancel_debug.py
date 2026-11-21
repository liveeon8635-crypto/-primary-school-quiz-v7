from pathlib import Path
import importlib.util
import sys

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("cancel_debug_helpers", ROOT / "tests/test_homework_solve.py")
helpers = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = helpers
spec.loader.exec_module(helpers)


def test_cancel_debug_classrooms_real_routes(tmp_path):
    helpers.run_isolated(tmp_path, helpers.COMMON + r'''
from sqlalchemy import insert, func, update, delete
from datetime import datetime
with TestClient(app) as client:
    th, sh, student_id, school_id = setup(client)
    with legacy.SessionLocal() as db:
        p = db.scalar(select(legacy.TeachingProgram).where(legacy.TeachingProgram.school_id == school_id))
        lesson = db.scalar(select(legacy.TeachingLesson).where(legacy.TeachingLesson.program_id == p.id,
            legacy.TeachingLesson.subject == '数学', legacy.TeachingLesson.lesson_no == 10))
        lesson.title='调试教案'; lesson.core_target='用字母表示数'; lesson.teacher_plan='保留完整教案'
        db.commit(); lid = lesson.id
    url = f'/teacher/weekend/lessons/{lid}'
    def new_class():
        r = client.post('/teacher/weekend/sessions', headers=th, json={'lessonId':lid})
        assert r.status_code == 200, r.text
        return r.json()['id']
    def cancel(ids):
        return client.post(url+'/cancel-debug-classrooms', headers=th,
            json={'subject':'数学','lessonNo':10,'confirmed':True,'sessionIds':ids})
    first = new_class()
    r = client.post(f'/teacher/weekend/sessions/{first}/written/questions', headers=th,
        json={'stem':'仅供调试的课堂题','reference':'答案'})
    assert r.status_code == 200, r.text
    assert client.post(f'/teacher/weekend/sessions/{first}/start', headers=th).status_code == 200
    assert client.post(f'/teacher/weekend/sessions/{first}/goto', headers=th, json={'stage':3}).status_code == 200
    assert client.request('DELETE', url, headers=th, json={'subject':'数学','lessonNo':10,'confirmed':True}).status_code == 409
    preview = client.get(url+'/debug-classrooms', headers=th)
    assert [r['id'] for r in preview.json()['items']] == [first]
    assert client.post(url+'/cancel-debug-classrooms', headers=sh,
        json={'subject':'数学','lessonNo':10,'confirmed':True,'sessionIds':[first]}).status_code == 403
    assert client.post(url+'/cancel-debug-classrooms', headers=th,
        json={'subject':'数学','lessonNo':10,'confirmed':False,'sessionIds':[first]}).status_code == 400
    second = new_class()
    assert client.post(f'/teacher/weekend/sessions/{second}/finish', headers=th).status_code == 200
    with legacy.SessionLocal() as db:
        courseware = legacy.Base.metadata.tables['weekend_courseware']
        owner = db.scalar(select(legacy.User.id).where(legacy.User.username=='teacher1'))
        db.execute(insert(courseware).values(school_id=school_id,lesson_id=lid,teacher_id=owner,
            kind='steps',stage_no=3,status='draft',params_json='{}',
            live_json=json.dumps({f'{first}:3:1':{'step':2},'999999:3:1':{'step':1}}),updated_at=datetime.utcnow()))
        db.commit()
    assert cancel([first]).status_code == 409  # A new classroom must not be silently included.
    r = cancel([first,second]); assert r.status_code == 200, r.text
    assert r.json()['cancelled'] == 2
    assert client.get(f'/teacher/weekend/sessions/{first}', headers=th).status_code == 404
    assert client.get(url, headers=th).json()['teacherPlan'] == '保留完整教案'
    with legacy.SessionLocal() as db:
        log = db.scalar(select(legacy.AuditLog).where(legacy.AuditLog.action == 'weekend.cancel_debug_classrooms'))
        snapshot = json.loads(log.detail)
        assert len(snapshot['sessions']) == 2
        assert snapshot['related']['weekend_stage_log']
        assert snapshot['related']['weekend_written_questions'][0]['stem'] == '仅供调试的课堂题'
        assert snapshot['coursewareLive']['removed'] == {f'{first}:3:1':{'step':2}}
        remaining = db.scalar(select(courseware.c.live_json).where(courseware.c.lesson_id==lid))
        assert json.loads(remaining) == {'999999:3:1':{'step':1}}
    r = client.request('DELETE', url, headers=th, json={'subject':'数学','lessonNo':10,'confirmed':True})
    assert r.status_code == 200, r.text
    assert client.get(url, headers=th).json()['teacherPlan'] == ''
    # Even a hint (without an answer) is actual participation and blocks removal.
    third = new_class()
    with legacy.SessionLocal() as db:
        sessions = legacy.Base.metadata.tables['weekend_sessions']
        owner = db.scalar(select(sessions.c.teacher_id).where(sessions.c.id == third))
        db.execute(update(sessions).where(sessions.c.id == third).values(teacher_id=owner+1000)); db.commit()
    assert cancel([third]).status_code == 409  # Cannot cancel another teacher's classroom.
    with legacy.SessionLocal() as db:
        db.execute(update(sessions).where(sessions.c.id == third).values(teacher_id=owner,status='finished')); db.commit()
    assert client.get(url+'/debug-classrooms', headers=th).status_code == 200
    with legacy.SessionLocal() as db:
        db.execute(update(sessions).where(sessions.c.id == third).values(status='planned'))
        answers = legacy.Base.metadata.tables['weekend_answers']
        db.execute(insert(answers).values(school_id=school_id,session_id=third,student_id=student_id,
            question_id=999,selected=0,correct=True,max_hint=0)); db.commit()
    assert cancel([third]).status_code == 409
    with legacy.SessionLocal() as db:
        db.execute(delete(answers).where(answers.c.session_id == third))
        reports = legacy.Base.metadata.tables['weekend_reports']
        db.execute(insert(reports).values(school_id=school_id,teacher_id=owner,student_id=student_id,
            report_date='2026-11-07',session_key=str(third),draft_json='{}',draft_revision=1,draft_hash='x',
            draft_saved_at=datetime.utcnow(),published_version=0,created_at=datetime.utcnow())); db.commit()
    assert cancel([third]).status_code == 409  # Report drafts also count, even without answers.
    with legacy.SessionLocal() as db:
        db.execute(delete(reports).where(reports.c.session_key == str(third))); db.commit()
    with legacy.SessionLocal() as db:
        table = legacy.Base.metadata.tables['weekend_hint_log']
        db.execute(insert(table).values(school_id=school_id,session_id=third,student_id=student_id,question_id=999,level=1))
        db.commit()
    assert cancel([third]).status_code == 409
    fourth = new_class()
    assert cancel([third,fourth]).status_code == 409
    assert client.get(f'/teacher/weekend/sessions/{fourth}', headers=th).status_code == 200
    assert client.get(f'/teacher/weekend/sessions/{third}', headers=th).status_code == 200
    # force=True revokes test classrooms even when answers/hints/reports exist, but never another teacher's.
    with legacy.SessionLocal() as db:
        reports = legacy.Base.metadata.tables['weekend_reports']
        db.execute(insert(reports).values(school_id=school_id,teacher_id=owner,student_id=student_id,
            report_date='2026-11-08',session_key=str(third),draft_json='{}',draft_revision=1,draft_hash='y',
            draft_saved_at=datetime.utcnow(),published_version=0,created_at=datetime.utcnow()))
        db.commit()
    all_preview = client.get(url+'/debug-classrooms?includeAll=1', headers=th)
    assert all_preview.status_code == 200 and sorted(r['id'] for r in all_preview.json()['items']) == sorted([third, fourth])
    forced = client.post(url+'/cancel-debug-classrooms', headers=th,
        json={'subject':'数学','lessonNo':10,'confirmed':True,'force':True,'sessionIds':[third, fourth]})
    assert forced.status_code == 200, forced.text
    assert forced.json()['cancelled'] == 2
    assert client.get(f'/teacher/weekend/sessions/{third}', headers=th).status_code == 404
    assert client.get(f'/teacher/weekend/sessions/{fourth}', headers=th).status_code == 404
    with legacy.SessionLocal() as db:
        reports = legacy.Base.metadata.tables['weekend_reports']
        assert db.scalar(select(func.count()).select_from(reports).where(reports.c.session_key == str(third))) == 0
    page = client.get('/v1/weekend-plan').text
    assert '撤销调试课堂' in page and '强制撤销测试课堂' in page and '/cancel-debug-classrooms' in page
    for route in ('/v1/weekend-plan','/v1/training'):
        response = client.get(route, headers={'User-Agent':'Version/12.1 Mobile Safari/605.1.15'})
        assert response.status_code == 200, response.text[:200]
        assert 'cy-safari12-runtime' in response.text
        assert '撤销调试课堂' in response.text
print('OK')
''')


def test_debug_cancel_button_preview_confirmation_and_errors():
    import subprocess
    from changying.web.weekend_pages import PLAN_JS
    handler = PLAN_JS.split("      var cancelDebugBtn=", 1)[1].split("      var deleteBtn=", 1)[0]
    script = r'''
const assert=require('node:assert/strict');
function el(tag,attrs){return {...attrs}}
const r={lessonId:7,lessonNo:10},SUBJ='数学',deleteFeedback={};
let allow=false,calls=[],prompt='',fail=false;
function confirm(text){prompt=text;return allow}
function api(path,opts){
 calls.push({path,opts});
 if(fail)return Promise.reject(new Error('已有学生作答，不能撤销'));
 return Promise.resolve(opts?{message:'已撤销，教案保留'}:{items:[{id:12,title:'数学第10课'}]});
}
async function settle(){for(let i=0;i<12;i++)await Promise.resolve()}
var cancelDebugBtn=''' + handler + r'''
(async()=>{
 cancelDebugBtn.onclick();await settle();
 assert.equal(calls.length,1);assert.equal(calls[0].opts,undefined);
 assert(prompt.includes('没有实际上课'));assert(!cancelDebugBtn.disabled);
 allow=true;calls=[];cancelDebugBtn.onclick();await settle();
 assert.equal(calls.length,2);assert(calls[1].path.endsWith('/cancel-debug-classrooms'));
 assert.deepEqual(calls[1].opts.json,{subject:'数学',lessonNo:10,confirmed:true,sessionIds:[12]});
 assert(deleteFeedback.textContent.includes('教案保留'));assert(!cancelDebugBtn.disabled);
 fail=true;calls=[];cancelDebugBtn.onclick();await settle();
 assert.equal(calls.length,1);assert(deleteFeedback.textContent.includes('已有学生作答'));
 assert(!cancelDebugBtn.disabled);
})().catch(e=>{console.error(e);process.exitCode=1});
'''
    result = subprocess.run(['node','-e',script],text=True,capture_output=True,timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr
