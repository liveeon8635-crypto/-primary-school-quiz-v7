from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

from changying.services import weekend_courseware as cw
from changying.web.weekend_courseware_pages import COURSEWARE_JS, COURSEWARE_PLAN_JS
from changying.web.weekend_courseware import required_visual_figure, required_visual_type, _repair_courseware_visual
from changying.web.homework_assistant_pages import PAGE_CSS

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("weekend_courseware_figure_helpers", ROOT / "tests" / "test_homework_solve.py")
helpers = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = helpers
spec.loader.exec_module(helpers)


def test_figures_are_data_checked_before_they_are_drawn():
    seg = cw.clean_figure({"type": "segment", "points": [{"name": "D", "at": 10}, {"name": "A", "at": 0}, {"name": "B", "at": 6}],
                           "marks": [{"from": "A", "to": "D", "label": "L"}]})
    assert [p["name"] for p in seg["points"]] == ["A", "B", "D"] and seg["marks"] == [{"from": "A", "to": "D", "label": "L"}]
    flow = cw.clean_figure({"type": "flow", "boxes": ["输入 n"], "branches": [{"when": "n 是单数", "boxes": ["2n + 4"]},
                                                                               {"when": "n 是双数", "boxes": ["n² + 2"]}]})
    assert flow["boxes"] == ["输入 n"] and [b["when"] for b in flow["branches"]] == ["n 是单数", "n 是双数"]
    shape = cw.clean_figure({"type": "shape", "shape": "rectangle", "labels": {"top": "a cm", "left": "b cm", "colour": "red"}})
    assert shape == {"type": "shape", "shape": "rectangle", "labels": {"top": "a cm", "left": "b cm"}}
    assert cw.clean_figure({"type": "table", "rows": [["n", "1", "2"], ["结果", "6", "8"]]})["rows"][1] == ["结果", "6", "8"]
    assert cw.clean_figure({}) == {} and cw.clean_figure(None) == {}
    for bad in ({"type": "image", "src": "x"}, {"type": "segment", "points": [{"name": "A", "at": 0}]},
                {"type": "segment", "points": [{"name": "A", "at": 0}, {"name": "A", "at": 3}]},
                {"type": "segment", "points": [{"name": "A", "at": 0}, {"name": "B", "at": 3}], "marks": [{"from": "A", "to": "Z", "label": "x"}]},
                {"type": "flow", "boxes": ["只有一个"]}, {"type": "flow", "boxes": ["输入"], "branches": [{"when": "单数", "boxes": ["+1"]}]},
                {"type": "shape", "shape": "circle"}, {"type": "table", "rows": [["a", "b"], ["c"]]}):
        with pytest.raises(ValueError):
            cw.clean_figure(bad)
    steps = cw.clean_steps({"steps": ["a", "b"], "answer": "1", "figure": {"type": "table", "rows": [["1", "2"], ["3", "4"]]}})
    assert steps["figure"]["type"] == "table" and cw.public_params("steps", steps)["figure"] == steps["figure"]


