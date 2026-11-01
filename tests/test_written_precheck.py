from __future__ import annotations

import importlib.util
import sys
import subprocess
from pathlib import Path

import pytest

from changying.services.written_precheck import equivalent, preview, transcription_prompt


@pytest.mark.parametrize("a,b,expected", [
    ("a×1.5", "1.5a", True), ("m*m", "m²", True), ("4b+6a", "6a+4b", True),
    ("10ab", "6a+4b", False), ("100-7a", "100-7*a", True), ("1/2", "0.5", True),
    (".5", "0.5", True), ("1kg", "1000g", None), ("舍己救人", "舍己救人", None),
    ("__import__('os')", "1", None), ("(a^6)^6", "a", None), ("2^100000", "1", None),
])
def test_bounded_independent_math_comparison(a, b, expected):
    assert equivalent(a, b) is expected


def test_matching_uncertainty_multi_blank_and_unconstrained_variable_names():
    stem = "（1）a×1.5简写成（）。 （2）一个数的3倍减去5，用式子表示是（）。"
    ref = "（1）1.5a （2）3x-5"
    obs = [dict(key="1", question="a×1.5简写成（）。", answers=["1.5a"], confidence=.98),
           dict(key="2", question="一个数的3倍减去5，用式子表示是（）。", answers=["3a-5"], confidence=.98)]
    assert preview(stem, ref, obs)["suggestedResult"] == "correct"
    obs[1]["question"] = "m×m简写成（）。"
    assert preview(stem, ref, obs)["suggestedResult"] is None
    obs[1]["question"] = "一个数的3倍减去5，用式子表示是（）。"
    obs[1]["confidence"] = .4
    assert preview(stem, ref, obs)["suggestedResult"] is None
    obs[1]["confidence"] = .98
    assert preview(stem, ref, obs + [obs[0]])["suggestedResult"] is None
    assert preview(stem, ref, obs + [dict(key="99")])["suggestedResult"] is None
    multi = preview("每本a元，买7本付（）元，付100元找回（）元。", "7a；100-7a",
        [dict(key="1", question="每本a元，买7本付（）元，付100元找回（）元。", answers=["7a", "100-7a"], confidence=1)])
    assert multi["suggestedResult"] == "correct"
    assert "不判对错" in transcription_prompt()


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("precheck_hw_helpers", ROOT / "tests/test_homework_solve.py")
helpers = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = helpers
spec.loader.exec_module(helpers)


