"""Top-level V1 chrome for mature Classic workflows.

Mobile Safari repeatedly proved unreliable when the legacy application was
started inside an iframe because Classic keeps authentication state in the
browsing context's sessionStorage. This module keeps Classic as the top-level
same-origin document, where its existing auth/session lifecycle works normally,
then adds the V1 navigation chrome around it.
"""
from __future__ import annotations

from changying.web.v1_cinematic import cinematic_snippet
from changying.web.v1_ribbon_banner import BRAND_FONT_B64, RIBBON_SVG_JSON

V1_CLASSIC_UNIFIED_MARKER = "changying_v1_classic_unified_top_v1"

V1_CLASSIC_LOGIN_GUARD_MARKER = "changying_v1_classic_login_guard_v1"

# Arriving from V1 the Classic document first renders its own login screen and
# only then hydrates the session handed over by V1, so every "全部功能" switch
# flashed the old login page. Keep it hidden until hydration has settled; the
# timer is a failsafe so a genuinely signed-out visitor still gets the login form.
V1_CLASSIC_LOGIN_GUARD = r'''
<style id="changying_v1_classic_login_guard_v1-style">html.cy-v1-login-pending #loginScreen{visibility:hidden!important}</style>
<script id="changying_v1_classic_login_guard_v1-script">
(function(){var p=new URLSearchParams(location.search);
 if(p.get('unified')!=='1'||p.get('from')!=='v1')return;
 var h=document.documentElement;h.classList.add('cy-v1-login-pending');
 window.__cyV1ReleaseLogin=function(){h.classList.remove('cy-v1-login-pending')};
 setTimeout(window.__cyV1ReleaseLogin,5000);
})();
</script>
'''

