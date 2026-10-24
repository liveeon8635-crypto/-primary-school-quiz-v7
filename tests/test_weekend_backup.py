"""Paper pack and transcription exercised through the production application entry."""
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('backup_helpers', ROOT/'tests/test_homework_solve.py')
helpers = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = helpers
spec.loader.exec_module(helpers)

COMMON = helpers.COMMON + r'''
import io, zipfile, hashlib
from pathlib import Path
from datetime import datetime, timezone, timedelta
from sqlalchemy import func, update
from changying.web.weekend_views import register_weekend_tables
from changying.web.weekend_practice import register_practice_tables
from changying.web.weekend_written import register_written_tables
from changying.web.weekend_scoring_views import register_scoring_tables

def prepare(client):
    th, sh, student, school = setup(client)
    with legacy.SessionLocal() as db:
        teacher = db.scalar(select(legacy.User).where(legacy.User.username=='teacher1'))
        program = db.scalar(select(legacy.TeachingProgram).where(legacy.TeachingProgram.school_id==school))
        lesson = legacy.TeachingLesson(school_id=school,program_id=program.id,subject='数学',lesson_no=909,
            title='图形的运动',core_target='旋转',duration_min=90,teacher_plan='环节1：观察\n环节2：旋转\n教师原稿尾部完整保留',
            reading_plan='长阅读材料开头\n'+'完整材料'*450+'\n材料最后一句',examples_json='["例题1：转动方法"]')
        db.add(lesson);db.flush();lid=lesson.id
        cls = db.scalar(select(legacy.SchoolClass).where(legacy.SchoolClass.school_id==school));cls.teacher_id=teacher.id
        link = db.scalar(select(legacy.ClassStudent).where(legacy.ClassStudent.student_id==student))
        if link:link.class_id=cls.id
        else:db.add(legacy.ClassStudent(class_id=cls.id,student_id=student))
        q = legacy.TeachingQuestion(school_id=school,program_id=program.id,lesson_id=lid,subject='数学',stage='lesson',
            level='B',knowledge='旋转中心',stem='选择正确的旋转方向<script>alert(1)</script>',options_json='["顺时针","逆时针"]',
            correct_index=0,explanation='教师独立解析SECRET_CHOICE',active=True)
        db.add(q);db.flush();qid=q.id;class_id=cls.id
        raw=b'%PDF-original-stored-diagram'
        db.add(legacy.TeachingResource(school_id=school,uploader_id=teacher.id,lesson_id=lid,title='原图',file_name='original.pdf',
            file_ext='.pdf',mime_type='application/pdf',size_bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),file_data=raw))
        db.commit()
    sid = client.post('/teacher/weekend/sessions',headers=th,json={'lessonId':lid,'classId':class_id}).json()['id']
    base = '/teacher/weekend/sessions/'+str(sid)
    r=client.post(base+'/written/questions',headers=th,json={'stem':'完整阅读开头\n'+'材料'*350+'\n阅读最后一句\n解释旋转中心', 'reference':'教师专用SECRET_WRITTEN'})
    assert r.status_code==200,r.text
    wid=r.json()['id']
    data=client.get(base+'/backup',headers=th).json()
    body=dict(version=data['version'],studentId=student,kind='choice',questionId=qid,selected=1,hintLevel=1,
        stage=4,note='断电，纸质答卷A1',occurredAt=datetime.now(timezone.utc).isoformat())
    return th,sh,student,school,lid,qid,wid,sid,base,body
'''


