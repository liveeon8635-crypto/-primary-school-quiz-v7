"""前端契约：步骤展开、预览兜底、六类图示渲染（只读源码与结构断言，不连数据库）。

这些用例守的是老师在周末课件页面看到的东西：
- 没展开的步骤只留“第 N 步”，不再出现“点下一步显示”这类字幕；
- 上一步／下一步／重来／答案四个按钮互不串状态；
- 任何图示字段缺失都只给一句人话，不白屏；
- 钝角三角形的高、方桌、地砖、百数表、环形跑道都真的画出来；
- 预览打不开时能看见原因，并且有“重试”。
"""
from __future__ import annotations

import json
import re
import subprocess

from changying.web.weekend_courseware_pages import COURSEWARE_JS, COURSEWARE_PLAN_JS


def _func(js: str, name: str, next_name: str) -> str:
    """截取一个函数的源码（从 function name( 到下一个 function next_name( 之前）。"""
    start = js.index('function ' + name + '(')
    end = js.index('function ' + next_name + '(', start)
    return js[start:end]


def _steps_branch(js: str) -> str:
    """截取 cwControl 里 c.kind==='steps' 的分支。"""
    start = js.index("var sp=c.params||{}")
    end = js.index('}else{', start)
    return js[start:end]


def _node(source: str) -> subprocess.CompletedProcess:
    """把脚本从标准输入交给 node 跑，不落临时文件（Windows 上也没路径问题）。"""
    return subprocess.run(['node', '-'], input=source, capture_output=True, text=True, encoding='utf-8', timeout=60)


DOM = r'''
const assert=require('assert');
class E{
  constructor(tag,a){this.tag=tag;this.a=a||{};this.children=[];this.parentNode=null;this.style={};this.attrs={};
    this._text=a&&a.text!=null?String(a.text):'';this.handlers={};this.value='';this.disabled=false;this.checked=false;this.className='';}
  appendChild(c){if(c&&c.parentNode)c.parentNode.children=c.parentNode.children.filter(function(x){return x!==c});this.children.push(c);if(c)c.parentNode=this;return c}
  insertBefore(c,b){if(c&&c.parentNode)c.parentNode.children=c.parentNode.children.filter(function(x){return x!==c});var i=b?this.children.indexOf(b):-1;this.children.splice(i<0?this.children.length:i,0,c);c.parentNode=this;return c}
  addEventListener(k,f){this.handlers[k]=f}
  setAttribute(k,v){this.attrs[k]=v}
  getAttribute(k){return this.attrs[k]}
  set textContent(v){this._text=v;this.children=[]}
  get textContent(){return this._text}
  scrollIntoView(){}
  querySelector(){return null}
  closest(){return null}
}
function el(tag,attrs){var n=new E(tag,attrs);Object.keys(attrs||{}).forEach(function(k){
  if(k==='class')n.className=attrs[k];
  else if(k==='text')n.textContent=attrs[k];
  else if(k.slice(0,2)==='on')n.addEventListener(k.slice(2),attrs[k]);
  else if(attrs[k]===true)n.setAttribute(k,'');
  else if(attrs[k]!==false&&attrs[k]!=null)n.setAttribute(k,attrs[k]);});
  for(var i=2;i<arguments.length;i++){var c=arguments[i];if(c==null)continue;n.appendChild(typeof c==='string'?new E('#text',{text:c}):c)}return n}
var document={createElement:function(t){return new E(t,{})},
  createElementNS:function(ns,t){var n=new E(t,{});if(t==='svg')n.createSVGRect=function(){return {}};return n},
  getElementById:function(){return null},addEventListener:function(){}};
var window={addEventListener:function(){}};
function all(e){return [e].concat(e.children.reduce(function(out,c){return out.concat(c instanceof E?all(c):[])},[]))}
function textOf(e){return all(e).map(function(x){return typeof x.textContent==='string'?x.textContent:''}).join('|')}
'''


def test_steps_collapsed_lines_never_show_the_placeholder_caption():
    """没展开的步骤只显示“第 N 步”，不能出现“（第 N 步，点下一步显示）”字幕。"""
    assert '\u70b9\u201c\u4e0b\u4e00\u6b65\u201d\u663e\u793a' not in COURSEWARE_JS  # 点“下一步”显示
    assert "点下一步显示" not in COURSEWARE_JS
    src = _func(COURSEWARE_JS, 'cwSteps', 'cwClock')
    # 折叠只留一行灰字；展开后显示真实步骤文本。
    assert "'第 '+(i+1)+' 步'" in src
    assert 'color:#98a2b3' in src
    # 新题从第 0 步开始，预览和课堂同一套规则。
    assert 'view.step||0' in src and 'previewMode' in src
    assert '\u5df2\u5c55\u5f00 ' in src  # 已展开 k / N 步


