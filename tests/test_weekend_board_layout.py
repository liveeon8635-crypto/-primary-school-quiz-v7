from __future__ import annotations

import json
import shutil
import subprocess

import pytest

from changying.web.weekend_pages import BOARD_JS, BOARD_LAYOUT_JS, board_page_html

TEXT = ("课题：用字母表示数和数量关系\n考点一：省略乘号的四条规则\n数与字母相乘，乘号省略，数写在字母前面：5×m＝5m，8×a×b＝8ab。\n"
        "1与字母相乘，1不写：a×1＝a，1×b＝b。\n易错：2a表示a＋a，a²表示a×a。\n"
        "示例：例题1 | 省略乘号：5×m＝（　　　）　a×1＝（　　　）　b×7.8＝（　　　）　还要说出理由。")

NODE = r'''
function el(tag,attrs,...kids){const n={tag,attrs:attrs||{},children:[],style:{},appendChild(c){if(c)this.children.push(c);return c}};kids.forEach(k=>n.appendChild(k));return n}
function all(n){return [n,...n.children.flatMap(all)]}
''' + BOARD_LAYOUT_JS + r'''
const blocks=blParse([TEXT]);
const body=el('div');const wide=boardLayout(body,[TEXT],true);const narrow=boardLayout(el('div'),[TEXT],false);
const texts=all(body).map(n=>n.attrs.text).filter(Boolean);
console.log(JSON.stringify({blocks:blocks.map(b=>[b.kind,b.title,b.lines.length]),items:blItems(blocks[2].lines[0]),wide,narrow,
  grid:all(body).some(n=>(n.attrs.style||'').includes('grid-template-columns:1fr 1fr')),
  warn:texts.filter(t=>t.startsWith('⚠')),numbers:texts.filter(t=>/^[0-9]$/.test(t)),cyan:all(body).filter(n=>(n.attrs.style||'').includes('#7dd3fc')).map(n=>n.attrs.text),
  plainItems:blItems('没有空括号的一句话')}));
'''


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_board_layout_separates_points_rules_examples_and_warnings():
    out = subprocess.run(["node", "-e", f"const TEXT={json.dumps(TEXT, ensure_ascii=False)};" + NODE], capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, out.stderr
    r = json.loads(out.stdout)
    assert r["blocks"] == [["plain", "", 1], ["know", "考点一　省略乘号的四条规则", 3], ["example", "例题1　省略乘号", 1]]
    # One item per blank: a question never breaks in the middle; text after the last blank stays as text.
    assert r["items"] == {"lead": "", "items": ["5×m＝", "a×1＝", "b×7.8＝"], "tail": "还要说出理由。"}
    assert r["plainItems"] is None
    assert r["wide"] == {"know": 1, "examples": 1} and r["grid"] is True
    assert r["warn"] == ["⚠ 易错：2a表示a＋a，a²表示a×a。"] and r["numbers"] == ["1", "2"]
    assert r["cyan"] == ["5×m＝5m，8×a×b＝8ab。", "a×1＝a，1×b＝b。"]


def test_board_page_uses_the_layout_and_draws_text_only():
    assert "boardLayout(body,d.content" in BOARD_JS and "boardLayout(top,topContent,false)" in BOARD_JS
    assert "innerHTML" not in BOARD_LAYOUT_JS and "insertAdjacentHTML" not in BOARD_LAYOUT_JS
    html = board_page_html()
    assert "function boardLayout(" in html and html.index("function boardLayout(") < html.index("function board(")


ROUTE = r'''
with TestClient(app) as client:
    page = client.get("/v1/weekend-board")
    assert page.status_code == 200 and "function boardLayout(" in page.text and "boardLayout(body,d.content" in page.text
    plan = client.get("/v1/weekend-plan").text
    assert "function startReason(" in plan and "data-start-reason" in plan
print("OK")
'''


def test_board_route_serves_the_layout(tmp_path):
    import importlib.util
    import sys
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location("weekend_board_layout_helpers", root / "tests" / "test_homework_solve.py")
    helpers = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = helpers
    spec.loader.exec_module(helpers)
    helpers.run_isolated(tmp_path, helpers.COMMON + ROUTE)


CASE2 = ("考点二：代入求值\n四步走：写式子（或抄原式）；把字母换成数，并把省略的乘号补回来：a＝2.5时，1.2a就是1.2×2.5；按先乘除后加减的顺序算出结果；结果带单位：长度用cm。\n"
         "示例：例题2 | 代值计算：（1）当a＝2.5时，求下面各式的值：5×a＝（　　）　1.2a＝（　　）　9－a＝（　　）　a÷4＝（　　）；"
         "（2）当a＝7.5、b＝2.5时，求4a＋b的值；（3）已知n＝m÷4，当n＝24时，m等于多少？")

NODE2 = r'''
function el(tag,attrs,...kids){const n={tag,attrs:attrs||{},children:[],style:{},appendChild(c){if(c)this.children.push(c);return c}};kids.forEach(k=>n.appendChild(k));return n}
function all(n){return [n,...n.children.flatMap(all)]}
''' + BOARD_LAYOUT_JS + r'''
const body=el('div');boardLayout(body,[TEXT],true);const nodes=all(body);
const line=blParse([TEXT])[1].lines[0];
console.log(JSON.stringify({parts:blParts(line),first:blItems(blParts(line)[0]),sentence:blItems('小明说：一个数的（　）倍等于这个数加上（　）。'),
  steps:nodes.map(n=>n.attrs.text).filter(t=>t&&t.startsWith('· ')),
  nowrapLong:nodes.filter(n=>(n.attrs.style||'').includes('white-space:nowrap')).map(n=>n.children.map(c=>c.attrs.text||'').join('')).filter(t=>t.length>14)}));
'''


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_sub_questions_and_long_rules_do_not_overlap():
    out = subprocess.run(["node", "-e", f"const TEXT={json.dumps(CASE2, ensure_ascii=False)};" + NODE2], capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, out.stderr
    r = json.loads(out.stdout)
    # （1）（2）（3） each start a row; the lead-in stays text; only the four short calculations go in the grid.
    assert [p[:3] for p in r["parts"]] == ["（1）", "（2）", "（3）"]
    assert r["first"] == {"lead": "（1）当a＝2.5时，求下面各式的值：", "items": ["5×a＝", "1.2a＝", "9－a＝", "a÷4＝"], "tail": ""}
    assert r["sentence"] is None                       # a sentence with blanks wraps as text, never in a no-wrap cell
    assert r["nowrapLong"] == []
    assert r["steps"] == ["· 写式子（或抄原式）", "· 把字母换成数，并把省略的乘号补回来：a＝2.5时，1.2a就是1.2×2.5",
                          "· 按先乘除后加减的顺序算出结果", "· 结果带单位：长度用cm"]


CASE3 = ("考点三：用字母表示运算定律和公式\n加法交换律：a＋b＝b＋a；加法结合律：（a＋b）＋c＝a＋（b＋c）；乘法交换律：a×b＝b×a。\n"
         "示例：例题13 | 中点问题（整体思想）：点B是线段AD上的一个动点，可以在AD上任意移动。")

NODE3 = r'''
function el(tag,attrs,...kids){const n={tag,attrs:attrs||{},children:[],style:{},appendChild(c){if(c)this.children.push(c);return c}};kids.forEach(k=>n.appendChild(k));return n}
function all(n){return [n,...n.children.flatMap(all)]}
''' + BOARD_LAYOUT_JS + r'''
const body=el('div');boardLayout(body,[TEXT],true);const texts=all(body).map(n=>n.attrs.text).filter(Boolean);
const b=blParse([TEXT]);
console.log(JSON.stringify({numbers:texts.filter(t=>/^[0-9]$/.test(t)),title:b[1].title,line:b[1].lines[0]}));
'''


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_law_lists_number_each_law_and_long_example_titles_are_cut():
    out = subprocess.run(["node", "-e", f"const TEXT={json.dumps(CASE3, ensure_ascii=False)};" + NODE3], capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, out.stderr
    r = json.loads(out.stdout)
    assert r["numbers"] == ["1", "2", "3"]                                # one numbered rule per law
    assert r["title"] == "例题13　中点问题（整体思想）" and r["line"].startswith("点B是线段AD上")


def test_board_picks_side_by_side_or_stacked_by_text_size():
    assert "var two=laid(true),one=laid(false);if(two>=one)laid(true)" in BOARD_JS
    assert "window.blRefit=function(){fitText(body)}" in BOARD_JS and "window.blRefit()" in BOARD_LAYOUT_JS


CASE4 = "例题1 | 省略乘号\n写出下面各式的结果：5×m＝（　　）　a×1＝（　　）　b×7.8＝（　　）\n参考答案：5m；a；7.8b"

CASE_BRACKET_ANSWER = "一个梯形上底5厘米、下底7厘米、高5厘米，求面积。\n【答案】30平方厘米，两个相同梯形拼合后面积减半。"

NODE4 = r'''
var window={};
function el(tag,attrs,...kids){const n={tag,attrs:attrs||{},children:[],style:{},appendChild(c){if(c)this.children.push(c);return c}};
  if(attrs&&attrs.style)attrs.style.split(';').forEach(d=>{const [k,v]=d.split(':');if(k==='display')n.style.display=v});kids.forEach(k=>n.appendChild(k));return n}
function all(n){return [n,...n.children.flatMap(all)]}
''' + BOARD_LAYOUT_JS + r'''
function paint(){const body=el('div');boardLayout(body,[TEXT],true);return all(body)}
let nodes=paint();const answer=()=>nodes.find(n=>n.attrs.text&&n.attrs.text.startsWith('参考答案'));const btn=()=>nodes.find(n=>n.tag==='button');
const before={hidden:answer().style.display==='none',label:btn().attrs.text};
btn().attrs.onclick();const clicked={hidden:answer().style.display==='none'};
nodes=paint();const repaint={hidden:answer().style.display==='none',label:btn().attrs.text};
console.log(JSON.stringify({before,clicked,repaint}));
'''


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_answers_stay_covered_until_the_teacher_shows_them():
    out = subprocess.run(["node", "-e", f"const TEXT={json.dumps(CASE4, ensure_ascii=False)};" + NODE4], capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, out.stderr
    r = json.loads(out.stdout)
    assert r["before"] == {"hidden": True, "label": "显示答案"}
    assert r["clicked"] == {"hidden": False}
    assert r["repaint"] == {"hidden": False, "label": "隐藏答案"}        # the 3-second refresh keeps it open


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_bracketed_answer_is_covered_for_imported_markdown_example():
    harness = NODE4.replace("startsWith('参考答案')", "startsWith('【答案】')")
    out = subprocess.run(["node", "-e", f"const TEXT={json.dumps(CASE_BRACKET_ANSWER, ensure_ascii=False)};" + harness], capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, out.stderr
    result = json.loads(out.stdout)
    assert result['before'] == {'hidden': True, 'label': '显示答案'}
    assert result['clicked']['hidden'] is False


CASE5 = "选择题 1：诊断题 3 | 选择（1）省略乘号，a×8×b 应写成（　　）\nA. 8ab\nB. ab8\n参考答案／评分要点：8ab"

NODE5 = r'''
var window={};
function el(tag,attrs,...kids){const n={tag,attrs:attrs||{},children:[],style:{},appendChild(c){if(c)this.children.push(c);return c}};kids.forEach(k=>n.appendChild(k));return n}
function all(n){return [n,...n.children.flatMap(all)]}
''' + BOARD_LAYOUT_JS + r'''
function nodes(){const body=el('div');boardLayout(body,[TEXT],true);return all(body)}
BL_COVER=false;const released=nodes();BL_COVER=true;const explaining=nodes();
console.log(JSON.stringify({cyan:released.filter(n=>(n.attrs.style||'').includes('#7dd3fc')).length,
  releasedButtons:released.filter(n=>n.tag==='button').length,explainingButtons:explaining.filter(n=>n.tag==='button').length}));
'''


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_practice_questions_are_plain_and_released_answers_are_not_covered():
    out = subprocess.run(["node", "-e", f"const TEXT={json.dumps(CASE5, ensure_ascii=False)};" + NODE5], capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, out.stderr
    r = json.loads(out.stdout)
    assert r["cyan"] == 0                                   # "选择题 1：…" is not a rule with an example
    assert r["releasedButtons"] == 0 and r["explainingButtons"] == 1


def test_imported_option_letters_are_not_doubled():
    from changying.services.weekend_answers import option_text as _option
    assert [_option(x) for x in ("A．8ab", "b. ab8", "C、8ba", "D) a8b", "8ab", "Apple")] == ["8ab", "ab8", "8ba", "a8b", "8ab", "Apple"]
    assert "BL_COVER=d.currentStage===2||d.currentStage===3" in BOARD_JS


def test_board_poll_preserves_scroll_and_suppresses_duplicate_courseware_question(tmp_path):
    harness = r'''
const assert=require('assert');
class E{
  constructor(tag,attrs){this.tag=tag;this.attrs=attrs||{};this.children=[];this.style={};this.scrollTop=0;this.scrollHeight=900;this.clientHeight=300;this.scrollWidth=800;this.clientWidth=800}
  appendChild(node){this.children.push(node);return node}
  set textContent(value){this._text=String(value||'');this.children=[]}
  get textContent(){return this._text||''}
}
function el(tag,attrs,...children){const node=new E(tag,attrs);children.forEach(child=>node.appendChild(child));return node}
function find(node,predicate){if(predicate(node))return node;for(const child of node.children){const got=find(child,predicate);if(got)return got}return null}
const root=new E('div'),bodyElement=new E('body'),intervals=[],handlers={},layoutCalls=[],coursewareCalls=[];
const window={innerWidth:1200,innerHeight:800,addEventListener:(name,fn)=>{handlers[name]=fn}};
const document={body:bodyElement,activeElement:bodyElement,getElementById:id=>find(root,n=>n.attrs.id===id)};
E.prototype.focus=function(){document.activeElement=this};
const data={
 id:1,title:'数学课',status:'running',covered:false,currentStage:3,stageName:'例题讲解',goal:'观察原题',
 remainingSeconds:60,deck:{index:0,total:2},content:['第1题：请根据图示判断图形旋转后的方向和角度'],
 courseware:{id:7,kind:'steps',params:{title:'第1题：请根据图示判断图形旋转后的方向和角度',sourceProblem:'第1题：请根据图示判断图形旋转后的方向和角度',question:'第1题：请根据图示判断图形旋转后的方向和角度',steps:['先观察图形'],figure:{}},view:{step:1}}
};
let seconds=60;
function api(){return Promise.resolve(Object.assign({},data,{remainingSeconds:seconds--}))}
function setInterval(fn,ms){intervals.push({fn,ms});return intervals.length}
function requestAnimationFrame(fn){fn()}
function boot(fn){fn()}
function fmt(value){return String(value)}
function msg(value){root.textContent=value}
function boardLayout(box,content){layoutCalls.push((content||[]).slice());box.appendChild(el('div',{text:(content||[]).join('|')}))}
function cwRender(box){coursewareCalls.push(1);box.appendChild(el('div',{text:'互动图示'}))}
const source=__BOARD_JS__;
const makeBoard=new Function('URLSearchParams','location','document','window','el','root','api','setInterval','requestAnimationFrame','boot','fmt','boardLayout','cwRender','msg',source+';return board;');
makeBoard(URLSearchParams,{search:'?s=1'},document,window,el,root,api,setInterval,requestAnimationFrame,boot,fmt,boardLayout,cwRender,msg);
function scrollBody(){return find(root,n=>n.style&&n.style.overflow==='auto')}
async function flush(){await new Promise(resolve=>setImmediate(resolve))}
(async()=>{
 await flush();
 const wrap=root.children[0],firstBody=scrollBody();
 assert(firstBody,'courseware body must be scrollable');
 assert.equal(layoutCalls.length,0,'the same question stem must not be printed above the courseware twice');
 firstBody.scrollTop=123;
 firstBody.focus();
 intervals.find(x=>x.ms===3000).fn();
 await flush();
 assert.strictEqual(root.children[0],wrap,'the 3-second poll must not replace the screen wrapper');
 assert.strictEqual(scrollBody(),firstBody,'clock-only refresh must not recreate the scroll container');
 assert.equal(firstBody.scrollTop,123,'clock-only refresh must preserve the exact scroll position');
 data.courseware.view={step:2};
 intervals.find(x=>x.ms===3000).fn();
 await flush();
 const secondBody=scrollBody();
 assert.notStrictEqual(secondBody,firstBody,'a real courseware change should repaint');
 assert.equal(secondBody.scrollTop,123,'repainting the same page must preserve its scroll position');
 assert.strictEqual(document.activeElement,secondBody,'repainting the same page must restore keyboard focus');
 handlers.resize();
 const resizedBody=scrollBody();
 assert.equal(resizedBody.scrollTop,123,'resizing must preserve the same page scroll position');
 assert.strictEqual(document.activeElement,resizedBody,'resizing must restore keyboard focus');
 data.deck={index:1,total:2};data.content=['第2题：请根据新页面图示判断图形变化'];
 intervals.find(x=>x.ms===3000).fn();
 await flush();
 assert.equal(scrollBody().scrollTop,0,'moving to another slide must start at the top');
 assert.deepEqual(layoutCalls[layoutCalls.length-1],['第2题：请根据新页面图示判断图形变化']);
 data.deck={index:2,total:3};data.courseware.params.title='为什么？';data.courseware.params.question='为什么？';data.content=['为什么？'];
 intervals.find(x=>x.ms===3000).fn();
 await flush();
 assert.equal(layoutCalls.length,1,'an exact short question line must also be deduplicated');
 const reading='阅读材料：'+('请认真阅读这段材料并结合图示进行观察。'.repeat(20))+'请根据材料回答下面的问题';
 data.deck={index:3,total:4};data.courseware.params.title='阅读题';data.courseware.params.question='请根据材料回答下面的问题';data.courseware.params.sourceProblem='';data.content=[reading];
 intervals.find(x=>x.ms===3000).fn();
 await flush();
 assert.equal(layoutCalls.length,2,'a long reading passage containing the question must remain visible');
 assert.equal(layoutCalls[1][0],reading);
 assert(coursewareCalls.length>=3);
 console.log('OK');
})().catch(error=>{console.error(error);process.exitCode=1});
'''
    harness = harness.replace('__BOARD_JS__', json.dumps(BOARD_JS, ensure_ascii=False))
    out = subprocess.run(["node"], input=harness, capture_output=True, text=True, encoding="utf-8", timeout=30)
    assert out.returncode == 0, out.stdout + out.stderr
    assert "OK" in out.stdout


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_board_content_first_compact_topbar_and_wide_split():
    from changying.web.weekend_courseware_pages import COURSEWARE_JS

    html = board_page_html()
    assert "board-topbar" in html
    assert "cw-big-stage" in html
    assert "cw-big-focusbar" in html

    harness = (
        "function el(tag,attrs,...kids){const n={tag,attrs:attrs||{},children:[],style:{},appendChild(c){if(c)this.children.push(c);return c}};kids.forEach(k=>n.appendChild(k));return n}\n"
        "function all(n){return [n,...n.children.flatMap(all)]}\n"
        "global.window={innerWidth:1920,innerHeight:1080};\n"
        "global.document={createElementNS:null};\n"
        + COURSEWARE_JS
        + r"""
const p={
  title:'例1｜双梯形倍拼推导公式',
  steps:['第一步','第二步'],
  answer:'25 cm²',
  stepFigures:[
    {type:'uploaded_image',data_url:'data:image/jpeg;base64,/9j/2Q==',alt:'图0'},
    {type:'uploaded_image',data_url:'data:image/jpeg;base64,/9j/2Q==',alt:'图1'},
    {type:'uploaded_image',data_url:'data:image/jpeg;base64,/9j/2Q==',alt:'图2'}
  ]
};
const bigBox=el('div');cwSteps(bigBox,p,{step:1,showAnswer:true},true,false);
const bigNodes=all(bigBox);
const bigStage=bigNodes.find(n=>n.attrs.class==='cw-big-stage');
const bigFocus=bigNodes.find(n=>n.attrs.class==='cw-big-focusbar');
const bigImg=bigNodes.find(n=>n.tag==='img');
const smallBox=el('div');cwSteps(smallBox,p,{step:1,showAnswer:true},false,true);
const smallNodes=all(smallBox);
const smallFocus=smallNodes.find(n=>n.attrs.class==='cw-big-focusbar');
const smallImg=smallNodes.find(n=>n.tag==='img');
console.log(JSON.stringify({
  hasBigStage:!!bigStage,
  hasBigFocus:!!bigFocus,
  bigFullWidth:bigBox.children[0].attrs.style.includes('max-width:none'),
  bigImgFillsStage:bigImg.attrs.style.includes('height:100%;max-width:100%;max-height:100%')&&bigImg.attrs.style.includes('object-fit:contain'),
  hasSmallFocus:!!smallFocus,
  smallMax980:smallBox.children[0].attrs.style.includes('max-width:980px'),
  smallImgHeight300:smallImg.attrs.style.includes('max-height:300px')
}));
"""
    )
    out = subprocess.run(["node"], input=harness, capture_output=True, text=True, encoding="utf-8", timeout=30)
    assert out.returncode == 0, out.stdout + out.stderr
    res = json.loads(out.stdout)
    assert res == {
        "hasBigStage": True,
        "hasBigFocus": True,
        "bigFullWidth": True,
        "bigImgFillsStage": True,
        "hasSmallFocus": False,
        "smallMax980": True,
        "smallImgHeight300": True,
    }


def test_board_slide_audio_toggle_and_resize_do_not_rebuild_dom():
    harness = r'''
const assert=require('assert');
class E{
  constructor(tag,attrs){this.tag=tag;this.attrs=attrs||{};this.children=[];this.style={};this.scrollTop=0}
  appendChild(node){this.children.push(node);return node}
  set textContent(value){this._text=String(value||'');this.children=[]}
  get textContent(){return this._text||''}
  querySelector(sel){
    if(this.tag===sel)return this;
    for(const c of this.children){if(c&&c.querySelector){const hit=c.querySelector(sel);if(hit)return hit}}
    return null;
  }
}
function el(tag,attrs,...children){const node=new E(tag,attrs);children.forEach(child=>node.appendChild(child));return node}
function find(node,predicate){if(predicate(node))return node;for(const child of node.children){const got=find(child,predicate);if(got)return got}return null}
const root=new E('div'),bodyElement=new E('body'),intervals=[],handlers={};
const window={innerWidth:1280,innerHeight:800,addEventListener:(name,fn)=>{handlers[name]=fn}};
const document={body:bodyElement,activeElement:bodyElement,getElementById:id=>find(root,n=>n.attrs.id===id)};
let cwCalls=0,playCalls=0,pauseCalls=0;
const data={
  id:1,title:'语文第12课',status:'running',covered:false,currentStage:2,stageName:'短文阅读',goal:'精读',
  remainingSeconds:900,content:['图文幻灯片'],
  courseware:{id:9,kind:'slide',kindLabel:'图文幻灯片',stageNo:2,page:0,
    params:{title:'短文',slides:[{heading:'第1页',audioUrl:'data:audio/mpeg;base64,SUQz'},{heading:'第2页'}]},
    view:{slideIndex:0,audioPlaying:false}}
};
function api(){return Promise.resolve(JSON.parse(JSON.stringify(data)))}
function setInterval(fn,ms){intervals.push({fn,ms});return intervals.length}
function requestAnimationFrame(fn){fn()}
function boot(fn){fn()}
function fmt(v){return String(v)}
function msg(v){root.textContent=v}
function boardLayout(box,c){box.appendChild(el('div',{text:(c||[]).join('|')}))}
function cwRender(box){
  cwCalls++;
  const au=el('audio',{});
  au.play=function(){playCalls++;return Promise.resolve()};
  au.pause=function(){pauseCalls++};
  box.appendChild(au);
}
const source=__BOARD_JS__;
const makeBoard=new Function('URLSearchParams','location','document','window','el','root','api','setInterval','requestAnimationFrame','boot','fmt','boardLayout','cwRender','msg',source+';return board;');
makeBoard(URLSearchParams,{search:'?s=1'},document,window,el,root,api,setInterval,requestAnimationFrame,boot,fmt,boardLayout,cwRender,msg);
function scrollBody(){return find(root,n=>n.style&&n.style.overflow==='auto')}
async function flush(){await new Promise(resolve=>setImmediate(resolve))}
(async()=>{
  await flush();
  assert.equal(cwCalls,1);
  const firstBody=scrollBody();
  data.courseware.view.audioPlaying=true;
  intervals.find(x=>x.ms===3000).fn();
  await flush();
  assert.equal(cwCalls,1,'toggling audioPlaying on slide must NOT rebuild DOM');
  assert.strictEqual(scrollBody(),firstBody);
  assert.equal(playCalls,1);
  data.courseware.view.audioPlaying=false;
  intervals.find(x=>x.ms===3000).fn();
  await flush();
  assert.equal(cwCalls,1,'pausing audioPlaying on slide must NOT rebuild DOM');
  assert.equal(pauseCalls,1);
  handlers.resize();
  assert.equal(cwCalls,1,'resize on slide courseware must NOT rebuild DOM');
  assert.strictEqual(scrollBody(),firstBody);
  data.courseware.view.slideIndex=1;
  intervals.find(x=>x.ms===3000).fn();
  await flush();
  assert.equal(cwCalls,2,'changing slideIndex MUST repaint');
  console.log('OK');
})().catch(e=>{console.error(e);process.exitCode=1});
'''
    harness = harness.replace('__BOARD_JS__', json.dumps(BOARD_JS, ensure_ascii=False))
    out = subprocess.run(["node"], input=harness, capture_output=True, text=True, encoding="utf-8", timeout=30)
    assert out.returncode == 0, out.stdout + out.stderr
    assert "OK" in out.stdout
