from __future__ import annotations

import subprocess

from changying.web.weekend_courseware_pages import COURSEWARE_PLAN_JS
from test_node_script import run_node


def test_courseware_plan_saves_and_applies_school_templates():
    script = r'''
const assert=require('node:assert/strict');
class Element{
 constructor(tag,attrs){this.tag=tag;this.attrs=attrs||{};this.children=[];this.value=this.attrs.value||'';this.hidden=!!this.attrs.hidden;this._text=this.attrs.text||''}
 appendChild(n){this.children.push(n);return n}
 set textContent(t){this._text=t;this.children=[]}get textContent(){return this._text}
 setAttribute(k,v){this.attrs[k]=v}
 addEventListener(name,fn){(this.handlers||(this.handlers={}))[name]=fn}
 querySelectorAll(tag){return all(this,tag)}
}
function all(n,tag){return n.children.flatMap(c=>c instanceof Element?[(c.tag===tag?c:null),...all(c,tag)].filter(Boolean):[])}
function el(tag,attrs,...children){const n=new Element(tag,attrs);children.forEach(c=>n.appendChild(c));return n}
var calls=[],promptAnswer='我的模板',confirmAnswer=true;
function confirm(){return confirmAnswer}
function prompt(){return promptAnswer}
const payload={lessonId:7,subject:'数学',templates:['rotation','clock','steps'],
  kindLabels:{rotation:'旋转',clock:'钟面',steps:'分步讲解'},hasSource:false,pages:{'2':[],'3':['页一']},
  items:[{stage:3,page:0,kind:'steps',status:'draft',approved:null,params:{steps:['第一步','第二步'],answer:'1'},
          writtenTask:false,pageText:'',templateId:null}]};
function api(path,opts){
  calls.push({path:path,opts:opts});
  if(path.indexOf('/courseware/templates')>=0)
    return Promise.resolve({items:[{id:5,name:'两步讲解模板',kind:'steps',kindLabel:'分步讲解',stageNo:3,page:0,writtenTask:false}]});
  if(path.indexOf('/from-template')>=0)return Promise.resolve(payload);
  if(path.indexOf('/save-as-template')>=0)return Promise.resolve({templateId:9,name:'我的模板',kind:'steps'});
  return Promise.resolve(payload);
}
function settle(){return new Promise(r=>setTimeout(r,0))}
''' + COURSEWARE_PLAN_JS + r'''
(async()=>{
 const box=new Element('div');
 cwPlan(box,7,null);await settle();await settle();
 const labels=all(box,'button').map(b=>b.textContent);
 assert(labels.includes('存为模板'),labels.join('|'));
 assert(labels.includes('套用模板'),labels.join('|'));

 // Applying asks this school's templates and posts the chosen one for that page.
 all(box,'button').find(b=>b.textContent==='套用模板').attrs.onclick();await settle();await settle();
 const names=all(box,'b').map(b=>b.textContent);
 assert(names.includes('两步讲解模板'),names.join('|'));
 assert(calls.some(c=>c.path.indexOf('/courseware/templates?subject=')>=0),'must ask this school\'s templates');
 all(box,'button').find(b=>b.textContent==='套用').attrs.onclick();await settle();await settle();
 const applied=calls.filter(c=>c.path.indexOf('/from-template')>=0);
 assert.equal(applied.length,1);
 assert.deepEqual(applied[0].opts.json,{stageNo:3,page:0,templateId:5});

 // Declining the confirm must not apply.
 confirmAnswer=false;
 all(box,'button').find(b=>b.textContent==='套用模板').attrs.onclick();await settle();await settle();
 all(box,'button').find(b=>b.textContent==='套用').attrs.onclick();await settle();
 assert.equal(calls.filter(c=>c.path.indexOf('/from-template')>=0).length,1,'a declined apply must not post');

 // Saving posts the name typed into the prompt for the current page.
 confirmAnswer=true;
 all(box,'button').find(b=>b.textContent==='存为模板').attrs.onclick();await settle();await settle();
 const saved=calls.filter(c=>c.path.indexOf('/save-as-template')>=0);
 assert.equal(saved.length,1);
 assert.equal(saved[0].opts.json.name,'我的模板');
 assert.equal(saved[0].opts.json.stageNo,3);
 console.log('OK');
})().catch(e=>{console.error(e);process.exitCode=1});
'''
    result = run_node(script, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