def test_hundred_chart_page_preview_opens_in_the_plan_editor(tmp_path):
    """The 田字形百数表 figure draws an SVG arrow marker; that path must not crash the editor."""
    import subprocess

    dom = r'''
const assert=require('assert');
class E{
  constructor(tag,a){this.tag=tag;this.a=a||{};this.children=[];this.parentNode=null;this.value=String(this.a.value==null?'':this.a.value);this.checked=false;this.handlers={};this._text=this.a.text||'';this.scrolled=false;this.className='';this.attrs={}}
  appendChild(c){if(c.parentNode)c.parentNode.children=c.parentNode.children.filter(x=>x!==c);this.children.push(c);c.parentNode=this;if(this.tag==='select'&&!this.value)this.value=String(c.a.value==null?'':c.a.value);return c}
  insertBefore(c,b){if(c.parentNode)c.parentNode.children=c.parentNode.children.filter(x=>x!==c);let i=b?this.children.indexOf(b):-1;this.children.splice(i<0?this.children.length:i,0,c);c.parentNode=this;return c}
  get nextSibling(){if(!this.parentNode)return null;let i=this.parentNode.children.indexOf(this);return this.parentNode.children[i+1]||null}
  addEventListener(k,f){this.handlers[k]=f}
  setAttribute(k,v){this.attrs[k]=v}
  set textContent(v){this._text=v;this.children=[]}
  get textContent(){return this._text}
  scrollIntoView(){this.scrolled=true}
}
function el(tag,attrs){var n=new E(tag,attrs);Object.keys(attrs||{}).forEach(function(k){if(k==='class')n.className=attrs[k];else if(k==='text')n.textContent=attrs[k];else if(k.slice(0,2)==='on')n.addEventListener(k.slice(2),attrs[k]);else if(attrs[k]===true)n.setAttribute(k,'');else if(attrs[k]!==false&&attrs[k]!=null)n.setAttribute(k,attrs[k])});for(var i=2;i<arguments.length;i++){var c=arguments[i];if(c==null)continue;n.appendChild(typeof c==='string'?new E('#text',{text:c}):c)}return n}
var document={createElement:function(t){return new E(t,{})},createElementNS:function(ns,t){var n=new E(t,{});if(t==='svg')n.createSVGRect=function(){return {}};return n},getElementById:function(){return null}};
var window={},sessionStorage={getItem:function(){return 'x'}},requestAnimationFrame=function(f){return f()},confirm=function(){return true},prompt=function(){return null};
function all(e){return [e].concat(e.children.reduce(function(out,c){return out.concat(c instanceof E?all(c):[])},[]))}
function find(e,text){return all(e).find(function(x){return x.tag==='button'&&x.a.text===text})}
var payload={lessonId:10,subject:'数学',templates:['rotation','clock','steps','reading'],kindLabels:{rotation:'图形旋转',clock:'时钟旋转',steps:'分步讲解',reading:'阅读分析'},hasSource:true,
  items:[{stage:3,page:11,kind:'steps',status:'draft',params:{title:'田字形百数表',problem:'“田”字形方格 百数表中，四格用 n、m 表示。',steps:['同行向右+1，同列向下+10。','四数和为 4n+22。'],answer:'4n+22',figure:{type:'hundred_chart_square',topLeftNumber:45},sourceFigure:{}},approved:null,writtenTask:false,templateId:null,pageText:'',updatedAt:''}],
  pages:{'2':[],'3':['第1题','第2题','第3题','第4题','第5题','第6题','第7题','第8题','第9题','第10题','第11题','第12题 “田”字形方格 百数表中，“田”字形四格左上角的数用 n 表示。']}};
function api(){return Promise.resolve(payload)}
'''
    exercise = r'''
(async function(){
  var root=new E('div');
  cwPlan(root,10,null);
  await new Promise(function(r){setTimeout(r,30)});
  var open=find(root,'预览／修改');
  assert(open,'preview button is rendered');
  open.a.onclick();
  await new Promise(function(r){setTimeout(r,30)});
  var notes=all(root).filter(function(x){return x.a&&x.a.role==='status'}).map(function(x){return x.textContent}).filter(Boolean);
  assert(!notes.some(function(t){return t.indexOf('预览打开失败')>=0}),notes.join('|'));
  var nodes=all(root);
  assert(nodes.some(function(x){return String(x.textContent||'').indexOf('百数表：同行向右')>=0}),'hundred chart preview is drawn');
  assert(nodes.some(function(x){return x.tag==='marker'&&x.attrs.id==='cw-hundred-arrow'}),'arrow marker is created');
  console.log('OK');
})().catch(function(e){console.error(e);process.exit(1)});
'''
    script = tmp_path / 'hundred_chart_preview.js'
    script.write_text(dom + COURSEWARE_JS + COURSEWARE_PLAN_JS + exercise, encoding='utf-8')
    result = subprocess.run(['node', str(script)], capture_output=True, text=True, encoding='utf-8', timeout=30)
    assert result.returncode == 0, result.stderr
    assert 'OK' in result.stdout


