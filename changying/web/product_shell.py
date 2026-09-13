"""Productized landing shell for 长缨辅学.

The shell keeps the complete legacy monolith available at /classic while
turning visible entry points into a modern teacher workbench. It is deliberately
data-safe: it reads existing browser auth state and existing API endpoints, but
it does not mutate production data.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

PRODUCT_SHELL_MARKER = "changying_product_shell_v1_2"


def teacher_workbench_html() -> str:
    """Return the productized 长缨辅学 workbench page."""
    return """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
  <meta name="theme-color" content="#3047ff">
  <link rel="manifest" href="/manifest.webmanifest">
  <title>长缨辅学｜教师工作台 V1.2</title>
  <style>
    :root{--brand:#3047ff;--brand2:#10a874;--brand3:#f59e0b;--ink:#172033;--muted:#68738a;--line:#e6eaf3;--surface:#fff;--soft:#f6f8ff;--shadow:0 20px 55px rgba(25,40,90,.12);--radius:24px}
    *{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;min-height:100dvh;color:var(--ink);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;background:radial-gradient(circle at top left,rgba(48,71,255,.18),transparent 32rem),radial-gradient(circle at top right,rgba(16,168,116,.16),transparent 30rem),linear-gradient(180deg,#f7f9ff 0%,#eef3ff 44%,#f7f8fb 100%);-webkit-text-size-adjust:100%}a{color:inherit;text-decoration:none}button{font:inherit}
    .page{width:min(1180px,100%);margin:0 auto;padding:24px clamp(16px,3vw,34px) 42px}.topbar{display:flex;align-items:center;justify-content:space-between;gap:16px;margin-bottom:18px}.brand{display:flex;align-items:center;gap:12px}.logo{width:50px;height:50px;border-radius:17px;background:linear-gradient(145deg,#3047ff,#6b7cff);box-shadow:var(--shadow);display:grid;place-items:center;color:#fff;font-size:24px;font-weight:900}.brand h1{font-size:23px;line-height:1.1;margin:0}.brand small{display:block;color:var(--muted);margin-top:4px}.actions{display:flex;align-items:center;gap:10px;flex-wrap:wrap}.pill{display:inline-flex;align-items:center;gap:7px;border:1px solid rgba(48,71,255,.14);background:rgba(255,255,255,.82);backdrop-filter:blur(10px);border-radius:999px;padding:10px 14px;color:var(--muted);font-size:13px}.btn{display:inline-flex;align-items:center;justify-content:center;gap:8px;border-radius:15px;padding:12px 16px;font-weight:850;background:#fff;border:1px solid var(--line);transition:.18s ease;cursor:pointer}.btn:hover{transform:translateY(-1px);box-shadow:0 12px 30px rgba(25,40,90,.12)}.btn.primary{background:var(--brand);border-color:var(--brand);color:#fff}.btn.green{background:var(--brand2);border-color:var(--brand2);color:#fff}.btn.ghost{background:rgba(255,255,255,.62)}
    .hero{display:grid;grid-template-columns:1.18fr .82fr;gap:18px;align-items:stretch;margin:18px 0}.panel{background:rgba(255,255,255,.88);border:1px solid rgba(229,234,246,.95);border-radius:var(--radius);box-shadow:var(--shadow);backdrop-filter:blur(14px)}.welcome{padding:30px;position:relative;overflow:hidden}.welcome:after{content:"";position:absolute;inset:auto -90px -110px auto;width:280px;height:280px;border-radius:50%;background:linear-gradient(135deg,rgba(48,71,255,.18),rgba(16,168,116,.18))}.eyebrow{display:inline-flex;gap:8px;align-items:center;font-size:13px;font-weight:900;color:var(--brand);background:#eef2ff;border:1px solid #dbe3ff;border-radius:999px;padding:8px 12px;margin-bottom:16px}.welcome h2{font-size:clamp(30px,5vw,54px);line-height:1.03;margin:0 0 12px;letter-spacing:-.04em}.welcome p{font-size:17px;color:var(--muted);line-height:1.8;margin:0;max-width:760px}.hero-actions{display:flex;gap:12px;flex-wrap:wrap;margin-top:24px;position:relative;z-index:1}.status{padding:22px;display:flex;flex-direction:column;gap:14px}.status h3,.section-title h3{margin:0;font-size:18px}.mini{display:flex;align-items:center;gap:12px;padding:14px;border-radius:18px;background:#f7f9ff;border:1px solid #e9edfb}.mini b{display:block;margin-bottom:3px}.mini span{font-size:13px;color:var(--muted);line-height:1.5}.dot{width:12px;height:12px;border-radius:50%;background:var(--brand);box-shadow:0 0 0 6px rgba(48,71,255,.12)}.dot.green{background:var(--brand2);box-shadow:0 0 0 6px rgba(16,168,116,.12)}.dot.orange{background:var(--brand3);box-shadow:0 0 0 6px rgba(245,158,11,.14)}
    .grid{display:grid;gap:16px}.kpis{grid-template-columns:repeat(4,1fr);margin:18px 0}.card{padding:20px;background:var(--surface);border:1px solid var(--line);border-radius:22px;box-shadow:0 14px 34px rgba(25,40,90,.08)}.kpi .icon{width:42px;height:42px;border-radius:16px;display:grid;place-items:center;background:#eef2ff;color:var(--brand);font-size:22px;margin-bottom:16px}.kpi strong{font-size:32px;display:block;letter-spacing:-.04em}.kpi span{color:var(--muted);font-size:14px}.live{font-size:11px;color:var(--brand2);font-weight:900;margin-top:8px}.section{margin-top:20px}.section-title{display:flex;justify-content:space-between;align-items:end;gap:12px;margin:0 0 14px}.section-title p{margin:4px 0 0;color:var(--muted);font-size:14px}.quick{grid-template-columns:repeat(3,1fr)}.quick-card{display:flex;gap:16px;align-items:flex-start;min-height:132px;position:relative;overflow:hidden}.quick-card:after{content:"→";position:absolute;right:20px;bottom:16px;color:#b8c1d6;font-weight:900;font-size:22px}.quick-card .icon{flex:0 0 48px;width:48px;height:48px;border-radius:18px;display:grid;place-items:center;background:#f1f5ff;font-size:24px}.quick-card h4{margin:2px 0 8px;font-size:17px}.quick-card p{margin:0;color:var(--muted);line-height:1.65;font-size:14px}.work{grid-template-columns:1fr 1fr}.list{display:grid;gap:10px}.list-item{display:flex;justify-content:space-between;gap:12px;align-items:center;padding:13px;border-radius:16px;background:var(--soft);border:1px solid #e8edfb}.list-item b{font-size:14px}.list-item span{font-size:13px;color:var(--muted);text-align:right}.path{grid-template-columns:repeat(4,1fr)}.path-step{position:relative;min-height:154px}.path-step em{font-style:normal;color:var(--brand);font-size:12px;font-weight:900;letter-spacing:.06em}.path-step h4{margin:8px 0 8px}.path-step p{margin:0;color:var(--muted);line-height:1.7;font-size:14px}.check{grid-template-columns:1.05fr .95fr}.check-grid{display:grid;gap:10px}.check-item{display:flex;gap:10px;align-items:flex-start;padding:12px;border-radius:16px;background:#f8faff;border:1px solid #edf1fb}.check-item i{font-style:normal}.check-item b{display:block;font-size:14px}.check-item span{display:block;margin-top:3px;color:var(--muted);font-size:13px;line-height:1.5}.note{padding:14px;border-radius:18px;background:#fff7ed;border:1px solid #fed7aa;color:#9a3412;line-height:1.7}.brand-card{background:linear-gradient(145deg,#172033,#3047ff);color:#fff;position:relative;overflow:hidden}.brand-card p{color:rgba(255,255,255,.78);line-height:1.75}.brand-card:after{content:"长缨";position:absolute;right:-18px;bottom:-24px;font-size:86px;font-weight:900;letter-spacing:-.08em;color:rgba(255,255,255,.08)}.footer{color:var(--muted);font-size:13px;text-align:center;margin-top:28px}.bottom-nav{display:none}
    @media(max-width:980px){.hero,.work,.check{grid-template-columns:1fr}.kpis,.path{grid-template-columns:repeat(2,1fr)}.quick{grid-template-columns:1fr 1fr}}@media(max-width:640px){.page{padding:18px 14px 96px}.topbar{align-items:flex-start;flex-direction:column}.pill.hide-mobile{display:none}.welcome{padding:24px 20px}.kpis,.quick,.path{grid-template-columns:1fr}.hero-actions .btn,.actions .btn{width:100%}.brand h1{font-size:20px}.bottom-nav{position:fixed;left:10px;right:10px;bottom:10px;z-index:99;display:grid;grid-template-columns:repeat(3,1fr);gap:8px;padding:8px;border-radius:20px;background:rgba(255,255,255,.92);box-shadow:0 18px 46px rgba(23,32,51,.18);border:1px solid var(--line);backdrop-filter:blur(12px)}.bottom-nav a{text-align:center;border-radius:15px;padding:10px 6px;background:#f7f9ff;font-size:12px;font-weight:900;color:var(--ink)}}
  </style>
</head>
<body>
  <main class="page">
    <header class="topbar"><div class="brand"><div class="logo">长</div><div><h1>长缨辅学</h1><small>教师工作台 · V1.2 运营预览</small></div></div><div class="actions"><span class="pill hide-mobile" id="clock">今天</span><a class="btn ghost" href="/classic">完整系统</a><a class="btn primary" href="/classic">开始上课</a></div></header>
    <section class="hero"><div class="panel welcome"><div class="eyebrow">长缨辅学 V1.2 · 可投入使用前的工作台</div><h2>先把每天上课的动作变简单。</h2><p id="heroText">新版工作台会自动读取现有登录状态；未登录时作为品牌入口，登录后显示真实学生、班级、题库、作业和教学数据概览。</p><div class="hero-actions"><a class="btn primary" href="/classic">进入完整系统</a><a class="btn green" href="#path">按流程上课</a><a class="btn" href="#checkup">运营体检</a></div></div><aside class="panel status"><h3>当前状态</h3><div class="mini"><i class="dot" id="sessionDot"></i><div><b id="sessionTitle">正在检查登录状态</b><span id="sessionDetail">会读取旧版系统的 v717Token / v717Remember，不需要重新登录。</span></div></div><div class="mini"><i class="dot green"></i><div><b>完整功能已保留</b><span>旧版系统入口仍在 /classic，数据和业务流程不变。</span></div></div><div class="mini"><i class="dot orange"></i><div><b>只读上线策略</b><span>本页只读 /session、/admin/overview、/teacher/classes，不写入生产数据。</span></div></div></aside></section>
    <section class="grid kpis" id="live" aria-label="运营概览"><div class="card kpi"><div class="icon">👨‍🎓</div><strong id="kpi-students">—</strong><span>学生</span><div class="live" id="students-live">等待登录后读取</div></div><div class="card kpi"><div class="icon">🏫</div><strong id="kpi-classes">—</strong><span>班级 / 课程</span><div class="live" id="classes-live">教师或管理员可见</div></div><div class="card kpi"><div class="icon">📖</div><strong id="kpi-questions">—</strong><span>题库</span><div class="live" id="questions-live">管理员概览</div></div><div class="card kpi"><div class="icon">📝</div><strong id="kpi-assignments">—</strong><span>作业</span><div class="live" id="assignments-live">管理员概览</div></div></section>
    <section class="section" id="path"><div class="section-title"><div><h3>今日上课路径</h3><p>按照线下辅学真实动作重排：先确认对象，再组织训练，最后看反馈。</p></div><a class="pill" href="/classic">完整系统 →</a></div><div class="grid path"><a class="card path-step" href="/classic"><em>STEP 01</em><h4>看今天学生</h4><p>确认学生、班级、到课和重点关注对象。</p></a><a class="card path-step" href="/classic"><em>STEP 02</em><h4>选题与组卷</h4><p>从题库、知识点和难度进入分层练习。</p></a><a class="card path-step" href="/classic"><em>STEP 03</em><h4>布置今日作业</h4><p>把课堂练习与课后任务连接起来。</p></a><a class="card path-step" href="/classic"><em>STEP 04</em><h4>看结果反馈</h4><p>用成绩、错题和积分决定下一次干预。</p></a></div></section>
    <section class="section" id="quick"><div class="section-title"><div><h3>高频功能入口</h3><p>老师常用功能集中展示，减少找菜单时间。</p></div></div><div class="grid quick"><a class="card quick-card" href="/classic"><div class="icon">👨‍🎓</div><div><h4>学生管理</h4><p>查看学生、家长、班级、学习状态与跟进记录。</p></div></a><a class="card quick-card" href="/classic"><div class="icon">🏫</div><div><h4>班级与课程</h4><p>管理晚托、周末课、寒暑假班与日常教学安排。</p></div></a><a class="card quick-card" href="/classic"><div class="icon">📖</div><div><h4>数学题库</h4><p>围绕人教版五年级、单元、知识点和难度组织题目。</p></div></a><a class="card quick-card" href="/classic"><div class="icon">📄</div><div><h4>自动组卷</h4><p>快速生成课后练习、单元测验与分层训练卷。</p></div></a><a class="card quick-card" href="/classic"><div class="icon">📝</div><div><h4>今日作业</h4><p>布置、查看提交、批改与回收学生完成情况。</p></div></a><a class="card quick-card" href="/classic"><div class="icon">📊</div><div><h4>成绩分析</h4><p>快速看到班级表现、错题集中区和需要重点关注的学生。</p></div></a></div></section>
    <section class="section grid work"><div class="card"><div class="section-title"><div><h3>我的班级</h3><p id="classHint">登录教师账号后，会展示当前负责班级。</p></div></div><div class="list" id="classList"><div class="list-item"><b>进入完整系统后查看</b><span>/classic</span></div></div></div><div class="card"><div class="section-title"><div><h3>今日工作流</h3><p>按照补习班一天的真实流程组织。</p></div></div><div class="list"><div class="list-item"><b>01 课前</b><span>看班级与学生</span></div><div class="list-item"><b>02 课中</b><span>题库与分层练习</span></div><div class="list-item"><b>03 课后</b><span>作业、成绩、错题</span></div></div></div></section>
    <section class="section grid check" id="checkup"><div class="card"><div class="section-title"><div><h3>运营体检</h3><p>把系统投入使用前最重要的检查项放在首页。</p></div></div><div class="check-grid"><div class="check-item"><i>✅</i><div><b>入口清晰</b><span>/workbench 看新版，/classic 用完整系统。</span></div></div><div class="check-item"><i>✅</i><div><b>业务保留</b><span>学生、题库、作业、成绩等功能继续走旧系统。</span></div></div><div class="check-item"><i>🔒</i><div><b>数据安全</b><span>新版工作台只读取数据，不直接修改数据库。</span></div></div><div class="check-item"><i>📱</i><div><b>移动端入口</b><span>手机底部增加工作台、流程、完整系统快捷入口。</span></div></div></div></div><div class="card"><div class="section-title"><div><h3>首次使用建议</h3><p>明天可以按这个顺序试跑一节课。</p></div></div><div class="list"><div class="list-item"><b>先登录完整系统</b><span>确认账号可用</span></div><div class="list-item"><b>回到工作台</b><span>看概览是否读取</span></div><div class="list-item"><b>进入学生/题库/作业</b><span>按真实流程试用</span></div><div class="list-item"><b>记录卡点</b><span>下一轮继续优化</span></div></div></div></section>
    <section class="section card brand-card"><h3>长缨辅学，不只是题库。</h3><p>它应该成为线下补习班每天真正使用的教师工作台：管理学生、组织班级、布置作业、生成练习、追踪成绩，并逐步连接公众号、小程序和 AI 辅学。</p></section>
    <p class="footer">长缨辅学 V1.2 · 新版工作台只读现有接口，不改变生产数据 · 完整系统保留在 /classic</p>
  </main>
  <nav class="bottom-nav" aria-label="移动端快捷入口"><a href="/workbench">工作台</a><a href="#path">上课路径</a><a href="/classic">完整系统</a></nav>
  <script>
    const token=localStorage.getItem('v717Token')||localStorage.getItem('v6Token')||'';
    const remembered=localStorage.getItem('v717Remember')==='1';
    const headers=token?{'Authorization':'Bearer '+token}:{};
    const setText=(id,text)=>{const el=document.getElementById(id);if(el)el.textContent=text;};
    const fmt=(n)=>Number.isFinite(Number(n))?String(n):'—';
    const clock=new Intl.DateTimeFormat('zh-CN',{weekday:'long',month:'long',day:'numeric'}).format(new Date());
    setText('clock',clock);
    async function getJSON(url){const res=await fetch(url,{headers,cache:'no-store'});if(!res.ok)throw new Error(url+':'+res.status);return res.json();}
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
      if(!Array.isArray(list)||list.length===0)return;
      setText('classHint','已读取教师班级列表，点击完整系统继续操作。');
      setText('kpi-classes',String(list.length));setText('classes-live','已读取教师班级');
      const html=list.slice(0,5).map((c,i)=>`<div class="list-item"><b>${c.name||c.title||('班级 '+(i+1))}</b><span>${c.grade||c.subject||c.status||'进入完整系统'}</span></div>`).join('');
      document.getElementById('classList').innerHTML=html;
    }
    async function boot(){
      if(!token){setText('sessionTitle','尚未登录');setText('sessionDetail','先进入 /classic 登录，再回到工作台查看真实概览。');return;}
      try{
        const session=await getJSON('/session');
        setText('sessionTitle',`已登录：${session.name||session.role||'当前账号'}`);
        setText('sessionDetail',`${session.role||'账号'} · ${remembered?'已开启记住登录':'当前会话'} · 可读取工作台数据`);
        document.getElementById('sessionDot').classList.add('green');
        setText('heroText','已识别登录状态。你可以从工作台查看概览，再进入完整系统完成学生、题库、作业和成绩操作。');
        try{applyOverview(await getJSON('/admin/overview'));}catch(e){setText('questions-live','非管理员或暂无概览');setText('assignments-live','非管理员或暂无概览');}
        try{applyClasses(await getJSON('/teacher/classes'));}catch(e){setText('classHint','当前账号暂无教师班级列表，仍可进入完整系统操作。');}
      }catch(e){setText('sessionTitle','登录已失效或未授权');setText('sessionDetail','请进入完整系统重新登录，然后回到工作台。');}
    }
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
