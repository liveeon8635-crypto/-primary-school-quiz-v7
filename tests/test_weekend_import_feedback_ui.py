from __future__ import annotations

from changying.web.weekend_pages import PLAN_JS
from test_node_script import run_node


def test_lesson_row_shows_import_failure_next_to_its_own_button():
    """A failed 导入教案/整包 must be visible at the row, not only above the list."""

    script = r'''
const assert=require('node:assert/strict');
class Element{
 constructor(tag,attrs){this.tag=tag;this.attrs=attrs||{};this.children=[];this.value=this.attrs.value||'';this.hidden=!!this.attrs.hidden;this.disabled=!!this.attrs.disabled;this._text=this.attrs.text||'';this.className=this.attrs.class||''}
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
var calls=[],importError=null;
function api(path,opts){
 calls.push({path:path,opts:opts});
 if(path.indexOf('/teacher/weekend/lessons/import')===0)return Promise.reject(importError);
 if(path.indexOf('/teacher/weekend/next')===0)return Promise.resolve({items:[]});
 if(path.indexOf('/teacher/weekend/schedule')===0)return Promise.resolve({items:[
   {lessonNo:3,hasPlan:false,lessonId:null,approvedQuestions:0,draftQuestions:0,title:'第3课 小数乘法'}]});
 return Promise.resolve({});
}
function growTextarea(){}function boot(){}function fmt(){return ''}function msg(){}
function settle(){return new Promise(function(r){setTimeout(r,0)})}
function byTag(tag){return all(root,tag)}
''' + PLAN_JS + r'''
(async()=>{
 plan();
 await settle();await settle();

 const inputs=byTag('input').filter(n=>String(n.attrs.accept||'').indexOf('.docx')===0&&!n.attrs.multiple);
 assert.equal(inputs.length,1,'the lesson row must render one file input');
 const fileIn=inputs[0];
 assert(fileIn.handlers&&fileIn.handlers.change,'choosing a file must be handled');

 // A rejected upload: the row must say so, next to the button, with the status code.
 const err=new Error('旧版 Word（.doc）暂不支持，请用 Word/WPS 打开后「另存为」.docx 再导入');
 err.status=400;
 importError=err;
 fileIn.files=[{name:'第03课-教案.doc'}];
 fileIn.handlers.change();
 await settle();await settle();

 const boxes=byTag('div').filter(n=>n.attrs['data-import-feedback']==='1');
 assert.equal(boxes.length,1,'one inline feedback area per lesson row');
 const shown=boxes[0].textContent;
 assert(shown.indexOf('导入失败（400）：')===0,shown);
 assert(shown.includes('另存为'),shown);
 assert(shown.includes('你选的文件不会被改动'),shown);
 assert.equal(boxes[0].className,'notice error');

 const buttons=byTag('button');
 const impBtn=buttons.find(b=>b.textContent==='导入教案/整包');
 assert(impBtn,'the import button must be identifiable again');
 assert(!impBtn.disabled,'the button must be usable after a failure');

 // The failure must not be reported only in the page-level note above the list.
 assert(!buttons.some(b=>b.textContent==='正在导入…'),'the busy label must be cleared');

 console.log('OK');
})().catch(e=>{console.error(e);process.exitCode=1});
'''

    result = run_node(script)
    assert result.returncode == 0, result.stdout + result.stderr