def test_backup_download_real_route_two_printable_word_files(tmp_path):
    helpers.run_isolated(tmp_path, COMMON+r'''
from xml.etree import ElementTree as ET

def document_text(data):
    package=zipfile.ZipFile(io.BytesIO(data))
    assert '[Content_Types].xml' in package.namelist()
    for name in package.namelist():
        if name.endswith('.xml') or name.endswith('.rels'):ET.fromstring(package.read(name))
    rels=package.read('word/_rels/document.xml.rels').decode()
    assert 'TargetMode="External"' not in rels and 'vbaProject' not in str(package.namelist())
    return '\n'.join(ET.fromstring(package.read('word/document.xml')).itertext())

with TestClient(app) as client:
    th,sh,student,school,lid,qid,wid,sid,base,body=prepare(client)
    for suffix in ('/backup.zip','/backup.docx?audience=teacher','/backup.docx?audience=student'):
        assert client.get(base+suffix).status_code==401
        assert client.get(base+suffix,headers=sh).status_code==403
    assert client.get(base+'/backup.docx?audience=other',headers=th).status_code==400
    response=client.get(base+'/backup.zip',headers=th)
    assert response.status_code==200,response.text
    assert 'no-store' in response.headers['cache-control']
    pack=zipfile.ZipFile(io.BytesIO(response.content))
    assert set(pack.namelist())=={'教师版.docx','学生版.docx'}
    teacher=document_text(pack.read('教师版.docx'));student_doc=document_text(pack.read('学生版.docx'))
    for text in (teacher,student_doc):
        assert '选择正确的旋转方向<script>alert(1)</script>' in text and '阅读最后一句' in text
        assert '第1题' in text and '第2题' in text and '满分7分' in text
        assert '教师原稿尾部完整保留' not in text and '长阅读材料开头' not in text
        assert '备课核对' not in text and '故障接续记录卡' not in text and '课后练习安排' not in text
    assert 'SECRET_WRITTEN' in teacher and 'SECRET_CHOICE' in teacher and '考点提醒：旋转中心' in teacher
    assert 'SECRET_' not in student_doc and '考点提醒' not in student_doc and '提示级别' not in student_doc
    for role in ('teacher','student'):
        r=client.get(base+'/backup.docx?audience='+role,headers=th)
        assert r.status_code==200,r.text
        assert r.headers['content-type']=='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        assert role+'.docx' in r.headers['content-disposition']
        assert r.headers['x-changying-paper-version']==body['version']
        document_text(r.content)
        # Fixture copies for offline renderer QA only; not production teaching files.
        qa=Path('/tmp/weekend-word-qa');qa.mkdir(exist_ok=True);(qa/(role+'.docx')).write_bytes(r.content)
    footer=zipfile.ZipFile(io.BytesIO(pack.read('教师版.docx'))).read('word/footer1.xml').decode()
    assert body['version'] in footer
    page=client.get('/v1/weekend').text
    assert '下载教师版 Word' in page and '下载学生版 Word' in page and '/backup.docx?audience=' in page
    assert 'backupTeacher(backupBox)' in page and 'backup-record' in page
    assert client.post(base+'/finish',headers=th).status_code==200
    assert client.get(base+'/backup',headers=th).json()['version']==body['version']
    print('OK')
''')


def test_word_exports_all_questions_marks_and_shared_reading_once(tmp_path):
    helpers.run_isolated(tmp_path, COMMON+r'''
from xml.etree import ElementTree as ET
with TestClient(app) as client:
    th,sh,student,school,lid,qid,wid,sid,base,body=prepare(client)
    reading='篇目一 旋转中的故事\n'+'这是完整文章。'*80
    with legacy.SessionLocal() as db:
        db.get(legacy.TeachingQuestion,qid).stem='原题（4分）'
        wt=register_written_tables(legacy)['questions']
        db.execute(update(wt).where(wt.c.id==wid).values(stem=reading+'\n\n1. 说明原因（6分）'))
        program=db.get(legacy.TeachingQuestion,qid).program_id
        for n in range(31):
            db.add(legacy.TeachingQuestion(school_id=school,program_id=program,lesson_id=lid,subject='数学',stage='lesson',
                level='B',knowledge='旋转',stem='额外原题'+str(n),options_json='["甲","乙"]',correct_index=0,active=True))
        db.commit()
    r=client.post(base+'/written/questions',headers=th,json={'stem':reading+'\n\n2. 写出方法（2.5分）','reference':'第二题教师答案'})
    assert r.status_code==200,r.text
    for role in ('teacher','student'):
        response=client.get(base+'/backup.docx?audience='+role,headers=th)
        assert response.status_code==200,response.text
        package=zipfile.ZipFile(io.BytesIO(response.content))
        text=''.join(ET.fromstring(package.read('word/document.xml')).itertext())
        assert '额外原题30' in text and '共34题' in text and '满分74.5分' in text
        assert '第1题　4分' in text and '第33题　6分' in text and '第34题　2.5分' in text
        assert text.count('这是完整文章。')==80 and '说明原因' in text and '写出方法' in text
        if role=='student':assert '第二题教师答案' not in text and 'SECRET_' not in text
    print('OK')
''')


