"""Productized landing shell for 长缨辅学.

The first V1 UI step replaces the root page with a modern teacher workbench
while keeping the complete legacy monolith available at /classic.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

PRODUCT_SHELL_MARKER = "changying_product_shell_v1"


def teacher_workbench_html() -> str:
    """Return the first productized 长缨辅学 workbench page."""
    return """<!doctype html>
<html lang=\"zh-CN\">
<head>
  <meta charset=\"utf-8\">
  <meta name=\"viewport\" content=\"width=device-width,initial-scale=1,viewport-fit=cover\">
  <meta name=\"theme-color\" content=\"#3047ff\">
  <link rel=\"manifest\" href=\"/manifest.webmanifest\">
  <title>长缨辅学｜教师工作台</title>
  <style>
    :root{--brand:#3047ff;--ink:#172033;--muted:#68738a;--line:#e6eaf3;--surface:#fff;--green:#10a874;--orange:#f59e0b;--shadow:0 20px 55px rgba(25,40,90,.12);--radius:24px}
    *{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;min-height:100dvh;color:var(--ink);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;background:radial-gradient(circle at top left,rgba(48,71,255,.18),transparent 32rem),radial-gradient(circle at top right,rgba(16,168,116,.16),transparent 30rem),linear-gradient(180deg,#f7f9ff 0%,#eef3ff 44%,#f7f8fb 100%);-webkit-text-size-adjust:100%}a{color:inherit;text-decoration:none}
    .page{width:min(1180px,100%);margin:0 auto;padding:24px clamp(16px,3vw,34px) 42px}.topbar{display:flex;align-items:center;justify-content:space-between;gap:16px;margin-bottom:18px}.brand{display:flex;align-items:center;gap:12px}.logo{width:48px;height:48px;border-radius:16px;background:linear-gradient(145deg,#3047ff,#6b7cff);box-shadow:var(--shadow);display:grid;place-items:center;color:#fff;font-size:24px;font-weight:900}.brand h1{font-size:22px;line-height:1.1;margin:0;letter-spacing:.02em}.brand small{display:block;color:var(--muted);margin-top:4px}.actions{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
    .pill{display:inline-flex;align-items:center;gap:7px;border:1px solid rgba(48,71,255,.14);background:rgba(255,255,255,.76);backdrop-filter:blur(10px);border-radius:999px;padding:10px 14px;color:var(--muted);font-size:13px}.btn{display:inline-flex;align-items:center;justify-content:center;gap:8px;border-radius:15px;padding:12px 16px;font-weight:800;transition:.18s ease;background:#fff;border:1px solid var(--line)}.btn:hover{transform:translateY(-1px);box-shadow:0 12px 30px rgba(25,40,90,.12)}.btn.primary{background:var(--brand);border-color:var(--brand);color:#fff}
    .hero{display:grid;grid-template-columns:1.35fr .65fr;gap:18px;align-items:stretch;margin:18px 0}.panel{background:rgba(255,255,255,.86);border:1px solid rgba(229,234,246,.9);border-radius:var(--radius);box-shadow:var(--shadow);backdrop-filter:blur(14px)}.welcome{padding:30px;position:relative;overflow:hidden}.welcome:after{content:"";position:absolute;inset:auto -90px -110px auto;width:280px;height:280px;border-radius:50%;background:linear-gradient(135deg,rgba(48,71,255,.18),rgba(16,168,116,.18))}.eyebrow{display:inline-flex;gap:8px;align-items:center;font-size:13px;font-weight:900;color:var(--brand);background:#eef2ff;border:1px solid #dbe3ff;border-radius:999px;padding:8px 12px;margin-bottom:16px}.welcome h2{font-size:clamp(30px,5vw,56px);line-height:1.02;margin:0 0 12px;letter-spacing:-.04em}.welcome p{font-size:17px;color:var(--muted);line-height:1.8;margin:0;max-width:720px}.hero-actions{display:flex;gap:12px;flex-wrap:wrap;margin-top:24px;position:relative;z-index:1}
    .today{padding:22px;display:flex;flex-direction:column;gap:14px}.today h3,.section-title h3{margin:0;font-size:18px}.todo{display:flex;align-items:center;gap:12px;padding:14px;border-radius:18px;background:#f7f9ff;border:1px solid #e9edfb}.todo b{display:block;margin-bottom:3px}.todo span{font-size:13px;color:var(--muted)}.dot{width:12px;height:12px;border-radius:50%;background:var(--brand);box-shadow:0 0 0 6px rgba(48,71,255,.12)}.dot.green{background:var(--green);box-shadow:0 0 0 6px rgba(16,168,116,.12)}.dot.orange{background:var(--orange);box-shadow:0 0 0 6px rgba(245,158,11,.14)}
    .grid{display:grid;gap:16px}.kpis{grid-template-columns:repeat(4,1fr);margin:18px 0}.card{padding:20px;background:var(--surface);border:1px solid var(--line);border-radius:22px;box-shadow:0 14px 34px rgba(25,40,90,.08)}.kpi .icon{width:42px;height:42px;border-radius:16px;display:grid;place-items:center;background:#eef2ff;color:var(--brand);font-size:22px;margin-bottom:16px}.kpi strong{font-size:30px;display:block;letter-spacing:-.04em}.kpi span{color:var(--muted);font-size:14px}
    .section{margin-top:20px}.section-title{display:flex;justify-content:space-between;align-items:end;gap:12px;margin:0 0 14px}.section-title p{margin:4px 0 0;color:var(--muted);font-size:14px}.quick{grid-template-columns:repeat(3,1fr)}.quick-card{display:flex;gap:16px;align-items:flex-start;min-height:132px;position:relative;overflow:hidden}.quick-card:after{content:"→";position:absolute;right:20px;bottom:16px;color:#b8c1d6;font-weight:900;font-size:22px}.quick-card .icon{flex:0 0 48px;width:48px;height:48px;border-radius:18px;display:grid;place-items:center;background:#f1f5ff;font-size:24px}.quick-card h4{margin:2px 0 8px;font-size:17px}.quick-card p{margin:0;color:var(--muted);line-height:1.65;font-size:14px}
    .flow{grid-template-columns:1.1fr .9fr;margin-top:16px}.flow-list{display:grid;gap:12px}.flow-item{display:flex;gap:12px;align-items:flex-start;padding:15px;border-radius:18px;background:#f8faff;border:1px solid #e8edfb}.num{width:30px;height:30px;border-radius:11px;background:var(--brand);color:#fff;display:grid;place-items:center;font-weight:900;font-size:13px;flex:none}.flow-item b{display:block;margin-bottom:4px}.flow-item span{color:var(--muted);font-size:14px;line-height:1.6}.brand-card{background:linear-gradient(145deg,#172033,#3047ff);color:#fff;position:relative;overflow:hidden}.brand-card p{color:rgba(255,255,255,.76);line-height:1.75}.brand-card:after{content:"长缨";position:absolute;right:-18px;bottom:-24px;font-size:86px;font-weight:900;letter-spacing:-.08em;color:rgba(255,255,255,.08)}.footer{color:var(--muted);font-size:13px;text-align:center;margin-top:28px}
    @media(max-width:900px){.hero,.flow{grid-template-columns:1fr}.kpis{grid-template-columns:repeat(2,1fr)}.quick{grid-template-columns:1fr 1fr}}@media(max-width:640px){.page{padding-top:18px}.topbar{align-items:flex-start}.actions{justify-content:flex-start}.pill.hide-mobile{display:none}.welcome{padding:24px 20px}.kpis,.quick{grid-template-columns:1fr}.hero-actions .btn{width:100%}.brand h1{font-size:20px}}
  </style>
</head>
<body>
  <main class=\"page\">
    <header class=\"topbar\"><div class=\"brand\"><div class=\"logo\">长</div><div><h1>长缨辅学</h1><small>教师工作台 · 产品化预览版</small></div></div><div class=\"actions\"><span class=\"pill hide-mobile\" id=\"clock\">今天</span><a class=\"btn\" href=\"/classic\">进入完整系统</a><a class=\"btn primary\" href=\"/classic\">开始上课</a></div></header>
    <section class=\"hero\"><div class=\"panel welcome\"><div class=\"eyebrow\">长缨辅学 V1.0 · 正式投入使用前 UI 升级</div><h2>把今天的课、学生、作业和组卷集中到一个工作台。</h2><p>新版首页先解决老师每天打开网站的第一件事：快速进入班级、布置作业、查看成绩、生成练习。完整旧版功能仍保留在「完整系统」中，保证现在就能使用。</p><div class=\"hero-actions\"><a class=\"btn primary\" href=\"/classic\">进入现有完整功能</a><a class=\"btn\" href=\"#quick\">查看快捷入口</a></div></div><aside class=\"panel today\"><h3>今日提醒</h3><div class=\"todo\"><i class=\"dot\"></i><div><b>先进入完整系统</b><span>继续使用现有学生、题库、作业与统计功能</span></div></div><div class=\"todo\"><i class=\"dot green\"></i><div><b>UI 正在产品化</b><span>后续页面会逐步统一为同一套长缨风格</span></div></div><div class=\"todo\"><i class=\"dot orange\"></i><div><b>保留原数据</b><span>本次只改界面入口，不改生产数据库</span></div></div></aside></section>
    <section class=\"grid kpis\" aria-label=\"运营概览\"><div class=\"card kpi\"><div class=\"icon\">📚</div><strong>课程</strong><span>晚托、周末课、寒暑假班</span></div><div class=\"card kpi\"><div class=\"icon\">👨‍🎓</div><strong>学生</strong><span>学生档案与学习跟进</span></div><div class=\"card kpi\"><div class=\"icon\">📝</div><strong>作业</strong><span>布置、提交、批改、反馈</span></div><div class=\"card kpi\"><div class=\"icon\">📊</div><strong>数据</strong><span>成绩统计与成长分析</span></div></section>
    <section class=\"section\" id=\"quick\"><div class=\"section-title\"><div><h3>高频功能入口</h3><p>先把老师最常用的入口集中展示，减少寻找菜单的时间。</p></div><a class=\"pill\" href=\"/classic\">完整系统 →</a></div><div class=\"grid quick\"><a class=\"card quick-card\" href=\"/classic\"><div class=\"icon\">👨‍🎓</div><div><h4>学生管理</h4><p>查看学生、家长、班级、学习状态与跟进记录。</p></div></a><a class=\"card quick-card\" href=\"/classic\"><div class=\"icon\">🏫</div><div><h4>班级与课程</h4><p>管理晚托、周末课、寒暑假班与日常教学安排。</p></div></a><a class=\"card quick-card\" href=\"/classic\"><div class=\"icon\">📖</div><div><h4>数学题库</h4><p>围绕人教版五年级、单元、知识点和难度组织题目。</p></div></a><a class=\"card quick-card\" href=\"/classic\"><div class=\"icon\">📄</div><div><h4>自动组卷</h4><p>快速生成课后练习、单元测验与分层训练卷。</p></div></a><a class=\"card quick-card\" href=\"/classic\"><div class=\"icon\">📝</div><div><h4>今日作业</h4><p>布置、查看提交、批改与回收学生完成情况。</p></div></a><a class=\"card quick-card\" href=\"/classic\"><div class=\"icon\">📊</div><div><h4>成绩分析</h4><p>快速看到班级表现、错题集中区和需要重点关注的学生。</p></div></a></div></section>
    <section class=\"section grid flow\"><div class=\"card\"><div class=\"section-title\"><div><h3>建议使用流程</h3><p>把线下补习班的真实动作搬到线上。</p></div></div><div class=\"flow-list\"><div class=\"flow-item\"><span class=\"num\">01</span><div><b>课前</b><span>进入班级，查看学生情况，选择今日训练目标。</span></div></div><div class=\"flow-item\"><span class=\"num\">02</span><div><b>课中</b><span>使用题库和组卷快速形成分层练习。</span></div></div><div class=\"flow-item\"><span class=\"num\">03</span><div><b>课后</b><span>布置作业，查看完成情况，沉淀错题与成绩数据。</span></div></div></div></div><div class=\"card brand-card\"><h3>长缨辅学，不只是题库。</h3><p>它应该成为线下教学、家长沟通、学生成长记录和未来 AI 辅学的统一入口。新版 UI 会优先围绕“老师每天真正要做什么”来完善。</p><a class=\"btn\" href=\"/classic\">打开完整系统</a></div></section>
    <p class=\"footer\">长缨辅学 V1.0 UI shell · 当前完整业务功能保留在 /classic</p>
  </main>
  <script>const now=new Date(),clock=document.getElementById('clock');if(clock){clock.textContent=now.toLocaleDateString('zh-CN',{weekday:'long',year:'numeric',month:'long',day:'numeric'})}</script>
</body>
</html>"""


def _modern_root() -> HTMLResponse:
    return HTMLResponse(teacher_workbench_html(), headers={"Cache-Control": "no-store"})


def install_product_shell(app: FastAPI, *, legacy_path: str = "/classic") -> None:
    """Install the modern root page while preserving the legacy UI."""
    if getattr(app.state, PRODUCT_SHELL_MARKER, False):
        return

    legacy_endpoint = None
    for route in app.router.routes:
        if getattr(route, "path", None) == "/" and "GET" in getattr(route, "methods", set()):
            legacy_endpoint = getattr(route, "endpoint", None)
            break

    if legacy_endpoint is not None:
        has_legacy_alias = any(
            getattr(route, "path", None) == legacy_path and "GET" in getattr(route, "methods", set())
            for route in app.router.routes
        )
        if not has_legacy_alias:
            app.add_api_route(legacy_path, legacy_endpoint, methods=["GET"], include_in_schema=False)

    app.add_api_route("/", _modern_root, methods=["GET"], include_in_schema=False)
    modern_route = app.router.routes.pop()
    insert_at = 0
    for index, route in enumerate(app.router.routes):
        if getattr(route, "path", None) == "/" and "GET" in getattr(route, "methods", set()):
            insert_at = index
            break
    app.router.routes.insert(insert_at, modern_route)
    setattr(app.state, PRODUCT_SHELL_MARKER, True)


__all__ = ["install_product_shell", "teacher_workbench_html"]
