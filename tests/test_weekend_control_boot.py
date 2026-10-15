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
 appendChild(n){this.children.push(n);return n}setAttribute(k,v){this[k]=v}
 addEventListener(k,fn){this['on'+k]=fn}querySelectorAll(){return []}
 set textContent(t){this._text=t;this.children=[]}get textContent(){return this._text+this.children.map(n=>n.textContent||'').join(' ')}
}
const rootNode=new Element('div'),back=new Element('a'),calls=[],intervals=[];
global.document={getElementById:()=>rootNode,querySelector:()=>back,createElement:t=>new Element(t),createTextNode:t=>({textContent:t}),addEventListener:()=>{}};
global.window={addEventListener:()=>{}};global.location={search:'?s=42'};
global.localStorage=global.sessionStorage={getItem:k=>k==='v717Token'?'test-token':null};
global.requestAnimationFrame=()=>{};global.setInterval=fn=>{intervals.push(fn);return intervals.length};global.clearInterval=()=>{};
global.alert=t=>{throw Error(t)};
let status='planned';
const state=()=>({title:'民间故事课堂',status,remainingSeconds:600,currentStage:1,stageCount:7,stageName:'导入',goal:'阅读',content:[],stages:[{no:1,name:'导入',minutes:10,extendMin:0}]});
global.fetch=(path,opts)=>{
 calls.push([path,opts.method||'GET']);let data;
 if(path==='/session')data={role:'teacher'};
 else if(path.endsWith('/questions'))data={items:[]};
 else if(path.endsWith('/written'))data={questions:[],items:[],submitted:0,total:0,reviewed:0,pending:0,correct:0,partial:0,submissionRate:0};
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
 assert(rootNode.textContent.includes('简答题与照片批改'));
 const start=nodes(rootNode).find(n=>n.textContent==='开始上课');assert(start,'Start button must render');
 start.onclick();await settle();assert.equal(status,'running');
 assert(nodes(rootNode).some(n=>n.textContent==='下一环节 ›'));
 assert(calls.some(c=>c[0].endsWith('/start')&&c[1]==='POST'));
 assert.equal(intervals.length,2,'Polling and clock must initialize');
 assert.equal(back.href,'/v1/weekend');
})().catch(e=>{console.error(e);process.exitCode=1});
"""
    result=subprocess.run(['node','-e',harness+'\n'+scripts+'\n'+check],text=True,capture_output=True,timeout=20)
    assert result.returncode==0,result.stdout+result.stderr
print("OK")
''')
