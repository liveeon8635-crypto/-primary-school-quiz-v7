"""Regressions for lesson 11's original four-method geometry question."""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

from changying.services import weekend_courseware as cw
from changying.services.weekend_courseware_quality import audit_example_pages
from changying.web.weekend_courseware import (
    _repair_courseware_visual, required_visual_figure, required_visual_type,
)
from changying.web.weekend_courseware_pages import COURSEWARE_JS, COURSEWARE_PLAN_JS

SOURCE = (
    "第2题　2分\n操作｜四种转化方法辨析\n"
    "（2）下面的方法中，也能推导出平行四边形面积公式的有（ ）。"
    "（点M、N是所在边中点）请逐一观察①②③④的移动、剪拼和旋转方向。"
)


def test_question_two_deterministic_figure_only_and_retain_teacher_content():
    assert required_visual_type(SOURCE) == "parallelogram_methods"
    assert required_visual_figure(SOURCE) == {"type": "parallelogram_methods"}
    assert cw.clean_figure(required_visual_figure(SOURCE)) == {"type": "parallelogram_methods"}
    assert required_visual_type("第2题：使用平行四边形面积公式求面积") == ""
    saved = {
        "figure": {}, "steps": [
            "先观察①②③④怎么移动", "比较形状和面积", "用剪拼说明面积不变", "判断方法是否能推导公式"
        ], "answer": "待教师确认（原题未提供图）",
    }
    restored = _repair_courseware_visual(saved, SOURCE)
    assert restored["figure"] == {"type": "parallelogram_methods"}
    assert restored["steps"] == saved["steps"]
    assert restored["answer"] == saved["answer"]
    assert saved["figure"] == {}
    teacher = {**saved, "figure": {"type": "shape", "shape": "parallelogram"}}
    assert _repair_courseware_visual(teacher, SOURCE) == teacher


def test_missing_diagrams_and_placeholder_answers_are_not_marked_ready():
    q = {"stage": 3, "page": 0, "kind": "steps",
         "params": {"figure": {}, "steps": ["一", "二", "三", "四"], "answer": "待教师确认"},
         "approved": None}
    check = audit_example_pages([SOURCE], [q], required_visual_type)
    assert check["flagged"] == 1
    assert check["pages"][0]["expectedFigureType"] == "parallelogram_methods"
    assert any("教学图示" in i for i in check["pages"][0]["issues"])
    assert any("答案仍为待确认" in i for i in check["pages"][0]["issues"])
    generic = audit_example_pages(
        ["第5题 如下图画出一条高，再计算图形面积。"],
        [{"stage": 3, "page": 0, "kind": "steps", "params": q["params"], "approved": None}],
        required_visual_type,
    )
    assert any("课件无图" in i for i in generic["pages"][0]["issues"])


