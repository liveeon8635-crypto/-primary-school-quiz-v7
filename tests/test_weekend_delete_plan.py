from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('delete_plan_helpers', ROOT / 'tests/test_homework_solve.py')
helpers = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = helpers
spec.loader.exec_module(helpers)


def test_delete_misimported_plan_clears_approved_questions_and_keeps_progress(tmp_path, monkeypatch):
    monkeypatch.setenv("TEACHING_DOCUMENT_AI_EGRESS_APPROVED", "1")
    helpers.run_isolated(tmp_path, helpers.COMMON + r'''
with TestClient(app) as client:
    th,sh,sid,school_id=setup(client)
    source='这份语文阅读教案误导入到了数学课，需清除文章以及已审核的题目。'
    replies.append(json.dumps({'title':'误导入的语文教案','coreTarget':'理解故事','teacherPlan':'阅读文章','ppt':['阅读'], 'examples':['例题'], 'closureTraining':'课后题',
        'questions':[{'stem':'选出人物','options':['阿木','鲁班'],'correctIndex':0}],
        'writtenQuestions':[{'stem':'概括故事','reference':'救助乡亲'}]},ensure_ascii=False))
    r=client.post('/teacher/weekend/lessons/import',headers=th,data={'subject':'数学','lessonNo':'17','text':source})
    assert r.status_code==200,r.text
    lid=r.json()['lessonId'];url=f'/teacher/weekend/lessons/{lid}'
    qid=client.get(url+'/questions',headers=th).json()['items'][0]['id']
    wid=client.get(url+'/written/questions',headers=th).json()['items'][0]['id']
    client.post(url+'/questions',headers=th,json={'approve':[qid]})
    client.post(url+'/written/questions',headers=th,json={'approve':[wid]})
    rows=[{'lessonNo':17,'schoolWeek':7,'schoolUnit':'正确数学单元','plannedDate':'2026-10-17','note':'保留进度'}]
    client.put('/teacher/weekend/schedule',headers=th,json={'subject':'数学','rows':rows})
    before=client.get(url,headers=th).json()
    body={'subject':'数学','lessonNo':17,'confirmed':True}
    assert client.request('DELETE',url,json=body).status_code==401
    assert client.request('DELETE',url,headers=sh,json=body).status_code==403
    assert client.request('DELETE',url,headers=th,json={**body,'confirmed':False}).status_code==400
    assert client.request('DELETE',url,headers=th,json={**body,'subject':'语文'}).status_code==400
    assert client.request('DELETE',url,headers=th,json={**body,'lessonNo':18}).status_code==400
    assert client.get(url,headers=th).json()==before
    # Cross-school lesson IDs cannot be used for deletion.
    with legacy.SessionLocal() as db:
        other_school=legacy.School(name='删除隔离测试学校',code='delete-isolation');db.add(other_school);db.flush()
        other_program=legacy.TeachingProgram(school_id=other_school.id,grade=5,semester='上',title='隔离课程');db.add(other_program);db.flush()
        other=legacy.TeachingLesson(school_id=other_school.id,program_id=other_program.id,subject='数学',lesson_no=17,title='别校教案',core_target='不得清除')
        db.add(other);db.commit();other_lid=other.id
    assert client.request('DELETE',f'/teacher/weekend/lessons/{other_lid}',headers=th,json=body).status_code==404
    r=client.request('DELETE',url,headers=th,json=body)
    assert r.status_code==200,r.text
    status=r.json()['status'];assert not status['hasPlan'] and status['approvedQuestions']==status['draftQuestions']==0
    got=client.get(url,headers=th).json()
    assert not got['sourceText'] and not got['teacherPlan'] and not got['closureTraining']
    assert got['ppt']==got['examples']==[]
    assert client.get(url+'/questions',headers=th).json()['items']==[]
    assert client.get(url+'/written/questions',headers=th).json()['items']==[]
    row=next(x for x in client.get('/teacher/weekend/schedule?subject=数学',headers=th).json()['items'] if x['lessonNo']==17)
    assert all(row[k]==rows[0][k] for k in ('schoolWeek','schoolUnit','plannedDate','note'))
    assert not row['hasPlan'] and row['approvedQuestions']==row['draftQuestions']==0
    # Retired question IDs cannot be resurrected through a stale approval call.
    client.post(url+'/questions',headers=th,json={'approve':[qid]})
    with legacy.SessionLocal() as db:
        old=db.get(legacy.TeachingQuestion,qid);assert not old.active and old.stem=='选出人物'
    # Re-import without force works, and does not delete historical question IDs.
    replies.append(json.dumps({'title':'正确数学教案','coreTarget':'计算','teacherPlan':'解题','ppt':['计算'],'examples':[],'questions':[]},ensure_ascii=False))
    r=client.post('/teacher/weekend/lessons/import',headers=th,data={'subject':'数学','lessonNo':'17','text':'这是正确的数学教案，讲解小数的加减计算与验算方法。'})
    assert r.status_code==200,r.text
    assert r.json()['lessonId']==lid and r.json()['status']['hasPlan']
    assert client.get(url+'/questions',headers=th).json()['items']==[]
    with legacy.SessionLocal() as db:assert db.get(legacy.TeachingQuestion,qid) is not None
    # Creating even a planned classroom protects the lesson and all its content.
    classroom=client.post('/teacher/weekend/sessions',headers=th,json={'lessonId':lid}).json()['id']
    before=client.get(url,headers=th).json()
    assert client.request('DELETE',url,headers=th,json=body).status_code==409
    assert client.get(url,headers=th).json()==before
    assert client.get(f'/teacher/weekend/sessions/{classroom}',headers=th).status_code==200
    # Legacy learning/essay records protect lesson content as well.
    with legacy.SessionLocal() as db:
        kept=legacy.TeachingLesson(school_id=school_id,program_id=db.get(legacy.TeachingLesson,lid).program_id,subject='数学',lesson_no=18,title='有作文记录的课',core_target='保留内容')
        db.add(kept);db.flush();kept_id=kept.id
        db.add(legacy.TeachingEssay(school_id=school_id,lesson_id=kept_id,student_id=sid,draft='学生原稿'))
        db.commit()
    protected=f'/teacher/weekend/lessons/{kept_id}'
    assert client.request('DELETE',protected,headers=th,json={'subject':'数学','lessonNo':18,'confirmed':True}).status_code==409
    assert client.get(protected,headers=th).json()['coreTarget']=='保留内容'
    html=client.get('/v1/weekend-plan').text
    assert '删除教案' in html and "method:'DELETE'" in html and '包括已通过的题' in html
    print('OK')
''')


