"""Native V1 "全部功能" hub.

``/v1/tool`` used to redirect straight into the Classic document, so every click
on "全部功能" (and every refresh) landed on the old page. The hub itself is now
rendered by V1; only a concrete function (``/v1/tool?page=<id>``) still opens
Classic, because those workflows have not been rebuilt natively yet.
"""
from __future__ import annotations

from changying.web.design_system import apply_surface

import json

from changying.web.v1_ribbon_banner import BRAND_FONT_B64, RIBBON_SVG

V1_TOOL_HUB_MARKER = "changying_v1_tool_hub_v1"

TOOL_HUB_MENUS: dict[str, list[tuple[str, str, str]]] = {
    "teacher": [
        ("classes", "班级学生", "建班、学生账号、家长关联、调班与毕业归档"),
        ("classPoints", "课堂积分", "课堂表现、积分规则、小组、成长看板与奖励"),
        ("ai", "AI 助手", "AI 出题、教案、批改辅助与个性化巩固"),
        ("teaching", "定制教学", "教学设置、期中期末题库、学生同步课堂（周末课请用“周末课”）"),
        ("resources", "教材教案", "教材、教案、课件与练习资料库"),
        ("catalog", "教材题库", "题库维护、知识点与题目管理"),
        ("papers", "组卷作业", "组卷、布置作业、检查提交与成绩导出"),
        ("analytics", "学情分析", "班级完成率、成绩、薄弱知识点与学生提醒"),
        ("audit", "操作记录", "查看本人教学操作审计记录"),
        ("leaderboard", "排行榜", "课堂积分与班级表现排行"),
        ("account", "我的", "账号、安全、通知与个人数据功能"),
    ],
    "student": [
        ("syncLearning", "同步课堂", "查看课堂学习与互动内容"),
        ("rewards", "积分奖励", "查看积分变化与奖励记录"),
        ("assignments", "我的作业", "查看并完成待办作业"),
        ("wrongbook", "我的错题", "回看错题并继续巩固"),
        ("practice", "自主练习", "练习、针对性训练与错题巩固"),
        ("progress", "我的学情", "查看学习进度与掌握情况"),
        ("leaderboard", "班级排行", "课堂积分与班级表现排行"),
        ("account", "我的", "账号、安全与个人数据"),
    ],
    "parent": [
        ("childLearning", "孩子课程", "查看孩子当前课程与学习安排"),
        ("childRewards", "课堂表现", "查看课堂表现与积分记录"),
        ("childProgress", "孩子学情", "查看成绩、知识点与学习进展"),
        ("childAssignments", "孩子作业", "查看作业进度、完成与逾期状态"),
        ("account", "我的", "查看家长账号与关联信息"),
    ],
    "admin": [
        ("admin", "平台总览", "学校教学与账号数据概览"),
        ("subscription", "套餐授权", "查看当前学校功能授权与容量"),
        ("users", "账号管理", "教师、学生、家长账号与学生恢复"),
        ("pointsAdmin", "积分奖励", "全校积分规则、奖励与自动奖励"),
        ("ai", "AI 设置", "学校级 AI 配置、安全边界与教学助手"),
        ("teaching", "定制教学", "教学方案、课时与分层教学"),
        ("resources", "教材教案", "学校资料库与官方教材导航"),
        ("imports", "批量导入", "批量导入账号、题目与教学数据"),
        ("catalog", "教材题库", "教材、知识点与题库管理"),
        ("adminAudit", "全校审计", "查看全校关键教学与账号操作记录"),
        ("system", "系统设置", "学校级系统维护与安全设置"),
    ],
}

