from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('mixed_helpers', ROOT / 'tests/test_homework_solve.py')
helpers = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = helpers
spec.loader.exec_module(helpers)


def test_reading_paper_import_approval_snapshot_submission_and_review(tmp_path):
    # A real teacher-uploaded DOCX can be exercised locally without committing
    # the user's entire document into the repository.
    docx_path = os.environ.get('LESSON_REPRO_DOCX', '')
    helpers.run_isolated(tmp_path, helpers.COMMON + '\nDOCX_PATH = ' + repr(docx_path) + r'''
import io, zipfile
from pathlib import Path
from html import escape
source = ''' + repr('篇目一：精读精测《神泉与金鹿》\n阿木进山找水，金鹿帮助他引出神泉，他化作石像。\n1.【概括】概括主要内容。\n2.【想象】哪些地方神奇？\n3.【复述】以阿木口吻复述。\n篇目二：变式拓展《鲁班造锯》\n鲁班观察草叶的细齿，造出了锯。\n1.【信息提取】说说发明的起因。\n2.【扩写】扩写观察动作。\n3.【缩写】缩写故事。\n篇目三：读写结合·小练笔\n题目 ：扩写白娘子打听消息。\n挑战题\nC1.【对比】阿木和海力布有什么相同？\nC2.【复述】为鲁班故事设计倒叙开头。\n五、参考答案与评分细则\n篇目一\n教师评分秘密：舍己为人。\n篇目二\n教师评分秘密：观察与创造。\n挑战题\n教师评分秘密：结构和情感。\n六、小练笔评分量规\n教师评分秘密：动作神态。') + r'''
if DOCX_PATH:
    raw=Path(DOCX_PATH).read_bytes()
else:
    buf=io.BytesIO()
    with zipfile.ZipFile(buf,'w') as z:
        z.writestr('[Content_Types].xml','<Types/>')
        z.writestr('word/document.xml','<w:document>'+''.join('<w:p><w:r><w:t>'+escape(line)+'</w:t></w:r></w:p>' for line in source.splitlines())+'</w:document>')
    raw=buf.getvalue()
with TestClient(app) as client:
    th, sh, student_id, school_id=setup(client)
    # Deliberately omit all written questions in the AI response. Literal
    # extraction must retain the nine actual paper questions anyway.
    replies.append(json.dumps({'title':'民间故事阅读','coreTarget':'概括与复述','teacherPlan':'阅读并作答','ppt':['目标'], 'examples':[], 'questions':[]},ensure_ascii=False))
    r=client.post('/teacher/weekend/lessons/import',headers=th,data={'subject':'语文','lessonNo':'17'},files={'file':('reading.docx',raw,'application/octet-stream')})
    assert r.status_code==200,r.text
    assert r.json()['writtenQuestionsFound']==9,r.text
    lid=r.json()['lessonId'];url=f'/teacher/weekend/lessons/{lid}/written/questions'
    full=client.get(f'/teacher/weekend/lessons/{lid}',headers=th).json()
    assert '神泉与金鹿' in full['sourceText'] and '鲁班造锯' in full['sourceText']
    questions=client.get(url,headers=th).json()['items']
    assert len(questions)==9 and not any(q['approved'] for q in questions)
    assert '金鹿' in questions[0]['stem'] and questions[0]['reference']
    assert '鲁班' in questions[3]['stem'] and questions[3]['reference']
    assert questions[6]['type']=='composition' and questions[6]['reference']
    assert client.get(url,headers=sh).status_code==403
    with legacy.SessionLocal() as db:
        tid=db.scalar(select(legacy.User.id).where(legacy.User.username=='teacher1'))
        cls=db.scalar(select(legacy.SchoolClass).where(legacy.SchoolClass.school_id==school_id));cls.teacher_id=tid
        link=db.scalar(select(legacy.ClassStudent).where(legacy.ClassStudent.student_id==student_id))
        if link:link.class_id=cls.id
        else:db.add(legacy.ClassStudent(class_id=cls.id,student_id=student_id))
        db.commit()
    # Unapproved templates never enter a classroom.
    s0=client.post('/teacher/weekend/sessions',headers=th,json={'lessonId':lid}).json()['id']
    assert client.get(f'/teacher/weekend/sessions/{s0}/written',headers=th).json()['questions']==[]
    q=questions[0]
    r=client.put(url+'/'+str(q['id']),headers=th,json={'stem':q['stem'],'reference':'教师专用评分秘密','hints':['找人物','找事件','组织句子']})
    assert r.status_code==200,r.text
    approved=client.post(url,headers=th,json={'approve':[x['id'] for x in questions]})
    assert approved.status_code==200 and approved.json()['approvedQuestions']==9,approved.text
    schedule=client.get('/teacher/weekend/schedule?subject=语文',headers=th).json()['items']
    assert next(x for x in schedule if x['lessonId']==lid)['approvedQuestions']==9
    session=client.post('/teacher/weekend/sessions',headers=th,json={'lessonId':lid}).json()['id']
    base=f'/teacher/weekend/sessions/{session}'
    assert len(client.get(base+'/written',headers=th).json()['questions'])==9
    client.post(base+'/start',headers=th);client.post(base+'/goto',headers=th,json={'stage':4})
    # This scenario explicitly opens its exercises before testing student work.
    for ordinal in range(1, client.get(base, headers=th).json()['answerRelease']['total'] + 1):
        assert client.post(base+'/practice-question', headers=th, json={'question':ordinal}).status_code == 200
    assert client.post(base+'/practice-question', headers=th, json={'question':1}).status_code == 200
    page=client.get(f'/student/weekend/sessions/{session}/written',headers=sh)
    assert page.status_code==200,page.text
    assert len(page.json()['questions'])==9 and page.json()['canSubmit']
    assert '教师专用评分秘密' not in page.text and '参考答案与采分点' not in page.text
    qid=page.json()['questions'][0]['id']
    assert client.post(f'/student/weekend/sessions/{session}/written/{qid}/hint',headers=sh).json()['text']=='找人物'
    sent=client.post(f'/student/weekend/sessions/{session}/written/{qid}',headers=sh,data={'text':'阿木救了乡亲，自己化成石像'})
    assert sent.status_code==200,sent.text
    teacher=client.get(base+'/written',headers=th).json();assert teacher['submitted']==1
    aid=teacher['items'][0]['id']
    assert client.post(base+f'/written/{aid}/review',headers=th,json={'revision':1,'result':'correct','comment':'概括完整'}).status_code==200
    assert client.get(f'/student/weekend/sessions/{session}/written',headers=sh).json()['questions'][0]['submission']['result']=='pending'
    board=client.get(base+'/board',headers=th)
    assert '概括' in board.text and '教师专用评分秘密' not in board.text
    published=client.post(base+'/publish-answers',headers=th,json={'question':1})
    assert published.status_code==200,published.text
    assert '教师专用评分秘密' in client.get(base+'/board',headers=th).text
    assert client.get(f'/student/weekend/sessions/{session}/written',headers=sh).json()['questions'][0]['submission']['result']=='correct'
    assert client.get(f'/student/weekend/sessions/{session}/written',headers=sh).json()['canSubmit'] is True
    # Editing approved templates returns them to draft without changing an
    # existing session snapshot or its grading reference.
    client.put(url+'/'+str(q['id']),headers=th,json={'stem':'修改后的题目','reference':'新参考'})
    assert not client.get(url,headers=th).json()['items'][0]['approved']
    assert client.get(base+'/written',headers=th).json()['questions'][0]['reference']=='教师专用评分秘密'
    # AI question generation uses actual imported reading material and accepts
    # written-only results without requiring any multiple choice.
    replies.append(json.dumps({'items':[{'type':'short_answer','level':'中等','stem':'用自己的话概括这篇文章讲了什么。','answer':'评分要点','steps':['找人物','找事件']}]},ensure_ascii=False))
    replies.append(json.dumps({'items':[]}))
    r=client.post('/teacher/weekend/lessons/draft',headers=th,json={'subject':'语文','lessonNo':17,'onlyQuestions':True})
    assert r.status_code==200,r.text
    assert '神泉与金鹿' in prompts[-2] and '写作／复述' in prompts[-2] and '提高' in prompts[-2]
    assert client.get(f'/teacher/weekend/lessons/{lid}',headers=th).json()==full
    assert len(client.get(url,headers=th).json()['items'])==9  # 8 approved originals + new draft
    # Approval/delete IDs cannot reach a different lesson or session snapshot.
    assert client.post(url,headers=sh,json={'approve':[qid]}).status_code==403
    html=client.get('/v1/weekend-plan').text
    assert all(t in html for t in ('教案编辑','习题审核','原文核对','展开阅读材料／题目全文'))
    assert 'loadQ();loadWritten()' in html and 'go.disabled=' in html
    assert 'function approveQuestionInPlace' in html and html.count('approveQuestionInPlace(') >= 3
    print('OK')
''')