V1_CLASSIC_UNIFIED_SNIPPET = r'''
<style id="changying_v1_classic_unified_top_v1-style">
@font-face{font-family:CyBrand;src:url(data:font/woff2;base64,__BRAND_FONT_B64__) format('woff2');font-display:swap}
html.cy-v1-unified{--cy-v1-navy:#a8101c;--cy-v1-ink:#172033;--cy-v1-muted:#7a625c;--cy-v1-line:#eadfd8;--cy-v1-soft:#fbf6f2;--cy-v1-shadow:0 8px 30px rgba(168,16,28,.06);--primary:#a8101c;--p:#a8101c;--soft:#fdebe7;--bg:#f8f3ee;--line:#eadfd8;--shadow:0 14px 38px rgba(168,16,28,.10)}
html.cy-v1-unified body{background:#f8f3ee!important;color:var(--cy-v1-ink)!important;padding-top:88px!important;padding-bottom:86px!important;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif!important;-webkit-text-size-adjust:100%}
html.cy-v1-unified .sidebar,html.cy-v1-unified .mobile-header,html.cy-v1-unified .bottom-nav,html.cy-v1-unified #changying_classic_ui_v2-ribbon,html.cy-v1-unified #changying_classic_ui_v2-workflow,html.cy-v1-unified .cy-classic-ribbon,html.cy-v1-unified .cy-workflow-panel{display:none!important}
html.cy-v1-unified .shell:not(.hidden){display:block!important;min-height:calc(100dvh - 152px)!important}
html.cy-v1-unified .main{margin:0 auto!important;max-width:1180px!important;width:100%!important;padding:28px clamp(16px,3.4vw,46px) 52px!important;min-height:calc(100dvh - 152px)!important;background:transparent!important}
html.cy-v1-unified .page-head{margin:0 0 22px!important;display:flex!important;align-items:flex-end!important;justify-content:space-between!important;gap:16px!important}
html.cy-v1-unified .page-head h1,html.cy-v1-unified h1{color:var(--cy-v1-ink)!important;letter-spacing:-.035em!important;font-weight:900!important}
html.cy-v1-unified .page-head p,html.cy-v1-unified .subtitle,html.cy-v1-unified .muted{color:var(--cy-v1-muted)!important}
html.cy-v1-unified .card,html.cy-v1-unified .panel,html.cy-v1-unified .box,html.cy-v1-unified .class-card,html.cy-v1-unified .student-card,html.cy-v1-unified .list-card,html.cy-v1-unified .stat-card{background:#fff!important;border:1px solid var(--cy-v1-line)!important;border-radius:18px!important;box-shadow:var(--cy-v1-shadow)!important}
html.cy-v1-unified .card,html.cy-v1-unified .panel,html.cy-v1-unified .box{padding:18px!important}
html.cy-v1-unified button,html.cy-v1-unified .btn,html.cy-v1-unified [role="button"]{border-radius:12px!important;font-family:inherit!important;font-weight:750!important;box-shadow:none!important}
html.cy-v1-unified button.primary,html.cy-v1-unified .btn.primary,html.cy-v1-unified .btn-primary{background:var(--cy-v1-navy)!important;color:#fff!important;border-color:var(--cy-v1-navy)!important}
html.cy-v1-unified input:not([type="checkbox"]):not([type="radio"]),html.cy-v1-unified select,html.cy-v1-unified textarea{border:1px solid #cfd7e5!important;border-radius:12px!important;background:#fff!important;color:var(--cy-v1-ink)!important;font-family:inherit!important}
#cy-v1-unified-top{position:fixed;left:0;right:0;top:0;height:88px;z-index:2147483600;display:flex;align-items:center;gap:12px;padding:0 clamp(16px,4vw,42px);overflow:hidden;background:radial-gradient(110% 240% at 6% -50%,rgba(255,222,160,.6),transparent 56%),linear-gradient(100deg,#a8101c 0%,#d9352a 36%,#ee7a38 64%,#c92a2c 100%);color:#fff;box-shadow:0 8px 22px rgba(168,16,28,.28);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif}
#cy-v1-unified-top .cy-ribbon{position:absolute;inset:0;width:100%;height:100%;pointer-events:none;z-index:0}#cy-v1-unified-top>:not(.cy-ribbon){position:relative;z-index:1}
#cy-v1-unified-top .cy-v1-brand{display:flex;align-items:center;text-decoration:none;color:#fff;white-space:nowrap}#cy-v1-unified-top .cy-v1-brand-text{font-family:CyBrand,'STXingkai','Xingkai SC','Kaiti SC',KaiTi,serif;font-size:46px;font-weight:400;letter-spacing:.14em;text-shadow:0 2px 8px rgba(100,0,10,.4)}#cy-v1-unified-top .cy-v1-spacer{flex:1}#cy-v1-unified-identity{font-size:12px;color:#fff;background:rgba(255,255,255,.2);border:1px solid rgba(255,255,255,.45);border-radius:999px;padding:7px 10px;max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}#cy-v1-unified-picker{min-width:180px;max-width:280px;border:1px solid rgba(255,255,255,.5)!important;border-radius:12px!important;background:rgba(255,255,255,.18)!important;color:#fff!important;padding:9px 34px 9px 11px!important;font:inherit!important}#cy-v1-unified-picker option{color:#172033}#cy-v1-unified-bottom{display:none}
#cy-v1-switch-account{border:1px solid rgba(255,255,255,.5)!important;background:rgba(255,255,255,.18)!important;color:#fff!important;padding:8px 10px!important;white-space:nowrap}
#cy-v1-tool-hub{position:fixed;inset:0;z-index:2147483640;background:rgba(17,24,39,.38);display:grid;place-items:end center;padding:16px}
#cy-v1-tool-hub[hidden]{display:none!important}#cy-v1-tool-hub-card{width:min(720px,100%);max-height:min(78dvh,760px);overflow:auto;background:#fff;border:1px solid #eadfd8;border-radius:22px;padding:18px;box-shadow:0 24px 80px rgba(168,16,28,.24)}
#cy-v1-tool-hub-head{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:14px}#cy-v1-tool-hub-head h2{margin:0;font-size:22px}#cy-v1-tool-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}
#cy-v1-tool-grid button{min-height:48px;background:#fbf6f2!important;border:1px solid #eadfd8!important;color:#172033!important;text-align:left;padding:11px 13px!important}
#cy-v1-tool-grid button strong{display:block;font-size:14px}#cy-v1-tool-account{margin-top:14px;padding-top:14px;border-top:1px solid #eadfd8;display:flex;gap:10px;align-items:center;justify-content:space-between}#cy-v1-tool-account small{color:#667085;line-height:1.45}
@media(max-width:720px){html.cy-v1-unified body{padding-top:68px!important;padding-bottom:82px!important}html.cy-v1-unified .main{padding:20px 14px calc(104px + env(safe-area-inset-bottom))!important;min-height:calc(100dvh - 142px)!important}html.cy-v1-unified #page>.page-head:first-child{margin-top:34px!important}html.cy-v1-unified .page-head{align-items:flex-start!important;flex-direction:column!important;margin-bottom:20px!important}html.cy-v1-unified .page-head h1{font-size:25px!important}#cy-v1-unified-top{height:68px;padding:0 12px;gap:8px}#cy-v1-unified-top .cy-v1-brand-text{font-size:30px;letter-spacing:.1em}#cy-v1-unified-identity{display:inline-flex;max-width:118px;padding:6px 8px;font-size:11px}#cy-v1-unified-picker{display:none!important}#cy-v1-switch-account{font-size:11px!important;padding:7px 8px!important}#cy-v1-tool-hub{padding:8px}#cy-v1-tool-hub-card{border-radius:20px;padding:15px;max-height:82dvh}#cy-v1-tool-grid{grid-template-columns:1fr}#cy-v1-unified-bottom{position:fixed;display:grid;grid-template-columns:repeat(auto-fit,minmax(0,1fr));left:8px;right:8px;bottom:max(8px,env(safe-area-inset-bottom));z-index:2147483600;background:rgba(255,255,255,.98);border:1px solid #eadfd8;border-radius:18px;padding:5px 6px;box-shadow:0 14px 40px rgba(168,16,28,.16);backdrop-filter:blur(14px);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif}#cy-v1-unified-bottom a{text-decoration:none;text-align:center;font-size:10px;color:#5f6b7e;padding:4px 1px;border-radius:10px}#cy-v1-unified-bottom a span{display:block;font-size:16px;margin-bottom:1px}#cy-v1-unified-bottom a.active{background:#fdebe7;color:#a8101c;font-weight:800}}
</style>
<script id="changying_v1_classic_unified_top_v1-script">
(function(){
 var params=new URLSearchParams(location.search);if(params.get('unified')!=='1')return;
 document.documentElement.classList.add('cy-v1-unified');
 var menus={teacher:[['classes','班级学生'],['classPoints','课堂积分'],['ai','AI 助手'],['teaching','定制教学'],['resources','教材教案'],['catalog','教材题库'],['papers','组卷作业'],['analytics','学情分析'],['audit','操作记录'],['leaderboard','排行榜'],['account','我的']],student:[['syncLearning','同步课堂'],['rewards','积分奖励'],['assignments','我的作业'],['wrongbook','我的错题'],['practice','自主练习'],['progress','我的学情'],['leaderboard','班级排行'],['account','我的']],parent:[['childLearning','孩子课程'],['childRewards','课堂表现'],['childProgress','孩子学情'],['childAssignments','孩子作业'],['account','我的']],admin:[['admin','平台总览'],['subscription','套餐授权'],['users','账号管理'],['pointsAdmin','积分奖励'],['ai','AI 设置'],['teaching','定制教学'],['resources','教材教案'],['imports','批量导入'],['catalog','教材题库'],['adminAudit','全校审计'],['system','系统设置']]};
 var quickMenus={
  teacher:[['workspace','▦','当前教学','/v1/workspace'],['tools','⌘','全部功能','/v1/workspace?view=all']],
  student:[['syncLearning','▦','课堂','syncLearning'],['assignments','✓','作业','assignments'],['practice','✎','练习','practice'],['progress','◉','学情','progress'],['tools','☰','更多','#']],
  parent:[['childLearning','▦','孩子课程','childLearning'],['childAssignments','✓','孩子作业','childAssignments'],['childProgress','◉','孩子学情','childProgress'],['childRewards','★','课堂表现','childRewards'],['account','⌘','我的','account']],
  admin:[['admin','▦','平台总览','admin'],['users','◉','账号管理','users'],['pointsAdmin','★','积分奖励','pointsAdmin'],['adminAudit','◷','全校审计','adminAudit'],['system','⌘','系统设置','system']]
 };
 function stateReady(){try{return typeof state!=='undefined'&&!!state.token&&!!state.user}catch(_e){return false}}
 function currentRole(){try{return String(state.user&&state.user.role||'teacher')}catch(_e){return 'teacher'}}
 function currentName(){try{return String(state.user&&state.user.name||'当前账号')}catch(_e){return '当前账号'}}
 function currentPage(){try{return String(state.page||params.get('page')||'')}catch(_e){return String(params.get('page')||'')}}
 function v1Token(){try{var remember=localStorage.getItem('v717Remember')==='1';return (remember?localStorage.getItem('v717Token'):sessionStorage.getItem('v717Token'))||sessionStorage.getItem('v717Token')||localStorage.getItem('v717Token')||sessionStorage.getItem('v6Token')||localStorage.getItem('v6Token')||''}catch(_e){return ''}}
 async function consumeV1Handoff(){try{var r=await fetch('/v1/auth-handoff/consume',{method:'POST',cache:'no-store',credentials:'same-origin'});if(!r.ok)return null;return await r.json()}catch(_e){return null}}
 function switchAccount(){try{if(typeof clearAuth==='function')clearAuth()}catch(_e){}try{localStorage.removeItem('cyV1Identity')}catch(_e){}location.replace('/v1')}
 function hideToolHub(){var hub=document.getElementById('cy-v1-tool-hub');if(hub)hub.hidden=true}
 function openToolPage(page){if(!page)return;try{if(typeof roleAllowsPage==='function'&&!roleAllowsPage(page))return}catch(_e){}hideToolHub();try{if(typeof go==='function'){go(page);var u=new URL(location.href);u.searchParams.delete('from');u.searchParams.set('legacy','1');u.searchParams.set('unified','1');u.searchParams.set('page',page);history.replaceState(null,'',u.pathname+u.search);sync();return}}catch(_e){}location.href='/classic?legacy=1&unified=1&page='+encodeURIComponent(page)}
 function showToolHub(){var hub=document.getElementById('cy-v1-tool-hub');if(!hub){hub=document.createElement('div');hub.id='cy-v1-tool-hub';hub.hidden=true;hub.innerHTML='<section id="cy-v1-tool-hub-card" role="dialog" aria-modal="true" aria-labelledby="cy-v1-tool-hub-title"><div id="cy-v1-tool-hub-head"><h2 id="cy-v1-tool-hub-title">全部功能</h2><button type="button" id="cy-v1-tool-hub-close">关闭</button></div><div id="cy-v1-tool-grid"></div><div id="cy-v1-tool-account"><small>需要更换教师、学生或家长账号时，请使用“切换账号”。</small><button type="button" id="cy-v1-tool-switch-account">切换账号</button></div></section>';document.body.appendChild(hub);hub.onclick=function(e){if(e.target===hub)hideToolHub()};document.getElementById('cy-v1-tool-hub-close').onclick=hideToolHub;document.getElementById('cy-v1-tool-switch-account').onclick=switchAccount}var role=currentRole(),items=menus[role]||menus.teacher,grid=document.getElementById('cy-v1-tool-grid');grid.innerHTML=items.map(function(x){return '<button type="button" data-tool-page="'+x[0]+'"><strong>'+x[1]+'</strong></button>'}).join('');grid.querySelectorAll('[data-tool-page]').forEach(function(b){b.onclick=function(){openToolPage(b.getAttribute('data-tool-page'))}});hub.hidden=false}
 function mount(){if(document.getElementById('cy-v1-unified-top'))return;var top=document.createElement('header');top.id='cy-v1-unified-top';top.innerHTML=__RIBBON_JSON__+'<a class="cy-v1-brand" href="/v1/workspace"><span class="cy-v1-brand-text">长缨辅学</span></a><span class="cy-v1-spacer"></span><span id="cy-v1-unified-identity">正在识别身份</span><select id="cy-v1-unified-picker" aria-label="切换功能"></select><button type="button" id="cy-v1-switch-account">切换账号</button>';document.body.insertBefore(top,document.body.firstChild);var bottom=document.createElement('nav');bottom.id='cy-v1-unified-bottom';document.body.appendChild(bottom);document.getElementById('cy-v1-switch-account').onclick=switchAccount;var picker=document.getElementById('cy-v1-unified-picker');picker.addEventListener('change',function(){openToolPage(picker.value)})}
 function sync(){mount();var role=currentRole(),items=menus[role]||menus.teacher,picker=document.getElementById('cy-v1-unified-picker'),identity=document.getElementById('cy-v1-unified-identity'),bottom=document.getElementById('cy-v1-unified-bottom');if(!picker||!identity||!bottom)return;var old=picker.value,html=items.map(function(x){return '<option value="'+x[0]+'">'+x[1]+'</option>'}).join('');if(picker.innerHTML!==html)picker.innerHTML=html;var page=currentPage();picker.value=items.some(function(x){return x[0]===page})?page:(old||items[0][0]);identity.textContent=currentName()+' · '+({teacher:'教师',student:'学生',parent:'家长',admin:'管理员'}[role]||role);var quick=quickMenus[role]||quickMenus.teacher;bottom.innerHTML=quick.map(function(x){var hub=x[0]==='tools'&&x[3]==='#',internal=!hub&&x[3].charAt(0)!=='/',href=hub?'#':(internal?'/classic?legacy=1&unified=1&page='+encodeURIComponent(x[3]):x[3]),active=(x[3]===page)||(hub&&params.get('page')==='__hub__');return '<a '+(active?'class="active" ':'')+(hub?'data-tool-hub="1" ':(internal?'data-classic-page="'+x[3]+'" ':''))+'href="'+href+'"><span>'+x[1]+'</span>'+x[2]+'</a>'}).join('');bottom.querySelectorAll('a[data-tool-hub]').forEach(function(a){a.onclick=function(e){e.preventDefault();showToolHub()}});bottom.querySelectorAll('a[data-classic-page]').forEach(function(a){a.onclick=function(e){e.preventDefault();openToolPage(a.getAttribute('data-classic-page'))}})}
 function clearV1FromMarker(){try{var u=new URL(location.href);if(u.searchParams.get('from')==='v1'){u.searchParams.delete('from');history.replaceState(null,'',u.pathname+u.search)}}catch(_e){}}
 async function hydrateFromV1(){
  var fromV1=params.get('from')==='v1',bridge=null,t='',s=null;
  if(fromV1)bridge=await consumeV1Handoff();
  if(bridge&&bridge.token){t=String(bridge.token);s=bridge}
  else if(stateReady()){
   try{try{if(typeof markNetwork==='function')markNetwork(true)}catch(_e){}if(typeof validateSavedSession==='function'){var savedOk=await Promise.resolve(validateSavedSession());if(!savedOk)return false}else if(typeof enter==='function'){enter()}clearV1FromMarker();sync();return true}catch(_e){return false}
  }else{t=v1Token()}
  if(!t||t==='demo')return false;
  try{if(!s){var r=await fetch('/session',{headers:{Authorization:'Bearer '+t},cache:'no-store'});if(!r.ok)return false;s=await r.json()}var u={id:s.userID??s.id??null,name:s.name||'',role:s.role||'teacher',grade:s.grade??null,subscription:s.subscription||null};if(typeof state==='undefined')return false;state.token=t;state.user=u;state.remember=localStorage.getItem('v717Remember')==='1';try{if(typeof saveAuth==='function')saveAuth()}catch(_e){}try{if(typeof markNetwork==='function')markNetwork(true)}catch(_e){}if(typeof validateSavedSession==='function'){var ok=await Promise.resolve(validateSavedSession());if(!ok)return false}else if(typeof enter==='function'){enter()}clearV1FromMarker();sync();return true}catch(_e){return false}
 }
 function autoResume(){if(window.__cyV1UnifiedAutoResume)return;try{var btn=document.getElementById('continueSessionBtn');if(!btn||btn.classList.contains('hidden'))return;window.__cyV1UnifiedAutoResume=true;if(typeof markNetwork==='function')markNetwork(true);btn.click()}catch(_e){}}
 function releaseLogin(){if(typeof window.__cyV1ReleaseLogin==='function')window.__cyV1ReleaseLogin()}
 async function start(){mount();sync();var hydrated=await hydrateFromV1();if(!hydrated)autoResume();sync();if(hydrated||!window.__cyV1UnifiedAutoResume)releaseLogin();if(hydrated&&stateReady()&&params.get('page')==='__hub__')showToolHub();var tries=0,t=setInterval(function(){sync();if(!stateReady())autoResume();if(stateReady()){releaseLogin();clearInterval(t)}else if(++tries>80){releaseLogin();clearInterval(t)}},100);setTimeout(function(){if(!stateReady())autoResume()},250)}
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start,{once:true});else start();
})();
</script>
'''




