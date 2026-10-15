import subprocess

from changying.web.weekend_pages import PLAN_JS


def test_save_button_verifies_server_and_shows_local_feedback():
    helper = PLAN_JS.split('function plan(){')[0]
    script = helper + r'''
const assert=require('assert');
(async function(){
  const payload={title:'教案',teacherPlan:'阅读文章'.repeat(5000),closureTraining:'1题\n2题\n3题\n4题\n5题',examples:['例题'],ppt:['第一张']};
  const button={disabled:false,textContent:'保存教案'},status={},fields=[{disabled:false}];
  let calls=[],finish;
  api=function(url,opts){calls.push(opts);return opts?new Promise(resolve=>finish=resolve):Promise.resolve(payload)};
  let pending=saveLessonEdits('/lesson',payload,button,status,fields);
  assert(button.disabled&&fields[0].disabled);assert(status.textContent.includes('正在保存'));
  await saveLessonEdits('/lesson',payload,button,status,fields);assert.equal(calls.length,1);
  finish({});await pending;
  assert.equal(calls.length,2);assert.equal(calls[0].json.teacherPlan,payload.teacherPlan);
  assert(status.textContent.includes('已核对服务器内容'));assert(!button.disabled&&!fields[0].disabled);
  api=()=>Promise.reject(new Error('请求失败（413）'));
  await saveLessonEdits('/lesson',payload,button,status,fields);
  assert(status.textContent.includes('413'));assert(status.textContent.includes('本页填写内容已保留'));assert(!button.disabled);
  api=(url,opts)=>Promise.resolve(opts?{}:{...payload,closureTraining:'只有两题'});
  await saveLessonEdits('/lesson',payload,button,status,fields);
  assert(status.textContent.includes('不一致'));assert(status.textContent.includes('回读核对未通过'));
  api=(url,opts)=>opts?Promise.resolve({}):Promise.reject(new Error('网络中断'));
  await saveLessonEdits('/lesson',payload,button,status,fields);
  assert(status.textContent.includes('保存请求已完成'));assert(status.textContent.includes('网络中断'));
})().catch(e=>{console.error(e);process.exit(1)});
'''
    subprocess.run(['node', '-e', script], check=True, capture_output=True, text=True)
    # Runtime wiring and adjacent accessible feedback in the page's actual script.
    assert "editPane.appendChild(saveButton);editPane.appendChild(saveStatus)" in PLAN_JS
    assert "saveLessonEdits('/teacher/weekend/lessons/'+r.lessonId" in PLAN_JS
    assert "role:'status','aria-live':'polite'" in PLAN_JS
