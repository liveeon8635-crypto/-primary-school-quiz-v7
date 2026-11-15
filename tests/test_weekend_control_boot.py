"""Run the real routed classroom script through boot and start."""
from __future__ import annotations
import importlib.util
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('weekend_boot_helpers',ROOT/'tests/test_homework_solve.py')
helpers=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=helpers
spec.loader.exec_module(helpers)

HARNESS=r'''
const assert=require('node:assert/strict');
class Element {
 constructor(tag){this.tag=tag;this.children=[];this.style={};this._text='';this.disabled=false}
 remove(){this.removed=true}appendChild(n){this.children.push(n);return n}setAttribute(k,v){if(k==='style')this.style.cssText=v;else this[k]=v}
 addEventListener(k,fn){this['on'+k]=fn}querySelectorAll(){return []}
 set textContent(t){this._text=t;this.children=[]}get textContent(){return this._text+this.children.map(n=>n.textContent||'').join(' ')}
}
const rootNode=new Element('div'),back=new Element('a'),calls=[],intervals=[];
global.document={body:new Element('body'),getElementById:()=>rootNode,querySelector:()=>back,createElement:t=>new Element(t),createTextNode:t=>({textContent:t}),addEventListener:()=>{}};
global.window={addEventListener:()=>{}};global.location={search:'?s=42'};
global.localStorage=global.sessionStorage={getItem:k=>k==='v717Token'?'test-token':null};
global.requestAnimationFrame=()=>{};global.setInterval=fn=>{intervals.push(fn);return intervals.length};global.clearInterval=()=>{};
global.alert=t=>{throw Error(t)};
let status='planned';
const state=()=>({title:'民间故事课堂',class:{id:1,name:'五年级语文班',studentCount:3},status,remainingSeconds:600,currentStage:1,stageCount:7,stageName:'导入',goal:'阅读',content:[],stages:[{no:1,name:'导入',minutes:10,extendMin:0}]});
global.fetch=(path,opts)=>{
 calls.push([path,opts.method||'GET']);let data;
 if(path==='/session')data={role:'teacher'};
 else if(path.endsWith('/questions'))data={items:[]};
 else if(path.endsWith('/written'))data={status,questions:[],items:[],submitted:0,total:0,reviewed:0,pending:0,correct:0,partial:0,submissionRate:0};
 else if(path.endsWith('/progress'))data={items:[],classCompletionRate:0};
 else if(path.endsWith('/start')){status='running';data=state()}
 else if(path==='/teacher/weekend/sessions/42')data=state();
 else throw Error('Unexpected request '+path);
 return Promise.resolve({ok:true,json:()=>Promise.resolve(data)});
};
function nodes(n){return [n,...(n.children||[]).flatMap(nodes)]}
async function settle(){for(let i=0;i<40;i++)await Promise.resolve()}
'''


def test_routed_control_boots_and_starts_without_missing_card_function(tmp_path):
    helpers.run_isolated(tmp_path,helpers.COMMON+'\nharness='+repr(HARNESS)+'\n'+r'''
import re,subprocess
with TestClient(app) as client:
    response=client.get('/v1/weekend?s=42')
    assert response.status_code==200
    scripts='\n'.join(re.findall(r'<script[^>]*>(.*?)</script>',response.text,re.S))
    check=r"""
(async()=>{
 await settle();assert(rootNode.textContent.includes('民间故事课堂'),rootNode.textContent);
 assert(rootNode.textContent.includes('学生作答与批改'));
 const addForm=nodes(rootNode).find(n=>n.tag==='details'&&n.textContent.includes('临时补充一道题'));assert(addForm&&!addForm.hidden);
 const start=nodes(rootNode).find(n=>n.textContent==='开始上课');assert(start,'Start button must render');
 start.onclick();await settle();assert.equal(status,'running');assert(addForm.hidden,'Hide question authoring as soon as class starts');
 assert(nodes(rootNode).some(n=>n.textContent==='下一环节 ›'));
 assert(calls.some(c=>c[0].endsWith('/start')&&c[1]==='POST'));
 assert.equal(intervals.length,2,'Polling and clock must initialize');
 assert.equal(back.href,'/v1/weekend');
})().catch(e=>{console.error(e);process.exitCode=1});
"""
    result=subprocess.run(['node'],input=harness+'\n'+scripts+'\n'+check,text=True,capture_output=True,timeout=20)
    assert result.returncode==0,result.stdout+result.stderr
print("OK")
''')