def test_real_upload_teacher_correction_confirmation_and_stale_versions(tmp_path):
    helpers.run_isolated(tmp_path, helpers.COMMON + r'''
import base64
from sqlalchemy import update
from changying.web import weekend_precheck as wp
PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+j5WQAAAAASUVORK5CYII=")
observed = [dict(key="1", question="a×1.5简写成（）。", answers=["1.5a"], confidence=.98),
            dict(key="2", question="m×m简写成（）。", answers=["2m"], confidence=.98)]
ocr_calls = []
def fake_ocr(impl, db, user, image, **kw):
    assert image == PNG
    assert db.get_bind().pool.checkedout()==0, 'OCR must not retain a pooled DB connection'
    assert "1.5a" not in kw['prompt'] and 'student1' not in kw['prompt']
    ocr_calls.append(kw)
    return {'text':json.dumps({'items':observed}), 'confidence':.98}
wp.vision_enabled = lambda: True
wp.recognize_image = fake_ocr
with TestClient(app) as client:
    th, sh, student_id, school_id = setup(client)
    with legacy.SessionLocal() as db:
        p = db.scalar(select(legacy.TeachingProgram).where(legacy.TeachingProgram.school_id == school_id))
        lesson = legacy.TeachingLesson(school_id=school_id, program_id=p.id, subject='数学', lesson_no=93, title='预批测试', core_target='代数式')
        db.add(lesson);db.flush();lid=lesson.id
        tid=db.scalar(select(legacy.User.id).where(legacy.User.username=='teacher1'))
        cls=db.scalar(select(legacy.SchoolClass).where(legacy.SchoolClass.school_id==school_id));cls.teacher_id=tid
        link=db.scalar(select(legacy.ClassStudent).where(legacy.ClassStudent.student_id==student_id))
        if link: link.class_id=cls.id
        else: db.add(legacy.ClassStudent(class_id=cls.id,student_id=student_id))
        db.commit()
    s=client.post('/teacher/weekend/sessions',headers=th,json={'lessonId':lid}).json()['id']
    base=f'/teacher/weekend/sessions/{s}/written'
    qid=client.post(base+'/questions',headers=th,json={'stem':'（1）a×1.5简写成（）。 （2）m×m简写成（）。','reference':'（1）1.5a （2）m²'}).json()['id']
    q2=client.post(base+'/questions',headers=th,json={'stem':'12-5=（）','reference':'7'}).json()['id']
    client.post(f'/teacher/weekend/sessions/{s}/start',headers=th)
    client.post(f'/teacher/weekend/sessions/{s}/goto',headers=th,json={'stage':4})
    # A single-connection pool reproduces the production pressure deterministically.
    # Upload + teacher retry + OCR must release their read transactions before waiting.
    from sqlalchemy import create_engine
    limited_engine=create_engine(legacy.engine.url,pool_size=1,max_overflow=0,pool_timeout=.2,connect_args={'check_same_thread':False})
    legacy.SessionLocal.configure(bind=limited_engine)
    url=f'/student/weekend/sessions/{s}/written/{qid}'
    saved=client.post(url,headers=sh,files={'photo':('answer.png',PNG,'image/png')})
    assert saved.status_code==200,saved.text
    assert saved.json()['result']=='pending' and 'precheck' not in saved.text and len(ocr_calls)==1
    a=next(i for i in client.get(base,headers=th).json()['items'] if i['questionId']==qid)
    aid=a['id'];job=a['precheck'];assert a['result']=='pending' and job['suggestedResult']=='partial' and job['status']=='ready'
    assert job['items'][1]['comparisons']==[False]
    students=client.get(f'/student/weekend/sessions/{s}/written',headers=sh)
    assert 'precheck' not in students.text and 'suggestedResult' not in students.text and 'reference' not in students.text
    assert client.post(base+f'/{aid}/precheck',headers=sh,json={'revision':1}).status_code==403
    # Repeating the generation request is idempotent; no second paid OCR call.
    assert client.post(base+f'/{aid}/precheck',headers=th,json={'revision':1}).status_code==200
    assert len(ocr_calls)==1
    status_read=client.get(base+f'/{aid}/precheck?revision=1',headers=th)
    assert status_read.status_code==200 and status_read.json()['precheck']['suggestedResult']=='partial'
    assert client.get(base+f'/{aid}/precheck?revision=1',headers=sh).status_code==403
    review=base+f'/{aid}/review'
    old={'revision':1,'result':'partial','precheckId':job['id'],'precheckToken':job['token']}
    assert client.post(review,headers=th,json={**old,'precheckToken':'wrong'}).status_code==409
    corrected=[{**x,'answers':['m²'] if x['key']=='2' else x['answers'],'confidence':1} for x in observed]
    r=client.post(base+f'/{aid}/precheck/transcription',headers=th,json={'revision':1,'token':job['token'],'items':corrected})
    assert r.status_code==200,r.text
    current=r.json()['precheck'];assert current['suggestedResult']=='correct' and current['transcriptionReviewed']
    assert client.post(review,headers=th,json=old).status_code==409
    # Suggestions and teacher corrections alone never change formal marks.
    a=next(i for i in client.get(base,headers=th).json()['items'] if i['id']==aid)
    assert a['result']=='pending' and a['revision']==1
    confirm={'revision':1,'result':'correct','precheckId':current['id'],'precheckToken':current['token']}
    assert client.post(review,headers=th,json=confirm).status_code==200
    assert client.post(review,headers=th,json=confirm).status_code==409
    # Resubmission resets formal marks and creates a different preview version.
    again=client.post(url,headers=sh,data={'text':'订正','revision':2})
    assert again.status_code==200 and again.json()['revision']==3
    a=next(i for i in client.get(base,headers=th).json()['items'] if i['id']==aid)
    assert a['result']=='pending' and a['precheck']['revision']==3
    assert client.post(review,headers=th,json=confirm).status_code==409
    # Updating the reference invalidates a previously matching preview, even with unchanged submission.
    latest=a['precheck']
    with legacy.SessionLocal() as db:
        qt=legacy.Base.metadata.tables['weekend_written_questions']
        db.execute(update(qt).where(qt.c.id==qid).values(reference='（1）2a （2）m²'));db.commit()
    assert client.post(review,headers=th,json={'revision':3,'result':latest['suggestedResult'],'precheckId':latest['id'],'precheckToken':latest['token']}).status_code==409
    # Typed numeric answers use the same independent comparison without OCR or AI permission.
    typed=client.post(f'/student/weekend/sessions/{s}/written/{q2}',headers=sh,data={'text':'7'})
    assert typed.status_code==200
    assert next(i for i in client.get(base,headers=th).json()['items'] if i['questionId']==q2)['precheck']['suggestedResult']=='correct'
    # Wrong worksheet, low confidence, provider errors, no permission: save the answer, keep formal pending.
    for mode in ('mismatch','low','error','disabled'):
        with legacy.SessionLocal() as db:
            st=legacy.Base.metadata.tables['weekend_written_submissions']
            db.execute(update(st).where(st.c.id==aid).values(revision=20+len(ocr_calls),result='pending'));db.commit()
            revision=db.execute(select(st.c.revision).where(st.c.id==aid)).scalar_one()
        def response(impl,db,user,image,**kw):
            ocr_calls.append(kw)
            if mode=='error': raise HTTPException(504,'do not leak provider details')
            if mode=='disabled': raise HTTPException(403,'private configuration')
            items=[dict(key='1',question='6×p简写成（）。' if mode=='mismatch' else observed[0]['question'],answers=['1.5a'],confidence=.98)]
            return {'text':json.dumps({'items':items}), 'confidence':.2 if mode=='low' else .98}
        wp.recognize_image=response
        r=client.post(base+f'/{aid}/precheck',headers=th,json={'revision':revision,'retry':True})
        assert r.status_code==200
        record=next(i for i in client.get(base,headers=th).json()['items'] if i['id']==aid)
        assert record['result']=='pending' and record['precheck']['suggestedResult'] is None
        if mode=='error': assert record['precheck']['code']=='timeout' and '超时' in record['precheck']['message']
        if mode=='disabled': assert record['precheck']['code']=='not_enabled'
        assert 'private configuration' not in json.dumps(record) and 'provider details' not in json.dumps(record)
    # The actual classroom page contains the new controls, not merely unused helper definitions.
    html=client.get('/v1/weekend').text
    for text in ('系统预批','precheck/transcription','我已逐项核验，采用预批并保存','学生答案识别内容'):
        assert text in html,text
    with legacy.SessionLocal() as db:
        sessions=legacy.Base.metadata.tables['weekend_sessions']
        db.execute(update(sessions).where(sessions.c.id==s).values(teacher_id=999999));db.commit()
    assert client.post(base+f'/{aid}/precheck',headers=th,json={'revision':revision}).status_code==404
print('OK')
''')


