"""Focused visual regression for the actual lesson 10 worked example 15."""
import subprocess

from changying.web.weekend_courseware import _repair_courseware_visual
from changying.web.weekend_courseware_pages import COURSEWARE_JS


PROBLEM = (
    "第15题 3×3方格规律。在每行10个数的数表中，用3×3方框圈九个数。"
    "若中心数为a，九数和是多少？若九数和为2016，中心数是多少？"
)


def legacy_figure():
    # Exact defect shown by teacher: right-middle and right-bottom are dots.
    return {
        "type": "table",
        "rows": [
            ["a-11", "a-10", "a-9"],
            ["a-1", "a", "·"],
            ["a+9", "a+10", "·"],
        ],
    }


def test_saved_example15_repairs_two_missing_cells_and_only_its_legacy_steps():
    original = {
        "title": "第15题3×3方格规律",
        "figure": legacy_figure(),
        "steps": [
            "第1步：在3×3方框中定位中心数a，它上下左右各有相邻数。",
            "第2步：同一行相邻两数差1，所以左右是a-1、a+1。",
            "第3步：观察上下", "第4步：角上", "第5步：九数和", "第6步：反求中心",
        ],
        "answer": "九数和为9a；当九数和为2016时，中心数a=224。",
        "sourceFigure": {"type": "uploaded_image", "data_url": "test://original"},
    }
    repaired = _repair_courseware_visual(original, PROBLEM)
    assert repaired["figure"]["type"] == "table"
    assert repaired["figure"]["nineGrid"] is True
    assert repaired["figure"]["targetSum"] == 2016
    assert repaired["figure"]["center"] == 224
    assert repaired["figure"]["rows"] == [
        ["a−11", "a−10", "a−9"],
        ["a−1", "a", "a+1"],
        ["a+9", "a+10", "a+11"],
    ]
    assert len(repaired["steps"]) == 6
    assert "a+1" in repaired["steps"][1] and "a+11" in repaired["steps"][3]
    assert repaired["answer"] == original["answer"]
    assert repaired["sourceFigure"] == original["sourceFigure"]
    assert original["figure"] == legacy_figure()  # no DB/object mutation


def test_non_example15_figures_and_tuned_steps_stay_unchanged():
    own = {
        "figure": {"type": "table", "rows": [
            ["a−11", "a−10", "a−9"],
            ["a−1", "a", "a+1"],
            ["a+9", "a+10", "a+11"],
        ]},
        "steps": ["老师的观察", "老师的猜想", "推导", "检验"],
    }
    assert _repair_courseware_visual(own, PROBLEM) == own
    other = _repair_courseware_visual(
        {"figure": legacy_figure(), "steps": ["自己的图"]},
        "第14题：求3×3方格的九数和，中心数为a，九数和2016",
    )
    assert other["figure"] == legacy_figure()


def test_example15_actual_js_reveals_only_corresponding_cells_at_each_step(tmp_path):
    harness = r"""
const assert=require('assert');
class E{
  constructor(tag,a){this.tag=tag;this.a=a||{};this.children=[];this.parentNode=null;this._text=this.a.text||'';this.style=''}
  appendChild(c){this.children.push(c);c.parentNode=this;return c}
  set textContent(v){this._text=v;this.children=[]}
  get textContent(){return this._text}
}
function el(tag,attrs){var n=new E(tag,attrs);Object.keys(attrs||{}).forEach(function(k){if(k==='text')n.textContent=attrs[k];else if(k==='style')n.style=attrs[k]});for(var i=2;i<arguments.length;i++){var c=arguments[i];if(c!=null)n.appendChild(typeof c==='string'?new E('#text',{text:c}):c)}return n}
var document={createElement:function(tag){return new E(tag,{})}};
function all(e){return [e].concat(e.children.reduce(function(a,c){return a.concat(c instanceof E?all(c):[])},[]))}
var f={type:'table',nineGrid:true,reveal:false,targetSum:2016,center:224,
  rows:[['a−11','a−10','a−9'],['a−1','a','a+1'],['a+9','a+10','a+11']]};
function render(n,teacher,preview){var box=new E('div');cwFigure(box,f,false,{step:n,previewMode:preview,showAnswer:false},teacher,6);return box}
function cells(box){return all(box).filter(function(x){return x.style&&x.style.indexOf('min-height:')>=0})}
function words(box){return all(box).map(function(x){return x.textContent}).join('|')}
var expected=[
  null,
  ['？','？','？','？','a','？','？','？','？'],
  ['？','？','？','a−1','a','a+1','？','？','？'],
  ['？','a−10','？','a−1','a','a+1','？','a+10','？'],
  ['a−11','a−10','a−9','a−1','a','a+1','a+9','a+10','a+11']
];
for(var step=1;step<=4;step++){
  var got=cells(render(step,false,true)).map(function(x){return x.textContent});
  assert.deepStrictEqual(got,expected[step],'step '+step+' visible digits');
}
var fifth=render(5,false,true),sixth=render(6,false,true);
assert.strictEqual(cells(fifth)[4].textContent,'a','step 5 still hides numeric answer');
assert(words(fifth).includes('九数和 = 9a'),'step 5 displays symbolic sum');
assert(!words(fifth).includes('224'),'student cannot see 224 before step 6');
assert.strictEqual(cells(sixth)[4].textContent,'224','step 6 reveals centre value');
assert(words(sixth).includes('9a = 2016'),'step 6 shows equation');
assert.strictEqual(cells(render(2,true,true))[5].textContent,'a+1','teacher preview follows current step');
assert.strictEqual(cells(render(1,true,false))[4].textContent,'224','teacher full view has answer');
console.log('OK');
"""
    script = tmp_path / "lesson15_six_steps.js"
    script.write_text(COURSEWARE_JS + harness, encoding="utf-8")
    result = subprocess.run(["node", str(script)], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip() == "OK"
