from __future__ import annotations

import subprocess

from changying.web.weekend_pages import PLAN_JS


def test_batch_card_previews_then_imports_and_reports_each_file():
    script = r'''
const assert=require('node:assert/strict');
class Element{
 constructor(tag,attrs){this.tag=tag;this.attrs=attrs||{};this.children=[];this.value=this.attrs.value||'';this.hidden=!!this.attrs.hidden;this.disabled=!!this.attrs.disabled;this._text=this.attrs.text||''}
 appendChild(n){this.children.push(n);return n}
 set textContent(t){this._text=t;this.children=[]}get textContent(){return this._text}
 setAttribute(k,v){this.attrs[k]=v}
 addEventListener(name,fn){(this.handlers||(this.handlers={}))[name]=fn}
 querySelectorAll(tag){return all(this,tag)}
}
function all(n,tag){return n.children.flatMap(c=>c instanceof Element?[(c.tag===tag?c:null),...all(c,tag)].filter(Boolean):[])}
function el(tag,attrs,...children){const n=new Element(tag,attrs);children.forEach(c=>n.appendChild(c));return n}
var root=new Element('div'),location={href:''};
var confirmAnswer=true;function confirm(){return confirmAnswer}
class FormData{constructor(){this.fields=[]}append(k,v){this.fields.push([k,v])}}
var calls=[],reply=null;
function api(path,opts){calls.push({path:path,opts:opts});return Promise.resolve(reply)}
function growTextarea(){}function boot(){}function fmt(){return ''}function msg(){}
function settle(){return new Promise(function(r){setTimeout(r,0)})}
''' + PLAN_JS + r'''
(async()=>{
 // 1. Preview lists every file and marks the one that would be overwritten.
 const panel=new Element('div');
 const picked=[{name:'a.docx'},{name:'b.docx'},{name:'c.docx'}];
 const preview={items:[
   {filename:'第03课-民间英雄.docx',lessonNo:3,ok:true,hasPlan:true,error:''},
   {filename:'第04课.docx',lessonNo:4,ok:true,hasPlan:false,error:''},
   {filename:'教案.docx',lessonNo:null,ok:true,hasPlan:false,error:''}],detected:2,ready:2};
 const go=batchPlanPanel(preview,picked,panel,function(){});
 const texts=all(panel,'span').map(n=>n.textContent);
 assert(texts.includes('第 3 课（已有教案，会覆盖）'),texts.join('|'));
 assert(texts.includes('第 4 课'),texts.join('|'));
 assert(texts.includes('文件名里看不出课次'),texts.join('|'));
 assert.equal(go.textContent,'确认导入 2 节');

 // 2. Declining the overwrite prompt must not call the batch endpoint.
 confirmAnswer=false;go.attrs.onclick();await settle();
 assert.equal(calls.filter(c=>c.path.endsWith('/batch')).length,0,'declined import must not post');

 // 3. Confirming sends subject + force=1 + all files, then shows each result.
 reply={items:[{filename:'第03课-民间英雄.docx',lessonNo:3,ok:true,error:''},
               {filename:'第04课.docx',lessonNo:4,ok:true,error:''},
               {filename:'教案.docx',lessonNo:null,ok:false,error:'没能从文件名看出课次'}],
        imported:2,failed:1,message:'成功导入 2 节，失败 1 节（失败的文件可以单独重试）'};
 confirmAnswer=true;go.attrs.onclick();await settle();await settle();
 const batch=calls.filter(c=>c.path.endsWith('/batch'));
 assert.equal(batch.length,1);
 const fields=batch[0].opts.body.fields;
 assert.deepEqual(fields.filter(f=>f[0]==='subject'),[['subject','数学']]);
 assert.deepEqual(fields.filter(f=>f[0]==='force'),[['force','1']],'an overwrite must be forced');
 assert.equal(fields.filter(f=>f[0]==='files').length,3);
 const shown=all(panel,'span').map(n=>n.textContent);
 assert(shown.includes('第 3 课已导入'),shown.join('|'));
 assert(shown.some(t=>t.indexOf('没导入：')===0),shown.join('|'));
 assert(all(panel,'div').some(n=>n.textContent.indexOf('成功导入 2 节')===0),'the summary must be shown');

 // 4. Nothing readable: warn and offer no confirm button.
 const empty=new Element('div');
 const none=batchPlanPanel({items:[{filename:'x.pdf',lessonNo:null,ok:false,error:'没有读到足够的文字'}],detected:0,ready:0},[{name:'x.pdf'}],empty,function(){});
 assert.equal(none,null);
 assert(all(empty,'div').some(n=>n.textContent.indexOf('没有可以导入的文件')===0));
 assert.equal(all(empty,'button').length,0);

 // 5. Editing an existing plan without overwrite keeps force at 0.
 confirmAnswer=true;
 const safe=new Element('div');
 const safeGo=batchPlanPanel({items:[{filename:'第05课.docx',lessonNo:5,ok:true,hasPlan:false,error:''}],detected:1,ready:1},[{name:'e.docx'}],safe,function(){});
 reply={items:[{filename:'第05课.docx',lessonNo:5,ok:true,error:''}],imported:1,failed:0,message:'成功导入 1 节，失败 0 节'};
 safeGo.attrs.onclick();await settle();await settle();
 const last=calls.filter(c=>c.path.endsWith('/batch')).pop();
 assert.deepEqual(last.opts.body.fields.filter(f=>f[0]==='force'),[['force','0']]);
 console.log('OK');
})().catch(e=>{console.error(e);process.exitCode=1});
'''
    result = subprocess.run(["node", "-e", script], text=True, capture_output=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