def test_teacher_page_does_not_auto_confirm_and_sends_versioned_adoption():
    from changying.web.weekend_written_pages import WRITTEN_JS
    script = r'''
const assert=require('node:assert/strict');
const requests=[];let allow=false;
function el(tag,attrs,...children){return {tag,attrs:attrs||{},children,value:attrs&&attrs.value||'',style:{},hidden:false,
 appendChild(c){this.children.push(c);return c},remove(){},addEventListener(){}}}
const window={addEventListener(){}},document={hidden:false},SID=1,TOKEN='test';
function confirm(){return allow}
const data={status:'running',total:1,submitted:1,students:[],questions:[{id:2,stem:'12-5=（）',reference:'7'}],
 items:[{id:3,questionId:2,studentId:4,name:'测试学生',revision:1,result:'pending',comment:'',text:'7',hasPhoto:false,
 precheck:{id:5,revision:1,token:'version-token',status:'ready',suggestedResult:'correct',message:'待核验',
 items:[{key:'1',question:'12-5=（）',observedQuestion:'12-5=（）',answers:['7'],reference:['7'],result:'correct',reason:'程序核对相符'}]}}]};
async function api(url,options){requests.push({url,options});if(url.endsWith('/written'))return data;
 if(url.endsWith('/review-batch'))return {reviewed:true,items:[{id:3,revision:2,result:'correct',comment:''}]};throw Error(url)}
function all(n){return [n,...(n.children||[]).filter(x=>x&&typeof x==='object').flatMap(all)]}
(async()=>{
 const box=el('div');writtenTeacher(box);await new Promise(setImmediate);
 assert.equal(requests.length,1,'loading a ready preview must not grade');
 const button=all(box).find(e=>e.attrs.text==='我已逐项核验，采用预批并保存');assert(button);
 button.attrs.onclick();await new Promise(setImmediate);assert.equal(requests.length,1,'cancel confirmation writes nothing');
 allow=true;button.attrs.onclick();await new Promise(setImmediate);
 const post=requests.find(r=>r.url.endsWith('/review-batch'));assert(post);
 assert.deepEqual(post.options.json.items,[{id:3,revision:1,result:'correct',comment:'',precheckId:5,precheckToken:'version-token'}]);
 console.log('OK');
})().catch(e=>{console.error(e);process.exit(1)});
'''
    result = subprocess.run(['node', '-e', WRITTEN_JS + script], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'OK' in result.stdout


def test_retry_updates_its_own_row_polls_and_limits_automatic_requests():
    from changying.web.weekend_written_pages import WRITTEN_JS
    script = r'''
const assert=require('node:assert/strict');
class E{constructor(tag,attrs){this.tag=tag;this.attrs=attrs||{};this.children=[];this.value='';this.disabled=false;this.style={}}
appendChild(c){this.children.push(c);return c}remove(){}addEventListener(){}
set textContent(v){this._text=v;this.children=[]}get textContent(){return this._text||this.attrs.text||''}}
function el(tag,attrs,...cs){const e=new E(tag,attrs);cs.forEach(c=>e.appendChild(c));return e}
function all(e){return [e,...e.children.filter(c=>c instanceof E).flatMap(all)]}
function text(e){return all(e).map(x=>x.textContent).join(' ')}
const timers=[];function setTimeout(f){timers.push(f)}
const window={addEventListener(){}},document={hidden:false},SID=1,TOKEN='test';function confirm(){return true}
async function flush(){for(let i=0;i<80;i++)await Promise.resolve()}
let mode='working',posts=[],reads=0,wholeReads=0;
const original={status:'running',total:2,submitted:2,students:[],questions:[{id:2,stem:'12-5=（）',reference:'7'}],items:[3,4].map(id=>({id,questionId:2,studentId:id,name:'测试'+id,revision:1,result:'pending',comment:'',text:'7',hasPhoto:false,precheck:{status:'failed',message:'旧的失败提示'}}))};
let data=original;
function api(url,opts){
 if(url.endsWith('/written')){wholeReads++;return Promise.resolve(JSON.parse(JSON.stringify(data)))}
 if(url.endsWith('/precheck')&&opts){posts.push(url);return Promise.resolve({queued:true})}
 if(url.includes('/precheck?')){reads++;return Promise.resolve({revision:1,precheck:mode==='working'?{status:'working',message:'旧失败信息不得覆盖进度'}:mode==='ready'?{id:5,revision:1,token:'new',status:'ready',suggestedResult:'correct',items:[],message:'预批完成'}:{status:'failed',message:'本次识别超时，请重试；仍可手工批改'}})}
 throw Error('unexpected '+url);
}
''' + WRITTEN_JS + r'''
(async()=>{
 const box=new E('div');writtenTeacher(box);await flush();
 const rows=all(box).filter(n=>n.tag==='div'&&n.children.some(c=>c instanceof E&&c.tag==='b'&&c.textContent.includes('测试')));
 assert.equal(rows.length,2);const row=rows[0],other=rows[1];
 const comment=all(row).find(n=>n.tag==='textarea');comment.value='老师未保存的评语';comment.oninput();
 const pick=all(row).find(n=>n.tag==='select');pick.value='partial';pick.onchange();
 const button=all(row).find(n=>n.tag==='button'&&n.attrs.text==='生成／重试预批');button.attrs.onclick();
 assert(button.disabled);assert(text(row).includes('正在识别'),'progress must be in the clicked row immediately');
 await flush();assert.equal(reads,1);assert.equal(timers.length,1);assert(button.disabled);
 assert(!text(row).includes('旧失败信息不得覆盖进度'));
 mode='ready';timers.shift()();await flush();
 assert(all(row).some(n=>n.attrs.text==='我已逐项核验，采用预批并保存'));
 assert.equal(comment.value,'老师未保存的评语');assert.equal(pick.value,'partial');assert.equal(wholeReads,1,'do not rebuild the class or lose drafts');
 assert(text(other).includes('旧的失败提示'),'other rows stay unchanged');
 mode='failed';all(other).find(n=>n.attrs.text==='生成／重试预批').attrs.onclick();await flush();
 assert(text(other).includes('本次识别超时'));assert(!all(other).find(n=>n.attrs.text==='生成／重试预批').disabled);
 // Four old submissions do not launch four recognition requests at once.
 posts=[];mode='working';data={...original,total:4,submitted:4,items:[7,8,9,10].map(id=>({...original.items[0],id,precheck:null}))};
 const queued=new E('div');writtenTeacher(queued);await flush();assert.equal(posts.length,2);
 assert(text(queued).includes('已排队'));console.log('OK');
})().catch(e=>{console.error(e);process.exit(1)});
'''
    result = subprocess.run(['node'], input=script, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'OK' in result.stdout
