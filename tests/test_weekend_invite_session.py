"""Invitation/follow-up isolation and stale UI responses through real application routes."""
import importlib.util
import sys
import subprocess
from pathlib import Path

spec=importlib.util.spec_from_file_location('invite_backup_helpers',Path(__file__).with_name('test_weekend_backup.py'))
backup=importlib.util.module_from_spec(spec);sys.modules[spec.name]=backup;spec.loader.exec_module(backup)


def test_new_class_hides_old_invitation_and_rejects_old_followup(tmp_path):
    backup.helpers.run_isolated(tmp_path,backup.COMMON+r'''
from sqlalchemy import insert
with TestClient(app) as client:
    th,sh,student,school,lid,qid,wid,sid,base,body=prepare(client)
    client.post(base+'/start',headers=th);client.post(base+'/goto',headers=th,json={'stage':4})
    r=client.post('/student/weekend/sessions/'+str(sid)+'/written/'+str(wid),headers=sh,data={'text':'旧语文答案'})
    assert r.status_code==200,r.text
    assert client.post(base+'/explain',headers=th,json={'tutorId':student,'questionId':wid,'questionType':'written'}).status_code==200
    assert client.get('/student/weekend/explain',headers=sh).json()['items']
    with legacy.SessionLocal() as db:
        old=db.get(legacy.TeachingLesson,lid)
        old.subject='语文'
        lesson=legacy.TeachingLesson(school_id=school,program_id=old.program_id,lesson_no=910,subject='数学',title='当前数学课',core_target='旋转')
        db.add(lesson);db.flush();new_lid=lesson.id
        rt=legacy.Base.metadata.tables['weekend_class_rosters']
        cls=db.execute(select(rt.c.class_id).where(rt.c.session_id==sid)).scalar_one()
        peer=register_scoring_tables(legacy)['peer']
        pid=db.execute(insert(peer).values(school_id=school,session_id=sid,tutor_id=student,tutee_id=student,question_id=qid,
            followup_json=json.dumps({'stem':'旧巩固题','options':['甲','乙'],'correctIndex':0}),created_at=datetime.utcnow())).inserted_primary_key[0]
        db.commit()
    new=client.post('/teacher/weekend/sessions',headers=th,json={'lessonId':new_lid,'classId':cls}).json()['id']
    nb='/teacher/weekend/sessions/'+str(new)
    nw=client.post(nb+'/written/questions',headers=th,json={'stem':'当前数学问题','reference':'数学参考'}).json()['id']
    client.post(nb+'/start',headers=th)
    assert client.get('/student/weekend/current',headers=sh).json()['sessionId']==new
    assert client.get('/student/weekend/explain',headers=sh).json()['items']==[]
    assert client.get('/student/weekend/followup',headers=sh).json()['active'] is False
    assert client.post('/student/weekend/followup',headers=sh,json={'peerHelpId':pid,'selected':0}).status_code==404
    client.post(nb+'/goto',headers=th,json={'stage':4})
    client.post('/student/weekend/sessions/'+str(new)+'/written/'+str(nw),headers=sh,data={'text':'数学本人答案'})
    assert client.post(nb+'/explain',headers=th,json={'tutorId':student,'questionId':nw,'questionType':'written'}).status_code==200
    data=client.get('/student/weekend/explain?sessionId='+str(new),headers=sh).json()
    assert data['sessionId']==new and len(data['items'])==1
    assert data['items'][0]['stem']=='当前数学问题' and data['items'][0]['answerText']=='数学本人答案'
    assert 'reference' not in data['items'][0]
    assert client.get('/student/weekend/explain?sessionId='+str(sid),headers=sh).json()['items']==[]
    client.post(nb+'/goto',headers=th,json={'stage':2})
    assert client.get('/student/weekend/explain',headers=sh).json()['items']==[]
    client.post(nb+'/finish',headers=th);client.post(base+'/finish',headers=th)
    assert client.get('/student/weekend/explain',headers=sh).json()['items']==[]
    with legacy.SessionLocal() as db:
        assert db.scalar(select(register_scoring_tables(legacy)['peer'].c.followup_correct).where(peer.c.id==pid)) is None
    print('OK')
''')


def test_invitation_layout_and_late_old_response_do_not_replace_current_class():
    from changying.web.weekend_pages import PRACTICE_JS
    node=r'''
const assert=require('assert');
function el(tag,attrs,...children){return {tag,attrs:attrs||{},children,appendChild(n){this.children.push(n);return n},insertBefore(n,b){let i=this.children.indexOf(b);this.children.splice(i<0?0:i,0,n)},set textContent(t){this.text=t;this.children=[]},get textContent(){return this.text||this.attrs.text||''},get firstChild(){return this.children[0]}}}
function all(n){return [n,...n.children.flatMap(all)]}
var root=el('div'),document={hidden:false},interval,session=1,requests=[];
function setInterval(f){interval=f;return 1}function boot_student(f){f()}function writtenStudent(){}function writtenPhoto(){}
function api(path){
 if(path==='/student/weekend/current')return Promise.resolve({active:true,sessionId:session,title:'当前课'+session,stage:4,practice:true,questions:[]});
 if(path.startsWith('/student/weekend/explain'))return new Promise(resolve=>requests.push({path,resolve}));
 if(path==='/student/knowledge-map')return Promise.reject(Error('知识地图未开启'));
 if(path==='/student/weekend/followup')return Promise.resolve({active:false});
 throw Error(path);
}
async function flush(){for(let i=0;i<30;i++)await Promise.resolve()}
''' + PRACTICE_JS + r'''
(async()=>{
 await flush();assert.equal(requests[0].path,'/student/weekend/explain?sessionId=1');
 session=2;interval();await flush();assert.equal(requests[1].path,'/student/weekend/explain?sessionId=2');
 requests[1].resolve({sessionId:2,items:[{questionType:'written',stem:'文章完整内容\n\n当前数学问题',answerText:'本人答案',reference:'已公布评分细则'}]});await flush();
 requests[0].resolve({sessionId:1,items:[{questionType:'written',stem:'不该显示的旧语文问题'}]});await flush();
 const nodes=all(root);assert(!nodes.some(n=>n.attrs.text==='不该显示的旧语文问题'));
 assert(nodes.some(n=>n.tag==='p'&&n.attrs.text==='当前数学问题'));
 const details=nodes.filter(n=>n.tag==='details');assert.equal(details.length,2);assert(details.every(n=>!n.attrs.open));
 assert(nodes.some(n=>n.attrs.text==='文章完整内容'));assert(nodes.some(n=>n.attrs.text==='你提交的答案：本人答案'));
 assert(!nodes.some(n=>n.tag==='b'&&n.attrs.text&&n.attrs.text.includes('文章')));
 session=3;interval();await flush();assert(!all(root).some(n=>n.attrs.text==='当前数学问题'));
 console.log('OK');
})().catch(e=>{console.error(e);process.exitCode=1});
'''
    r=subprocess.run(['node','-e',node],text=True,capture_output=True,timeout=20)
    assert r.returncode==0,r.stdout+r.stderr
    assert 'OK' in r.stdout
