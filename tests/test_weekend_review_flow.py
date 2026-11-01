"""Real routes for three attempts and atomic grading; actual UI scripts for stable review/receipts."""
import importlib.util
import sys
import subprocess
from pathlib import Path

spec=importlib.util.spec_from_file_location('review_helpers',Path(__file__).with_name('test_weekend_backup.py'))
b=importlib.util.module_from_spec(spec);sys.modules[spec.name]=b;spec.loader.exec_module(b)


def test_three_attempts_and_atomic_batch_review_without_duplicate_answers(tmp_path):
    b.helpers.run_isolated(tmp_path,b.COMMON+r'''
from sqlalchemy import insert
import base64
PNG=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+j5WQAAAAASUVORK5CYII=')
with TestClient(app) as client:
    th,sh,student,school,lid,qid,wid,sid,base,body=prepare(client)
    with legacy.SessionLocal() as db:
        rt=legacy.Base.metadata.tables['weekend_class_rosters'];roster=db.execute(select(rt).where(rt.c.session_id==sid)).first()
        other=legacy.User(school_id=school,username='review_other',password_hash=legacy.hash_password('x'),name='乙同学',role='student',grade=3)
        db.add(other);db.flush();oid=other.id;db.add(legacy.ClassStudent(class_id=roster.class_id,student_id=oid))
        members=json.loads(roster.members_json)+[{'id':oid,'name':'乙同学'}]
        db.execute(update(rt).where(rt.c.session_id==sid).values(members_json=json.dumps(members)));db.commit()
    oh={'Authorization':'Bearer '+login_and_change(client,'review_other','x','Other1234')}
    client.post(base+'/start',headers=th);client.post(base+'/goto',headers=th,json={'stage':4})
    url='/student/weekend/sessions/'+str(sid)+'/written/'+str(wid)
    first=client.post(url,headers=sh,data={'text':'甲第一次'}).json()
    assert first['attempts']==1 and first['submission']['questionId']==wid
    assert client.post(url,headers=sh,data={'text':'甲第一次'}).json()['attempts']==1
    second=client.post(url,headers=oh,data={'text':'乙第一次'},files={'photo':('answer.png',PNG,'image/png')}).json()
    aa,bb=first['submission']['id'],second['submission']['id']
    batch=base+'/written/review-batch'
    payload={'items':[{'id':aa,'revision':1,'result':'correct','comment':'甲评语'},{'id':bb,'revision':1,'result':'partial','comment':'乙评语'}]}
    assert client.post(batch,headers=sh,json=payload).status_code==403
    assert client.post(batch,headers=th,json=payload).status_code==200
    retry=client.post(url,headers=sh,data={'text':'甲第一次','revision':0}).json()
    assert retry['attempts']==1 and retry['submission']['result']=='pending' and retry['submission']['comment']==''
    # A stale row aborts the whole batch, including the earlier row update.
    stale={'items':[{'id':aa,'revision':2,'result':'revise'},{'id':bb,'revision':1,'result':'correct'}]}
    assert client.post(batch,headers=th,json=stale).status_code==409
    rows=client.get(base+'/written',headers=th).json()['items'];a=next(x for x in rows if x['id']==aa)
    assert a['result']=='correct' and a['revision']==2
    assert client.get('/student/weekend/sessions/'+str(sid)+'/written',headers=sh).json()['questions'][0]['submission']['result']=='pending'
    # Teacher grading increments revision but never student attempts.
    assert client.post(url,headers=sh,data={'text':'甲第二次','revision':1}).status_code==409
    r=client.post(url,headers=sh,data={'text':'甲第二次','revision':2});assert r.status_code==200,r.text
    assert r.json()['attempts']==2
    assert client.post(base+'/written/'+str(aa)+'/review',headers=th,json={'revision':3,'result':'partial'}).status_code==200
    r=client.post(url,headers=sh,data={'text':'甲第三次','revision':4});assert r.status_code==200,r.text
    assert r.json()['attempts']==3
    assert client.post(url,headers=sh,data={'text':'甲第三次','revision':4}).json()['attempts']==3
    assert client.post(url,headers=sh,data={'text':'甲第四次','revision':5}).status_code==409
    r=client.post(url,headers=oh,data={'text':'乙修改文字','revision':2});assert r.status_code==200,r.text
    assert r.json()['submission']['hasPhoto']
    assert client.get('/weekend/written/submissions/'+str(bb)+'/photo',headers=oh).content==PNG
    removed=client.post(url,headers=oh,data={'text':'乙改用文字','revision':3,'removePhoto':'true'})
    assert removed.status_code==200 and not removed.json()['submission']['hasPhoto']
    assert client.get('/weekend/written/submissions/'+str(bb)+'/photo',headers=oh).status_code==404
    # Choice answers also have three attempts, one final row, no feedback leak.
    choice='/student/weekend/answer'
    for selected,attempt in [(0,0),(1,1),(0,2)]:
        r=client.post(choice,headers=sh,json={'sessionId':sid,'questionId':qid,'selected':selected,'attempt':attempt})
        assert r.status_code==200,r.text
        assert r.json()['attempts']==attempt+1 and 'correct' not in r.json()
    assert client.post(choice,headers=sh,json={'sessionId':sid,'questionId':qid,'selected':1,'attempt':3}).status_code==409
    with legacy.SessionLocal() as db:
        answers=register_practice_tables(legacy)['answers'];written=register_written_tables(legacy)['submissions']
        assert db.scalar(select(func.count()).select_from(answers).where(answers.c.session_id==sid))==1
        assert db.scalar(select(func.count()).select_from(written).where(written.c.session_id==sid))==2
        assert db.scalar(select(func.count()).select_from(legacy.AuditLog).where(legacy.AuditLog.user_id==student,legacy.AuditLog.action==f'weekend.submit.written.{sid}.{wid}'))==3
    client.post(base+'/publish-answers',headers=th,json={'question':1})
    assert client.post(choice,headers=sh,json={'sessionId':sid,'questionId':qid,'selected':0,'attempt':3}).status_code==409
    client.post(base+'/publish-answers',headers=th,json={'question':2})
    assert client.post(url,headers=oh,data={'text':'公布后修改','revision':3}).status_code==409
    final={'items':[{'id':aa,'revision':5,'result':'correct'},{'id':bb,'revision':4,'result':'correct'}]}
    assert client.post(batch,headers=th,json=final).status_code==200
    client.post(base+'/finish',headers=th)
    assert client.post(base+'/settle',headers=th).status_code==200
    assert client.post(base+'/written/'+str(aa)+'/review',headers=th,json={'revision':6,'result':'revise'}).status_code==409
    print('OK')
''')