def test_next_previous_and_reset_move_their_own_state_only():
    """下一步只 +1，上一步只 -1，重来把 step 归 0 并收起答案。"""
    branch = _steps_branch(COURSEWARE_JS)
    assert 'Math.min(slen,stepNow()+1)' in branch
    assert 'Math.max(0,stepNow()-1)' in branch
    assert 'view.step=0;view.showAnswer=false' in branch
    # 答案按钮只动 showAnswer，不许顺手改 step。
    assert 'view.showAnswer=!view.showAnswer' in branch
    assert 'view.step' not in branch[branch.index('view.showAnswer=!view.showAnswer'):branch.index('view.showAnswer=!view.showAnswer') + 80]


def test_step_buttons_carry_progress_and_disable_at_the_edges():
    """按钮文案带当前进度，到边界要 disabled。"""
    branch = _steps_branch(COURSEWARE_JS)
    assert 'nextBtn.textContent=' in branch and "'/'+slen" in branch
    assert 'prevBtn.disabled=' in branch and 'nextBtn.disabled=' in branch
    assert 'syncSteps' in COURSEWARE_JS


def test_answer_is_independent_of_the_step_counter():
    """答案只跟 showAnswer（或老师全展开）走，不跟 step 联动。"""
    src = _func(COURSEWARE_JS, 'cwSteps', 'cwClock')
    assert 'answerVisible' in src
    assert 'view.showAnswer' in src
    assert 'teacher&&!view.previewMode' in src
    # 答案行不再出现在 shown>=steps.length 的条件里。
    assert 'shown>=steps.length' not in src


def test_figure_text_survives_every_missing_field():
    """任何字段缺失都只给一句读得懂的话，绝不抛异常。"""
    src = _func(COURSEWARE_JS, 'cwFigureText', 'cwFigureOk')
    assert 'f=f||{}' in src
    for field in ('points', 'marks', 'boxes', 'branches', 'sampleCounts',
                  'whiteCounts', 'blueCounts', 'terms', 'rows', 'labels'):
        assert 'f.' + field + '||' in src, field
    assert 'f.labels||{}' in src


def test_obtuse_triangle_height_draws_base_extension_altitude_and_foot():
    """钝角三角形：底边水平、延长线虚线、高垂直、垂足有直角小方块、三处标注。"""
    src = _func(COURSEWARE_JS, 'cwObtuseTriangleHeight', 'cwFigure')
    assert src
    assert 'polygon' in src                      # 三角形本体
    assert 'stroke-dasharray' in src             # 延长线与高都是虚线
    assert 'F.x+14' in src and 'F.y-14' in src   # 垂足直角小方块
    assert '底 BC = ' in src and '边 AC = ' in src and '高 = ' in src
    assert 'base*height/2' in src                # 面积 = 底 × 高 ÷ 2
    assert 'step>=2' in src and 'step>=3' in src and 'step>=4' in src and 'step>=5' in src
    # 分派要接到 cwFigure 里，否则老师永远看不到这张图。
    assert "if(f.type==='obtuse_triangle_height'){cwObtuseTriangleHeight(" in COURSEWARE_JS


def test_obtuse_triangle_height_requires_positive_values():
    """底、斜边、高都必须是正数，缺一个就不画。"""
    src = _func(COURSEWARE_JS, 'cwFigureOk', 'cwSeatingPattern')
    assert "f.type==='obtuse_triangle_height'" in src
    assert 'f.base>0' in src and 'f.side>0' in src and 'f.height>0' in src


def test_square_tables_are_rectangles_not_circles():
    """方桌用矩形画；圆／椭圆不能当桌子。"""
    src = _func(COURSEWARE_JS, 'cwSeatingPattern', 'cwAlternatingTriangle')
    assert "cwNode('rect'" in src
    assert "cwNode('circle'" not in src
    assert "cwNode('ellipse'" not in src


def test_tile_pattern_has_a_white_row_and_a_blue_column():
    """白砖横排（x 递增）、蓝砖竖列（y 递减），两段都用 rect。"""
    src = _func(COURSEWARE_JS, 'cwTilePattern', 'cwSquareSticksPattern')
    assert 'x:x+i*unit' in src
    assert 'y:base-(j+1)*unit' in src
    assert src.count("cwNode('rect'") >= 2
    assert '\u767d\u7816\u8fb9 ' in src and '\u84dd\u7816\u8fb9 ' in src  # 白砖边 / 蓝砖边


