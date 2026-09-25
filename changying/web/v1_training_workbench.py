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
.layout{max-width:1120px;margin:14px auto 96px;padding:0 14px;display:grid;grid-template-columns:240px minmax(0,1fr);gap:14px}.rail{background:#fff;border:1px solid var(--line);border-radius:18px;padding:12px;align-self:start;position:sticky;top:86px;max-height:calc(100dvh - 110px);overflow:auto}.rail h3{margin:4px 3px 9px}.step{width:100%;border:0;background:transparent;display:grid;grid-template-columns:28px 1fr auto;gap:8px;align-items:center;text-align:left;padding:8px;border-radius:11px;color:var(--ink)}.step.active{background:#eaf1ff}.step.done{background:#eef9f0}.step.skipped{background:#fff7e8}.step-no{width:27px;height:27px;border:1px solid #d7e0ed;border-radius:9px;background:#fff;display:grid;place-items:center;font-size:12px;font-weight:900}.step small{color:var(--muted)}.stage{min-width:0}.card{background:#fff;border:1px solid var(--line);border-radius:18px;padding:18px}.hero{background:linear-gradient(145deg,#eef4ff,#fff)}h1{font-size:25px;margin:5px 0 8px}h2{font-size:19px;margin:0 0 8px}p{line-height:1.65}.relation{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:9px;margin-top:12px}.relation>div{border:1px solid var(--line);background:#fafcff;border-radius:13px;padding:11px}.relation b{display:block;font-size:11px;color:var(--navy);margin-bottom:4px}.relation span{font-size:12px;line-height:1.5;color:#4d5a70}.page-card{margin-top:12px}.page-head{display:flex;justify-content:space-between;align-items:flex-start;gap:10px;padding-bottom:13px;border-bottom:1px solid var(--line)}.page-head h2{font-size:22px;margin:0}.page-head p{margin:4px 0 0;color:var(--muted);font-size:13px}.form-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;margin-top:14px}.field{display:grid;gap:5px}.field label{font-size:12px;color:#475467;font-weight:700}.field input,.field select,.field textarea{width:100%;border:1px solid #cad6e5;border-radius:11px;background:white;padding:11px 12px;color:var(--ink)}.field textarea{min-height:90px}.full{grid-column:1/-1}.action-row{display:flex;flex-wrap:wrap;gap:8px;margin-top:14px}.notice{padding:11px 12px;border-radius:12px;background:#f7f9fc;border:1px solid var(--line);font-size:13px;line-height:1.6}.notice.ok{background:#eef9f0;border-color:#cce9d2;color:#245f33}.notice.warn{background:#fff8e8;border-color:#efd59c;color:#754d00}.list{display:grid;gap:9px;margin-top:12px}.item{border:1px solid var(--line);border-radius:13px;padding:12px;background:#fff}.item b{display:block}.item small{display:block;color:var(--muted);margin-top:4px;line-height:1.5}.question{border:1px solid var(--line);border-radius:14px;padding:13px;margin-top:10px}.options{display:grid;gap:7px;margin-top:9px}.option{border:1px solid #d3ddea;background:#fff;border-radius:10px;padding:10px;text-align:left}.option.selected{border-color:#7da2e8;background:#edf3ff}.metric-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:9px;margin-top:12px}.metric{border:1px solid var(--line);border-radius:13px;padding:12px;background:#fafcff}.metric strong{font-size:24px;display:block}.metric small{color:var(--muted)}.mode-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:12px}.mode{border:1px solid #d4deec;border-radius:15px;background:#fff;padding:14px;text-align:left}.mode b{display:block;margin-bottom:6px}.mode small{color:var(--muted);line-height:1.55}.map-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.map-node{border:1px solid var(--line);border-radius:14px;padding:13px;background:#fff}.map-node b{display:block}.map-node small{color:var(--muted);line-height:1.5;display:block;margin-top:4px}
.bottom{position:fixed;left:10px;right:10px;bottom:max(8px,env(safe-area-inset-bottom));z-index:35;background:rgba(255,255,255,.98);border:1px solid var(--line);border-radius:17px;padding:8px;display:flex;gap:7px;justify-content:center;box-shadow:0 16px 48px rgba(20,39,76,.18);backdrop-filter:blur(14px)}.bottom .btn{padding:9px 11px}.spacer{flex:1}
.drawer{position:fixed;inset:0;z-index:60;background:rgba(12,25,47,.46);display:flex;justify-content:flex-end}.drawer-panel{width:min(440px,92vw);height:100%;background:#fff;padding:18px;overflow:auto;box-shadow:-14px 0 50px rgba(12,25,47,.22)}.drawer-head{display:flex;justify-content:space-between;gap:10px;align-items:center}.assistant-log{display:grid;gap:8px;margin:12px 0}.assistant-msg{border:1px solid var(--line);border-radius:12px;padding:10px 11px;line-height:1.6;font-size:13px}.assistant-msg.ai{background:#f5f8fd}
@media(max-width:760px){.top{padding:9px 10px}.top-actions .label{display:none}.layout{display:block;margin-top:10px;padding:0 10px;margin-bottom:88px}.rail{position:static;max-height:none;margin-bottom:10px;display:none}.rail.open{display:block}.relation{grid-template-columns:1fr}.form-grid{grid-template-columns:1fr}.full{grid-column:auto}.metric-grid{grid-template-columns:1fr 1fr}.mode-grid,.map-grid{grid-template-columns:1fr}.card{padding:14px;border-radius:16px}h1{font-size:23px}.page-head h2{font-size:20px}.bottom{overflow-x:auto;justify-content:flex-start}.bottom .btn{white-space:nowrap}.top-copy small{max-width:220px}}
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
      <a class="icon-btn" href="/v1/workspace">退出</a>
    </div>
  </div>
  <div class="progress-wrap"><div class="progress"><i id="progressBar"></i></div><span id="progressText">0/0</span></div>
</header>
<main class="layout">
  <aside class="rail" id="rail"><h3>训练地图</h3><div id="steps"></div><div style="margin-top:12px"><label class="small muted">快速场景</label><select id="scenario" style="width:100%;margin-top:5px;padding:9px;border:1px solid #d4deec;border-radius:10px"><option value="empty">从零开始</option><option value="assigned">从已布置作业开始</option><option value="submitted">从已有学生提交开始</option><option value="classroom">从课堂复盘开始</option></select><button class="btn soft" id="loadScenario" style="width:100%;margin-top:7px">载入场景</button></div></aside>
  <section class="stage" id="stage"><div class="card">正在启动实操沙盒…</div></section>
</main>
<nav class="bottom">
  <button class="btn" id="prevBtn">← 上一步</button>
  <button class="btn" id="skipBtn">跳过</button>
  <button class="btn" id="relationBtn">角色关系</button>
  <span class="spacer"></span>
  <button class="btn" id="resetStepBtn">重做本步</button>
  <button class="btn primary" id="nextBtn">下一步 →</button>
</nav>
<div class="drawer hidden" id="drawer"><section class="drawer-panel"><div class="drawer-head"><h2 id="drawerTitle">角色关系</h2><button class="btn" id="drawerClose">关闭</button></div><div id="drawerBody"></div></section></div>
<script>
(()=>{
const TOKEN_KEY='v717Token',SESSION_KEY='cyTrainingSandboxSessionV1',INDEX_KEY='cyTrainingStepIndexV1';
const token=()=>{const remember=localStorage.getItem('v717Remember')==='1';return (remember?localStorage.getItem(TOKEN_KEY):sessionStorage.getItem(TOKEN_KEY))||sessionStorage.getItem(TOKEN_KEY)||localStorage.getItem(TOKEN_KEY)||sessionStorage.getItem('v6Token')||localStorage.getItem('v6Token')||''};
const esc=v=>String(v??'').replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
const stage=document.getElementById('stage'),rail=document.getElementById('rail'),stepsEl=document.getElementById('steps'),progressBar=document.getElementById('progressBar'),progressText=document.getElementById('progressText'),topTitle=document.getElementById('topTitle'),topMeta=document.getElementById('topMeta');
const drawer=document.getElementById('drawer'),drawerTitle=document.getElementById('drawerTitle'),drawerBody=document.getElementById('drawerBody');
let session=null,index=Math.max(0,Number(sessionStorage.getItem(INDEX_KEY)||0)),answers={};

async function request(path,opt={}){
  const t=token();if(!t){location.href='/v1';throw new Error('请先登录')}
  const headers={'Content-Type':'application/json',...(opt.headers||{}),Authorization:'Bearer '+t};
  const r=await fetch(path,{...opt,headers,cache:'no-store'});let d={};try{d=await r.json()}catch{}
  if(!r.ok)throw new Error(d.detail||('请求失败 '+r.status));return d
}
async function act(action,payload={}){session=await request('/v1/training-sandbox/'+session.sessionID+'/action',{method:'POST',body:JSON.stringify({action,payload})});render();return session}
async function start(){
  try{
    const id=sessionStorage.getItem(SESSION_KEY);
    if(id){try{session=await request('/v1/training-sandbox/'+id)}catch{sessionStorage.removeItem(SESSION_KEY)}}
    if(!session){session=await request('/v1/training-sandbox/start',{method:'POST',body:JSON.stringify({linked_mode:'choose'})});sessionStorage.setItem(SESSION_KEY,session.sessionID)}
    index=Math.min(index,Math.max(0,session.flow.length-1));render();
  }catch(e){stage.innerHTML='<div class="card"><h2>无法启动实操沙盒</h2><p>'+esc(e.message)+'</p><a class="btn primary" href="/v1">返回登录</a></div>'}
}
function current(){return session?.flow?.[index]||null}
function setIndex(i){index=Math.max(0,Math.min(session.flow.length-1,i));sessionStorage.setItem(INDEX_KEY,String(index));answers={};render()}
function relation(step=current()){return session?.relationships?.[step?.id]||{}}
function statusClass(id){const s=session.progress?.[id];return s==='done'?'done':s==='skipped'?'skipped':''}
function pageIntro(step,subtitle=''){
  const rel=relation(step);
  return '<div class="card hero"><span class="tag">第 '+(index+1)+' / '+session.flow.length+' 关</span><h1>'+esc(step.title)+'</h1><p>'+esc(subtitle||'请像正式使用一样完成本页操作。所有业务数据只存在于临时实操沙盒。')+'</p><div class="relation"><div><b>这一步由谁操作</b><span>'+esc(rel.who||session.primaryRole)+'</span></div><div><b>操作会产生什么</b><span>'+esc(rel.creates||'训练进度')+'</span></div><div><b>其他角色会看到什么</b><span>'+esc(rel.other_role_sees||rel.visible_to||'按权限显示')+'</span></div></div></div>';
}
function pageCard(title,subtitle,body,actions=''){
  return '<section class="card page-card"><div class="page-head"><div><h2>'+esc(title)+'</h2><p>'+esc(subtitle)+'</p></div><span class="tag warn">实操沙盒</span></div>'+body+(actions?'<div class="action-row">'+actions+'</div>':'')+'</section>';
}
function listItems(items,formatter){return '<div class="list">'+(items?.length?items.map(formatter).join(''):'<div class="notice">当前还没有数据，请先完成上一环节。</div>')+'</div>'}
function markStep(status='done'){return act('visit_step',{step:current().id,status})}
function render(){
  if(!session)return;const step=current(),doneCount=Object.values(session.progress||{}).filter(x=>x==='done'||x==='skipped').length;
  topTitle.textContent='实操沙盒 · '+step.title;
  topMeta.textContent='主身份：'+roleName(session.primaryRole)+' · 当前体验：'+roleName(session.currentRole)+(session.currentRole!==session.primaryRole?' · 完成后可一键返回主身份':'');
  progressBar.style.width=Math.round(((index+1)/Math.max(1,session.flow.length))*100)+'%';progressText.textContent=(index+1)+'/'+session.flow.length;
  stepsEl.innerHTML=session.flow.map((s,i)=>'<button class="step '+(i===index?'active ':'')+statusClass(s.id)+'" data-i="'+i+'"><span class="step-no">'+(i+1)+'</span><span><b>'+esc(s.title)+'</b><small>'+esc(s.page)+'</small></span><span>'+({done:'✓',skipped:'↷'}[session.progress?.[s.id]]||'')+'</span></button>').join('');
  stepsEl.querySelectorAll('.step').forEach(b=>b.onclick=()=>setIndex(Number(b.dataset.i)));
  document.getElementById('prevBtn').disabled=index===0;document.getElementById('nextBtn').disabled=index===session.flow.length-1;
  renderStep(step);
}
function roleName(r){return({teacher:'教师',student:'学生',parent:'家长',admin:'管理员'}[r]||r||'当前身份')}
function renderStep(step){
  const d=session.data||{};
  if(session.primaryRole!=='teacher'){renderNonTeacher(step);return}
  const views={
    purpose:()=>pageIntro(step,'先理解长缨不是单一出题工具，而是把教学动作和长期学生档案连成一个闭环。')+pageCard('教师工作全景','从今天的教学动作，持续回流到同一个学生档案。','<div class="map-grid"><div class="map-node"><b>当前教学</b><small>班级、作业、课堂：今天要做什么。</small></div><div class="map-node"><b>学生连续档案</b><small>成绩、错题、知识点、积分和历史：长期发生了什么。</small></div><div class="map-node"><b>AI / 针对练习</b><small>基于证据形成下一步教学草稿，教师负责审核。</small></div><div class="map-node"><b>课堂与历史</b><small>复盘、互动、阶段变化继续引用同一学生。</small></div></div>','<button class="btn primary" id="understand">我理解教师主线</button>'),
    create_class:()=>pageIntro(step,'真正创建一个临时练习班级。它不会进入正式班级统计。')+pageCard('班级学生','先建立当前教学容器。','<div class="form-grid"><div class="field"><label>班级名称</label><input id="className" value="五年级实操班"></div><div class="field"><label>年级</label><select id="classGrade">'+[1,2,3,4,5,6].map(x=>'<option '+(x===5?'selected':'')+' value="'+x+'">'+x+'年级</option>').join('')+'</select></div></div>'+listItems(d.classes,x=>'<div class="item"><b>'+esc(x.name)+'</b><small>'+esc(x.grade)+'年级 · 沙盒教师</small></div>'),'<button class="btn primary" id="createClass">＋新建班级</button>'),
    add_student:()=>{const cls=d.classes?.at(-1);return pageIntro(step,'创建一个与练习班级关联的虚拟学生账号，后续可以亲自切到这个学生视角。')+pageCard('创建学生账号',cls?'当前班级：'+cls.name:'请先建立班级','<div class="form-grid"><div class="field"><label>学生姓名</label><input id="studentName" value="小禾"></div><div class="field"><label>学生账号</label><input id="studentUser" value="xiaohe01"></div></div>'+listItems(d.students,x=>'<div class="item"><b>'+esc(x.name)+'</b><small>'+esc(x.username)+' · '+esc(x.className)+'</small></div>'),'<button class="btn primary" id="addStudent">创建学生账号</button>')},
    student_profile:()=>{const s=d.students?.at(-1);const sub=d.submissions?.at(-1);return pageIntro(step,'学生档案是长期主线；后面的作业和课堂结果都会回到这里。')+pageCard('学生连续档案',s?esc(s.name)+' · '+esc(s.className):'暂无学生',s?'<div class="metric-grid"><div class="metric"><strong>'+esc(sub?.score??'—')+'</strong><small>最近得分</small></div><div class="metric"><strong>'+esc(sub?.wrongCount??0)+'</strong><small>错题</small></div><div class="metric"><strong>'+esc(d.points?.reduce((n,x)=>n+Number(x.points||0),0)||0)+'</strong><small>积分</small></div><div class="metric"><strong>'+esc(d.history?.length||0)+'</strong><small>历史阶段</small></div></div><div class="notice" style="margin-top:12px">现在数据较少是正常的。完成一次作业后再回来，档案会发生变化。</div>':'<div class="notice">请先添加学生。</div>','<button class="btn primary" id="profileDone">我已了解连续档案</button>')},
    paper:()=>pageIntro(step,'像正式教师一样设置科目、教材、知识点和题量，并生成可审核的沙盒试卷。')+pageCard('组卷 / 自动出题','生成后会看到实际题目列表，不是截图说明。','<div class="form-grid"><div class="field"><label>科目</label><select id="paperSubject"><option>数学</option><option>语文</option><option>英语</option></select></div><div class="field"><label>教材</label><input id="paperTextbook" value="人教版"></div><div class="field"><label>知识点</label><input id="paperKnowledge" value="小数乘法"></div><div class="field"><label>题量</label><select id="paperCount"><option>5</option><option selected>8</option><option>10</option><option>15</option></select></div></div>'+listItems(d.papers,x=>'<div class="item"><b>'+esc(x.title)+'</b><small>'+esc(x.subject)+' · '+esc(x.textbook)+' · '+x.questions.length+'题 · '+esc(x.knowledge)+'</small></div>'),'<button class="btn primary" id="createPaper">生成练习试卷</button>'),
    review:()=>{const p=d.papers?.at(-1);return pageIntro(step,'教师审核是关键人机边界。检查题型、答案方式、难度和积分后再进入布置。')+pageCard('教师审核',p?esc(p.title):'暂无试卷',p?'<div class="list">'+p.questions.map(q=>'<div class="question"><b>'+q.index+'. '+esc(q.prompt)+'</b><small class="muted">'+esc(q.type)+' · '+esc(q.knowledge)+'</small><div class="options">'+(q.options||[]).map((o,i)=>'<button class="option" disabled>'+String.fromCharCode(65+i)+'. '+esc(o)+'</button>').join('')+'</div></div>').join('')+'</div>':'<div class="notice">请先生成试卷。</div>','<button class="btn primary" id="reviewPaper">确认题型、答案方式、难度与积分</button>')},
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
  stage.innerHTML=(views[step.id]||views.purpose)();bindTeacher(step);
}
function renderStudentSubmission(step){
  const d=session.data||{},a=d.assignments?.at(-1),p=d.papers?.at(-1),s=d.students?.at(-1),sub=d.submissions?.at(-1);
  if(sub)return pageIntro(step,'这份练习已提交，可以继续查看证据；如需重做可重置沙盒。')+pageCard('学生作答已完成',esc(sub.studentName),'<div class="metric-grid"><div class="metric"><strong>'+sub.score+'%</strong><small>得分</small></div><div class="metric"><strong>'+sub.correct+'/'+sub.total+'</strong><small>答对</small></div></div>','<button class="btn primary" id="submissionDone">继续查看教师端结果</button>');
  if(session.currentRole==='student'&&a&&p&&s){
    return pageIntro(step,'你现在正在临时体验关联虚拟学生。主身份仍是教师，不需要重新登录。')+pageCard('我的作业 · '+esc(a.title),esc(s.name)+' · '+esc(a.due),'<div id="studentQuestions">'+p.questions.map(q=>'<div class="question" data-q="'+q.id+'"><b>'+q.index+'. '+esc(q.prompt)+'</b><small class="muted">'+esc(q.type)+' · '+esc(q.knowledge)+'</small><div class="options">'+(q.options||[]).map((o,i)=>'<button class="option answerOption" data-q="'+q.id+'" data-i="'+i+'">'+String.fromCharCode(65+i)+'. '+esc(o)+'</button>').join('')+'</div></div>').join('')+'</div>','<button class="btn" id="returnTeacher">返回教师视角</button><button class="btn primary" id="studentSubmit">提交这份练习</button>');
  }
  return pageIntro(step,'这里由你选择：亲自切到关联虚拟学生完成作答，或者保持教师身份由沙盒自动模拟一次学生提交。')+pageCard('关联角色体验方式',a?esc(a.title):'请先布置作业','<div class="mode-grid"><button class="mode" id="switchStudent"><b>亲自体验学生端</b><small>临时切换到小禾，不重新登录；真正逐题选择答案并提交，然后返回教师身份。</small></button><button class="mode" id="simulateStudent"><b>自动模拟关联数据</b><small>保持教师身份，由沙盒生成一次合理的学生提交，直接继续教师端结果回流。</small></button></div>','');
}
function renderNonTeacher(step){
  const rel=relation(step);
  stage.innerHTML=pageIntro(step,'当前阶段先提供完整页面关系和角色任务训练；教师闭环完成后将继续把本身份所有操作接入同一沙盒。')+pageCard(step.title,'页面：'+step.page,'<div class="notice">当前身份：'+roleName(session.primaryRole)+'。本步重点理解自己的操作权限、上游来源与下游去向。</div><div class="relation"><div><b>可见范围</b><span>'+esc(rel.visible_to||'按角色权限')+'</span></div><div><b>沟通提示</b><span>'+esc(rel.communication_tip||'确认任务名称、状态和下一步责任人')+'</span></div><div><b>下一步</b><span>'+esc(rel.next||'继续角色主线')+'</span></div></div>','<button class="btn primary" id="genericDone">完成本页学习</button>');
  document.getElementById('genericDone').onclick=()=>markStep();
}
function bindTeacher(step){
  const $=id=>document.getElementById(id);
  if($('understand'))$('understand').onclick=()=>markStep();
  if($('createClass'))$('createClass').onclick=()=>act('create_class',{name:$('className').value,grade:+$('classGrade').value});
  if($('addStudent'))$('addStudent').onclick=()=>act('add_student',{name:$('studentName').value,username:$('studentUser').value});
  if($('profileDone'))$('profileDone').onclick=()=>markStep();
  if($('createPaper'))$('createPaper').onclick=()=>act('create_paper',{subject:$('paperSubject').value,textbook:$('paperTextbook').value,knowledge:$('paperKnowledge').value,questionCount:+$('paperCount').value});
  if($('reviewPaper'))$('reviewPaper').onclick=()=>act('review_paper',{});
  if($('assignWork'))$('assignWork').onclick=()=>act('assign',{title:$('assignTitle').value,due:$('assignDue').value});
  if($('switchStudent'))$('switchStudent').onclick=()=>act('switch_to_student',{});
  if($('simulateStudent'))$('simulateStudent').onclick=()=>act('simulate_student_submission',{});
  if($('returnTeacher'))$('returnTeacher').onclick=()=>act('return_primary_role',{});
  document.querySelectorAll('.answerOption').forEach(b=>b.onclick=()=>{answers[b.dataset.q]=+b.dataset.i;document.querySelectorAll('.answerOption[data-q="'+b.dataset.q+'"]').forEach(x=>x.classList.toggle('selected',x===b))});
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
async function askAssistant(){
 openDrawer('产品助手','<div class="assistant-log" id="assistantLog"><div class="assistant-msg ai">可以问：这个页面有什么用？其他角色会看到什么？我下一步应该做什么？</div></div><div class="field"><label>问题</label><textarea id="assistantQuestion" placeholder="例如：学生提交以后，教师和家长分别能看到什么？"></textarea></div><button class="btn primary" id="assistantSend" style="margin-top:9px">发送</button>');
 document.getElementById('assistantSend').onclick=async()=>{const q=document.getElementById('assistantQuestion').value.trim();if(!q)return;const log=document.getElementById('assistantLog');log.insertAdjacentHTML('beforeend','<div class="assistant-msg">'+esc(q)+'</div>');try{const d=await request('/v1/product-assistant/query',{method:'POST',body:JSON.stringify({question:q,page:current().page,identity:roleName(session.currentRole),tutorial_step:current().title})});log.insertAdjacentHTML('beforeend','<div class="assistant-msg ai">'+esc(d.reply)+'</div>')}catch(e){log.insertAdjacentHTML('beforeend','<div class="assistant-msg ai">'+esc(e.message)+'</div>')}}
}
document.getElementById('prevBtn').onclick=()=>setIndex(index-1);
document.getElementById('nextBtn').onclick=()=>setIndex(index+1);
document.getElementById('skipBtn').onclick=async()=>{await markStep('skipped');if(index<session.flow.length-1)setIndex(index+1)};
document.getElementById('resetStepBtn').onclick=async()=>{answers={};await act('rewind_step',{step:current().id})};
document.getElementById('relationBtn').onclick=showRelation;
document.getElementById('drawerClose').onclick=()=>drawer.classList.add('hidden');
drawer.onclick=e=>{if(e.target===drawer)drawer.classList.add('hidden')};
document.getElementById('toggleMap').onclick=()=>rail.classList.toggle('open');
document.getElementById('askBtn').onclick=askAssistant;
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