def test_plan_tabs_and_written_approval_enable_classroom_without_erasing_edits():
    from test_node_script import run_node
    from changying.web.weekend_pages import PLAN_JS
    script = r'''
const assert=require('node:assert/strict');
class Element {
 constructor(tag,attrs){this.tag=tag;this.attrs=attrs||{};this.children=[];this.value=this.attrs.value||'';this.hidden=!!this.attrs.hidden;this.disabled=!!this.attrs.disabled;this._text=this.attrs.text||''}
 appendChild(n){this.children.push(n);return n}
 set textContent(t){this._text=t;this.children=[]} get textContent(){return this._text}
 setAttribute(k,v){this.attrs[k]=v}
 addEventListener(){} querySelectorAll(tag){return all(this,tag)}
}
function all(n,tag){return n.children.flatMap(c=>c instanceof Element?[(c.tag===tag?c:null),...all(c,tag)].filter(Boolean):[])}
function el(tag,attrs,...children){const n=new Element(tag,attrs);children.forEach(c=>n.appendChild(c));return n}
var root=new Element('div'),location={href:''};
function growTextarea(){} function boot(){} function confirm(){return true}
const row={lessonId:1,lessonNo:1,hasPlan:true,approvedQuestions:0,draftQuestions:1};
let approved=false;
function api(path,opts){
 if(path==='/teacher/weekend/next')return Promise.resolve({items:[]});
 if(path.startsWith('/teacher/weekend/schedule'))return Promise.resolve({items:[row]});
 if(path.endsWith('/written/questions')){if(opts){approved=true;return Promise.resolve({...row,approvedQuestions:1,draftQuestions:0})}return Promise.resolve({items:[{id:11,type:'short_answer',stem:'阅读文章\n\n概括内容',reference:'仅老师可见',approved,hints:[]}]})}
 if(path.endsWith('/questions'))return Promise.resolve({items:[]});
 if(path==='/teacher/weekend/lessons/1')return Promise.resolve({title:'阅读',coreTarget:'概括',teacherPlan:'流程',sourceText:'完整原文和教师答案',ppt:[],examples:[],closureTraining:'作业'});
 throw Error(path);
}
async function settle(){for(let i=0;i<15;i++)await Promise.resolve()}
''' + PLAN_JS + r'''
(async()=>{
 plan();await settle();let go=all(root,'button').find(x=>x.textContent==='开课');assert(go.disabled);
 all(root,'button').find(x=>x.textContent==='审改').attrs.onclick();await settle();
 const tabs=all(root,'button').filter(x=>x.attrs.role==='tab');assert.equal(tabs.length,4);assert.equal(tabs[3].textContent,'互动课件');
 let panes=all(root,'div').find(x=>x.attrs.role==='tablist');
 const form=all(root,'textarea').find(x=>x.value==='流程');form.value='尚未保存的编辑';
 tabs[1].attrs.onclick();assert.equal(tabs[1].attrs['aria-selected'],'true');
 all(root,'button').find(x=>x.textContent==='通过').attrs.onclick();await settle();
 assert(!go.disabled);assert.equal(form.value,'尚未保存的编辑');
 assert.equal(tabs[1].attrs['aria-selected'],'true');
 tabs[2].attrs.onclick();assert.equal(tabs[2].attrs['aria-selected'],'true');
 assert(all(root,'pre').some(x=>x.textContent==='完整原文和教师答案'));
 console.log('OK');
})().catch(e=>{console.error(e);process.exitCode=1});
'''
    # 页面脚本加上这些功能后超过了 Windows 32k 命令行上限，用仓库统一的临时文件执行器。
    result = run_node(script, timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr
