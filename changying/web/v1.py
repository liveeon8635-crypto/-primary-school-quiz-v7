"""Clickable V1 shell built on the existing authentication and teaching APIs."""

from __future__ import annotations

import json
import os
import subprocess

from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response

from changying.web.v1_ribbon_banner import BRAND_FONT_B64 as _BRAND_FONT_B64
from changying.web.v1_ribbon_banner import RIBBON_SVG as _RIBBON_SVG

V1_UI_MARKER = "changying_v1_20260915"
PERSONAL_HOME_COOKIE = "cy_personal_home"
PERSONAL_HOME_JS = """(function(){
  try{
    if(!/(?:^|; )cy_personal_home=1(?:;|$)/.test(document.cookie||""))return;
    var p=location.pathname,q=location.search||"";
    var home=p==="/"||p==="/v1"||p==="/v1/"||(p==="/v1/workspace"&&q.indexOf("view=all")<0);
    if(home&&window.location.pathname!=="/start")window.location.replace("/start");
  }catch(e){}
})();"""

V1_PATHS = ("/v1", "/v1/workspace", "/v1/student", "/v1/history", "/v1/transition")


def current_v1_build_id() -> str:
    configured = (os.getenv("RENDER_GIT_COMMIT") or os.getenv("GIT_COMMIT") or "").strip()
    if configured:
        return configured
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=2,
        ).strip()
    except (OSError, subprocess.SubprocessError):
        return V1_UI_MARKER


