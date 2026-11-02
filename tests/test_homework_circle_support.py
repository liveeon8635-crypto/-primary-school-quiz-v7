"""Circle-area support: real routes, non-scoring persistence, and actual student JS interactions."""
import importlib.util
import subprocess
import sys
from pathlib import Path

from changying.web.homework_circle_support_pages import CIRCLE_SUPPORT_JS

spec = importlib.util.spec_from_file_location('circle_helpers', Path(__file__).with_name('test_homework_solve.py'))
helpers = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = helpers
spec.loader.exec_module(helpers)


def test_circle_help_context_is_private_non_scoring_and_does_not_regenerate(tmp_path):
    helpers.run_isolated(tmp_path, helpers.COMMON + r'''
from sqlalchemy import func, update
from changying.services.homework_math_check import parse_answer
with TestClient(app) as client:
    th,sh,student,school=setup(client)
    with legacy.SessionLocal() as db:
        teacher=db.scalar(select(legacy.User).where(legacy.User.username=='teacher1'))
        cls=db.scalar(select(legacy.SchoolClass).where(legacy.SchoolClass.school_id==school))
        cls.teacher_id=teacher.id
        member=db.scalar(select(legacy.ClassStudent).where(legacy.ClassStudent.student_id==student))
        if member: member.class_id=cls.id
        else: db.add(legacy.ClassStudent(student_id=student,class_id=cls.id))
        db.commit()
        before=[r for r in db.scalars(select(legacy.Submission.answers_json))]
    hid=make_help(client,sh,'半径2厘米，π取3.14，求圆的面积。',6)
    url=f'/student/homework/help/{hid}'
    support={'entry':'before','focus':'concept','gaps':['radius'],'rounds':{'radius':1},'outcome':'practice_passed','unitChecked':True,'untrusted_note':'secret-injected-instruction'}
    assert client.post(url+'/circle-support',headers=th,json=support).status_code==403
    assert client.post(url+'/circle-support',headers=sh,json={**support,'gaps':['bad-gap']}).status_code==422
    assert client.post(url+'/circle-support',headers=sh,json={**support,'rounds':{'radius':3}}).status_code==422
    saved=client.post(url+'/circle-support',headers=sh,json=support)
    assert saved.status_code==200,saved.text
    assert not calls and 'untrusted_note' not in saved.text
    replies.append(sol(answer='12.56平方厘米',expression='3.14*2*2',kp='圆的面积'))
    solved=client.post(url+'/solve',headers=sh)
    assert solved.status_code==200,solved.text
    data=solved.json();assert data['circleEligible'] and data['circleSupport']['gaps']==['radius']
    assert len(calls)==1 and '半径与直径' in prompts[-1] and '非长期掌握结论' in prompts[-1]
    assert 'secret-injected-instruction' not in prompts[-1]
    assert data['solution']['layer'] is None  # no invented map/quiz when none is published
    progress={'selfSolved':True,'finalChecked':True,'wrongTries':1,'stepsAnswered':2}
    assert client.post(url+'/progress',headers=sh,json=progress).status_code==200
    after={'entry':'after','focus':'calculation','gaps':['square'],'rounds':{'square':2},'outcome':'needs_teacher'}
    assert client.post(url+'/circle-support',headers=sh,json=after).status_code==200
    assert client.post(url+'/solve',headers=sh).status_code==200 and len(calls)==1
    row=row_of(hid);stored=json.loads(row['ai_json'])
    assert stored['progress']['wrongTries']==1 and stored['progress']['selfSolved']
    assert stored['circleSupport']['outcome']=='needs_teacher'
    assert client.post(url+'/escalate',headers=sh,json={'note':'还没理解'}).status_code==200
    detail=client.get(f'/teacher/homework/help/{hid}',headers=th)
    assert detail.status_code==200,detail.text
    transcript=detail.json()['conversation']
    summaries=[m['text'] for m in transcript if '卡点：' in m['text']]
    assert len(summaries)==1 and len(summaries[0].splitlines())==3 and '两轮补救' in summaries[0]
    assert '借助圆面积图示辅导算出' in str(transcript)
    with legacy.SessionLocal() as db:
        assert list(db.scalars(select(legacy.Submission.answers_json)))==before
    # No change to global numeric/unit grading; the new unit task belongs only to support.
    assert parse_answer('12.56厘米')[0]==parse_answer('12.56平方厘米')[0]
    other=make_help(client,sh,'12-5等于多少？',3)
    assert client.post(f'/student/homework/help/{other}/circle-support',headers=sh,json=support).status_code==409
    old=client.get(f'/student/homework/help/{other}',headers=sh).json()
    assert old['circleSupport'] is None and not old['circleEligible']
    # Another student's credentials cannot annotate the first student's conversation.
    with legacy.SessionLocal() as db:
        cls=db.scalar(select(legacy.SchoolClass).where(legacy.SchoolClass.school_id==school))
        other_user=legacy.User(school_id=school,username='circle_other',name='测试乙',role='student',grade=6,password_hash=legacy.hash_password('Other1234'))
        db.add(other_user);db.commit()
    oh={'Authorization':'Bearer '+login_and_change(client,'circle_other','Other1234','Other5678')}
    assert client.post(url+'/circle-support',headers=oh,json=support).status_code==404
    # Real rendered entry contains the wired, fixed support controls.
    html=client.get('/v1/homework').text
    for marker in ('圆面积刚学，先回忆基础','circle-support','切得越多','不计分、不改变知识地图掌握度'):
        assert marker in html,marker
print('OK')
''')


