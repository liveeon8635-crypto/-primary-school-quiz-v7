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
  <title>长缨辅学｜小学托管与教学</title>
  <style>
    :root{--brand:#1e2fbf;--brand2:#10a874;--gold:#f4b740;--ink:#142033;--muted:#66728a;--line:#e6eaf3;--surface:#fff;--soft:#f6f8ff;--deep:#111a3a;--shadow:0 20px 55px rgba(21,33,70,.12);--radius:24px}
    *{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;min-height:100dvh;color:var(--ink);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;background:radial-gradient(circle at top left,rgba(30,47,191,.18),transparent 34rem),radial-gradient(circle at top right,rgba(16,168,116,.14),transparent 31rem),linear-gradient(180deg,#f7f9ff 0%,#eef3ff 45%,#f7f8fb 100%);-webkit-text-size-adjust:100%}a{color:inherit;text-decoration:none}button{font:inherit}.page{width:min(1180px,100%);margin:0 auto;padding:24px clamp(16px,3vw,34px) 42px}.topbar{display:flex;align-items:center;justify-content:space-between;gap:16px;margin-bottom:18px}.brand{display:flex;align-items:center;gap:12px}.logo{width:52px;height:52px;border-radius:18px;background:linear-gradient(145deg,var(--deep),var(--brand));box-shadow:var(--shadow);display:grid;place-items:center;color:#fff;font-size:24px;font-weight:950}.brand h1{font-size:23px;line-height:1.1;margin:0}.brand small{display:block;color:var(--muted);margin-top:4px}.actions{display:flex;align-items:center;gap:10px;flex-wrap:wrap}.pill{display:inline-flex;align-items:center;gap:7px;border:1px solid rgba(30,47,191,.14);background:rgba(255,255,255,.82);backdrop-filter:blur(10px);border-radius:999px;padding:10px 14px;color:var(--muted);font-size:13px}.btn{display:inline-flex;align-items:center;justify-content:center;gap:8px;border-radius:15px;padding:12px 16px;font-weight:850;background:#fff;border:1px solid var(--line);transition:.18s ease;cursor:pointer}.btn:hover{transform:translateY(-1px);box-shadow:0 12px 30px rgba(25,40,90,.12)}.btn.primary{background:var(--brand);border-color:var(--brand);color:#fff}.btn.green{background:var(--brand2);border-color:var(--brand2);color:#fff}.btn.dark{background:var(--deep);border-color:var(--deep);color:#fff}.btn.ghost{background:rgba(255,255,255,.62)}
    .hero{display:grid;grid-template-columns:1.18fr .82fr;gap:18px;align-items:stretch;margin:18px 0}.panel,.card{background:rgba(255,255,255,.9);border:1px solid rgba(229,234,246,.95);border-radius:var(--radius);box-shadow:var(--shadow);backdrop-filter:blur(14px)}.welcome{padding:30px;position:relative;overflow:hidden}.welcome:after{content:"";position:absolute;inset:auto -90px -110px auto;width:280px;height:280px;border-radius:50%;background:linear-gradient(135deg,rgba(30,47,191,.18),rgba(16,168,116,.18))}.eyebrow{display:inline-flex;gap:8px;align-items:center;font-size:13px;font-weight:900;color:var(--brand);background:#eef2ff;border:1px solid #dbe3ff;border-radius:999px;padding:8px 12px;margin-bottom:16px}.welcome h2{font-size:clamp(30px,5vw,54px);line-height:1.03;margin:0 0 12px;letter-spacing:-.04em}.welcome p{font-size:17px;color:var(--muted);line-height:1.8;margin:0;max-width:760px}.hero-actions{display:flex;gap:12px;flex-wrap:wrap;margin-top:24px;position:relative;z-index:1}.status{padding:22px;display:flex;flex-direction:column;gap:14px}.status h3,.section-title h3{margin:0;font-size:18px}.mini{display:flex;align-items:center;gap:12px;padding:14px;border-radius:18px;background:#f7f9ff;border:1px solid #e9edfb}.mini b{display:block;margin-bottom:3px}.mini span{font-size:13px;color:var(--muted);line-height:1.5}.dot{width:12px;height:12px;border-radius:50%;background:var(--brand);box-shadow:0 0 0 6px rgba(30,47,191,.12)}.dot.green{background:var(--brand2);box-shadow:0 0 0 6px rgba(16,168,116,.12)}.dot.orange{background:var(--gold);box-shadow:0 0 0 6px rgba(244,183,64,.16)}
    .grid{display:grid;gap:16px}.kpis{grid-template-columns:repeat(4,1fr);margin:18px 0}.card{padding:20px}.kpi .icon{width:42px;height:42px;border-radius:16px;display:grid;place-items:center;background:#eef2ff;color:var(--brand);font-size:22px;margin-bottom:16px}.kpi strong{font-size:32px;display:block;letter-spacing:-.04em}.kpi span{color:var(--muted);font-size:14px}.live{font-size:11px;color:var(--brand2);font-weight:900;margin-top:8px}.section{margin-top:20px}.section-title{display:flex;justify-content:space-between;align-items:end;gap:12px;margin:0 0 14px}.section-title p{margin:4px 0 0;color:var(--muted);font-size:14px}.quick{grid-template-columns:repeat(3,1fr)}.quick-card{display:flex;gap:16px;align-items:flex-start;min-height:132px;position:relative;overflow:hidden}.quick-card:after{content:"→";position:absolute;right:20px;bottom:16px;color:#b8c1d6;font-weight:900;font-size:22px}.quick-card .icon{flex:0 0 48px;width:48px;height:48px;border-radius:18px;display:grid;place-items:center;background:#f1f5ff;font-size:24px}.quick-card h4{margin:2px 0 8px;font-size:17px}.quick-card p{margin:0;color:var(--muted);line-height:1.65;font-size:14px}.work,.check{grid-template-columns:1.05fr .95fr}.list{display:grid;gap:10px}.list-item{display:flex;justify-content:space-between;gap:12px;align-items:center;padding:13px;border-radius:16px;background:var(--soft);border:1px solid #e8edfb}.list-item b{font-size:14px}.list-item span{font-size:13px;color:var(--muted);text-align:right}.path{grid-template-columns:repeat(4,1fr)}.path-step{position:relative;min-height:154px}.path-step em{font-style:normal;color:var(--brand);font-size:12px;font-weight:900;letter-spacing:.06em}.path-step h4{margin:8px 0 8px}.path-step p{margin:0;color:var(--muted);line-height:1.7;font-size:14px}.system{grid-template-columns:repeat(5,1fr)}.system .card{min-height:168px;background:#fff}.system em{font-style:normal;display:inline-grid;place-items:center;width:34px;height:34px;border-radius:13px;background:#eef2ff;color:var(--brand);font-weight:950}.system h4{margin:14px 0 8px}.system p{margin:0;color:var(--muted);line-height:1.65;font-size:14px}.bridge{grid-template-columns:repeat(3,1fr)}.bridge .card{min-height:172px}.bridge b{display:inline-block;margin-bottom:10px;color:var(--brand)}.bridge p{margin:0;color:var(--muted);line-height:1.7;font-size:14px}.check-grid{display:grid;gap:10px}.check-item{display:flex;gap:10px;align-items:flex-start;padding:12px;border-radius:16px;background:#f8faff;border:1px solid #edf1fb}.check-item i{font-style:normal}.check-item b{display:block;font-size:14px}.check-item span{display:block;margin-top:3px;color:var(--muted);font-size:13px;line-height:1.5}.brand-card{background:linear-gradient(145deg,#111a3a,#1e2fbf);color:#fff;position:relative;overflow:hidden}.brand-card p{color:rgba(255,255,255,.8);line-height:1.75}.brand-card:after{content:"辅学";position:absolute;right:-18px;bottom:-24px;font-size:86px;font-weight:950;letter-spacing:-.08em;color:rgba(255,255,255,.08)}.footer{color:var(--muted);font-size:13px;text-align:center;margin-top:28px}.bottom-nav{display:none}
    @media(max-width:980px){.hero,.work,.check{grid-template-columns:1fr}.kpis,.path,.system,.bridge{grid-template-columns:repeat(2,1fr)}.quick{grid-template-columns:1fr 1fr}}@media(max-width:640px){.page{padding:18px 14px 96px}.topbar{align-items:flex-start;flex-direction:column}.pill.hide-mobile{display:none}.welcome{padding:24px 20px}.kpis,.quick,.path,.system,.bridge{grid-template-columns:1fr}.hero-actions .btn,.actions .btn{width:100%}.brand h1{font-size:20px}.bottom-nav{position:fixed;left:10px;right:10px;bottom:10px;z-index:99;display:grid;grid-template-columns:repeat(4,1fr);gap:8px;padding:8px;border-radius:20px;background:rgba(255,255,255,.92);box-shadow:0 18px 46px rgba(23,32,51,.18);border:1px solid var(--line);backdrop-filter:blur(12px)}.bottom-nav a{text-align:center;border-radius:15px;padding:10px 4px;background:#f7f9ff;font-size:12px;font-weight:900;color:var(--ink)}}
    [hidden]{display:none!important}.btn:disabled{cursor:wait;opacity:.6}
  </style>
</head>
<body>
  <main class="page">
    <header class="topbar"><div class="brand"><div class="logo">长</div><div><h1>长缨辅学</h1><small>小学托管与教学</small></div></div><div class="actions"><span class="pill hide-mobile" id="clock">今天</span><a class="btn primary" href="/v1">登录 / 进入 V1</a></div></header>
    <section class="hero"><div class="panel welcome"><div class="eyebrow">专注小学阶段的托管与教学</div><h2>一名学生，<br>一份连续发展档案。</h2><p id="heroText">服务晚托、周末课与寒暑假班，支持小学学校教学任务。学生换班、换老师或升年级后，教学记录仍归入同一份长期档案。</p><div class="hero-actions"><a class="btn primary" href="/v1">进入长缨辅学 V1</a><a class="btn green" href="#services">查看服务范围</a><a class="btn ghost" href="#guide">查看使用指引</a></div></div><aside class="panel status"><h3>当前状态</h3><div id="sessionFeedback" role="status" aria-live="polite"><a id="loginAction" class="btn primary" href="/v1" hidden>前往登录</a><button id="retryStatus" class="btn ghost" type="button" hidden>重试</button></div><div class="mini"><i class="dot" id="sessionDot"></i><div><b id="sessionTitle" role="status" aria-live="polite">正在检查登录状态</b><span id="sessionDetail">登录后查看账号对应的教学内容。</span></div></div><div class="mini"><i class="dot green"></i><div><b>学生与家长</b><span>查看学生动态、作业、学习反馈与历史时间线。</span></div></div><div class="mini"><i class="dot orange"></i><div><b>教师与管理员</b><span>按培训机构或学校模式进入当前教学工作台。</span></div></div></aside></section>
    <section class="section" id="services"><div class="section-title"><div><h3>小学托管与教学服务</h3><p>围绕小学阶段的学习与日常照看，按班级安排具体内容。</p></div></div><div class="grid path"><div class="card path-step"><h4>日常托管</h4><p>衔接放学后的日常照看、作业辅导和学习情况反馈。</p></div><div class="card path-step"><h4>周末教学</h4><p>围绕教材内容安排讲解、课堂练习与课后巩固。</p></div><div class="card path-step"><h4>寒暑假班</h4><p>统筹假期课程、复习巩固、作业与学习安排。</p></div><div class="card path-step"><h4>学校教学支持</h4><p>可按学校需要承接小学备课、课堂作业、批改与反馈任务；具体安排另行确认。</p></div></div></section>
    <section class="section" id="live"><div class="section-title"><div><h3>教学概览</h3><p>教师与管理员登录后，按账号权限读取数据。</p></div></div><div class="grid kpis" aria-label="教学概览"><div class="card kpi"><strong id="kpi-students">—</strong><span>学生</span><div class="live" id="students-live">请先登录</div></div><div class="card kpi"><strong id="kpi-classes">—</strong><span>班级 / 课程</span><div class="live" id="classes-live">请先登录</div></div><div class="card kpi"><strong id="kpi-questions">—</strong><span>题库</span><div class="live" id="questions-live">请先登录</div></div><div class="card kpi"><strong id="kpi-assignments">—</strong><span>作业</span><div class="live" id="assignments-live">请先登录</div></div></div></section>
    <section class="section" id="path"><div class="section-title"><div><h3>今日教学安排</h3><p>在教学系统中按实际课程完成以下工作。</p></div></div><div class="grid path"><div class="card path-step"><em>STEP 01</em><h4>确认学生与班级</h4><p>查看班级名单，明确当天课程与需要关注的学生。</p></div><div class="card path-step"><em>STEP 02</em><h4>备课与选题</h4><p>按教材、单元和学生学习情况准备讲解与练习。</p></div><div class="card path-step"><em>STEP 03</em><h4>布置与批改作业</h4><p>安排课堂和课后作业，查看提交并完成批改。</p></div><div class="card path-step"><em>STEP 04</em><h4>整理学习反馈</h4><p>结合课堂表现与作业结果，做好后续辅导。</p></div></div></section>
    <section class="section grid work"><div class="card"><div class="section-title"><div><h3>我的班级</h3><p id="classHint">教师登录后查看负责的班级。</p></div></div><div class="list" id="classList"></div><a class="btn ghost" href="/classic">进入原教学系统查看详情</a></div><div class="card" id="guide"><div class="section-title"><div><h3>使用指引</h3><p>沿用现有账号，先识别身份，再进入对应工作台。</p></div></div><div class="list"><div class="list-item"><b>机构老师 / 管理员</b><span>晚托、周末课或假期班当前教学</span></div><div class="list-item"><b>学校教师 / 管理员</b><span>按学年、学期、年级、班级和学科教学</span></div><div class="list-item"><b>家长</b><span>查看已关联孩子的学习动态</span></div><div class="list-item"><b>学生</b><span>查看本人教学与作业</span></div></div><div class="hero-actions"><a class="btn primary" href="/v1">登录 / 进入 V1</a></div></div></section>
    <p class="footer">长缨辅学 · 小学托管、周末教学、寒暑假班与学校教学支持</p>
  </main>
  <nav class="bottom-nav" aria-label="移动端快捷入口"><a href="#services">服务范围</a><a href="#path">教学安排</a><a href="#guide">使用指引</a><a href="/v1">进入 V1</a></nav>
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
      if(error.status===403){loginAction.hidden=false;loginAction.textContent='进入教学系统查看';}
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
      if(list.length===0){setText('classHint','尚未分配班级');setText('classList','暂无班级，请联系管理员分配或进入教学系统创建。');setText('kpi-classes','0');setText('classes-live','已读取教师班级');return;}
      setText('classHint','已读取教师班级列表，点击教学系统继续操作。');
      setText('kpi-classes',String(list.length));setText('classes-live','已读取教师班级');
      const html=list.slice(0,5).map((c,i)=>`<div class="list-item"><b>${c.name||c.title||('班级 '+(i+1))}</b><span>${c.grade||c.subject||c.status||'进入教学系统'}</span></div>`).join('');
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
        setText('heroText','已登录。请进入教学系统使用账号对应的课程、作业与学习反馈功能。');
        if(session.role==='admin'){
          setText('classHint','班级详情请在教学系统查看');
          try{applyOverview(await getJSON('/admin/overview'));}
          catch(error){
            for(const name of ['students','classes','questions','assignments'])setText(name+'-live',failureMessage(error));
            showFailure(error);
          }
        }else if(session.role==='teacher'){
          for(const name of ['students','questions','assignments'])setText(name+'-live','请进入教学系统查看');
          try{applyClasses(await getJSON('/teacher/classes'));}
          catch(error){setText('classHint',failureMessage(error));setText('classes-live',failureMessage(error));showFailure(error);}
        }else{
          for(const name of ['students','classes','questions','assignments'])setText(name+'-live','请进入教学系统查看学习内容');
          setText('classHint','班级与学习内容请进入教学系统查看');
        }
      }catch(error){
        const message=failureMessage(error);
        setText('sessionTitle',message);
        setText('sessionDetail',error.status===401?'请进入教学系统重新登录。':error.status===403?'请进入教学系统查看账号提示。':'网络或服务暂时不可用，恢复后点击重试。');
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

