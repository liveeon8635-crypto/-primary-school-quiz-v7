"""Productized landing shell for 长缨辅学.

The shell keeps the complete legacy monolith available at /classic while
turning visible entry points into a modern teacher workbench. It is deliberately
data-safe: it reads existing browser auth state and existing API endpoints, but
it does not mutate production data.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

PRODUCT_SHELL_MARKER = "changying_product_shell_v1_3"


def teacher_workbench_html() -> str:
    """Return the productized 长缨辅学 workbench page."""
    return """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
  <meta name="theme-color" content="#1e2fbf">
  <link rel="manifest" href="/manifest.webmanifest">
  <title>长缨辅学｜实践工作台 V1.3</title>
  <style>
    :root{--brand:#1e2fbf;--brand2:#10a874;--gold:#f4b740;--ink:#142033;--muted:#66728a;--line:#e6eaf3;--surface:#fff;--soft:#f6f8ff;--deep:#111a3a;--shadow:0 20px 55px rgba(21,33,70,.12);--radius:24px}
    *{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;min-height:100dvh;color:var(--ink);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;background:radial-gradient(circle at top left,rgba(30,47,191,.18),transparent 34rem),radial-gradient(circle at top right,rgba(16,168,116,.14),transparent 31rem),linear-gradient(180deg,#f7f9ff 0%,#eef3ff 45%,#f7f8fb 100%);-webkit-text-size-adjust:100%}a{color:inherit;text-decoration:none}button{font:inherit}.page{width:min(1180px,100%);margin:0 auto;padding:24px clamp(16px,3vw,34px) 42px}.topbar{display:flex;align-items:center;justify-content:space-between;gap:16px;margin-bottom:18px}.brand{display:flex;align-items:center;gap:12px}.logo{width:52px;height:52px;border-radius:18px;background:linear-gradient(145deg,var(--deep),var(--brand));box-shadow:var(--shadow);display:grid;place-items:center;color:#fff;font-size:24px;font-weight:950}.brand h1{font-size:23px;line-height:1.1;margin:0}.brand small{display:block;color:var(--muted);margin-top:4px}.actions{display:flex;align-items:center;gap:10px;flex-wrap:wrap}.pill{display:inline-flex;align-items:center;gap:7px;border:1px solid rgba(30,47,191,.14);background:rgba(255,255,255,.82);backdrop-filter:blur(10px);border-radius:999px;padding:10px 14px;color:var(--muted);font-size:13px}.btn{display:inline-flex;align-items:center;justify-content:center;gap:8px;border-radius:15px;padding:12px 16px;font-weight:850;background:#fff;border:1px solid var(--line);transition:.18s ease;cursor:pointer}.btn:hover{transform:translateY(-1px);box-shadow:0 12px 30px rgba(25,40,90,.12)}.btn.primary{background:var(--brand);border-color:var(--brand);color:#fff}.btn.green{background:var(--brand2);border-color:var(--brand2);color:#fff}.btn.dark{background:var(--deep);border-color:var(--deep);color:#fff}.btn.ghost{background:rgba(255,255,255,.62)}
    .hero{display:grid;grid-template-columns:1.18fr .82fr;gap:18px;align-items:stretch;margin:18px 0}.panel,.card{background:rgba(255,255,255,.9);border:1px solid rgba(229,234,246,.95);border-radius:var(--radius);box-shadow:var(--shadow);backdrop-filter:blur(14px)}.welcome{padding:30px;position:relative;overflow:hidden}.welcome:after{content:"";position:absolute;inset:auto -90px -110px auto;width:280px;height:280px;border-radius:50%;background:linear-gradient(135deg,rgba(30,47,191,.18),rgba(16,168,116,.18))}.eyebrow{display:inline-flex;gap:8px;align-items:center;font-size:13px;font-weight:900;color:var(--brand);background:#eef2ff;border:1px solid #dbe3ff;border-radius:999px;padding:8px 12px;margin-bottom:16px}.welcome h2{font-size:clamp(30px,5vw,54px);line-height:1.03;margin:0 0 12px;letter-spacing:-.04em}.welcome p{font-size:17px;color:var(--muted);line-height:1.8;margin:0;max-width:760px}.hero-actions{display:flex;gap:12px;flex-wrap:wrap;margin-top:24px;position:relative;z-index:1}.status{padding:22px;display:flex;flex-direction:column;gap:14px}.status h3,.section-title h3{margin:0;font-size:18px}.mini{display:flex;align-items:center;gap:12px;padding:14px;border-radius:18px;background:#f7f9ff;border:1px solid #e9edfb}.mini b{display:block;margin-bottom:3px}.mini span{font-size:13px;color:var(--muted);line-height:1.5}.dot{width:12px;height:12px;border-radius:50%;background:var(--brand);box-shadow:0 0 0 6px rgba(30,47,191,.12)}.dot.green{background:var(--brand2);box-shadow:0 0 0 6px rgba(16,168,116,.12)}.dot.orange{background:var(--gold);box-shadow:0 0 0 6px rgba(244,183,64,.16)}
    .grid{display:grid;gap:16px}.kpis{grid-template-columns:repeat(4,1fr);margin:18px 0}.card{padding:20px}.kpi .icon{width:42px;height:42px;border-radius:16px;display:grid;place-items:center;background:#eef2ff;color:var(--brand);font-size:22px;margin-bottom:16px}.kpi strong{font-size:32px;display:block;letter-spacing:-.04em}.kpi span{color:var(--muted);font-size:14px}.live{font-size:11px;color:var(--brand2);font-weight:900;margin-top:8px}.section{margin-top:20px}.section-title{display:flex;justify-content:space-between;align-items:end;gap:12px;margin:0 0 14px}.section-title p{margin:4px 0 0;color:var(--muted);font-size:14px}.quick{grid-template-columns:repeat(3,1fr)}.quick-card{display:flex;gap:16px;align-items:flex-start;min-height:132px;position:relative;overflow:hidden}.quick-card:after{content:"→";position:absolute;right:20px;bottom:16px;color:#b8c1d6;font-weight:900;font-size:22px}.quick-card .icon{flex:0 0 48px;width:48px;height:48px;border-radius:18px;display:grid;place-items:center;background:#f1f5ff;font-size:24px}.quick-card h4{margin:2px 0 8px;font-size:17px}.quick-card p{margin:0;color:var(--muted);line-height:1.65;font-size:14px}.work,.check{grid-template-columns:1.05fr .95fr}.list{display:grid;gap:10px}.list-item{display:flex;justify-content:space-between;gap:12px;align-items:center;padding:13px;border-radius:16px;background:var(--soft);border:1px solid #e8edfb}.list-item b{font-size:14px}.list-item span{font-size:13px;color:var(--muted);text-align:right}.path{grid-template-columns:repeat(4,1fr)}.path-step{position:relative;min-height:154px}.path-step em{font-style:normal;color:var(--brand);font-size:12px;font-weight:900;letter-spacing:.06em}.path-step h4{margin:8px 0 8px}.path-step p{margin:0;color:var(--muted);line-height:1.7;font-size:14px}.system{grid-template-columns:repeat(5,1fr)}.system .card{min-height:168px;background:#fff}.system em{font-style:normal;display:inline-grid;place-items:center;width:34px;height:34px;border-radius:13px;background:#eef2ff;color:var(--brand);font-weight:950}.system h4{margin:14px 0 8px}.system p{margin:0;color:var(--muted);line-height:1.65;font-size:14px}.bridge{grid-template-columns:repeat(3,1fr)}.bridge .card{min-height:172px}.bridge b{display:inline-block;margin-bottom:10px;color:var(--brand)}.bridge p{margin:0;color:var(--muted);line-height:1.7;font-size:14px}.check-grid{display:grid;gap:10px}.check-item{display:flex;gap:10px;align-items:flex-start;padding:12px;border-radius:16px;background:#f8faff;border:1px solid #edf1fb}.check-item i{font-style:normal}.check-item b{display:block;font-size:14px}.check-item span{display:block;margin-top:3px;color:var(--muted);font-size:13px;line-height:1.5}.brand-card{background:linear-gradient(145deg,#111a3a,#1e2fbf);color:#fff;position:relative;overflow:hidden}.brand-card p{color:rgba(255,255,255,.8);line-height:1.75}.brand-card:after{content:"实践";position:absolute;right:-18px;bottom:-24px;font-size:86px;font-weight:950;letter-spacing:-.08em;color:rgba(255,255,255,.08)}.footer{color:var(--muted);font-size:13px;text-align:center;margin-top:28px}.bottom-nav{display:none}
    @media(max-width:980px){.hero,.work,.check{grid-template-columns:1fr}.kpis,.path,.system,.bridge{grid-template-columns:repeat(2,1fr)}.quick{grid-template-columns:1fr 1fr}}@media(max-width:640px){.page{padding:18px 14px 96px}.topbar{align-items:flex-start;flex-direction:column}.pill.hide-mobile{display:none}.welcome{padding:24px 20px}.kpis,.quick,.path,.system,.bridge{grid-template-columns:1fr}.hero-actions .btn,.actions .btn{width:100%}.brand h1{font-size:20px}.bottom-nav{position:fixed;left:10px;right:10px;bottom:10px;z-index:99;display:grid;grid-template-columns:repeat(4,1fr);gap:8px;padding:8px;border-radius:20px;background:rgba(255,255,255,.92);box-shadow:0 18px 46px rgba(23,32,51,.18);border:1px solid var(--line);backdrop-filter:blur(12px)}.bottom-nav a{text-align:center;border-radius:15px;padding:10px 4px;background:#f7f9ff;font-size:12px;font-weight:900;color:var(--ink)}}
    [hidden]{display:none!important}.btn:disabled{cursor:wait;opacity:.6}
  </style>
</head>
<body>
  <main class="page">
    <header class="topbar"><div class="brand"><div class="logo">长</div><div><h1>长缨辅学</h1><small>实践工作台 · V1.3</small></div></div><div class="actions"><span class="pill hide-mobile" id="clock">今天</span><a class="btn ghost" href="/classic">完整系统</a><a class="btn primary" href="/classic">开始上课</a></div></header>
    <section class="hero"><div class="panel welcome"><div class="eyebrow">长缨辅学 V1.3 · 改造世界的核心实践体系</div><h2>把认识、训练、反馈和经营连成一条实践闭环。</h2><p id="heroText">新版工作台会自动读取现有登录状态；未登录时作为品牌入口，登录后显示真实学生、班级、题库、作业和教学数据概览。产品方向从“补课工具”升级为“能力发展实践系统”。</p><div class="hero-actions"><a class="btn primary" href="/classic">进入完整系统</a><a class="btn green" href="#system">查看实践体系</a><a class="btn dark" href="#market">AI 与市场化</a></div></div><aside class="panel status"><h3>当前状态</h3><div id="sessionFeedback" role="status" aria-live="polite"><a id="loginAction" class="btn primary" href="/classic" hidden>前往登录</a><button id="retryStatus" class="btn ghost" type="button" hidden>重试</button></div><div class="mini"><i class="dot" id="sessionDot"></i><div><b id="sessionTitle" role="status" aria-live="polite">正在检查登录状态</b><span id="sessionDetail">会读取旧版系统的 v717Token / v717Remember，不需要重新登录。</span></div></div><div class="mini"><i class="dot green"></i><div><b>完整功能已保留</b><span>旧版系统入口仍在 /classic，数据和业务流程不变。</span></div></div><div class="mini"><i class="dot orange"></i><div><b>只读上线策略</b><span>本页只读 /session、/admin/overview、/teacher/classes，不写入生产数据。</span></div></div></aside></section>
    <section class="grid kpis" id="live" aria-label="运营概览"><div class="card kpi"><div class="icon">👨‍🎓</div><strong id="kpi-students">—</strong><span>学生</span><div class="live" id="students-live">等待登录后读取</div></div><div class="card kpi"><div class="icon">🏫</div><strong id="kpi-classes">—</strong><span>班级 / 课程</span><div class="live" id="classes-live">教师或管理员可见</div></div><div class="card kpi"><div class="icon">📖</div><strong id="kpi-questions">—</strong><span>题库</span><div class="live" id="questions-live">管理员概览</div></div><div class="card kpi"><div class="icon">📝</div><strong id="kpi-assignments">—</strong><span>作业</span><div class="live" id="assignments-live">管理员概览</div></div></section>
    <section class="section" id="system"><div class="section-title"><div><h3>长缨实践体系</h3><p>把长期理论转成产品结构：经验、知识、能力、行动、反馈、重构。</p></div><a class="pill" href="/classic">进入执行系统 →</a></div><div class="grid system"><div class="card"><em>1</em><h4>经验采集</h4><p>学生表现、作业、错题、到课和课堂观察进入同一实践记录。</p></div><div class="card"><em>2</em><h4>知识结构</h4><p>按年级、教材、单元、知识点和关系组织题库与讲解。</p></div><div class="card"><em>3</em><h4>能力估计</h4><p>不只看分数，还看稳定性、迁移、独立完成度和支持程度。</p></div><div class="card"><em>4</em><h4>任务干预</h4><p>通过分层练习、自动组卷、作业和课堂支持改变下一次表现。</p></div><div class="card"><em>5</em><h4>反馈重构</h4><p>用成绩、错题、家长反馈和复测结果重构教学方案。</p></div></div></section>
    <section class="section" id="path"><div class="section-title"><div><h3>今日上课路径</h3><p>按照线下辅学真实动作重排：先确认对象，再组织训练，最后看反馈。</p></div></div><div class="grid path"><a class="card path-step" href="/classic"><em>STEP 01</em><h4>看今天学生</h4><p>确认学生、班级、到课和重点关注对象。</p></a><a class="card path-step" href="/classic"><em>STEP 02</em><h4>选题与组卷</h4><p>从题库、知识点和难度进入分层练习。</p></a><a class="card path-step" href="/classic"><em>STEP 03</em><h4>布置今日作业</h4><p>把课堂练习与课后任务连接起来。</p></a><a class="card path-step" href="/classic"><em>STEP 04</em><h4>看结果反馈</h4><p>用成绩、错题和积分决定下一次干预。</p></a></div></section>
    <section class="section" id="quick"><div class="section-title"><div><h3>高频功能入口</h3><p>老师常用功能集中展示，减少找菜单时间。</p></div></div><div class="grid quick"><a class="card quick-card" href="/classic"><div class="icon">👨‍🎓</div><div><h4>学生管理</h4><p>查看学生、家长、班级、学习状态与跟进记录。</p></div></a><a class="card quick-card" href="/classic"><div class="icon">🏫</div><div><h4>班级与课程</h4><p>管理晚托、周末课、寒暑假班与日常教学安排。</p></div></a><a class="card quick-card" href="/classic"><div class="icon">📖</div><div><h4>数学题库</h4><p>围绕人教版五年级、单元、知识点和难度组织题目。</p></div></a><a class="card quick-card" href="/classic"><div class="icon">📄</div><div><h4>自动组卷</h4><p>快速生成课后练习、单元测验与分层训练卷。</p></div></a><a class="card quick-card" href="/classic"><div class="icon">📝</div><div><h4>今日作业</h4><p>布置、查看提交、批改与回收学生完成情况。</p></div></a><a class="card quick-card" href="/classic"><div class="icon">📊</div><div><h4>成绩分析</h4><p>快速看到班级表现、错题集中区和需要重点关注的学生。</p></div></a></div></section>
    <section class="section grid work"><div class="card"><div class="section-title"><div><h3>我的班级</h3><p id="classHint">登录教师账号后，会展示当前负责班级。</p></div></div><div class="list" id="classList"><div class="list-item"><b>进入完整系统后查看</b><span>/classic</span></div></div></div><div class="card"><div class="section-title"><div><h3>今日工作流</h3><p>按照补习班一天的真实流程组织。</p></div></div><div class="list"><div class="list-item"><b>01 课前</b><span>看班级与学生</span></div><div class="list-item"><b>02 课中</b><span>题库与分层练习</span></div><div class="list-item"><b>03 课后</b><span>作业、成绩、错题</span></div></div></div></section>
    <section class="section" id="market"><div class="section-title"><div><h3>AI 对接与市场化价值</h3><p>先把接口位置和商业价值在 UI 中明确，后续再接真实 AI 服务和小程序。</p></div></div><div class="grid bridge"><div class="card"><b>AI 辅学入口</b><p>下一步对接 AI 讲题、错因分析、分层练习建议和家长反馈文案；先从只读学习数据开始，避免误改生产数据。</p></div><div class="card"><b>公众号获客</b><p>网站承担信任建立和预约转化：展示能力发展闭环、真实教学流程、试听课入口和家长可理解的学习报告。</p></div><div class="card"><b>会员服务</b><p>把晚托、周末课、寒暑假班打包成长期服务，而不是一次性卖课；用数据反馈提高续费和转介绍。</p></div></div></section>
    <section class="section grid check" id="checkup"><div class="card"><div class="section-title"><div><h3>运营体检</h3><p>把系统投入使用前最重要的检查项放在首页。</p></div></div><div class="check-grid"><div class="check-item"><i>✅</i><div><b>入口清晰</b><span>/workbench 看新版，/classic 用完整系统。</span></div></div><div class="check-item"><i>✅</i><div><b>业务保留</b><span>学生、题库、作业、成绩等功能继续走旧系统。</span></div></div><div class="check-item"><i>🔒</i><div><b>数据安全</b><span>新版工作台只读取数据，不直接修改数据库。</span></div></div><div class="check-item"><i>📱</i><div><b>移动端入口</b><span>手机底部增加工作台、体系、AI、完整系统快捷入口。</span></div></div></div></div><div class="card"><div class="section-title"><div><h3>首次使用建议</h3><p>明天可以按这个顺序试跑一节课。</p></div></div><div class="list"><div class="list-item"><b>先登录完整系统</b><span>确认账号可用</span></div><div class="list-item"><b>回到工作台</b><span>看概览是否读取</span></div><div class="list-item"><b>进入学生/题库/作业</b><span>按真实流程试用</span></div><div class="list-item"><b>记录卡点</b><span>下一轮继续优化</span></div></div></div></section>
    <section class="section card brand-card"><h3>长缨辅学，是一套实践系统。</h3><p>目标不是做一个普通教育网站，而是把线下教学、学生能力发展、AI 辅学、家校沟通、公众号获客和会员服务连成一个可持续迭代的实践体系。</p></section>
    <p class="footer">长缨辅学 V1.3 · 新版工作台只读现有接口，不改变生产数据 · 完整系统保留在 /classic</p>
  </main>
  <nav class="bottom-nav" aria-label="移动端快捷入口"><a href="/workbench">工作台</a><a href="#system">体系</a><a href="#market">AI</a><a href="/classic">系统</a></nav>
  <script>
    let headers={};
    let loading=false;
    const retryButton=document.getElementById('retryStatus');
    const loginAction=document.getElementById('loginAction');
    const setText=(id,text)=>{const el=document.getElementById(id);if(el)el.textContent=text;};
    const fmt=(n)=>Number.isFinite(Number(n))?String(n):'—';
    const clock=new Intl.DateTimeFormat('zh-CN',{weekday:'long',month:'long',day:'numeric'}).format(new Date());
    setText('clock',clock);
    async function getJSON(url){
      const controller=new AbortController();
      const timer=setTimeout(()=>controller.abort(),10000);
      try{
        const res=await fetch(url,{headers,cache:'no-store',signal:controller.signal});
        if(!res.ok){const error=new Error('Request failed');error.status=res.status;throw error;}
        return await res.json();
      }finally{clearTimeout(timer);}
    }
    function failureMessage(error){
      if(error.status===401)return '登录已过期，请重新登录';
      if(error.status===403)return '当前账号无权查看此内容';
      return '暂时无法读取，请重试';
    }
    function showFailure(error){
      if(error.status===401)loginAction.hidden=false;
      // A forbidden session can also require an account action in the full system.
      if(error.status===403){loginAction.hidden=false;loginAction.textContent='进入完整系统查看';}
      if(error.status!==401&&error.status!==403)retryButton.hidden=false;
    }
    function applyOverview(data){
      const students=data.students ?? data.studentCount ?? data.totalStudents ?? data.user_count ?? data.users;
      const classes=data.classes ?? data.classCount ?? data.totalClasses ?? data.courses;
      const questions=data.questions ?? data.questionCount ?? data.totalQuestions ?? data.items;
      const assignments=data.assignments ?? data.assignmentCount ?? data.homework ?? data.tasks;
      setText('kpi-students',fmt(students));setText('kpi-classes',fmt(classes));setText('kpi-questions',fmt(questions));setText('kpi-assignments',fmt(assignments));
      if(students!==undefined)setText('students-live','已读取管理员概览');
      if(classes!==undefined)setText('classes-live','已读取管理员概览');
      if(questions!==undefined)setText('questions-live','已读取管理员概览');
      if(assignments!==undefined)setText('assignments-live','已读取管理员概览');
    }
    function applyClasses(items){
      const list=Array.isArray(items)?items:(items.classes||items.data||items.items||[]);
      if(!Array.isArray(list))throw new Error('Invalid class list');
      if(list.length===0){setText('classHint','尚未分配班级');setText('classList','暂无班级，请联系管理员分配或进入完整系统创建。');setText('kpi-classes','0');setText('classes-live','已读取教师班级');return;}
      setText('classHint','已读取教师班级列表，点击完整系统继续操作。');
      setText('kpi-classes',String(list.length));setText('classes-live','已读取教师班级');
      const html=list.slice(0,5).map((c,i)=>`<div class="list-item"><b>${c.name||c.title||('班级 '+(i+1))}</b><span>${c.grade||c.subject||c.status||'进入完整系统'}</span></div>`).join('');
      document.getElementById('classList').innerHTML=html;
    }
    async function boot(){
      if(loading)return;
      loading=true;retryButton.disabled=true;retryButton.hidden=true;loginAction.hidden=true;
      loginAction.textContent='前往登录';
      document.getElementById('sessionDot').classList.remove('green');
      setText('sessionTitle','正在检查登录状态');setText('sessionDetail','正在读取，请稍候。');
      for(const name of ['students','classes','questions','assignments']){
        setText('kpi-'+name,'—');setText(name+'-live','等待读取');
      }
      setText('classList','');setText('classHint','等待读取班级');
      try{
        const token=localStorage.getItem('v717Token')||localStorage.getItem('v6Token')||'';
        const remembered=localStorage.getItem('v717Remember')==='1';
        headers=token?{'Authorization':'Bearer '+token}:{};
        if(!token){
          setText('sessionTitle','尚未登录');setText('sessionDetail','请先登录，再查看工作台数据。');
          loginAction.hidden=false;
          for(const name of ['students','classes','questions','assignments'])setText(name+'-live','请先登录');
          setText('classHint','请先登录');return;
        }
        const session=await getJSON('/session');
        setText('sessionTitle',`已登录：${session.name||session.role||'当前账号'}`);
        setText('sessionDetail',`${session.role||'账号'} · ${remembered?'已开启记住登录':'当前会话'}`);
        document.getElementById('sessionDot').classList.add('green');
        setText('heroText','已识别登录状态。你可以从工作台查看概览，再进入完整系统完成学生、题库、作业和成绩操作。');
        if(session.role==='admin'){
          setText('classHint','班级详情请在完整系统查看');
          try{applyOverview(await getJSON('/admin/overview'));}
          catch(error){
            for(const name of ['students','classes','questions','assignments'])setText(name+'-live',failureMessage(error));
            showFailure(error);
          }
        }else if(session.role==='teacher'){
          for(const name of ['students','questions','assignments'])setText(name+'-live','请进入完整系统查看');
          try{applyClasses(await getJSON('/teacher/classes'));}
          catch(error){setText('classHint',failureMessage(error));setText('classes-live',failureMessage(error));showFailure(error);}
        }else{
          for(const name of ['students','classes','questions','assignments'])setText(name+'-live','当前账号无权查看此内容');
          setText('classHint','当前账号无权查看此内容');
        }
      }catch(error){
        const message=failureMessage(error);
        setText('sessionTitle',message);
        setText('sessionDetail',error.status===401?'请进入完整系统重新登录。':error.status===403?'请进入完整系统查看账号提示。':'网络或服务暂时不可用，恢复后点击重试。');
        for(const name of ['students','classes','questions','assignments'])setText(name+'-live',message);
        setText('classHint',message);showFailure(error);
      }finally{loading=false;retryButton.disabled=false;}
    }
    retryButton.addEventListener('click',boot);
    boot();
  </script>
</body>
</html>"""


def install_product_shell(app: FastAPI) -> None:
    """Install the productized root page while preserving the legacy page at /classic."""
    if getattr(app.state, "product_shell_installed", False):
        return

    legacy_root = None
    for route in list(app.router.routes):
        if getattr(route, "path", None) == "/" and "GET" in getattr(route, "methods", set()):
            legacy_root = route
            break

    if legacy_root is not None and not any(getattr(r, "path", None) == "/classic" for r in app.router.routes):
        app.add_api_route(
            "/classic",
            legacy_root.endpoint,
            methods=["GET"],
            response_class=getattr(legacy_root, "response_class", HTMLResponse),
            include_in_schema=False,
        )

    app.router.routes = [
        route
        for route in app.router.routes
        if not (getattr(route, "path", None) == "/" and "GET" in getattr(route, "methods", set()))
    ]

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    def changying_product_home():
        return HTMLResponse(teacher_workbench_html())

    app.state.product_shell_installed = True


__all__ = ["PRODUCT_SHELL_MARKER", "install_product_shell", "teacher_workbench_html"]

