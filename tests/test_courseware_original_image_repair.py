import importlib.util
import sys
from pathlib import Path

spec = importlib.util.spec_from_file_location('courseware_backup_helpers', Path(__file__).with_name('test_weekend_backup.py'))
b = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = b
spec.loader.exec_module(b)


def test_numbered_original_questions_are_extracted_without_teacher_answers():
    from changying.services.weekend_presentation import literal_numbered_questions, lesson_deck
    text = '第1题 2分\n选择题\n1＋1＝？\n答案：2\n解析：相加\n第2题 3分\n填空\n2＋2＝？\n答案：4'
    questions = literal_numbered_questions(text)
    assert len(questions) == 2
    assert '1＋1＝？' in questions[0] and '2＋2＝？' in questions[1]
    assert all('答案' not in q and q in text for q in questions)
    assert literal_numbered_questions(text + '\n第2题\n重复题') == []
    commentary = '第1题检查学生能否区分数量。\n第2题检查运算顺序。'
    assert literal_numbered_questions(commentary) == []
    assert literal_numbered_questions('\n'.join(commentary)) == []
    pages = lesson_deck({'reading_plan': text, 'examples_json': '["AI 摘要"]'}, 3)
    assert len(pages) == 2 and '1＋1＝？' in pages[0] and 'AI 摘要' not in pages[0]


def test_mismatched_or_ambiguous_numbers_never_fall_back_to_another_figure():
    from changying.web.weekend_courseware import match_figure
    figure = {'type': 'uploaded_image', 'data_url': 'data:image/jpeg;base64,' + 'A' * 40}
    figures = [{'number': 7, 'key': '两个题共用的很长文字以及更多的说明', 'figure': figure}]
    assert match_figure(figures, '第8题 两个题共用的很长文字以及更多的说明') == {}
    assert match_figure(figures + figures, '第7题 两个题共用的很长文字以及更多的说明') == {}


def test_editor_preview_and_save_keep_original_image(tmp_path):
    import subprocess
    from changying.web.weekend_courseware_pages import COURSEWARE_JS, COURSEWARE_PLAN_JS
    dom = r'''
const assert=require('assert');
class E{constructor(tag,a){this.tag=tag;this.a=a||{};this.children=[];this.parentNode=null;this.value=String(this.a.value||'');this.checked=false;this.handlers={};this._text=this.a.text||'';this.scrolled=false}
 appendChild(c){if(c.parentNode)c.parentNode.children=c.parentNode.children.filter(x=>x!==c);this.children.push(c);c.parentNode=this;if(this.tag==='select'&&!this.value)this.value=String(c.a.value||'');return c}
 insertBefore(c,b){if(c.parentNode)c.parentNode.children=c.parentNode.children.filter(x=>x!==c);let i=b?this.children.indexOf(b):-1;this.children.splice(i<0?this.children.length:i,0,c);c.parentNode=this;return c}
 get nextSibling(){if(!this.parentNode)return null;let i=this.parentNode.children.indexOf(this);return this.parentNode.children[i+1]||null}
 addEventListener(k,f){this.handlers[k]=f} set textContent(v){this._text=v;this.children=[]} get textContent(){return this._text}
 scrollIntoView(){this.scrolled=true} }
function el(tag,a,...children){let e=new E(tag,a);children.filter(Boolean).forEach(c=>e.appendChild(c));return e}
function all(e){return [e,...e.children.flatMap(c=>c instanceof E?all(c):[])]}
function find(e,text){return all(e).find(x=>x.tag==='button'&&x.a.text===text)}
var document={},confirm=()=>true,prompt=()=>null,sent=null;
var figure={type:'uploaded_image',data_url:'data:image/jpeg;base64,'+'A'.repeat(40),alt:'原卷插图'};
var data={subject:'数学',courseType:'math',stageOptions:[{no:3,name:'例题讲解'},4,5,6,7].map(function(n){return typeof n==='number'?{no:n,name:'环节'+n}:n}),templates:['steps'],kindLabels:{steps:'分步讲解'},pages:{'3':['第1题']},
 cached:{'3:0':{stage:3,page:0,kind:'steps',status:'draft',params:{title:'原题',problem:'题目',steps:['一','二'],answer:'4',figure:figure}}},
 items:[{stage:3,page:0,kind:'steps',status:'draft',params:{title:'原题',problem:'题目',steps:['一','二'],answer:'4',figure:figure}}]};
function api(path,opts){if(opts&&opts.method==='PUT'){sent=opts.json;return Promise.resolve(data)}return Promise.resolve(data)}
'''
    exercise = r'''
(async()=>{let root=new E('div');cwPlan(root,1,null);await Promise.resolve();await Promise.resolve();
 let open=find(root,'预览／修改');assert(open,'the page button offers preview once it has courseware');open.a.onclick();await Promise.resolve();
 assert(all(root).some(x=>x.tag==='img'&&x.a.src===figure.data_url));
 let save=find(root,'保存修改（需重新审核）');assert(save);
 let editorBox=save.parentNode.parentNode;
 assert(editorBox,'editor container exists');
 assert(editorBox.scrolled,'the editor is brought into view');
 save.a.onclick();await Promise.resolve();
 assert.deepStrictEqual(sent.params.figure,figure);console.log('OK')})().catch(e=>{console.error(e);process.exit(1)});
'''
    script = tmp_path / 'courseware_editor.js'
    script.write_text(dom + COURSEWARE_JS + COURSEWARE_PLAN_JS + exercise, encoding='utf-8')
    r = subprocess.run(['node', str(script)], capture_output=True, text=True, encoding='utf-8', timeout=20)
    assert r.returncode == 0, r.stderr
    assert 'OK' in r.stdout


