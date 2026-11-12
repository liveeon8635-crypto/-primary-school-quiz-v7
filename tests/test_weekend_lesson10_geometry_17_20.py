"""Visual regression for the two remaining lesson-10 geometry examples.

Only already saved generic rectangle diagrams are enhanced; other courseware
and teacher-authored steps are not changed in the database.
"""
import subprocess

from changying.web.weekend_courseware_pages import COURSEWARE_JS


def test_ex17_and_ex20_existing_figures_render_as_real_geometry(tmp_path):
    harness = r"""
const assert=require('assert');
class E {
 constructor(tag,a){this.tag=tag;this.a=a||{};this.children=[];this.parentNode=null;this._text=this.a.text||'';this.style='';this.attrs={};this.createSVGRect=function(){}}
 appendChild(c){this.children.push(c);c.parentNode=this;return c}
 setAttribute(k,v){this.attrs[k]=String(v)}
 set textContent(v){this._text=String(v);this.children=[]}
 get textContent(){return this._text}
}
function el(tag,attrs){var n=new E(tag,attrs);Object.keys(attrs||{}).forEach(function(k){if(k==='text')n.textContent=attrs[k];else if(k==='style')n.style=attrs[k]});for(var i=2;i<arguments.length;i++){var c=arguments[i];if(c!=null)n.appendChild(typeof c==='string'?new E('#text',{text:c}):c)}return n}
var document={createElement:function(tag){return new E(tag,{})},createElementNS:function(ns,tag){return new E(tag,{})}};
function all(n){return [n].concat(n.children.reduce(function(acc,c){return acc.concat(all(c))},[]))}
function words(n){return all(n).map(function(x){return x.textContent}).filter(Boolean).join('|')}
function elems(n,t){return all(n).filter(function(x){return x.tag===t})}
function renderFigure(p,step,teacher,preview){var root=new E('div');var before=JSON.stringify(p);
 var matched=cwLesson10Geometry(root,p,{step:step,previewMode:preview},false,teacher);
 assert.strictEqual(JSON.stringify(p),before,'must not mutate teacher data');return {root:root,matched:matched}}
var shape={type:'shape',shape:'rectangle',labels:{top:'a',left:'b'}};
var ex17={title:'第17题 整理｜单元知识回顾',
 problem:'正方形边长a；长方形长a、宽b；若m=n+20且m=37，求n。',
 figure:shape,steps:['观察','正方形','长方形','求n','检验'],answer:'17'};
var a1=renderFigure(ex17,1,false,true);
assert(a1.matched,'example 17 must use the dedicated drawing');
assert.strictEqual(elems(a1.root,'rect').length,2,'square and rectangle are two separate figures');
var dims=elems(a1.root,'rect').map(function(x){return [+x.attrs.width,+x.attrs.height]});
assert.strictEqual(dims[0][0],dims[0][1],'the first one is a square');
assert(dims[1][0]!==dims[1][1],'the second one is a rectangle');
assert(renderFigure({...ex17,title:'第17题',problem:'正方形边长a，长方形长a宽b'},1,false,true).matched,'17 title alone matches');
assert(words(a1.root).indexOf('4a')<0,'no formula in the diagram at first step');
assert(words(renderFigure(ex17,2,false,true).root).indexOf('4a')>=0);
assert(words(renderFigure(ex17,3,false,true).root).indexOf('2(a+b)')>=0);
assert(words(renderFigure(ex17,4,false,true).root).indexOf('n = 17')>=0);
assert(words(renderFigure(ex17,1,true,true).root).indexOf('n = 17')<0,'teacher preview follows the step');
var ex20={title:'大、小正方形拼图',
 problem:'由2个大正方形和3个小正方形拼成一个长方形，大正方形边长m cm，小正方形边长n cm，求周长。',
 figure:{type:'shape',shape:'rectangle',labels:{top:'上边2m cm'}},
 steps:['观察拼图','比较上下','列等式','求出周长'],answer:'C=11n'};
assert(renderFigure({...ex20,title:'第20题'},1,false,true).matched,'20 title alone matches');
var b1=renderFigure(ex20,1,false,true);
assert(b1.matched,'example 20 must use the tiling drawing');
var squares=elems(b1.root,'rect');
assert.strictEqual(squares.length,5,'two big and three small squares');
assert(squares.every(function(x){return x.attrs.width===x.attrs.height}), 'all five must be actual squares');
assert.strictEqual(+squares[0].attrs.width*2,+squares[2].attrs.width*3,'equal total widths');
assert.strictEqual(+squares[0].attrs.y + +squares[0].attrs.height,+squares[2].attrs.y,'rows touch without gaps');
assert(words(b1.root).indexOf('C =')<0,'do not leak final answer at step 1');
assert(words(renderFigure(ex20,2,false,true).root).includes('上排总宽 2m'));
assert(words(renderFigure(ex20,3,false,true).root).includes('2m = 3n'));
assert(words(renderFigure(ex20,4,false,true).root).includes('C = 2(3n+m+n) = 11n'));
assert(words(renderFigure(ex20,1,true,true).root).indexOf('11n')<0);
var other={title:'另一道几何题',problem:'长方形面积是多少？',figure:shape,steps:['看图','求值']};
assert(!renderFigure(other,2,false,true).matched,'other geometry must keep the existing renderer');
var changed=new E('div');
cwSteps(changed,ex20,{step:2,previewMode:true},false,false);
assert.strictEqual(elems(changed,'rect').length,5,'existing cwSteps must use five-square diagram');
console.log('OK');
"""
    path = tmp_path / "lesson10_geometry.js"
    path.write_text(COURSEWARE_JS + harness, encoding="utf-8")
    run = subprocess.run(["node", str(path)], capture_output=True, text=True, timeout=30)
    assert run.returncode == 0, run.stdout + run.stderr
    assert run.stdout.strip() == "OK"


def test_no_unrelated_lesson_or_database_changes_in_renderer():
    assert "function cwLesson10Geometry(" in COURSEWARE_JS
    # Other teaching figures may now be checked first; the original
    # 17/20 renderer and generic fallback must still be present and used.
    assert "cwLesson10Geometry(wrap,p,view,big,teacher)" in COURSEWARE_JS
    assert "cwFigure(wrap,p.figure,big,view,teacher,p.steps.length)" in COURSEWARE_JS
    assert "if(!p.figure||p.figure.type!=='shape'||p.figure.shape!=='rectangle')return false" in COURSEWARE_JS
    assert "innerHTML" not in COURSEWARE_JS
