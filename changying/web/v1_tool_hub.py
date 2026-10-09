"""Native V1 "全部功能" hub.

``/v1/tool`` used to redirect straight into the Classic document, so every click
on "全部功能" (and every refresh) landed on the old page. The hub itself is now
rendered by V1; only a concrete function (``/v1/tool?page=<id>``) still opens
Classic, because those workflows have not been rebuilt natively yet.
"""
from __future__ import annotations

import json

V1_TOOL_HUB_MARKER = "changying_v1_tool_hub_v1"

TOOL_HUB_MENUS: dict[str, list[tuple[str, str]]] = {
    "teacher": [("classes", "班级学生"), ("classPoints", "课堂积分"), ("ai", "AI 助手"), ("teaching", "定制教学"), ("resources", "教材教案"), ("catalog", "教材题库"), ("papers", "组卷作业"), ("analytics", "学情分析"), ("audit", "操作记录"), ("leaderboard", "排行榜"), ("account", "我的")],
    "student": [("syncLearning", "同步课堂"), ("rewards", "积分奖励"), ("assignments", "我的作业"), ("wrongbook", "我的错题"), ("practice", "自主练习"), ("progress", "我的学情"), ("leaderboard", "班级排行"), ("account", "我的")],
    "parent": [("childLearning", "孩子课程"), ("childRewards", "课堂表现"), ("childProgress", "孩子学情"), ("childAssignments", "孩子作业"), ("account", "我的")],
    "admin": [("admin", "平台总览"), ("subscription", "套餐授权"), ("users", "账号管理"), ("pointsAdmin", "积分奖励"), ("ai", "AI 设置"), ("teaching", "定制教学"), ("resources", "教材教案"), ("imports", "批量导入"), ("catalog", "教材题库"), ("adminAudit", "全校审计"), ("system", "系统设置")],
}

_HUB_TEMPLATE = r'''<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#173c78">
<title>全部功能 · 长缨辅学</title>
<style>
:root{--navy:#173c78;--ink:#172033;--muted:#667085;--line:#e4e9f2;--soft:#f3f6fb}
*{box-sizing:border-box}html,body{margin:0;min-height:100%;background:var(--soft);color:var(--ink);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;-webkit-text-size-adjust:100%}a{text-decoration:none;color:inherit}
.top{height:64px;display:flex;align-items:center;justify-content:space-between;gap:12px;padding:0 clamp(14px,4vw,40px);background:#fff;border-bottom:1px solid var(--line);position:sticky;top:0;z-index:5}
.brand{display:flex;align-items:center;gap:10px;font-weight:900}.mark{width:36px;height:36px;border-radius:12px;display:grid;place-items:center;background:var(--navy);color:#fff;font-size:19px}
.chip{font-size:12px;color:var(--navy);background:#edf3ff;border:1px solid #dbe7ff;border-radius:999px;padding:8px 10px;max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
main{max-width:1080px;margin:0 auto;padding:24px clamp(16px,4vw,40px) 60px}h1{margin:0 0 6px;font-size:22px}.lead{margin:0 0 18px;color:var(--muted);font-size:13px;line-height:1.6}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:12px}
.tool{display:block;width:100%;text-align:left;border:1px solid var(--line);border-radius:16px;background:#fff;padding:16px 14px;font:inherit;font-weight:800;color:var(--ink);cursor:pointer;box-shadow:0 8px 30px rgba(23,60,120,.04)}.tool:active{background:#eaf1ff}
.notice{display:none;margin:0 0 14px;padding:10px 12px;border-radius:12px;background:#fff8e8;border:1px solid #f5d79a;color:#7a4a00;font-size:13px}.notice.show{display:block}
</style>
</head>
<body>
<header class="top"><a class="brand" href="/v1/workspace"><span class="mark">长</span><span>长缨辅学</span></a><span class="chip" id="identity">正在识别身份</span></header>
<main>
<h1>全部功能</h1>
<p class="lead">按当前身份列出可用功能。点击后进入对应功能页。</p>
<div class="notice" id="notice"></div>
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
    if(t&&t!=='demo'){try{const r=await fetch('/v1/auth-handoff',{method:'POST',headers:{Authorization:'Bearer '+t},cache:'no-store',credentials:'same-origin'});if(!r.ok){say('登录状态同步失败，请重试');return}}catch{say('登录状态同步失败，请重试');return}}
    location.href='/v1/tool?page='+encodeURIComponent(page);
  }
  async function start(){
    const t=token();let role='teacher';
    if(!t){identity.textContent='未登录';say('请先登录长缨辅学后再查看全部功能。');grid.innerHTML='<a class="tool" href="/v1">前往登录</a>';return}
    if(t==='demo'){identity.textContent='演示教师'}
    else{try{const r=await fetch('/session',{headers:{Authorization:'Bearer '+t},cache:'no-store'});if(!r.ok)throw 0;const s=await r.json();role=String(s.role||'teacher');identity.textContent=(s.name||'当前账号')+' · '+({teacher:'教师',student:'学生',parent:'家长',admin:'管理员'}[role]||role)}catch{identity.textContent='登录已失效';say('登录状态已失效，请重新登录。');grid.innerHTML='<a class="tool" href="/v1">前往登录</a>';return}}
    const items=MENUS[role]||MENUS.teacher;
    grid.innerHTML=items.map(x=>'<button type="button" class="tool" data-page="'+x[0]+'">'+x[1]+'</button>').join('');
    grid.querySelectorAll('[data-page]').forEach(b=>b.onclick=()=>openTool(b.dataset.page));
  }
  start();
})();
</script>
<!-- changying_v1_tool_hub_v1 -->
</body>
</html>'''


def tool_hub_html() -> str:
    return _HUB_TEMPLATE.replace("__MENUS__", json.dumps(TOOL_HUB_MENUS, ensure_ascii=False))


def is_tool_hub_request(page: str | None) -> bool:
    """True for ``/v1/tool`` and ``/v1/tool?page=__hub__`` (no concrete function)."""
    return str(page or "").strip() in {"", "__hub__"}


__all__ = ["V1_TOOL_HUB_MARKER", "TOOL_HUB_MENUS", "is_tool_hub_request", "tool_hub_html"]
