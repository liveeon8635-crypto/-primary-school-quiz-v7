"""First-visit onboarding and a persistent V1 product guide.

This is presentation-only. The acknowledgement lives in localStorage and the
guide never writes school, student, teaching, billing, or authorization data.
"""

from __future__ import annotations

from changying.web import v1 as v1_module


V1_PRODUCT_GUIDE_MARKER = "changying_v1_product_guide_v1"
GUIDE_PATH = "/v1/guide"

_GUIDE_SNIPPET = r'''
<style id="changying_v1_product_guide_css_v1">
  #cy-v1-guide-overlay{position:fixed;inset:0;z-index:120;background:rgba(18,31,53,.48);display:grid;place-items:center;padding:18px}
  #cy-v1-guide-overlay .cy-guide-dialog{width:min(760px,100%);max-height:min(820px,88dvh);overflow:auto;background:#fff;border-radius:22px;padding:22px;box-shadow:0 24px 80px rgba(18,31,53,.28)}
  .cy-guide-flow{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;margin-top:16px}
  .cy-guide-step{border:1px solid var(--line);border-radius:16px;padding:15px;background:#fff}
  .cy-guide-step b{display:block;margin:8px 0 6px;font-size:17px}.cy-guide-step p{margin:0;color:var(--muted);line-height:1.65}
  .cy-guide-actions{display:flex;gap:10px;flex-wrap:wrap;margin-top:18px}
  #cy-v1-product-guide-page{padding:28px clamp(16px,4vw,48px) 110px;max-width:1060px;margin:0 auto}
  #cy-v1-product-guide-page .cy-guide-intro{background:#eaf1ff;border:1px solid #cfe0ff;border-radius:18px;padding:18px;line-height:1.75}
  @media(max-width:640px){
    #guideButton{padding:8px 10px;font-size:12px}.top-actions{gap:6px}.top-actions .identity-chip{max-width:104px}
    .cy-guide-flow{grid-template-columns:1fr}#cy-v1-guide-overlay{padding:10px}
    #cy-v1-guide-overlay .cy-guide-dialog{padding:18px 15px;border-radius:18px}
    #cy-v1-product-guide-page{padding:20px 14px 104px}
  }
</style>
<script id="changying_v1_product_guide_v1-script">
(()=>{
  if(window.__cyV1ProductGuideInstalled)return;
  window.__cyV1ProductGuideInstalled=true;
  const KEY='cyV1ProductGuideSeenV1';
  const screen=document.getElementById('screen');
  const guideButton=document.getElementById('guideButton');
  const identityButton=document.getElementById('identityButton');
  const steps=[
    ['1','学生主档案','先找到学生本人。成绩、作业、课堂表现、家长关联和历史变化都围绕同一个学生 ID 累积。','/v1/student'],
    ['2','教学归属','确认学生当前所在班级、教师和教学阶段；调班或换老师时保留历史，不重新建学生。','/v1/student'],
    ['3','课堂与学习动态','从当前教学进入课堂、练习、作业、测验和后续跟进，结果继续回到学生连续档案。','/v1/workspace'],
    ['4','家长关联','家长关系属于学生档案的一部分；需要查看家庭关联时，从学生档案进入对应信息。','/v1/student'],
    ['5','升年级衔接','升年级或升学时继续使用原学生档案，记录上一阶段事实、衔接计划和下一阶段进展。','/v1/transition'],
    ['6','历史查询','已经结束的班级、学期和课程进入往期教学；历史记录只读保留，仍能回到同一学生。','/v1/history']
  ];
  const esc=v=>String(v??'').replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  const flow=()=>steps.map(x=>'<article class="cy-guide-step"><span class="tag">STEP '+x[0]+'</span><b>'+esc(x[1])+'</b><p>'+esc(x[2])+'</p><a class="btn" data-cy-guide-target href="'+x[3]+'" style="margin-top:12px">打开这个入口</a></article>').join('');
  const markSeen=()=>localStorage.setItem(KEY,'1');
  const authenticated=()=>{
    if(identityButton)return identityButton.hidden===false;
    const chip=document.getElementById('identityChip');
    if(chip&&/已登录|切换身份/.test(chip.textContent||''))return true;
    return false;
  };

  function closeOverlay(){
    markSeen();
    document.getElementById('cy-v1-guide-overlay')?.remove();
  }
  function showFirstVisit(){
    if(document.getElementById('cy-v1-guide-overlay'))return;
    const overlay=document.createElement('div');overlay.id='cy-v1-guide-overlay';
    overlay.innerHTML='<section class="cy-guide-dialog" role="dialog" aria-modal="true" aria-labelledby="cy-guide-title"><span class="tag">首次使用</span><h1 id="cy-guide-title" style="margin:10px 0 8px">先看懂长缨的使用主线</h1><p class="subtitle">学生不是一次作业或一个班级里的临时记录。先确定学生，再把教学过程、家庭关联、阶段衔接和历史事实持续放回同一份档案。</p><div class="cy-guide-flow">'+flow()+'</div><div class="cy-guide-actions"><button class="btn primary" id="cy-guide-start">开始使用</button><button class="btn" id="cy-guide-skip">暂时跳过</button></div><p style="color:var(--muted);font-size:12px;margin:14px 0 0">以后可随时点击顶部“使用指南”重新查看。</p></section>';
    document.body.appendChild(overlay);
    overlay.querySelectorAll('[data-cy-guide-target]').forEach(a=>a.addEventListener('click',markSeen));
    overlay.querySelector('#cy-guide-start').onclick=closeOverlay;
    overlay.querySelector('#cy-guide-skip').onclick=closeOverlay;
  }

  function renderPersistentGuide(){
    if(!screen||screen.querySelector('#cy-v1-product-guide-page'))return;
    screen.innerHTML='<main id="cy-v1-product-guide-page"><header class="page-head"><div><span class="tag">产品说明</span><h1 style="margin-top:10px">长缨辅学使用指南</h1><p class="subtitle">与首次使用引导共用同一套流程说明，后续随时可以回来查看。</p></div></header><section class="cy-guide-intro"><b>核心原则：学生始终是一份连续档案。</b><br>当前教学负责正在发生的事；学生页负责连续档案；升年级衔接记录阶段变化；往期教学负责历史查询。班级、教师和学期变化不会重新创建学生。</section><section class="cy-guide-flow">'+flow()+'</section><section class="card" style="margin-top:18px"><h2>不知道从哪里开始？</h2><p style="color:var(--muted);line-height:1.7">教师通常从“当前教学”开始，再进入具体学生；学生和家长通常先进入自己的学生档案。需要旧系统完整能力时使用“全部功能”。</p><div class="cy-guide-actions"><a class="btn primary" href="/v1/workspace">当前教学</a><a class="btn" href="/v1/student">学生档案</a><a class="btn" href="/v1/history">往期教学</a><a class="btn" href="/v1/tool">全部功能</a></div></section></main>';
    screen.querySelectorAll('[data-cy-guide-target]').forEach(a=>a.addEventListener('click',markSeen));
  }

  function sync(){
    const authed=authenticated();
    if(guideButton)guideButton.hidden=!authed;
    if(!authed)return;
    if(location.pathname==='/v1/guide'){markSeen();renderPersistentGuide();return}
    if(localStorage.getItem(KEY)!=='1')showFirstVisit();
  }

  if(guideButton)guideButton.onclick=()=>{location.href='/v1/guide'};
  if(screen)new MutationObserver(()=>queueMicrotask(sync)).observe(screen,{childList:true});
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
    top_replacement = '<span class="identity-chip" id="identityChip">检查登录状态</span><button class="btn" id="guideButton" hidden>使用指南</button><button class="btn" id="identityButton" hidden>切换身份</button>'
    if top_marker not in html:
        raise RuntimeError("V1 product guide: top action marker not found")
    html = html.replace(top_marker, top_replacement, 1)

    if "</body>" not in html:
        raise RuntimeError("V1 product guide: closing body marker not found")
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