def v1_html() -> str:
    from changying.web.v1_classic_gzip_embed import _ALLOWED_TOOL_PAGES

    tool_pages = json.dumps(sorted(_ALLOWED_TOOL_PAGES - {"__hub__"}))
    build_id = json.dumps(current_v1_build_id())
    return f'''<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="build-sha" content={build_id}>
  <meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
  <meta name="theme-color" content="#a8101c">
  <title>长缨辅学 V1</title>
  <style id="{V1_UI_MARKER}-style">
    :root{{--navy:#a8101c;--blue:#c0262d;--cyan:#0e7490;--green:#15803d;--amber:#b45309;--red:#b91c1c;--ink:#172033;--muted:#667085;--line:#eadfd8;--soft:#fbf6f2;--white:#fff;--shadow:0 18px 50px rgba(168,16,28,.10)}}
    *{{box-sizing:border-box}}html{{scroll-behavior:smooth}}body{{margin:0;min-height:100dvh;background:#f8f3ee;color:var(--ink);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;-webkit-text-size-adjust:100%}}button,input,select{{font:inherit}}button,a{{-webkit-tap-highlight-color:transparent}}a{{color:inherit;text-decoration:none}}[hidden]{{display:none!important}}
    .app{{min-height:100dvh;padding-top:101px}}.top{{height:101px;display:flex;align-items:center;justify-content:space-between;gap:16px;padding:0 clamp(16px,4vw,42px);background:#fff;border-bottom:1px solid var(--line);position:fixed;left:0;right:0;top:0;z-index:50}}.brand{{display:flex;align-items:center;gap:10px;font-weight:900}}.mark{{width:38px;height:38px;border-radius:13px;display:grid;place-items:center;background:var(--navy);color:#fff;font-size:20px}}.brand small{{display:block;color:var(--muted);font-size:11px;font-weight:600;margin-top:2px}}.top-actions{{display:flex;align-items:center;gap:8px}}.identity-chip{{font-size:12px;color:var(--navy);background:#edf3ff;border:1px solid #dbe7ff;border-radius:999px;padding:8px 11px;max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
    .cy-term{{display:inline-flex;align-items:center;gap:26px;white-space:nowrap}}.cy-term-year{{font-size:clamp(25px,4vw,38px);font-weight:800;letter-spacing:-.035em;color:var(--ink)}}.cy-dd{{position:relative}}.cy-dd-btn{{display:inline-flex;align-items:center;gap:10px;padding:9px 16px 9px 20px;border:1px solid #efc9c1;border-radius:999px;background:linear-gradient(180deg,#fff,#fff3ee);color:var(--navy);font:inherit;font-size:18px;font-weight:800;letter-spacing:.06em;cursor:pointer;box-shadow:0 4px 14px rgba(168,16,28,.12)}}.cy-dd-btn::after{{content:'';width:8px;height:8px;border-right:2.4px solid var(--navy);border-bottom:2.4px solid var(--navy);transform:translateY(-2px) rotate(45deg);transition:transform .18s}}.cy-dd-btn[aria-expanded=true]::after{{transform:translateY(2px) rotate(-135deg)}}.cy-dd-btn:hover{{border-color:#e07a6e}}.cy-dd-btn:focus-visible{{outline:2px solid var(--navy);outline-offset:3px}}.cy-dd-menu{{position:absolute;right:0;top:calc(100% + 10px);min-width:156px;margin:0;padding:6px;list-style:none;background:#fff;border:1px solid #f0d6d0;border-radius:16px;box-shadow:0 22px 48px rgba(168,16,28,.22);z-index:30;animation:cyDdIn .16s ease-out}}.cy-dd-menu[hidden]{{display:none}}.cy-dd-menu li{{padding:10px 14px;border-radius:11px;font-size:16px;font-weight:700;letter-spacing:.06em;color:#5a423d;cursor:pointer}}.cy-dd-menu li:hover{{background:#fdebe7;color:var(--navy)}}.cy-dd-menu li.on{{background:linear-gradient(100deg,#a8101c,#d9352a);color:#fff}}@keyframes cyDdIn{{from{{opacity:0;transform:translateY(-6px) scale(.97)}}to{{opacity:1;transform:none}}}}@media(prefers-reduced-motion:reduce){{.cy-dd-menu{{animation:none}}}}
    @font-face{{font-family:CyBrand;src:url(data:font/woff2;base64,{_BRAND_FONT_B64}) format('woff2');font-display:swap}}
    .cy-seg{{position:fixed;left:clamp(8px,1.6vw,20px);top:113px;z-index:45;display:grid;grid-template-columns:1fr;grid-template-rows:repeat(var(--n),1fr);height:calc(100dvh - 125px);min-height:260px;margin:0;padding:5px;width:84px;border-radius:26px;background:linear-gradient(180deg,#f6e4dc,#fbefe9);box-shadow:inset 0 1px 3px rgba(168,16,28,.16),0 10px 24px rgba(168,16,28,.08)}}
    .cy-seg-thumb{{position:absolute;left:5px;right:5px;top:5px;height:calc((100% - 10px)/var(--n));transform:translateY(calc(var(--i)*100%));border-radius:21px;background:linear-gradient(180deg,#fff,#fff4ee);box-shadow:0 1px 3px rgba(168,16,28,.22),0 8px 18px rgba(168,16,28,.14),inset 0 1px 0 #fff;transition:transform .24s cubic-bezier(.4,0,.2,1)}}
    .cy-seg a{{position:relative;z-index:1;display:flex;align-items:center;justify-content:center;padding:0 calc(50% - .62em);white-space:normal;word-break:break-all;line-height:1.7;text-align:center;border-radius:21px;font-size:19px;font-weight:900;color:#a07f78}}.cy-seg a.active{{color:var(--navy)}}
    @media(prefers-reduced-motion:reduce){{.cy-seg-thumb{{transition:none}}}}
    .layout{{display:grid;grid-template-columns:minmax(0,1fr);padding-left:calc(84px + clamp(8px,1.6vw,20px) + 4px);min-height:calc(100dvh - 101px)}}.side{{background:#fff;border-right:1px solid var(--line);padding:18px 12px;position:sticky;top:68px;height:calc(100dvh - 68px)}}.nav{{display:grid;gap:5px}}.nav a{{display:flex;align-items:center;gap:10px;padding:11px 13px;border-radius:12px;font-size:14px;color:#465269}}.nav a:hover,.nav a.active{{background:#fdebe7;color:var(--navy);font-weight:800}}.nav span{{font-size:18px}}.scope{{position:absolute;left:14px;right:14px;bottom:18px;padding:12px;background:var(--soft);border-radius:14px;color:var(--muted);font-size:12px;line-height:1.6}}
    main{{min-width:0;padding:28px clamp(16px,3.4vw,46px) 90px}}.page-head{{display:flex;align-items:flex-end;justify-content:space-between;gap:16px;margin-bottom:22px}}h1{{font-size:clamp(25px,4vw,38px);margin:0;letter-spacing:-.035em}}.subtitle{{color:var(--muted);margin:7px 0 0;line-height:1.65}}.tag{{display:inline-flex;align-items:center;gap:6px;padding:7px 10px;border:1px solid #d9e3f2;border-radius:999px;background:#fff;color:#526178;font-size:12px}}.tag.demo{{color:#8a4b00;background:#fff8e8;border-color:#f7d99b}}.btn{{border:1px solid var(--line);border-radius:12px;background:#fff;padding:10px 14px;font-weight:750;color:var(--ink);cursor:pointer;min-height:42px}}.btn.primary{{background:var(--navy);border-color:var(--navy);color:#fff}}.btn.green{{background:var(--green);border-color:var(--green);color:#fff}}.btn:disabled{{opacity:.55;cursor:wait}}
    .grid{{display:grid;gap:15px}}.cols-4{{grid-template-columns:repeat(4,minmax(0,1fr))}}.cols-3{{grid-template-columns:repeat(3,minmax(0,1fr))}}.cols-2{{grid-template-columns:repeat(2,minmax(0,1fr))}}.card{{background:#fff;border:1px solid var(--line);border-radius:18px;padding:18px;box-shadow:0 8px 30px rgba(23,60,120,.04)}}.card h2,.card h3{{margin:0 0 6px}}.card p{{color:var(--muted);line-height:1.65;margin:0}}.kpi strong{{font-size:28px;display:block;margin:8px 0 4px}}.kpi span{{font-size:13px;color:var(--muted)}}.section{{margin-top:22px}}.section-head{{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:11px}}.section-head h2{{font-size:18px;margin:0}}.section-head p{{font-size:13px;color:var(--muted);margin:3px 0 0}}.list{{display:grid;gap:9px}}.row{{display:flex;align-items:center;justify-content:space-between;gap:14px;padding:12px 13px;border:1px solid var(--line);border-radius:13px;background:#fff}}.row-main{{min-width:0}}.row b{{display:block;font-size:14px}}.row small{{display:block;color:var(--muted);margin-top:4px;overflow:hidden;text-overflow:ellipsis}}.row-action{{font-size:13px;color:var(--blue);font-weight:750;white-space:nowrap}}.empty{{padding:22px;text-align:center;color:var(--muted);background:var(--soft);border-radius:13px;line-height:1.7}}.notice{{padding:13px 15px;border-radius:14px;background:#eef6ff;border:1px solid #d4e7ff;color:#285078;line-height:1.6;font-size:13px}}.notice.warn{{background:#fff8e8;border-color:#f5d79a;color:#7a4a00}}.error{{background:#fff1f1;border-color:#fecaca;color:#991b1b}}
    .login-wrap{{min-height:calc(100dvh - 68px);display:grid;place-items:center;padding:26px}}.login{{width:min(470px,100%);padding:28px;background:#fff;border:1px solid var(--line);border-radius:24px;box-shadow:var(--shadow)}}.login h1{{font-size:28px}}.field{{display:grid;gap:6px;margin-top:15px}}.field label{{font-size:13px;font-weight:750}}.field input{{width:100%;border:1px solid #cfd7e5;border-radius:12px;padding:12px 13px;font-size:16px}}.login .btn{{width:100%;margin-top:18px}}.login-help{{font-size:12px;color:var(--muted);line-height:1.6;margin-top:14px}}
    .identities{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;margin-top:20px}}.identity{{text-align:left;background:#fff;border:1px solid var(--line);border-radius:17px;padding:17px;cursor:pointer}}.identity:hover{{border-color:#9db8e8;box-shadow:0 10px 26px rgba(23,60,120,.08)}}.identity strong{{display:block;margin:8px 0 5px}}.identity small{{color:var(--muted);line-height:1.5}}
    .mode-switch{{display:inline-flex;padding:4px;background:#e9eef6;border-radius:12px}}.mode-switch button{{border:0;background:transparent;padding:8px 11px;border-radius:9px;cursor:pointer;font-size:13px}}.mode-switch button.active{{background:#fff;color:var(--navy);font-weight:800;box-shadow:0 3px 10px rgba(0,0,0,.07)}}
    .student-head{{background:linear-gradient(130deg,#a8101c,#c0262d);color:#fff;border:0}}.student-head p{{color:rgba(255,255,255,.8)}}.student-meta{{display:flex;gap:9px;flex-wrap:wrap;margin-top:13px}}.student-meta .tag{{background:rgba(255,255,255,.13);border-color:rgba(255,255,255,.25);color:#fff}}.mastery{{display:flex;gap:6px;align-items:center;flex-wrap:wrap;margin-top:12px}}.mastery span{{font-size:12px;padding:7px 9px;border-radius:9px;background:#eef2f7;color:#748096}}.mastery span.on{{background:#dff2e5;color:#166534;font-weight:800}}.timeline{{border-left:2px solid #dce5f3;margin-left:8px;padding-left:20px;display:grid;gap:16px}}.event{{position:relative}}.event:before{{content:"";position:absolute;width:10px;height:10px;border-radius:50%;background:var(--blue);left:-26px;top:5px;box-shadow:0 0 0 5px #eef4ff}}.event time{{font-size:12px;color:var(--muted)}}.event b{{display:block;margin:4px 0}}.event p{{font-size:13px}}
    .steps{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px}}.step{{padding:15px;border:1px solid var(--line);border-radius:15px;background:#fff;min-height:110px}}.step em{{font-style:normal;font-size:11px;color:var(--blue);font-weight:900}}.step b{{display:block;margin:8px 0 5px}}.step small{{color:var(--muted);line-height:1.5}}.placeholder{{border-style:dashed;background:#fbfcfe}}
    .bottom{{display:none}}.toast{{position:fixed;left:50%;bottom:24px;transform:translateX(-50%);background:#172033;color:#fff;border-radius:999px;padding:10px 15px;font-size:13px;opacity:0;pointer-events:none;transition:.2s;z-index:100}}.toast.show{{opacity:1;transform:translateX(-50%) translateY(-5px)}}
    @media(max-width:980px){{.cols-4{{grid-template-columns:repeat(2,1fr)}}.cols-3{{grid-template-columns:1fr 1fr}}.steps{{grid-template-columns:repeat(2,1fr)}}}}
    .top{{overflow:hidden;background:radial-gradient(110% 240% at 6% -50%,rgba(255,222,160,.6),transparent 56%),linear-gradient(100deg,#a8101c 0%,#d9352a 36%,#ee7a38 64%,#c92a2c 100%);border-bottom:0;color:#fff;box-shadow:0 8px 22px rgba(168,16,28,.28)}}.cy-ribbon{{position:absolute;inset:0;width:100%;height:100%;pointer-events:none;z-index:0}}.top .brand,.top .top-actions{{position:relative;z-index:1}}@media(max-width:720px){{.cy-ribbon{{opacity:.7}}}}.top .brand{{color:#fff;gap:14px}}.top .mark{{background:#fff;color:#b3141e;box-shadow:0 2px 8px rgba(120,0,10,.3)}}.top .brand>span:last-child{{display:flex;align-items:baseline;gap:16px;font-family:CyBrand,'STXingkai','Xingkai SC','Kaiti SC',KaiTi,serif;font-size:52px;font-weight:400;letter-spacing:.14em;white-space:nowrap;text-shadow:0 2px 8px rgba(100,0,10,.4)}}.top .brand small{{display:inline;margin:0;font-family:-apple-system,BlinkMacSystemFont,'PingFang SC','Microsoft YaHei',sans-serif;color:rgba(255,255,255,.88);font-size:12px;letter-spacing:.06em;text-shadow:none}}.top .identity-chip{{background:rgba(255,255,255,.2);color:#fff;border-color:rgba(255,255,255,.45)}}.top .top-actions .btn{{background:rgba(255,255,255,.18);color:#fff;border-color:rgba(255,255,255,.5)}}
    @media(max-width:720px){{.top .brand>span:last-child{{font-size:36px;letter-spacing:.1em}}.top .brand small{{display:none}}.top .top-actions .btn{{white-space:nowrap;padding:8px 8px;font-size:12px}}.top .identity-chip{{max-width:64px}}}}
    @media(max-width:720px){{.app{{padding-top:78px}}.top{{height:78px;padding:0 10px;gap:8px}}.brand{{gap:7px}}.mark{{width:36px;height:36px}}.brand small{{display:none}}.top-actions{{gap:5px;min-width:0}}.identity-chip{{max-width:105px;padding:7px 8px}}.top-actions .btn{{padding:8px 9px;min-height:36px;font-size:12px}}.layout{{display:grid;grid-template-columns:minmax(0,1fr);padding-left:0;min-height:calc(100dvh - 78px)}}.cy-seg{{top:auto;left:8px;right:8px;bottom:max(8px,env(safe-area-inset-bottom));width:auto;height:58px;min-height:0;margin:0;grid-template-columns:repeat(var(--n),1fr);grid-template-rows:1fr;border-radius:20px}}.cy-seg-thumb{{left:5px;right:auto;top:5px;bottom:5px;width:calc((100% - 10px)/var(--n));height:auto;transform:translateX(calc(var(--i)*100%));border-radius:16px}}.cy-seg a{{font-size:15px;line-height:1.2;padding:0 4px;word-break:normal;border-radius:16px}}.side{{display:none}}main{{padding:16px 14px calc(92px + env(safe-area-inset-bottom))}}.page-head{{align-items:flex-start;flex-direction:column}}.cols-4{{grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}}.cols-3,.cols-2,.identities,.steps{{grid-template-columns:1fr}}.kpi{{padding:14px}}.kpi strong{{font-size:24px;margin:5px 0 2px}}.kpi span,.kpi small{{font-size:11px}}.login-wrap{{min-height:calc(100dvh - 60px);padding:18px 14px 84px}}.login{{padding:22px 18px}}.row{{align-items:flex-start}}.bottom{{position:fixed;display:grid;grid-template-columns:repeat(5,1fr);left:8px;right:8px;bottom:max(8px,env(safe-area-inset-bottom));z-index:60;background:rgba(255,255,255,.96);border:1px solid var(--line);border-radius:18px;padding:5px 6px;box-shadow:0 14px 40px rgba(23,60,120,.16);backdrop-filter:blur(14px)}}.bottom a{{text-align:center;font-size:10px;color:#5f6b7e;padding:4px 1px;border-radius:10px}}.bottom a span{{display:block;font-size:16px;margin-bottom:1px}}.bottom a.active{{background:#fdebe7;color:var(--navy);font-weight:800}}}}
  </style>
</head>
<body>
  <div class="app" id="app"><header class="top">{_RIBBON_SVG}<a class="brand" href="/v1"><span>长缨辅学<small>学生连续发展档案 · V1</small></span></a><div class="top-actions"><a class="btn" href="/signup" style="text-decoration:none" title="独立老师可免费注册个人工作台">免费注册</a><span class="identity-chip" id="identityChip">检查登录状态</span><button class="btn" id="identityButton" hidden>切换身份</button></div></header><div id="screen"></div></div>
  <div class="toast" id="toast"></div>
  <script id="{V1_UI_MARKER}-script">
  (()=>{{
    const TOKEN_KEY='v717Token', USER_KEY='v717User', REMEMBER_KEY='v717Remember', IDENTITY_KEY='cyV1Identity', CYCLE_KEY='cyV1Cycle';
    const authRemember=()=>localStorage.getItem(REMEMBER_KEY)==='1';
    const authStore=()=>authRemember()?localStorage:sessionStorage;
    const readToken=()=>authStore().getItem(TOKEN_KEY)||sessionStorage.getItem(TOKEN_KEY)||localStorage.getItem(TOKEN_KEY)||sessionStorage.getItem('v6Token')||localStorage.getItem('v6Token')||'';
    const legacyUser=s=>({{id:s?.userID??s?.id??null,name:s?.name||'',role:s?.role||'teacher',grade:s?.grade??null,mustChangePassword:!!s?.mustChangePassword,subscription:s?.subscription||null}});
    const persistAuth=(result,remember)=>{{const store=remember?localStorage:sessionStorage,other=remember?sessionStorage:localStorage;store.setItem(TOKEN_KEY,result?.token||token||'');store.setItem(USER_KEY,JSON.stringify(legacyUser(result)));other.removeItem(TOKEN_KEY);other.removeItem(USER_KEY);localStorage.setItem(REMEMBER_KEY,remember?'1':'0')}};
    const clearAuthStorage=()=>{{localStorage.removeItem(TOKEN_KEY);localStorage.removeItem(USER_KEY);localStorage.removeItem(REMEMBER_KEY);sessionStorage.removeItem(TOKEN_KEY);sessionStorage.removeItem(USER_KEY);localStorage.removeItem('v6Token');localStorage.removeItem('v6User');sessionStorage.removeItem('v6Token');sessionStorage.removeItem('v6User');sessionStorage.removeItem('cyV1RoleTutorialShownThisLoginV7')}};
    const stageClassicHandoff=async()=>{{if(!token||token==='demo')return true;try{{const r=await fetch('/v1/auth-handoff',{{method:'POST',headers:{{Authorization:'Bearer '+token}},cache:'no-store',credentials:'same-origin'}});return r.ok}}catch{{return false}}}};
    const CLASSIC_PAGES=new Set({tool_pages});
    const classicTarget=path=>{{try{{const u=new URL(path,location.origin);if(u.origin===location.origin&&u.pathname==='/v1/tool'){{const p=(u.searchParams.get('page')||'').trim();if(p&&p!=='__hub__'&&CLASSIC_PAGES.has(p))return '/classic?legacy=1&unified=1&from=v1&page='+encodeURIComponent(p)}}}}catch(_e){{}}return path}};
    const showOpening=()=>{{let o=document.getElementById('cy-opening');if(!o){{o=document.createElement('div');o.id='cy-opening';o.setAttribute('role','status');o.style.cssText='position:fixed;left:50%;top:50%;transform:translate(-50%,-50%);z-index:2147483000;background:rgba(15,23,42,.88);color:#fff;padding:12px 22px;border-radius:999px;font:600 15px system-ui,sans-serif;box-shadow:0 8px 28px rgba(0,0,0,.25);pointer-events:none';o.textContent='正在打开…';document.body.appendChild(o)}}o.hidden=false;return o}};
    window.addEventListener('pageshow',e=>{{if(e.persisted){{const o=document.getElementById('cy-opening');if(o)o.hidden=true}}}});
    const openClassic=async path=>{{const tip=showOpening();const ok=await stageClassicHandoff();if(!ok){{tip.hidden=true;toast('登录状态同步失败，请重试');return false}}location.href=classicTarget(path);return true}};
    let session=null, identity=null, token=readToken();
    const screen=document.getElementById('screen'), chip=document.getElementById('identityChip'), identityButton=document.getElementById('identityButton');
    const esc=value=>String(value??'').replace(/[&<>"']/g,ch=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[ch]));
    const studentPosition=p=>{{const grade=p?.grade?`档案年级：${{p.grade}}年级`:'';const className=p?.className||p?.currentClassName||'';const current=className?`当前班级：${{className}}`:'当前教学位置待完善';return[grade,current].filter(Boolean).join(' · ')}};
    const demoStudents=[{{id:900101,name:'演示学生·小禾',grade:3,className:'演示三年级晚托班',classID:900201}},{{id:900102,name:'演示学生·小川',grade:5,className:'演示五年级周末班',classID:900202}}];
    const demoStudentForMode=x=>identity?.mode==='school'?{{...x,className:x.grade===3?'演示三年级二班':'演示五年级一班'}}:{{...x}};
    function demoProfile(id){{
      const student=demoStudentForMode(demoStudents.find(x=>x.id===Number(id))||demoStudents[0]);
      return {{
        student:{{...student,active:true,parents:[{{id:900301,name:'演示监护人',username:'demo-parent'}}]}},
        academic:{{
          avgScore:82,accuracy:79,submissionCount:6,pendingAssignments:1,overdueAssignments:0,
          weakKnowledge:[{{knowledge:'小数乘法',accuracy:62,answered:8}},{{knowledge:'阅读概括',accuracy:70,answered:10}}],
          recentAssignments:[{{title:'演示作业：数学巩固',subject:'数学',dueDate:'本周五',status:'待完成'}}]
        }},
        suggestions:['演示建议：先复习小数乘法计算步骤。','演示建议：下次课检查独立完成情况。'],
        classHistory:[{{className:identity?.mode==='school'?'演示二年级二班':'演示二年级托管班',current:false}},{{className:student.className,current:true}}],
        timeline:[{{time:'本周',title:'演示测验记录',detail:'数学 82 分 · 已进入同一学生档案'}},{{time:'上月',title:'演示班级变化',detail:'升年级后继续使用原学生档案'}}]
      }};
    }}
    const demoApi=url=>{{if(url==='/teacher/classes')return identity?.mode==='school'?[{{id:900201,name:'演示三年级二班',grade:3,studentCount:1}},{{id:900202,name:'演示五年级一班',grade:5,studentCount:1}}]:[{{id:900201,name:'演示三年级晚托班',grade:3,studentCount:1}},{{id:900202,name:'演示五年级周末班',grade:5,studentCount:1}}];if(url.includes('/students/')&&url.endsWith('/growth-profile'))return demoProfile(url.split('/')[3]);if(url.includes('/teacher/classes/')&&url.endsWith('/students'))return demoStudents.filter(x=>x.classID===Number(url.split('/')[3])).map(demoStudentForMode);if(url==='/teacher/dashboard')return{{pendingSubmissions:1,avgScore:82}};return[]}};
    const api=async(url,options={{}})=>{{if(session?.demo)return demoApi(url);const timeoutMs=Number(options.timeoutMs||10000),requestOptions={{...options}};delete requestOptions.timeoutMs;const controller=new AbortController();const timer=setTimeout(()=>controller.abort(),timeoutMs);try{{const res=await fetch(url,{{...requestOptions,headers:{{'Content-Type':'application/json',...(token?{{Authorization:'Bearer '+token}}:{{}}),...(requestOptions.headers||{{}})}},signal:controller.signal}});let body=null;try{{body=await res.json()}}catch{{}}if(!res.ok){{const error=new Error(body?.detail||'请求失败');error.status=res.status;throw error}}return body}}finally{{clearTimeout(timer)}}}};
    const toast=message=>{{const el=document.getElementById('toast');el.textContent=message;el.classList.add('show');clearTimeout(el._t);el._t=setTimeout(()=>el.classList.remove('show'),2200)}};
    const PAGE_BUILD={build_id};
    let buildCheckBusy=false;
    const ensureFreshBuild=async(target)=>{{
      if(buildCheckBusy||session?.demo)return false;
      buildCheckBusy=true;
      try{{
        const res=await fetch('/v1/version?ts='+Date.now(),{{cache:'no-store'}});
        if(!res.ok)return false;
        const body=await res.json(),remote=String(body?.build||'');
        if(remote&&remote!==String(PAGE_BUILD)){{
          const now=Date.now(),lastBuild=sessionStorage.getItem('cyV1ReloadBuild')||'',lastAt=Number(sessionStorage.getItem('cyV1ReloadAt')||0);
          if(lastBuild!==remote||now-lastAt>10000){{
            sessionStorage.setItem('cyV1ReloadBuild',remote);
            sessionStorage.setItem('cyV1ReloadAt',String(now));
            const url=new URL(target||location.href,location.origin);
            url.searchParams.set('__v1_build',remote.slice(0,16));
            location.replace(url.pathname+url.search+url.hash);
            return true;
          }}
        }}
      }}catch(_e){{}}
      finally{{buildCheckBusy=false}}
      return false;
    }};
    const navigate=async(path)=>{{history.pushState({{}},'',path);const stale=ensureFreshBuild(path);render();await stale}};
    const identityReturnPath=()=>{{const path=location.pathname,full=path+location.search;return ['/v1/workspace','/v1/student','/v1/history','/v1/transition'].includes(path)?full:''}};
    let pendingIdentityReturnPath='';
    const roleLabel={{admin:'管理员',teacher:'教师',parent:'家长',student:'学生'}};
    const identitiesFor=s=>{{if(!s)return[];const common={{accountRole:s.role,name:s.name||roleLabel[s.role]||'当前账号'}};if(s.role==='admin'){{const institution={{...common,key:'institution_admin',label:'机构管理员',mode:'institution',icon:'🏫'}};return s.demo?[institution,{{...common,key:'school_admin',label:'学校管理员',mode:'school',icon:'🏛️'}}]:[institution]}}if(s.role==='teacher'){{const institution={{...common,key:'institution_teacher',label:'机构老师',mode:'institution',icon:'👩‍🏫'}};return s.demo?[institution,{{...common,key:'school_teacher',label:'学校教师',mode:'school',icon:'📚'}}]:[institution]}}if(s.role==='parent')return[{{...common,key:'parent',label:'家长',mode:'family',icon:'👪'}}];return[{{...common,key:'student',label:'学生',mode:'student',icon:'🎒'}}]}};
    function roleQuickNav(){{
      const role=session?.role||'teacher';
      if(role==='student')return[
        ['syncLearning','▦','课堂','/v1/tool?page=syncLearning'],
        ['assignments','✓','作业','/v1/tool?page=assignments'],
        ['practice','✎','练习','/v1/tool?page=practice'],
        ['progress','◉','学情','/v1/tool?page=progress'],
        ['tools','☰','更多','/v1/tool?page=__hub__'],
      ];
      if(role==='parent')return[
        ['childLearning','▦','孩子课程','/v1/tool?page=childLearning'],
        ['childAssignments','✓','孩子作业','/v1/tool?page=childAssignments'],
        ['childProgress','◉','孩子学情','/v1/tool?page=childProgress'],
        ['childRewards','★','课堂表现','/v1/tool?page=childRewards'],
        ['account','⌘','我的','/v1/tool?page=account'],
      ];
      if(role==='admin')return[
        ['admin','▦','平台总览','/v1/tool?page=admin'],
        ['users','◉','账号管理','/v1/tool?page=users'],
        ['pointsAdmin','★','积分奖励','/v1/tool?page=pointsAdmin'],
        ['adminAudit','◷','全校审计','/v1/tool?page=adminAudit'],
        ['system','⌘','系统设置','/v1/tool?page=system'],
      ];
      return[
        ['workspace','▦','当前教学','/v1/workspace'],
        ['tools','⌘','全部功能','/v1/workspace?view=all'],
      ];
    }}
    function shell(content,active='workspace'){{const nav=roleQuickNav();const viewAll=location.pathname==='/v1/workspace'&&new URLSearchParams(location.search).get('view')==='all';const segOf={{students:'workspace',history:'tools',transition:'tools'}};const base=segOf[active]||active;const cur=base==='workspace'&&viewAll?'tools':base;const idx=Math.max(0,nav.findIndex(n=>n[0]===cur));const item=n=>`<a href="${{n[3]}}" data-seg="${{n[0]}}" ${{n[3].startsWith('/v1/tool')?'': 'data-nav'}} class="${{cur===n[0]?'active':''}}">${{n[2]}}</a>`;return `<div class="layout"><nav class="cy-seg" id="cy-seg" style="--n:${{nav.length}};--i:${{idx}}"><span class="cy-seg-thumb"></span>${{nav.map(item).join('')}}</nav><main>${{content}}</main></div>`}}
    function bindNav(){{document.querySelectorAll('[data-nav]').forEach(a=>a.onclick=e=>{{e.preventDefault();navigate(a.getAttribute('href'))}})}}
    function loginView(message=''){{identityButton.hidden=true;chip.textContent='尚未登录';screen.innerHTML=`<div class="login-wrap"><form class="login" id="loginForm"><span class="tag">长缨辅学 V1</span><h1>登录教学系统</h1><p class="subtitle">登录后识别身份，进入账号已授权的教学视图。</p>${{message?`<div class="notice error">${{esc(message)}}</div>`:''}}<div class="field"><label>账号</label><input name="username" autocomplete="username" required></div><div class="field"><label>密码</label><input name="password" type="password" autocomplete="current-password" required></div><label class="field" style="display:flex;grid-template-columns:auto 1fr;align-items:center"><input name="remember" type="checkbox" style="width:auto">记住登录</label><button class="btn primary" type="submit">登录并继续</button><button class="btn" id="demoButton" type="button">查看演示流程</button><div class="login-help">演示流程使用明确标注的浏览器占位数据，不写入数据库；真实账号继续使用现有权限和数据。</div></form></div>`;document.getElementById('demoButton').onclick=()=>{{token='demo';session={{userID:900001,name:'演示教师',role:'teacher',demo:true}};pendingIdentityReturnPath=identityReturnPath();chooseIdentity()}};document.getElementById('loginForm').onsubmit=async e=>{{e.preventDefault();const btn=e.submitter;btn.disabled=true;try{{const data=Object.fromEntries(new FormData(e.target)),remember=data.remember==='on';const result=await api('/login',{{method:'POST',body:JSON.stringify({{username:data.username,password:data.password,remember}})}});token=result.token;persistAuth(result,remember);session=result;if(result.mustChangePassword){{toast('请先修改初始密码');await openClassic('/v1/tool?page=account');return}}pendingIdentityReturnPath=identityReturnPath();chooseIdentity()}}catch(err){{loginView(err.message)}}}}}}
    function chooseIdentity(){{const choices=identitiesFor(session);identity=null;localStorage.removeItem(IDENTITY_KEY);chip.textContent=session?.name||'当前账号';identityButton.hidden=true;screen.innerHTML=`<div class="login-wrap"><section class="login" style="width:min(650px,100%)"><span class="tag">已识别账号：${{esc(session?.name||'')}}</span><h1>选择本次使用身份</h1><p class="subtitle">${{session?.demo?'演示流程可切换机构与学校模式。':'现有账号按原权限接入培训机构数据；学校数据域建立后再开放对应真实身份。'}}</p><div class="identities">${{choices.map(x=>`<button class="identity" data-key="${{x.key}}"><span style="font-size:25px">${{x.icon}}</span><strong>${{x.label}}</strong><small>${{x.mode==='school'?'进入学校教学工作台':'进入'+(x.mode==='institution'?'培训机构教学工作台':'个人教学视图')}}</small></button>`).join('')}}</div></section></div>`;document.querySelectorAll('[data-key]').forEach(btn=>btn.onclick=()=>{{identity=choices.find(x=>x.key===btn.dataset.key);localStorage.setItem(IDENTITY_KEY,identity.key);const fallback=identity.mode==='family'||identity.mode==='student'?'/v1/student':'/v1/workspace?mode='+identity.mode,target=pendingIdentityReturnPath||fallback;pendingIdentityReturnPath='';navigate(target)}})}}
    function heading(title,desc,extra=''){{return `<header class="page-head"><div><h1>${{title}}</h1>${{desc?`<p class="subtitle">${{desc}}</p>`:''}}</div>${{extra}}</header>`}}
    async function loadPeople(){{if(session.role==='admin'){{const users=await api('/admin/users');return users.filter(x=>x.role==='student')}}if(session.role==='teacher'){{const classes=await api('/teacher/classes');let people=[];for(const c of classes.slice(0,8)){{try{{const rows=await api('/teacher/classes/'+c.id+'/students');people.push(...rows.map(x=>({{...x,className:c.name,classID:c.id}})))}}catch{{}}}}return [...new Map(people.map(x=>[x.id,x])).values()]}}if(session.role==='parent')return await api('/parent/children');return[{{id:session.userID||session.id,name:session.name,grade:session.grade,role:'student'}}]}}
    async function workspace(){{const mode=new URLSearchParams(location.search).get('mode')||identity.mode;const termOptions=['上学期','暑假','下学期','寒假'],TERM_KEY='cyV1Term',monthNow=new Date().getMonth()+1,year=new Date().getFullYear();let term=localStorage.getItem(TERM_KEY);if(!termOptions.includes(term))term=monthNow>=9?'上学期':monthNow>=7?'暑假':monthNow>=3?'下学期':'寒假';const cycle={{'暑假':'summer','寒假':'winter'}}[term]||'term';const isSchool=mode==='school';let people=[],classes=[],stats={{}};try{{people=await loadPeople();if(session.role==='teacher'){{classes=await api('/teacher/classes');stats=await api('/teacher/dashboard')}}else if(session.role==='admin'){{classes=await api('/admin/classes');stats=await api('/admin/overview')}}else if(session.role==='student'){{const pair=await Promise.all([api('/student/assignments'),api('/student/progress')]);const studentAssignments=Array.isArray(pair[0])?pair[0]:[],studentProgress=pair[1]||{{}},classNames=[...new Set(studentAssignments.map(x=>x.assignedClassName).filter(Boolean))];classes=classNames.map((name,i)=>({{id:i+1,name}}));stats={{pendingSubmissions:studentAssignments.filter(x=>!x.completed).length,avgScore:studentProgress.avgScore??null}}}}}}catch(err){{if(err.status===428){{await openClassic('/v1/tool?page=account');return}}}}
      const cycleNames={{term:'正常学期',winter:'寒假班',summer:'暑假班'}};const tasks=isSchool?['今日课表','我的班级','教学进度','备课','作业','批改/订正','测验','教学评价']:(cycle==='term'?['晚托','周末课','今日/本周教学','作业与错题','学习进度']:[cycleNames[cycle],'当前班级','今日课程','教学进度','作业/练习']);
      const title=isSchool?'学校教学工作台':'培训机构教学工作台';const phase=isSchool?'<span class="tag">学校模式</span>':`<div class="cy-term" id="termSelect"><span class="cy-term-year">${{year}}年</span><div class="cy-dd" id="termDd"><button type="button" class="cy-dd-btn" id="termBtn" aria-haspopup="listbox" aria-expanded="false">${{term}}</button><ul class="cy-dd-menu" role="listbox" aria-label="学期" hidden>${{termOptions.map(t=>`<li role="option" data-term="${{t}}" aria-selected="${{t===term}}" class="${{t===term?'on':''}}">${{t}}</li>`).join('')}}</ul></div></div>`;
      const cards=tasks.map((x,i)=>`<button class="card" data-feature="${{esc(x)}}" style="text-align:left;cursor:pointer"><span style="font-size:22px">${{['▣','◫','◉','✓','↗','✎'][i%6]}}</span><h3 style="margin-top:10px">${{esc(x)}}</h3><p>${{isSchool?(x==='今日课表'?'按学校课表查看当天课程':'学校数据域内的教学入口'):({{'晚托':'查看当日晚托学生与任务','周末课':'查看本周末课程与学生','今日/本周教学':'逾期、即将到期与待回访提醒','作业与错题':'按学生汇总待完成、逾期与薄弱项','课堂复盘':'复盘讲义、互动课堂与随堂检测','学习进度':'成绩、作业与薄弱知识概览','当前班级':'查看当前班级与学生','今日课程':'查看今日课程安排','教学进度':'成绩、作业与薄弱知识概览','作业/练习':'按学生汇总待完成、逾期与薄弱项'}}[x]||'进入当前教学周期')}}</p></button>`).join('');
      let cycleRows=null;if(!isSchool&&cycle!=='term'){{try{{const r=await api('/v1/teaching-cycles');cycleRows=((r&&r.cycles)||[]).filter(x=>x.cycleKind===cycle&&Number(x.academicYear)===year)}}catch{{cycleRows=[]}}}}
      const notice=session.demo?`<div class="notice warn">演示数据 · 当前身份：${{esc(identity.label)}} · ${{esc(session.name||'')}}。页面操作不会写入数据库。</div>`:'';
      const cycleBody=cycleRows===null?'':(cycleRows.length?'<section class="section"><div class="list">'+cycleRows.map(x=>`<div class="row"><span class="row-main"><b>${{esc(x.title||x.term)}}</b><small>${{esc(x.grade?x.grade+'年级':'')}}</small></span></div>`).join('')+'</div></section>':`<section class="section"><div class="empty" id="cy-cycle-empty">暂无${{year}}年${{term}}教学安排</div></section>`);
      const content=cycleRows!==null?heading(title,'',phase)+notice+cycleBody:heading(title,'',phase)+notice+`<section class="section grid cols-3"><div class="card kpi"><span>当前班级</span><strong>${{classes.length}}</strong><small>按当前账号权限</small></div><div class="card kpi"><span>待完成作业</span><strong>${{stats.pendingSubmissions??stats.assignments??'—'}}</strong><small>${{session.demo?'演示数据':'现有作业数据'}}</small></div><div class="card kpi"><span>平均成绩</span><strong>${{stats.avgScore??'—'}}</strong><small>有记录时显示</small></div></section><section class="section"><div class="section-head"><div><h2>${{isSchool?'教师工作台':'当前教学'}}</h2></div></div><div class="grid cols-3">${{cards}}</div></section><section class="section"><div class="section-head"><div><h2>当前学生</h2><span class="tag">${{people.length}} 人</span></div><button class="btn" id="allStudents">查看全部</button></div><div class="list">${{people.slice(0,6).map(p=>`<a class="row" data-student href="/v1/student?id=${{p.id}}"><span class="row-main"><b>${{esc(p.name)}}</b><small>${{esc(studentPosition(p))}}</small></span><span class="row-action">查看动态 →</span></a>`).join('')||'<div class="empty">当前账号暂无可见学生。可进入原教学系统维护真实学生与班级关系。</div>'}}</div></section>`;
      screen.innerHTML=shell(content,'workspace');bindNav();const termBtn=document.getElementById('termBtn'),termMenu=document.querySelector('#termDd .cy-dd-menu');if(termBtn&&termMenu){{const closeTerm=()=>{{termMenu.hidden=true;termBtn.setAttribute('aria-expanded','false')}};termBtn.onclick=e=>{{e.stopPropagation();const open=termMenu.hidden;termMenu.hidden=!open;termBtn.setAttribute('aria-expanded',String(open))}};termMenu.querySelectorAll('[data-term]').forEach(li=>li.onclick=()=>{{localStorage.setItem(TERM_KEY,li.dataset.term);workspace()}});if(!window.__cyTermDd){{window.__cyTermDd=true;document.addEventListener('click',e=>{{const m=document.querySelector('#termDd .cy-dd-menu'),b=document.getElementById('termBtn');if(m&&!m.hidden&&!(b&&b.contains(e.target))){{m.hidden=true;b&&b.setAttribute('aria-expanded','false')}}}});document.addEventListener('keydown',e=>{{if(e.key==='Escape'){{const m=document.querySelector('#termDd .cy-dd-menu');if(m)m.hidden=true}}}})}}}}document.querySelectorAll('[data-student]').forEach(a=>a.onclick=e=>{{e.preventDefault();navigate(a.getAttribute('href'))}});document.querySelectorAll('[data-feature]').forEach(b=>b.onclick=()=>toast(b.dataset.feature+'：V1 入口已预留'));const allBtn=document.getElementById('allStudents');if(allBtn)allBtn.onclick=()=>navigate('/v1/student');
    }}

    function v1QuestionTypeLabel(q){{
      const t=String(q?.questionType||q?.question_type||'').toLowerCase();
      return ({{single_choice:'单选题',choice:'单选题',true_false:'判断题',fill_blank:'填空题',calculation:'计算题',short_answer:'应用简答题'}})[t]||(((q?.options||[]).length>0)?'选择题':'练习题');
    }}
    function v1ChoiceLike(q){{
      const t=String(q?.questionType||q?.question_type||'').toLowerCase();
      return ['single_choice','choice','true_false'].includes(t)||(((q?.options||[]).length>0)&&!['fill_blank','calculation','short_answer'].includes(t));
    }}
    function v1RenderQuestionFigure(fig){{
      if(!fig||!fig.type)return '';
      const type=String(fig.type||'').toLowerCase(),w=320,h=210,m=28,num=(v,d=0)=>Number.isFinite(+v)?+v:d;
      if(type==='uploaded_image'&&/^data:image\\/jpeg;base64,[A-Za-z0-9+/]+={{0,2}}$/.test(String(fig.data_url||''))&&String(fig.data_url).length<=700000)return '<div style="margin:12px 0;padding:10px;border:1px solid #e5e7eb;border-radius:12px;background:#fff"><img src="'+fig.data_url+'" alt="'+esc(fig.alt||'题目照片')+'" style="display:block;max-width:100%;max-height:360px;object-fit:contain;margin:auto"></div>';
      let body='';
      if(type==='coordinate_grid'){{
        const xm=Math.max(1,Math.min(12,num(fig.xMax,8))),ym=Math.max(1,Math.min(12,num(fig.yMax,8))),sx=(w-2*m)/xm,sy=(h-2*m)/ym;
        for(let x=0;x<=xm;x++){{const px=m+x*sx;body+='<line x1="'+px+'" y1="'+m+'" x2="'+px+'" y2="'+(h-m)+'" stroke="#d8dee9" stroke-width="1"/><text x="'+px+'" y="'+(h-m+17)+'" text-anchor="middle" font-size="10">'+x+'</text>'}}
        for(let y=0;y<=ym;y++){{const py=h-m-y*sy;body+='<line x1="'+m+'" y1="'+py+'" x2="'+(w-m)+'" y2="'+py+'" stroke="#d8dee9" stroke-width="1"/><text x="'+(m-9)+'" y="'+(py+3)+'" text-anchor="middle" font-size="10">'+y+'</text>'}}
        (fig.segments||[]).forEach(seg=>{{if(['x1','y1','x2','y2'].every(k=>Number.isFinite(+seg[k])))body+='<line x1="'+(m+num(seg.x1)*sx)+'" y1="'+(h-m-num(seg.y1)*sy)+'" x2="'+(m+num(seg.x2)*sx)+'" y2="'+(h-m-num(seg.y2)*sy)+'" stroke="#4b5563" stroke-width="2"/>'}});
        (fig.points||[]).forEach(p=>{{const px=m+num(p.x)*sx,py=h-m-num(p.y)*sy;body+='<circle cx="'+px+'" cy="'+py+'" r="4" fill="#111827"/><text x="'+(px+7)+'" y="'+(py-7)+'" font-size="12">'+esc(p.label||p.name||'')+'</text>'}});
      }}else if(type==='geometry'){{
        const shape=String(fig.shape||'rectangle').toLowerCase(),labels=fig.labels||{{}};
        const txt=(key,x,y,anchor='middle')=>{{if(labels[key])body+='<text x="'+x+'" y="'+y+'" text-anchor="'+anchor+'" font-size="12" font-weight="600">'+esc(labels[key])+'</text>'}};
        if(shape==='triangle'){{body='<polygon points="65,170 255,170 160,45" fill="none" stroke="#374151" stroke-width="3"/>';txt('底',160,190);if(labels['高']){{body+='<line x1="160" y1="45" x2="160" y2="170" stroke="#64748b" stroke-width="1.5" stroke-dasharray="5 4"/>';txt('高',170,112,'start')}}}}
        else if(shape==='trapezoid'){{body='<polygon points="85,55 225,55 270,170 45,170" fill="none" stroke="#374151" stroke-width="3"/>';txt('上底',155,45);txt('下底',155,190);if(labels['高']){{body+='<line x1="155" y1="55" x2="155" y2="170" stroke="#64748b" stroke-width="1.5" stroke-dasharray="5 4"/>';txt('高',165,116,'start')}}}}
        else if(shape==='parallelogram'){{body='<polygon points="90,55 260,55 225,170 55,170" fill="none" stroke="#374151" stroke-width="3"/>';txt('底',140,190);if(labels['高']){{body+='<line x1="90" y1="55" x2="90" y2="170" stroke="#64748b" stroke-width="1.5" stroke-dasharray="5 4"/>';txt('高',100,116,'start')}}}}
        else if(shape==='composite_rect'){{body='<path d="M55 45 H265 V170 H145 V110 H55 Z" fill="none" stroke="#374151" stroke-width="3"/>';let y=198;Object.keys(labels).slice(0,4).forEach(k=>{{body+='<text x="'+m+'" y="'+y+'" font-size="11">'+esc(k)+'：'+esc(labels[k])+'</text>';y-=15}})}}
        else {{body='<rect x="55" y="50" width="210" height="120" fill="none" stroke="#374151" stroke-width="3"/>';txt('长',160,42);txt('宽',276,114,'start')}}
      }}else if(type==='line_segment'){{
        const segs=(fig.segments||[]).length?fig.segments:[{{label:'线段',ratio:1}}],total=segs.reduce((sum,x)=>sum+Math.max(.1,num(x.ratio,1)),0);let x=m;
        segs.forEach((seg,idx)=>{{const ww=(w-2*m)*Math.max(.1,num(seg.ratio,1))/total;body+='<line x1="'+x+'" y1="105" x2="'+(x+ww)+'" y2="105" stroke="#374151" stroke-width="4"/><line x1="'+x+'" y1="96" x2="'+x+'" y2="114" stroke="#374151" stroke-width="2"/><text x="'+(x+ww/2)+'" y="88" text-anchor="middle" font-size="12">'+esc(seg.label||('第'+(idx+1)+'段'))+'</text>';x+=ww}});body+='<line x1="'+x+'" y1="96" x2="'+x+'" y2="114" stroke="#374151" stroke-width="2"/>';
      }}else if(type==='bar_chart'){{
        const bars=(fig.bars||[]).slice(0,8),max=Math.max(1,...bars.map(x=>num(x.value,0))),bw=Math.max(18,(w-2*m)/Math.max(1,bars.length)-10);
        body+='<line x1="'+m+'" y1="'+(h-m)+'" x2="'+(w-m)+'" y2="'+(h-m)+'" stroke="#374151"/>';
        bars.forEach((bar,idx)=>{{const bh=(h-2*m)*num(bar.value,0)/max,x=m+idx*((w-2*m)/Math.max(1,bars.length))+5,y=h-m-bh;body+='<rect x="'+x+'" y="'+y+'" width="'+bw+'" height="'+bh+'" fill="#9ca3af"/><text x="'+(x+bw/2)+'" y="'+(h-m+15)+'" text-anchor="middle" font-size="10">'+esc(bar.name||bar.label||'')+'</text><text x="'+(x+bw/2)+'" y="'+(y-5)+'" text-anchor="middle" font-size="10">'+num(bar.value,0)+'</text>'}});
      }}else if(type==='object_group'){{
        const groups=(fig.groups||[]).slice(0,6);let y=48;groups.forEach(g=>{{const count=Math.max(0,Math.min(12,Math.round(num(g.count,0)))),symbol=esc(g.symbol||'●');body+='<text x="25" y="'+y+'" font-size="13">'+esc(g.label||g.name||'')+'：</text><text x="105" y="'+y+'" font-size="18">'+Array(count).fill(symbol).join(' ')+'</text>';y+=28}});
      }}else return '';
      const title=fig.title?'<div style="text-align:center;color:#667085;font-size:12px;margin-bottom:4px">'+esc(fig.title)+'</div>':'';
      return '<div style="margin:12px 0;padding:10px;border:1px solid #e5e7eb;border-radius:12px;background:#fff">'+title+'<svg viewBox="0 0 '+w+' '+h+'" style="width:100%;max-width:420px;display:block;margin:auto" role="img" aria-label="题目图示">'+body+'</svg></div>';
    }}
    async function openV1StudentAssignment(aid){{
      try{{
        const rows=await api('/student/assignments');const a=rows.find(x=>Number(x.id)===Number(aid));
        if(!a){{toast('没有找到这份测试');return}}
        if(a.submissionMode==='media'){{await openClassic('/v1/tool?page=assignments');return}}
        if(a.quizSubmitted){{toast('这份在线测试已经提交');return}}
        if(!a.paperID){{toast('这份测试没有可用试卷');return}}
        const questions=await api('/papers/'+a.paperID+'/questions');
        if(!questions.length){{toast('这份测试暂时没有可用题目');return}}
        let index=0;const answers=new Map();
        const backToProfile=()=>navigate('/v1/student?id='+(session.userID||session.id||''));
        const renderQuestion=()=>{{
          const q=questions[index],saved=answers.get(q.id)||{{}},isChoice=v1ChoiceLike(q),selected=Number.isInteger(saved.selected_index)?saved.selected_index:null,textAnswer=String(saved.text_answer||''),answered=answers.size;
          const meta=[q.textbook,q.unit,q.knowledge].filter(Boolean).map(esc).join(' · '),typeName=v1QuestionTypeLabel(q),figure=v1RenderQuestionFigure(q.figure||{{}});
          const options=isChoice?(q.options||[]).map((option,i)=>'<button class="btn v1-quiz-option" data-option="'+i+'" style="width:100%;text-align:left;justify-content:flex-start;border-color:'+(selected===i?'#c0262d':'#e4e9f2')+';background:'+(selected===i?'#fdebe7':'#fff')+'"><b style="margin-right:8px">'+String.fromCharCode(65+i)+'.</b> '+esc(option)+'</button>').join(''):'';
          const textInput=isChoice?'':(String(q.questionType||q.question_type||'').toLowerCase()==='short_answer'?'<textarea id="v1QuizTextAnswer" rows="4" style="width:100%;border:1px solid #cfd7e5;border-radius:12px;padding:12px 13px;font:inherit" placeholder="请输入简短答案">'+esc(textAnswer)+'</textarea>':'<input id="v1QuizTextAnswer" inputmode="'+(String(q.questionType||q.question_type||'').toLowerCase()==='calculation'?'decimal':'text')+'" style="width:100%;border:1px solid #cfd7e5;border-radius:12px;padding:12px 13px;font:inherit" value="'+esc(textAnswer)+'" placeholder="请输入答案">');
          const body=heading(esc(a.title||'在线测试'),'第 '+(index+1)+' / '+questions.length+' 题 · 已答 '+answered+' / '+questions.length,'<button class="btn" id="v1QuizExit">退出测试</button>')+
            '<section class="card"><div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:14px"><span class="tag">'+esc(typeName)+'</span><span class="tag">'+(meta||'在线答题')+'</span></div><h2 style="line-height:1.6;margin-bottom:16px">'+esc(q.text||'题目')+'</h2>'+figure+'<div class="grid" style="gap:10px">'+options+textInput+'</div><div class="notice" style="margin-top:14px">正式作业不会在提交前显示正确答案或解析。</div></section><section class="section" style="display:flex;gap:10px;justify-content:space-between"><button class="btn" id="v1QuizPrev" '+(index===0?'disabled':'')+'>上一题</button><div style="display:flex;gap:10px"><button class="btn" id="v1QuizNext" '+(index===questions.length-1?'style="display:none"':'')+'>下一题</button><button class="btn primary" id="v1QuizSubmit" '+(index===questions.length-1?'':'style="display:none"')+' '+(answers.size===questions.length?'':'disabled')+'>提交测试</button></div></section>';
          screen.innerHTML=shell(body,'students');bindNav();
          document.querySelectorAll('.v1-quiz-option').forEach(btn=>btn.onclick=()=>{{answers.set(q.id,{{selected_index:Number(btn.dataset.option)}});renderQuestion()}});
          const input=document.getElementById('v1QuizTextAnswer');if(input)input.oninput=()=>{{const value=input.value;if(value.trim())answers.set(q.id,{{text_answer:value}});else answers.delete(q.id);const submit=document.getElementById('v1QuizSubmit');if(submit)submit.disabled=answers.size!==questions.length}};
          document.getElementById('v1QuizPrev').onclick=()=>{{if(index>0){{index--;renderQuestion()}}}};
          document.getElementById('v1QuizNext').onclick=()=>{{if(index<questions.length-1){{index++;renderQuestion()}}}};
          document.getElementById('v1QuizExit').onclick=()=>{{if(!answers.size||confirm('确定退出测试吗？当前未提交答案不会保存。'))backToProfile()}};
          const submit=document.getElementById('v1QuizSubmit');if(submit)submit.onclick=async()=>{{if(answers.size!==questions.length){{toast('请完成全部题目后再提交');return}}submit.disabled=true;submit.textContent='正在提交…';try{{const payload={{answers:questions.map(item=>{{const saved=answers.get(item.id)||{{}};return v1ChoiceLike(item)?{{question_id:item.id,selected_index:saved.selected_index}}:{{question_id:item.id,text_answer:String(saved.text_answer||'').trim()}}}})}};const result=await api('/student/assignments/'+a.id+'/submit',{{method:'POST',body:JSON.stringify(payload)}});const paper=a.paper||{{}},subject=a.subject||paper.subject||'',textbook=a.textbook||paper.textbook||'',learning=Number(result.learningPointsAwarded||0),homework=Number(result.homeworkPointsAwarded||0),isHomework=!!result.homeworkPointsDetail,wrong=Math.max(0,Number(result.total||0)-Number(result.correct||0)),kind=String(a.title||'').includes('AI')?'AI 针对性练习':String(a.title||'').includes('综合测试')?'综合测试':(String(a.title||'').includes('专项')||String(a.title||'').includes('模块'))?'知识模块练习':'在线测试';const resultBody=heading(esc(a.title||'测试已完成'),'成绩已经写入当前学生的连续学习记录。')+'<section class="card" style="text-align:center"><div style="display:flex;gap:8px;justify-content:center;flex-wrap:wrap"><span class="tag">'+esc(kind)+'</span>'+(subject?'<span class="tag">'+esc(subject)+'</span>':'')+(textbook?'<span class="tag">'+esc(textbook)+'</span>':'')+'</div><strong style="display:block;font-size:48px;margin:18px 0 8px">'+esc(result.score)+' 分</strong><p>答对 '+esc(result.correct)+' / '+esc(result.total)+' 题 · 答错 '+esc(wrong)+' 题</p><p><span class="tag" style="background:#eefbf2;color:#247447;border-color:#cdebd7">'+(isHomework?'本次获得 '+(homework>=0?'+':'')+esc(homework)+' 晚托作业积分':'本次获得 +'+esc(learning)+' 学习积分')+'</span></p><button class="btn primary" id="v1QuizBackProfile" style="margin-top:18px">返回学生档案</button></section>';screen.innerHTML=shell(resultBody,'students');bindNav();document.getElementById('v1QuizBackProfile').onclick=backToProfile}}catch(err){{toast(err.message);submit.disabled=false;submit.textContent='提交测试'}}}};
        }};
        renderQuestion();
      }}catch(err){{toast(err.message||'无法打开测试')}}
    }}

    function bindV1StudentAssignments(assignments){{
      if(session.role!=='student')return;
      const card=[...document.querySelectorAll('.card')].find(node=>node.querySelector('h2')?.textContent.trim()==='作业情况');if(!card)return;
      const rows=card.querySelectorAll('.list .row');
      assignments.slice(0,6).forEach((a,i)=>{{const row=rows[i];if(!row||row.querySelector('.v1-start-assignment'))return;if((a.submissionMode||'quiz')==='media'||a.quizSubmitted)return;const b=document.createElement('button');b.type='button';b.className='btn primary v1-start-assignment';b.textContent=a.overdue?'补交测试':'开始测试';b.onclick=()=>openV1StudentAssignment(a.id);row.appendChild(b)}});
    }}
    async function studentPage(){{const id=Number(new URLSearchParams(location.search).get('id')||0);let people=[];try{{people=await loadPeople()}}catch(err){{}}if(!id){{const content=heading('学生','打开学生的长期连续发展档案。','<span class="tag">学生是独立实体</span>')+`<div class="list">${{people.map(p=>`<a class="row" data-student href="/v1/student?id=${{p.id}}"><span class="row-main"><b>${{esc(p.name)}}</b><small>${{esc(studentPosition(p))}}</small></span><span class="row-action">查看动态 →</span></a>`).join('')||'<div class="empty">暂无可见学生</div>'}}</div>`;screen.innerHTML=shell(content,'students');bindNav();document.querySelectorAll('[data-student]').forEach(a=>a.onclick=e=>{{e.preventDefault();navigate(a.getAttribute('href'))}});return}}
      let profile=null;try{{if(session.role==='teacher'||session.role==='admin')profile=await api('/teacher/students/'+id+'/growth-profile');else if(session.role==='parent'){{const progress=await api('/parent/children/'+id+'/progress');const assignments=await api('/parent/children/'+id+'/assignments');profile={{student:{{id,name:progress.studentName,grade:progress.grade,className:progress.className}},academic:{{avgScore:progress.avgScore,weakKnowledge:progress.knowledge||[],recentAssignments:assignments,pendingAssignments:assignments.filter(x=>!x.completed).length,overdueAssignments:assignments.filter(x=>x.overdue).length}},classHistory:progress.classHistory||[],timeline:[]}}}}else{{const progress=await api('/student/progress');const assignments=await api('/student/assignments');const learningTimeline=assignments.map(x=>{{const paper=x.paper||{{}},submitted=x.submittedAt||x.quizSubmittedAt||x.mediaSubmittedAt||'',assigned=x.assignedAt||x.createdAt||'',qn=(paper.questionIDs||[]).length,subject=x.subject||paper.subject||'',textbook=x.textbook||paper.textbook||'';return{{time:x.completed?(submitted||assigned||x.dueDate||''):(assigned||x.dueDate||''),title:(x.completed?'完成：':'布置：')+(x.title||'学习任务'),detail:[subject,textbook,qn?qn+'题':'',x.status||'',x.score!==null&&x.score!==undefined?x.score+'分':''].filter(Boolean).join(' · ')}}}});profile={{student:{{id:session.userID||session.id,name:session.name,grade:session.grade}},academic:{{avgScore:progress.avgScore,weakKnowledge:progress.knowledge||[],recentAssignments:assignments,pendingAssignments:assignments.filter(x=>!x.completed).length,overdueAssignments:assignments.filter(x=>x.overdue).length}},timeline:learningTimeline}}}}}}catch(err){{screen.innerHTML=shell(heading('学生动态','无法读取此学生档案')+`<div class="notice error">${{esc(err.message)}}</div>`,'students');bindNav();return}}
      const s=profile.student||{{}},a=profile.academic||{{}},weak=a.weakKnowledge||[],assignments=a.recentAssignments||[],timeline=profile.timeline||[],suggestions=profile.suggestions||[];const stage=(a.avgScore>=90?3:a.avgScore>=75?2:a.submissionCount>0?1:0);const content=heading('学生动态','围绕同一个学生 ID 汇总当前状态与历史变化。',`<span class="tag">档案编号 ${{esc(s.id||id)}}</span>`)+`<section class="card student-head"><h2>${{esc(s.name||'学生')}}</h2><p>${{esc(studentPosition(s))}}</p><div class="student-meta"><span class="tag">${{s.active===false?'已归档':'当前在读'}}</span><span class="tag">监护人 ${{s.parents?.length??'—'}}</span></div></section><section class="section grid cols-4"><div class="card kpi"><span>阶段成绩</span><strong>${{a.avgScore??'—'}}</strong><small>现有记录平均分</small></div><div class="card kpi"><span>待完成作业</span><strong>${{a.pendingAssignments??0}}</strong></div><div class="card kpi"><span>逾期作业</span><strong>${{a.overdueAssignments??0}}</strong></div><div class="card kpi"><span>最近变化</span><strong>${{timeline.length}}</strong><small>可见时间线事件</small></div></section><section class="section grid cols-2"><div class="card"><div class="section-head"><div><h2>掌握状态</h2><p>由事实记录逐步表达变化</p></div></div><div class="mastery">${{['不会','学习中','基本掌握','稳定掌握'].map((x,i)=>`<span class="${{i<=stage?'on':''}}">${{x}}</span>`).join('')}}</div><div class="notice warn" style="margin-top:14px">当前为 V1 展示规则，尚未作为智能诊断结论。</div></div><div class="card"><h2>需要关注 / 下一步教学</h2><div class="list" style="margin-top:12px">${{suggestions.slice(0,4).map(x=>`<div class="row"><span class="row-main"><b>${{esc(x)}}</b></span></div>`).join('')||'<div class="empty">暂无明确建议，继续积累课堂、作业与测验记录。</div>'}}</div></div></section><section class="section grid cols-2"><div class="card"><h2>作业情况</h2><div class="list" style="margin-top:12px">${{assignments.slice(0,6).map(x=>{{const paper=x.paper||{{}},subject=x.subject||paper.subject||'',textbook=x.textbook||paper.textbook||'',qn=x.questionCount??(paper.questionIDs||[]).length,assigned=x.assignedAt||x.createdAt||'',submitted=x.submittedAt||x.quizSubmittedAt||x.mediaSubmittedAt||'',kind=String(x.title||'').includes('AI')?'AI 针对性练习':String(x.title||'').includes('综合测试')?'综合测试':(String(x.title||'').includes('专项')||String(x.title||'').includes('模块'))?'知识模块练习':x.submissionModeName||'学习任务';return `<div class="row"><span class="row-main"><b>${{esc(x.title||'作业')}}</b><small>${{esc([subject,textbook,kind].filter(Boolean).join(' · '))}}</small><small>${{esc([assigned?'布置 '+assigned:'',x.dueDate?'截止 '+x.dueDate:'',submitted?'提交 '+submitted:'',x.assignedClassName?'班级 '+x.assignedClassName:'',qn?'题量 '+qn+'题':'',x.score!==null&&x.score!==undefined?'成绩 '+x.score+'分':''].filter(Boolean).join(' · '))}}</small></span><span class="tag">${{esc(x.status||((x.completed)?'已完成':'待完成'))}}</span></div>`}}).join('')||'<div class="empty">暂无作业记录</div>'}}</div></div><div class="card"><h2>薄弱内容 / 错题</h2><div class="list" style="margin-top:12px">${{weak.slice(0,6).map(x=>`<div class="row"><span class="row-main"><b>${{esc(x.knowledge||'知识点')}}</b><small>已答 ${{esc(x.answered??0)}} 题</small></span><span class="tag">${{esc(x.accuracy??0)}}%</span></div>`).join('')||'<div class="empty">暂无足够数据判断薄弱内容</div>'}}</div></div></section><section class="section"><div class="section-head"><div><h2>历史时间线</h2><p>换班、换老师或升年级后仍保留在同一档案</p></div><button class="btn" id="transitionLink">查看升学衔接</button></div><div class="card"><div class="timeline">${{timeline.slice(0,10).map(x=>`<div class="event"><time>${{esc(x.time||'')}}</time><b>${{esc(x.title||'教学记录')}}</b><p>${{esc(x.detail||'')}}</p></div>`).join('')||'<div class="empty">暂无时间线记录；后续教学记录将持续累积在这里。</div>'}}</div></div></section>`;screen.innerHTML=shell(content,'students');bindNav();document.getElementById('transitionLink').onclick=()=>navigate('/v1/transition?id='+id);if(session.role==='student')bindV1StudentAssignments(assignments);
    }}
    async function historyPage(){{let people=[];try{{people=await loadPeople()}}catch{{}}const content=heading('往期教学 / 历史','当前工作台只服务当前周期，结束内容按时间层级查询。','<span class="tag">只读查询</span>')+`<div class="grid cols-2"><section class="card"><h2>查询层级</h2><div class="list" style="margin-top:12px"><div class="row"><b>1 学年</b><span>2025—2026（演示）</span></div><div class="row"><b>2 学期 / 寒暑假</b><span>选择教学周期</span></div><div class="row"><b>3 班级或教学项目</b><span>按当时归属查询</span></div><div class="row"><b>4 学生</b><span>回到连续个人档案</span></div><div class="row"><b>5 教学记录</b><span>作业、成绩、跟进</span></div></div></section><section class="card"><h2>已有班级历史</h2><p>${{session.demo?'下列为明确标注的演示占位学生，点击查看连续档案。':'下列学生来自当前账号真实可见范围，点击查看其连续档案。'}}</p><div class="list" style="margin-top:12px">${{people.slice(0,8).map(p=>`<a class="row" data-student href="/v1/student?id=${{p.id}}"><span class="row-main"><b>${{esc(p.name)}}</b><small>${{esc(p.className||p.currentClassName||'历史教学待查询')}}</small></span><span class="row-action">打开档案 →</span></a>`).join('')||'<div class="empty">暂无可见历史数据</div>'}}</div></section></div>`;screen.innerHTML=shell(content,'history');bindNav();document.querySelectorAll('[data-student]').forEach(a=>a.onclick=e=>{{e.preventDefault();navigate(a.getAttribute('href'))}})}}
    function transitionPage(){{const id=new URLSearchParams(location.search).get('id')||'';const types=['幼升小','低段到中段','中段到高段','五升六','小升初'];const stages=['上一阶段状态','下一阶段要求','前置知识检查','差距识别','衔接计划','假期干预','开学诊断','下一阶段'];const content=heading('升年级与升学衔接','围绕同一份学生档案记录阶段变化，不因升年级创建新学生。',id?`<span class="tag">学生档案 #${{esc(id)}}</span>`:'<span class="tag demo">结构占位</span>')+`<section class="card"><div class="section-head"><div><h2>衔接类型</h2><p>V1 预留结构，尚未启用自动分析</p></div></div><div style="display:flex;gap:8px;flex-wrap:wrap">${{types.map(x=>`<button class="btn" data-transition>${{x}}</button>`).join('')}}</div></section><section class="section"><div class="section-head"><div><h2>衔接流程</h2><p>未来每一步都引用同一个 student_id</p></div></div><div class="steps">${{stages.map((x,i)=>`<div class="step placeholder"><em>STEP ${{String(i+1).padStart(2,'0')}}</em><b>${{x}}</b><small>${{i===0?'读取已有档案事实':'待教师录入或后续规则支持'}}</small></div>`).join('')}}</div></section>`;screen.innerHTML=shell(content,'transition');bindNav();document.querySelectorAll('[data-transition]').forEach(b=>b.onclick=()=>toast(b.textContent+'：入口已预留'))}}
    async function render(){{if(!token){{loginView();return}}if(!session){{try{{session=await api('/session');persistAuth({{...session,token}},authRemember())}}catch(err){{token='';clearAuthStorage();loginView(err.status===401?'登录已过期，请重新登录':err.message);return}}}}if(session?.mustChangePassword){{toast('请先修改初始密码');await openClassic('/v1/tool?page=account');return}}const choices=identitiesFor(session),saved=localStorage.getItem(IDENTITY_KEY);identity=choices.find(x=>x.key===saved)||null;if(!identity){{pendingIdentityReturnPath=identityReturnPath();chooseIdentity();return}}chip.textContent=identity.label+' · '+(session.name||'');identityButton.hidden=false;const path=location.pathname;if(path==='/v1'||path==='/v1/'){{pendingIdentityReturnPath='';chooseIdentity();return}}if(path.includes('/student'))await studentPage();else if(path.includes('/history'))await historyPage();else if(path.includes('/transition'))transitionPage();else await workspace()}}
    identityButton.onclick=chooseIdentity;window.addEventListener('popstate',async()=>{{if(await ensureFreshBuild(location.pathname+location.search))return;render()}});document.addEventListener('visibilitychange',()=>{{if(!document.hidden)ensureFreshBuild(location.pathname+location.search)}});document.addEventListener('click',e=>{{const classic=e.target.closest('a[href^="/v1/tool"],a[href^="/classic"]');if(classic&&token&&token!=='demo'){{e.preventDefault();openClassic(classic.getAttribute('href'));return}}const a=e.target.closest('a[data-nav]');if(a){{e.preventDefault();navigate(a.getAttribute('href'))}}}});render();
  }})();
  </script>
  <script src="/v1/personal-home.js"></script>
</body>
</html>'''


def install_v1_routes(app: FastAPI) -> None:
    """Install the V1 experience without replacing the legacy application."""
    if getattr(app.state, "v1_routes_installed", False):
        return

    router = APIRouter()

    def response() -> HTMLResponse:
        return HTMLResponse(
            v1_html(),
            headers={
                "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                "X-Changying-V1": V1_UI_MARKER,
                "X-Changying-V1-Build": current_v1_build_id(),
            },
        )

    @router.get("/v1/personal-home.js", include_in_schema=False)
    def personal_home_script():
        """Send a personal workspace to the quick page on first paint.

        Kept as an external file on purpose: the Safari 12 builder ignores
        <script src=...>, so adding this cannot invalidate the shared asset manifest.
        """
        return Response(
            PERSONAL_HOME_JS,
            media_type="application/javascript; charset=utf-8",
            headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"},
        )

    @router.get("/v1/version", include_in_schema=False)
    def v1_version():
        return JSONResponse(
            {"build": current_v1_build_id()},
            headers={
                "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                "Pragma": "no-cache",
                "Expires": "0",
            },
        )

    def personal_home(request: Request):
        """A personal workspace lands on the quick page instead of the school console.

        The cookie is set at login; it only decides where /v1 sends the browser.
        """
        if request.cookies.get(PERSONAL_HOME_COOKIE) == "1":
            return RedirectResponse("/start", status_code=307, headers={"Cache-Control": "no-store"})
        return response()

    for path in V1_PATHS:
        handler = personal_home if path == "/v1" else response
        router.add_api_route(path, handler, methods=["GET"], include_in_schema=False)
    app.include_router(router)
    app.state.v1_routes_installed = True


__all__ = ["V1_PATHS", "V1_UI_MARKER", "current_v1_build_id", "install_v1_routes", "v1_html"]