def test_original_image_survives_save_and_approval(tmp_path):
    b.helpers.run_isolated(tmp_path, b.COMMON + r'''
with TestClient(app) as client:
    th,sh,student,school,lid,qid,wid,sid,base,body=prepare(client)
    page=client.get('/v1/weekend-plan',headers={'User-Agent':'Mozilla/5.0 (iPad; CPU OS 12_5_8 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/12.1 Mobile/15E148 Safari/604.1'})
    assert page.status_code==200,page.text
    url='/teacher/weekend/lessons/'+str(lid)+'/courseware'
    fig={'type':'uploaded_image','data_url':'data:image/jpeg;base64,'+'A'*40,'alt':'原卷插图'}
    data={'stageNo':3,'page':0,'kind':'steps','params':{'problem':'原题','steps':['第一步','第二步'],'answer':'答案','figure':fig},'writtenTask':False}
    r=client.put(url,headers=th,json=data)
    assert r.status_code==200,r.text
    assert r.json()['items'][0]['params']['figure']==fig
    r=client.post(url+'/approve',headers=th,json={'stageNo':3,'page':0})
    assert r.status_code==200,r.text
    assert r.json()['items'][0]['approved']['figure']==fig
    data['params']['answer']='新答案'
    r=client.put(url,headers=th,json=data)
    assert r.status_code==200,r.text
    assert r.json()['items'][0]['approved']['answer']=='答案'
    r=client.post(url+'/restore-previous',headers=th,json={'stageNo':3,'page':0})
    assert r.status_code==200,r.text
    assert r.json()['items'][0]['params']['answer']=='答案'
    assert r.json()['items'][0]['params']['figure']==fig
    print('OK')
''')


