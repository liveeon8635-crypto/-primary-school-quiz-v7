"""第17题等面积三角形作图：作图区A/B要跟着步数画出三角形，不能只在"显示答案"时才画。"""
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
var P17={title:'第17题 等面积三角形作图',
  sourceProblem:'第17题：涂色平行四边形的底6格、高3格。请分别在"作图区A"和"作图区B"内画三角形。',
  steps:['数面积','想底×高','A区作图','B区作图','核对面积'],answer:'A：9×4÷2=18；B：12×3÷2=18'};
var P18={title:'第18题 测量·直角三角形',
  sourceProblem:'第18题：直角三角形，两条直角边10厘米、7.5厘米，斜边12.5厘米。',
  steps:['看方格','找底','找高','算面积','核对'],answer:'37.5'};
function render(p,view,teacher){var box=new E('div');cwSteps(box,p,view,true,teacher);return box}
function texts(box){return walk(box,[]).map(function(n){return String(n.text||'')}).join('|')}
function polys(box){return walk(box,[]).filter(function(n){return n.tag==='polygon'})}
function lines(box,stroke){return walk(box,[]).filter(function(n){return n.tag==='line'&&String(n.attrs.stroke)===stroke})}

// 第17题：作图区A 从第2步出现，B 从第3步出现，算式从第5步出现
assert(polys(render(P17,{step:1},false)).length===1,'第1步只有原图平行四边形');
assert(polys(render(P17,{step:2},false)).length===2,'第2步出现作图区A的三角形');
assert(polys(render(P17,{step:3},false)).length===3,'第3步再出现作图区B的三角形');
assert.equal(polys(render(P17,{step:5},false)).length,3,'两个三角形都保留');
var t5=texts(render(P17,{step:5},false));
assert(t5.indexOf('A：9×4÷2=18')>=0,'第5步给出面积算式');
assert(t5.indexOf('底9格')>=0&&t5.indexOf('高4格')>=0,'A区标出底和高');
assert(t5.indexOf('底12格')>=0&&t5.indexOf('高3格')>=0,'B区标出底和高');
// 老师预览也跟着步数走，并且第0步什么都不展开
assert(polys(render(P17,{step:0,previewMode:true},true)).length===1,'预览第0步只有原图');
assert(polys(render(P17,{step:2,previewMode:true},true)).length===2,'预览第2步出现A区三角形');
// 显示答案时一次到位
assert.equal(polys(render(P17,{step:0,showAnswer:true},false)).length,3,'显示答案时两个三角形都在');

// 第18题：底、高、面积分三步出现
var base18=function(v){return lines(render(P18,v,false),'#1d4ed8').length};
assert.equal(base18({step:1}),0,'第1步还没画底');
assert(base18({step:2})>=1,'第2步画出底');
function height18(v){return walk(render(P18,v,false),[]).filter(function(n){
  return n.tag==='line'&&Number(n.attrs.x1)===157&&Number(n.attrs.y1)===89&&String(n.attrs.stroke)==='#b42318';}).length}
assert.equal(height18({step:2}),0,'第2步还没有高');
assert(height18({step:3})>=1,'第3步画出高');
assert(texts(render(P18,{step:3},false)).indexOf('高5格=2.5 cm')>=0,'第3步标出高');
assert(texts(render(P18,{step:4},false)).indexOf('面积=4×2.5÷2=5 cm²')>=0,'第4步算出面积');
assert(texts(render(P18,{step:5},false)).indexOf('37.5')>=0,'第5步算出右边面积');
console.log('OK');
"""


def test_q17_draws_both_triangles_step_by_step():
    result = subprocess.run(
        ["node", "-e", SCRIPT, str(JSFILE)], text=True, capture_output=True, timeout=30
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "OK" in result.stdout
