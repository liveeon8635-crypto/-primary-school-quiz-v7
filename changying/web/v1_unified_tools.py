"""Unified V1 shell for mature Classic capabilities.

The existing Classic monolith still owns a number of proven teaching workflows.
This module keeps those workflows intact but opens them inside a stable V1 frame
so daily acceptance happens on one product surface. No database, auth,
permission, or write semantics change.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from changying.web import v1 as v1_module

V1_UNIFIED_TOOLS_MARKER = "changying_v1_unified_tools_v1"
V1_UNIFIED_TOOL_PATH = "/v1/tool"

_TOOL_HTML = r'''<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
  <meta name="theme-color" content="#173c78">
  <title>长缨辅学 · 功能工作区</title>
  <style>
    :root{--navy:#173c78;--ink:#172033;--muted:#667085;--line:#e4e9f2;--soft:#f3f6fb}
    *{box-sizing:border-box}html,body{margin:0;min-height:100%;background:var(--soft);color:var(--ink);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;-webkit-text-size-adjust:100%}a{text-decoration:none;color:inherit}button,select{font:inherit}
    .top{height:68px;display:flex;align-items:center;justify-content:space-between;gap:12px;padding:0 clamp(14px,4vw,40px);background:#fff;border-bottom:1px solid var(--line);position:sticky;top:0;z-index:30}.brand{display:flex;align-items:center;gap:10px;font-weight:900}.mark{width:38px;height:38px;border-radius:13px;display:grid;place-items:center;background:var(--navy);color:#fff;font-size:20px}.brand small{display:block;color:var(--muted);font-size:11px;font-weight:600;margin-top:2px}.top-actions{display:flex;align-items:center;gap:8px}.chip{font-size:12px;color:var(--navy);background:#edf3ff;border:1px solid #dbe7ff;border-radius:999px;padding:8px 10px;max-width:190px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.back{border:1px solid var(--line);border-radius:11px;background:#fff;padding:9px 12px;font-weight:800;color:var(--ink)}
    .bar{display:grid;grid-template-columns:minmax(0,1fr) minmax(190px,320px);gap:12px;align-items:center;padding:12px clamp(14px,3vw,30px);background:#fff;border-bottom:1px solid var(--line)}.tool-title b{display:block;font-size:18px}.tool-title small{display:block;color:var(--muted);margin-top:3px;line-height:1.45}.picker{width:100%;border:1px solid #d5deec;border-radius:12px;background:#fff;padding:10px 12px;color:var(--ink)}
    .frame-wrap{position:relative;height:calc(100dvh - 125px);min-height:420px;background:#fff}.frame{display:block;width:100%;height:100%;border:0;background:#fff}.loading{position:absolute;inset:0;display:grid;place-items:center;background:#fff;z-index:3;color:var(--muted);font-size:14px}.loading.hidden{display:none}.notice{position:absolute;left:12px;right:12px;top:12px;z-index:4;padding:10px 12px;border-radius:12px;background:#fff8e8;border:1px solid #f5d79a;color:#7a4a00;font-size:12px;line-height:1.5;display:none}.notice.show{display:block}.bottom{display:none}
    @media(max-width:720px){.top{height:60px;padding:0 12px}.brand small{display:none}.chip{display:none}.back{padding:8px 10px}.bar{grid-template-columns:1fr;padding:10px 12px;gap:8px}.tool-title b{font-size:16px}.tool-title small{font-size:11px}.picker{font-size:14px;padding:9px 10px}.frame-wrap{height:calc(100dvh - 166px);padding-bottom:env(safe-area-inset-bottom)}.bottom{position:fixed;display:grid;grid-template-columns:repeat(5,1fr);left:8px;right:8px;bottom:max(8px,env(safe-area-inset-bottom));z-index:40;background:rgba(255,255,255,.97);border:1px solid var(--line);border-radius:18px;padding:5px 6px;box-shadow:0 14px 40px rgba(23,60,120,.16);backdrop-filter:blur(14px)}.bottom a{text-align:center;font-size:10px;color:#5f6b7e;padding:4px 1px;border-radius:10px}.bottom a span{display:block;font-size:16px;margin-bottom:1px}.bottom a.active{background:#eaf1ff;color:var(--navy);font-weight:800}}
  </style>
</head>
<body>
  <header class="top"><a class="brand" href="/v1/workspace"><span class="mark">长</span><span>长缨辅学<small>统一功能工作区</small></span></a><div class="top-actions"><span class="chip" id="identity">正在识别身份</span><a class="back" href="/v1/tool">全部功能</a></div></header>
  <section class="bar"><div class="tool-title"><b id="toolTitle">功能工作区</b><small>保留原有业务能力，但统一放进长缨辅学界面；这里暴露的问题再逐项原生化。</small></div><select class="picker" id="toolPicker" aria-label="切换功能"></select></section>
  <div class="frame-wrap"><div class="loading" id="loading">正在打开功能…</div><div class="notice" id="notice"></div><iframe class="frame" id="toolFrame" title="长缨辅学功能"></iframe></div>
  <nav class="bottom"><a href="/v1/workspace"><span>▦</span>当前教学</a><a href="/v1/student"><span>◉</span>学生</a><a href="/v1/history"><span>◷</span>往期教学</a><a href="/v1/transition"><span>↗</span>升学衔接</a><a class="active" href="/v1/tool"><span>⌘</span>全部功能</a></nav>
<script>
(()=>{
  const TOKEN_KEY='v717Token';
  const token=()=>localStorage.getItem(TOKEN_KEY)||localStorage.getItem('v6Token')||'';
  const menus={
    teacher:[['classes','班级学生'],['classPoints','课堂积分'],['ai','AI 助手'],['teaching','定制教学'],['resources','教材教案'],['catalog','教材题库'],['papers','组卷作业'],['analytics','学情分析'],['audit','操作记录'],['leaderboard','排行榜'],['account','我的']],
    student:[['syncLearning','同步课堂'],['rewards','积分奖励'],['assignments','我的作业'],['wrongbook','我的错题'],['practice','自主练习'],['progress','我的学情'],['leaderboard','班级排行'],['account','我的']],
    parent:[['childLearning','孩子课程'],['childRewards','课堂表现'],['childProgress','孩子学情'],['childAssignments','孩子作业'],['account','我的']],
    admin:[['admin','平台总览'],['subscription','套餐授权'],['users','账号管理'],['pointsAdmin','积分奖励'],['ai','AI 设置'],['teaching','定制教学'],['resources','教材教案'],['imports','批量导入'],['catalog','教材题库'],['adminAudit','全校审计'],['system','系统设置']]
  };
  const params=new URLSearchParams(location.search),requested=params.get('page')||'';
  const picker=document.getElementById('toolPicker'),title=document.getElementById('toolTitle'),frame=document.getElementById('toolFrame'),loading=document.getElementById('loading'),identity=document.getElementById('identity'),notice=document.getElementById('notice');
  let role='teacher',items=menus.teacher;
  function find(page){return items.find(x=>x[0]===page)||items[0]}
  function classicUrl(page){return '/classic?legacy=1&embedded=1&from=v1&page='+encodeURIComponent(page)}
  function embeddedPolish(doc){
    if(!doc||doc.getElementById('cy-v1-embedded-style'))return;
    const style=doc.createElement('style');style.id='cy-v1-embedded-style';style.textContent=`
      #changying_classic_ui_v2-ribbon,#changying_classic_ui_v2-workflow,.cy-classic-ribbon,.cy-workflow-panel{display:none!important}
      .sidebar,.mobile-header,.bottom-nav{display:none!important}
      .shell{display:block!important;min-height:100%!important}.main{padding:14px!important;min-height:100%!important}
      body{background:#f3f6fb!important}.page-head{margin-top:0!important}.network-banner{top:8px!important}
      @media(max-width:650px){.main{padding:12px 10px 28px!important}.card{border-radius:16px!important}.page-head h1{font-size:22px!important}}
    `;doc.head.appendChild(style);
  }
  function open(page,replace=true){
    const item=find(page);page=item[0];title.textContent=item[1];picker.value=page;loading.classList.remove('hidden');notice.classList.remove('show');frame.src=classicUrl(page);
    const u=new URL(location.href);u.searchParams.set('page',page);if(replace)history.replaceState(null,'',u.pathname+u.search);
  }
  frame.addEventListener('load',()=>{
    try{
      const doc=frame.contentDocument;embeddedPolish(doc);
      const continueBtn=doc?.getElementById('continueSessionBtn');
      if(continueBtn&&!continueBtn.classList.contains('hidden')){continueBtn.click();setTimeout(()=>embeddedPolish(frame.contentDocument),250)}
      setTimeout(()=>embeddedPolish(frame.contentDocument),700);
    }catch{}
    loading.classList.add('hidden');
  });
  picker.onchange=()=>open(picker.value,false);
  async function start(){
    const t=token();
    if(t&&t!=='demo'){
      try{const r=await fetch('/session',{headers:{Authorization:'Bearer '+t},cache:'no-store'});if(r.ok){const s=await r.json();role=String(s.role||'teacher');identity.textContent=(s.name||'当前账号')+' · '+({teacher:'教师',student:'学生',parent:'家长',admin:'管理员'}[role]||role)}}catch{}
    }else if(t==='demo'){identity.textContent='演示教师';role='teacher'}
    items=menus[role]||menus.teacher;
    picker.innerHTML=items.map(x=>`<option value="${x[0]}">${x[1]}</option>`).join('');
    const allowed=items.some(x=>x[0]===requested);if(requested&&!allowed){notice.textContent='当前账号没有该功能权限，已返回可用功能。';notice.classList.add('show')}
    open(allowed?requested:items[0][0]);
  }
  start();
})();
</script>
</body>
</html>'''


def unified_tool_html() -> str:
    return _TOOL_HTML


def install_v1_unified_tool_route(app: FastAPI) -> None:
    if getattr(app.state, "v1_unified_tool_route_installed", False):
        return

    @app.get(V1_UNIFIED_TOOL_PATH, include_in_schema=False)
    def v1_unified_tool():
        return HTMLResponse(
            unified_tool_html(),
            headers={
                "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                "X-Changying-V1": V1_UNIFIED_TOOLS_MARKER,
            },
        )

    app.state.v1_unified_tool_route_installed = True


def patch_v1_unified_tools(html: str) -> str:
    if V1_UNIFIED_TOOLS_MARKER in html:
        return html
    html = html.replace(
        '<a href="/classic"><span>⌂</span>原教学系统</a>',
        '<a href="/v1/tool"><span>⌘</span>全部功能</a>',
    )
    html = html.replace(
        '<a href="/classic"><span>⌂</span>原系统</a>',
        '<a href="/v1/tool"><span>⌘</span>全部功能</a>',
    )
    snippet = r'''
<script id="changying_v1_unified_tools_v1-script">
(()=>{
  if(window.__cyV1UnifiedToolsInstalled)return;window.__cyV1UnifiedToolsInstalled=true;
  function unifyCapabilityLinks(){
    const section=document.getElementById('cy-capabilities');if(!section)return false;
    section.querySelectorAll('a[data-cy-capability]').forEach(a=>{const page=a.dataset.cyCapability;if(page)a.href='/v1/tool?page='+encodeURIComponent(page);const cta=a.querySelector('span');if(cta&&cta.textContent!=='在统一界面打开 →')cta.textContent='在统一界面打开 →'});
    const p=section.querySelector('.cy-cap-head p');if(p)p.textContent='旧版成熟功能全部保留，但现在统一在长缨辅学工作区内打开；先统一使用界面，再根据真实使用暴露的问题逐项改造。';
    const note=section.querySelector('.cy-cap-note');if(note)note.textContent='当前阶段不复制数据、不重写成熟业务逻辑。所有功能先进入同一界面连续验收；发现慢、重复、缺失或流程不顺后，再按优先级原生化。';
    return true;
  }
  function settle(){
    let tries=0;const timer=setInterval(()=>{const ok=unifyCapabilityLinks();if(ok||++tries>25)clearInterval(timer)},80);
  }
  window.addEventListener('popstate',settle);settle();
})();
</script>
'''
    if "</body>" not in html:
        raise RuntimeError("V1 unified tools patch: closing body marker not found")
    return html.replace("</body>", snippet + f"\n<!-- {V1_UNIFIED_TOOLS_MARKER} --></body>", 1)


def install_v1_unified_tools_patch() -> None:
    if getattr(v1_module, "_unified_tools_patch_installed", False):
        return
    original = v1_module.v1_html

    def patched_v1_html() -> str:
        return patch_v1_unified_tools(original())

    v1_module.v1_html = patched_v1_html
    v1_module._unified_tools_patch_installed = True


__all__ = [
    "V1_UNIFIED_TOOL_PATH",
    "V1_UNIFIED_TOOLS_MARKER",
    "install_v1_unified_tool_route",
    "install_v1_unified_tools_patch",
    "patch_v1_unified_tools",
    "unified_tool_html",
]