_ASSIGNMENT_RECORD_OLD = r'''<small>${esc(a.assignedClassName||"")} · ${esc(a.submissionModeName||"在线答题")} · 截止 ${esc(a.dueDate)}${a.score!==null?` · 成绩 ${a.score}分`:""}</small>'''
_ASSIGNMENT_RECORD_NEW = r'''<small>${esc(a.paper?.subject||"未标科目")} · ${esc(a.paper?.textbook||"")} · ${esc(a.assignedClassName||"")} · ${(a.paper?.questionIDs||[]).length}题</small><small style="display:block;margin-top:4px">布置 ${esc(a.assignedAt||"时间未记录")} · 截止 ${esc(a.dueDate||"未设置")}${a.quizSubmittedAt?` · 提交 ${esc(a.quizSubmittedAt)}`:""}${a.score!==null?` · 成绩 ${a.score}分`:""}</small>'''

_PROGRESS_RECORD_OLD = r'''<p>${esc(latest.title||"最近练习")} · ${esc(latest.submittedAt||"")}</p>'''
_PROGRESS_RECORD_NEW = r'''<p>${[latest.subject,latest.textbook,latest.title].filter(Boolean).map(esc).join(" · ")} · 提交 ${esc(latest.submittedAt||"时间未记录")}</p>'''


def _polish_student_record_detail(html: str) -> str:
    html = html.replace(_ASSIGNMENT_RECORD_OLD, _ASSIGNMENT_RECORD_NEW, 1)
    html = html.replace(_PROGRESS_RECORD_OLD, _PROGRESS_RECORD_NEW, 1)
    return html

def inject_v1_classic_unified(html: str) -> str:
    if V1_CLASSIC_UNIFIED_MARKER in html:
        return html
    html = _polish_student_record_detail(html)
    if V1_CLASSIC_LOGIN_GUARD_MARKER not in html:
        guard = V1_CLASSIC_LOGIN_GUARD + f"<!-- {V1_CLASSIC_LOGIN_GUARD_MARKER} -->"
        html = html.replace("<head>", "<head>" + guard, 1) if "<head>" in html else guard + html
    snippet = V1_CLASSIC_UNIFIED_SNIPPET.replace("__BRAND_FONT_B64__", BRAND_FONT_B64).replace("__RIBBON_JSON__", RIBBON_SVG_JSON)
    marker = snippet + f"\n<!-- {V1_CLASSIC_UNIFIED_MARKER} -->" + cinematic_snippet()
    return html.replace("</body>", marker + "</body>", 1) if "</body>" in html else html + marker


__all__ = ["V1_CLASSIC_LOGIN_GUARD_MARKER", "V1_CLASSIC_UNIFIED_MARKER", "inject_v1_classic_unified"]