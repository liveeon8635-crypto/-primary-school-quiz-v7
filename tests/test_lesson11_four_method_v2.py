"""Lesson 11 method #2: intact student diagrams and teacher-only results."""
from __future__ import annotations

import subprocess
from pathlib import Path

from changying.web.weekend_pages import plan_page_html, control_page_html, board_page_html


def test_geometry_v2_on_all_three_views_without_changing_inline_scripts():
    for page in (plan_page_html(), control_page_html(), board_page_html()):
        assert '<script src="/v1/lesson11-methods-v2.js?v=20261115-lesson11-diagrams-r6"></script>' in page
        assert page.count('<script src="/v1/lesson11-methods-v2.js?v=20261115-lesson11-diagrams-r6"></script>') == 1
    code = (Path(__file__).parents[1] / "changying/web/lesson11_methods_v2.js").read_text()
    assert 'window.cwParallelogramMethods=' in code
    assert "view.showAnswer" in code
    assert "左侧沿高剪移" in code and "右侧沿高剪移" in code
    assert "中点M" not in code


def test_four_states_are_unresolved_until_teacher_reveal():
    jsfile = Path(__file__).parents[1] / "changying/web/lesson11_methods_v2.js"
    script = r"""
const assert=require('assert'),fs=require('fs'),vm=require('vm');
class E {
 constructor(t,a,v){this.tag=t;this.attrs=a||{};this.children=[];this.text=v||'';this.createSVGRect=t==='svg'?function(){}:undefined;}
 appendChild(n){this.children.push(n);return n;}
}
global.window=global;
global.document={createElementNS:function(_,t){return new E(t)},createElement:function(t){return new E(t)}};
global.el=function(t,a){var n=new E(t,a);if(a&&a.text)n.text=a.text;return n};
global.cwNode=function(t,a,v){return new E(t,a,v)};
global.cwFigureText=function(f){return f.type};
global.cwSteps=function(box,p){box.appendChild(new E('div',{text:'OLD_STEPS'}))};
vm.runInThisContext(fs.readFileSync(process.argv[1],'utf8'));
function render(view,teacher){var box=new E('div');cwParallelogramMethods(box,view,false,teacher);return box.children[0].children[0]}
function polygonPoints(g){return g.children.filter(function(c){return c.tag==='polygon'}).map(function(c){return c.attrs.points})}
var student=render({step:5},false),teacherStart=render({step:1,previewMode:true},true);
var teacherEnd=render({step:5,previewMode:true},true);
function highlighted(svg){
 return svg.children.map((panel,index)=>panel.children[0].attrs.stroke==='#cb7616'?index+1:0).filter(Boolean);
}
assert.deepEqual(highlighted(render({step:0},false)),[]);
for(var step=1;step<=4;step++){
 var board=render({step:step,showAnswer:false},false);
 assert.deepEqual(highlighted(board),[step]);
 assert.deepEqual(board.children.map(polygonPoints),student.children.map(polygonPoints),'focus must not expose solved geometry');
}
assert.deepEqual(highlighted(render({step:4,showAnswer:true},false)),[]);

var legacy={figure:{type:'parallelogram_methods'},problem:'点M、N是所在边中点'};
var teacherWarn=new E('div'),studentBlocked=new E('div');
cwSteps(teacherWarn,legacy,{step:1},false,true);
cwSteps(studentBlocked,legacy,{step:1},true,false);
assert(teacherWarn.children.some(function(x){return String(x.attrs.text||'').indexOf('旧版')>=0}),'teacher sees stale-source warning');
assert.equal(studentBlocked.children.length,1,'old mismatched student geometry is withheld');
assert.equal(studentBlocked.children[0].tag,'div');
assert.equal(studentBlocked.children[0].attrs.text.indexOf('暂停展示')>=0,true);
assert.equal(student.children.length,4);
assert.equal(teacherStart.children.length,4);
const original='40,191 146,191 174,105 68,105',rotated='75,79 168,123 168,210 75,166';
for(var i=0;i<3;i++)assert(polygonPoints(student.children[i]).indexOf(original)>=0,'student start '+i);
assert(polygonPoints(student.children[3]).indexOf(rotated)>=0,'④ starts as tilted parallelogram');
var r1='68,105 174,105 174,191 68,191',r3='40,105 146,105 146,191 40,191',r4='75,79 168,79 168,166 75,166';
for(var n=0;n<4;n++)assert(!polygonPoints(student.children[n]).some(function(q){return [r1,r3,r4].indexOf(q)>=0}),'premature rectangle');
assert(polygonPoints(teacherEnd.children[0]).indexOf(r1)>=0,'① results in rectangle');
assert(polygonPoints(teacherEnd.children[2]).indexOf(r3)>=0,'③ results in rectangle');
assert(polygonPoints(teacherEnd.children[3]).indexOf(r4)>=0,'④ results in rectangle');
assert(polygonPoints(teacherEnd.children[1]).some(function(q){return q==='56,191 162,191 190,105 84,105'}),'② stays parallelogram');
assert(!polygonPoints(teacherStart.children[0]).some(function(q){return q===r1}));
assert(!/①③④.*正确/.test(fs.readFileSync(process.argv[1],'utf8')),'no premature answer key');
console.log('OK');
"""
    result = subprocess.run(["node", "-e", script, str(jsfile)], text=True, capture_output=True, timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "OK" in result.stdout