def test_real_teacher_courseware_route_recovers_and_guards_answer(tmp_path):
    spec = importlib.util.spec_from_file_location(
        "four_methods_backup_helpers", Path(__file__).with_name("test_weekend_backup.py")
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    module.helpers.run_isolated(tmp_path, module.COMMON + r'''
import json
SOURCE="第2题 2分\n操作｜四种转化方法辨析\n（2）下面的方法中，也能推导出平行四边形面积公式的有（ ）。点M、N是所在边中点，请观察①②③④的移动、剪拼和旋转方向。"
with TestClient(app) as client:
    th,sh,student,school,lid,qid,wid,sid,base,body=prepare(client)
    with legacy.SessionLocal() as db:
        lesson=db.get(legacy.TeachingLesson,lid)
        lesson.reading_plan=SOURCE
        lesson.examples_json=json.dumps([SOURCE],ensure_ascii=False)
        db.commit()
    url="/teacher/weekend/lessons/"+str(lid)+"/courseware"
    assert client.get(url).status_code==401
    response=client.get(url,headers=th)
    assert response.status_code==200,response.text
    audit=response.json()["qualityAudit"]
    assert audit["pages"][0]["expectedFigureType"]=="parallelogram_methods"
    draft={"stageNo":3,"page":0,"kind":"steps","writtenTask":False,
           "params":{"title":"四种转化方法辨析","problem":SOURCE,
                     "steps":["观察四幅图","说出剪拼路径","比较面积是否改变","解释底与高"],
                     "answer":"待教师确认（原题未提供图）","figure":{}}}
    before=client.get("/teacher/weekend/lessons/"+str(lid)+"/questions",headers=th).json()
    saved=client.put(url,headers=th,json=draft)
    assert saved.status_code==200,saved.text
    assert saved.json()["items"][0]["params"]["figure"]=={"type":"parallelogram_methods"}
    blocked=client.post(url+"/approve",headers=th,json={"stageNo":3,"page":0})
    assert blocked.status_code==400,blocked.text
    assert "核实并填写答案" in blocked.text
    draft["params"]["answer"]="①、③、④（教师核对原题）"
    fixed=client.put(url,headers=th,json=draft)
    assert fixed.status_code==200,fixed.text
    approved=client.post(url+"/approve",headers=th,json={"stageNo":3,"page":0})
    assert approved.status_code==200,approved.text
    assert approved.json()["items"][0]["approved"]["figure"]["type"]=="parallelogram_methods"
    assert client.get("/teacher/weekend/lessons/"+str(lid)+"/questions",headers=th).json()==before
    print("OK")
''')


def test_four_original_options_render_as_svg_in_preview_not_as_answer_key(tmp_path):
    script = r'''
const assert=require('assert');
class E {
  constructor(tag,attrs){this.tag=tag;this.attrs=attrs||{};this.children=[];this._text=(attrs||{}).text||'';this.parentNode=null;}
  appendChild(x){this.children.push(x);x.parentNode=this;return x;}
  setAttribute(k,v){this.attrs[k]=v;}
  set textContent(v){this._text=v;this.children=[];}
  get textContent(){return this._text;}
}
function el(tag,attrs){var n=new E(tag,attrs);for(var i=2;i<arguments.length;i++){var x=arguments[i];if(x)n.appendChild(x)}return n;}
var document={
 createElementNS:function(ns,tag){var node=new E(tag,{});if(tag==='svg')node.createSVGRect=function(){return {}};return node;},
 createElement:function(tag){return new E(tag,{})}
};
function all(node){return [node].concat(node.children.reduce(function(acc,c){return acc.concat(all(c))},[]))}
''' + COURSEWARE_JS + r'''
function preview(step){
 var root=new E('div',{});cwFigure(root,{type:'parallelogram_methods'},false,{previewMode:true,step:step},true,4);
 return root;
}
var a=preview(1),b=preview(4);
var texts=all(a).filter(function(n){return n.tag==='text'}).map(function(n){return n.textContent});
assert(['①','②','③','④','M','N','高'].every(function(w){return texts.indexOf(w)>=0}),texts.join('|'));
assert(all(a).some(function(n){return n.tag==='svg'&&n.attrs.role==='img'}),'draw real vector SVG');
assert.strictEqual(all(a).filter(function(n){return n.tag==='g'&&String(n.attrs.transform||'').indexOf('translate(')===0}).length,4);
assert(all(a).some(function(n){return n.tag==='rect'&&n.attrs.stroke==='#d97706'}),'step 1 highlights first panel');
assert(all(b).some(function(n){return n.tag==='g'&&n.attrs.transform==='translate(570,0)'&&n.children.some(function(c){return c.tag==='rect'&&c.attrs.stroke==='#d97706'})}),'step 4 highlights fourth panel');
assert(!all(a).some(function(n){return String(n.textContent||'').indexOf('①③④正确')>=0}),'diagram does not reveal answer');
console.log('OK');
''';
    path=tmp_path/"four_methods_preview.js"
    path.write_text(script,encoding="utf-8")
    result=subprocess.run(["node",str(path)],capture_output=True,text=True,encoding="utf-8",timeout=25)
    assert result.returncode==0,result.stdout+result.stderr
    assert result.stdout.strip()=="OK"
