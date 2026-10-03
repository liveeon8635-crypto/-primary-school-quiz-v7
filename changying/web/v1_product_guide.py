"""Role-specific, game-like onboarding for Changying V1.

The tutorial is presentation-only. It uses synthetic demo identities and keeps
progress in localStorage. It never writes school, student, teaching, billing,
authorization, score, points, classroom, or learning-evidence data.
"""

from __future__ import annotations

from changying.web import v1 as v1_module


V1_PRODUCT_GUIDE_MARKER = "changying_v1_product_guide_v7"
GUIDE_PATH = "/v1/guide"

_GUIDE_SNIPPET = r'''
<style id="changying_v1_product_guide_css_v7">
  #cy-onboarding-overlay{position:fixed;inset:0;z-index:140;background:rgba(12,25,47,.58);display:grid;place-items:center;padding:12px}
  .cy-onboarding-shell{width:min(980px,100%);max-height:94dvh;overflow:auto;background:#f5f8fd;border-radius:24px;box-shadow:0 26px 90px rgba(12,25,47,.32);border:1px solid rgba(255,255,255,.4)}
  .cy-onboarding-head{position:sticky;top:0;z-index:3;display:flex;align-items:center;justify-content:space-between;gap:12px;padding:15px 18px;background:rgba(255,255,255,.94);backdrop-filter:blur(14px);border-bottom:1px solid #dfe7f2}
  .cy-onboarding-head strong{font-size:16px}.cy-onboarding-head small{display:block;color:var(--muted);margin-top:2px}
  .cy-onboarding-body{padding:18px}
  .cy-role-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin-top:16px}
  .cy-role-card{display:flex;flex-direction:column;gap:8px;min-height:170px;text-align:left;border:1px solid #dce5f1;background:#fff;border-radius:18px;padding:16px;cursor:pointer}
  .cy-role-card:hover{border-color:#9db7e7}.cy-role-card .cy-role-icon{font-size:28px}.cy-role-card b{font-size:17px}.cy-role-card p{margin:0;color:var(--muted);line-height:1.55;font-size:13px}
  .cy-role-progress{height:7px;background:#e8edf5;border-radius:99px;overflow:hidden;margin-top:auto}.cy-role-progress>i{display:block;height:100%;background:var(--navy)}
  .cy-role-meta{font-size:12px;color:var(--muted)}
  .cy-tutorial-layout{display:grid;grid-template-columns:260px minmax(0,1fr);gap:14px}
  .cy-tutorial-rail{background:#fff;border:1px solid #dfe7f2;border-radius:18px;padding:12px;align-self:start}
  .cy-step-list{display:grid;gap:7px;margin-top:10px}.cy-step-item{display:grid;grid-template-columns:30px 1fr auto;align-items:center;gap:8px;padding:9px;border-radius:12px;border:1px solid transparent;background:#f8faff;text-align:left;width:100%}
  .cy-step-item.active{background:#eaf1ff;border-color:#bfd2f4}.cy-step-item.done{background:#f0f8f1}.cy-step-item.skipped{background:#fff8ec}
  .cy-step-no{width:28px;height:28px;border-radius:9px;display:grid;place-items:center;background:#fff;border:1px solid #dce5f1;font-weight:800;font-size:12px}
  .cy-step-state{font-size:11px;color:var(--muted)}
  .cy-tutorial-stage{min-width:0}
  .cy-lesson-card{background:#fff;border:1px solid #dfe7f2;border-radius:20px;padding:18px}
  .cy-lesson-top{display:flex;align-items:flex-start;justify-content:space-between;gap:12px}.cy-lesson-top h2{margin:4px 0 6px;font-size:24px}.cy-lesson-top p{margin:0;color:var(--muted);line-height:1.6}
  .cy-badge{display:inline-flex;align-items:center;gap:6px;background:#eaf1ff;color:var(--navy);border-radius:999px;padding:6px 10px;font-size:12px;font-weight:800}
  .cy-progress-row{display:flex;align-items:center;gap:10px;margin:15px 0}.cy-progress-row span{font-size:12px;color:var(--muted)}.cy-progress-track{flex:1;height:8px;background:#e9eef6;border-radius:99px;overflow:hidden}.cy-progress-track i{display:block;height:100%;background:var(--navy)}
  .cy-mission{margin-top:12px;padding:14px;border-radius:15px;background:#0f2347;color:#fff}.cy-mission strong{display:block;font-size:12px;opacity:.74;margin-bottom:5px}.cy-mission p{margin:0;line-height:1.6}
  .cy-demo-app{margin-top:14px;border:1px solid #cfdbea;border-radius:18px;overflow:hidden;background:#f6f8fb}
  .cy-demo-appbar{display:flex;align-items:center;justify-content:space-between;gap:8px;padding:11px 13px;background:#fff;border-bottom:1px solid #dfe7f2}.cy-demo-appbar b{font-size:14px}.cy-demo-appbar span{font-size:11px;color:var(--muted)}
  .cy-demo-canvas{padding:14px}.cy-demo-screen-title{font-size:18px;font-weight:850;margin-bottom:4px}.cy-demo-screen-sub{color:var(--muted);font-size:12px;margin-bottom:12px}
  .cy-demo-cards{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:9px}.cy-demo-card{background:#fff;border:1px solid #dce5f1;border-radius:14px;padding:12px;min-height:78px}.cy-demo-card b{display:block;margin-bottom:5px}.cy-demo-card small{color:var(--muted);line-height:1.45}
  .cy-demo-action{margin-top:12px}.cy-demo-action .btn{width:100%;justify-content:center}
  .cy-demo-feedback{display:none;margin-top:10px;padding:11px 12px;border-radius:12px;background:#eaf7ed;border:1px solid #cce7d2;color:#245f33;line-height:1.55}.cy-demo-feedback.show{display:block}
  .cy-lesson-notes{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:9px;margin-top:14px}.cy-note{background:#f8faff;border:1px solid #dfe7f2;border-radius:14px;padding:12px}.cy-note strong{display:block;font-size:12px;color:var(--navy);margin-bottom:5px}.cy-note p{margin:0;color:var(--muted);font-size:12px;line-height:1.55}
  .cy-lesson-actions{display:flex;gap:9px;flex-wrap:wrap;margin-top:14px}.cy-lesson-actions .btn.primary{margin-left:auto}
  .cy-skip-note{font-size:11px;color:var(--muted);margin-top:9px}
  .cy-practice-form{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin-top:12px;padding:12px;border:1px dashed #b9c9df;border-radius:14px;background:#fff}.cy-practice-form label{display:grid;gap:5px;font-size:11px;color:var(--muted)}.cy-practice-form input,.cy-practice-form select{width:100%;border:1px solid #cfdbea;border-radius:10px;padding:9px 10px;background:#fff;color:var(--ink)}.cy-practice-tip{margin-top:12px;padding:10px 12px;border-radius:12px;background:#fff8e8;border:1px solid #f3d69a;color:#744b06;font-size:12px;line-height:1.55}
  #cy-v1-product-guide-page{padding:26px clamp(14px,4vw,44px) 110px;max-width:1080px;margin:0 auto}
  .cy-guide-hero{background:linear-gradient(145deg,#edf3ff,#fff);border:1px solid #d3e0f4;border-radius:22px;padding:22px}.cy-guide-hero h1{margin:8px 0}.cy-guide-hero p{color:var(--muted);line-height:1.7;max-width:760px}
  .cy-guide-summary{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin-top:16px}.cy-guide-summary>div{background:#fff;border:1px solid #dfe7f2;border-radius:15px;padding:13px}.cy-guide-summary b{display:block;margin-bottom:4px}.cy-guide-summary small{color:var(--muted);line-height:1.45}
  @media(max-width:760px){
    #tutorialButton{padding:8px 9px;font-size:12px}.top-actions{gap:5px}.top-actions .identity-chip{max-width:96px}
    #cy-onboarding-overlay{padding:0}.cy-onboarding-shell{width:100%;height:100dvh;max-height:none;border-radius:0}
    .cy-onboarding-body{padding:12px}.cy-role-grid{grid-template-columns:1fr}.cy-tutorial-layout{grid-template-columns:1fr}
    .cy-tutorial-rail{order:2}.cy-step-list{grid-template-columns:repeat(2,minmax(0,1fr))}
    .cy-step-item{grid-template-columns:26px 1fr}.cy-step-state{display:none}.cy-demo-cards,.cy-lesson-notes,.cy-guide-summary,.cy-practice-form{grid-template-columns:1fr}
    .cy-lesson-top{display:block}.cy-lesson-top .cy-badge{margin-top:8px}.cy-lesson-actions{display:grid;grid-template-columns:1fr 1fr}.cy-lesson-actions .btn.primary{margin-left:0;grid-column:1/-1}
    #cy-v1-product-guide-page{padding:18px 12px 100px}
  }
</style>
<script id="changying_v1_product_guide_v7-script">
(()=>{
  if(window.__cyV1ProductGuideInstalled)return;
  window.__cyV1ProductGuideInstalled=true;

  const screen=document.getElementById('screen');
  const tutorialButton=document.getElementById('tutorialButton');
  const identityButton=document.getElementById('identityButton');
  const identityChip=document.getElementById('identityChip');
  const esc=v=>String(v??'').replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));

  const personas=[
    {id:'institution_teacher',icon:'👩‍🏫',name:'机构老师'},
    {id:'school_teacher',icon:'📚',name:'学校教师'},
    {id:'institution_admin',icon:'🏫',name:'机构管理员'},
    {id:'school_admin',icon:'🏛️',name:'学校管理员'},
    {id:'student',icon:'🎒',name:'学生'},
    {id:'parent',icon:'👪',name:'家长'}
  ];

  const currentPersonaId=()=>{
    const label=String(identityChip?.textContent||'');
    if(label.includes('学校教师'))return 'school_teacher';
    if(label.includes('机构老师'))return 'institution_teacher';
    if(label.includes('学校管理员'))return 'school_admin';
    if(label.includes('机构管理员'))return 'institution_admin';
    if(label.includes('家长'))return 'parent';
    if(label.includes('学生'))return 'student';
    if(label.includes('教师')||label.includes('老师'))return 'institution_teacher';
    if(label.includes('管理员'))return 'institution_admin';
    return '';
  };
  const currentPersona=()=>personas.find(p=>p.id===currentPersonaId())||null;
  const SESSION_SHOWN_KEY='cyV1RoleTutorialShownThisLoginV7';
  const sessionShownFor=()=>sessionStorage.getItem(SESSION_SHOWN_KEY)||'';
  const markSessionShown=id=>sessionStorage.setItem(SESSION_SHOWN_KEY,id||'');
  const clearSessionShown=()=>sessionStorage.removeItem(SESSION_SHOWN_KEY);
  const hasAuthToken=()=>Boolean(
    sessionStorage.getItem('v717Token')||
    localStorage.getItem('v717Token')||
    sessionStorage.getItem('v6Token')||
    localStorage.getItem('v6Token')
  );
  const identityReady=()=>Boolean(identityButton&&identityButton.hidden===false&&currentPersonaId());


  function closeOverlay(){document.getElementById('cy-onboarding-overlay')?.remove()}
  function mountShell(){
    closeOverlay();
    const assistantPanel=document.getElementById('cy-product-assistant-panel');if(assistantPanel)assistantPanel.hidden=true;
    const overlay=document.createElement('div');overlay.id='cy-onboarding-overlay';
    overlay.innerHTML='<section class="cy-onboarding-shell" role="dialog" aria-modal="true"><header class="cy-onboarding-head"><div><strong>长缨新手教学</strong><small>虚拟演示账户 · 不写真实数据</small></div><button class="btn" id="cy-onboarding-close">退出并保存</button></header><div class="cy-onboarding-body"></div></section>';
    document.body.appendChild(overlay);
    overlay.querySelector('#cy-onboarding-close').onclick=closeOverlay;
    return overlay;
  }

  function showCurrentIntro({firstVisit=false}={}){
    const persona=currentPersona();
    if(!persona)return;
    const overlay=mountShell(),body=overlay.querySelector('.cy-onboarding-body');
    body.innerHTML='<section class="cy-lesson-card" style="max-width:760px;margin:0 auto"><span class="tag">'+(firstVisit?'首次登录引导':'继续新手教学')+'</span><h1 style="margin:10px 0 7px">'+persona.icon+' '+esc(persona.name)+'：进入同身份实操沙盒</h1><p class="subtitle">不是看说明图。你会在临时虚拟环境里真实建班、加学生、组卷、布置、作答、查看结果和继续教学；需要关联角色时可选择亲自切换虚拟账号，或由系统自动模拟关联数据。所有训练业务数据都不会写入正式档案。</p><div class="cy-guide-summary"><div><b>真实操作</b><small>按长缨实际业务顺序完成每个页面任务</small></div><div><b>跨角色可选</b><small>亲自切换体验，或自动模拟后继续主身份</small></div><div><b>可反复重练</b><small>支持跳过、回退、场景起点和整条重置</small></div></div><div class="cy-guide-actions"><button class="btn primary" id="cy-current-start">进入实操沙盒</button><button class="btn" id="cy-current-exit">暂不学习</button></div></section>';
    body.querySelector('#cy-current-start').onclick=()=>{location.href='/v1/training'};
    body.querySelector('#cy-current-exit').onclick=closeOverlay;
  }

  function renderPersistentGuide(){
    if(!screen)return;
    const existing=screen.querySelector('#cy-v1-product-guide-page');
    if(existing?.dataset?.guideVersion==='v7')return;
    if(existing)existing.remove();
    const persona=currentPersona();
    if(!persona){
      screen.innerHTML='<main id="cy-v1-product-guide-page" data-guide-version="v7"><section class="cy-guide-hero"><span class="tag">新手教学</span><h1>请先完成账号登录并选择身份</h1><p>新手教学会根据你真实登录后的身份显示对应流程；未登录或尚未选择身份时不会提前展示。</p></section></main>';
      return;
    }
    screen.innerHTML='<main id="cy-v1-product-guide-page" data-guide-version="v7"><section class="cy-guide-hero"><span class="tag">'+persona.icon+' '+esc(persona.name)+'</span><h1>当前身份 · 实操沙盒</h1><p>使用临时虚拟账号和真实操作流程学习长缨。训练主体是可操作页面；路线图只负责导航、角色关系解释和复习。</p><div class="cy-guide-actions"><button class="btn primary" id="cy-guide-start">进入 / 继续实操沙盒</button><button class="btn" id="cy-guide-restart">清空训练进度后进入</button></div><div class="cy-guide-summary"><div><b>完整主线</b><small>了解每个功能页面的上游、下游与角色关系</small></div><div><b>关联角色二选一</b><small>切虚拟账号亲自体验 / 自动模拟数据</small></div><div><b>正式数据 0 写入</b><small>沙盒过期或重置后临时业务数据消失</small></div></div></section><section class="card" style="margin-top:18px"><h2>边用边学</h2><p style="color:var(--muted);line-height:1.75">第一次建议从零走完整闭环；以后可直接从“已布置作业 / 已有提交 / 课堂复盘”等场景开始复习，不必重复已经熟悉的步骤。</p></section></main>';
    screen.querySelector('#cy-guide-start').onclick=()=>{location.href='/v1/training'};
    screen.querySelector('#cy-guide-restart').onclick=()=>{sessionStorage.removeItem('cyTrainingSandboxSessionV1');sessionStorage.setItem('cyTrainingStepIndexV1','0');location.href='/v1/training'};
  }

  function renderPersistentGuideRefresh(){
    const old=screen?.querySelector('#cy-v1-product-guide-page');if(old)old.remove();renderPersistentGuide();
  }

  function sync(){
    const ready=identityReady(),persona=currentPersona();
    const params=new URLSearchParams(location.search);
    const tab=String(params.get('tab')||'');
    const feedbackReview=Boolean(
      params.get('cy_feedback_review')||
      params.get('reviewed')||
      params.get('focus')||
      params.get('from')==='feedback'||
      tab==='feedback-records'||
      tab==='feedback'
    );
    if(tutorialButton)tutorialButton.hidden=!ready;
    // Route changes briefly hide/reset identity controls while auth is still
    // valid. Do not treat that transient loading state as a logout, otherwise
    // every internal navigation can clear the session marker and relaunch the
    // first-login tutorial. Clear only after auth itself is actually gone.
    if(!ready){if(!hasAuthToken())clearSessionShown();return}
    if(location.pathname==='/v1/guide'){renderPersistentGuide();return}
    // Feedback acceptance/return is a focused product-validation flow. Never
    // cover it with first-login teaching, including standalone-page fallbacks.
    if(feedbackReview){markSessionShown(persona.id);return}
    if(sessionShownFor()!==persona.id){
      markSessionShown(persona.id);
      showCurrentIntro({firstVisit:true});
    }
  }

  if(tutorialButton)tutorialButton.onclick=()=>showCurrentIntro();
  if(screen){
    const guideObserver=new MutationObserver(()=>{
      if(location.pathname!=='/v1/guide')return;
      if(screen.querySelector('#cy-v1-product-guide-page[data-guide-version="v7"]'))return;
      queueMicrotask(sync);
    });
    guideObserver.observe(screen,{childList:true,subtree:false});
  }
  const identityObserver=new MutationObserver(()=>queueMicrotask(sync));
  if(identityButton)identityObserver.observe(identityButton,{attributes:true,attributeFilter:['hidden']});
  if(identityChip)identityObserver.observe(identityChip,{childList:true,characterData:true,subtree:true});
  window.addEventListener('pageshow',sync);
  window.addEventListener('popstate',sync);
  setTimeout(sync,0);setTimeout(sync,300);
})();
</script>
'''


