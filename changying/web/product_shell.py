"""Focused teacher workbench for 长缨辅学.

The shell keeps the complete legacy system at /classic and provides a mobile-first,
read-only entry for elementary tutoring. It deliberately excludes unrelated AI,
training, commercial and cross-business narratives from the tutoring product.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

PRODUCT_SHELL_MARKER = "changying_product_shell_v1_3"


def teacher_workbench_html() -> str:
    """Return the focused 长缨辅学 teacher workbench."""
    return """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>长缨辅学｜实践工作台 V1.3</title>
<style>
:root{--b:#2038b8;--g:#0c9b72;--i:#172033;--m:#68738a;--l:#e7eaf2;--s:#f5f7fc}*{box-sizing:border-box}body{margin:0;background:#f4f6fb;color:var(--i);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif}.page{max-width:1080px;margin:auto;padding:20px 16px 90px}.top,.row{display:flex;align-items:center;justify-content:space-between;gap:12px}.brand{font-size:22px;font-weight:900}.muted{color:var(--m)}.btn{display:inline-block;padding:11px 15px;border-radius:13px;background:#fff;border:1px solid var(--l);text-decoration:none;color:inherit;font-weight:800}.primary{background:var(--b);color:#fff;border-color:var(--b)}.hero,.card{background:#fff;border:1px solid var(--l);border-radius:22px;padding:20px;box-shadow:0 12px 35px rgba(25,35,70,.07)}.hero{margin:18px 0}.hero h1{font-size:clamp(30px,6vw,48px);margin:6px 0 10px}.hero p{line-height:1.7}.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:14px 0}.card h3{margin:0 0 8px}.kpi{font-size:30px;font-weight:900}.section{margin-top:22px}.steps{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}.step b{color:var(--b)}.list{display:grid;gap:10px}.item{padding:13px;border-radius:14px;background:var(--s);border:1px solid var(--l)}.status{font-size:13px;color:var(--g);font-weight:800}.bottom{display:none}@media(max-width:720px){.grid,.steps{grid-template-columns:1fr 1fr}.top{align-items:flex-start}.bottom{display:grid;position:fixed;left:10px;right:10px;bottom:10px;grid-template-columns:repeat(3,1fr);gap:8px;background:#fff;padding:8px;border:1px solid var(--l);border-radius:18px}.bottom a{text-align:center;padding:10px;text-decoration:none;color:inherit;font-weight:800}}@media(max-width:430px){.grid,.steps{grid-template-columns:1fr}}
</style>
</head><body><main class="page">
<header class="top"><div><div class="brand">长缨辅学</div><div class="muted">实践工作台 · V1.3</div></div><a class="btn" href="/classic">完整系统</a></header>
<section class="hero"><div class="status" id="sessionTitle">正在检查登录状态</div><h1>围绕学生连续发展，安排今天的教学。</h1><p id="heroText" class="muted">长缨辅学当前聚焦小学阶段晚托、周末课、寒暑假班及可能承担的学校教学任务。工作台把当前教学、学生学习动态、历史记录和年级衔接放在同一条教师使用路径中。</p><p><a class="btn primary" href="/classic" id="loginAction">进入完整系统</a> <button class="btn" id="retryStatus" type="button" hidden>重试</button></p></section>
<section class="grid" aria-label="教学概览"><div class="card"><div class="kpi" id="kpi-students">—</div><div>学生</div><div class="status" id="students-live">等待读取</div></div><div class="card"><div class="kpi" id="kpi-classes">—</div><div>班级 / 课程</div><div class="status" id="classes-live">等待读取</div></div><div class="card"><div class="kpi" id="kpi-questions">—</div><div>题库</div><div class="status" id="questions-live">等待读取</div></div><div class="card"><div class="kpi" id="kpi-assignments">—</div><div>作业</div><div class="status" id="assignments-live">等待读取</div></div></section>
<section class="section"><h2>今日上课路径</h2><div class="steps"><div class="card step"><b>STEP 01</b><h3>当前教学</h3><p class="muted">确认今天班级、课程与教学位置。</p></div><div class="card step"><b>STEP 02</b><h3>学生</h3><p class="muted">进入学生连续记录，而不是只看一次成绩。</p></div><div class="card step"><b>STEP 03</b><h3>学习动态</h3><p class="muted">查看作业、错题、测验、薄弱点和下一步教学。</p></div><div class="card step"><b>STEP 04</b><h3>历史与衔接</h3><p class="muted">连接往期教学、学期假期、年级与升学衔接。</p></div></div></section>
<section class="section"><div class="card"><h2>我的班级</h2><p class="muted" id="classHint">登录教师账号后读取当前负责班级。</p><div class="list" id="classList"><div class="item">进入完整系统后查看</div></div></div></section>
<section class="section"><div class="card"><h2>运营体检</h2><div class="list"><div class="item">教学范围：小学晚托、周末课、寒暑假班与学校教学任务</div><div class="item">学生记录：跨学期、假期、年级保持连续</div><div class="item">数据策略：本工作台只读现有接口，不直接修改生产数据</div><div class="item">完整业务：保留在 /classic</div></div></div></section>
<section class="section"><div class="card"><h2>首次使用建议</h2><p class="muted">登录 → 工作台 → 当前教学 → 学生 → 学习动态 → 往期教学/历史 → 年级/升学衔接。</p></div></section>
</main><nav class="bottom" aria-label="移动端快捷入口"><a href="/">工作台</a><a href="#classList">学生</a><a href="/classic">完整系统</a></nav>
<script>
let headers={};let loading=false;const retryButton=document.getElementById('retryStatus');const loginAction=document.getElementById('loginAction');
const setText=(id,text)=>{const el=document.getElementById(id);if(el)el.textContent=text};const fmt=n=>Number.isFinite(Number(n))?String(n):'—';
async function getJSON(url){const c=new AbortController(),t=setTimeout(()=>c.abort(),10000);try{const r=await fetch(url,{headers,cache:'no-store',signal:c.signal});if(!r.ok){const e=new Error('Request failed');e.status=r.status;throw e}return await r.json()}finally{clearTimeout(t)}}
function applyOverview(d){const values={students:d.students??d.studentCount??d.totalStudents??d.user_count??d.users,classes:d.classes??d.classCount??d.totalClasses??d.courses,questions:d.questions??d.questionCount??d.totalQuestions??d.items,assignments:d.assignments??d.assignmentCount??d.homework??d.tasks};for(const [k,v] of Object.entries(values)){setText('kpi-'+k,fmt(v));if(v!==undefined)setText(k+'-live','已读取')}}
function applyClasses(data){const list=Array.isArray(data)?data:(data.classes||data.data||data.items||[]);setText('kpi-classes',String(list.length));setText('classes-live','已读取教师班级');setText('classHint',list.length?'当前负责班级':'尚未分配班级');document.getElementById('classList').innerHTML=list.length?list.slice(0,5).map((c,i)=>`<div class="item">${c.name||c.title||('班级 '+(i+1))}</div>`).join(''):'<div class="item">暂无班级</div>'}
async function boot(){if(loading)return;loading=true;retryButton.hidden=true;try{const token=localStorage.getItem('v717Token')||localStorage.getItem('v6Token')||'';const remembered=localStorage.getItem('v717Remember')==='1';headers=token?{'Authorization':'Bearer '+token}:{};if(!token){setText('sessionTitle','尚未登录');return}const s=await getJSON('/session');setText('sessionTitle',`已登录：${s.name||s.role||'当前账号'} · ${remembered?'已记住登录':'当前会话'}`);if(s.role==='admin')applyOverview(await getJSON('/admin/overview'));else if(s.role==='teacher')applyClasses(await getJSON('/teacher/classes'))}catch(e){setText('sessionTitle',e.status===401?'登录已过期':'暂时无法读取，请重试');retryButton.hidden=false}finally{loading=false}}
retryButton.addEventListener('click',boot);boot();
</script></body></html>"""


def install_product_shell(app: FastAPI) -> None:
    """Install the focused root page while preserving the legacy page at /classic."""
    if getattr(app.state, "product_shell_installed", False):
        return
    legacy_root = None
    for route in list(app.router.routes):
        if getattr(route, "path", None) == "/" and "GET" in getattr(route, "methods", set()):
            legacy_root = route
            break
    if legacy_root is not None and not any(getattr(r, "path", None) == "/classic" for r in app.router.routes):
        app.add_api_route("/classic", legacy_root.endpoint, methods=["GET"], response_class=getattr(legacy_root, "response_class", HTMLResponse), include_in_schema=False)
    app.router.routes = [route for route in app.router.routes if not (getattr(route, "path", None) == "/" and "GET" in getattr(route, "methods", set()))]
    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    def changying_product_home():
        return HTMLResponse(teacher_workbench_html())
    app.state.product_shell_installed = True


__all__ = ["PRODUCT_SHELL_MARKER", "install_product_shell", "teacher_workbench_html"]
