from __future__ import annotations
import importlib.util
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('student_home_helpers',ROOT/'tests/test_homework_solve.py')
helpers=importlib.util.module_from_spec(spec);sys.modules[spec.name]=helpers;spec.loader.exec_module(helpers)


def test_actual_classic_entry_shows_live_class_and_only_available_learning(tmp_path):
    helpers.run_isolated(tmp_path,helpers.COMMON+r'''
import re,subprocess
with TestClient(app) as client:
    response=client.get('/classic?legacy=1&unified=1&page=syncLearning')
    assert response.status_code==200,response.text
    html=response.text
    start=html.index('async function syncLearning(){');end=html.index('\n}\n',start)+2
    script=html[start:end]
    assert 'student-current-class' in script and 'cy-wk-band' not in html
    node=r"""
const assert=require('node:assert/strict');
const page={innerHTML:''},panel={innerHTML:'',children:[],appendChild(n){this.children.push(n)}};
let active=true,failOverview=false,timer;
var state={},window={},document={hidden:false,getElementById:()=>panel,querySelectorAll:()=>[],createElement:()=>({})};
function $(selector){assert.equal(selector,'#page');return page}
function esc(x){return String(x||'').replaceAll('<','&lt;')}
function head(title,description){return '<h1>'+title+'</h1><p>'+description+'</p>'}
function setInterval(fn){timer=fn;return 1}function clearInterval(){}
function api(path){
 if(path==='/student/weekend/current')return Promise.resolve(active?{active:true,sessionId:7,title:'本班民间故事课',className:'语文甲班',stageName:'随堂练习',practice:true}:{active:false});
 if(path==='/student/teaching/overview')return failOverview?Promise.reject(Error('No old program')):Promise.resolve({gradeMatch:true,lessons:[{id:1,published:true,subject:'语文',title:'已发布阅读',coreTarget:'概括'},{id:2,published:false,title:'草稿不得显示'}],tests:[{available:false,stageName:'空考试',status:'not_started'},{available:true,stageName:'已配置考试',status:'not_started',subject:'语文',stage:'midterm'}]});
 return Promise.resolve([]);
}
function classroomInvitationsClassic(){}function classroomQuickChecksClassic(){}function startTeachingAdaptive(){}function go(){}
async function settle(){for(let i=0;i<30;i++)await Promise.resolve()}
"""+script+r"""
(async()=>{
 await syncLearning();assert(panel.innerHTML.includes('本班民间故事课'));assert(panel.innerHTML.includes('语文甲班'));assert(panel.innerHTML.includes('/v1/weekend-practice?s=7'));
 assert(page.innerHTML.includes('已发布阅读'));assert(page.innerHTML.includes('已配置考试'));
 assert(!page.innerHTML.includes('草稿不得显示'));assert(!page.innerHTML.includes('空考试'));assert(!page.innerHTML.includes('C层优先'));assert(!page.innerHTML.includes('教师尚未配置'));
 active=false;timer();await settle();assert(panel.innerHTML.includes('当前没有正在上的周末课'));
 active=true;failOverview=true;await syncLearning();assert(panel.innerHTML.includes('本班民间故事课'),'Legacy configuration must not block live classroom');
 assert(!page.innerHTML.includes('阶段性测评'));assert(panel.children.some(n=>n.textContent==='刷新课堂状态'));
})().catch(e=>{console.error(e);process.exitCode=1});
"""
    result=subprocess.run(['node','-e',node],text=True,capture_output=True,timeout=20)
    assert result.returncode==0,result.stdout+result.stderr
print('OK')
''')
