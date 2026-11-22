import subprocess

from changying.web.weekend_courseware_pages import COURSEWARE_JS


def test_rapid_clicks_are_sent_in_order():
    script = r'''
const assert = require('assert');
function el(tag, a) { return {tag:tag, attrs:a||{}, children:[], appendChild:function(x){this.children.push(x)}, textContent:''}; }
let requests=[], resolvers=[], CW_PENDING=0, CW_VERSION=0;
function api(path, opts) { requests.push(opts.json); return new Promise(resolve => resolvers.push(resolve)); }
function cwRender(){}
function tick(){return new Promise(resolve=>setImmediate(resolve))}
''' + COURSEWARE_JS[COURSEWARE_JS.index('function cwControl('):] + r'''
(async function(){
  let root=el('div'), c={kind:'steps',kindLabel:'讲解',stageNo:3,page:2,params:{steps:['一','二','三'],figure:{}},view:{step:0,showAnswer:false}};
  cwControl(root,c,19);
  let buttons=root.children[1].children, next=buttons.find(x=>x.attrs.text==='下一步');
  next.attrs.onclick(); next.attrs.onclick();
  assert.equal(CW_PENDING,2);
  assert.equal(CW_VERSION,2);
  await Promise.resolve();
  assert.equal(requests.length,1); assert.equal(requests[0].view.step,1);
  resolvers.shift()({view:{step:1,showAnswer:false}});
  await tick();
  assert.equal(requests.length,2); assert.equal(requests[1].view.step,2);
  assert.equal(requests[1].stageNo,3); assert.equal(requests[1].page,2);
  resolvers.shift()({view:{step:2,showAnswer:false}});
  await tick();
  let back=buttons.find(x=>x.attrs.text==='上一步'),answer=buttons.find(x=>x.attrs.text==='显示/隐藏答案'),reset=buttons.find(x=>x.attrs.text==='重来');
  back.attrs.onclick(); await Promise.resolve();
  assert.equal(requests[2].view.step,1); resolvers.shift()({view:{step:1,showAnswer:false}});
  await tick();
  answer.attrs.onclick(); await Promise.resolve();
  assert.equal(requests[3].view.step,1); assert.equal(requests[3].view.showAnswer,true);
  resolvers.shift()({view:{step:1,showAnswer:true}});
  await tick();
  reset.attrs.onclick(); await Promise.resolve();
  assert.deepStrictEqual(requests[4].view,{step:0,showAnswer:false});
  resolvers.shift()({view:{step:0,showAnswer:false}});
  await tick();
  assert.equal(CW_PENDING,0);
})().catch(e=>{console.error(e);process.exitCode=1});
'''
    result = subprocess.run(['node', '-e', script], text=True, capture_output=True, encoding='utf-8', timeout=20)
    assert result.returncode == 0, result.stderr


def test_slide_controls_do_not_redraw_audio_on_unchanged_server_ack_or_big_screen_toggle():
    script = r'''
const assert = require('assert');
function el(tag, a) { return {tag:tag, attrs:a||{}, children:[], appendChild:function(x){this.children.push(x)}, textContent:''}; }
let requests=[], resolvers=[], cwRenderCalls=0, CW_PENDING=0, CW_VERSION=0;
function api(path, opts) { requests.push(opts.json); return new Promise(resolve => resolvers.push(resolve)); }
function cwRender(stage, c, view) { cwRenderCalls++; stage.textContent = 'slide:' + (view.slideIndex || 0); }
function tick(){return new Promise(resolve=>setImmediate(resolve))}
''' + COURSEWARE_JS[COURSEWARE_JS.index('function cwControl('):] + r'''
(async function(){
  let root = el('div');
  let c = {
    kind: 'slide',
    kindLabel: '图文幻灯片',
    stageNo: 2,
    page: 0,
    params: {
      title: '母亲的那盏灯',
      slides: [
        {heading: '第1页', body: ['段落一'], audioUrl: 'data:audio/mpeg;base64,SUQz'},
        {heading: '第2页', body: ['段落二'], audioUrl: 'data:audio/mpeg;base64,SUQz'}
      ]
    },
    view: {slideIndex: 0, audioPlaying: false}
  };
  cwControl(root, c, 19);
  assert.equal(cwRenderCalls, 1, 'initial mount renders once');
  let buttons = root.children[1].children;
  let nextBtn = buttons.find(x => x.attrs.text === '下一页 ›');
  let bigAudioBtn = buttons.find(x => x.attrs.text === '🔊 大屏播放/暂停朗读');
  assert(nextBtn && bigAudioBtn);

  nextBtn.attrs.onclick();
  assert.equal(cwRenderCalls, 2, 'slide change redraws once immediately');
  await Promise.resolve();
  assert.equal(requests.length, 1);
  assert.deepStrictEqual(requests[0].view, {audioPlaying: false, slideIndex: 1});
  resolvers.shift()({view: {slideIndex: 1, audioPlaying: false}});
  await tick();
  assert.equal(cwRenderCalls, 2, 'identical server ack (even different key order) must NOT redraw control audio');

  bigAudioBtn.attrs.onclick();
  assert.equal(cwRenderCalls, 2, 'toggling big-screen playback must NOT redraw control audio');
  await Promise.resolve();
  assert.deepStrictEqual(requests[1].view, {audioPlaying: true, slideIndex: 1});
  resolvers.shift()({view: {slideIndex: 1, audioPlaying: true}});
  await tick();
  assert.equal(cwRenderCalls, 2, 'big-screen toggle ack must NOT redraw control audio');

  root._cwSyncView({slideIndex: 1, audioPlaying: true});
  assert.equal(cwRenderCalls, 2, '15s poll matching active slide must NOT redraw control audio');

  root._cwSyncView({slideIndex: 0, audioPlaying: false});
  assert.equal(cwRenderCalls, 3, 'remote slide change via 15s poll should update control view');
  console.log('OK');
})().catch(e=>{console.error(e);process.exitCode=1});
'''
    result = subprocess.run(['node', '-e', script], text=True, capture_output=True, encoding='utf-8', timeout=20)
    assert result.returncode == 0, result.stderr + result.stdout
    assert 'OK' in result.stdout