def test_board_new_context_consumes_staged_login_and_popup_fallback(tmp_path):
    helpers.run_isolated(tmp_path,helpers.COMMON+'\nharness='+repr(HARNESS)+'\n'+r'''
import re,subprocess,json
with TestClient(app) as client:
    scripts={}
    for key,url in [('control','/v1/weekend?s=42'),('board','/v1/weekend-board?s=42')]:
        response=client.get(url)
        assert response.status_code==200
        scripts[key]='\n'.join(re.findall(r'<script[^>]*>(.*?)</script>',response.text,re.S))
    check=r"""
const vm=require('node:vm'),assert=require('node:assert/strict');
async function scenario(blocked){
 const net={staged:false,consumed:0,release:null},popup={opener:{},location:{href:'about:blank'}};
 const c={console,require,URLSearchParams,net,popup,blocked};c.global=c;vm.createContext(c);
 vm.runInContext(HARNESS+`
 let clickHandler;
 document.addEventListener=(event,fn)=>{if(event==='click')clickHandler=fn};
 window.open=(url,target)=>{assert.equal(url,'about:blank');return blocked?null:popup};
 const baseFetch=fetch;
 fetch=(path,opts)=>{
  if(path==='/v1/auth-handoff'){
   assert.equal(opts.headers.Authorization,'Bearer test-token');
   assert.equal(opts.credentials,'same-origin');
   return new Promise(resolve=>{net.release=()=>{net.staged=true;resolve({ok:true})}});
  }
  return baseFetch(path,opts);
 };
 `+SCRIPTS.control,c);
 await vm.runInContext('settle()',c);
 vm.runInContext(`
 const link=nodes(rootNode).find(n=>n.tag==='a'&&n.textContent==='打开大屏');assert(link);
 assert.equal(link['data-cy-open-window'],'1');assert.equal(typeof clickHandler,'function');
 link.getAttribute=k=>link[k];
 clickHandler({target:{closest:selector=>selector==='a[data-cy-open-window]'?link:null},preventDefault(){},stopPropagation(){}});
 assert(net.release,'Click must stage handoff');
 assert.equal(popup.location.href,'about:blank','Do not navigate before handoff completes');
 if(!blocked)assert.equal(popup.opener,null);
 net.release();
 `,c);
 await vm.runInContext('settle()',c);
 const href=blocked?c.location.href:popup.location.href;
 assert.equal(href,'/v1/weekend-board?s=42');assert(!href.includes('token'));
 const b={console,require,URLSearchParams,net};b.global=b;vm.createContext(b);
 vm.runInContext(HARNESS+`
 localStorage={getItem:()=>null,setItem:()=>{throw Error('Must not persist login')}};
 const saved={};sessionStorage={getItem:k=>saved[k]||null,setItem:(k,v)=>{saved[k]=v}};
 fetch=(path,opts)=>{
  let data;
  if(path==='/v1/auth-handoff/consume'){
   assert(net.staged);net.staged=false;net.consumed++;assert.equal(opts.credentials,'same-origin');
   data={token:'test-token',userID:7,role:'teacher'};
  }else{
   assert.equal(opts.headers.Authorization,'Bearer test-token');
   if(path==='/session')data={role:'teacher'};
   else if(path==='/teacher/weekend/sessions/42/board')data=state();
   else throw Error(path);
  }
  return Promise.resolve({ok:true,json:()=>Promise.resolve(data)});
 };
 `+SCRIPTS.board,b);
 await vm.runInContext('settle()',b);
 vm.runInContext(`assert(rootNode.textContent.includes('马上开始上课'),rootNode.textContent);assert.equal(saved.v717Token,'test-token');assert.equal(intervals.length,2)`,b);
 assert.equal(net.consumed,1);
}
(async()=>{await scenario(false);await scenario(true)})().catch(e=>{console.error(e);process.exitCode=1});
"""
    script='const HARNESS='+json.dumps(harness)+';const SCRIPTS='+json.dumps(scripts)+';\n'+check
    result=subprocess.run(['node'],input=script,text=True,capture_output=True,timeout=20)
    assert result.returncode==0,result.stdout+result.stderr
print('OK')
''')