def test_transcription_original_identity_wrong_book_evidence_and_points_once(tmp_path):
    helpers.run_isolated(tmp_path, COMMON+r'''
with TestClient(app) as client:
    th,sh,student,school,lid,qid,wid,sid,base,body=prepare(client)
    assert client.post(base+'/backup-record',headers=sh,json=body).status_code==403
    assert client.post(base+'/backup-record',headers=th,json=body).status_code==409
    client.post(base+'/finish',headers=th)
    assert client.post(base+'/backup-record',headers=th,json={**body,'studentId':999999}).status_code==404
    assert client.post(base+'/backup-record',headers=th,json={**body,'version':'0'*16}).status_code==409
    assert client.post(base+'/backup-record',headers=th,json={**body,'kind':'other'}).status_code==404
    assert client.post(base+'/backup-record',headers=th,json={**body,'occurredAt':(datetime.now(timezone.utc)+timedelta(days=1)).isoformat()}).status_code==400
    # A paper-only class is ended through the original finish action before transcription.
    r=client.post(base+'/backup-record',headers=th,json=body);assert r.status_code==200,r.text
    assert r.json()['recorded'] is True
    r=client.post(base+'/backup-record',headers=th,json=body);assert r.status_code==200 and r.json()['alreadyRecorded']
    assert client.post(base+'/backup-record',headers=th,json={**body,'selected':0}).status_code==409
    written={**body,'kind':'written','questionId':wid,'selected':None,'text':'以固定点为中心转动','result':'correct'}
    r=client.post(base+'/backup-record',headers=th,json=written);assert r.status_code==200,r.text
    assert client.post(base+'/backup-record',headers=th,json=written).json()['alreadyRecorded']
    with legacy.SessionLocal() as db:
        answers=register_practice_tables(legacy)['answers'];wt=register_written_tables(legacy)['submissions']
        assert db.scalar(select(func.count()).select_from(answers).where(answers.c.session_id==sid))==1
        assert db.scalar(select(func.count()).select_from(wt).where(wt.c.session_id==sid))==1
        ev=db.scalars(select(legacy.LearningEvidenceEvent).where(legacy.LearningEvidenceEvent.student_id==student,legacy.LearningEvidenceEvent.note.like('周末课纸质%'))).all()
        assert len(ev)==2 and all(e.school_id==school for e in ev)
        assert all(e.knowledge_key==('旋转中心' if json.loads(e.context)['kind']=='choice' else '旋转') for e in ev)
        assert all(json.loads(e.context)['sessionId']==sid for e in ev)
        wrong=db.scalars(select(legacy.WrongQuestionRecord).where(legacy.WrongQuestionRecord.student_id==student,legacy.WrongQuestionRecord.source=='weekend_backup')).all()
        assert len(wrong)==1 and wrong[0].knowledge=='旋转中心'
        assert db.scalar(select(func.count()).select_from(legacy.PointLedger).where(legacy.PointLedger.related_id==sid,legacy.PointLedger.category.like('weekend_%')))==0
    client.post(base+'/finish',headers=th)
    archive=client.get(base+'/archive',headers=th).json();a=next(s for s in archive['students'] if s['studentId']==student)
    assert a['total']==2 and a['correct']==1
    assert client.get(base+'/settle-preview',headers=th).json()['items']
    settled=client.post(base+'/settle',headers=th);assert settled.status_code==200,settled.text
    assert client.post(base+'/settle',headers=th).status_code==409
    assert client.post(base+'/backup-record',headers=th,json=body).json()['alreadyRecorded']
    with legacy.SessionLocal() as db:
        awards=register_scoring_tables(legacy)['awards']
        assert db.scalar(select(func.count()).select_from(awards).where(awards.c.session_id==sid))==4
    # Actual student wrong-book API sees the original student's paper mistake.
    book=client.get('/student/wrong-questions',headers=sh);assert book.status_code==200,book.text
    assert any(x.get('source')=='weekend_backup' for x in book.json()['items'])
    print('OK')
''')


