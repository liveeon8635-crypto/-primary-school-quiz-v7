"""Interactive role training workbench for Changying V1.

This is the primary onboarding surface. It uses the ephemeral training sandbox
API so users operate a complete workflow instead of reading static screenshots.\nThe training bar remains secondary to the actual task surface.
"""

from __future__ import annotations

from changying.web.v1_ribbon_banner import BRAND_FONT_B64, RIBBON_SVG
from fastapi import APIRouter, FastAPI
from fastapi.responses import HTMLResponse

TRAINING_WORKBENCH_PATH = "/v1/training"
TRAINING_WORKBENCH_MARKER = "changying_v1_training_workbench_v1"

_TRAINING_HTML = r'''<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#a8101c">
<title>长缨辅学 · 角色实操沙盒</title>
<style>
:root{--navy:#a8101c;--ink:#172033;--muted:#7a625c;--line:#eadfd8;--soft:#f8f3ee;--blue:#c0262d;--ok:#247447;--warn:#8b5e00;--danger:#b42318}
*{box-sizing:border-box}html,body{margin:0;min-height:100%;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;color:var(--ink);background:var(--soft);-webkit-text-size-adjust:100%}
button,input,select,textarea{font:inherit}.hidden{display:none!important}.muted{color:var(--muted)}.small{font-size:12px}.tag{display:inline-flex;align-items:center;gap:5px;padding:5px 9px;border-radius:999px;background:#fdebe7;color:var(--navy);font-size:12px;font-weight:800}.tag.ok{background:#eef9f0;color:var(--ok)}.tag.warn{background:#fff7e8;color:var(--warn)}
@font-face{font-family:CyBrand;src:url(data:font/woff2;base64,__BRAND_FONT_B64__) format('woff2');font-display:swap}
.top{position:sticky;top:0;z-index:30;overflow:hidden;color:#fff;background:radial-gradient(110% 240% at 6% -50%,rgba(255,222,160,.6),transparent 56%),linear-gradient(100deg,#a8101c 0%,#d9352a 36%,#ee7a38 64%,#c92a2c 100%);border-bottom:0;padding:12px 14px;box-shadow:0 8px 22px rgba(168,16,28,.28)}
.top .cy-ribbon{position:absolute;inset:0;width:100%;height:100%;pointer-events:none}.top>:not(.cy-ribbon){position:relative;z-index:1}
select{background:#fff;border:1px solid var(--line);border-radius:12px;padding:9px 10px;color:var(--ink)}
.top .top-copy b,.top .top-copy small,.top .progress-wrap span{color:#fff}.top .top-copy small{opacity:.9}.top .icon-btn,.top a.icon-btn{background:rgba(255,255,255,.18)!important;color:#fff!important;border:1px solid rgba(255,255,255,.5)!important}.top .progress{background:rgba(255,255,255,.3)}.top .progress i{background:#ffe9a8}
.top-row{max-width:1120px;margin:auto;display:flex;align-items:center;gap:10px}.brand{color:#fff;font-family:CyBrand,'STXingkai','Xingkai SC','Kaiti SC',KaiTi,serif;font-weight:400;font-size:34px;letter-spacing:.12em;text-shadow:0 2px 8px rgba(100,0,10,.4);white-space:nowrap}.top-copy{min-width:0;flex:1}.top-copy b{display:block;font-size:15px}.top-copy small{display:block;color:var(--muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;margin-top:2px}.top-actions{display:flex;gap:7px}.icon-btn,.btn{border:1px solid #eadfd8;background:#fff;color:var(--ink);border-radius:11px;padding:9px 12px;font-weight:800;cursor:pointer}.btn.primary{background:var(--navy);border-color:var(--navy);color:#fff}.btn.soft{background:#fdebe7;color:var(--navy);border-color:#d1def5}.btn.danger{color:var(--danger)}.btn:disabled{opacity:.45;cursor:not-allowed}
.progress-wrap{max-width:1120px;margin:8px auto 0;display:flex;gap:8px;align-items:center}.progress{height:7px;background:#f3e4de;border-radius:999px;overflow:hidden;flex:1}.progress i{display:block;height:100%;background:var(--navy);width:0}.progress-wrap span{font-size:11px;color:var(--muted);min-width:48px;text-align:right}
.layout{max-width:1120px;margin:14px auto 96px;padding:0 14px;display:grid;grid-template-columns:240px minmax(0,1fr);gap:14px}.rail{background:#fff;border:1px solid var(--line);border-radius:18px;padding:12px;align-self:start;position:sticky;top:86px;max-height:calc(100dvh - 110px);overflow:auto}.rail h3{margin:4px 3px 9px}.step{width:100%;border:0;background:transparent;display:grid;grid-template-columns:28px 1fr auto;gap:8px;align-items:center;text-align:left;padding:8px;border-radius:11px;color:var(--ink)}.step.active{background:#fdebe7}.step.done{background:#eef9f0}.step.skipped{background:#fff7e8}.step.locked{opacity:.46}.step:disabled{cursor:not-allowed}.step-no{width:27px;height:27px;border:1px solid #d7e0ed;border-radius:9px;background:#fff;display:grid;place-items:center;font-size:12px;font-weight:900}.step small{color:var(--muted)}.stage{min-width:0}.card{background:#fff;border:1px solid var(--line);border-radius:18px;padding:18px}.hero{background:linear-gradient(145deg,#eef4ff,#fff)}h1{font-size:25px;margin:5px 0 8px}h2{font-size:19px;margin:0 0 8px}p{line-height:1.65}.relation{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:9px;margin-top:12px}.relation>div{border:1px solid var(--line);background:#fff8f4;border-radius:13px;padding:11px}.relation b{display:block;font-size:11px;color:var(--navy);margin-bottom:4px}.relation span{font-size:12px;line-height:1.5;color:#4d5a70}.page-card{margin-top:12px}.page-head{display:flex;justify-content:space-between;align-items:flex-start;gap:10px;padding-bottom:13px;border-bottom:1px solid var(--line)}.page-head h2{font-size:22px;margin:0}.page-head p{margin:4px 0 0;color:var(--muted);font-size:13px}.form-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;margin-top:14px}.field{display:grid;gap:5px}.field label{font-size:12px;color:#475467;font-weight:700}.field input,.field select,.field textarea{width:100%;border:1px solid #e3cfc8;border-radius:11px;background:white;padding:11px 12px;color:var(--ink)}.field textarea{min-height:90px}.full{grid-column:1/-1}.action-row{display:flex;flex-wrap:wrap;gap:8px;margin-top:14px}.notice{padding:11px 12px;border-radius:12px;background:#f7f9fc;border:1px solid var(--line);font-size:13px;line-height:1.6}.notice.ok{background:#eef9f0;border-color:#cce9d2;color:#245f33}.notice.warn{background:#fff8e8;border-color:#efd59c;color:#754d00}.list{display:grid;gap:9px;margin-top:12px}.item{border:1px solid var(--line);border-radius:13px;padding:12px;background:#fff}.item b{display:block}.item small{display:block;color:var(--muted);margin-top:4px;line-height:1.5}.question{border:1px solid var(--line);border-radius:14px;padding:13px;margin-top:10px}.options{display:grid;gap:7px;margin-top:9px}.option{border:1px solid #d3ddea;background:#fff;border-radius:10px;padding:10px;text-align:left}.option.selected{border-color:#7da2e8;background:#fdebe7}.answer-input{width:100%;margin-top:10px;border:1px solid #e3cfc8;border-radius:11px;background:#fff;padding:11px 12px;color:var(--ink);font:inherit}.answer-input.textarea{min-height:92px;resize:vertical}.question-nav{display:grid;grid-template-columns:auto 1fr auto;align-items:center;gap:8px;margin-top:10px}.question-nav span{text-align:center;font-size:12px;color:var(--muted);font-weight:800}.metric-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:9px;margin-top:12px}.metric{border:1px solid var(--line);border-radius:13px;padding:12px;background:#fff8f4}.metric strong{font-size:24px;display:block}.metric small{color:var(--muted)}.mode-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:12px}.mode{border:1px solid #eadfd8;border-radius:15px;background:#fff;padding:14px;text-align:left}.mode b{display:block;margin-bottom:6px}.mode small{color:var(--muted);line-height:1.55}.map-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.map-node{border:1px solid var(--line);border-radius:14px;padding:13px;background:#fff}.map-node b{display:block}.map-node small{color:var(--muted);line-height:1.5;display:block;margin-top:4px}
.bottom{position:fixed;left:10px;right:10px;bottom:max(8px,env(safe-area-inset-bottom));z-index:35;background:rgba(255,255,255,.98);border:1px solid var(--line);border-radius:17px;padding:8px;display:flex;gap:7px;justify-content:center;box-shadow:0 16px 48px rgba(168,16,28,.18);backdrop-filter:blur(14px)}.bottom .btn{padding:9px 11px}.bottom #moreBtn{display:none}.spacer{flex:1}.rail-head{display:flex;align-items:center;justify-content:space-between;gap:8px}.rail-head h3{margin:4px 3px 9px}.rail-head .btn{padding:6px 9px;font-size:12px}
.drawer{position:fixed;inset:0;z-index:60;background:rgba(60,8,14,.46);display:flex;justify-content:flex-end}.drawer-panel{width:min(440px,92vw);height:100%;background:#fff;padding:18px;overflow:auto;box-shadow:-14px 0 50px rgba(60,8,14,.22)}.drawer-head{display:flex;justify-content:space-between;gap:10px;align-items:center}.assistant-log{display:grid;gap:8px;margin:12px 0}.assistant-msg{border:1px solid var(--line);border-radius:12px;padding:10px 11px;line-height:1.6;font-size:13px}.assistant-msg.ai{background:#fff4ee}
@media(max-width:760px){
html,body{overflow-x:hidden}.top{padding:9px 12px}.top-row{gap:9px}.brand{font-size:26px;flex:0 0 auto}.top-copy b{font-size:16px}.top-copy small{max-width:46vw;font-size:12px}.top-actions{gap:0}.top-actions #toggleMap,.top-actions #askBtn,.top-actions #feedbackBtn{display:none}.top-actions .icon-btn{padding:8px 10px;border-radius:10px;font-size:14px}.top-actions .icon-btn[href]{white-space:nowrap}
.progress-wrap{margin-top:7px}.progress-wrap span{min-width:40px}.layout{display:block;margin-top:10px;padding:0 10px;margin-bottom:92px}.rail{position:fixed;inset:74px 10px 86px;z-index:50;max-height:none;margin:0;display:none;box-shadow:0 18px 55px rgba(168,16,28,.20)}.rail.open{display:block}.relation{display:none}.form-grid{grid-template-columns:1fr}.full{grid-column:auto}.metric-grid{grid-template-columns:1fr 1fr}.mode-grid,.map-grid{grid-template-columns:1fr}.card{padding:14px;border-radius:16px}h1{font-size:22px}.page-head h2{font-size:20px}
.bottom{left:10px;right:10px;bottom:max(8px,env(safe-area-inset-bottom));display:grid;grid-template-columns:minmax(0,1fr) auto minmax(0,1.25fr);gap:7px;padding:7px;overflow:visible}.bottom .btn{min-width:0;white-space:nowrap;padding:11px 10px}.bottom .spacer,.bottom #skipBtn,.bottom #relationBtn,.bottom #resetStepBtn{display:none}.bottom #prevBtn{grid-column:1}.bottom #moreBtn{display:block;grid-column:2}.bottom #nextBtn{grid-column:3;width:100%}
.drawer-panel{width:92vw;padding:16px}.stage[aria-busy="true"]{opacity:.72;pointer-events:none}
}
</style>
</head>
<body>
<header class="top">
  <div class="top-row">
    <div class="brand">长缨辅学</div>
    <div class="top-copy"><b id="topTitle">角色实操沙盒</b><small id="topMeta">正在准备同身份虚拟环境…</small></div>
    <div class="top-actions">
      <button class="icon-btn" id="toggleMap"><span class="label">训练地图</span> ☰</button>
      <button class="icon-btn" id="askBtn"><span class="label">问助手</span> ✦</button>
      <button class="icon-btn" id="feedbackBtn"><span class="label">反馈</span> ◇</button>
      <a class="icon-btn" href="/v1/workspace">退出</a>
    </div>
  </div>
  <div class="progress-wrap"><div class="progress"><i id="progressBar"></i></div><span id="progressText">准备中</span></div>
</header>
<main class="layout">
  <aside class="rail" id="rail"><div class="rail-head"><h3>训练地图</h3><button class="btn" id="closeRail">关闭</button></div><div id="steps"></div><div style="margin-top:12px"><label class="small muted">快速场景</label><select id="scenario" style="width:100%;margin-top:5px;padding:9px;border:1px solid #eadfd8;border-radius:10px"><option value="empty">从零开始</option><option value="assigned">从已布置作业开始</option><option value="submitted">从已有学生提交开始</option><option value="classroom">从课堂复盘开始</option></select><button class="btn soft" id="loadScenario" style="width:100%;margin-top:7px">载入场景</button><button class="btn danger" id="cleanupDemoData" style="width:100%;margin-top:7px">正式使用前 · 清空演示数据</button><div class="small muted" style="margin-top:6px">只清除当前账号的临时实操沙盒，不会删除真实班级、学生、作业、积分或学习证据。</div></div></aside>
  <section class="stage" id="stage"><div class="card"><h2>正在准备练习环境</h2><p class="muted">正在载入与你当前身份一致的临时虚拟数据…</p></div></section>
</main>
<nav class="bottom">
  <button class="btn" id="prevBtn" disabled>← 上一步</button>
  <button class="btn" id="skipBtn" disabled>跳过</button>
  <button class="btn" id="relationBtn" disabled>角色关系</button>
  <span class="spacer"></span>
  <button class="btn" id="resetStepBtn" disabled>重做本步</button>
  <button class="btn" id="moreBtn">更多</button>
  <button class="btn primary" id="nextBtn" disabled>下一步 →</button>
</nav>
<div class="drawer hidden" id="drawer"><section class="drawer-panel"><div class="drawer-head"><h2 id="drawerTitle">角色关系</h2><button class="btn" id="drawerClose">关闭</button></div><div id="drawerBody"></div></section></div>
<script>
(()=>{
const TOKEN_KEY='v717Token',SESSION_KEY='cyTrainingSandboxSessionV1',INDEX_KEY='cyTrainingStepIndexV1';
const token=()=>{const remember=localStorage.getItem('v717Remember')==='1';return (remember?localStorage.getItem(TOKEN_KEY):sessionStorage.getItem(TOKEN_KEY))||sessionStorage.getItem(TOKEN_KEY)||localStorage.getItem(TOKEN_KEY)||sessionStorage.getItem('v6Token')||localStorage.getItem('v6Token')||''};
const esc=v=>String(v??'').replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
const stage=document.getElementById('stage'),rail=document.getElementById('rail'),stepsEl=document.getElementById('steps'),progressBar=document.getElementById('progressBar'),progressText=document.getElementById('progressText'),topTitle=document.getElementById('topTitle'),topMeta=document.getElementById('topMeta');
const drawer=document.getElementById('drawer'),drawerTitle=document.getElementById('drawerTitle'),drawerBody=document.getElementById('drawerBody');
let session=null,index=Math.max(0,Number(sessionStorage.getItem(INDEX_KEY)||0)),answers={},questionCursor=0,actionPending=false;

async function request(path,opt={}){
  const t=token();if(!t){location.href='/v1';throw new Error('请先登录')}
  const headers={'Content-Type':'application/json',...(opt.headers||{}),Authorization:'Bearer '+t};
  const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),12000);
  let r;
  try{r=await fetch(path,{...opt,headers,cache:'no-store',signal:controller.signal})}
  catch(e){if(e?.name==='AbortError')throw new Error('连接超时，请重试');throw e}
  finally{clearTimeout(timer)}
  let d={};try{d=await r.json()}catch{}
  if(!r.ok)throw new Error(d.detail||('请求失败 '+r.status));return d
}
function setStageBusy(flag){
  actionPending=flag;
  stage.setAttribute('aria-busy',flag?'true':'false');
  stage.querySelectorAll('button').forEach(btn=>{
    if(flag){if(!btn.disabled)btn.dataset.cyBusyDisabled='1';btn.disabled=true}
    else if(btn.dataset.cyBusyDisabled==='1'){btn.disabled=false;delete btn.dataset.cyBusyDisabled}
  });
}
function showActionError(error){
  let box=document.getElementById('actionError');
  if(!box){stage.insertAdjacentHTML('afterbegin','<div class="notice warn" id="actionError" role="alert"></div>');box=document.getElementById('actionError')}
  box.textContent='这一步没有完成：'+String(error?.message||error||'请重试');
  box.scrollIntoView({block:'center',behavior:'smooth'});
}
async function act(action,payload={}){
  if(actionPending)return session;
  setStageBusy(true);
  try{
    session=await request('/v1/training-sandbox/'+session.sessionID+'/action',{method:'POST',body:JSON.stringify({action,payload})});
    render();
    return session;
  }catch(e){
    showActionError(e);
    throw e;
  }finally{
    setStageBusy(false);
  }
}
async function start(){
  try{
    const id=sessionStorage.getItem(SESSION_KEY);
    if(id){try{session=await request('/v1/training-sandbox/'+id)}catch{sessionStorage.removeItem(SESSION_KEY)}}
    if(!session){session=await request('/v1/training-sandbox/start',{method:'POST',body:JSON.stringify({linked_mode:'choose'})});sessionStorage.setItem(SESSION_KEY,session.sessionID)}
    index=Math.min(index,Math.max(0,session.flow.length-1));const frontier=session.flow.findIndex(s=>!stepSettled(s.id));if(frontier>=0)index=Math.min(index,frontier);render();
  }catch(e){
    progressText.textContent='未连接';
    stage.innerHTML='<div class="card"><h2>练习环境没有启动</h2><p>'+esc(e.message||'请重试')+'</p><div class="action-row"><button class="btn primary" id="retryTraining">重新载入</button><a class="btn" href="/v1/workspace">返回工作台</a></div></div>';
    const retry=document.getElementById('retryTraining');if(retry)retry.onclick=()=>{session=null;start()};
  }
}
function current(){return session?.flow?.[index]||null}
function stepSettled(id){return ['done','skipped'].includes(session?.progress?.[id])}
function firstUnsettledIndex(){const i=session?.flow?.findIndex(s=>!stepSettled(s.id))??-1;return i<0?(session?.flow?.length||0):i}
function setIndex(i){index=Math.max(0,Math.min(session.flow.length-1,i));sessionStorage.setItem(INDEX_KEY,String(index));answers={};questionCursor=0;render();requestAnimationFrame(()=>window.scrollTo({top:0,behavior:'smooth'}))}
function relation(step=current()){return session?.relationships?.[step?.id]||{}}
function answerMode(q){return q?.answerKind==='choice'?'选择答案':(q?.type==='简短应用题'?'填写答案（含单位）':'输入答案')}
function correctDisplay(q){if(q?.answerKind==='choice'){const i=Number(q.correctIndex);return (q.options||[])[i]??''}return q?.correctAnswer??''}
function questionControl(q,optionClass,inputClass){
  const key=String(q.id),saved=answers[key];
  if(q.answerKind==='choice'){
    return '<div class="options">'+(q.options||[]).map((o,i)=>'<button class="option '+optionClass+(String(saved)===String(i)?' selected':'')+'" data-q="'+q.id+'" data-i="'+i+'">'+String.fromCharCode(65+i)+'. '+esc(o)+'</button>').join('')+'</div>';
  }
  const value=saved??'',placeholder=esc(q.placeholder||'输入答案');
  if(q.type==='简短应用题'||q.type==='简短回答')return '<textarea class="answer-input textarea '+inputClass+'" data-q="'+q.id+'" placeholder="'+placeholder+'">'+esc(value)+'</textarea>';
  return '<input class="answer-input '+inputClass+'" data-q="'+q.id+'" value="'+esc(value)+'" placeholder="'+placeholder+'">';
}
function questionPager(p,optionClass,inputClass){
  if(!p?.questions?.length)return '<div class="notice">暂无题目。</div>';
  questionCursor=Math.max(0,Math.min(p.questions.length-1,questionCursor));const q=p.questions[questionCursor];
  return '<div class="question"><div class="tag">'+esc(q.type)+' · '+esc(answerMode(q))+'</div><h2 style="margin-top:10px">'+q.index+'. '+esc(q.prompt)+'</h2><small class="muted">'+esc(q.knowledge)+'</small>'+questionControl(q,optionClass,inputClass)+'</div><div class="question-nav"><button class="btn" id="questionPrev" '+(questionCursor===0?'disabled':'')+'>← 上一题</button><span>第 '+(questionCursor+1)+' / '+p.questions.length+' 题</span><button class="btn" id="questionNext" '+(questionCursor===p.questions.length-1?'disabled':'')+'>下一题 →</button></div>';
}
function bindQuestionPager(optionClass,inputClass){
  document.querySelectorAll('.'+optionClass).forEach(b=>b.onclick=()=>{answers[String(b.dataset.q)]=Number(b.dataset.i);renderStep(current())});
  document.querySelectorAll('.'+inputClass).forEach(i=>i.oninput=()=>{answers[String(i.dataset.q)]=i.value});
  const prev=document.getElementById('questionPrev'),next=document.getElementById('questionNext');
  if(prev)prev.onclick=()=>{questionCursor=Math.max(0,questionCursor-1);renderStep(current())};
  if(next)next.onclick=()=>{questionCursor=Math.min((session?.data?.papers?.at(-1)?.questions?.length||1)-1,questionCursor+1);renderStep(current())};
}
function statusClass(id){const s=session.progress?.[id];return s==='done'?'done':s==='skipped'?'skipped':''}
function pageIntro(step,subtitle=''){
  const rel=relation(step),settled=stepSettled(step.id);
  return '<div class="card hero"><span class="tag '+(settled?'ok':'')+'">'+(settled?'✓ 本步完成':'第 '+(index+1)+' / '+session.flow.length+' 关')+'</span><h1>'+esc(step.title)+'</h1><p>'+esc(subtitle||'请像正式使用一样完成本页操作。所有业务数据只存在于临时实操沙盒。')+'</p><div class="notice '+(settled?'ok':'')+'">'+(settled?'已完成本步。可以继续下一步，也可以从“更多”中重做。':'当前任务：完成下面的实际操作；完成后“下一步”会自动解锁。')+'</div><div class="relation"><div><b>这一步由谁操作</b><span>'+esc(rel.who||session.primaryRole)+'</span></div><div><b>操作会产生什么</b><span>'+esc(rel.creates||'训练进度')+'</span></div><div><b>其他角色会看到什么</b><span>'+esc(rel.other_role_sees||rel.visible_to||'按权限显示')+'</span></div></div></div>';
}
function pageCard(title,subtitle,body,actions=''){
  return '<section class="card page-card"><div class="page-head"><div><h2>'+esc(title)+'</h2><p>'+esc(subtitle)+'</p></div><span class="tag warn">实操沙盒</span></div>'+body+(actions?'<div class="action-row">'+actions+'</div>':'')+'</section>';
}
// 周末课、知识地图、应试专项：沙盒不模拟这些模块，只按顺序讲清流程；真正操作在真实页面上。
const TOURS={
  teacher_weekend_plan:['在“18 次课进度表与备课”里，每次课点“导入教案/整包”：可上传 Word/PPT/PDF，也可只上传一个 JSON 整包，一次带入教案、随堂题和互动课件草稿；没有教案时点“没教案？AI 帮我写”。','整包导入后仍要分别审核：题目通过才发给学生，课件通过才进入课堂讲解；不能把“导入成功”当成“已审核通过”。','点“AI 出习题”：AI 按题型和难度出一整套草稿，数学答案会逐题验算。','点“审改”分四块处理：教案编辑、习题审核（例题逐题核对通过，练习通过才发给学生）、原文核对（导入时的原文，只存档）、互动课件（给例题配分步讲解和图示）。','习题审核顶部先看题数：例题几道（其中待审几道）、可用练习几道（其中待审几道），开课前就知道第 4 环节有没有题；例题内容一改会变回“已修改，待重新审核”，上线前的旧课显示“历史·已通过”；例题审核和互动课件审核分开记录。','第 4 环节没题时，用“单独导入随堂练习”或“导入混合资料并分组（例题讲解／随堂练习）”粘贴或上传，不确定条目会标为待定，需老师切换确认后再导入；开课后新通过的练习不会自动推入正在上课的课堂，需在控制页点“同步新增练习（+X 题）”手动补进。','第 4 环节实际可用练习为 0 道时阻止开课并明确提示原因；互动课件未审核通过时开课前会提醒确认；题干提到图示但缺少配图时，需勾选确认才能通过。','删掉的题，课堂、大屏、打印 Word 会自动跟着少；教案文字不会变。；仅调试、未实际上课时，可在备课页“撤销调试课堂”：核对名单后清除空课堂，保留教案；有学生作答、提示、积分或反馈时禁止撤销。之后可另行删除教案。','习题审核里每道文字题标一个考点（系统按题目小标题先填好，可“采用全部考点建议”），标一次这节课的所有班级通用；课后才做的题勾“课后题”。'],
  teacher_weekend_class:['开课后进入控制页，按 7 个环节推进：到课与热身、知识点介绍、例题讲解、随堂练习、练习复盘、课堂互动、布置课后。','打开大屏：知识点卡和例题卡自动分开排版，放不下就上下排；讲解环节的答案默认遮住，点“显示答案”才出现。','随堂练习：学生在平板“课堂练习”作答，可用阶梯提示；答案要老师逐题公布。','学生上传文字或照片后，在“学生作答与批改”查看系统预批；逐项核对识别题目、学生答案和参考答案，识别错误可修改再预批。只有老师确认保存后才成为正式结果。','点“生成／重试预批”后，在本份答案旁看排队、识别进度及失败原因，结果会自动更新，未保存的评语和选择会保留；无需反复点击或刷新全班。','传错题目、字迹模糊、程序不能核对时手工批改；重新提交会使旧预批失效。预批建议不展示给学生或家长。','练习复盘时系统建议请谁讲题（强带弱），课后结算进步分和团队分。'],
  teacher_weekend_report:['先在上课页“学生作答与批改”批完照片题：同一道题全班答案排在一起，可“本题待批全部标为正确”再改个别。','打开“课后总结与家长反馈”：没标考点的文字题可在“逐题统计”里直接标；点“为全班生成草稿”一次生成每个孩子的反馈。','老师逐份核对、修改，再发布（可“发布全部草稿”）；改了没发布，家长仍看到上一版；也可下载 Word。','“纸质备用与课后补录”：下载教师版/学生版 Word 打印；断网时纸上作答，课后补录回系统。'],
  teacher_knowledge_map:['按模板建地图（现有人教版五年级上册数学）：单元 → 知识点 → 先学什么。','给每个知识点配题：从题库挑、AI 出题（按单元选考法，数学答案验算）、系统画图题。','把题分到基础、中等、提高三档；每个知识点至少 6 道、每档至少 2 道才能用于诊断。','点“发布”：同年级学生马上能看到；以后改了要再发布一次。'],
  teacher_knowledge_class:['学生做 12 题入门诊断，以后可在任意学过的知识点做 3～5 题小测。','老师在“查看全班掌握情况”看颜色表：熟练、达标、薄弱、证据不足。','勾选薄弱学生，一键布置巩固练习（只出他们没做过的题）。','记录自己对每个学生的判断，看与系统结论的一致率（目标 80%）。'],
  teacher_exam_prep:['建考试目标：日期、范围（勾选知识地图单元）、班级。','发模拟卷：学生限时作答，系统记录用时。','看失分点：每个学生最多 3 个，按卷面分值排序。','一键布置专项练习 → 发再测卷 → 对比前后。','生成家长提分报告，写“老师的话”后发布。'],
  teacher_kp_cards:['每个知识点一张讲解卡：AI 写草稿，老师修改、审核。','审核后学生可以搜索；学生做错题时会看到对应知识点的卡片。'],
  student_weekend:['老师开课后，在学习首页点“查看本节课堂”进入课堂练习。','到“随堂练习”环节才出现题目；先自己做，卡住再点提示（三级，前两级不给答案）。','页面顶部还有“课前诊断／课后补测”入口，连到我的知识地图。'],
  student_knowledge_map:['打开“我的知识地图”：按单元排列的知识点，颜色表示掌握情况。','先做 12 题入门诊断（每人一次），每道题只算第一次作答。','点任意学过的知识点可以做 3～5 题小测，做完地图马上更新。'],
  student_exam_paper:['首页出现“限时模拟卷”卡片时，点“开始限时作答”。','顶部倒计时；中途刷新不会丢答案，倒计时接着走。','交卷前会提醒还有哪题没写；时间到了不会强制收卷，但用时会被记录。'],
  parent_weekend_brief:['在“孩子学情”页顶部点“周末课学情反馈”。','每节课最上面是“一眼看懂”：掌握得好的考点、需要加强的考点、回家做的一件事，以及和孩子自己上次比。','下面是老师发布的完整反馈：这节课学了什么、孩子表现、接下来怎么做。','没有排名，也看不到其他孩子。'],
  parent_exam_report:['在“孩子学情”页顶部点“考试提分报告”。','看到得分变化、失分点、专项练习和再测对比，以及老师的话。','看不到答案和其他孩子的信息。']
};
TOURS.teacher_weekend_plan.push('语文课先保存“阅读课”或“作文课”型；旧课的待选课型不会自动猜测。作文教案导入后到“作文素材与审核”核对范文、图组、方法和主题；待确认素材仅教师可见，缺配图不能开课。审核后课堂使用独立快照，学生到作文入口提交，教师发布反馈后家长可见。开发分支尚未完成全部界面验收。');
TOURS.teacher_weekend_plan.push('语文课在六环节课件与审核中逐项核对；补充课件只生成草稿，不自动审核或覆盖已有课件。AI 辅助和课堂维护在更多操作中。');
TOURS.teacher_weekend_plan.push('创建及开始语文课堂都要通过六环节缺项与逐页审核检查；普通教案默认本地导入，外发需要单独的教案授权。学生数据开关不能代替。');
TOURS.teacher_weekend_class[0]='课堂按课型推进：数学七环节；阅读课和作文课各六环节。进入环节不代表语文内容已经在学生端开放；语文素材分步显示和接口权限仍需开发与验收。';
TOURS.teacher_weekend_plan.push('已有教案可在“互动课件”预检导入课件包；默认不覆盖，勾选替换可保留上一版并生成待审核草稿，不改教案或习题。');
TOURS.teacher_weekend_plan.push('如果网站一次只能选一个文件，就在课次行点“导入教案/整包”，上传 JSON 单文件整包；系统会同时建立教案、随堂题和互动课件草稿，随后分别审核。');
TOURS.teacher_weekend_plan.push('第4环节可按已通过的随堂练习逐题配课件；课堂公布该题答案后才显示讲解，须逐题审核。');
function tourPage(step,roleLabel,doneId='auxDone'){
  const rel=relation(step),lines=TOURS[step.id]||[];
  const open=roleLabel==='教师'?'<a class="btn" href="'+esc(step.page)+'" target="_blank" rel="noopener">打开真实页面（新窗口，会影响真实数据）</a>':'';
  const body='<div class="notice warn">这是导览：沙盒不模拟这个模块，下面按顺序讲清它怎么运转。真正操作要到真实页面上，真实页面上的操作会立刻影响真实的老师、学生和家长。</div>'+
    '<ol class="list">'+lines.map(x=>'<li class="item">'+esc(x)+'</li>').join('')+'</ol>'+roleRelationBlock(rel);
  const intro=roleLabel==='教师'?'教师导览：先看懂流程和各角色的关系，再跟着真实备课、上课去做。':roleLabel+'导览：看懂'+roleLabel+'在这一步看到什么、能做什么，以及和老师的关系。';
  return pageIntro(step,intro)+pageCard(step.title,'真实页面：'+step.page,body,open+'<button class="btn primary" id="'+doneId+'">看懂了，下一步</button>');
}
function auxiliaryPage(step,roleLabel,details=''){
  if(TOURS[step.id])return tourPage(step,roleLabel);
  const rel=relation(step);
  const body='<div class="notice">'+esc(details||'这个页面属于 '+roleLabel+' 的完整功能地图。请先理解它的上游来源、可见范围和下游去向，再继续。')+'</div>'+roleRelationBlock(rel);
  return pageIntro(step,'这一页不是孤立功能；训练重点是理解它和其他角色、上下游页面之间的关系。')+pageCard(step.title,'页面：'+step.page,body,'<button class="btn primary" id="auxDone">完成本页实操</button>');
}
function listItems(items,formatter){return '<div class="list">'+(items?.length?items.map(formatter).join(''):'<div class="notice">当前还没有数据，请先完成上一环节。</div>')+'</div>'}
function markStep(status='done'){return act('visit_step',{step:current().id,status})}
function render(){
  if(!session)return;const step=current(),doneCount=Object.values(session.progress||{}).filter(x=>x==='done'||x==='skipped').length,frontier=firstUnsettledIndex(),settled=stepSettled(step.id);
  topTitle.textContent='实操沙盒 · '+step.title;
  topMeta.textContent='主身份：'+roleName(session.primaryRole)+' · 当前体验：'+roleName(session.currentRole)+(session.currentRole!==session.primaryRole?' · 完成后可一键返回主身份':'');
  progressBar.style.width=Math.round((doneCount/Math.max(1,session.flow.length))*100)+'%';progressText.textContent=doneCount+'/'+session.flow.length;
  stepsEl.innerHTML=session.flow.map((s,i)=>{const available=i<=frontier||stepSettled(s.id);return '<button class="step '+(i===index?'active ':'')+statusClass(s.id)+(available?'':' locked')+'" data-i="'+i+'" '+(available?'':'disabled')+'><span class="step-no">'+(i+1)+'</span><span><b>'+esc(s.title)+'</b><small>'+esc(s.page)+'</small></span><span>'+({done:'✓',skipped:'↷'}[session.progress?.[s.id]]||(available?'':'🔒'))+'</span></button>'}).join('');
  stepsEl.querySelectorAll('.step:not(:disabled)').forEach(b=>b.onclick=()=>{setIndex(Number(b.dataset.i));rail.classList.remove('open')});
  const scenario=document.getElementById('scenario');
  if(session.primaryRole!=='teacher'&&scenario&&scenario.options.length>1)scenario.innerHTML='<option value="empty">重新载入本身份练习</option>';
  document.getElementById('prevBtn').disabled=index===0;const next=document.getElementById('nextBtn');next.disabled=!settled||index===session.flow.length-1;next.textContent=index===session.flow.length-1?(settled?'已完成':'完成本步'):(settled?'下一步 →':'先完成本步');
  document.getElementById('skipBtn').disabled=false;document.getElementById('relationBtn').disabled=false;document.getElementById('resetStepBtn').disabled=false;
  renderStep(step);
}
function roleName(r){return({teacher:'教师',student:'学生',parent:'家长',admin:'管理员'}[r]||r||'当前身份')}
function renderStep(step){
  const d=session.data||{};
  if(session.primaryRole!=='teacher'){renderNonTeacher(step);return}
  const views={
    teacher_dashboard:()=>pageIntro(step,'先从教师工作台建立全局认识：当前教学动作最终都会回流到同一个学生连续档案。')+pageCard('教师工作台','从今天的教学动作，持续回流到同一个学生档案。','<div class="map-grid"><div class="map-node"><b>班级学生</b><small>确定当前教学对象和关系。</small></div><div class="map-node"><b>组卷作业</b><small>生成、审核并布置任务。</small></div><div class="map-node"><b>学情 / AI</b><small>读取证据并形成下一轮教学。</small></div><div class="map-node"><b>课堂 / 历史</b><small>把教学结果继续沉淀到长期档案。</small></div></div>','<button class="btn primary" id="understand">我理解教师工作台</button>'),
    create_class:()=>pageIntro(step,'真正创建一个临时练习班级。它不会进入正式班级统计。')+pageCard('班级学生','先建立当前教学容器。','<div class="form-grid"><div class="field"><label>班级名称</label><input id="className" value="五年级实操班"></div><div class="field"><label>年级</label><select id="classGrade">'+[1,2,3,4,5,6].map(x=>'<option '+(x===5?'selected':'')+' value="'+x+'">'+x+'年级</option>').join('')+'</select></div></div>'+listItems(d.classes,x=>'<div class="item"><b>'+esc(x.name)+'</b><small>'+esc(x.grade)+'年级 · 沙盒教师</small></div>'),'<button class="btn primary" id="createClass">＋新建班级</button>'),
    add_student:()=>{const cls=d.classes?.at(-1);return pageIntro(step,'创建一个与练习班级关联的虚拟学生账号，后续可以亲自切到这个学生视角。')+pageCard('创建学生账号',cls?'当前班级：'+cls.name:'请先建立班级','<div class="form-grid"><div class="field"><label>学生姓名</label><input id="studentName" value="小禾"></div><div class="field"><label>学生账号</label><input id="studentUser" value="xiaohe01"></div></div>'+listItems(d.students,x=>'<div class="item"><b>'+esc(x.name)+'</b><small>'+esc(x.username)+' · '+esc(x.className)+'</small></div>'),'<button class="btn primary" id="addStudent">创建学生账号</button>')},
    student_profile:()=>{const s=d.students?.at(-1);const sub=d.submissions?.at(-1);return pageIntro(step,'学生档案是长期主线；后面的作业和课堂结果都会回到这里。')+pageCard('学生连续档案',s?esc(s.name)+' · '+esc(s.className):'暂无学生',s?'<div class="metric-grid"><div class="metric"><strong>'+esc(sub?.score??'—')+'</strong><small>最近得分</small></div><div class="metric"><strong>'+esc(sub?.wrongCount??0)+'</strong><small>错题</small></div><div class="metric"><strong>'+esc(d.points?.reduce((n,x)=>n+Number(x.points||0),0)||0)+'</strong><small>积分</small></div><div class="metric"><strong>'+esc(d.history?.length||0)+'</strong><small>历史阶段</small></div></div><div class="notice" style="margin-top:12px">现在数据较少是正常的。完成一次作业后再回来，档案会发生变化。</div>':'<div class="notice">请先添加学生。</div>','<button class="btn primary" id="profileDone">我已了解连续档案</button>')},
    paper:()=>pageIntro(step,'像正式教师一样设置科目、教材、知识点和题量，并生成可审核的沙盒试卷。真实页面里还可以用「导入试卷」把已有试卷或真题导入：保存后试卷在「组卷与作业」，题目进入「教材题库」。')+pageCard('组卷 / 自动出题','生成后会看到实际题目列表，不是截图说明。','<div class="form-grid"><div class="field"><label>科目</label><select id="paperSubject"><option>数学</option><option>语文</option><option>英语</option></select></div><div class="field"><label>教材</label><input id="paperTextbook" value="人教版"></div><div class="field"><label>知识点</label><input id="paperKnowledge" value="小数乘法"></div><div class="field"><label>题量</label><select id="paperCount"><option>5</option><option selected>8</option><option>10</option><option>15</option></select></div></div>'+listItems(d.papers,x=>'<div class="item"><b>'+esc(x.title)+'</b><small>'+esc(x.subject)+' · '+esc(x.textbook)+' · '+x.questions.length+'题 · '+esc(x.knowledge)+'</small></div>'),'<button class="btn primary" id="createPaper">生成练习试卷</button>'),
    review:()=>{const p=d.papers?.at(-1);return pageIntro(step,'教师审核是关键人机边界。检查题型、答案方式、难度和积分后再进入布置。')+pageCard('教师审核',p?esc(p.title):'暂无试卷',p?'<div class="list">'+p.questions.map(q=>'<div class="question"><b>'+q.index+'. '+esc(q.prompt)+'</b><small class="muted">'+esc(q.type)+' · '+esc(answerMode(q))+' · '+esc(q.knowledge)+'</small>'+(q.answerKind==='choice'?'<div class="options">'+(q.options||[]).map((o,i)=>'<button class="option '+(i===Number(q.correctIndex)?'selected':'')+'" disabled>'+String.fromCharCode(65+i)+'. '+esc(o)+'</button>').join('')+'</div>':'<div class="notice" style="margin-top:9px">标准答案：'+esc(correctDisplay(q))+'</div>')+'</div>').join('')+'</div>':'<div class="notice">请先生成试卷。</div>','<button class="btn primary" id="reviewPaper">确认题型、答案方式、难度与积分</button>')},
    assign:()=>{const p=d.papers?.at(-1),cls=d.classes?.at(-1),s=d.students?.at(-1);return pageIntro(step,'布置后，关联虚拟学生会得到一份待完成作业。')+pageCard('布置作业',cls?esc(cls.name)+' · '+(s?esc(s.name):'暂无学生'):'暂无班级','<div class="form-grid"><div class="field"><label>作业名称</label><input id="assignTitle" value="'+esc(p?.title||'课后练习')+'"></div><div class="field"><label>截止时间</label><input id="assignDue" value="本周五"></div></div>'+listItems(d.assignments,x=>'<div class="item"><b>'+esc(x.title)+'</b><small>状态：'+esc(x.status)+' · 截止 '+esc(x.due)+'</small></div>'),'<button class="btn primary" id="assignWork">布置给练习班级</button>')},
    student_submission:()=>renderStudentSubmission(step),
    evidence:()=>{const s=d.submissions?.at(-1);return pageIntro(step,'同一次提交会形成分数、逐题结果、知识点正确率、错题和积分，供下一轮教学继续使用。')+pageCard('结果与学习证据',s?'来源：'+(s.source==='manual_virtual_student'?'亲自体验学生端':'关联角色自动模拟'):'暂无提交',s?'<div class="metric-grid"><div class="metric"><strong>'+s.score+'%</strong><small>得分</small></div><div class="metric"><strong>'+s.correct+'/'+s.total+'</strong><small>答对</small></div><div class="metric"><strong>'+s.accuracy+'%</strong><small>'+esc(s.knowledge)+'</small></div><div class="metric"><strong>'+s.wrongCount+'</strong><small>错题</small></div></div><div class="notice ok" style="margin-top:12px">这份证据只在沙盒里。正式使用时，它会按角色权限进入学生、教师和家长对应页面。</div>':'<div class="notice">请先让虚拟学生提交，或选择自动模拟。</div>','<button class="btn primary" id="evidenceDone">我已理解结果如何回流</button>')},
    targeted:()=>{const sub=d.submissions?.at(-1);return pageIntro(step,'不是重新随机出题，而是根据刚才形成的证据生成下一轮练习草稿。')+pageCard('AI 针对性练习',sub?'依据：最近提交 + '+esc(sub.knowledge)+' 错题':'暂无依据','<div class="form-grid"><div class="field"><label>针对题量</label><select id="targetCount"><option>3</option><option selected>6</option><option>10</option></select></div></div>'+listItems(d.targeted_practices,x=>'<div class="item"><b>'+esc(x.knowledge)+' 针对练习</b><small>'+x.questionCount+'题 · 状态 '+esc(x.status)+'</small></div>'),'<button class="btn primary" id="createTarget">生成针对性练习草稿</button>')},
    class_review:()=>pageIntro(step,'把学生个体证据汇总成班级共性问题，由教师决定是否形成课堂复盘。')+pageCard('课堂复盘','教师决定是否生成讲义草稿。',listItems(d.class_reviews,x=>'<div class="item"><b>'+esc(x.summary)+'</b><small>状态：'+esc(x.status)+'</small></div>'),'<button class="btn primary" id="createReview">生成复盘讲义草稿</button>'),
    interactive:()=>pageIntro(step,'选择讲解方式，再用随堂检测收口。邀请学生讲解始终由教师决定。')+pageCard('互动课堂与随堂检测','模拟真实课堂控制，不自动推进。','<div class="form-grid"><div class="field"><label>讲解方式</label><select id="classMode"><option>教师讲解</option><option>学生讲解</option><option selected>师生共讲</option><option>讨论</option><option>暂不讲</option></select></div><div class="field"><label>随堂检测反馈</label><select id="studentResponse"><option>已完成</option><option>需要再讲</option></select></div></div>'+listItems(d.classroom_events,x=>'<div class="item"><b>'+esc(x.mode)+'</b><small>随堂检测：'+(x.quickCheck?'已开放':'未开放')+' · '+esc(x.studentResponse)+'</small></div>'),'<button class="btn primary" id="runClass">完成一次课堂互动</button>'),
    points:()=>pageIntro(step,'积分不是学习成绩。必须能看到来源，并区分自动积分与教师课堂评价。学习积分口径：每题完成得 1 分，答对再加 1 分。同一件事只记一次积分，重复提交或重复点结算不会再加分；老师手工加减分不受这个限制。')+pageCard('积分与课堂评价','查看刚才提交产生的练习积分。',listItems(d.points,x=>'<div class="item"><b>+'+esc(x.points)+' 学习积分</b><small>来源：'+esc(x.source)+'</small></div>'),'<button class="btn primary" id="pointsDone">确认积分来源</button>'),
    history:()=>pageIntro(step,'教学结束后进入只读历史，但学生连续档案继续保留。')+pageCard('往期教学','结束班级不是删除学生。',listItems(d.history,x=>'<div class="item"><b>'+esc(x.className)+'</b><small>状态：只读历史</small></div>'),'<button class="btn primary" id="archiveHistory">把练习班级放入历史</button>'),
    transition:()=>{const s=d.students?.at(-1);return pageIntro(step,'升年级改变阶段，不重新创建学生。')+pageCard('升年级与升学衔接',s?esc(s.name)+' · 同一学生档案':'暂无学生','<div class="form-grid"><div class="field"><label>上一阶段</label><input id="transitionFrom" value="五年级"></div><div class="field"><label>下一阶段</label><input id="transitionTo" value="六年级"></div></div>'+listItems(d.transitions,x=>'<div class="item"><b>'+esc(x.from)+' → '+esc(x.to)+'</b><small>同一学生档案 #'+esc(x.studentID)+'</small></div>'),'<button class="btn primary" id="createTransition">建立练习衔接计划</button>')},
    hub:()=>pageIntro(step,'最后从功能关系图回看整条链，理解每个页面的上游、下游和角色交接。')+pageCard('全部功能关系图','不是菜单清单，而是业务链。','<div class="map-grid">'+session.flow.map((x,i)=>'<div class="map-node"><b>'+(i+1)+'. '+esc(x.title)+'</b><small>'+esc(x.page)+'<br>'+esc(session.relationships?.[x.id]?.next||'继续当前角色主线')+'</small></div>').join('')+'</div>','<button class="btn primary" id="finishTraining">完成本轮实操训练</button>')
  };
  stage.innerHTML=(views[step.id]||(()=>auxiliaryPage(step,'教师',teacherAuxDetail(step.id))))();bindTeacher(step);
}
function teacherAuxDetail(id){
  return ({
    teacher_follow_ups:'在“晚托作业助手”顶部的“待跟进”标签：系统挑出今天最需要你留意的求助，每条写明原因（学生主动求助／AI 解答验算未通过，已转给老师／已讲解，尚无独立巩固结果）和验证状态（无法匹配知识点／尚无后续作答／题量不足待补充／已有结果尚未达标／无法判定；后续练习达到条件的会自动移出）。打开列表时系统先确认当天名额再显示：每个班每天最多 5 条，同一学生当天最多 1 条；点“已处理”或“今天先不提醒”都不返还名额；一个学生同时在两个班，会同时占两个班的名额。点“已处理”只是收起这条建议，求助本身的状态不变，仍要到“求助列表”里确认。这是试点功能，学生和家长看不到这份列表。',
    teacher_resources:'这里管理教材、教案和课件。私有备课资料与学生可见资料必须区分。',
    teacher_catalog:'这里浏览教材题库并为组卷/AI出题提供上游资源；浏览题库不等于给学生布置任务。导入或拍照上传的题目也在这里：按学科、教材和单元查找，单元就是导入时填写的单元；题库里已有完全相同的题（带插图的题除外）会直接沿用、不重复保存，仍在它原来的单元下；勾选题目后可批量修改单元或教材（老师只能改自己导入或创建的题目，管理员可改本校所有题目）。',
    teacher_audit:'这里回看教师自己的操作记录，帮助确认谁在什么时间做了什么。',
    teacher_leaderboard:'这里查看班级激励排行；它用于激励，不替代学情诊断。',
    teacher_homework:'在“全部功能”里点“晚托作业助手”：把家长转发的作业通知粘贴进来（或上传截图），AI 整理成清单，你逐条核对、选好学生再发布。从“待跟进”点开建议会自动定位对应学生与求助详情；“待跟进”标签每个班每天最多推 5 条、同一学生当天 1 条，点“已处理”只收起建议、不返还名额，也不改变求助状态；学生点“求助老师”后，也可在“求助列表”查看AI引导、学生做到哪一步；圆面积辅导另附卡点、图示轮次和当前状态的短摘要。补救确认不进入正式提交或掌握度，由你另安排审核后的独立题验证。AI可能整理错，发布前一定要核对。',
    account:'这里管理当前账号、设备和登录相关设置，不改变学生学习事实。'
  })[id]||'请理解这一页在教师完整工作流中的位置。';
}
function renderStudentSubmission(step){
  const d=session.data||{},a=d.assignments?.at(-1),p=d.papers?.at(-1),s=d.students?.at(-1),sub=d.submissions?.at(-1);
  if(sub)return pageIntro(step,'这份练习已提交，可以继续查看证据；如需重做可重置沙盒。')+pageCard('学生作答已完成',esc(sub.studentName),'<div class="metric-grid"><div class="metric"><strong>'+sub.score+'%</strong><small>得分</small></div><div class="metric"><strong>'+sub.correct+'/'+sub.total+'</strong><small>答对</small></div></div>','<button class="btn primary" id="submissionDone">继续查看教师端结果</button>');
  if(session.currentRole==='student'&&a&&p&&s){
    return pageIntro(step,'你现在正在临时体验关联虚拟学生。主身份仍是教师，不需要重新登录。')+pageCard('我的作业 · '+esc(a.title),esc(s.name)+' · '+esc(a.due),questionPager(p,'answerOption','answerInput'),'<button class="btn" id="returnTeacher">返回教师视角</button><button class="btn primary" id="studentSubmit">提交这份练习</button>');
  }
  return pageIntro(step,'这里由你选择：亲自切到关联虚拟学生完成作答，或者保持教师身份由沙盒自动模拟一次学生提交。')+pageCard('关联角色体验方式',a?esc(a.title):'请先布置作业','<div class="mode-grid"><button class="mode" id="switchStudent"><b>亲自体验学生端</b><small>临时切换到小禾，不重新登录；真正逐题选择答案并提交，然后返回教师身份。</small></button><button class="mode" id="simulateStudent"><b>自动模拟关联数据</b><small>保持教师身份，由沙盒生成一次合理的学生提交，直接继续教师端结果回流。</small></button></div>','');
}
function renderNonTeacher(step){
  const role=session.primaryRole,d=session.data||{},rel=relation(step);
  if(role==='student')return renderStudentRole(step,d,rel);
  if(role==='parent')return renderParentRole(step,d,rel);
  if(role==='admin')return renderAdminRole(step,d,rel);
  stage.innerHTML=pageIntro(step)+pageCard(step.title,'页面：'+step.page,'<div class="notice">当前身份暂未配置实操页面。</div>','<button class="btn primary" id="genericDone">完成本页学习</button>');
  document.getElementById('genericDone').onclick=()=>markStep();
}
function roleRelationBlock(rel){
  return '<div class="relation"><div><b>可见范围</b><span>'+esc(rel.visible_to||'按角色权限')+'</span></div><div><b>沟通提示</b><span>'+esc(rel.communication_tip||'确认任务状态、入口和下一步责任人')+'</span></div><div><b>下一步</b><span>'+esc(rel.next||'继续角色主线')+'</span></div></div>';
}
function renderStudentRole(step,d,rel){
  const s=d.students?.at(-1),a=d.assignments?.at(-1),p=d.papers?.at(-1),sub=d.submissions?.at(-1);
  const done='<button class="btn primary" id="roleDone">完成本页实操</button>';
  if(step.id==='classroom'){
    stage.innerHTML=pageIntro(step,'先理解课堂邀请、随堂检测与教师课堂控制之间的关系。')+pageCard('同步课堂',s?esc(s.className)+' · 教师 '+esc(d.classes?.at(-1)?.teacher||'周老师'):'虚拟课堂','<div class="notice">当前课堂知识点：小数乘法。讲解邀请可以接受或拒绝；拒绝不会形成负面学习证据。</div>'+roleRelationBlock(rel),done);
  }else if(step.id==='assignments'){
    stage.innerHTML=pageIntro(step,'找到教师刚布置的任务，确认名称、截止时间和提交状态。')+pageCard('我的作业','正式系统会区分待完成、进行中和已完成；沙盒本步演示首次完整提交。',listItems(d.assignments,x=>'<div class="item"><b>'+esc(x.title)+'</b><small>截止 '+esc(x.due)+' · '+(sub?'已完成':'待完成')+'</small></div>')+roleRelationBlock(rel),done);
  }else if(step.id==='answer'){
    stage.innerHTML=pageIntro(step,'正式系统会自动保存草稿，也可以逐题正式提交；每道题默认合计 4 次机会，互相独立。沙盒本步用一次完整提交演示结果回流。')+pageCard('逐题作答',a?esc(a.title):'暂无作业',sub?'<div class="notice ok">这份练习已经完成首次提交。正式系统仍可逐题修改，老师也可追加次数；修改不会重复发完成积分。</div>':(p?questionPager(p,'studentSelfOption','studentSelfInput'):'<div class="notice">暂无题目。</div>'),sub?done:'<button class="btn primary" id="studentSelfSubmit">正式提交</button>');
  }else if(step.id==='result'){
    stage.innerHTML=pageIntro(step,'部分题正式提交后先显示进行中，分数仍以全卷为分母；首次覆盖全部题目才完成并发一次积分。一次分数不代表长期掌握结论。')+pageCard('提交结果',sub?esc(sub.studentName):'尚未提交',sub?'<div class="metric-grid"><div class="metric"><strong>'+sub.score+'%</strong><small>得分</small></div><div class="metric"><strong>'+sub.correct+'/'+sub.total+'</strong><small>答对</small></div><div class="metric"><strong>'+sub.wrongCount+'</strong><small>错题</small></div><div class="metric"><strong>'+esc(sub.knowledge)+'</strong><small>知识点</small></div></div>'+roleRelationBlock(rel):'<div class="notice warn">请先完成上一页的正式提交。</div>',done);
  }else if(step.id==='practice'){
    stage.innerHTML=pageIntro(step,'针对性练习说明“为什么给我这些题”，并继续把结果回流到同一档案。')+pageCard('针对性练习','依据最近提交和错题生成。',listItems(d.targeted_practices,x=>'<div class="item"><b>'+esc(x.knowledge)+' · '+x.questionCount+'题</b><small>状态：'+esc(x.status)+'</small></div>')+roleRelationBlock(rel),d.targeted_practices?.length?'<button class="btn primary" id="completeStudentPractice">完成这组针对练习</button>':done);
  }else if(step.id==='progress'){
    stage.innerHTML=pageIntro(step,'学情看长期趋势和证据来源，不只是一个考试分数。')+pageCard('我的学情','来自作业、练习和课堂事实。',sub?'<div class="metric-grid"><div class="metric"><strong>'+sub.score+'%</strong><small>最近练习</small></div><div class="metric"><strong>'+esc(sub.knowledge)+'</strong><small>当前关注</small></div><div class="metric"><strong>'+d.wrong_questions.length+'</strong><small>待巩固错题</small></div><div class="metric"><strong>'+d.points.reduce((n,x)=>n+Number(x.points||0),0)+'</strong><small>积分</small></div></div>'+roleRelationBlock(rel):'<div class="notice">提交一次练习后这里会出现证据。</div>',done);
  }else if(step.id==='rewards'){
    stage.innerHTML=pageIntro(step,'积分用于激励，必须能看到来源，不能把积分误解成学习成绩。')+pageCard('积分奖励','每一笔都可追溯来源。',listItems(d.points,x=>'<div class="item"><b>+'+esc(x.points)+' 积分</b><small>'+esc(x.source)+'</small></div>')+roleRelationBlock(rel),done);
  }else if(step.id==='wrongbook'){
    stage.innerHTML=pageIntro(step,'错题用于下一轮学习，不是给学生贴负面标签。')+pageCard('我的错题','来自刚才的提交结果。',listItems(d.wrong_questions,x=>'<div class="item"><b>'+esc(x.prompt)+'</b><small>'+esc(x.knowledge)+'</small></div>')+roleRelationBlock(rel),done);
  }else if(step.id==='student_home'){
    stage.innerHTML=pageIntro(step,'学习首页只负责汇总今天要做什么；看到任务不等于已经完成。')+pageCard('学习首页',s?esc(s.name)+' · '+esc(s.className):'学生首页','<div class="metric-grid"><div class="metric"><strong>'+d.assignments.length+'</strong><small>作业</small></div><div class="metric"><strong>'+d.targeted_practices.length+'</strong><small>针对练习</small></div><div class="metric"><strong>'+d.wrong_questions.length+'</strong><small>错题</small></div><div class="metric"><strong>'+d.points.reduce((n,x)=>n+Number(x.points||0),0)+'</strong><small>积分</small></div></div>'+roleRelationBlock(rel),done);
  }else if(step.id==='student_homework'){
    stage.innerHTML=pageIntro(step,'老师发来的家庭作业清单，和拍题求助，都在“晚托作业助手”里。')+pageCard('晚托作业助手','在底栏“作业”页顶部看到家庭作业；不会的题可以拍下来问 AI。','<div class="item"><b>今天的家庭作业</b><small>老师发布后，作业页顶部会出现清单；点进助手，做完一项就在前面打勾。</small></div><div class="item"><b>这道题我不会</b><small>只拍这一道题，拖动白框框住题目，确认识别出的文字，再让 AI 一步一步引导你：先从你知识地图上已经会的知识想起，每一步先回答一个小问题，答错了有提示；最后的答案要自己算出来。AI 可能出错，请自己判断。</small></div><div class="item"><b>真的会了吗</b><small>讲完点“去做同类题”，在知识地图上做 3～5 道这个知识点的新题。只算第一次作答，做对了地图上的颜色会变。</small></div><div class="item"><b>圆的面积刚学不懂</b><small>六年级圆面积题可选先回忆基础，普通求助不用多选一步。固定图示区分半径/直径、平方和圆周长，按题目给定的π取值回到原题；同一卡点两轮未过就请老师。这里的确认题只记辅导过程，不改变掌握度；没有可用审核新题时请老师安排验证。</small></div><div class="item"><b>还是不会</b><small>点“求助老师”，老师会看到你的题目、AI 的引导，和你自己做到了哪一步，再来帮你。</small></div>'+roleRelationBlock(rel),done);
  }else if(TOURS[step.id]){
    stage.innerHTML=tourPage(step,'学生','roleDone');
  }else if(step.id==='student_leaderboard'){
    stage.innerHTML=pageIntro(step,'班级排行用于激励，不代表学习能力排名。')+pageCard('班级排行','只理解展示规则和边界。','<div class="notice">你的练习积分会影响允许展示的班级排行，但教师仍应使用学情、错题和课堂证据判断下一步教学。</div>'+roleRelationBlock(rel),done);
  }else{
    stage.innerHTML=pageIntro(step,'理解账号、身份和当前教学归属。')+pageCard('我的账号',s?esc(s.name)+' · 学生':'学生账号','<div class="item"><b>当前班级</b><small>'+esc(s?.className||'五年级实操班')+'</small></div>'+roleRelationBlock(rel),done);
  }
  bindStudentRole();
}
function bindStudentRole(){
  const done=document.getElementById('roleDone');if(done)done.onclick=()=>markStep();
  bindQuestionPager('studentSelfOption','studentSelfInput');
  const submit=document.getElementById('studentSelfSubmit');if(submit)submit.onclick=()=>act('student_submit_self',{answers});
  const practice=document.getElementById('completeStudentPractice');if(practice)practice.onclick=()=>act('complete_student_practice',{});
}
function renderParentRole(step,d,rel){
  if(TOURS[step.id]){stage.innerHTML=tourPage(step,'家长','parentDone');document.getElementById('parentDone').onclick=()=>markStep();return}
  const child=d.students?.at(-1),cls=d.classes?.at(-1),assignment=d.assignments?.at(-1),sub=d.submissions?.at(-1);
  let body='';
  if(step.id==='parent_home')body='<div class="metric-grid"><div class="metric"><strong>'+esc(child?.name||'小禾')+'</strong><small>当前孩子</small></div><div class="metric"><strong>'+d.assignments.length+'</strong><small>作业</small></div><div class="metric"><strong>'+esc(sub?.score??'—')+'</strong><small>最近结果</small></div><div class="metric"><strong>'+d.points.reduce((n,x)=>n+Number(x.points||0),0)+'</strong><small>积分</small></div></div>';
  else if(step.id==='learning')body='<div class="item"><b>'+esc(child?.name||'小禾')+'</b><small>'+esc(cls?.name||'五年级实操班')+' · 教师 '+esc(cls?.teacher||'周老师')+'</small></div>';
  else if(step.id==='assignments')body='<div class="item"><b>'+esc(assignment?.title||'小数乘法练习')+'</b><small>截止 '+esc(assignment?.due||'本周五')+' · '+(sub?'已完成':'待完成')+'。家长只查看状态，不代替孩子作答。</small></div>';
  else if(step.id==='progress')body=sub?'<div class="metric-grid"><div class="metric"><strong>'+sub.score+'%</strong><small>最近练习</small></div><div class="metric"><strong>'+esc(sub.knowledge)+'</strong><small>需要关注</small></div><div class="metric"><strong>'+sub.wrongCount+'</strong><small>错题</small></div><div class="metric"><strong>趋势</strong><small>看长期变化</small></div></div>':'<div class="notice">暂无结果。</div>';
  else if(step.id==='rewards')body=listItems(d.points,x=>'<div class="item"><b>+'+esc(x.points)+' 积分</b><small>'+esc(x.source)+' · 积分不是成绩</small></div>');
  else if(step.id==='history')body='<div class="item"><b>连续档案</b><small>当前：'+esc(cls?.name||'五年级实操班')+'；往期：'+esc(d.history?.at(-1)?.className||'四年级实操班')+'。升年级仍是同一个孩子。</small></div>';
  else body='<div class="item"><b>关联孩子</b><small>'+esc(child?.name||'小禾')+' · 家长只能看到已授权关联的孩子。</small></div>';
  stage.innerHTML=pageIntro(step,'家长端重点是理解孩子发生了什么，而不是替教师或孩子操作。')+pageCard(step.title,'家长可见范围与教师/学生端不同。',body+roleRelationBlock(rel),'<button class="btn primary" id="parentDone">完成本页实操</button>');
  document.getElementById('parentDone').onclick=()=>markStep();
}
function renderAdminRole(step,d,rel){
  const done='<button class="btn primary" id="adminDone">完成本页实操</button>';
  if(step.id==='overview'){
    stage.innerHTML=pageIntro(step,'管理员先看平台关系和异常，不直接替教师完成教学。')+pageCard('平台总览','虚拟机构数据','<div class="metric-grid"><div class="metric"><strong>'+d.accounts.filter(x=>x.role==='teacher').length+'</strong><small>教师账号</small></div><div class="metric"><strong>'+d.accounts.filter(x=>x.role==='student').length+'</strong><small>学生账号</small></div><div class="metric"><strong>'+d.classes.length+'</strong><small>班级</small></div><div class="metric"><strong>'+d.audit.length+'</strong><small>审计事件</small></div></div>'+roleRelationBlock(rel),done);
  }else if(step.id==='users'){
    stage.innerHTML=pageIntro(step,'真实创建一个临时教师或家长账号，理解角色边界。')+pageCard('账号管理','创建的账号只存在于沙盒。','<div class="form-grid"><div class="field"><label>姓名</label><input id="adminUserName" value="林老师"></div><div class="field"><label>账号</label><input id="adminUsername" value="teacher02"></div><div class="field"><label>角色</label><select id="adminRole"><option value="teacher">教师</option><option value="parent">家长</option></select></div></div>'+listItems(d.accounts,x=>'<div class="item"><b>'+esc(x.name)+' · '+esc(x.role)+'</b><small>'+esc(x.username)+' · '+esc(x.status)+'</small></div>'),'<button class="btn primary" id="adminCreateAccount">创建练习账号</button>');
  }else if(step.id==='classes'){
    stage.innerHTML=pageIntro(step,'班级关系决定谁在教谁；调班换老师应改变关系，不复制学生档案。')+pageCard('班级与教学归属','把班级关联到虚拟教师。','<div class="form-grid"><div class="field"><label>班级名称</label><input id="adminClassName" value="五年级二班"></div><div class="field"><label>年级</label><select id="adminClassGrade"><option>4</option><option selected>5</option><option>6</option></select></div></div>'+listItems(d.classes,x=>'<div class="item"><b>'+esc(x.name)+'</b><small>'+x.grade+'年级 · 教师 '+esc(x.teacher)+'</small></div>'),'<button class="btn primary" id="adminCreateClass">建立班级归属</button>');
  }else if(step.id==='points'){
    stage.innerHTML=pageIntro(step,'管理员维护规则，教师课堂评价和学生实际积分仍保持来源可追溯。')+pageCard('积分规则','修改规则不应回写历史积分。','<div class="form-grid"><div class="field"><label>规则名称</label><input id="pointRuleName" value="课堂参与"></div><div class="field"><label>积分</label><input id="pointRuleValue" type="number" value="2"></div></div>'+listItems(d.point_rules,x=>'<div class="item"><b>'+esc(x.name)+' +'+esc(x.points)+'</b><small>状态：'+(x.active?'启用':'停用')+'</small></div>'),'<button class="btn primary" id="adminPointRule">保存练习规则</button>');
  }else if(step.id==='audit'){
    stage.innerHTML=pageIntro(step,'审计用于回答“谁在什么时候做了什么”，不是修改业务事实的入口。')+pageCard('全校审计','刚才的沙盒管理动作已经进入临时审计时间线。',listItems(d.audit,x=>'<div class="item"><b>'+esc(x.action)+'</b><small>'+esc(x.actor)+' · '+esc(x.detail)+'</small></div>')+roleRelationBlock(rel),done);
  }else if(step.id==='system'){
    stage.innerHTML=pageIntro(step,'系统设置影响功能可用性，但不能绕过权限或改写历史学习证据。')+pageCard('系统设置','在沙盒中练习一个设置变更。','<div class="form-grid"><div class="field"><label>设置项</label><input id="systemKey" value="trainingFeature"></div><div class="field"><label>值</label><select id="systemValue"><option>开启</option><option>关闭</option></select></div></div><div class="notice">当前设置：'+esc(JSON.stringify(d.system_settings))+'</div>','<button class="btn primary" id="adminSystemSave">保存练习设置</button>');
  }else if(step.id==='history'){
    stage.innerHTML=pageIntro(step,'从管理员视角确认历史班级、账号关系和学生连续性仍能追踪。')+pageCard('历史连续性','管理关系变化，不能删除学生历史事实。','<div class="notice">班级、教师和账号关系可以变化；学生连续档案仍保持同一主体。沙盒审计事件：'+d.audit.length+' 条。</div>'+roleRelationBlock(rel),done);
  }else{
    stage.innerHTML=auxiliaryPage(step,'管理员',adminAuxDetail(step.id));
  }
  bindAdminRole();
}
function adminAuxDetail(id){
  return ({
    admin_subscription:'这里管理套餐和功能授权。它决定功能是否可用，但不应该改写任何历史学习事实。',
    admin_ai:'这里设置 AI 服务和学生数据授权边界。密钥只属于管理员；教师仍保留审核发布权。使用晚托作业助手前，要先“启用”并勾选“允许发送学生内容”。',
    admin_teaching:'这里配置学校/机构的教学计划和课时；配置与正式发布是两个动作。',
    admin_resources:'这里管理教材、教案和课件资源，必须区分学校自有资料、官方导航和学生可见范围。',
    admin_imports:'这里批量导入账号和基础关系。导入前要核对重复账号、班级和角色，避免批量制造关系错误。',
    admin_catalog:'这里维护教材题库上游资源；学生不会直接看到后台题库配置。'
  })[id]||'请理解这一管理页面如何影响教师、学生和家长端。';
}
function bindAdminRole(){
  const $=id=>document.getElementById(id);
  if($('adminDone'))$('adminDone').onclick=()=>markStep();
  if($('auxDone'))$('auxDone').onclick=()=>markStep();
  if($('adminCreateAccount'))$('adminCreateAccount').onclick=()=>act('admin_create_account',{name:$('adminUserName').value,username:$('adminUsername').value,role:$('adminRole').value});
  if($('adminCreateClass'))$('adminCreateClass').onclick=()=>act('admin_create_class',{name:$('adminClassName').value,grade:+$('adminClassGrade').value});
  if($('adminPointRule'))$('adminPointRule').onclick=()=>act('admin_set_point_rule',{name:$('pointRuleName').value,points:+$('pointRuleValue').value});
  if($('adminSystemSave'))$('adminSystemSave').onclick=()=>act('admin_set_system',{key:$('systemKey').value,value:$('systemValue').value});
}
function bindTeacher(step){
  const $=id=>document.getElementById(id);
  if($('understand'))$('understand').onclick=()=>markStep();
  if($('auxDone'))$('auxDone').onclick=()=>markStep();
  if($('createClass'))$('createClass').onclick=()=>act('create_class',{name:$('className').value,grade:+$('classGrade').value});
  if($('addStudent'))$('addStudent').onclick=()=>act('add_student',{name:$('studentName').value,username:$('studentUser').value});
  if($('profileDone'))$('profileDone').onclick=()=>markStep();
  if($('paperSubject')&&$('paperKnowledge'))$('paperSubject').onchange=()=>{$('paperKnowledge').value=({数学:'小数乘法',语文:'词语理解与表达',英语:'基础词汇与句型'}[$('paperSubject').value]||$('paperKnowledge').value)};
  if($('createPaper'))$('createPaper').onclick=()=>act('create_paper',{subject:$('paperSubject').value,textbook:$('paperTextbook').value,knowledge:$('paperKnowledge').value,questionCount:+$('paperCount').value});
  if($('reviewPaper'))$('reviewPaper').onclick=()=>act('review_paper',{});
  if($('assignWork'))$('assignWork').onclick=()=>act('assign',{title:$('assignTitle').value,due:$('assignDue').value});
  if($('switchStudent'))$('switchStudent').onclick=()=>act('switch_to_student',{});
  if($('simulateStudent'))$('simulateStudent').onclick=()=>act('simulate_student_submission',{});
  if($('returnTeacher'))$('returnTeacher').onclick=()=>act('return_primary_role',{});
  bindQuestionPager('answerOption','answerInput');
  if($('studentSubmit'))$('studentSubmit').onclick=()=>act('student_submit',{answers});
  if($('submissionDone'))$('submissionDone').onclick=async()=>{if(session.currentRole!=='teacher')await act('return_primary_role',{});await markStep()};
  if($('evidenceDone'))$('evidenceDone').onclick=()=>markStep();
  if($('createTarget'))$('createTarget').onclick=()=>act('create_targeted_practice',{questionCount:+$('targetCount').value});
  if($('createReview'))$('createReview').onclick=()=>act('create_class_review',{});
  if($('runClass'))$('runClass').onclick=()=>act('run_interactive_classroom',{mode:$('classMode').value,studentResponse:$('studentResponse').value});
  if($('pointsDone'))$('pointsDone').onclick=()=>act('review_points',{});
  if($('archiveHistory'))$('archiveHistory').onclick=()=>act('archive_history',{});
  if($('createTransition'))$('createTransition').onclick=()=>act('create_transition',{from:$('transitionFrom').value,to:$('transitionTo').value});
  if($('finishTraining'))$('finishTraining').onclick=async()=>{await markStep();openDrawer('训练完成','<p>你已经走完当前身份的完整教师主线。以后可以从训练地图选择任一步复习，或载入预置场景快速重练。</p><div class="action-row"><button class="btn danger" id="finishReset">清空并重新练</button><a class="btn primary" href="/v1/workspace">进入真实工作台</a></div>');document.getElementById('finishReset').onclick=resetAll};
}
function openDrawer(title,html){drawerTitle.textContent=title;drawerBody.innerHTML=html;drawer.classList.remove('hidden')}
function showRelation(){
 const s=current(),r=relation(s);openDrawer('角色关系 · '+s.title,'<div class="list"><div class="item"><b>谁操作</b><small>'+esc(r.who||roleName(session.currentRole))+'</small></div><div class="item"><b>产生什么</b><small>'+esc(r.creates||'训练进度')+'</small></div><div class="item"><b>谁能看到</b><small>'+esc(r.visible_to||'按权限显示')+'</small></div><div class="item"><b>其他角色看到什么</b><small>'+esc(r.other_role_sees||'按角色页面呈现')+'</small></div><div class="item"><b>沟通时最应该说明</b><small>'+esc(r.communication_tip||'确认当前状态、入口和下一步责任人')+'</small></div><div class="item"><b>下一步</b><small>'+esc(r.next||'继续主线')+'</small></div></div>')
}
async function resetAll(){if(!confirm('清空本次实操沙盒并从头重新练习？'))return;session=await request('/v1/training-sandbox/'+session.sessionID+'/reset',{method:'POST',body:'{}'});index=0;answers={};sessionStorage.setItem(INDEX_KEY,'0');render();drawer.classList.add('hidden')}
async function openTrainingCleanup(){
  try{
    const preview=await request('/v1/training-sandbox/cleanup-preview');
    const count=Number(preview.eligibleSessionCount||0);
    openDrawer('正式使用前 · 清空演示数据',
      '<div class="notice">安全范围：只清除当前账号的临时实操沙盒。真实班级、学生、作业、提交、积分、错题和学习证据不会被修改。</div>'+
      '<div class="item" style="margin-top:12px"><b>可清理的临时实操会话：'+count+' 个</b><small>清理后将返回真实工作台。以后需要教学演示时可重新进入新手实操。</small></div>'+
      (count?'<button class="btn danger" id="confirmTrainingCleanup" style="margin-top:12px">确认清空演示数据</button>':'<a class="btn primary" href="/v1/workspace" style="margin-top:12px">返回真实工作台</a>')
    );
    const btn=document.getElementById('confirmTrainingCleanup');
    if(btn)btn.onclick=async()=>{
      btn.disabled=true;btn.textContent='正在清理…';
      try{
        const result=await request('/v1/training-sandbox/cleanup-all',{method:'POST',body:'{}'});
        sessionStorage.removeItem(SESSION_KEY);sessionStorage.setItem(INDEX_KEY,'0');
        session=null;answers={};index=0;
        location.href='/v1/workspace?training_cleanup=1&cleared='+encodeURIComponent(String(result.clearedSessionCount||0));
      }catch(e){
        btn.disabled=false;btn.textContent='确认清空演示数据';
        showActionError(e);
      }
    };
  }catch(e){showActionError(e)}
}
async function askAssistant(){
 openDrawer('产品助手','<div class="assistant-log" id="assistantLog"><div class="assistant-msg ai">可以问：这个页面有什么用？其他角色会看到什么？我下一步应该做什么？</div></div><div class="field"><label>问题</label><textarea id="assistantQuestion" placeholder="例如：学生提交以后，教师和家长分别能看到什么？"></textarea></div><button class="btn primary" id="assistantSend" style="margin-top:9px">发送</button>');
 document.getElementById('assistantSend').onclick=async()=>{const q=document.getElementById('assistantQuestion').value.trim();if(!q)return;const log=document.getElementById('assistantLog');log.insertAdjacentHTML('beforeend','<div class="assistant-msg">'+esc(q)+'</div>');try{const d=await request('/v1/product-assistant/query',{method:'POST',body:JSON.stringify({question:q,page:current().page,identity:roleName(session.currentRole),tutorial_step:current().title})});log.insertAdjacentHTML('beforeend','<div class="assistant-msg ai">'+esc(d.reply)+'</div>')}catch(e){log.insertAdjacentHTML('beforeend','<div class="assistant-msg ai">'+esc(e.message)+'</div>')}}
}
function openMobileMore(){
  const step=current();if(!step)return;
  openDrawer('本步操作','<div class="list"><button class="item" id="mobileMap"><b>训练路线</b><small>查看全部步骤和快速场景</small></button><button class="item" id="mobileRelation"><b>角色关系</b><small>这一步由谁做、产生什么、其他角色看到什么</small></button><button class="item" id="mobileRepeat"><b>重做本步</b><small>保留上游数据，从当前步骤重新操作</small></button><button class="item" id="mobileSkip"><b>跳过本步</b><small>以后可从训练路线回来复习</small></button><button class="item" id="mobileAsk"><b>问产品助手</b><small>结合当前身份和页面回答怎么用</small></button><button class="item" id="mobileFeedback"><b>反馈这个页面</b><small>把当前步骤和问题一起提交</small></button><button class="item" id="mobileCleanup"><b>正式使用前 · 清空演示数据</b><small>只清除临时实操沙盒，真实教学数据不会受影响</small></button></div>');
  document.getElementById('mobileMap').onclick=()=>{drawer.classList.add('hidden');rail.classList.add('open')};
  document.getElementById('mobileRelation').onclick=()=>{drawer.classList.add('hidden');showRelation()};
  document.getElementById('mobileRepeat').onclick=async()=>{drawer.classList.add('hidden');answers={};await act('rewind_step',{step:current().id})};
  document.getElementById('mobileSkip').onclick=async()=>{drawer.classList.add('hidden');await markStep('skipped');if(index<session.flow.length-1)setIndex(index+1)};
  document.getElementById('mobileAsk').onclick=()=>{drawer.classList.add('hidden');askAssistant()};
  document.getElementById('mobileFeedback').onclick=()=>{drawer.classList.add('hidden');sendTrainingFeedback()};
  document.getElementById('mobileCleanup').onclick=()=>{drawer.classList.add('hidden');openTrainingCleanup()};
}
async function sendTrainingFeedback(){
  openDrawer('训练反馈','<div class="notice">反馈会附带当前身份、当前功能页和训练步骤，进入长缨 / Freeman 产品反馈链；不会附带沙盒答题内容。</div><div class="field" style="margin-top:12px"><label>类型</label><select id="feedbackCategory"><option>操作不清楚</option><option>页面难用</option><option>流程太繁琐</option><option>角色关系不清楚</option><option>功能建议</option><option>其他反馈</option></select></div><div class="field" style="margin-top:9px"><label>反馈内容</label><textarea id="feedbackMessage" placeholder="告诉我们具体卡在哪一步、期待怎样改。"></textarea></div><button class="btn primary" id="feedbackSend" style="margin-top:9px">提交反馈</button><div id="feedbackResult" class="small muted" style="margin-top:8px"></div>');
  document.getElementById('feedbackSend').onclick=async()=>{const message=document.getElementById('feedbackMessage').value.trim();if(!message)return;const btn=document.getElementById('feedbackSend');btn.disabled=true;try{await request('/v1/product-feedback',{method:'POST',body:JSON.stringify({category:document.getElementById('feedbackCategory').value,message,page:current().page,identity:roleName(session.currentRole),tutorial_step:current().title})});document.getElementById('feedbackResult').textContent='已提交。谢谢，这条反馈会进入产品优化池。'}catch(e){document.getElementById('feedbackResult').textContent=e.message}finally{btn.disabled=false}}
}
document.getElementById('prevBtn').onclick=()=>setIndex(index-1);
document.getElementById('nextBtn').onclick=()=>setIndex(index+1);
document.getElementById('skipBtn').onclick=async()=>{await markStep('skipped');if(index<session.flow.length-1)setIndex(index+1)};
document.getElementById('resetStepBtn').onclick=async()=>{answers={};await act('rewind_step',{step:current().id})};
document.getElementById('relationBtn').onclick=showRelation;
document.getElementById('drawerClose').onclick=()=>drawer.classList.add('hidden');
drawer.onclick=e=>{if(e.target===drawer)drawer.classList.add('hidden')};
document.getElementById('toggleMap').onclick=()=>rail.classList.toggle('open');
document.getElementById('closeRail').onclick=()=>rail.classList.remove('open');
document.getElementById('askBtn').onclick=askAssistant;
document.getElementById('feedbackBtn').onclick=sendTrainingFeedback;
document.getElementById('cleanupDemoData').onclick=openTrainingCleanup;
document.getElementById('moreBtn').onclick=openMobileMore;
window.addEventListener('unhandledrejection',event=>{event.preventDefault();showActionError(event.reason)});
document.getElementById('loadScenario').onclick=async()=>{const preset=document.getElementById('scenario').value;await act('load_scenario',{preset});const target={empty:0,assigned:7,submitted:8,classroom:10}[preset]??0;setIndex(Math.min(target,session.flow.length-1))};
start();
})();
</script>
<!-- changying_v1_training_workbench_v1 -->
</body>
</html>'''


def training_workbench_html() -> str:
    return _TRAINING_HTML.replace("__BRAND_FONT_B64__", BRAND_FONT_B64).replace(
        '<header class="top">', '<header class="top">' + RIBBON_SVG, 1
    )


def install_v1_training_workbench_route(app: FastAPI) -> None:
    if getattr(app.state, "v1_training_workbench_route_installed", False):
        return

    router = APIRouter()

    @router.get(TRAINING_WORKBENCH_PATH, include_in_schema=False)
    def training_workbench():
        return HTMLResponse(
            training_workbench_html(),
            headers={
                "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                "X-Changying-V1-Training": TRAINING_WORKBENCH_MARKER,
            },
        )

    app.include_router(router)
    app.state.v1_training_workbench_route_installed = True


__all__ = [
    "TRAINING_WORKBENCH_MARKER",
    "TRAINING_WORKBENCH_PATH",
    "install_v1_training_workbench_route",
    "training_workbench_html",
]