DOM=r'''
const assert=require('assert');
class E{constructor(tag,attrs){this.tag=tag;this.attrs=attrs||{};this.children=[];this.value=String(this.attrs.value||'');this.disabled=false;this.handlers={}}
 appendChild(e){this.children.push(e);if(this.tag==='select'&&!this.value)this.value=String(e.attrs.value||'');return e}
 addEventListener(k,f){this.handlers[k]=f}set textContent(v){this._text=v;this.children=[]}get textContent(){return this._text||this.attrs.text||''}}
function el(tag,attrs,...children){const e=new E(tag,attrs);children.forEach(c=>e.appendChild(c));return e}
function all(e,tag){return e.children.flatMap(c=>c instanceof E?[(c.tag===tag?c:null),...all(c,tag)].filter(Boolean):[])}
async function flush(){for(let i=0;i<40;i++)await Promise.resolve()}
var SID=1,TOKEN='t',document={hidden:false},window={addEventListener(){}},location={search:'',href:'https://test/v1/weekend-practice'},history={replaceState(){}},timers=[],setInterval=f=>timers.push(f),confirm=()=>true,alert=m=>{throw Error(m)};
'''


def run_js(script):
    r=subprocess.run(['node','-e',script],text=True,capture_output=True,timeout=20)
    assert r.returncode==0,r.stdout+r.stderr
    assert 'OK' in r.stdout


def test_teacher_reviews_preserve_rows_and_other_pupils_comments():
    from changying.web.weekend_written_pages import WRITTEN_JS
    run_js(DOM+r'''
var gets=0,posts=[];
var data={status:'running',total:2,submitted:2,questions:[{id:1,stem:'原题',reference:'参考答案'}],items:[{id:11,questionId:1,name:'甲',text:'甲答案',revision:1,result:'pending',comment:''},{id:12,questionId:1,name:'乙',text:'乙答案',revision:1,result:'pending',comment:''}]};
function api(path,opts){if(path.includes('/precheck'))return Promise.resolve(path.includes('?')?{precheck:{status:'failed',message:'模拟识别不可用'}}:{queued:true});if(!opts){gets++;return Promise.resolve(JSON.parse(JSON.stringify(data)))}posts.push(opts.json.items);return Promise.resolve({reviewed:true,items:opts.json.items.map(a=>({...a,revision:a.revision+1}))})}
''' + WRITTEN_JS+r'''
(async()=>{const box=new E('div');writtenTeacher(box);await flush();
 const section=all(box,'section')[0],comments=all(section,'textarea');comments[1].value='乙尚未保存的评语';comments[1].oninput();
 all(section,'button').find(x=>x.attrs.text==='正确').attrs.onclick();await flush();
 assert.equal(gets,1);assert.equal(all(box,'section')[0],section);assert.equal(comments[1].value,'乙尚未保存的评语');
 assert(all(section,'b').some(x=>x.textContent==='甲 · 正确'));
 const picks=all(section,'select');picks[1].value='partial';picks[1].onchange();
 all(box,'button').find(x=>x.attrs.text==='保存全部批改').attrs.onclick();await flush();
 assert.equal(gets,1);assert.equal(posts[1].length,1);assert.equal(posts[1][0].id,12);assert.equal(posts[1][0].comment,'乙尚未保存的评语');
 assert(all(section,'h3')[0].textContent.includes('2/2'));assert(all(section,'b').some(x=>x.textContent==='乙 · 部分正确'));console.log('OK');
})().catch(e=>{console.error(e);process.exitCode=1});
''')


