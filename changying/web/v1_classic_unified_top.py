"""Top-level V1 chrome for mature Classic workflows.

Mobile Safari repeatedly proved unreliable when the legacy application was
started inside an iframe because Classic keeps authentication state in the
browsing context's sessionStorage. This module keeps Classic as the top-level
same-origin document, where its existing auth/session lifecycle works normally,
then adds the V1 navigation chrome around it.
"""
from __future__ import annotations

V1_CLASSIC_UNIFIED_MARKER = "changying_v1_classic_unified_top_v1"

V1_CLASSIC_UNIFIED_SNIPPET = r'''
<style id="changying_v1_classic_unified_top_v1-style">
html.cy-v1-unified{--cy-v1-navy:#173c78;--cy-v1-ink:#172033;--cy-v1-muted:#667085;--cy-v1-line:#e4e9f2;--cy-v1-soft:#f5f7fb;--cy-v1-shadow:0 8px 30px rgba(23,60,120,.04)}
html.cy-v1-unified body{background:#f3f6fb!important;color:var(--cy-v1-ink)!important;padding-top:66px!important;padding-bottom:86px!important;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif!important;-webkit-text-size-adjust:100%}
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
#cy-v1-unified-top{position:fixed;left:0;right:0;top:0;height:66px;z-index:2147483600;display:flex;align-items:center;gap:12px;padding:0 16px;background:rgba(255,255,255,.98);border-bottom:1px solid #e4e9f2;box-shadow:0 8px 24px rgba(23,60,120,.06);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif}
#cy-v1-unified-top .cy-v1-brand{display:flex;align-items:center;gap:10px;text-decoration:none;color:#172033;font-weight:900;white-space:nowrap}#cy-v1-unified-top .cy-v1-mark{width:40px;height:40px;border-radius:13px;display:grid;place-items:center;background:#173c78;color:white;font-size:21px}#cy-v1-unified-top .cy-v1-spacer{flex:1}#cy-v1-unified-identity{font-size:12px;color:#173c78;background:#edf3ff;border:1px solid #dbe7ff;border-radius:999px;padding:7px 10px;max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}#cy-v1-unified-picker{min-width:180px;max-width:280px;border:1px solid #d5deec!important;border-radius:12px!important;background:#fff!important;color:#172033!important;padding:9px 34px 9px 11px!important;font:inherit!important}#cy-v1-unified-bottom{display:none}
@media(max-width:720px){html.cy-v1-unified body{padding-top:60px!important;padding-bottom:82px!important}html.cy-v1-unified .main{padding:20px 14px calc(104px + env(safe-area-inset-bottom))!important;min-height:calc(100dvh - 142px)!important}html.cy-v1-unified .page-head{align-items:flex-start!important;flex-direction:column!important;margin-bottom:20px!important}html.cy-v1-unified .page-head h1{font-size:25px!important}#cy-v1-unified-top{height:60px;padding:0 12px;gap:8px}#cy-v1-unified-top .cy-v1-mark{width:38px;height:38px}#cy-v1-unified-top .cy-v1-brand-text,#cy-v1-unified-identity{display:none}#cy-v1-unified-picker{flex:1;min-width:0;max-width:none;font-size:14px!important;padding:8px 30px 8px 10px!important}#cy-v1-unified-bottom{position:fixed;display:grid;grid-template-columns:repeat(5,1fr);left:8px;right:8px;bottom:max(8px,env(safe-area-inset-bottom));z-index:2147483600;background:rgba(255,255,255,.98);border:1px solid #e4e9f2;border-radius:18px;padding:5px 6px;box-shadow:0 14px 40px rgba(23,60,120,.16);backdrop-filter:blur(14px);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif}#cy-v1-unified-bottom a{text-decoration:none;text-align:center;font-size:10px;color:#5f6b7e;padding:4px 1px;border-radius:10px}#cy-v1-unified-bottom a span{display:block;font-size:16px;margin-bottom:1px}#cy-v1-unified-bottom a.active{background:#eaf1ff;color:#173c78;font-weight:800}}
</style>
<script id="changying_v1_classic_unified_top_v1-script">
(function(){
 var params=new URLSearchParams(location.search);if(params.get('unified')!=='1')return;
 document.documentElement.classList.add('cy-v1-unified');
 var menus={teacher:[['classes','班级学生'],['classPoints','课堂积分'],['ai','AI 助手'],['teaching','定制教学'],['resources','教材教案'],['catalog','教材题库'],['papers','组卷作业'],['analytics','学情分析'],['audit','操作记录'],['leaderboard','排行榜'],['account','我的']],student:[['syncLearning','同步课堂'],['rewards','积分奖励'],['assignments','我的作业'],['wrongbook','我的错题'],['practice','自主练习'],['progress','我的学情'],['leaderboard','班级排行'],['account','我的']],parent:[['childLearning','孩子课程'],['childRewards','课堂表现'],['childProgress','孩子学情'],['childAssignments','孩子作业'],['account','我的']],admin:[['admin','平台总览'],['subscription','套餐授权'],['users','账号管理'],['pointsAdmin','积分奖励'],['ai','AI 设置'],['teaching','定制教学'],['resources','教材教案'],['imports','批量导入'],['catalog','教材题库'],['adminAudit','全校审计'],['system','系统设置']]};
 function stateReady(){try{return typeof state!=='undefined'&&!!state.token&&!!state.user}catch(_e){return false}}
 function currentRole(){try{return String(state.user&&state.user.role||'teacher')}catch(_e){return 'teacher'}}
 function currentName(){try{return String(state.user&&state.user.name||'当前账号')}catch(_e){return '当前账号'}}
 function currentPage(){try{return String(state.page||params.get('page')||'')}catch(_e){return String(params.get('page')||'')}}
 function v1Token(){try{return localStorage.getItem('v717Token')||sessionStorage.getItem('v717Token')||localStorage.getItem('v6Token')||sessionStorage.getItem('v6Token')||''}catch(_e){return ''}}
 async function consumeV1Handoff(){try{var r=await fetch('/v1/auth-handoff/consume',{method:'POST',cache:'no-store',credentials:'same-origin'});if(!r.ok)return null;return await r.json()}catch(_e){return null}}
 function mount(){if(document.getElementById('cy-v1-unified-top'))return;var top=document.createElement('header');top.id='cy-v1-unified-top';top.innerHTML='<a class="cy-v1-brand" href="/v1/workspace"><span class="cy-v1-mark">长</span><span class="cy-v1-brand-text">长缨辅学</span></a><span class="cy-v1-spacer"></span><span id="cy-v1-unified-identity">正在识别身份</span><select id="cy-v1-unified-picker" aria-label="切换功能"></select>';document.body.insertBefore(top,document.body.firstChild);var bottom=document.createElement('nav');bottom.id='cy-v1-unified-bottom';bottom.innerHTML='<a href="/v1/workspace"><span>▦</span>当前教学</a><a href="/v1/student"><span>◉</span>学生</a><a href="/v1/history"><span>◷</span>往期教学</a><a href="/v1/transition"><span>↗</span>升学衔接</a><a class="active" href="/v1/tool"><span>⌘</span>全部功能</a>';document.body.appendChild(bottom);var picker=document.getElementById('cy-v1-unified-picker');picker.addEventListener('change',function(){var page=picker.value;if(!page)return;try{if(typeof roleAllowsPage==='function'&&!roleAllowsPage(page))return}catch(_e){}try{if(typeof go==='function'){go(page);var u=new URL(location.href);u.searchParams.set('page',page);history.replaceState(null,'',u.pathname+u.search);return}}catch(_e){}location.href='/classic?legacy=1&unified=1&from=v1&page='+encodeURIComponent(page)})}
 function sync(){mount();var role=currentRole(),items=menus[role]||menus.teacher,picker=document.getElementById('cy-v1-unified-picker'),identity=document.getElementById('cy-v1-unified-identity');if(!picker||!identity)return;var old=picker.value,html=items.map(function(x){return '<option value="'+x[0]+'">'+x[1]+'</option>'}).join('');if(picker.innerHTML!==html)picker.innerHTML=html;var page=currentPage();picker.value=items.some(function(x){return x[0]===page})?page:(old||items[0][0]);identity.textContent=currentName()+' · '+({teacher:'教师',student:'学生',parent:'家长',admin:'管理员'}[role]||role)}
 async function hydrateFromV1(){
  var bridge=params.get('from')==='v1'?await consumeV1Handoff():null,t='',s=null;if(bridge&&bridge.token){t=String(bridge.token);s=bridge}else{if(stateReady())return true;t=v1Token()}if(!t||t==='demo')return false;
  try{if(!s){var r=await fetch('/session',{headers:{Authorization:'Bearer '+t},cache:'no-store'});if(!r.ok)return false;s=await r.json()}var u={id:s.userID??s.id??null,name:s.name||'',role:s.role||'teacher',grade:s.grade??null,subscription:s.subscription||null};if(typeof state==='undefined')return false;state.token=t;state.user=u;state.remember=localStorage.getItem('v717Remember')==='1';try{if(typeof saveAuth==='function')saveAuth()}catch(_e){}try{if(typeof markNetwork==='function')markNetwork(true)}catch(_e){}if(typeof validateSavedSession==='function'){var ok=await Promise.resolve(validateSavedSession());if(!ok)return false}sync();return true}catch(_e){return false}
 }
 function autoResume(){if(window.__cyV1UnifiedAutoResume)return;try{var btn=document.getElementById('continueSessionBtn');if(!btn||btn.classList.contains('hidden'))return;window.__cyV1UnifiedAutoResume=true;if(typeof markNetwork==='function')markNetwork(true);btn.click()}catch(_e){}}
 async function start(){mount();sync();var hydrated=await hydrateFromV1();if(!hydrated)autoResume();sync();var tries=0,t=setInterval(function(){sync();if(!stateReady())autoResume();if(stateReady()||++tries>80)clearInterval(t)},100);setTimeout(function(){if(!stateReady())autoResume()},250)}
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start,{once:true});else start();
})();
</script>
'''


def inject_v1_classic_unified(html: str) -> str:
    if V1_CLASSIC_UNIFIED_MARKER in html:
        return html
    marker = V1_CLASSIC_UNIFIED_SNIPPET + f"\n<!-- {V1_CLASSIC_UNIFIED_MARKER} -->"
    return html.replace("</body>", marker + "</body>", 1) if "</body>" in html else html + marker


__all__ = ["V1_CLASSIC_UNIFIED_MARKER", "inject_v1_classic_unified"]