"""第19题这类 lesson11 手绘图：大屏要跟着老师的步数逐步展开，不能只在老师端才画高线。"""
from __future__ import annotations

import subprocess
from pathlib import Path

JSFILE = Path(__file__).parents[1] / "changying/web/lesson11_methods_v2.js"

SCRIPT = r"""
const assert=require('assert'),fs=require('fs'),vm=require('vm');
class E {
  constructor(t,a,v){this.tag=t;this.attrs=a||{};this.children=[];this.text=v||'';this.createSVGRect=t==='svg'?function(){}:undefined;}
  appendChild(n){this.children.push(n);return n;}
}
global.window=global;
global.document={createElementNS:function(_,t){return new E(t)},createElement:function(t){return new E(t)}};
global.el=function(t,a){var n=new E(t,a);if(a&&a.text)n.text=a.text;return n};
global.cwNode=function(t,a,v){return new E(t,a,v)};
global.cwFigureText=function(f){return f&&f.type};
global.cwSteps=function(box){box.appendChild(new E('div',{text:'OLD_STEPS'}))};
vm.runInThisContext(fs.readFileSync(process.argv[1],'utf8'));
function walk(n,out){out.push(n);(n.children||[]).forEach(function(c){walk(c,out)});return out}
var P={title:'第19题 画高·钝角三角形',
  sourceProblem:'第19题：钝角三角形选定的底边长7 cm，另一边长15 cm，顶点到底边所在直线的垂直距离为7.5 cm。注意：垂足落在底边的延长线上。',
  steps:['找底','延长底边','向延长线作垂线','标垂足和高','算面积'],
  figure:{type:'obtuse_triangle_height',base:7,side:15,height:7.5},
  answer:'7×7.5÷2=26.25'};
function render(view,teacher){var box=new E('div');cwSteps(box,P,view,true,teacher);return box}
function heightLines(box){return walk(box,[]).filter(function(n){
  return n.tag==='line'&&Number(n.attrs.x1)===30&&Number(n.attrs.x2)===30&&String(n.attrs.stroke)==='#b42318';})}
function texts(box){return walk(box,[]).map(function(n){return String(n.text||'')})}
// 大屏（teacher=false）跟着步数走
assert.equal(heightLines(render({step:1},false)).length,0,'step1 大屏还没有高线');
assert.equal(heightLines(render({step:2},false)).length>=1,true,'step2 大屏应画出高线');
assert.equal(heightLines(render({step:5},false)).length>=1,true,'step5 高线仍在');
// 老师预览（teacher=true + previewMode）同样按步数走
assert.equal(heightLines(render({step:1,previewMode:true},true)).length,0,'预览第1步不画高线');
assert.equal(heightLines(render({step:3,previewMode:true},true)).length>=1,true,'预览第3步画高线');
// 显示答案时不依赖步数
assert.equal(heightLines(render({step:0,showAnswer:true},false)).length>=1,true,'显示答案时画高线');
// 未展开的步骤只能是“第 N 步”，不能是占位句
var t=texts(render({step:2},false)).join('|');
assert(t.indexOf('点“下一步”显示')<0,'不再出现占位句');
assert(t.indexOf('第 3 步')>=0&&t.indexOf('第 5 步')>=0,'未展开步骤显示第 N 步');
// 老师预览从第 0 步开始时，一步都不展开
var zero=texts(render({step:0,previewMode:true},true)).join('|');
assert(zero.indexOf('找底')<0,'第0步不展开任何步骤');
console.log('OK');
"""


def test_q19_height_and_steps_follow_the_shared_step_counter():
    result = subprocess.run(
        ["node", "-e", SCRIPT, str(JSFILE)], text=True, capture_output=True, timeout=30
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "OK" in result.stdout