def test_delete_button_requires_confirmation_and_shows_server_failure_locally():
    from changying.web.weekend_pages import PLAN_JS
    handler=PLAN_JS.split("      var deleteFeedback=el(",1)[1].split("      list.appendChild(el('div',{class:'card'}",1)[0]
    script=r'''
const assert=require('node:assert/strict');
function el(tag,attrs){return {...attrs,textContent:attrs.text||'',disabled:!!attrs.disabled}}
const r={lessonId:7,lessonNo:6,title:'误导入的语文教案'},SUBJ='数学',impBtn={},draftBtn={},qBtn={};
let calls=[],loads=0,notes=[],answer=false,prompt='';
function confirm(text){prompt=text;return answer}
function note(kind,text){notes.push(text)}function load(){loads++}
function api(path,opts){calls.push({path,opts});return Promise.reject(new Error('这节课已有课堂记录，不能删除'))}
async function settle(){for(let i=0;i<10;i++)await Promise.resolve()}
var deleteFeedback=el('''+handler+r'''
(async()=>{
 deleteBtn.onclick();assert.equal(calls.length,0);assert(prompt.includes('数学 · 第 6 次课'));assert(prompt.includes('包括已通过的题'));
 answer=true;deleteBtn.onclick();assert(deleteBtn.disabled);await settle();
 assert.equal(calls[0].opts.method,'DELETE');assert.equal(calls[0].opts.json.subject,'数学');assert(calls[0].opts.json.confirmed);
 assert(deleteFeedback.textContent.includes('已有课堂记录'));assert(!deleteBtn.disabled);assert.equal(loads,0);
 api=(path,opts)=>Promise.resolve({message:'教案已清除'});deleteBtn.onclick();await settle();assert.equal(loads,1);
})().catch(e=>{console.error(e);process.exitCode=1});
'''
    result=subprocess.run(['node','-e',script],text=True,capture_output=True,timeout=20)
    assert result.returncode==0,result.stdout+result.stderr
