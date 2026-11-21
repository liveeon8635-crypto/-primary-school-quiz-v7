from __future__ import annotations

from changying.web.weekend_pages import PLAN_JS
from test_node_script import run_node


def test_approvals_keep_question_nodes_open_material_and_unsaved_answers():
    script=r'''
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
const row={lessonId:1,lessonNo:6,hasPlan:true,approvedQuestions:0,draftQuestions:10};
let gets=0,posts=0,fail=false,finish;
function api(path,opts){
 if(path==='/teacher/weekend/next')return Promise.resolve({items:[]});
 if(path.startsWith('/teacher/weekend/schedule'))return Promise.resolve({items:[row,{lessonId:null,lessonNo:7,hasPlan:false,approvedQuestions:0,draftQuestions:0}]});
 if(path.endsWith('/questions')){
  if(opts){posts++;return new Promise((resolve,reject)=>{finish=()=>fail?reject(Error('审核暂时失败')):resolve({...row,approvedQuestions:posts})})}
  gets++;
  if(path.endsWith('/written/questions'))return Promise.resolve({items:Array.from({length:9},(_,i)=>({id:i+11,type:'short_answer',stem:'原文材料'+i+'\n\n简答题'+i,reference:'教师参考'+i,approved:false,hints:[]}))});
  return Promise.resolve({items:[{id:1,stem:'选择题',options:['甲','乙'],correctIndex:0,active:false}]});
 }
 if(path==='/teacher/weekend/lessons/1')return Promise.resolve({title:'阅读',coreTarget:'概括',teacherPlan:'教学流程',sourceText:'完整原文',ppt:[],examples:[],closureTraining:''});
 throw Error(path);
}
async function settle(){for(let i=0;i<15;i++)await Promise.resolve()}
''' + PLAN_JS + r'''
(async()=>{
 plan();await settle();
 // 开课 is grey with its reason written beside it (tooltips are invisible on tablets).
 const reasons=all(root,'span').filter(n=>n.attrs['data-start-reason']).map(n=>n.textContent);
 assert.deepEqual(reasons,['还差：在“习题审核”里至少通过 1 道习题（现有 10 道草稿待审）','还差：先导入教案或让 AI 写教案，才能开课']);
 all(root,'button').find(n=>n.textContent==='教案与题目审核').attrs.onclick();await settle();
 all(root,'button').filter(n=>n.attrs.role==='tab')[1].attrs.onclick();
 const originalGets=gets,originalAreas=all(root,'textarea'),material=all(root,'details').find(n=>n.children[0].textContent==='展开阅读材料／题目全文');
 material.open=true;const draft=originalAreas.find(n=>n.value==='教师参考8');draft.value='第九题未保存的评分要点';
 const approve=all(root,'button').filter(n=>n.textContent==='通过');assert.equal(approve.length,10);
 // Approving one written question must not collapse/rebuild all nine cards.
 approve[1].attrs.onclick();await settle();assert(approve[1].disabled);assert.equal(gets,originalGets);
 approve[1].attrs.onclick();assert.equal(posts,1,'Duplicate approval should not submit twice');
 finish();await settle();
 assert.equal(gets,originalGets,'Approving a question must not reload/collapse the whole list');
 assert.deepEqual(all(root,'textarea'),originalAreas);assert.equal(draft.value,'第九题未保存的评分要点');assert(material.open);
 assert.equal(approve[1].textContent,'已通过');assert(approve[1].disabled);
 assert(!all(root,'button').find(n=>n.textContent==='开课').disabled);
 assert.equal(all(root,'span').find(n=>n.attrs['data-start-reason']).textContent,'');
 // The selection-question path has the same position guarantee.
 approve[0].attrs.onclick();finish();await settle();assert.equal(gets,originalGets);assert.equal(approve[0].textContent,'已通过');
 // Failure stays beside the current question, re-enables retry, and retains edits.
 fail=true;approve[2].attrs.onclick();finish();await settle();assert(!approve[2].disabled);
 assert(all(root,'div').some(n=>n.textContent==='审核暂时失败'));assert.equal(draft.value,'第九题未保存的评分要点');
 assert.equal(gets,originalGets);assert.equal(location.href,'');
})().catch(e=>{console.error(e);process.exitCode=1});
'''
    result=run_node(script,timeout=20)
    assert result.returncode==0,result.stdout+result.stderr