def test_three_by_three_grid_shows_all_nine_numbers_at_first_step(tmp_path):
    """The 3×3 number grid is the question condition: every cell must be visible from step 1."""
    import subprocess

    dom = r'''
const assert=require('assert');
class E{
  constructor(tag,a){this.tag=tag;this.a=a||{};this.children=[];this.parentNode=null;this._text=this.a.text||''}
  appendChild(c){this.children.push(c);c.parentNode=this;return c}
}
function el(tag,attrs){var n=new E(tag,attrs);Object.keys(attrs||{}).forEach(function(k){if(k==='text')n.textContent=attrs[k];else if(k==='style')n.style=attrs[k]});for(var i=2;i<arguments.length;i++){var c=arguments[i];if(c==null)continue;n.appendChild(typeof c==='string'?new E('#text',{text:c}):c)}return n}
var document={createElement:function(t){return new E(t,{})}};
function all(e){return [e].concat(e.children.reduce(function(out,c){return out.concat(c instanceof E?all(c):[])},[]))}
'''
    exercise = r'''
var rows=[["a−11","a−10","a−9"],["a−1","a","a+1"],["a+9","a+10","a+11"]];
function nodes(reveal){var box=new E('div');cwFigure(box,{type:'table',reveal:reveal,rows:rows},false,{step:1,previewMode:true},true,4);
  return all(box).filter(function(x){return x.tag==='td'||x.tag==='th'})}
var fullNodes=nodes(false),full=fullNodes.map(function(x){return x.textContent}).join('|');
assert(full.indexOf('a+1')>=0&&full.indexOf('a+11')>=0,'all nine numbers are visible');
assert(full.indexOf('·')<0,'no hidden cell at step 1');
assert(fullNodes.every(function(x){return String(x.style||'').indexOf('#dbeafe')<0}),'no column highlight when all cells are shown');
var partial=nodes(undefined).map(function(x){return x.textContent}).join('|');
assert(partial.indexOf('·')>=0,'tables without the flag still reveal by step');
console.log('OK');
'''
    script = tmp_path / 'three_by_three_table.js'
    script.write_text(dom + COURSEWARE_JS + exercise, encoding='utf-8')
    result = subprocess.run(['node', str(script)], capture_output=True, text=True, encoding='utf-8', timeout=30)
    assert result.returncode == 0, result.stderr
    assert 'OK' in result.stdout


def test_page_code_draws_figures_without_markup_and_answers_on_the_row():
    for t in ("function cwFigure(", "cwFigureText", "createSVGRect"):
        assert t in COURSEWARE_JS, t
    assert "innerHTML" not in COURSEWARE_JS and "innerHTML" not in COURSEWARE_PLAN_JS
    for t in ("生成中…", "notes[String(x.page)]", "正在处理另一页", "figType", "线段和点", "计算程序图"):
        assert t in COURSEWARE_PLAN_JS, t


FLOW = r'''
with TestClient(app) as client:
    th, sh, sid, school_id = setup(client)
    examples = [{"title": "例题13 | 中点问题", "question": "点B是线段AD上的一个动点，点C、E分别是线段BD、AB的中点，线段EC的长度会变化吗？", "answer": "不变，EC=AD的一半"},
                {"title": "例题11 | 顺推与逆推", "question": "输入一个数→除以0.5→加b→输出。输入数a时，输出的数是（ ）。", "answer": "2a+b"}]
    with legacy.SessionLocal() as db:
        p = db.scalar(select(legacy.TeachingProgram).where(legacy.TeachingProgram.school_id == school_id))
        math = legacy.TeachingLesson(school_id=school_id, program_id=p.id, subject="数学", lesson_no=95, title="分层综合提升",
                                     core_target="整体思想", teacher_plan="讲例题", examples_json=json.dumps(examples, ensure_ascii=False))
        db.add(math); db.commit(); mid = math.id
    base = f"/teacher/weekend/lessons/{mid}/courseware"
    seg = {"type": "segment", "points": [{"name": "A", "at": 0}, {"name": "E", "at": 3}, {"name": "B", "at": 6}, {"name": "C", "at": 8},
                                          {"name": "D", "at": 10}], "marks": [{"from": "A", "to": "D", "label": "L"}]}
    replies.append(json.dumps({"template": "steps", "title": "中点问题", "problem": "线段EC的长度会变化吗？", "steps": ["EB=AB的一半", "BC=BD的一半", "EC=AD的一半"],
                               "answer": "不变", "figure": seg}, ensure_ascii=False))
    d = client.post(base + "/generate", headers=th, json={"stageNo": 3, "page": 0}).json()
    item = next(i for i in d["items"] if i["page"] == 0)
    assert item["kind"] == "steps" and item["params"]["figure"] == seg and not d["notice"]
    assert '"type":"segment"' in prompts[-1] and '"type":"flow"' in prompts[-1] and "只画已知条件" in prompts[-1]
    # A figure that fails the checks is dropped; the worked example itself is kept, and the teacher is told.
    replies.append(json.dumps({"template": "steps", "title": "程序", "steps": ["a÷0.5=2a", "再加b"], "answer": "2a+b",
                               "figure": {"type": "flow", "boxes": ["只有一个框"]}}, ensure_ascii=False))
    d = client.post(base + "/generate", headers=th, json={"stageNo": 3, "page": 1}).json()
    item = next(i for i in d["items"] if i["page"] == 1)
    assert item["params"]["figure"] == {} and "AI 画的图示没有通过校验" in d["notice"]
    if item["params"].get("sourceFigure"):
        assert "原题图片保留为对照" in d["notice"]
    # The teacher explicitly adds the reviewed segment to the first page.
    first = next(i for i in d['items'] if i['page'] == 0)
    r = client.put(base, headers=th, json={'stageNo':3,'page':0,'kind':'steps','params':{**first['params'],'figure':seg}})
    assert r.status_code == 200, r.text
    # The teacher draws it in the editor (PUT): checked the same way.
    flow = {"type": "flow", "boxes": ["输入 a", "÷ 0.5", "+ b", "输出"]}
    bad = client.put(base, headers=th, json={"stageNo": 3, "page": 1, "kind": "steps", "params": {**item["params"], "figure": {"type": "flow", "boxes": []}}})
    assert bad.status_code == 400 and "程序图" in bad.json()["detail"]
    d = client.put(base, headers=th, json={"stageNo": 3, "page": 1, "kind": "steps", "params": {**item["params"], "figure": flow}}).json()
    assert next(i for i in d["items"] if i["page"] == 1)["params"]["figure"]["boxes"] == flow["boxes"]
    # Approved, the figure reaches the big screen with the page.
    for i in (0, 1):
        assert client.post(base + "/approve", headers=th, json={"stageNo": 3, "page": i}).status_code == 200
    with legacy.SessionLocal() as db:
        teacher = db.scalar(select(legacy.User).where(legacy.User.username == "teacher1"))
        cls = legacy.SchoolClass(school_id=school_id, name="周末五年级", grade=5, teacher_id=teacher.id); db.add(cls); db.flush()
        db.add(legacy.ClassStudent(class_id=cls.id, student_id=sid)); db.commit(); cls_id = cls.id
    s = client.post("/teacher/weekend/sessions", headers=th, json={"lessonId": mid, "classId": cls_id}).json()["id"]
    client.post(f"/teacher/weekend/sessions/{s}/start", headers=th); client.post(f"/teacher/weekend/sessions/{s}/goto", headers=th, json={"stage": 3})
    board = client.get(f"/teacher/weekend/sessions/{s}/board", headers=th).json()
    assert board["courseware"]["params"]["figure"]["points"][1]["name"] == "E" and "reference" not in board["courseware"]["params"]
    assert "cwFigure" in client.get("/v1/weekend-board").text and "figType" in client.get("/v1/weekend-plan").text
print("OK")
'''