def test_paper_never_overwrites_online_answers_stale_packs_or_other_teachers(tmp_path):
    helpers.run_isolated(tmp_path, COMMON+r'''
with TestClient(app) as client:
    th,sh,student,school,lid,qid,wid,sid,base,body=prepare(client)
    client.post(base+'/start',headers=th);client.post(base+'/goto',headers=th,json={'stage':4})
    online=client.post('/student/weekend/answer',headers=sh,json={'sessionId':sid,'questionId':qid,'selected':0})
    assert online.status_code==200,online.text
    assert client.post(base+'/backup-record',headers=th,json=body).status_code==409
    submission=client.post('/student/weekend/sessions/'+str(sid)+'/written/'+str(wid),headers=sh,data={'text':'线上草稿'})
    assert submission.status_code==200,submission.text
    assert client.post(base+'/settle',headers=th).status_code==409
    with legacy.SessionLocal() as db:
        lesson=db.get(legacy.TeachingLesson,lid);lesson.teacher_plan+='已修订';db.commit()
    assert client.post(base+'/backup-record',headers=th,json={**body,'kind':'written','questionId':wid,'text':'旧纸卷'}).status_code==409
    with legacy.SessionLocal() as db:
        table=register_weekend_tables(legacy)['sessions'];db.execute(update(table).where(table.c.id==sid).values(teacher_id=999999));db.commit()
    assert client.get(base+'/backup.zip',headers=th).status_code==404
    assert client.get(base+'/backup.docx?audience=teacher',headers=th).status_code==404
    assert client.post(base+'/backup-record',headers=th,json=body).status_code==404
    print('OK')
''')


def test_paper_photo_review_and_settlement_lock(tmp_path):
    helpers.run_isolated(tmp_path, COMMON+r'''
import base64
PNG=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+j5WQAAAAASUVORK5CYII=')
with TestClient(app) as client:
    th,sh,student,school,lid,qid,wid,sid,base,body=prepare(client)
    client.post(base+'/finish',headers=th)
    paper={**body,'kind':'written','questionId':wid,'selected':None,'text':'','result':'partial','photoBase64':base64.b64encode(PNG).decode()}
    assert client.post(base+'/backup-record',headers=th,json={**paper,'photoBase64':'not base64'}).status_code==400
    assert client.post(base+'/backup-record',headers=th,json={**paper,'photoBase64':base64.b64encode(b'invalid').decode()}).status_code==400
    assert client.post(base+'/backup-record',headers=th,json={**paper,'occurredAt':'2020-01-01T00:00:00'}).status_code==400
    r=client.post(base+'/backup-record',headers=th,json=paper);assert r.status_code==200,r.text
    a=client.get(base+'/written',headers=th).json()['items'][0]
    assert a['hasPhoto'] and a['result']=='partial'
    photo='/weekend/written/submissions/'+str(a['id'])+'/photo'
    assert client.get(photo).status_code==401
    assert client.get(photo,headers=sh).content==PNG
    assert client.get(photo,headers=th).content==PNG
    archive=client.get(base+'/archive',headers=th).json()
    # A partial written answer is listed as such, not under the lesson goal (written questions have no knowledge point).
    assert next(x for x in archive['students'] if x['studentId']==student)['wrongKnowledge']==['文字／照片题（未标注考点）']
    assert client.post(base+'/settle',headers=th).status_code==200
    # The missing choice answer cannot change already-settled award inputs.
    assert client.post(base+'/backup-record',headers=th,json=body).status_code==409
    assert client.post(base+'/backup-record',headers=th,json=paper).json()['alreadyRecorded']
    with legacy.SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(legacy.LearningEvidenceEvent).where(legacy.LearningEvidenceEvent.student_id==student,legacy.LearningEvidenceEvent.note.like('周末课纸质%')))==1
        ev=db.scalar(select(legacy.LearningEvidenceEvent).where(legacy.LearningEvidenceEvent.student_id==student,legacy.LearningEvidenceEvent.note.like('周末课纸质%')))
        assert ev.success is None
    print('OK')
''')


