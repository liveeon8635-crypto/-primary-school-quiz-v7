"""Regression coverage for the 18 lesson weekend planning navigator."""
from __future__ import annotations

from changying.web.weekend_pages import PLAN_JS
from test_node_script import run_node


def test_weekend_plan_navigates_lessons_keeps_focus_and_saves_all_rows():
    script = r'''
const assert=require('node:assert/strict');
class TextNode {constructor(text){this.textContent=String(text)}}
class Element {
 constructor(tag,attrs){this.tag=tag;this.attrs=attrs||{};this.children=[];this.parentNode=null;this.value=this.attrs.value||'';this.hidden=!!this.attrs.hidden;this.disabled=!!this.attrs.disabled;this.open=!!this.attrs.open;this._text=this.attrs.text||'';this.className=''}
 appendChild(n){this.children.push(n);if(n&&typeof n==='object')n.parentNode=this;return n}
 set textContent(t){this._text=String(t);this.children=[]}get textContent(){return this._text+this.children.map(c=>c&&c.textContent||'').join('')}
 setAttribute(k,v){this.attrs[k]=String(v)}getAttribute(k){return Object.prototype.hasOwnProperty.call(this.attrs,k)?this.attrs[k]:null}
 addEventListener(type,fn){this.attrs['on'+type]=fn}querySelectorAll(tag){return all(this,tag)}scrollIntoView(){}
 get lastElementChild(){return this.children.filter(x=>x instanceof Element).slice(-1)[0]||null}
}
function all(n,tag){return n.children.flatMap(c=>c instanceof Element?[(c.tag===tag?c:null),...all(c,tag)].filter(Boolean):[])}
var root=new Element('div'),location={search:'',href:''},document={getElementById:()=>root,createElement:t=>new Element(t,{}),createTextNode:t=>new TextNode(t)};
var el=function(tag,attrs){const n=document.createElement(tag);Object.keys(attrs||{}).forEach(k=>{if(k==='class')n.className=attrs[k];else if(k==='text')n.textContent=attrs[k];else if(k.slice(0,2)==='on')n.addEventListener(k.slice(2),attrs[k]);else if(attrs[k]===true)n.setAttribute(k,'');else if(attrs[k]!==false&&attrs[k]!=null)n.setAttribute(k,attrs[k])});for(let i=2;i<arguments.length;i++){const c=arguments[i];if(c!=null)n.appendChild(typeof c==='string'?document.createTextNode(c):c)}return n};
function requestAnimationFrame(fn){fn()} function growTextarea(){} function boot(){} function confirm(){return true}
const rows=Array.from({length:18},(_,i)=>({lessonId:100+i,lessonNo:i+1,subject:'数学',hasPlan:true,taught:false,title:'课次'+(i+1),approvedQuestions:1,practiceReady:1,draftQuestions:i===3?2:0,schoolWeek:null,schoolUnit:'',plannedDate:''}));
let savedRows=null,deleted=false;
function api(path,opts){
 if(path==='/teacher/weekend/next')return Promise.resolve({items:[{subject:'数学',lessonNo:7,done:false,schoolUnit:'当前进度',plannedDate:'',weakKnowledge:[],tips:['备课提示']}]});
 if(path.startsWith('/teacher/weekend/schedule')){
  if(opts&&opts.method==='PUT'){savedRows=opts.json.rows;return Promise.resolve({})}
  return Promise.resolve({items:rows});
 }
 if(path==='/teacher/weekend/lessons/103'&&opts&&opts.method==='DELETE'){deleted=true;return Promise.resolve({message:'已删除'})}
 throw Error(path);
}
async function settle(){for(let i=0;i<40;i++)await Promise.resolve()}
''' + PLAN_JS + r'''
(async()=>{
 plan();await settle();
 const nav=all(root,'div').find(n=>n.attrs['data-lesson-navigation']==='true');assert(nav,'lesson navigation exists');
 const cards=all(root,'b').filter(n=>/^第 \d+ 次$/.test(n.textContent)).map(n=>n.parentNode.parentNode);
 assert.equal(cards.length,18,'all lesson cards stay in the DOM');
 assert.equal(cards[6].hidden,false,'the server selected next lesson 7 by default');
 assert(cards.filter((c,i)=>i!==6).every(c=>c.hidden),'only the current lesson is shown');
 assert.equal(all(root,'details').filter(n=>n.className==='card').every(n=>!n.open),true,'low frequency cards start collapsed');
 let navButtons=all(nav,'button');navButtons.find(b=>b.textContent==='下一课 ›').onclick();
 assert.equal(cards[7].hidden,false,'next lesson focuses lesson 8');
 navButtons=all(nav,'button');navButtons.find(b=>b.textContent==='‹ 上一课').onclick();assert.equal(cards[6].hidden,false);
 let capsules=all(nav,'button').filter(b=>b.attrs['data-lesson-no']);assert.equal(capsules.length,18);
 capsules[3].attrs.onclick();assert.equal(cards[3].hidden,false,'lesson capsule jumps to lesson 4');
 navButtons=all(nav,'button');navButtons.find(b=>b.textContent==='展开全部 18 次课').onclick();assert(cards.every(c=>!c.hidden));
 navButtons=all(nav,'button');navButtons.find(b=>b.textContent==='只看当前课').onclick();assert.equal(cards[3].hidden,false);assert.equal(cards.filter(c=>!c.hidden).length,1);
 const deleteButton=all(cards[3],'button').find(b=>b.textContent==='删除教案');assert(deleteButton);deleteButton.attrs.onclick();await settle();
 assert(deleted);assert.equal(cards[3].hidden,false,'load() after delete keeps lesson 4 selected');
 all(root,'button').find(b=>b.textContent==='保存进度表').attrs.onclick();await settle();
 assert.equal(savedRows.length,18,'save still submits every lesson when only one card is visible');
 assert.deepEqual(savedRows.map(r=>r.lessonNo),Array.from({length:18},(_,i)=>i+1));
 console.log('OK');
})().catch(e=>{console.error(e);process.exitCode=1});
'''
    result = run_node(script, timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr
