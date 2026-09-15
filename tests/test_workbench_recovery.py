"""Execute the shipped inline JavaScript against controlled API responses."""
import ast
import json
from pathlib import Path
import subprocess
import unittest


class WorkbenchRecoveryTests(unittest.TestCase):
    def test_recovery_and_auth_states(self):
        source = Path('changying/web/product_shell.py').read_text()
        module = ast.parse(source)
        function = next(n for n in module.body if isinstance(n, ast.FunctionDef) and n.name == 'teacher_workbench_html')
        html = next(n.value.value for n in function.body if isinstance(n, ast.Return))
        script = html.split('<script>', 1)[1].split('</script>', 1)[0]
        harness = r'''
const vm=require('node:vm');
const assert=require('node:assert/strict');
const code=SCRIPT;
function page(handler,initialToken='kept-token'){
  const elements=new Map();
  function element(id){
    if(!elements.has(id))elements.set(id,{textContent:'',innerHTML:'',hidden:true,disabled:false,
      classList:{add(){},remove(){}},addEventListener(event,fn){this[event]=fn;}});
    return elements.get(id);
  }
  const stored={v717Token:initialToken};
  const calls=[];
  const timers=[];
  const context=vm.createContext({document:{getElementById:element},
    localStorage:{getItem:key=>stored[key]||null},Intl,Date,AbortController,
    setTimeout:fn=>{timers.push(fn);return timers.length;},clearTimeout:()=>{},
    fetch:async(url,options)=>{calls.push(url);return handler(url,options);}});
  vm.runInContext(code,context);
  return {context,element,stored,calls,timers};
}
const response=(status,body)=>({ok:status>=200&&status<300,status,json:async()=>body});
const settle=()=>new Promise(resolve=>setImmediate(resolve));
(async()=>{
  let offline=true;
  const p=page(url=>{if(offline)throw new TypeError('offline');return response(200,url==='/session'?{name:'老师',role:'teacher'}:[]);});
  await settle();
  assert.equal(p.element('sessionTitle').textContent,'暂时无法读取，请重试');
  assert.equal(p.element('retryStatus').hidden,false);
  assert.equal(p.element('loginAction').hidden,true);
  assert.equal(p.stored.v717Token,'kept-token');
  offline=false;
  await p.element('retryStatus').click();
  assert.match(p.element('sessionTitle').textContent,/已登录/);
  assert.equal(p.element('classHint').textContent,'尚未分配班级');
  assert.equal(p.element('kpi-classes').textContent,'0');
  assert.equal(p.element('retryStatus').hidden,true);
  assert.equal(p.calls.includes('/admin/overview'),false);
  for(const [status,title,retry] of [[401,'登录已过期，请重新登录',false],[403,'当前账号无权查看此内容',false],[503,'暂时无法读取，请重试',true]]){
    const q=page(()=>response(status,{}));await settle();
    assert.equal(q.element('sessionTitle').textContent,title);
    assert.equal(q.element('retryStatus').hidden,!retry);
    assert.equal(q.element('loginAction').hidden,retry);
    assert.equal(q.stored.v717Token,'kept-token');
  }
  const noLogin=page(()=>{throw Error('must not fetch');},'');await settle();
  assert.equal(noLogin.calls.length,0);
  assert.equal(noLogin.element('sessionTitle').textContent,'尚未登录');
  assert.equal(noLogin.element('loginAction').hidden,false);
  const admin=page(url=>response(url==='/session'?200:503,{role:'admin'}));await settle();
  assert.match(admin.element('sessionTitle').textContent,/已登录/);
  assert.equal(admin.element('questions-live').textContent,'暂时无法读取，请重试');
  assert.equal(admin.element('retryStatus').hidden,false);
  assert.equal(admin.calls.includes('/teacher/classes'),false);
  const denied=page(url=>response(url==='/session'?200:403,{role:'teacher'}));await settle();
  assert.equal(denied.element('classHint').textContent,'当前账号无权查看此内容');
  const timeout=page((url,options)=>new Promise((resolve,reject)=>options.signal.addEventListener('abort',()=>reject(new Error('timeout')))));
  assert.equal(timeout.element('retryStatus').disabled,true);
  timeout.timers[0]();await settle();
  assert.equal(timeout.element('sessionTitle').textContent,'暂时无法读取，请重试');
  assert.equal(timeout.element('retryStatus').disabled,false);
  // Double clicks cannot start overlapping refreshes.
  const pending=page(()=>new Promise(()=>{}));
  await pending.element('retryStatus').click();
  assert.equal(pending.calls.length,1);
  // A retry re-reads a token changed by logging in in another tab.
  p.stored.v717Token='';await p.element('retryStatus').click();
  assert.equal(p.element('sessionTitle').textContent,'尚未登录');
  assert.equal(p.element('kpi-classes').textContent,'—');
  console.log('Recovery, timeout, role access, empty state, token preservation and retry checks passed');
})().catch(error=>{console.error(error);process.exitCode=1;});
'''.replace('SCRIPT', json.dumps(script))
        result = subprocess.run(['node', '-e', harness], capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