def test_support_survives_failed_ai_without_an_extra_model_call(tmp_path):
    helpers.run_isolated(tmp_path, helpers.COMMON + r'''
with TestClient(app) as client:
    th,sh,student,school=setup(client)
    hid=make_help(client,sh,'圆的面积公式是什么意思？',6)
    base=f'/student/homework/help/{hid}'
    body={'entry':'before','gaps':['circumference'],'rounds':{'circumference':1},'outcome':'stopped'}
    assert client.post(base+'/circle-support',headers=sh,json=body).status_code==200
    replies.append(HTTPException(503,'模拟服务错误'))
    assert client.post(base+'/solve',headers=sh).status_code==503
    assert len(calls)==1
    view=client.get(base,headers=sh).json()
    assert view['state']=='confirmed' and view['circleSupport']['gaps']==['circumference']
    # Fixed support can report its result while AI is unavailable.
    assert client.post(base+'/circle-support',headers=sh,json={**body,'outcome':'teacher_requested'}).status_code==200
    assert len(calls)==1
print('OK')
''')


def test_published_map_with_deleted_questions_does_not_offer_a_dead_quiz(tmp_path):
    helpers.run_isolated(tmp_path, helpers.COMMON + r'''
from datetime import datetime
from sqlalchemy import insert
with TestClient(app) as client:
    th,sh,student,school=setup(client)
    published={'version':1,'units':[{'key':'U1','name':'圆','kind':'unit','learned':True}],
        'nodes':[{'key':'circle','unit':'U1','name':'圆的面积','detail':'','kind':'core','enabled':True,
                  'prereqs':[],'bankKeys':[],'levels':{'999991':'basic','999992':'medium','999993':'hard'}}]}
    with legacy.SessionLocal() as db:
        maps=legacy.Base.metadata.tables['knowledge_maps']
        teacher=db.scalar(select(legacy.User.id).where(legacy.User.username=='teacher1'))
        db.execute(insert(maps).values(school_id=school,grade=6,subject='数学',term='上册',textbook='测试教材',
            title='测试圆面积地图',template_key='test-circle',map_json=json.dumps(published),revision=1,
            published_json=json.dumps(published),published_revision=1,published_at=datetime.utcnow(),
            updated_by=teacher,updated_at=datetime.utcnow()));db.commit()
    hid=make_help(client,sh,'半径2厘米，π取3.14，求圆的面积。',6)
    reply=json.loads(sol(answer='12.56平方厘米',expression='3.14*2*2',kp='圆的面积'));reply['nodeKey']='circle'
    replies.append(json.dumps(reply))
    view=client.post(f'/student/homework/help/{hid}/solve',headers=sh)
    assert view.status_code==200,view.text
    assert view.json()['solution']['layer']['node']['key']=='circle'
    assert view.json()['solution']['layer']['quiz'] is False
print('OK')
''', {'KNOWLEDGE_MAP':'1'})


