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
class E{constructor(tag,a){this.tag=tag;this.a=a||{};this.children=[];this.value=String(this.a.value||'');this.checked=false;this.handlers={};this._text=this.a.text||''}
 appendChild(c){this.children.push(c);if(this.tag==='select'&&!this.value)this.value=String(c.a.value||'');return c}
 addEventListener(k,f){this.handlers[k]=f} set textContent(v){this._text=v;this.children=[]} get textContent(){return this._text}
 scrollIntoView(){} }
function el(tag,a,...children){let e=new E(tag,a);children.filter(Boolean).forEach(c=>e.appendChild(c));return e}
function all(e){return [e,...e.children.flatMap(c=>c instanceof E?all(c):[])]}
function find(e,text){return all(e).find(x=>x.tag==='button'&&x.a.text===text)}
var document={},confirm=()=>true,prompt=()=>null,sent=null;
var figure={type:'uploaded_image',data_url:'data:image/jpeg;base64,'+'A'.repeat(40),alt:'原卷插图'};
var data={subject:'数学',templates:['steps'],kindLabels:{steps:'分步讲解'},pages:{'3':['第1题']},items:[{stage:3,page:0,kind:'steps',status:'draft',params:{title:'原题',problem:'题目',steps:['一','二'],answer:'4',figure:figure}}]};
function api(path,opts){if(opts&&opts.method==='PUT'){sent=opts.json;return Promise.resolve(data)}return Promise.resolve(data)}
'''
    exercise = r'''
(async()=>{let root=new E('div');cwPlan(root,1,null);await Promise.resolve();await Promise.resolve();
 let open=find(root,'预览／修改');assert(open);open.a.onclick();
 assert(all(root).some(x=>x.tag==='img'&&x.a.src===figure.data_url));
 let save=find(root,'保存修改（需重新审核）');assert(save);save.a.onclick();await Promise.resolve();
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