def test_imported_literal_question_survives_ai_summary(tmp_path):
    b.helpers.run_isolated(tmp_path, b.COMMON + r'''
source='第1题 2分\n判断\n原题：2＋2＝几？\n答案：4\n解析：相加\n第2题 3分\n填空\n原题：3＋3＝几？\n答案：6'
def fake_call(*args,**kwargs):
    prompt=args[3]
    if '选择一个互动课件模板' in prompt:
        return json.dumps({'template':'steps','title':'算一算','problem':'AI 改写内容','steps':['看题','计算'],'answer':'4','figure':{}},ensure_ascii=False)
    return json.dumps({'title':'原题保护','coreTarget':'计算','examples':['AI 摘要'], 'ppt':[], 'questions':[], 'writtenQuestions':[]},ensure_ascii=False)
legacy._ai_call=fake_call
with TestClient(app) as client:
    th,sh,student,school,lid,qid,wid,sid,base,body=prepare(client)
    r=client.post('/teacher/weekend/lessons/import',headers=th,data={'subject':'数学','lessonNo':'10','text':source})
    assert r.status_code==200,r.text
    imported=r.json()['lessonId']; url='/teacher/weekend/lessons/'+str(imported)+'/courseware'
    r=client.post(url+'/generate',headers=th,json={'stageNo':3,'page':0})
    assert r.status_code==200,r.text
    params=r.json()['items'][0]['params']
    assert '原题：2＋2＝几？' in params['sourceProblem']
    assert '答案：4' not in params['sourceProblem']
    assert params['problem']==params['sourceProblem']
    print('OK')
''')



def test_reimport_restores_lesson_questions_figures_and_courseware_atomically(tmp_path):
    b.helpers.run_isolated(tmp_path, b.COMMON + r'''
with TestClient(app) as client:
    th, sh, sid, school = setup(client)
    path = "/teacher/weekend/lessons/import/structured"
    def put(title):
        item = dict(lessonNo=6, title=title, coreTarget=title, teacherPlan=title + "教法",
            ppt=[title + "大屏"], examples=[title + "例题"], closureTraining=title + "练习",
            questions=[dict(stem=title+"选择", options=["左","右"], correctIndex=1)],
            writtenQuestions=[dict(stem=title+"简答", reference=title+"参考")])
        response = client.post(path, headers=th, json=dict(subject="数学", onConflict="overwrite", items=[item]))
        assert response.status_code == 200, response.text
        result = response.json()["items"][0]
        assert result["ok"], result
        return result["lessonId"]
    lid = put("原版")
    url = "/teacher/weekend/lessons/" + str(lid)
    figure = dict(type="uploaded_image",data_url="data:image/jpeg;base64,"+"A"*40,alt="原卷插图")
    params = dict(title="原图题",problem="题目",steps=["步骤一","步骤二"],answer="4",figure=figure)
    saved = client.put(url+"/courseware",headers=th,json=dict(stageNo=3,page=0,kind="steps",params=params))
    assert saved.status_code == 200, saved.text
    assert client.post(url+"/courseware/approve",headers=th,json=dict(stageNo=3,page=0)).status_code == 200
    with legacy.SessionLocal() as db:
        question = db.scalar(select(legacy.TeachingQuestion).where(legacy.TeachingQuestion.lesson_id == lid,
            legacy.TeachingQuestion.stem == "原版选择"))
        question.figure_json = json.dumps(figure)
        db.commit()
    def read():
        return [client.get(url+suffix,headers=th).json() for suffix in ("","/questions","/written/questions","/courseware")]
    before = read()
    assert put("新版") == lid
    current = read()
    version = current[0]["previousImportId"]
    assert version and current[0]["title"] == "新版"
    assert len(current[3]["items"]) == 1  # old reviewable courseware survives overwrite
    old = current[3]["items"][0]
    assert old["status"] == "draft" and old["needsSync"] is True and old["approved"] is None
    assert old["params"]["title"] == "原图题"
    assert client.post(url+"/courseware/approve",headers=th,json=dict(stageNo=3,page=0)).status_code == 409
    undo = url + "/import-history/" + str(version) + "/restore"
    assert client.post(undo,headers=sh).status_code == 403
    response = client.post(undo,headers=th)
    assert response.status_code == 200, response.text
    assert read() == before
    assert client.post(undo,headers=th).status_code == 409
    # Even when text is identical, a DOCX picture can have changed.
    # Reimport must revoke old approval and demand an explicit new save.
    assert put("原版") == lid
    same = read()[3]["items"][0]
    assert same["needsSync"] is True and same["status"] == "draft"
    assert client.post(url+"/courseware/approve",headers=th,json=dict(stageNo=3,page=0)).status_code == 409
    new_draft = client.put(url+"/courseware",headers=th,json=dict(stageNo=3,page=0,kind="steps",params=params))
    assert new_draft.status_code == 200 and not new_draft.json()["items"][0]["needsSync"]
    assert client.post(url+"/courseware/approve",headers=th,json=dict(stageNo=3,page=0)).status_code == 200
    put("再次导入")
    undo = url + "/import-history/" + str(read()[0]["previousImportId"]) + "/restore"
    with legacy.SessionLocal() as db:
        lesson = db.get(legacy.TeachingLesson, lid)
        lesson.teacher_plan = "导入后老师手改"
        db.commit()
    assert client.post(undo,headers=th).status_code == 409
    assert read()[0]["teacherPlan"] == "导入后老师手改"
    print("OK")
''')


