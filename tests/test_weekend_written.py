from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("written_hw_helpers", ROOT / "tests" / "test_homework_solve.py")
helpers = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = helpers
spec.loader.exec_module(helpers)


def test_written_answers_real_routes_and_private_photos(tmp_path):
    helpers.run_isolated(tmp_path, helpers.COMMON + r'''
import base64
from sqlalchemy import update
PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+j5WQAAAAASUVORK5CYII=")
with TestClient(app) as client:
    th, sh, sid, school_id = setup(client)
    def approve_courseware_gate(lid):
        __import__('sys').path.insert(0, 'tests'); from test_chinese_readiness import prepare_reviewed_lesson
        prepare_reviewed_lesson(client, th, legacy, lid)
    with legacy.SessionLocal() as db:
        p = db.scalar(select(legacy.TeachingProgram).where(legacy.TeachingProgram.school_id == school_id))
        l = legacy.TeachingLesson(school_id=school_id, program_id=p.id, subject="语文", lesson_no=12, title="民间故事", core_target="概括情节")
        db.add(l); db.flush(); lid = l.id
        tid = db.scalar(select(legacy.User.id).where(legacy.User.username == "teacher1"))
        cls = db.scalar(select(legacy.SchoolClass).where(legacy.SchoolClass.school_id == school_id)); cls.teacher_id = tid
        link = db.scalar(select(legacy.ClassStudent).where(legacy.ClassStudent.student_id == sid))
        if link is None: db.add(legacy.ClassStudent(class_id=cls.id, student_id=sid))
        else: link.class_id = cls.id
        db.commit(); class_id = cls.id
    selected = client.put('/teacher/weekend/schedule/语文/12/course-type', headers=th,
                          json={'courseType':'reading','expectedRevision':0})
    assert selected.status_code == 200, selected.text
    # 阅读课开课前必须先有一道已审核的课堂任务；先维护一道选择题并通过。
    with legacy.SessionLocal() as db:
        p = db.scalar(select(legacy.TeachingProgram).where(legacy.TeachingProgram.school_id == school_id))
        db.add(legacy.TeachingQuestion(school_id=school_id, program_id=p.id, lesson_id=lid, stage="4", subject="语文", level="A",
                                       knowledge="民间故事", stem="海力布为什么愿意牺牲自己？",
                                       options_json=json.dumps(["想出名", "救乡亲", "赚钱", "没想过"], ensure_ascii=False),
                                       correct_index=1, explanation="他为了救乡亲。", active=False))
        db.commit()
        ready = db.scalar(select(legacy.TeachingQuestion.id).where(legacy.TeachingQuestion.lesson_id == lid))
    assert client.post('/teacher/weekend/lessons/%d/questions' % lid, headers=th, json={'approve': [ready]}).status_code == 200
    approve_courseware_gate(lid)
    s = client.post('/teacher/weekend/sessions', headers=th, json={'lessonId':lid}).json()['id']
    base = f'/teacher/weekend/sessions/{s}'
    student = f'/student/weekend/sessions/{s}/written'
    assert client.post(base+'/written/questions', headers=sh, json={'stem':'x'}).status_code == 403
    assert client.post(base+'/written/questions', headers=th, json={'stem':'  '}).status_code == 400
    assert client.post(base+'/written/questions', headers=th, json={'stem':'x', 'hints':['x']}).status_code == 400
    r = client.post(base+'/written/questions', headers=th, json={'stem':'概括海力布的品质', 'reference':'舍己救人', 'hints':['找关键句','联系行为','归纳品质']})
    assert r.status_code == 200, r.text
    qid = r.json()['id']; url = student+f'/{qid}'
    assert client.get(student, headers=sh).json()['questions'] == []
    assert client.post(url, headers=sh, data={'text':'答案'}).status_code == 409
    client.post(base+'/start', headers=th);client.post(base+'/goto', headers=th, json={'stage':5})
    # 随堂练习逐题开放：老师上到第 5 环节后开放第 1 道文字题，学生才能看到并提交。
    assert client.post(base+'/practice-question', headers=th, json={'question':1}).status_code == 200
    assert client.post(base+'/written/questions', headers=th, json={'stem':'late'}).status_code == 409
    page = client.get('/v1/weekend-practice').text
    assert 'writtenStudent(writtenBox)' in page and 'function cropPhoto' in page and '重新提交答案' in page
    control = client.get('/v1/weekend').text
    assert 'function writtenTeacher' in control and 'writtenTeacher(writtenBox)' in control
    current = client.get(student, headers=sh)
    assert '舍己救人' not in current.text and current.json()['canSubmit']
    assert client.post(url+'/hint', headers=sh).json()['text'] == '找关键句'
    assert client.get(student, headers=sh).json()['questions'][0]['hintUsed'] == 1
    assert client.post(url+'/hint', headers=sh).json()['level'] == 2
    assert client.post(url+'/hint', headers=sh).json()['level'] == 3
    assert client.post(url+'/hint', headers=sh).status_code == 404
    assert client.post(url, headers=sh, data={'text':' '}).status_code == 400
    assert client.post(url, headers=sh, files={'photo':('bad.png',b'not an image','image/png')}).status_code == 400
    assert client.post(url, headers=sh, files={'photo':('huge.png',b'x'*(3*1024*1024+1),'image/png')}).status_code == 413
    r = client.post(url, headers=sh, data={'text':'为救乡亲牺牲自己'}, files={'photo':('answer.png',PNG,'image/png')})
    assert r.status_code == 200, r.text
    assert r.json()['result'] == 'pending'
    candidates=client.get(base+'/peer-suggest',headers=th).json()
    assert candidates['mode']=='peer' and candidates['questions'][0]['questionType']=='written'
    assert candidates['questions'][0]['submitted'][0]['result']=='pending'
    assert '还没有学生作答' not in candidates['message']
    invite=client.post(base+'/explain',headers=th,json={'questionType':'written','questionId':qid,'tutorId':sid})
    assert invite.status_code==200,invite.text
    assert invite.json()['followup'] is False
    assert client.post(base+'/explain',headers=th,json={'questionType':'written','questionId':qid,'tutorId':sid}).status_code==200
    invitation=client.get('/student/weekend/explain',headers=sh).json()['items']
    assert len(invitation)==1 and invitation[0]['questionType']=='written'
    assert invitation[0]['answerText']=='为救乡亲牺牲自己' and invitation[0]['submission']['hasPhoto']
    assert 'reference' not in invitation[0]
    assert '综合练习' in str(client.get(base+'/board',headers=th).json()['content'])
    assert client.get(base+'/peer-help',headers=th).json()['items']==[]
    assert client.get('/student/weekend/followup',headers=sh).json()['active'] is False

    assert client.post(url, headers=sh, data={'text':'stale'}).status_code == 409
    d = client.get(base+'/written', headers=th).json()
    assert d['submitted'] == 1 and d['pending'] == 1 and d['reviewed'] == 0 and d['submissionRate'] == 100
    a = d['items'][0]; photo = f"/weekend/written/submissions/{a['id']}/photo"
    assert client.get(photo).status_code == 401
    assert client.get(photo, headers=th).content == PNG and client.get(photo, headers=sh).content == PNG
    with legacy.SessionLocal() as db:
        other = legacy.User(school_id=school_id, username='written_other', password_hash=legacy.hash_password('x'), name='同班同学', role='student', grade=3)
        db.add(other);db.flush();db.add(legacy.ClassStudent(class_id=class_id, student_id=other.id));other_id=other.id;db.commit()
    oh = {'Authorization':'Bearer '+login_and_change(client,'written_other','x','Other1234')}
    assert client.get(photo, headers=oh).status_code == 404
    assert client.get(student, headers=oh).json()['questions'][0]['submission'] is None
    assert client.get('/student/weekend/explain',headers=oh).json()['items']==[]
    assert client.post(base+'/explain',headers=th,json={'questionType':'written','questionId':qid,'tutorId':other_id}).status_code in (400,404)

    assert client.post(url+'/hint', headers=sh).status_code == 409
    review = base+f"/written/{a['id']}/review"
    assert client.post(review, headers=sh, json={'revision':1,'result':'correct'}).status_code == 403
    assert client.post(review, headers=th, json={'revision':1,'result':'invalid'}).status_code == 400
    assert client.post(review, headers=th, json={'revision':1,'result':'partial','comment':'补充品质词'}).status_code == 200
    assert client.post(review, headers=th, json={'revision':1,'result':'correct'}).status_code == 409
    a = client.get(student, headers=sh).json()['questions'][0]['submission']
    assert a['result'] == 'pending' and a['comment'] == '' and a['revision'] == 2
    assert client.post(url, headers=sh, data={'text':'舍己救人','revision':1}).status_code == 409
    assert client.post(url, headers=sh, data={'text':'舍己救人','revision':2}).status_code == 200
    assert client.post(review, headers=th, json={'revision':3,'result':'correct','comment':'完整'}).status_code == 200
    d = client.get(base+'/written', headers=th).json()
    assert d['submitted'] == d['reviewed'] == d['correct'] == 1 and d['pending'] == 0
    assert client.post(url, headers=sh, data={'text':'第三次核对后的答案','revision':4}).status_code == 200
    assert client.post(review, headers=th, json={'revision':5,'result':'correct','comment':'完整'}).status_code == 200
    before = client.get(base+'/board', headers=th)
    assert '舍己救人' not in before.text
    # 随堂练习逐题开放：第 1 题是选择题（画面上是它的题干），
    # 老师翻到第 1 题就把它开放，并把这道文字题的参考答案一起公布。
    deck = client.get(base+'/board', headers=th).json()['deck']
    assert client.post(base+'/slide', headers=th, json={'delta': deck['index'] - 1}).status_code == 200
    published = client.post(base+'/publish-answers', headers=th, json={'question':1})
    assert published.status_code == 200, published.text
    # 逐题公布：第 2 题（文字题）也公布后，板书才翻到第 2 题的答案页。
    assert client.post(base+'/publish-answers', headers=th, json={'question':2}).status_code == 200
    assert client.post(base+'/slide', headers=th, json={'index': 1}).status_code == 200
    assert '舍己救人' in client.get(base+'/board', headers=th).text
    assert client.get('/student/weekend/explain',headers=sh).json()['items'][0]['reference']=='舍己救人'
    candidates=client.get(base+'/peer-suggest',headers=th).json()['questions'][0]['submitted']
    assert candidates[0]['result']=='correct' and candidates[0]['asked'] is True
    assert client.post(url, headers=sh, data={'text':'late','revision':4}).status_code == 409
    assert client.get(student, headers=sh).json()['questions'][0]['submission']['comment'] == '完整'
    client.post(base+'/finish', headers=th)
    d = client.get(student, headers=sh).json()
    assert d['canSubmit'] is False and d['questions'][0]['submission']['comment'] == '完整'
    assert client.post(url, headers=sh, data={'text':'late','revision':4}).status_code == 409
    # 每次开课都要有已审核的课堂任务；上一节已下课，这里再通过一道选择题供新课堂使用。
    with legacy.SessionLocal() as db:
        p = db.scalar(select(legacy.TeachingProgram).where(legacy.TeachingProgram.school_id == school_id))
        db.add(legacy.TeachingQuestion(school_id=school_id, program_id=p.id, lesson_id=lid, stage="4", subject="语文", level="A",
                                       knowledge="民间故事", stem="海力布把石头吐出来时说了什么？",
                                       options_json=json.dumps(["高声唤醒乡亲", "请求帮助", "告诉家人", "什么也没说"], ensure_ascii=False),
                                       correct_index=0, explanation="他让大家快跑。", active=False))
        db.commit()
        ready2 = db.scalar(select(legacy.TeachingQuestion.id).where(legacy.TeachingQuestion.lesson_id == lid,
                                                                  legacy.TeachingQuestion.stem.like("海力布把石头%")).order_by(legacy.TeachingQuestion.id.desc()))
    assert client.post('/teacher/weekend/lessons/%d/questions' % lid, headers=th, json={'approve': [ready2]}).status_code == 200
    approve_courseware_gate(lid)
    next_s = client.post('/teacher/weekend/sessions', headers=th, json={'lessonId':lid}).json()['id']
    assert client.get(f'/teacher/weekend/sessions/{next_s}/written', headers=th).json()['questions'] == []
    # Another teacher cannot read or grade this session's answers.
    with legacy.SessionLocal() as db:
        db.execute(update(legacy.Base.metadata.tables['weekend_sessions']).where(legacy.Base.metadata.tables['weekend_sessions'].c.id == s).values(teacher_id=999999))
        db.commit()
    assert client.get(photo, headers=th).status_code == 404
    assert client.get(base+'/written', headers=th).status_code == 404
    assert client.get(student, headers=sh).status_code == 404
    print('OK')
''')


def test_math_practice_empty_states_sync_gate_and_photo_submission(tmp_path):
    helpers.run_isolated(tmp_path, helpers.COMMON + r'''
import base64
from sqlalchemy import select
PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+j5WQAAAAASUVORK5CYII=")
with TestClient(app) as client:
    th, sh, student_id, school_id = setup(client)
    with legacy.SessionLocal() as db:
        teacher = db.scalar(select(legacy.User).where(legacy.User.username == "teacher1"))
        program = db.scalar(select(legacy.TeachingProgram).where(legacy.TeachingProgram.school_id == school_id))
        cls = legacy.SchoolClass(school_id=school_id, name="隔离数学练习班", grade=5, teacher_id=teacher.id)
        lesson = legacy.TeachingLesson(school_id=school_id, program_id=program.id, subject="数学", lesson_no=19,
                                       title="梯形与组合图形面积", core_target="会计算组合图形面积")
        db.add_all([cls, lesson]); db.flush()
        db.add(legacy.ClassStudent(class_id=cls.id, student_id=student_id))
        first = legacy.TeachingQuestion(school_id=school_id, program_id=program.id, lesson_id=lesson.id, stage="4",
                                        subject="数学", level="A", knowledge="梯形面积", stem="计算图形面积一",
                                        options_json=json.dumps(["12", "18"]), correct_index=0, active=True)
        db.add(first); db.commit()
        lesson_id, class_id, first_id, program_id = lesson.id, cls.id, first.id, program.id

    session_id = client.post("/teacher/weekend/sessions", headers=th,
                             json={"lessonId": lesson_id, "classId": class_id}).json()["id"]
    base = f"/teacher/weekend/sessions/{session_id}"
    written = client.post(base + "/written/questions", headers=th,
                          json={"stem": "写出梯形面积的计算过程", "reference": "底和×高÷2"})
    assert written.status_code == 200, written.text
    written_id = written.json()["id"]
    assert client.post(base + "/start", headers=th).status_code == 200
    assert client.post(base + "/goto", headers=th, json={"stage": 4}).status_code == 200

    with legacy.SessionLocal() as db:
        late = legacy.TeachingQuestion(school_id=school_id, program_id=program_id, lesson_id=lesson_id, stage="4",
                                       subject="数学", level="A", knowledge="梯形面积", stem="计算图形面积二",
                                       options_json=json.dumps(["24", "30"]), correct_index=1, active=True)
        db.add(late); db.commit()

    current = client.get("/student/weekend/current", headers=sh).json()
    assert current["practice"] and current["questions"] == []
    assert current["questionAvailability"]["state"] == "waiting_for_teacher"
    assert current["questionAvailability"]["written"] == {"total": 1, "open": 0}
    written_view = client.get(f"/student/weekend/sessions/{session_id}/written", headers=sh).json()
    assert written_view["questions"] == [] and written_view["questionAvailability"]["written"] == {"total": 1, "open": 0}

    control = client.get(base, headers=th).json()
    assert control["pendingPracticeSync"] == 1
    page = client.get("/v1/weekend-practice").text
    assert "习题审核" in page and "同步新增练习" in page and "学生首页“作业”" in page
    synced = client.post(base + "/sync-practice", headers=th, json={})
    assert synced.status_code == 200 and synced.json()["addedChoices"] == 1
    current = client.get("/student/weekend/current", headers=sh).json()
    assert current["questionAvailability"]["choice"] == {"total": 2, "open": 0}
    assert client.post(base + "/practice-question", headers=th, json={"question": 1}).status_code == 200
    assert len(client.get("/student/weekend/current", headers=sh).json()["questions"]) == 1
    hidden_written = client.get(f"/student/weekend/sessions/{session_id}/written", headers=sh).json()
    assert len(hidden_written["questions"]) == 1
    assert hidden_written["questions"][0]["canSubmit"] is True
    assert client.post(base + "/practice-question", headers=th, json={"question": 2}).status_code == 200
    assert len(client.get("/student/weekend/current", headers=sh).json()["questions"]) == 2
    assert client.post(base + "/practice-question", headers=th, json={"question": 3}).status_code == 200
    written_view = client.get(f"/student/weekend/sessions/{session_id}/written", headers=sh).json()
    assert [q["id"] for q in written_view["questions"]] == [written_id]
    submitted = client.post(f"/student/weekend/sessions/{session_id}/written/{written_id}", headers=sh,
                            data={"text": "", "revision": "0"}, files={"photo": ("answer.png", PNG, "image/png")})
    assert submitted.status_code == 200 and submitted.json()["submission"]["hasPhoto"]
    refreshed = client.get(f"/student/weekend/sessions/{session_id}/written", headers=sh).json()
    assert refreshed["questions"][0]["submission"]["hasPhoto"]
    teacher_answers = client.get(base + "/written", headers=th).json()["items"]
    photo_answer = next(item for item in teacher_answers if item["studentId"] == student_id)
    reviewed = client.post(base + "/written/review-batch", headers=th,
                           json={"items": [{"id": photo_answer["id"], "revision": photo_answer["revision"],
                                            "result": "partial", "comment": "补全高的对应边"}]})
    assert reviewed.status_code == 200 and reviewed.json()["items"][0]["result"] == "partial"
    print("OK")
''')


def test_student_keeps_other_question_drafts_when_submitting(tmp_path):
    from changying.web.weekend_written_pages import WRITTEN_JS

    script = r'''
const assert = require('node:assert/strict');
class Element {
  constructor(tag,attrs){this.tag=tag;this.attrs=attrs||{};this.children=[];this.value='';this._text='';this.disabled=!!this.attrs.disabled}
  addEventListener(){}
  appendChild(n){this.children.push(n);return n}
  set textContent(t){this._text=t;this.children=[]}
  get textContent(){return this._text||this.attrs.text||''}
}
function el(tag,attrs,...children){const n=new Element(tag,attrs);children.forEach(c=>n.appendChild(c));return n}
var ticks=[],document={hidden:false},setInterval=fn=>{ticks.push(fn);return ticks.length},window={addEventListener(){}},location={search:'',href:'https://example.test/v1/weekend-practice'},history={replaceState(){}},TOKEN='test';
var confirm=()=>true,alert=(msg)=>{throw Error(msg)},saved=[];
var practiceOpen=true;
var questions=[{id:1,stem:'篇目一：阅读\n共同文章正文\n\n题一',hasHints:false,submission:null},{id:2,stem:'篇目一：阅读\n共同文章正文\n\n题二',hasHints:false,submission:null}];
function api(path,opts){
  if(path==='/student/weekend/current')return Promise.resolve({active:true,practice:practiceOpen,sessionId:1});
  if(path.endsWith('/written'))return Promise.resolve({canSubmit:true,questions:questions});
  saved.push(opts.body.get('text'));questions[0].submission={id:10,questionId:1,text:opts.body.get('text'),revision:1,result:'pending',hasPhoto:false};
  return Promise.resolve({submitted:true,attempts:1,submission:questions[0].submission});
}
function all(root,tag){return root.children.flatMap(n=>n instanceof Element?[(n.tag===tag?n:null),...all(n,tag)].filter(Boolean):[])}
async function settle(){for(let i=0;i<8;i++)await Promise.resolve()}
''' + WRITTEN_JS + r'''
(async()=>{
 const root=new Element('div');writtenStudent(root);await settle();
 let areas=all(root,'textarea');assert.equal(areas.length,2);
 assert.equal(all(root,'div').filter(n=>n.attrs.text==='共同文章正文').length,1,'Render shared reading material once');
 areas[0].value='第一题答案';areas[0].oninput();areas[1].value='第二题尚未交的草稿';areas[1].oninput();
 const send=all(root,'button').find(n=>n.attrs.text==='提交答案');
 practiceOpen=false;ticks[0]();await settle();assert(send.disabled);assert.equal(areas[1].value,'第二题尚未交的草稿');
 practiceOpen=true;ticks[0]();await settle();assert(!send.disabled);
 send.attrs.onclick();await settle();
 assert.deepEqual(saved,['第一题答案']);areas=all(root,'textarea');
 assert.equal(areas.length,2);assert.equal(areas[1].value,'第二题尚未交的草稿');
 console.log('OK');
})().catch(e=>{console.error(e);process.exitCode=1});
'''
    result = subprocess.run(["node", "-e", script], text=True, capture_output=True, timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "OK" in result.stdout
