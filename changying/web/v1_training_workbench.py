"""Interactive role training workbench for Changying V1.

This is the primary onboarding surface. It uses the ephemeral training sandbox
API so users operate a complete workflow instead of reading static screenshots.\nThe training bar remains secondary to the actual task surface.
"""

from __future__ import annotations

from fastapi import APIRouter, FastAPI
from fastapi.responses import HTMLResponse

TRAINING_WORKBENCH_PATH = "/v1/training"
TRAINING_WORKBENCH_MARKER = "changying_v1_training_workbench_v1"

_TRAINING_HTML = r'''<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#173c78">
<title>长缨辅学 · 角色实操沙盒</title>
<style>
:root{--navy:#173c78;--ink:#172033;--muted:#667085;--line:#dfe7f2;--soft:#f3f6fb;--blue:#2f6fed;--ok:#247447;--warn:#8b5e00;--danger:#b42318}
*{box-sizing:border-box}html,body{margin:0;min-height:100%;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;color:var(--ink);background:var(--soft);-webkit-text-size-adjust:100%}
button,input,select,textarea{font:inherit}.hidden{display:none!important}.muted{color:var(--muted)}.small{font-size:12px}.tag{display:inline-flex;align-items:center;gap:5px;padding:5px 9px;border-radius:999px;background:#edf3ff;color:var(--navy);font-size:12px;font-weight:800}.tag.ok{background:#eef9f0;color:var(--ok)}.tag.warn{background:#fff7e8;color:var(--warn)}
.top{position:sticky;top:0;z-index:30;background:rgba(255,255,255,.98);border-bottom:1px solid var(--line);padding:10px 14px;backdrop-filter:blur(14px)}
.top-row{max-width:1120px;margin:auto;display:flex;align-items:center;gap:10px}.brand{width:38px;height:38px;border-radius:13px;background:var(--navy);color:white;display:grid;place-items:center;font-weight:900;font-size:20px}.top-copy{min-width:0;flex:1}.top-copy b{display:block;font-size:15px}.top-copy small{display:block;color:var(--muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;margin-top:2px}.top-actions{display:flex;gap:7px}.icon-btn,.btn{border:1px solid #d4deec;background:#fff;color:var(--ink);border-radius:11px;padding:9px 12px;font-weight:800;cursor:pointer}.btn.primary{background:var(--navy);border-color:var(--navy);color:#fff}.btn.soft{background:#edf3ff;color:var(--navy);border-color:#d1def5}.btn.danger{color:var(--danger)}.btn:disabled{opacity:.45;cursor:not-allowed}
.progress-wrap{max-width:1120px;margin:8px auto 0;display:flex;gap:8px;align-items:center}.progress{height:7px;background:#e9eef6;border-radius:999px;overflow:hidden;flex:1}.progress i{display:block;height:100%;background:var(--navy);width:0}.progress-wrap span{font-size:11px;color:var(--muted);min-width:48px;text-align:right}
.layout{max-width:1120px;margin:14px auto 96px;padding:0 14px;display:grid;grid-template-columns:240px minmax(0,1fr);gap:14px}.rail{background:#fff;border:1px solid var(--line);border-radius:18px;padding:12px;align-self:start;position:sticky;top:86px;max-height:calc(100dvh - 110px);overflow:auto}.rail h3{margin:4px 3px 9px}.step{width:100%;border:0;background:transparent;display:grid;grid-template-columns:28px 1fr auto;gap:8px;align-items:center;text-align:left;padding:8px;border-radius:11px;color:var(--ink)}.step.active{background:#eaf1ff}.step.done{background:#eef9f0}.step.skipped{background:#fff7e8}.step.locked{opacity:.46}.step:disabled{cursor:not-allowed}.step-no{width:27px;height:27px;border:1px solid #d7e0ed;border-radius:9px;background:#fff;display:grid;place-items:center;font-size:12px;font-weight:900}.step small{color:var(--muted)}.stage{min-width:0}.card{background:#fff;border:1px solid var(--line);border-radius:18px;padding:18px}.hero{background:linear-gradient(145deg,#eef4ff,#fff)}h1{font-size:25px;margin:5px 0 8px}h2{font-size:19px;margin:0 0 8px}p{line-height:1.65}.relation{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:9px;margin-top:12px}.relation>div{border:1px solid var(--line);background:#fafcff;border-radius:13px;padding:11px}.relation b{display:block;font-size:11px;color:var(--navy);margin-bottom:4px}.relation span{font-size:12px;line-height:1.5;color:#4d5a70}.page-card{margin-top:12px}.page-head{display:flex;justify-content:space-between;align-items:flex-start;gap:10px;padding-bottom:13px;border-bottom:1px solid var(--line)}.page-head h2{font-size:22px;margin:0}.page-head p{margin:4px 0 0;color:var(--muted);font-size:13px}.form-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;margin-top:14px}.field{display:grid;gap:5px}.field label{font-size:12px;color:#475467;font-weight:700}.field input,.field select,.field textarea{width:100%;border:1px solid #cad6e5;border-radius:11px;background:white;padding:11px 12px;color:var(--ink)}.field textarea{min-height:90px}.full{grid-column:1/-1}.action-row{display:flex;flex-wrap:wrap;gap:8px;margin-top:14px}.notice{padding:11px 12px;border-radius:12px;background:#f7f9fc;border:1px solid var(--line);font-size:13px;line-height:1.6}.notice.ok{background:#eef9f0;border-color:#cce9d2;color:#245f33}.notice.warn{background:#fff8e8;border-color:#efd59c;color:#754d00}.list{display:grid;gap:9px;margin-top:12px}.item{border:1px solid var(--line);border-radius:13px;padding:12px;background:#fff}.item b{display:block}.item small{display:block;color:var(--muted);margin-top:4px;line-height:1.5}.question{border:1px solid var(--line);border-radius:14px;padding:13px;margin-top:10px}.options{display:grid;gap:7px;margin-top:9px}.option{border:1px solid #d3ddea;background:#fff;border-radius:10px;padding:10px;text-align:left}.option.selected{border-color:#7da2e8;background:#edf3ff}.answer-input{width:100%;margin-top:10px;border:1px solid #cad6e5;border-radius:11px;background:#fff;padding:11px 12px;color:var(--ink);font:inherit}.answer-input.textarea{min-height:92px;resize:vertical}.question-nav{display:grid;grid-template-columns:auto 1fr auto;align-items:center;gap:8px;margin-top:10px}.question-nav span{text-align:center;font-size:12px;color:var(--muted);font-weight:800}.metric-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:9px;margin-top:12px}.metric{border:1px solid var(--line);border-radius:13px;padding:12px;background:#fafcff}.metric strong{font-size:24px;display:block}.metric small{color:var(--muted)}.mode-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:12px}.mode{border:1px solid #d4deec;border-radius:15px;background:#fff;padding:14px;text-align:left}.mode b{display:block;margin-bottom:6px}.mode small{color:var(--muted);line-height:1.55}.map-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.map-node{border:1px solid var(--line);border-radius:14px;padding:13px;background:#fff}.map-node b{display:block}.map-node small{color:var(--muted);line-height:1.5;display:block;margin-top:4px}
.bottom{position:fixed;left:10px;right:10px;bottom:max(8px,env(safe-area-inset-bottom));z-index:35;background:rgba(255,255,255,.98);border:1px solid var(--line);border-radius:17px;padding:8px;display:flex;gap:7px;justify-content:center;box-shadow:0 16px 48px rgba(20,39,76,.18);backdrop-filter:blur(14px)}.bottom .btn{padding:9px 11px}.bottom #moreBtn{display:none}.spacer{flex:1}.rail-head{display:flex;align-items:center;justify-content:space-between;gap:8px}.rail-head h3{margin:4px 3px 9px}.rail-head .btn{padding:6px 9px;font-size:12px}
.drawer{position:fixed;inset:0;z-index:60;background:rgba(12,25,47,.46);display:flex;justify-content:flex-end}.drawer-panel{width:min(440px,92vw);height:100%;background:#fff;padding:18px;overflow:auto;box-shadow:-14px 0 50px rgba(12,25,47,.22)}.drawer-head{display:flex;justify-content:space-between;gap:10px;align-items:center}.assistant-log{display:grid;gap:8px;margin:12px 0}.assistant-msg{border:1px solid var(--line);border-radius:12px;padding:10px 11px;line-height:1.6;font-size:13px}.assistant-msg.ai{background:#f5f8fd}
@media(max-width:760px){
html,body{overflow-x:hidden}.top{padding:9px 12px}.top-row{gap:9px}.brand{width:42px;height:42px;border-radius:14px;flex:0 0 auto}.top-copy b{font-size:16px}.top-copy small{max-width:46vw;font-size:12px}.top-actions{gap:0}.top-actions #toggleMap,.top-actions #askBtn,.top-actions #feedbackBtn{display:none}.top-actions .icon-btn{padding:8px 10px;border-radius:10px;font-size:14px}.top-actions .icon-btn[href]{white-space:nowrap}
.progress-wrap{margin-top:7px}.progress-wrap span{min-width:40px}.layout{display:block;margin-top:10px;padding:0 10px;margin-bottom:92px}.rail{position:fixed;inset:74px 10px 86px;z-index:50;max-height:none;margin:0;display:none;box-shadow:0 18px 55px rgba(20,39,76,.20)}.rail.open{display:block}.relation{display:none}.form-grid{grid-template-columns:1fr}.full{grid-column:auto}.metric-grid{grid-template-columns:1fr 1fr}.mode-grid,.map-grid{grid-template-columns:1fr}.card{padding:14px;border-radius:16px}h1{font-size:22px}.page-head h2{font-size:20px}
.bottom{left:10px;right:10px;bottom:max(8px,env(safe-area-inset-bottom));display:grid;grid-template-columns:minmax(0,1fr) auto minmax(0,1.25fr);gap:7px;padding:7px;overflow:visible}.bottom .btn{min-width:0;white-space:nowrap;padding:11px 10px}.bottom .spacer,.bottom #skipBtn,.bottom #relationBtn,.bottom #resetStepBtn{display:none}.bottom #prevBtn{grid-column:1}.bottom #moreBtn{display:block;grid-column:2}.bottom #nextBtn{grid-column:3;width:100%}
.drawer-panel{width:92vw;padding:16px}.stage[aria-busy="true"]{opacity:.72;pointer-events:none}
}
</style>
</head>
<body>
<header class="top">
  <div class="top-row">
    <div class="brand">长</div>
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
  <aside class="rail" id="rail"><div class="rail-head"><h3>训练地图</h3><button class="btn" id="closeRail">关闭</button></div><div id="steps"></div><div style="margin-top:12px"><label class="small muted">快速场景</label><select id="scenario" style="width:100%;margin-top:5px;padding:9px;border:1px solid #d4deec;border-radius:10px"><option value="empty">从零开始</option><option value="assigned">从已布置作业开始</option><option value="submitted">从已有学生提交开始</option><option value="classroom">从课堂复盘开始</option></select><button class="btn soft" id="loadScenario" style="width:100%;margin-top:7px">载入场景</button><button class="btn danger" id="cleanupDemoData" style="width:100%;margin-top:7px">正式使用前 · 清空演示数据</button><div class="small muted" style="margin-top:6px">只清除当前账号的临时实操沙盒，不会删除真实班级、学生、作业、积分或学习证据。</div></div></aside>
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
function auxiliaryPage(step,roleLabel,details=''){
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
    points:()=>pageIntro(step,'积分不是学习成绩。必须能看到来源，并区分自动积分与教师课堂评价。')+pageCard('积分与课堂评价','查看刚才提交产生的练习积分。',listItems(d.points,x=>'<div class="item"><b>+'+esc(x.points)+' 学习积分</b><small>来源：'+esc(x.source)+'</small></div>'),'<button class="btn primary" id="pointsDone">确认积分来源</button>'),
    history:()=>pageIntro(step,'教学结束后进入只读历史，但学生连续档案继续保留。')+pageCard('往期教学','结束班级不是删除学生。',listItems(d.history,x=>'<div class="item"><b>'+esc(x.className)+'</b><small>状态：只读历史</small></div>'),'<button class="btn primary" id="archiveHistory">把练习班级放入历史</button>'),
    transition:()=>{const s=d.students?.at(-1);return pageIntro(step,'升年级改变阶段，不重新创建学生。')+pageCard('升年级与升学衔接',s?esc(s.name)+' · 同一学生档案':'暂无学生','<div class="form-grid"><div class="field"><label>上一阶段</label><input id="transitionFrom" value="五年级"></div><div class="field"><label>下一阶段</label><input id="transitionTo" value="六年级"></div></div>'+listItems(d.transitions,x=>'<div class="item"><b>'+esc(x.from)+' → '+esc(x.to)+'</b><small>同一学生档案 #'+esc(x.studentID)+'</small></div>'),'<button class="btn primary" id="createTransition">建立练习衔接计划</button>')},
    hub:()=>pageIntro(step,'最后从功能关系图回看整条链，理解每个页面的上游、下游和角色交接。')+pageCard('全部功能关系图','不是菜单清单，而是业务链。','<div class="map-grid">'+session.flow.map((x,i)=>'<div class="map-node"><b>'+(i+1)+'. '+esc(x.title)+'</b><small>'+esc(x.page)+'<br>'+esc(session.relationships?.[x.id]?.next||'继续当前角色主线')+'</small></div>').join('')+'</div>','<button class="btn primary" id="finishTraining">完成本轮实操训练</button>')
  };
  stage.innerHTML=(views[step.id]||(()=>auxiliaryPage(step,'教师',teacherAuxDetail(step.id))))();bindTeacher(step);
}
function teacherAuxDetail(id){
  return ({
    teacher_resources:'这里管理教材、教案和课件。私有备课资料与学生可见资料必须区分。',
    teacher_catalog:'这里浏览教材题库并为组卷/AI出题提供上游资源；浏览题库不等于给学生布置任务。导入或拍照上传的题目也在这里：按学科、教材和单元查找，单元就是导入时填写的单元；题库里已有完全相同的题（带插图的题除外）会直接沿用、不重复保存，仍在它原来的单元下；勾选题目后可批量修改单元或教材（老师只能改自己导入或创建的题目，管理员可改本校所有题目）。',
    teacher_audit:'这里回看教师自己的操作记录，帮助确认谁在什么时间做了什么。',
    teacher_leaderboard:'这里查看班级激励排行；它用于激励，不替代学情诊断。',
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
    stage.innerHTML=pageIntro(step,'找到教师刚布置的任务，确认名称、截止时间和提交状态。')+pageCard('我的作业','待完成 / 已完成状态来自教师布置和你的提交。',listItems(d.assignments,x=>'<div class="item"><b>'+esc(x.title)+'</b><small>截止 '+esc(x.due)+' · '+(sub?'已完成':'待完成')+'</small></div>')+roleRelationBlock(rel),done);
  }else if(step.id==='answer'){
    stage.innerHTML=pageIntro(step,'像正式学生一样逐题选择答案，再正式提交。')+pageCard('逐题作答',a?esc(a.title):'暂无作业',sub?'<div class="notice ok">这份练习已经提交。可继续查看结果，或重置沙盒后再练。</div>':(p?questionPager(p,'studentSelfOption','studentSelfInput'):'<div class="notice">暂无题目。</div>'),sub?done:'<button class="btn primary" id="studentSelfSubmit">正式提交</button>');
  }else if(step.id==='result'){
    stage.innerHTML=pageIntro(step,'提交后才形成结果。一次分数只是一次证据，不代表长期掌握结论。')+pageCard('提交结果',sub?esc(sub.studentName):'尚未提交',sub?'<div class="metric-grid"><div class="metric"><strong>'+sub.score+'%</strong><small>得分</small></div><div class="metric"><strong>'+sub.correct+'/'+sub.total+'</strong><small>答对</small></div><div class="metric"><strong>'+sub.wrongCount+'</strong><small>错题</small></div><div class="metric"><strong>'+esc(sub.knowledge)+'</strong><small>知识点</small></div></div>'+roleRelationBlock(rel):'<div class="notice warn">请先完成上一页的正式提交。</div>',done);
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
    admin_ai:'这里设置 AI 服务和学生数据授权边界。密钥只属于管理员；教师仍保留审核发布权。',
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
    return _TRAINING_HTML


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
