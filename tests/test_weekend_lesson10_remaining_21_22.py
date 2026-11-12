"""Only restore the two existing specialized visuals for legacy lessons 21/22."""
import subprocess

from changying.web.weekend_courseware_pages import COURSEWARE_JS


def test_running_track_and_triangular_numbers_use_real_courseware_render(tmp_path):
    harness = r"""
const assert=require('assert');
class E{
 constructor(tag,a){this.tag=tag;this.a=a||{};this.children=[];this.parentNode=null;this._text=this.a.text||'';this.style='';this.attrs={};this.createSVGRect=function(){}}
 appendChild(c){this.children.push(c);c.parentNode=this;return c}
 setAttribute(k,v){this.attrs[k]=String(v)}
 set textContent(v){this._text=String(v);this.children=[]}
 get textContent(){return this._text}
}
function el(tag,attrs){var n=new E(tag,attrs);Object.keys(attrs||{}).forEach(function(k){if(k==='text')n.textContent=attrs[k];else if(k==='style')n.style=attrs[k]});for(var i=2;i<arguments.length;i++){var c=arguments[i];if(c!=null)n.appendChild(typeof c==='string'?new E('#text',{text:c}):c)}return n}
var document={createElement:function(t){return new E(t,{})},createElementNS:function(ns,t){return new E(t,{})}};
function all(e){return [e].concat(e.children.reduce(function(a,c){return a.concat(all(c))},[]))}
function elems(e,t){return all(e).filter(function(n){return n.tag===t})}
function words(e){return all(e).map(function(x){return x.textContent}).join('|')}
function render(p,step,teacher,preview){var root=new E('div'),serialized=JSON.stringify(p);
 cwSteps(root,p,{step:step,previewMode:preview,showAnswer:false},false,teacher);
 assert.strictEqual(JSON.stringify(p),serialized,'teacher-saved params must not mutate');
 return root}
var p21={
 title:'跑道追及问题',
 problem:'操场跑道周长为s米。丽丽每分钟跑180米，丙丙每分钟跑140米，从同一地点同时出发、同向而行。多少分钟后丽丽超过丙丙一整圈？',
 steps:['观察跑道','比较每分钟路程','相差一圈','列式','检验'],
 answer:'s/40 分钟',figure:{},
 sourceFigure:{type:'uploaded_image',data_url:'data:image/jpeg;base64,QUJD',alt:'对照'}
};
var a1=render(p21,1,false,true),a2=render(p21,2,false,true),a5=render(p21,5,false,true);
assert.strictEqual(elems(a1,'ellipse').length,2,'lesson21 real oval track');
assert.strictEqual(elems(a1,'circle').length,2,'two runners on track');
assert(words(a1).indexOf('180')>=0&&words(a1).indexOf('140')>=0,'accurate original speed data');
assert(words(a1).indexOf('s / 40')<0,'step one must hide final quotient');
assert(words(a2).indexOf('80 米')>=0,'step two should show accumulated difference');
assert(words(a5).indexOf('s / 40')>=0,'last step reveals final formula');
assert.strictEqual(elems(a1,'details').length,1,'preserve source image comparison');
var p22={
 title:'三角形数规律',
 problem:'1、3、6、10、15......这些数称为三角形数。按规律，第 10 个三角形数是多少？第 n 个三角形数怎样表示？',
 steps:['观察相邻差','排成三角形','发现逐层增加','拼成长方形','推导公式'],
 answer:'第10个55；第n个n(n+1)÷2',
 figure:{type:'table',rows:[['n','1','2','3','4','5'],['三角形数','1','3','6','10','15']]}
};
var b1=render(p22,1,false,true),b3=render(p22,3,false,true),b5=render(p22,5,false,true);
assert.strictEqual(elems(b1,'table').length,0,'generic table should become dots');
assert.strictEqual(elems(b1,'circle').length,1,'one dot at step one');
assert.strictEqual(elems(b3,'circle').length,6,'triangular 1+2+3 at step three');
assert.strictEqual(elems(b5,'circle').length,45,'full dot triangle plus two-triangle rectangle proof');
assert(words(b1).indexOf('55')<0,'no result in first-step dot diagram');
assert(words(b5).indexOf('55')>=0&&words(b5).indexOf('n(n+1)')>=0,'final generalized rule');
var custom={title:p22.title,problem:p22.problem,steps:p22.steps,answer:p22.answer,
 figure:{type:'table',rows:[['教师设计表','A'],['自定义观察','B']]}};
assert.strictEqual(elems(render(custom,3,false,true),'table').length,1,'do not replace teacher custom table');
var prebuilt={title:p22.title,problem:p22.problem,steps:p22.steps,answer:p22.answer,
 figure:{type:'triangular_numbers',terms:[1,3,6,10,15],targetTerm:10}};
assert.strictEqual(elems(render(prebuilt,2,false,true),'circle').length,3,'existing dedicated figure remains supported');
var unrelated={title:'另一题',problem:p21.problem,steps:p21.steps,answer:p21.answer,figure:{}};
assert.strictEqual(elems(render(unrelated,3,false,true),'ellipse').length,0,'other questions not changed');
console.log('OK');
"""
    path=tmp_path/"weekend_21_22.js"
    path.write_text(COURSEWARE_JS+harness,encoding="utf-8")
    result=subprocess.run(["node",str(path)],capture_output=True,text=True,timeout=30)
    assert result.returncode==0,result.stdout+result.stderr
    assert result.stdout.strip()=="OK"


def test_lesson21_22_are_presentation_only():
    assert "function cwLesson10RemainingFigure(" in COURSEWARE_JS
    assert "function cwRunningTrack(" in COURSEWARE_JS
    assert "function cwTriangularNumbers(" in COURSEWARE_JS
    assert "cwLesson10RemainingFigure(wrap,p,view,big,teacher)" in COURSEWARE_JS
    assert "innerHTML" not in COURSEWARE_JS