_HUB_TEMPLATE = r'''<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#173c78">
<title>全部功能 · 长缨辅学</title>
<style>
@font-face{font-family:CyBrand;src:url(data:font/woff2;base64,__BRAND_FONT_B64__) format('woff2');font-display:swap}
:root{--navy:#a8101c;--ink:#172033;--muted:#7a625c;--line:#eadfd8;--soft:#f8f3ee}
*{box-sizing:border-box}html,body{margin:0;min-height:100%;background:var(--soft);color:var(--ink);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;-webkit-text-size-adjust:100%}a{text-decoration:none;color:inherit}
.top{position:fixed;left:0;right:0;top:0;height:101px;display:flex;align-items:center;justify-content:space-between;gap:12px;padding:0 clamp(14px,4vw,40px);overflow:hidden;background:radial-gradient(110% 240% at 6% -50%,rgba(255,222,160,.6),transparent 56%),linear-gradient(100deg,#a8101c 0%,#d9352a 36%,#ee7a38 64%,#c92a2c 100%);box-shadow:0 8px 22px rgba(168,16,28,.28);z-index:5}
.cy-ribbon{position:absolute;inset:0;width:100%;height:100%;pointer-events:none}.top>:not(.cy-ribbon){position:relative;z-index:1}.brand{color:#fff;font-family:CyBrand,'STXingkai','Xingkai SC','Kaiti SC',KaiTi,serif;font-size:52px;letter-spacing:.14em;text-shadow:0 2px 8px rgba(100,0,10,.4)}
.chip{font-size:12px;color:#fff;background:rgba(255,255,255,.2);border:1px solid rgba(255,255,255,.45);border-radius:999px;padding:8px 10px;max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
@media(max-width:720px){.top{height:78px}.brand{font-size:36px}}
main{max-width:1080px;margin:0 auto;padding:125px clamp(16px,4vw,40px) 60px}h1{margin:0 0 6px;font-size:22px}.lead{margin:0 0 18px;color:var(--muted);font-size:13px;line-height:1.6}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:12px}
.tool small{display:block;margin-top:4px;color:var(--muted);font-weight:500;font-size:12px;line-height:1.4}.tool{display:block;width:100%;min-height:48px;text-align:left;border:1px solid var(--line);border-radius:16px;background:#fff;padding:16px 14px;font:inherit;font-weight:800;color:var(--ink);cursor:pointer;box-shadow:0 8px 30px rgba(23,60,120,.04)}.tool:active{background:#eaf1ff}
.notice{display:none;margin:0 0 14px;padding:10px 12px;border-radius:12px;background:#fff8e8;border:1px solid #f5d79a;color:#7a4a00;font-size:13px}.notice.show{display:block}
</style>
</head>
<body>
<header class="top">__RIBBON__<a class="brand" href="/v1/workspace">长缨辅学</a><span class="chip" id="identity">正在识别身份</span></header>
<main>
<h1>全部功能</h1>
<p class="lead">按当前身份选择功能；办理进度请看功能页中的待审核、已发布等提示。</p>
<div class="notice" id="notice" role="status"></div>
<div class="grid" id="grid"></div>
</main>
<script id="changying_v1_tool_hub_v1-script">
(()=>{
  const MENUS=__MENUS__;
  const TOKEN_KEY='v717Token';
  const token=()=>{const remember=localStorage.getItem('v717Remember')==='1';return (remember?localStorage.getItem(TOKEN_KEY):sessionStorage.getItem(TOKEN_KEY))||sessionStorage.getItem(TOKEN_KEY)||localStorage.getItem(TOKEN_KEY)||sessionStorage.getItem('v6Token')||localStorage.getItem('v6Token')||''};
  const grid=document.getElementById('grid'),notice=document.getElementById('notice'),identity=document.getElementById('identity');
  const say=t=>{notice.textContent=t;notice.classList.add('show')};
  async function openTool(page){
    const t=token();
    if(t&&t!=='demo'){try{const r=await fetch('/v1/auth-handoff',{method:'POST',headers:{Authorization:'Bearer '+t},cache:'no-store',credentials:'same-origin'});if(!r.ok){say('暂时无法打开功能，请重试；如果仍无法打开，请返回首页重新登录。');return}}catch{say('暂时无法打开功能，请重试；如果仍无法打开，请返回首页重新登录。');return}}
    location.href='/v1/tool?page='+encodeURIComponent(page);
  }
  async function start(){
    const t=token();let role='teacher';
    if(!t){identity.textContent='未登录';say('请先登录长缨辅学后再查看全部功能。');grid.innerHTML='<a class="tool" href="/v1">前往登录</a>';return}
    if(t==='demo'){identity.textContent='演示教师';location.replace('/v1/workspace?view=all');return}
    else{try{const r=await fetch('/session',{headers:{Authorization:'Bearer '+t},cache:'no-store'});if(!r.ok)throw 0;const s=await r.json();role=String(s.role||'teacher');identity.textContent=(s.name||'当前账号')+' · '+({teacher:'教师',student:'学生',parent:'家长',admin:'管理员'}[role]||role)}catch{identity.textContent='登录已失效';say('登录状态已失效，请重新登录。');grid.innerHTML='<a class="tool" href="/v1">前往登录</a>';return}}
    if(role==='teacher'){location.replace('/v1/workspace?view=all');return}
    const items=MENUS[role]||MENUS.teacher;
    grid.innerHTML=items.map(x=>'<button type="button" class="tool" data-page="'+x[0]+'">'+x[1]+'<small>'+x[2]+'</small></button>').join('');
    grid.querySelectorAll('[data-page]').forEach(b=>b.onclick=()=>openTool(b.dataset.page));
  }
  start();
})();
</script>
<!-- changying_v1_tool_hub_v1 -->
</body>
</html>'''


def tool_hub_html() -> str:
    return apply_surface(
        _HUB_TEMPLATE.replace("__MENUS__", json.dumps(TOOL_HUB_MENUS, ensure_ascii=False))
        .replace("__BRAND_FONT_B64__", BRAND_FONT_B64)
        .replace("__RIBBON__", RIBBON_SVG),
        "hub",
    )


def is_tool_hub_request(page: str | None) -> bool:
    """True for ``/v1/tool`` and ``/v1/tool?page=__hub__`` (no concrete function)."""
    return str(page or "").strip() in {"", "__hub__"}


__all__ = ["V1_TOOL_HUB_MARKER", "TOOL_HUB_MENUS", "is_tool_hub_request", "tool_hub_html"]