def test_teacher_selects_one_class_before_creating_classroom(tmp_path):
    helpers.run_isolated(tmp_path,helpers.COMMON+'\nharness='+repr(HARNESS)+'\n'+r'''
import re,subprocess
with TestClient(app) as client:
    scripts='\n'.join(re.findall(r'<script[^>]*>(.*?)</script>',client.get('/v1/weekend').text,re.S))
    network=r"""
const originalFetch=fetch;let created=null;
fetch=(path,opts)=>{
 if(path==='/teacher/weekend/classes')return Promise.resolve({ok:true,json:()=>Promise.resolve({items:[{id:101,name:'甲班',studentCount:2},{id:202,name:'乙班',studentCount:3}]})});
 if(path==='/teacher/weekend/sessions'&&opts.method==='POST'){created=JSON.parse(opts.body);return Promise.resolve({ok:true,json:()=>Promise.resolve({id:77})})}
 return originalFetch(path,opts);
};
"""
    check=r"""
(async()=>{
 await settle();createWeekendClassroom(99);await settle();assert.equal(created,null,'No all-teacher default roster');
 const choice=nodes(document.body).find(n=>n.tag==='button'&&n.textContent==='乙班（3人）');assert(choice);
 choice.onclick();await settle();assert.deepEqual(created,{lessonId:99,classId:202,requireReady:true});
 assert.equal(location.href,'/v1/weekend?s=77');
})().catch(e=>{console.error(e);process.exitCode=1});
"""
    result=subprocess.run(['node'],input=harness+network+scripts+check,text=True,capture_output=True,timeout=20)
    assert result.returncode==0,result.stdout+result.stderr
print('OK')
''')


def test_running_board_fits_text_and_refits_on_resize(tmp_path):
    helpers.run_isolated(tmp_path,helpers.COMMON+'\nharness='+repr(HARNESS)+'\n'+r'''
import re,subprocess
with TestClient(app) as client:
    scripts='\n'.join(re.findall(r'<script[^>]*>(.*?)</script>',client.get('/v1/weekend-board?s=42').text,re.S))
    geometry=r"""
window.innerHeight=720;let onResize=null,paintCount=0;
window.addEventListener=(name,fn)=>{if(name==='resize')onResize=fn};
requestAnimationFrame=fn=>fn();
Object.defineProperties(Element.prototype,{
 clientHeight:{get(){return 420}},clientWidth:{get(){return 1000}},
 scrollHeight:{get(){return (parseFloat(this.style.fontSize)||48)*20}},
 scrollWidth:{get(){return 900}}
});
const text='完整阅读材料和例题说明'.repeat(20);
fetch=(path,opts)=>Promise.resolve({ok:true,json:()=>Promise.resolve(path==='/session'?{role:'teacher'}:{...state(),status:'running',deck:{total:8,index:0},content:[text]})});
"""
    check=r"""
(async()=>{
 await settle();assert(rootNode.textContent.includes(text));
 const body=nodes(rootNode).find(n=>n.style.fontSize);assert(body);
 assert(body.scrollHeight<=body.clientHeight);assert(body.scrollWidth<=body.clientWidth);
 assert(parseFloat(body.style.fontSize)<32,'Reduce text size to available screen height');
 assert.equal(typeof onResize,'function');onResize();assert(rootNode.textContent.includes(text));
 assert.equal(document.body.style.overflow,'hidden');
 assert.equal(intervals.length,2);
})().catch(e=>{console.error(e);process.exitCode=1});
"""
    result=subprocess.run(['node'],input=harness+geometry+scripts+check,text=True,capture_output=True,timeout=20)
    assert result.returncode==0,result.stdout+result.stderr
print('OK')
''')