def patch_v1_product_guide(html: str) -> str:
    if V1_PRODUCT_GUIDE_MARKER in html:
        return html

    top_marker = '<span class="identity-chip" id="identityChip">检查登录状态</span><button class="btn" id="identityButton" hidden>切换身份</button>'
    top_replacement = '<span class="identity-chip" id="identityChip">检查登录状态</span><button class="btn" id="tutorialButton" hidden>新手教学</button><button class="btn" id="identityButton" hidden>切换身份</button>'
    if top_marker not in html:
        raise RuntimeError("V1 role tutorial: top action marker not found")
    html = html.replace(top_marker, top_replacement, 1)

    if "</body>" not in html:
        raise RuntimeError("V1 role tutorial: closing body marker not found")
    return html.replace(
        "</body>",
        _GUIDE_SNIPPET + f"\n<!-- {V1_PRODUCT_GUIDE_MARKER} -->\n</body>",
        1,
    )


def install_v1_product_guide_patch() -> None:
    if getattr(v1_module, "_product_guide_patch_installed", False):
        return

    original = v1_module.v1_html

    def patched_v1_html() -> str:
        return patch_v1_product_guide(original())

    v1_module.v1_html = patched_v1_html
    if GUIDE_PATH not in v1_module.V1_PATHS:
        v1_module.V1_PATHS = (*v1_module.V1_PATHS, GUIDE_PATH)
    v1_module._product_guide_patch_installed = True


__all__ = [
    "GUIDE_PATH",
    "V1_PRODUCT_GUIDE_MARKER",
    "install_v1_product_guide_patch",
    "patch_v1_product_guide",
]