def test_hundred_chart_square_covers_the_ten_by_ten_grid():
    """百数表要 10×10 循环、1..100 数值，并讲清 n/n+1/n+10/n+11。"""
    src = _func(COURSEWARE_JS, 'cwHundredChartSquare', 'cwTriangularNumbers')
    assert 'r<10' in src and 'c<10' in src
    assert 'r*10+c+1' in src            # 1..100
    for part in ('n+1', 'n+10', 'n+11'):
        assert part in src


def test_running_track_marks_a_and_b_and_states_the_speed_difference():
    """环形跑道要标 A、B 两点，说清每分钟多跑多少米，并写出 s ÷ (速度差)。"""
    src = _func(COURSEWARE_JS, 'cwRunningTrack', 'cwTilePattern')
    assert "point(95,145,'A')" in src and "'B'" in src
    assert 'fastSpeed' in src and 'slowSpeed' in src
    assert 'distanceSymbol' in src
    assert 'fastSpeed-f.slowSpeed' in src
    exercise = r'''
var box=new E('div');
cwFigure(box,{type:'running_track',fastSpeed:180,slowSpeed:140,distanceSymbol:'s'},false,{step:5,previewMode:true},false,5);
var text=textOf(box);
assert(text.indexOf('每分钟多跑 40')>=0,text);
assert(text.indexOf('÷ (180 - 140)')>=0,text);
assert(text.indexOf('s / 40')>=0,text);
assert(text.indexOf('A')>=0&&text.indexOf('B')>=0,'要标出 A、B 两点');
console.log('OK');
'''
    result = _node(DOM + COURSEWARE_JS + exercise)
    assert result.returncode == 0, result.stderr
    assert 'OK' in result.stdout


def test_preview_failure_shows_reason_and_a_retry_button():
    """预览失败不能只写一句报错：要有原因、console.error 和“重试”。"""
    assert '\u9884\u89c8\u5931\u8d25\uff1a' in COURSEWARE_PLAN_JS  # 预览失败：
    assert '\u91cd\u8bd5' in COURSEWARE_PLAN_JS                    # 重试
    assert "console.error('" in COURSEWARE_PLAN_JS
    assert 'openEditor(x,it)' in COURSEWARE_PLAN_JS
    # 旧的提示文案“预览打开失败：…”不能再作为老师看到的说明（console.error 里可以出现）。
    assert '\u9884\u89c8\u6253\u5f00\u5931\u8d25\uff1a' not in COURSEWARE_PLAN_JS


def test_plan_preview_guards_missing_payload_before_rendering():
    """空数据、缺 items、缺 params 都先兜底，不能抛 Cannot convert undefined or null to object。"""
    assert 'd=d||{}' in COURSEWARE_PLAN_JS
    assert 'd.items=d.items||[]' in COURSEWARE_PLAN_JS
    assert 'd.pages=d.pages||{}' in COURSEWARE_PLAN_JS
    assert 'd.templates=d.templates||[]' in COURSEWARE_PLAN_JS
    assert 'data.templates=data.templates||[]' in COURSEWARE_PLAN_JS
    assert 'kinds.length' in COURSEWARE_PLAN_JS


def test_render_wraps_every_figure_in_try_catch():
    """单个图画坏了也只坏一块，不能整页白屏。"""
    start = COURSEWARE_JS.index('function cwRender(')
    src = COURSEWARE_JS[start:COURSEWARE_JS.index('var CW_PENDING', start)]
    assert 'try{' in src and 'catch' in src
    assert '\u56fe\u793a\u6e32\u67d3\u5931\u8d25' in src  # 图示渲染失败
    assert '\u91cd\u8bd5' in src
    assert 'console.error' in src


