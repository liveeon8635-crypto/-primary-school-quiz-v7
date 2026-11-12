"""Regression: mixed weekend lesson review follows the source numbering."""
from __future__ import annotations

from changying.web.weekend_pages import PLAN_JS
from test_node_script import run_node


def test_mixed_choice_and_written_keep_original_numbered_order():
    script = r'''
const assert=require('node:assert/strict');
class Element {
 constructor(tag,attrs){this.tag=tag;this.attrs=attrs||{};this.children=[];this.value=this.attrs.value||'';this.hidden=!!this.attrs.hidden;this.disabled=!!this.attrs.disabled;this._text=this.attrs.text||'';this.open=false}
 appendChild(n){this.children.push(n);return n}
 set textContent(t){this._text=t;this.children=[]}get textContent(){return this._text}
 setAttribute(k,v){this.attrs[k]=v}addEventListener(){}querySelectorAll(tag){return all(this,tag)}
}
function all(n,tag){return n.children.flatMap(c=>c instanceof Element?[(c.tag===tag?c:null),...all(c,tag)].filter(Boolean):[])}
function el(tag,attrs,...children){const n=new Element(tag,attrs);children.forEach(c=>n.appendChild(c));return n}
var root=new Element('div'),location={href:''};
function growTextarea(){}function boot(){}function confirm(){return true}
const row={lessonId:11,lessonNo:11,hasPlan:true,approvedQuestions:0,draftQuestions:5};
const stems=[
 '（1）将平行四边形沿一条高剪开，把剪下的三角形平移到另一侧，拼成一个长方形。',
 '（2）观察两个平行四边形的底与高，说明为什么底和高需要一一对应。',
 '把两个完全相同的三角形拼成平行四边形，解释面积公式中的除以二。',
 '没有原文对应序号的补充题目'
];
let gets=0,posts=0;
function api(path,opts){
 if(path==='/teacher/weekend/next')return Promise.resolve({items:[]});
 if(path.startsWith('/teacher/weekend/schedule'))return Promise.resolve({items:[row]});
 if(path==='/teacher/weekend/lessons/11')return Promise.resolve({
  title:'多边形的面积',coreTarget:'面积推导',teacherPlan:'转化',ppt:[],examples:[],closureTraining:'',
  sourceText:'第1题 4分\n'+stems[0]+'\n'+stems[1]+'\n第3题 4分\n'+stems[2]+'\n第4题 4分\n面积单位选择题。'
 });
 if(path.endsWith('/written/questions')){
  if(opts){posts++;return Promise.resolve({...row,approvedQuestions:posts})}
  gets++;return Promise.resolve({items:stems.map((s,i)=>({id:i+21,type:'short_answer',stem:s,reference:'仅教师可见',approved:false,hints:[]}))});
 }
 if(path.endsWith('/questions')){
  if(opts){posts++;return Promise.resolve({...row,approvedQuestions:posts})}
  gets++;return Promise.resolve({items:[{id:4,stem:'第4题 4分｜面积单位选择题',options:['甲','乙'],correctIndex:1,active:false}]});
 }
 throw Error(path);
}
async function settle(){for(let i=0;i<20;i++)await Promise.resolve()}
''' + PLAN_JS + r'''
(async()=>{
 plan();await settle();
 all(root,'button').find(n=>n.textContent==='审改').attrs.onclick();await settle();
 all(root,'button').filter(n=>n.attrs.role==='tab')[1].attrs.onclick();
 const review=all(root,'div').find(n=>n.attrs['data-review-list']==='true');
 assert(review,'the combined review list must be rendered');
 assert.deepEqual(review.children.map(n=>n.attrs['data-review-group']||n.attrs['data-review-number']||''),['1','3','4','']);
 const group=review.children[0];
 assert.equal(group.tag,'section');
 assert.deepEqual(group.children.slice(1).map(n=>n.attrs['data-review-number']),['1','1']);
 assert(group.children[0].textContent.includes('第 1 题'));
 const headings=all(group,'b').map(n=>n.textContent);
 assert(headings.includes('第 1 题（1）'));
 assert(headings.includes('第 1 题（2）'));
 assert(all(group.children[1],'p').some(n=>!n.textContent.startsWith('（1）')),'question text does not duplicate part numbering');
 const note=all(root,'p').find(n=>n.textContent.includes('未能可靠识别原文序号'));
 assert(note && note.textContent.includes('1道题'),'unknown order must be marked rather than guessed');
 const cards=review.children.slice();
 const originalGets=gets;
 const approve=all(root,'button').filter(n=>n.textContent==='通过');
 assert.equal(approve.length,5);
 // Approval of a written card must not reorder/collapse other live cards.
 approve[0].attrs.onclick();await settle();
 assert.equal(posts,1);
 assert.equal(gets,originalGets);
 assert.deepEqual(review.children,cards);
 assert.equal(all(root,'span').find(n=>n.attrs['data-start-reason']).textContent,'');
})().catch(e=>{console.error(e);process.exitCode=1});
'''
    result = run_node(script, timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr
