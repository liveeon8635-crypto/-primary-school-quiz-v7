import subprocess

from changying.web.weekend_courseware_pages import COURSEWARE_JS


def test_rapid_clicks_are_sent_in_order():
    script = r'''
const assert = require('assert');
function el(tag, a) { return {tag:tag, attrs:a||{}, children:[], appendChild:function(x){this.children.push(x)}, textContent:''}; }
let requests=[], resolvers=[];
function api(path, opts) { requests.push(opts.json); return new Promise(resolve => resolvers.push(resolve)); }
function cwRender(){}
''' + COURSEWARE_JS[COURSEWARE_JS.index('function cwControl('):] + r'''
(async function(){
  let root=el('div'), c={kind:'steps',kindLabel:'讲解',stageNo:3,page:2,params:{steps:['一','二','三'],figure:{}},view:{step:0,showAnswer:false}};
  cwControl(root,c,19);
  let buttons=root.children[1].children, next=buttons.find(x=>x.attrs.text==='下一步');
  next.attrs.onclick(); next.attrs.onclick();
  await Promise.resolve();
  assert.equal(requests.length,1); assert.equal(requests[0].view.step,1);
  resolvers.shift()({view:{step:1,showAnswer:false}});
  for(let i=0;i<5;i++) await Promise.resolve();
  assert.equal(requests.length,2); assert.equal(requests[1].view.step,2);
  assert.equal(requests[1].stageNo,3); assert.equal(requests[1].page,2);
  resolvers.shift()({view:{step:2,showAnswer:false}});
})().catch(e=>{console.error(e);process.exitCode=1});
'''
    result = subprocess.run(['node', '-e', script], text=True, capture_output=True, encoding='utf-8', timeout=20)
    assert result.returncode == 0, result.stderr