def test_slide_pager_badge_disabled_edges_and_next_stage_button():
    script = r'''
const assert = require('assert');
function el(tag, a) { return {tag:tag, attrs:a||{}, children:[], appendChild:function(x){this.children.push(x)}, textContent:''}; }
let requests=[], resolvers=[], nextStageCalls=0, CW_PENDING=0, CW_VERSION=0;
function api(path, opts) { requests.push(opts.json); return new Promise(resolve => resolvers.push(resolve)); }
function cwRender() {}
''' + COURSEWARE_JS[COURSEWARE_JS.index('function cwControl('):] + r'''
(async function(){
  // 1. Single-slide stage: prev/next disabled, badge shows 1/1, 进入下一环节 › immediately visible.
  let root1 = el('div');
  cwControl(root1, {
    kind: 'slide',
    kindLabel: '图文幻灯片',
    stageNo: 1,
    page: null,
    params: {title: '导入', slides: [{heading: '导入页', body: ['欢迎']}]},
    view: {slideIndex: 0, audioPlaying: false}
  }, 19, {canNextStage: true, onNextStage: () => { nextStageCalls++; }});
  let bar1 = root1.children[1].children;
  let prev1 = bar1.find(x => x.attrs.text === '‹ 上一页');
  let badge1 = bar1.find(x => x.tag === 'span');
  let next1 = bar1.find(x => x.attrs.text === '下一页 ›');
  let nextStage1 = bar1.find(x => x.attrs.text === '进入下一环节 ›');
  assert.equal(prev1.disabled, true);
  assert.equal(next1.disabled, true);
  assert.equal(badge1.textContent, '本环节 第 1 / 1 页');
  assert(nextStage1 && !nextStage1.hidden, 'single-page stage should immediately show 进入下一环节 ›');
  next1.attrs.onclick();
  assert.equal(requests.length, 0, 'boundary click on disabled next must not fire request');
  nextStage1.attrs.onclick();
  assert.equal(nextStageCalls, 1);

  // 2. Two-slide stage: 进入下一环节 › hidden on slide 1, visible on slide 2.
  let root2 = el('div');
  cwControl(root2, {
    kind: 'slide',
    kindLabel: '图文幻灯片',
    stageNo: 2,
    page: 0,
    params: {title: '短文', slides: [{heading: '第1页', body: ['a']}, {heading: '第2页', body: ['b']}]},
    view: {slideIndex: 0, audioPlaying: false}
  }, 19, {canNextStage: true, onNextStage: () => { nextStageCalls++; }});
  let bar2 = root2.children[1].children;
  let prev2 = bar2.find(x => x.attrs.text === '‹ 上一页');
  let badge2 = bar2.find(x => x.tag === 'span');
  let next2 = bar2.find(x => x.attrs.text === '下一页 ›');
  let nextStage2 = bar2.find(x => x.attrs.text === '进入下一环节 ›');
  assert.equal(prev2.disabled, true);
  assert.equal(next2.disabled, false);
  assert.equal(badge2.textContent, '本环节 第 1 / 2 页');
  assert.equal(nextStage2.hidden, true);
  next2.attrs.onclick();
  assert.equal(prev2.disabled, false);
  assert.equal(next2.disabled, true);
  assert.equal(badge2.textContent, '本环节 第 2 / 2 页');
  assert.equal(nextStage2.hidden, false);
  nextStage2.attrs.onclick();
  assert.equal(nextStageCalls, 2);
  console.log('OK');
})().catch(e=>{console.error(e);process.exitCode=1});
'''
    result = subprocess.run(['node', '-e', script], text=True, capture_output=True, encoding='utf-8', timeout=20)
    assert result.returncode == 0, result.stderr + result.stdout
    assert 'OK' in result.stdout