def test_obtuse_triangle_runs_from_triangle_to_area():
    """真的用 node 跑一遍：第 1 步只有三角形，最后一步才给面积。"""
    exercise = r'''
function draw(step,teacher,preview){var box=new E('div');
  cwFigure(box,{type:'obtuse_triangle_height',base:7,side:15,height:7.5,unit:'cm'},false,{step:step,previewMode:preview!==false},!!teacher,5);
  return {svg:all(box).filter(function(x){return x.tag==='svg'}),text:textOf(box)};}
var s1=draw(1,false);
assert(s1.svg.length===1,'第 1 步就要画出三角形');
assert(s1.text.indexOf('面积')<0,'第 1 步不能先给面积');
assert(s1.text.indexOf('垂足')<0,'第 1 步还没画高');
var s2=draw(2,false);
assert(s2.text.indexOf('底边延长线')>=0,'第 2 步画延长线');
assert(s2.text.indexOf('垂足')<0,'第 2 步还没画高');
var s3=draw(3,false);
assert(s3.text.indexOf('垂足')>=0,'第 3 步画高和垂足');
assert(s3.text.indexOf('面积')<0,'第 3 步不给面积');
var s5=draw(5,false);
assert(s5.text.indexOf('底 BC = 7cm')>=0,s5.text);
assert(s5.text.indexOf('边 AC = 15cm')>=0,s5.text);
assert(s5.text.indexOf('高 = 7.5cm')>=0,s5.text);
assert(s5.text.indexOf('26.25')>=0,'面积 7×7.5÷2=26.25，实际：'+s5.text);
var whole=draw(0,true,false);
assert(whole.text.indexOf('26.25')>=0,'老师全展开要看到面积');
console.log('OK');
'''
    result = _node(DOM + COURSEWARE_JS + exercise)
    assert result.returncode == 0, result.stderr
    assert 'OK' in result.stdout


def test_collapsed_steps_and_answer_are_rendered_separately():
    """点开 0 步时只露“第 1 步”，答案点了才出现；图示待确认时换黄底提示。"""
    exercise = r'''
function render(view,extra){var box=new E('div'),p={title:'例题',problem:'题干',answer:'42',
  steps:['甲乙丙正文一','甲乙丙正文二','甲乙丙正文三','甲乙丙正文四'],figure:{type:'table',rows:[['1','2']]}};
  Object.keys(extra||{}).forEach(function(k){p[k]=extra[k]});
  cwSteps(box,p,view,false,false);return box}
var a=render({step:0,previewMode:true,showAnswer:false});
var at=textOf(a);
assert(at.indexOf('第 1 步')>=0,at);
assert(at.indexOf('甲乙丙正文一')<0,'没展开的步骤不能露出正文');
assert(at.indexOf('答案')<0,'没点显示答案不能出现答案');
assert(at.indexOf('已展开 0 / 4 步')>=0,at);
var b=render({step:2,previewMode:true,showAnswer:false});
var bt=textOf(b);
assert(bt.indexOf('甲乙丙正文一')>=0&&bt.indexOf('甲乙丙正文二')>=0,'展开两步');
assert(bt.indexOf('甲乙丙正文三')<0,'第三步还没展开');
assert(bt.indexOf('答案')<0,'答案仍要等按钮');
var c=render({step:2,previewMode:true,showAnswer:true});
assert(textOf(c).indexOf('答案：42')>=0,'点了显示答案就要出现');
var d=render({step:0,previewMode:false,showAnswer:false},{figureUnverified:true,figureNotice:'图示待确认：数字对不上'});
var dt=textOf(d);
assert(dt.indexOf('本题需要老师确认配图')>=0,dt);
assert(dt.indexOf('图示待确认：数字对不上')>=0,dt);
assert(all(d).filter(function(x){return x.tag==='svg'}).length===0,'待确认时不能当正确图画出来');
var e=render({step:0,previewMode:false,showAnswer:false},{figureUnverified:true});
assert(textOf(e).indexOf('题干与图示不一致')>=0,'缺省提示也要有');
console.log('OK');
'''
    result = _node(DOM + COURSEWARE_JS + exercise)
    assert result.returncode == 0, result.stderr
    assert 'OK' in result.stdout


def test_figure_text_never_throws_on_empty_figure():
    """空图示、null 都要返回一句可读描述。"""
    exercise = r'''
var empty=cwFigureText({});
assert(typeof empty==='string'&&empty.length>0,empty);
var nul=cwFigureText(null);
assert(typeof nul==='string'&&nul.length>0,nul);
for(var i=0;i<3;i++){var f={type:'segment'};assert(typeof cwFigureText(f)==='string')}
assert(cwFigureText({type:'tile_pattern'}).indexOf('数据不全')>=0,'缺字段给占位说明');
assert(cwFigureText({type:'obtuse_triangle_height',base:7,side:15,height:7.5,unit:'cm'}).indexOf('7cm')>=0);
console.log('OK');
'''
    result = _node(DOM + COURSEWARE_JS + exercise)
    assert result.returncode == 0, result.stderr
    assert 'OK' in result.stdout