def test_teacher_restores_previous_lesson_from_review_in_chrome(tmp_path):
    """Exercise the actual teacher page in Chrome with synthetic, in-memory HTTP responses."""
    import shutil
    import subprocess
    import pytest
    from changying.web.weekend_pages import plan_page_html

    chrome = shutil.which("google-chrome") or shutil.which("chromium")
    if not chrome:
        pytest.skip("Chrome unavailable on this host")
    fixture = """
sessionStorage.setItem('v717Token','test-only');
let restored=false,confirmed=false,posts=0;
window.confirm=()=>confirmed;
window.fetch=(path,opts)=>{
  let row={subject:'数学',lessonId:4,lessonNo:4,hasPlan:true,approvedQuestions:1,draftQuestions:0,title:restored?'旧教案':'新教案'};
  let data={items:[]};
  if(path==='/session')data={role:'teacher'};
  if(path.includes('/schedule?'))data={items:[row]};
  if(path==='/teacher/weekend/lessons/4/import-history/7/restore'){
    if(opts.method!=='POST')throw Error('method');
    restored=true;posts++;data=row;
  }
  if(path==='/teacher/weekend/lessons/4')data={title:row.title,ppt:[],examples:[],previousImportId:restored?null:7};
  return Promise.resolve({ok:true,json:()=>Promise.resolve(data)});
};
"""
    exercise = """
function button(label){return Array.from(document.querySelectorAll('button')).find(b=>b.textContent===label)}
let phase=0;
let timer=setInterval(()=>{
  let undo=button('恢复重新导入前的整份教案');
  if(phase===0&&button('教案与题目审核')){button('教案与题目审核').click();phase=1}
  else if(phase===1&&undo){undo.click();if(posts)throw Error('cancel');confirmed=true;undo.click();phase=2}
  else if(phase===2&&!undo&&posts===1&&Array.from(document.querySelectorAll('input')).some(i=>i.value==='旧教案')){
    document.body.setAttribute('data-restore-result','passed');clearInterval(timer);
  }
},40);
"""
    html = plan_page_html().replace('<script>', '<script>'+fixture+'</script><script>', 1)
    path = tmp_path / 'review.html'
    path.write_text(html.replace('</body>', '<script>'+exercise+'</script></body>'), encoding='utf-8')
    result = subprocess.run([chrome, '--headless', '--no-sandbox', '--disable-dev-shm-usage',
        '--disable-gpu', '--disable-background-networking', '--user-data-dir='+str(tmp_path/'chrome'),
        '--virtual-time-budget=4000', '--dump-dom', path.as_uri()], capture_output=True, text=True, timeout=40)
    assert result.returncode == 0, result.stderr
    assert 'data-restore-result="passed"' in result.stdout
