"""First-visit onboarding, persistent product guide, and interactive V1 demo.

This module is presentation-only. Guide acknowledgement and demo progress live in
localStorage. The walkthrough never writes school, student, teaching, billing,
authorization, score, points, or learning-evidence data.
"""

from __future__ import annotations

from changying.web import v1 as v1_module


V1_PRODUCT_GUIDE_MARKER = "changying_v1_product_guide_v2"
GUIDE_PATH = "/v1/guide"

_GUIDE_SNIPPET = r'''
<style id="changying_v1_product_guide_css_v2">
  #cy-v1-guide-overlay,#cy-v1-demo-overlay{position:fixed;inset:0;z-index:120;background:rgba(18,31,53,.52);display:grid;place-items:center;padding:18px}
  #cy-v1-guide-overlay .cy-guide-dialog,#cy-v1-demo-overlay .cy-demo-dialog{width:min(820px,100%);max-height:min(860px,90dvh);overflow:auto;background:#fff;border-radius:22px;padding:22px;box-shadow:0 24px 80px rgba(18,31,53,.28)}
  .cy-guide-flow{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;margin-top:16px}
  .cy-guide-step{border:1px solid var(--line);border-radius:16px;padding:15px;background:#fff}
  .cy-guide-step b{display:block;margin:8px 0 6px;font-size:17px}.cy-guide-step p{margin:0;color:var(--muted);line-height:1.65}
  .cy-guide-actions{display:flex;gap:10px;flex-wrap:wrap;margin-top:18px}
  #cy-v1-product-guide-page{padding:28px clamp(16px,4vw,48px) 110px;max-width:1060px;margin:0 auto}
  #cy-v1-product-guide-page .cy-guide-intro{background:#eaf1ff;border:1px solid #cfe0ff;border-radius:18px;padding:18px;line-height:1.75}
  .cy-demo-progress{display:flex;align-items:center;gap:10px;margin:14px 0 18px}.cy-demo-progress-track{height:8px;flex:1;background:#e9eef6;border-radius:99px;overflow:hidden}.cy-demo-progress-bar{height:100%;background:var(--navy);border-radius:99px;transition:width .2s ease}
  .cy-demo-stage{border:1px solid #dbe4f3;background:#f8faff;border-radius:18px;padding:18px}.cy-demo-stage h2{margin:6px 0 8px;font-size:24px}.cy-demo-role{display:inline-flex;padding:6px 10px;border-radius:999px;background:#eaf1ff;color:var(--navy);font-size:12px;font-weight:800}
  .cy-demo-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin-top:15px}.cy-demo-fact{background:#fff;border:1px solid var(--line);border-radius:14px;padding:13px}.cy-demo-fact strong{display:block;font-size:12px;color:var(--navy);margin-bottom:6px}.cy-demo-fact p{margin:0;color:var(--muted);line-height:1.55;font-size:13px}
  .cy-demo-sample{margin-top:14px;border:1px dashed #b9c8df;background:#fff;border-radius:14px;padding:13px;line-height:1.65}.cy-demo-sample b{display:block;margin-bottom:5px}
  .cy-demo-nav{display:grid;grid-template-columns:1fr auto auto;gap:9px;align-items:center;margin-top:16px}.cy-demo-nav .btn{white-space:nowrap}
  .cy-demo-caption{color:var(--muted);font-size:12px;line-height:1.55;margin-top:10px}
  @media(max-width:640px){
    #guideButton,#walkthroughButton{padding:8px 9px;font-size:12px}.top-actions{gap:5px}.top-actions .identity-chip{max-width:88px}
    .cy-guide-flow,.cy-demo-grid{grid-template-columns:1fr}#cy-v1-guide-overlay,#cy-v1-demo-overlay{padding:8px}
    #cy-v1-guide-overlay .cy-guide-dialog,#cy-v1-demo-overlay .cy-demo-dialog{padding:17px 14px;border-radius:18px;max-height:92dvh}
    #cy-v1-product-guide-page{padding:20px 14px 104px}
    .cy-demo-nav{grid-template-columns:1fr 1fr}.cy-demo-nav .cy-demo-open{grid-column:1/-1}
  }
</style>
<script id="changying_v1_product_guide_v2-script">
(()=>{
  if(window.__cyV1ProductGuideInstalled)return;
  window.__cyV1ProductGuideInstalled=true;
  const KEY='cyV1ProductGuideSeenV2';
  const DEMO_KEY='cyV1ProductDemoStepV1';
  const screen=document.getElementById('screen');
  const guideButton=document.getElementById('guideButton');
  const walkthroughButton=document.getElementById('walkthroughButton');
  const identityButton=document.getElementById('identityButton');

  const steps=[
    ['1','学生主档案','先找到学生本人。成绩、作业、课堂表现、家长关联和历史变化都围绕同一个学生 ID 累积。','/v1/student'],
    ['2','教学归属','确认学生当前所在班级、教师和教学阶段；调班或换老师时保留历史，不重新建学生。','/v1/student'],
    ['3','课堂与学习动态','从当前教学进入课堂、练习、作业、测验和后续跟进，结果继续回到学生连续档案。','/v1/workspace'],
    ['4','家长关联','家长关系属于学生档案的一部分；需要查看家庭关联时，从学生档案进入对应信息。','/v1/student'],
    ['5','升年级衔接','升年级或升学时继续使用原学生档案，记录上一阶段事实、衔接计划和下一阶段进展。','/v1/transition'],
    ['6','历史查询','已经结束的班级、学期和课程进入往期教学；历史记录只读保留，仍能回到同一学生。','/v1/history']
  ];

  const demoSteps=[
    {
      title:'教师进入当前教学',role:'教师',
      action:'选择当前教学周期、班级与学生，先确认“现在正在教谁、处于哪个教学阶段”。',
      system:'系统只切换当前教学视角，不重新创建学生；班级与教师是教学归属，学生 ID 保持不变。',
      result:'得到一个明确的当前教学入口，并可以继续进入该学生的长期档案。',
      sample:'示例：钟老师 → 五年级一班 → 刘麦迪；当前教学与历史档案从这里开始分工。',
      path:'/v1/workspace'
    },
    {
      title:'打开学生连续档案',role:'教师 / 家长 / 学生',
      action:'进入同一学生，查看成绩、知识点掌握、作业、错题、积分、课堂表现与历史变化。',
      system:'不同来源的数据围绕同一个学生 ID 汇总，新的记录追加进连续档案。',
      result:'可以回答“这个学生最近学得怎么样、哪里薄弱、之前发生过什么”。',
      sample:'示例：数学小数乘法正确率偏低；最近作业有 1 项待完成；积分与课堂记录仍保留。',
      path:'/v1/student'
    },
    {
      title:'教师生成并布置练习',role:'教师',
      action:'按年级、科目、教材和知识模块生成综合测试或针对性练习，教师审核后再布置。',
      system:'练习与当前学生、科目、教材版本和已有薄弱知识点关联；教师保留最终决定权。',
      result:'学生收到明确的待完成练习，而不是一份与其学情无关的随机题目。',
      sample:'示例：人教版五年级数学 → 小数乘法 → 8 题针对性练习 → 教师审核后布置。',
      path:'/v1/tool?page=practice'
    },
    {
      title:'学生完成练习并提交',role:'学生',
      action:'切到学生视角逐题作答，可在题目间切换；提交后查看得分、知识点正确率与错题。',
      system:'客观题自动判定；符合规则的积分进入积分动态；错题和学习证据写回同一学生档案。',
      result:'一次练习同时形成成绩、知识点证据、错题、积分与下一轮教学依据。',
      sample:'示例：8 题答对 6 题 → 75% → 小数乘法进位仍薄弱 → 错题进入错题记录。',
      path:'/v1/tool?page=assignments'
    },
    {
      title:'教师根据结果继续针对教学',role:'教师',
      action:'回到学生档案查看本次结果，让 AI 基于最近测试、知识模块正确率和错题生成下一轮练习。',
      system:'AI 只提出针对性内容；教师审核后才能布置，后续提交继续回流档案。',
      result:'形成“测验 → 诊断 → 针对练习 → 再验证”的连续闭环。',
      sample:'示例：系统建议继续练“小数乘法进位”，教师删改后只布置给该学生。',
      path:'/v1/student'
    },
    {
      title:'课堂复盘并生成讲义',role:'教师',
      action:'同班学生完成练习后查看班级汇总，由教师决定是否生成课堂复盘讲义并确认发布版本。',
      system:'系统汇总全班知识点表现；讲义先是草稿，教师确认后冻结为发布版本，后续修改不覆盖旧版本。',
      result:'教师得到一份基于真实课堂数据的复盘材料，而不是自动对学生发布。',
      sample:'示例：发现“习作修改”是全班共同薄弱点 → 生成讲义草稿 → 教师确认发布 V1。',
      path:'/v1/tool?page=classroom'
    },
    {
      title:'开展互动课堂与随堂检测',role:'教师 + 学生',
      action:'针对知识点选择教师讲、学生讲、共同讲或讨论；需要时邀请学生讲解，再开放随堂检测。',
      system:'候选学生证据信号只供教师参考；学生可接受或拒绝；随堂检测结果由教师收口，不自动推进课堂。',
      result:'课堂从“教师单向讲”变成可观察、可互动、可根据即时反馈调整的过程。',
      sample:'示例：邀请学生讲“习作修改” → 学生接受 → 完成讲解 → 开放 1 道 quick check → 教师查看反馈。',
      path:'/v1/tool?page=syncLearning'
    },
    {
      title:'长期跟踪：家长、历史与升年级',role:'教师 / 家长 / 管理员',
      action:'查看家长关联、往期教学和升年级衔接；学生换班、换教师、换学期后仍沿用原档案。',
      system:'历史事实保留，阶段变化通过教学归属与衔接记录表达，不通过“重新建一个学生”解决。',
      result:'系统最终形成跨学期、跨班级、跨教师的连续发展档案。',
      sample:'示例：五年级结束 → 记录衔接计划 → 六年级继续使用同一学生 ID → 仍能回看五年级课堂与作业。',
      path:'/v1/transition'
    }
  ];

  const esc=v=>String(v??'').replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  const flow=()=>steps.map(x=>'<article class="cy-guide-step"><span class="tag">STEP '+x[0]+'</span><b>'+esc(x[1])+'</b><p>'+esc(x[2])+'</p><a class="btn" data-cy-guide-target href="'+x[3]+'" style="margin-top:12px">打开这个入口</a></article>').join('');
  const markSeen=()=>localStorage.setItem(KEY,'1');
  const demoIndex=()=>Math.max(0,Math.min(demoSteps.length-1,Number(localStorage.getItem(DEMO_KEY)||0)||0));
  const authenticated=()=>{
    if(identityButton)return identityButton.hidden===false;
    const chip=document.getElementById('identityChip');
    if(chip&&/已登录|切换身份/.test(chip.textContent||''))return true;
    return false;
  };

  function closeGuide(){
    markSeen();
    document.getElementById('cy-v1-guide-overlay')?.remove();
  }

  function closeDemo(){
    document.getElementById('cy-v1-demo-overlay')?.remove();
  }

  function renderDemoStep(index){
    const overlay=document.getElementById('cy-v1-demo-overlay');
    if(!overlay)return;
    const i=Math.max(0,Math.min(demoSteps.length-1,index)),step=demoSteps[i];
    localStorage.setItem(DEMO_KEY,String(i));
    const pct=Math.round(((i+1)/demoSteps.length)*100);
    overlay.querySelector('.cy-demo-body').innerHTML=
      '<span class="cy-demo-role">'+esc(step.role)+'</span>'+
      '<h2>'+esc(step.title)+'</h2>'+
      '<div class="cy-demo-progress"><b>第 '+(i+1)+' / '+demoSteps.length+' 步</b><div class="cy-demo-progress-track"><div class="cy-demo-progress-bar" style="width:'+pct+'%"></div></div></div>'+
      '<section class="cy-demo-stage"><div class="cy-demo-grid">'+
        '<div class="cy-demo-fact"><strong>你做什么</strong><p>'+esc(step.action)+'</p></div>'+
        '<div class="cy-demo-fact"><strong>系统记录什么</strong><p>'+esc(step.system)+'</p></div>'+
        '<div class="cy-demo-fact"><strong>最终得到什么</strong><p>'+esc(step.result)+'</p></div>'+
      '</div><div class="cy-demo-sample"><b>演示场景</b>'+esc(step.sample)+'</div></section>'+
      '<div class="cy-demo-nav">'+
        '<button class="btn" id="cy-demo-prev" '+(i===0?'disabled':'')+'>上一步</button>'+
        '<button class="btn primary" id="cy-demo-next">'+(i===demoSteps.length-1?'完成演示':'下一步')+'</button>'+
        '<a class="btn cy-demo-open" id="cy-demo-open" href="'+step.path+'">打开对应功能</a>'+
      '</div>'+
      '<div class="cy-guide-actions"><button class="btn" id="cy-demo-restart">从头开始</button><button class="btn" id="cy-demo-exit">退出演示</button></div>'+
      '<p class="cy-demo-caption">这是安全演示说明，不会创建真实学生、作业、积分、学习证据或课堂数据；点击“打开对应功能”只进入现有页面。</p>';
    const prev=overlay.querySelector('#cy-demo-prev');
    if(prev)prev.onclick=()=>renderDemoStep(i-1);
    overlay.querySelector('#cy-demo-next').onclick=()=>i===demoSteps.length-1?closeDemo():renderDemoStep(i+1);
    overlay.querySelector('#cy-demo-restart').onclick=()=>renderDemoStep(0);
    overlay.querySelector('#cy-demo-exit').onclick=closeDemo;
    overlay.querySelector('#cy-demo-open').onclick=()=>localStorage.setItem(DEMO_KEY,String(i));
  }

  function startDemo({restart=false}={}){
    closeGuide();
    if(document.getElementById('cy-v1-demo-overlay'))return;
    if(restart)localStorage.setItem(DEMO_KEY,'0');
    const overlay=document.createElement('div');overlay.id='cy-v1-demo-overlay';
    overlay.innerHTML='<section class="cy-demo-dialog" role="dialog" aria-modal="true" aria-labelledby="cy-demo-title"><span class="tag">完整演示</span><div class="cy-demo-body"></div></section>';
    document.body.appendChild(overlay);
    renderDemoStep(restart?0:demoIndex());
  }

  function showFirstVisit(){
    if(document.getElementById('cy-v1-guide-overlay')||document.getElementById('cy-v1-demo-overlay'))return;
    const overlay=document.createElement('div');overlay.id='cy-v1-guide-overlay';
    overlay.innerHTML='<section class="cy-guide-dialog" role="dialog" aria-modal="true" aria-labelledby="cy-guide-title"><span class="tag">首次使用</span><h1 id="cy-guide-title" style="margin:10px 0 8px">先看懂长缨的使用主线</h1><p class="subtitle">学生不是一次作业或一个班级里的临时记录。建议第一次使用先走一遍完整演示，再进入真实功能。</p><div class="cy-guide-flow">'+flow()+'</div><div class="cy-guide-actions"><button class="btn primary" id="cy-guide-demo">开始完整演示</button><button class="btn" id="cy-guide-start">先进入系统</button><button class="btn" id="cy-guide-skip">暂时跳过</button></div><p style="color:var(--muted);font-size:12px;margin:14px 0 0">以后可随时点击顶部“完整演示”或“使用指南”重新查看。</p></section>';
    document.body.appendChild(overlay);
    overlay.querySelectorAll('[data-cy-guide-target]').forEach(a=>a.addEventListener('click',markSeen));
    overlay.querySelector('#cy-guide-demo').onclick=()=>{markSeen();startDemo({restart:true})};
    overlay.querySelector('#cy-guide-start').onclick=closeGuide;
    overlay.querySelector('#cy-guide-skip').onclick=closeGuide;
  }

  function renderPersistentGuide(){
    if(!screen||screen.querySelector('#cy-v1-product-guide-page'))return;
    screen.innerHTML='<main id="cy-v1-product-guide-page"><header class="page-head"><div><span class="tag">产品说明</span><h1 style="margin-top:10px">长缨辅学使用指南</h1><p class="subtitle">这里既是产品说明，也可以随时重新开始完整演示。</p></div><button class="btn primary" id="cy-guide-page-demo">开始完整演示</button></header><section class="cy-guide-intro"><b>核心原则：学生始终是一份连续档案。</b><br>当前教学负责正在发生的事；学生页负责连续档案；练习与课堂结果回流学生；升年级衔接记录阶段变化；往期教学负责历史查询。班级、教师和学期变化不会重新创建学生。</section><section class="card" style="margin-top:18px"><h2>完整演示会带你走完什么？</h2><p style="color:var(--muted);line-height:1.7">从教师进入当前教学开始，依次体验学生档案、练习布置、学生作答、针对性教学、课堂复盘、互动课堂，以及家长/历史/升年级的长期链条。每一步都会说明“你做什么 / 系统记录什么 / 最终得到什么”。</p><div class="cy-guide-actions"><button class="btn primary" id="cy-guide-page-demo-2">从第 1 步开始</button><button class="btn" id="cy-guide-page-resume">继续上次演示</button></div></section><section class="cy-guide-flow">'+flow()+'</section><section class="card" style="margin-top:18px"><h2>不知道从哪里开始？</h2><p style="color:var(--muted);line-height:1.7">教师通常从“当前教学”开始，再进入具体学生；学生和家长通常先进入自己的学生档案。需要旧系统完整能力时使用“全部功能”。</p><div class="cy-guide-actions"><a class="btn primary" href="/v1/workspace">当前教学</a><a class="btn" href="/v1/student">学生档案</a><a class="btn" href="/v1/history">往期教学</a><a class="btn" href="/v1/tool">全部功能</a></div></section></main>';
    screen.querySelectorAll('[data-cy-guide-target]').forEach(a=>a.addEventListener('click',markSeen));
    screen.querySelector('#cy-guide-page-demo').onclick=()=>startDemo({restart:true});
    screen.querySelector('#cy-guide-page-demo-2').onclick=()=>startDemo({restart:true});
    screen.querySelector('#cy-guide-page-resume').onclick=()=>startDemo({restart:false});
  }

  function sync(){
    const authed=authenticated();
    if(guideButton)guideButton.hidden=!authed;
    if(walkthroughButton)walkthroughButton.hidden=!authed;
    if(!authed)return;
    if(location.pathname==='/v1/guide'){markSeen();renderPersistentGuide();return}
    if(localStorage.getItem(KEY)!=='1')showFirstVisit();
  }

  if(guideButton)guideButton.onclick=()=>{location.href='/v1/guide'};
  if(walkthroughButton)walkthroughButton.onclick=()=>startDemo({restart:true});
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
    top_replacement = '<span class="identity-chip" id="identityChip">检查登录状态</span><button class="btn" id="walkthroughButton" hidden>完整演示</button><button class="btn" id="guideButton" hidden>使用指南</button><button class="btn" id="identityButton" hidden>切换身份</button>'
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
