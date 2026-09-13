"""Productized landing shell for 长缨辅学.

The V1 shell keeps the complete legacy monolith available at /classic while
turning the root page into a modern teacher workbench. The shell is deliberately
small and data-safe: it reads existing browser auth state and existing API
endpoints, but it does not mutate production data.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

PRODUCT_SHELL_MARKER = "changying_product_shell_v1_1"


def teacher_workbench_html() -> str:
    """Return the productized 长缨辅学 workbench page."""
    return """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
  <meta name="theme-color" content="#3047ff">
  <link rel="manifest" href="/manifest.webmanifest">
  <title>长缨辅学｜教师工作台</title>
  <style>
    :root{--brand:#3047ff;--brand2:#10a874;--ink:#172033;--muted:#68738a;--line:#e6eaf3;--surface:#fff;--soft:#f6f8ff;--shadow:0 20px 55px rgba(25,40,90,.12);--radius:24px}
    *{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;min-height:100dvh;color:var(--ink);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;background:radial-gradient(circle at top left,rgba(48,71,255,.18),transparent 32rem),radial-gradient(circle at top right,rgba(16,168,116,.16),transparent 30rem),linear-gradient(180deg,#f7f9ff 0%,#eef3ff 44%,#f7f8fb 100%);-webkit-text-size-adjust:100%}a{color:inherit;text-decoration:none}
    .page{width:min(1180px,100%);margin:0 auto;padding:24px clamp(16px,3vw,34px) 42px}.topbar{display:flex;align-items:center;justify-content:space-between;gap:16px;margin-bottom:18px}.brand{display:flex;align-items:center;gap:12px}.logo{width:50px;height:50px;border-radius:17px;background:linear-gradient(145deg,#3047ff,#6b7cff);box-shadow:var(--shadow);display:grid;place-items:center;color:#fff;font-size:24px;font-weight:900}.brand h1{font-size:23px;line-height:1.1;margin:0}.brand small{display:block;color:var(--muted);margin-top:4px}.actions{display:flex;align-items:center;gap:10px;flex-wrap:wrap}.pill{display:inline-flex;align-items:center;gap:7px;border:1px solid rgba(48,71,255,.14);background:rgba(255,255,255,.8);backdrop-filter:blur(10px);border-radius:999px;padding:10px 14px;color:var(--muted);font-size:13px}.btn{display:inline-flex;align-items:center;justify-content:center;gap:8px;border-radius:15px;padding:12px 16px;font-weight:800;background:#fff;border:1px solid var(--line);transition:.18s ease}.btn:hover{transform:translateY(-1px);box-shadow:0 12px 30px rgba(25,40,90,.12)}.btn.primary{background:var(--brand);border-color:var(--brand);color:#fff}.btn.green{background:var(--brand2);border-color:var(--brand2);color:#fff}
    .hero{display:grid;grid-template-columns:1.25fr .75fr;gap:18px;align-items:stretch;margin:18px 0}.panel{background:rgba(255,255,255,.88);border:1px solid rgba(229,234,246,.95);border-radius:var(--radius);box-shadow:var(--shadow);backdrop-filter:blur(14px)}.welcome{padding:30px;position:relative;overflow:hidden}.welcome:after{content:"";position:absolute;inset:auto -90px -110px auto;width:280px;height:280px;border-radius:50%;background:linear-gradient(135deg,rgba(48,71,255,.18),rgba(16,168,116,.18))}.eyebrow{display:inline-flex;gap:8px;align-items:center;font-size:13px;font-weight:900;color:var(--brand);background:#eef2ff;border:1px solid #dbe3ff;border-radius:999px;padding:8px 12px;margin-bottom:16px}.welcome h2{font-size:clamp(30px,5vw,54px);line-height:1.03;margin:0 0 12px;letter-spacing:-.04em}.welcome p{font-size:17px;color:var(--muted);line-height:1.8;margin:0;max-width:760px}.hero-actions{display:flex;gap:12px;flex-wrap:wrap;margin-top:24px;position:relative;z-index:1}
    .status{padding:22px;display:flex;flex-direction:column;gap:14px}.status h3,.section-title h3{margin:0;font-size:18px}.mini{display:flex;align-items:center;gap:12px;padding:14px;border-radius:18px;background:#f7f9ff;border:1px solid #e9edfb}.mini b{display:block;margin-bottom:3px}.mini span{font-size:13px;color:var(--muted)}.dot{width:12px;height:12px;border-radius:50%;background:var(--brand);box-shadow:0 0 0 6px rgba(48,71,255,.12)}.dot.green{background:var(--brand2);box-shadow:0 0 0 6px rgba(16,168,116,.12)}.dot.orange{background:#f59e0b;box-shadow:0 0 0 6px rgba(245,158,11,.14)}
    .grid{display:grid;gap:16px}.kpis{grid-template-columns:repeat(4,1fr);margin:18px 0}.card{padding:20px;background:var(--surface);border:1px solid var(--line);border-radius:22px;box-shadow:0 14px 34px rgba(25,40,90,.08)}.kpi .icon{width:42px;height:42px;border-radius:16px;display:grid;place-items:center;background:#eef2ff;color:var(--brand);font-size:22px;margin-bottom:16px}.kpi strong{font-size:32px;display:block;letter-spacing:-.04em}.kpi span{color:var(--muted);font-size:14px}.live{font-size:11px;color:var(--brand2);font-weight:900;margin-top:8px}.section{margin-top:20px}.section-title{display:flex;justify-content:space-between;align-items:end;gap:12px;margin:0 0 14px}.section-title p{margin:4px 0 0;color:var(--muted);font-size:14px}.quick{grid-template-columns:repeat(3,1fr)}.quick-card{display:flex;gap:16px;align-items:flex-start;min-height:132px;position:relative;overflow:hidden}.quick-card:after{content:"→";position:absolute;right:20px;bottom:16px;color:#b8c1d6;font-weight:900;font-size:22px}.quick-card .icon{flex:0 0 48px;width:48px;height:48px;border-radius:18px;display:grid;place-items:center;background:#f1f5ff;font-size:24px}.quick-card h4{margin:2px 0 8px;font-size:17px}.quick-card p{margin:0;color:var(--muted);line-height:1.65;font-size:14px}.work{grid-template-columns:1fr 1fr}.list{display:grid;gap:10px}.list-item{display:flex;justify-content:space-between;gap:12px;align-items:center;padding:13px;border-radius:16px;background:var(--soft);border:1px solid #e8edfb}.list-item b{font-size:14px}.list-item span{font-size:13px;color:var(--muted)}.note{padding:14px;border-radius:18px;background:#fff7ed;border:1px solid #fed7aa;color:#9a3412;line-height:1.7}.brand-card{background:linear-gradient(145deg,#172033,#3047ff);color:#fff;position:relative;overflow:hidden}.brand-card p{color:rgba(255,255,255,.78);line-height:1.75}.brand-card:after{content:"长缨";position:absolute;right:-18px;bottom:-24px;font-size:86px;font-weight:900;letter-spacing:-.08em;color:rgba(255,255,255,.08)}.footer{color:var(--muted);font-size:13px;text-align:center;margin-top:28px}
    @media(max-width:900px){.hero,.work{grid-template-columns:1fr}.kpis{grid-template-columns:repeat(2,1fr)}.quick{grid-template-columns:1fr 1fr}}@media(max-width:640px){.page{padding-top:18px}.topbar{align-items:flex-start}.pill.hide-mobile{display:none}.welcome{padding:24px 20px}.kpis,.quick{grid-template-columns:1fr}.hero-actions .btn,.actions .btn{width:100%}.brand h1{font-size:20px}}
  </style>
</head>
<body>
  <main class="page">
    <header class="topbar"><div class="brand"><div class="logo">长</div><div><h1>长缨辅学</h1><small>教师工作台 · V1.1 可操作预览</small></div></div><div class="actions"><span class="pill hide-mobile" id="clock">今天</span><a class="btn" href="/classic">完整系统</a><a class="btn primary" href="/classic">开始上课</a></div></header>
    <section class="hero"><div class="panel welcome"><div class="eyebrow">长缨辅学 V1.1 · 登录感知工作台</div><h2>打开首页，就知道今天先做什么。</h2><p id="heroText">新版首页会自动读取现有登录状态；未登录时作为品牌入口，登录后显示真实学生、班级、题库、作业和教学数据概览。</p><div class="hero-actions"><a class="btn primary" href="/classic">进入现有完整功能</a><a class="btn" href="#quick">查看快捷入口</a><a class="btn green" href="#live">查看数据概览</a></div></div><aside class="panel status"><h3>当前状态</h3><div class="mini"><i class="dot" id="sessionDot"></i><div><b id="sessionTitle">正在检查登录状态</b><span id="sessionDetail">会读取旧版系统的 v717Token，不需要重新登录。</span></div></div><div class="mini"><i class="dot green"></i><div><b>完整功能已保留</b><span>旧版系统入口仍在 /classic，数据和业务流程不变。</span></div></div><div class="mini"><i class="dot orange"></i><div><b>安全上线策略</b><span>本页只读现有接口，不写入生产数据库。</span></div></div></aside></section>
    <section class="grid kpis" id="live" aria-label="运营概览"><div class="card kpi"><div class="icon">👨‍🎓</div><strong id="kpi-students">—</strong><span>学生</span><div class="live" id="students-live">等待登录后读取</div></div><div class="card kpi"><div class="icon">🏫</div><strong id="kpi-classes">—</strong><span>班级 / 课程</span><div class="live" id="classes-live">教师或管理员可见</div></div><div class="card kpi"><div class="icon">📖</div><strong id="kpi-questions">—</strong><span>题库</span><div class="live" id="questions-live">管理员概览</div></div><div class="card kpi"><div class="icon">📝</div><strong id="kpi-assignments">—</strong><span>作业</span><div class="live" id="assignments-live">管理员概览</div></div></section>
    <section class="section" id="quick"><div class="section-title"><div><h3>高频功能入口</h3><p>先把老师最常用的入口集中展示，减少寻找菜单的时间。</p></div><a class="pill" href="/classic">完整系统 →</a></div><div class="grid quick"><a class="card quick-card" href="/classic"><div class="icon">👨‍🎓</div><div><h4>学生管理</h4><p>查看学生、家长、班级、学习状态与跟进记录。</p></div></a><a class="card quick-card" href="/classic"><div class="icon">🏫</div><div><h4>班级与课程</h4><p>管理晚托、周末课、寒暑假班与日常教学安排。</p></div></a><a class="card quick-card" href="/classic"><div class="icon">📖</div><div><h4>数学题库</h4><p>围绕人教版五年级、单元、知识点和难度组织题目。</p></div></a><a class="card quick-card" href="/classic"><div class="icon">📄</div><div><h4>自动组卷</h4><p>快速生成课后练习、单元测验与分层训练卷。</p></div></a><a class="card quick-card" href="/classic"><div class="icon">📝</div><div><h4>今日作业</h4><p>布置、查看提交、批改与回收学生完成情况。</p></div></a><a class="card quick-card" href="/classic"><div class="icon">📊</div><div><h4>成绩分析</h4><p>快速看到班级表现、错题集中区和需要重点关注的学生。</p></div></a></div></section>
    <section class="section grid work"><div class="card"><div class="section-title"><div><h3>我的班级</h3><p id="classHint">登录教师账号后，会展示当前负责班级。</p></div></div><div class="list" id="classList"><div class="list-item"><b>进入完整系统后查看</b><span>/classic</span></div></div></div><div class="card"><div class="section-title"><div><h3>今日工作流</h3><p>按照线下补习班真实流程组织。</p></div></div><div class="list"><div class="list-item"><b>01 课前</b><span>看班级与学生</span></div><div class="list-item"><b>02 课中</b><span>题库与分层练习</span></div><div class="list-item"><b>03 课后</b><span>作业、成绩、错题</span></div></div></div></section>
    <section class="section card brand-card"><h3>长缨辅学，不只是题库。</h3><p>它应该成为线下补习班每天真正使用的教师工作台：管理学生、组织班级、布置作业、生成练习、追踪成绩，并逐步连接公众号、小程序和 AI 辅学。</p></section>
    <p class="footer">长缨辅学 V1.1 · 新版首页只读现有接口，不改变生产数据 · 完整系统保留在 /classic</p>
  </main>
  <script>
    const $=s=>document.querySelector(s);
    const setText=(id,value)=>{const el=$(id);if(el)el.textContent=value};
    const token=()=>{const remembered=localStorage.getItem('v717Remember')==='1';return (remembered?localStorage.getItem('v717Token'):sessionStorage.getItem('v717Token'))||localStorage.getItem('v717Token')||sessionStorage.getItem('v717Token')||localStorage.getItem('v6Token')||''};
    async function getJson(path){const headers={'Accept':'application/json'};const t=token();if(t)headers.Authorization='Bearer '+t;const r=await fetch(path,{headers});if(!r.ok)throw new Error(String(r.status));return await r.json()}
    function setLoggedOut(){setText('#sessionTitle','未登录');setText('#sessionDetail','点击“开始上课”进入完整系统登录。');setText('#heroText','这是新版长缨辅学入口。登录后首页会自动显示真实运营数据；未登录时仍可作为品牌首页和功能导航使用。');['students','classes','questions','assignments'].forEach(x=>setText('#'+`kpi-${x}`,'—'))}
    function applyOverview(o){if(!o)return;setText('#kpi-students',String(o.activeStudents??o.students??'—'));setText('#kpi-classes',String(o.classes??'—'));setText('#kpi-questions',String(o.questions??'—'));setText('#kpi-assignments',String(o.assignments??'—'));setText('#students-live','来自 /admin/overview');setText('#classes-live','来自 /admin/overview');setText('#questions-live','来自 /admin/overview');setText('#assignments-live','来自 /admin/overview')}
    function applyClasses(rows){if(!Array.isArray(rows))return;setText('#kpi-classes',String(rows.length));setText('#classes-live','来自 /teacher/classes');const box=$('#classList');if(!box)return;box.innerHTML=rows.length?rows.slice(0,6).map(c=>`<a class="list-item" href="/classic"><b>${escapeHtml(c.name||'未命名班级')}</b><span>${c.grade||''}年级 · ${c.studentCount||0}人</span></a>`).join(''):'<div class="list-item"><b>暂无班级</b><span>可在完整系统创建</span></div>';setText('#classHint','已读取教师班级数据')}
    function escapeHtml(s){return String(s).replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[m]))}
    async function boot(){setText('#clock',new Intl.DateTimeFormat('zh-CN',{weekday:'long',month:'long',day:'numeric'}).format(new Date()));try{const s=await getJson('/session');if(!s||!s.valid)throw new Error('invalid');setText('#sessionTitle','已登录：'+(s.name||s.username||'用户'));setText('#sessionDetail','角色：'+(s.role||'未知')+' · 可直接进入完整系统继续操作');setText('#heroText','欢迎回来。新版首页正在逐步把现有功能整理成更清晰的工作台，同时保留完整系统作为稳定入口。');if(s.role==='admin'){try{applyOverview(await getJson('/admin/overview'))}catch(e){setText('#students-live','管理员概览读取失败：'+e.message)}}if(s.role==='teacher'){try{applyClasses(await getJson('/teacher/classes'))}catch(e){setText('#classHint','教师班级读取失败：'+e.message)}}}catch(e){setLoggedOut()}}
    boot();
  </script>
</body>
</html>"""


def install_product_shell(app: FastAPI) -> None:
    """Install the modern root shell and preserve the previous root at /classic."""
    if getattr(app.state, "product_shell_installed", False):
        return

    legacy_home = None
    for route in list(app.router.routes):
        if getattr(route, "path", None) == "/" and "GET" in getattr(route, "methods", set()):
            legacy_home = route
            app.router.routes.remove(route)
            break

    if legacy_home is not None:
        app.add_api_route(
            "/classic",
            legacy_home.endpoint,
            methods=["GET"],
            response_class=getattr(legacy_home, "response_class", HTMLResponse),
            include_in_schema=False,
        )

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    def product_home() -> HTMLResponse:
        return HTMLResponse(
            teacher_workbench_html(),
            headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"},
        )

    app.state.product_shell_installed = True


__all__ = ["PRODUCT_SHELL_MARKER", "install_product_shell", "teacher_workbench_html"]