DOM = r'''
const assert=require('node:assert/strict');
class E{constructor(tag,attrs){this.tag=tag;this.attrs=attrs||{};this.children=[];this.style={};this.events={};this.value=this.attrs.value||'';this.hidden=!!this.attrs.hidden;this.disabled=false}
appendChild(c){this.children.push(c);if(c&&typeof c==='object')c.parent=this;return c}
remove(){if(this.parent)this.parent.children=this.parent.children.filter(x=>x!==this)}
addEventListener(k,f){this.events[k]=f}
set textContent(v){this._text=v;this.children=[]}get textContent(){return this._text||this.attrs.text||''}}
function el(tag,attrs,...cs){const e=new E(tag,attrs);cs.forEach(c=>e.appendChild(c));return e}
function DOMParser(){this.parseFromString=function(source){const e=new E('svg');e.nodeName='svg';e.source=source;return {documentElement:e}}}
function nodes(e){return [e,...e.children.filter(c=>c instanceof E).flatMap(nodes)]}
function contents(e){return nodes(e).map(n=>n.textContent).join(' ')}
function click(box,label){const b=nodes(box).find(n=>n.tag==='button'&&n.textContent===label);assert(b,'missing button '+label);const f=b.attrs.onclick||b.events.click;assert(f);f()}
function number(box,value){nodes(box).find(n=>n.tag==='input').value=value;click(box,'确定')}
async function flush(){for(let i=0;i<50;i++)await Promise.resolve()}
'''