def test_backup_form_keeps_question_identity_and_clears_other_pupil_drafts():
    from changying.web.weekend_backup_pages import BACKUP_JS
    import subprocess
    harness = r'''
const assert=require('assert');
var links=[],downloads=[];
class E{click(){if(this.tag==='a')links.push(this.attrs)}remove(){}constructor(tag,attrs){this.tag=tag;this.attrs=attrs||{};this.children=[];this.handlers={};this.value=String(this.attrs.value||'');this.files=[];this.disabled=false}
 appendChild(e){this.children.push(e);if(this.tag==='select'&&this.value==='')this.value=String(e.attrs.value);return e}
 addEventListener(k,f){this.handlers[k]=f}set textContent(v){this._text=v;this.children=[];if(this.tag==='select')this.value=''}get textContent(){return this._text||this.attrs.text||''}}
function el(tag,attrs,...children){const e=new E(tag,attrs);children.forEach(c=>e.appendChild(c));return e}
function all(e,tag){return e.children.flatMap(c=>c instanceof E?[(c.tag===tag?c:null),...all(c,tag)].filter(Boolean):[])}
var SID=1,TOKEN='t',yes=true,confirm=()=>yes;
var document={body:new E('body')},URL={createObjectURL:()=> 'blob:local',revokeObjectURL:()=>{}},setTimeout=()=>0;
function fetch(url,options){downloads.push({url,options});return Promise.resolve({ok:true,headers:{get:()=>data.version},blob:()=>Promise.resolve({})})}
var data={version:'aaaaaaaaaaaaaaaa',status:'finished',settled:false,students:[{id:1,name:'甲'},{id:2,name:'乙'}],questions:[{kind:'written',id:101,stem:'原题101'},{kind:'choice',id:201,stem:'原题201',options:['a','b']}],recorded:[]};
var posts=[],failNext=false;
function api(url,opts){if(opts&&opts.json){if(failNext)return Promise.reject(Error('纸质包版本冲突'));posts.push(opts.json);data.questions.reverse();data.recorded=[{studentId:2,kind:'written',questionId:101}];return Promise.resolve({message:'已保存'})}return Promise.resolve(data)}
async function settle(){for(let i=0;i<20;i++)await Promise.resolve()}
''' + BACKUP_JS + r'''
(async()=>{
 const root=new E('div');backupTeacher(root);const details=root.children[0];details.open=true;details.handlers.toggle();await settle();
 const selects=all(root,'select'),pupil=selects[0],question=selects[1],text=all(root,'textarea')[0],inputs=all(root,'input');
 text.value='甲的未保存答案';pupil.value='2';yes=false;pupil.onchange();assert.equal(pupil.value,'1');assert.equal(text.value,'甲的未保存答案');
 pupil.value='2';yes=true;pupil.onchange();assert.equal(text.value,'');
 inputs.find(x=>String(x.attrs.placeholder||'').includes('16位')).value=data.version;
 inputs.find(x=>String(x.attrs.placeholder||'').includes('故障原因')).value='答卷2';
 text.value='乙的答案';const save=all(root,'button').find(x=>x.attrs.text==='核对并补入原课堂');save.onclick();await settle();
 assert.equal(posts.length,1);assert.equal(posts[0].studentId,2);assert.equal(posts[0].questionId,101);assert.equal(posts[0].text,'乙的答案');
 assert.equal(question.value,'written:101');assert.equal(text.value,'');assert(save.disabled);
 question.value='choice:201';question.onchange();const choice=selects[2];choice.value='1';failNext=true;save.onclick();await settle();
 assert(all(root,'p').some(x=>x.textContent==='纸质包版本冲突'));assert.equal(choice.value,'1');assert(!save.disabled);
 choice.value='';
 for(const role of ['teacher','student']){all(root,'button').find(x=>x.attrs.text===(role==='teacher'?'下载教师版 Word':'下载学生版 Word')).onclick();await settle()}
 assert.deepEqual(downloads.map(x=>x.url),['/teacher/weekend/sessions/1/backup.docx?audience=teacher','/teacher/weekend/sessions/1/backup.docx?audience=student']);
 assert(downloads.every(x=>x.options.headers.Authorization==='Bearer t'));assert.deepEqual(links.map(x=>x.download),['weekend-1-teacher.docx','weekend-1-student.docx']);
 console.log('OK');
})().catch(e=>{console.error(e);process.exitCode=1});
'''
    result = subprocess.run(['node','-e',harness],text=True,capture_output=True,timeout=30)
    assert result.returncode==0,result.stdout+result.stderr
    assert 'OK' in result.stdout