def test_student_keeps_receipt_and_draft_when_grading_changes_revision():
    from changying.web.weekend_written_pages import WRITTEN_JS
    run_js(DOM+r'''
var posts=[],staleRead=false,rejectOnce=false,stored=null;
function api(path,opts){
 if(path==='/student/weekend/current')return Promise.resolve({active:true,practice:true,sessionId:1});
 if(path.endsWith('/written'))return Promise.resolve({canSubmit:true,questions:[{id:1,stem:'原题',submission:staleRead?null:stored}]});
 posts.push({text:opts.body.get('text'),revision:Number(opts.body.get('revision'))});
 if(rejectOnce){rejectOnce=false;stored.revision=2;var e=Error('答案已更新');e.status=409;return Promise.reject(e)}
 stored={id:11,questionId:1,text:opts.body.get('text'),revision:posts.length===1?1:3,result:'pending',comment:'',attempts:posts.length===1?1:2};
 return Promise.resolve({submitted:true,attempts:stored.attempts,submission:{...stored}});
}
''' + WRITTEN_JS+r'''
(async()=>{const box=new E('div');writtenStudent(box);await flush();
 let text=all(box,'textarea')[0];text.value='首次答案';text.oninput();staleRead=true;
 all(box,'button').find(x=>x.attrs.text==='提交答案').attrs.onclick();await flush();
 assert(all(box,'div').some(x=>x.textContent.includes('已提交')));assert.equal(all(box,'textarea')[0].value,'首次答案');
 staleRead=false;rejectOnce=true;text=all(box,'textarea')[0];text.value='编辑中的第二稿';text.oninput();
 all(box,'button').find(x=>x.attrs.text==='重新提交答案').attrs.onclick();await flush();
 assert.equal(all(box,'textarea')[0].value,'编辑中的第二稿');
 all(box,'button').find(x=>x.attrs.text==='重新提交答案').attrs.onclick();await flush();
 assert.equal(posts[2].revision,2);assert.equal(stored.text,'编辑中的第二稿');console.log('OK');
})().catch(e=>{console.error(e);process.exitCode=1});
''')


def test_choice_page_allows_changes_until_third_submission():
    from changying.web.weekend_pages import PRACTICE_JS
    run_js(DOM+r'''
E.prototype.insertBefore=function(n,b){this.children.unshift(n)};
var root=new E('div'),posts=[],q={id:7,stem:'选择原题',options:['甲','乙'],hintUsed:0,levelNames:[],canSubmit:true,answered:false,attempts:0};
function writtenStudent(){}function writtenPhoto(){}function boot_student(f){f()}
function api(path,opts){
 if(path==='/student/weekend/current')return Promise.resolve({active:true,practice:true,sessionId:1,stage:4,title:'本课堂',questions:[{...q}]});
 if(path.startsWith('/student/weekend/explain'))return Promise.resolve({sessionId:1,items:[]});
 if(path==='/student/knowledge-map')return Promise.reject(Error('知识地图未开启'));
 if(path==='/student/weekend/followup')return Promise.resolve({active:false});
 posts.push(opts.json);q.selected=opts.json.selected;q.answered=true;q.attempts++;return Promise.resolve({submitted:true,attempts:q.attempts});
}
''' + PRACTICE_JS+r'''
(async()=>{await flush();for(const selected of [1,0,1]){
 const option=all(root,'button').find(x=>x.attrs.text===(selected?'B. 乙':'A. 甲'));assert(!option.disabled);option.handlers.click();
 const send=all(root,'button').find(x=>x.attrs.class==='primary');assert(send);send.attrs.onclick();await flush();
 }assert.deepEqual(posts.map(x=>x.attempt),[0,1,2]);assert(!all(root,'button').some(x=>x.attrs.class==='primary'));
 assert(all(root,'button').filter(x=>/^A\.|^B\./.test(x.attrs.text||'')).every(x=>x.disabled));console.log('OK');
})().catch(e=>{console.error(e);process.exitCode=1});
''')