def run_js(script):
    result = subprocess.run(['node'], input=DOM + CIRCLE_SUPPORT_JS + script, text=True, capture_output=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr


def test_two_rounds_radius_support_reaches_teacher_without_ai():
    run_js(r'''
(async()=>{
 const box=el('div');let saved,teacher;
 hwCircleSupport(box,{before:true,onFinish:async(s,t)=>{saved=s;teacher=t}});
 click(box,'公式还没懂，先检查基础');
 assert(nodes(box).find(n=>n.source).source.includes('蓝色直径d'));
 click(box,'蓝色d');click(box,'6厘米');click(box,'开始第二轮补救');click(box,'10厘米');
 assert(contents(box).includes('两轮图示补救'));
 click(box,'带上本次辅导过程，求助老师');await flush();
 assert.equal(saved.rounds.radius,2);assert.equal(saved.outcome,'needs_teacher');assert(teacher);
 assert.deepEqual(saved.gaps,['radius']);
})().catch(e=>{console.error(e);process.exit(1)});
''')


def test_square_circumference_pi_units_and_confirmation_follow_the_fixed_path():
    run_js(r'''
(async()=>{
 const box=el('div');let saved;
 hwCircleSupport(box,{before:false,onFinish:async s=>{saved=s}});
 click(box,'公式还没懂，先检查基础');click(box,'红色r');
 assert.equal((nodes(box).find(n=>n.source).source.match(/<rect /g)||[]).length,16);
 click(box,'8平方厘米');assert(contents(box).includes('4×4，不是4×2'));
 click(box,'25平方厘米');click(box,'继续');click(box,'πr²');
 assert(contents(box).includes('先离开面积推导'));click(box,'2×3.14×3');click(box,'继续');
 assert(contents(box).includes('它不是长方形本身'));click(box,'分成16份看看');
 const figure=nodes(box).find(n=>n.source);assert(figure.source.includes('长约为πr'));
 click(box,'用一个有明确π取值的例子试试');number(box,'π×4');
 assert(contents(box).includes('不算答错'));number(box,'4');number(box,'12.56厘米');
 assert(contents(box).includes('单位会单独练习'));number(box,'12.56');
 click(box,'厘米');click(box,'平方厘米');click(box,'继续');number(box,'28.26');
 click(box,'保存反馈，回到原题');await flush();
 assert.equal(saved.outcome,'practice_passed');assert(saved.unitChecked);
 assert(saved.gaps.includes('square')&&saved.gaps.includes('circumference')&&saved.gaps.includes('unit'));
 // Reopening this help shows the saved outcome instead of resetting counters to farm attempts.
 hwCircleSupport(box,{record:saved,onFinish:async s=>{saved=s}});
 assert(contents(box).includes('补救确认已经完成'));click(box,'返回原题讲解');await flush();
 assert.equal(saved.outcome,'practice_passed');assert.equal(saved.rounds.square,1);
})().catch(e=>{console.error(e);process.exit(1)});
''')


def test_existing_guide_does_not_mark_symbolic_pi_wrong_or_invent_quiz_link():
    from changying.web.homework_assistant_pages import STUDENT_HELP_JS
    script = DOM + STUDENT_HELP_JS + r'''
const window={},document={},TOKEN='test';let requests=[];
function notice(kind,text){return el('div',{class:kind,text})}
async function api(path,opts){requests.push({path,opts});return {}}
const box=el('div');const h={id:1,grade:6,questionText:'半径2厘米，π取3.14，圆的面积是多少？',state:'answered',solution:{steps:[],answer:'12.56平方厘米',finalCheck:{value:12.56,tol:.00001},layer:null}};
showSolution(box,h);number(box,'12.56π');assert.equal(requests.length,0);
assert(contents(box).includes('暂不判错'));
number(box,'12.56');assert.equal(requests.filter(r=>r.path.endsWith('/progress')).length,1);
assert(!nodes(box).some(n=>n.tag==='a'));assert(contents(box).includes('没有可用的老师审核小测入口'));
assert(nodes(box).some(n=>n.textContent==='还是不懂，补一补圆面积基础'));
'''
    result = subprocess.run(['node'], input=script, text=True, capture_output=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr


def test_optional_precheck_saves_context_before_one_solve_and_rejects_changed_question():
    from changying.web.homework_assistant_pages import STUDENT_HELP_JS
    script = DOM + STUDENT_HELP_JS + r'''
const window={},document={},TOKEN='test',ME={grade:6},CONFIG={visionEnabled:false};let root=el('div'),requests=[],record=null;
function notice(kind,text){return el('div',{class:kind,text})}
const question='半径2厘米，π取3.14，求圆的面积。';
async function api(path,opts){
 requests.push({path,opts});
 if(path==='/student/homework/help')return {id:5,grade:6,state:'confirmed',questionText:question};
 if(path.endsWith('/circle-support')){record=opts.json;return {circleSupport:record}}
 if(path.endsWith('/solve'))return {id:5,grade:6,state:'answered',questionText:question,circleSupport:record,solution:{steps:[],answer:'12.56平方厘米',finalCheck:{value:12.56,tol:.00001},layer:null}};
 return {};
}
(async()=>{
 helpCard();let text=nodes(root).find(n=>n.tag==='textarea');
 text.value='12-5等于多少';text.events.input();assert(nodes(root).find(n=>n.textContent==='圆面积刚学，先回忆基础').hidden);
 text.value=question;text.events.input();assert(!nodes(root).find(n=>n.textContent==='圆面积刚学，先回忆基础').hidden);
 click(root,'确认题目，请 AI 讲解');await flush();
 assert.equal(requests.filter(r=>r.path.endsWith('/solve')).length,1);
 assert.equal(requests.filter(r=>r.path.endsWith('/circle-support')).length,0,'ordinary help has no compulsory diagnosis');
 root=el('div');requests=[];record=null;helpCard();text=nodes(root).find(n=>n.tag==='textarea');text.value=question;text.events.input();
 click(root,'圆面积刚学，先回忆基础');await flush();assert.equal(requests.filter(r=>r.path.endsWith('/solve')).length,0);
 click(root,'基础我会，想看公式来历');click(root,'2πr');
 click(root,'跳过补救，直接请AI讲原题');await flush();
 const saveIndex=requests.findIndex(r=>r.path.endsWith('/circle-support')),solveIndex=requests.findIndex(r=>r.path.endsWith('/solve'));
 assert(saveIndex>=0&&solveIndex>saveIndex);assert.equal(requests.filter(r=>r.path.endsWith('/solve')).length,1);
 root=el('div');requests=[];record=null;helpCard();text=nodes(root).find(n=>n.tag==='textarea');text.value=question;text.events.input();
 click(root,'圆面积刚学，先回忆基础');await flush();text.value='新题目';
 click(root,'跳过补救，直接请AI讲原题');await flush();assert(contents(root).includes('题目或年级已改变'));
 assert(!requests.some(r=>r.path.endsWith('/solve')||r.path.endsWith('/circle-support')));
})().catch(e=>{console.error(e);process.exit(1)});
'''
    result = subprocess.run(['node'], input=script, text=True, capture_output=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
