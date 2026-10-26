"""Exercise the actual served report's inline drill-down, including retry and return."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("answer_trace_helpers", ROOT / "tests" / "test_homework_solve.py")
helpers = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = helpers
spec.loader.exec_module(helpers)


def test_report_opens_recorded_answers_inline_and_can_retry_or_return(tmp_path):
    helpers.run_isolated(tmp_path, helpers.COMMON + r'''
import subprocess
with TestClient(app) as client:
    html = client.get('/v1/weekend-report').text
    start = html.index('  function practicePanel(')
    end = html.index('\n  load();', start)
    function = html[start:end]
    script = r"""
const assert = require('node:assert/strict');
class Element {
  constructor(tag, attrs) { this.tag=tag;this.attrs=attrs||{};this.children=[];this._text=this.attrs.text||'';this.disabled=false; }
  appendChild(c) {this.children.push(c);return c;}
  get textContent() {return this._text+this.children.map(c=>c.textContent).join('');}
  set textContent(v) {this._text=v;this.children=[];}
  set innerHTML(v) {throw Error('untrusted HTML insertion');}
}
function el(tag,attrs,...children){const e=new Element(tag,attrs);children.forEach(c=>e.appendChild(c));return e;}
let requests=[],fail=false;
function api(path){requests.push(path);return fail?Promise.reject(Error('读取失败，请重试')):Promise.resolve({
  state:'submitted',correct:0,total:1,questionNotice:'当前题库；帮助情况未知',
  items:[{text:'<img src=x onerror=alert(1)>',options:['甲','乙'],knowledge:'旋转方向',studentAnswer:'B.（记录的选项序号）',correct:false}]
});}
const tick=()=>new Promise(resolve=>setImmediate(resolve));
""" + function + r"""
(async()=>{
  const card=el('div',{},el('h1',{text:'原报告仍在此处'}));
  const r={id:71,studentId:9,studentName:'学生',practiceLabels:{assigned:'已布置'},
    practiceGroups:[{key:'g',subject:'数学',topic:'旋转',basis:'原题1'}],
    draft:{practice:{state:'assigned',groups:[{key:'g',questions:[]}],assignments:[{assignmentId:42,subject:'数学',title:'新题',state:'graded',correct:0,total:1}]}}};
  practicePanel(card,r,{},()=>{throw Error('should not navigate or redraw the report');});
  function all(n){return [n,...n.children.flatMap(all)];}
  const button=all(card).find(n=>n.attrs.text==='查看作答与批改');
  assert(button);button.attrs.onclick();assert(button.disabled);await tick();
  assert.equal(requests[0],'/teacher/weekend/reports/71/practice/42/answers');
  assert(card.textContent.includes('记录的回答：B.'));
  assert(card.textContent.includes('提交时判定：需订正'));
  assert(card.textContent.includes('<img src=x onerror=alert(1)>'));
  assert(card.textContent.includes('帮助情况未知'));assert(!button.disabled);
  button.attrs.onclick();assert(!card.textContent.includes('记录的回答：'));
  assert(card.textContent.includes('原报告仍在此处'));assert.equal(requests.length,1);
  fail=true;button.attrs.onclick();await tick();assert(!button.disabled);
  assert(card.textContent.includes('读取失败，请重试'));
  fail=false;button.attrs.onclick();await tick();assert(card.textContent.includes('记录的回答：B.'));
  console.log('OK');
})().catch(e=>{console.error(e);process.exitCode=1;});
"""
    result = subprocess.run(['node', '-'], input=script, text=True, capture_output=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'OK' in result.stdout
    print('OK')
''')