def test_worked_example_figure_from_ai_to_the_big_screen(tmp_path):
    helpers.run_isolated(tmp_path, helpers.COMMON + FLOW)




def test_remaining_tenth_lesson_questions_get_matching_diagrams_and_explanations():
    questions = [
        ("月历“十”字框：若五数和是90", "calendar_cross"),
        ("说明月历十字框中最上与最下之和为何等于最左与最右之和", "calendar_cross"),
        ("3×3方框圈九个数，中心数为a，九数和是多少", "table"),
        ("月历框形辨析：哪一种错误？", "calendar_compare"),
        ("正方形边长a、长方形长a宽b，求周长和面积公式", "table"),
        ("地砖排列：第1幅5块白地砖4块蓝地砖，第2幅8块白地砖7块蓝地砖", "tile_pattern"),
        ("当a=5、b=3，求a+b²；小明算成5+6", "flow"),
        ("2个大正方形和3个小正方形拼成长方形，求关系和周长", "table"),
        ("跑道周长s米，丽丽每分钟跑180米，丙丙每分钟跑140米，多久超过一圈", "running_track"),
        ("三角形数1、3、6、10、15，第10个是多少", "triangular_numbers"),
        ("黑白棋子按层排成三角形，黑棋子比白棋子多m颗", "alternating_triangle"),
    ]
    for question, expected in questions:
        assert required_visual_type(question) == expected, question
        figure = required_visual_figure(question)
        assert figure.get("type") == expected, question
        repaired = _repair_courseware_visual({"figure": {}, "steps": ["(第1步，点下一步显示)"]}, question)
        assert repaired["figure"] == figure
        assert len(repaired["steps"]) >= 4
        assert not any("点下一步显示" in step for step in repaired["steps"])
    assert ".item{display:flex;flex-wrap:wrap;" in PAGE_CSS
    assert ".item>button{flex:0 0 auto;min-width:68px" in PAGE_CSS

def test_calendar_comparison_is_answer_free_and_keeps_four_shapes():
    question = "月历框形辨析：哪一种错误？"
    figure = required_visual_figure(question)
    assert figure == {"type": "calendar_compare"}
    assert cw.clean_figure(figure) == figure
    repaired = _repair_courseware_visual({"figure": {}, "steps": ["旧步骤"], "answer": "C"}, question)
    assert repaired["figure"] == figure
    assert len(repaired["steps"]) == 4
    assert all("C错误" not in s and "选项C写成" not in s for s in repaired["steps"])
    assert "function cwCalendarCompare(" in COURSEWARE_JS
    assert "view.calendarChoice" in COURSEWARE_JS

def test_calendar_choice_is_validated_and_survives_teacher_screen_state():
    params = cw.clean_steps({
        "title": "月历框形辨析", "problem": "哪一种错误？",
        "steps": ["先观察", "再比较", "自己表达", "独立判断"],
        "answer": "C", "figure": {"type": "calendar_compare"}
    })
    assert cw.clean_view("steps", params, {"calendarChoice": "D", "calendarFeedback": True})["calendarChoice"] == "D"
    assert cw.clean_view("steps", params, {"calendarChoice": "invalid"})["calendarChoice"] == "A"
    assert cw.clean_view("steps", params, {"calendarChoice": "B", "calendarFeedback": True})["calendarFeedback"]
    assert "view._calendarOnChange=send" in COURSEWARE_JS
    assert "if(view._calendarOnChange)view._calendarOnChange()" in COURSEWARE_JS
