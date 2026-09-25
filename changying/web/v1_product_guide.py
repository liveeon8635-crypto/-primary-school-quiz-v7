"""Role-specific, game-like onboarding for Changying V1.

The tutorial is presentation-only. It uses synthetic demo identities and keeps
progress in localStorage. It never writes school, student, teaching, billing,
authorization, score, points, classroom, or learning-evidence data.
"""

from __future__ import annotations

from changying.web import v1 as v1_module


V1_PRODUCT_GUIDE_MARKER = "changying_v1_product_guide_v4"
GUIDE_PATH = "/v1/guide"

_GUIDE_SNIPPET = r'''
<style id="changying_v1_product_guide_css_v4">
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
  #cy-v1-product-guide-page{padding:26px clamp(14px,4vw,44px) 110px;max-width:1080px;margin:0 auto}
  .cy-guide-hero{background:linear-gradient(145deg,#edf3ff,#fff);border:1px solid #d3e0f4;border-radius:22px;padding:22px}.cy-guide-hero h1{margin:8px 0}.cy-guide-hero p{color:var(--muted);line-height:1.7;max-width:760px}
  .cy-guide-summary{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin-top:16px}.cy-guide-summary>div{background:#fff;border:1px solid #dfe7f2;border-radius:15px;padding:13px}.cy-guide-summary b{display:block;margin-bottom:4px}.cy-guide-summary small{color:var(--muted);line-height:1.45}
  @media(max-width:760px){
    #tutorialButton{padding:8px 9px;font-size:12px}.top-actions{gap:5px}.top-actions .identity-chip{max-width:96px}
    #cy-onboarding-overlay{padding:0}.cy-onboarding-shell{width:100%;height:100dvh;max-height:none;border-radius:0}
    .cy-onboarding-body{padding:12px}.cy-role-grid{grid-template-columns:1fr}.cy-tutorial-layout{grid-template-columns:1fr}
    .cy-tutorial-rail{order:2}.cy-step-list{grid-template-columns:repeat(2,minmax(0,1fr))}
    .cy-step-item{grid-template-columns:26px 1fr}.cy-step-state{display:none}.cy-demo-cards,.cy-lesson-notes,.cy-guide-summary{grid-template-columns:1fr}
    .cy-lesson-top{display:block}.cy-lesson-top .cy-badge{margin-top:8px}.cy-lesson-actions{display:grid;grid-template-columns:1fr 1fr}.cy-lesson-actions .btn.primary{margin-left:0;grid-column:1/-1}
    #cy-v1-product-guide-page{padding:18px 12px 100px}
  }
</style>
<script id="changying_v1_product_guide_v4-script">
(()=>{
  if(window.__cyV1ProductGuideInstalled)return;
  window.__cyV1ProductGuideInstalled=true;

  const STATE_KEY='cyV1RoleTutorialStateV4';
  const screen=document.getElementById('screen');
  const tutorialButton=document.getElementById('tutorialButton');
  const identityButton=document.getElementById('identityButton');
  const identityChip=document.getElementById('identityChip');
  const esc=v=>String(v??'').replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));

  const teacherSteps=[
    ['workspace','进入当前教学','先确认当前周期、班级和学生。','选择“演示五年级周末班”','当前教学','班级：演示五年级周末班|学生：演示学生·小禾|本周待办：3 项','已进入本周教学工作台。','当前教学只代表现在正在发生的教学，不会改变学生长期档案。'],
    ['student','打开学生连续档案','找到同一个学生的成绩、错题、积分、课堂与历史。','打开“演示学生·小禾”','学生档案','数学平均分：82|薄弱点：小数乘法|待完成作业：1','已打开同一学生 ID 的连续档案。','成绩、作业、课堂表现、家长关系和阶段变化都围绕同一个学生 ID 累积。'],
    ['assessment','生成综合测试','用年级、科目、教材和知识模块生成诊断性内容。','生成 8 题数学综合测试','自动出题','年级：五年级|教材：人教版|题型：选择 / 填空 / 计算 / 应用','已生成一份仅用于演示的测试草稿。','AI 负责生成草稿，教师仍然负责审核后再布置。'],
    ['review','审核并布置','检查题干、答案方式、图示、难度与积分后再发布。','确认并布置给演示学生','教师审核','题目：8 题|图示：按需|积分：按规则赋值','演示作业已布置。','真实系统中教师始终保留最终发布权。'],
    ['submission','查看学生提交','从教师视角查看学生提交后的分数、知识点正确率和错题。','查看最新提交结果','提交结果','得分：75%|小数乘法：62%|错题：2 道','已读取本次学习证据。','一次提交会形成成绩、逐题证据、知识点结果和错题记录。'],
    ['targeted','生成针对性练习','根据最近测试、薄弱知识点和错题生成下一轮练习。','生成针对性练习','AI 针对性练习','依据：最近测试 + 错题|知识点：小数乘法|题数：6','已生成下一轮针对性练习草稿。','AI 建议仍需教师审核，审核后可只布置给该学生。'],
    ['reviewHandout','生成课堂复盘讲义','汇总同班学生数据，由教师决定是否形成课堂讲义。','生成复盘讲义草稿','课堂复盘','共同薄弱点：习作修改|草稿：1 份|已发布版本：0','讲义草稿已生成。','系统不会自动向学生发布；教师确认后才冻结为发布版本。'],
    ['interactive','开展互动课堂','选择教师讲、学生讲、共同讲或讨论，并用随堂检测即时收口。','开始 1 道随堂检测','互动课堂','讲解方式：师生共讲|候选学生：仅教师可见|Quick check：1 题','随堂检测已完成演示。','邀请由教师决定，学生可拒绝；课堂不会自动推进。'],
    ['points','查看积分与课堂评价','理解积分如何从练习、课堂与教师自定义评价进入积分动态。','查看演示积分动态','积分奖励','本周积分：29|练习积分：18|课堂评价：11','已打开积分动态。','重复提交不会重复加分；教师评价与自动积分来源应可追溯。'],
    ['history','查询往期教学','结束的班级、课程和学期进入只读历史。','打开上一学期记录','往期教学','2025—2026 上学期|班级：演示五年级一班|记录：完整保留','已回到历史教学记录。','历史事实保留，不会因为换班或换老师重新创建学生。'],
    ['transition','处理升年级衔接','用同一学生档案记录阶段变化和下一阶段计划。','建立五升六衔接计划','升学衔接','上一阶段：五年级|衔接类型：五升六|状态：演示计划','已建立虚拟衔接计划。','衔接记录阶段变化，学生身份和历史档案保持连续。'],
    ['hub','认识全部功能中心','最后认识角色下的完整功能入口与快捷导航。','打开全部功能地图','全部功能','教学 / 作业 / 练习 / 学情|课堂 / 积分 / 历史|账号 / 设置 / 更多工具','教师新手教学主线已走完。','以后可从右上角“新手教学”回来重做任一步。']
  ];

  const adminSteps=[
    ['overview','平台总览','从管理员视角理解机构/学校的账号、班级、教学与异常概况。','打开总览卡片','平台总览','教师账号：12|学生账号：238|当前班级：9','已打开演示总览。','总览用于发现问题，不直接改动学生学习证据。'],
    ['users','账号管理','认识教师、学生、家长账号与角色边界。','查看演示账号清单','账号管理','教师：12|学生：238|家长：176','已打开账号清单。','角色权限不同，不能用管理员入口替代教师教学操作。'],
    ['classes','班级与教学归属','查看班级、教师、学生之间的当前教学关系。','打开演示五年级一班','班级管理','班级：五年级一班|教师：钟老师（演示）|学生：32','已打开班级归属。','调班或换老师应改变教学归属，不应复制学生档案。'],
    ['pointsAdmin','积分奖励规则','查看积分规则、来源和审计，而不是直接覆盖历史积分。','查看积分规则','积分奖励','作业完成：+2|课堂表现：教师自定义|重复提交：不重复加分','已打开积分规则。','积分必须能追溯来源，修改规则不应改写历史事实。'],
    ['audit','全校审计','查看关键操作、发布、评分和关系变化的审计记录。','筛选今日审计事件','全校审计','发布讲义：3|评分确认：18|身份变更：2','已筛选演示审计。','审计用于追溯谁在什么时候做了什么。'],
    ['system','系统设置','认识系统级设置与教学数据之间的边界。','打开系统设置','系统设置','登录安全|教学周期|功能开关','已打开系统设置。','系统设置不能绕过业务权限或直接篡改学习证据。'],
    ['historyAdmin','历史与连续性','从管理员视角确认历史班级、学生关系和阶段变化仍可追踪。','查看历史班级','历史查询','往期班级：14|连续学生档案：238|历史关系：保留','已完成连续性检查。','管理员应能核对关系历史，但学生仍是一份连续档案。']
  ];

  const studentSteps=[
    ['classroom','进入课堂','查看当前课堂、教师邀请和随堂检测。','进入演示课堂','我的课堂','当前知识点：小数乘法|互动状态：可参与|Quick check：待完成','已进入演示课堂。','学生可接受或拒绝讲解邀请，拒绝不会形成负面学习证据。'],
    ['assignments','查看作业','区分待完成、已完成和逾期作业。','打开“数学巩固练习”','我的作业','待完成：1|已完成：5|逾期：0','已打开待完成作业。','作业与教师布置、截止时间和学生提交状态关联。'],
    ['answer','逐题作答','体验不同题型、上下题切换和必要图示。','完成演示第 1 题','练习作答','题型：计算题|进度：1 / 8|可切换上下题','演示答案已保存。','作答过程允许切题，题干与答案输入方式应匹配。'],
    ['submit','提交与查看结果','提交后查看得分、知识点正确率、错题和积分变化。','提交演示练习','提交结果','得分：75%|薄弱点：小数乘法|新增积分：+6','演示提交完成。','真实系统会防止重复提交重复加分。'],
    ['practice','做针对性练习','查看教师审核后只针对自己的下一轮练习。','打开针对性练习','针对性练习','来源：上次测试|知识点：小数乘法|题数：6','已进入针对性练习。','针对性练习应能说明“为什么给我这些题”。'],
    ['progress','查看学情','从自己的长期档案看成绩、知识点和近期变化。','打开我的学情','我的学情','数学：82|英语：88|最近提升：阅读概括','已打开学情页。','这里看的是长期趋势，不只是一次考试。'],
    ['rewards','查看积分与表现','查看积分来源、课堂表现和奖励记录。','打开积分动态','积分动态','总积分：29|本周：+8|最近来源：练习完成','已打开积分动态。','积分来源应清晰，不能只显示一个总数。'],
    ['more','认识更多功能','认识错题、历史记录、账号和其他学生入口。','打开更多功能地图','更多','错题本|历史练习|账号设置|课堂记录','学生新手教学已走完。','以后可随时从“新手教学”回来继续或重做。']
  ];

  const parentSteps=[
    ['childLearning','查看孩子课程','先找到孩子当前课程、班级和教师。','打开孩子课程','孩子课程','学生：演示学生·小禾|班级：五年级一班|教师：钟老师（演示）','已打开孩子当前课程。','家长看到的是已授权孩子，不是任意学生。'],
    ['childAssignments','查看孩子作业','查看待完成、已完成和截止时间。','打开孩子作业','孩子作业','待完成：1|本周已完成：3|逾期：0','已打开孩子作业。','家长看到状态，不替学生直接完成作答。'],
    ['childProgress','查看孩子学情','理解分数、知识点正确率和长期趋势。','打开孩子学情','孩子学情','数学：82|薄弱点：小数乘法|近 4 周：上升','已打开孩子学情。','重点是趋势和需要支持的知识点，而不是单次排名。'],
    ['childRewards','查看课堂表现','查看课堂参与、积分与教师评价。','打开课堂表现','课堂表现','积分：29|讲解参与：1 次|教师评价：积极','已打开课堂表现。','课堂评价与积分要能看到来源和时间。'],
    ['historyParent','理解连续档案','查看孩子换班、升年级后历史是否仍在同一档案里。','查看往期记录','连续档案','五年级：保留|六年级：继续同一 ID|家长关系：持续','已查看连续档案。','升年级不会重新生成一个“新孩子”。'],
    ['account','我的与账号','查看自己的账号、关联孩子和安全设置。','打开我的账号','我的','关联孩子：1|账号安全：正常|通知：演示','家长新手教学已走完。','以后可从右上角“新手教学”返回任一步。']
  ];

  const personas=[
    {id:'institution_teacher',icon:'👩‍🏫',name:'机构老师',account:'演示账号 · 周老师',desc:'从教学、作业、练习、AI 针对性、课堂复盘到升年级，走完整教师闭环。',steps:teacherSteps},
    {id:'school_teacher',icon:'📚',name:'学校教师',account:'演示账号 · 林老师',desc:'与教师主线相同，但用学校班级、课表和校内教学语境演示。',steps:teacherSteps},
    {id:'institution_admin',icon:'🏫',name:'机构管理员',account:'演示账号 · 机构负责人',desc:'学习账号、班级、积分、审计和系统设置等管理能力。',steps:adminSteps},
    {id:'school_admin',icon:'🏛️',name:'学校管理员',account:'演示账号 · 教务管理员',desc:'以学校数据域演示账号、班级、审计和系统治理。',steps:adminSteps},
    {id:'student',icon:'🎒',name:'学生',account:'演示账号 · 小禾',desc:'亲自走课堂、作业、练习、提交、学情、积分和更多功能。',steps:studentSteps},
    {id:'parent',icon:'👪',name:'家长',account:'演示账号 · 小禾家长',desc:'从家长视角查看课程、作业、学情、课堂表现与连续档案。',steps:parentSteps}
  ];

  const currentPersonaId=()=>{
    const label=String(identityChip?.textContent||'');
    if(label.includes('学校教师'))return 'school_teacher';
    if(label.includes('机构老师'))return 'institution_teacher';
    if(label.includes('学校管理员'))return 'school_admin';
    if(label.includes('机构管理员'))return 'institution_admin';
    if(label.includes('家长'))return 'parent';
    if(label.includes('学生'))return 'student';
    return '';
  };
  const currentPersona=()=>personas.find(p=>p.id===currentPersonaId())||null;
  const seenKey=id=>'cyV1RoleTutorialSeenV4:'+id;
  const identityReady=()=>Boolean(identityButton&&identityButton.hidden===false&&currentPersonaId());
  const loadState=()=>{try{return JSON.parse(localStorage.getItem(STATE_KEY)||'{}')||{}}catch{return{}}};
  const saveState=s=>localStorage.setItem(STATE_KEY,JSON.stringify(s));
  const personaState=id=>loadState()[id]||{index:0,status:{}};
  const completion=p=>{const st=personaState(p.id),total=p.steps.length,settled=Object.values(st.status||{}).filter(x=>x==='done'||x==='skipped').length;return{settled,total,pct:Math.round((settled/Math.max(1,total))*100)}};
  const markSeen=id=>{if(id)localStorage.setItem(seenKey(id),'1')};
  const statusText=s=>s==='done'?'已完成':s==='skipped'?'已跳过':'未开始';

  function closeOverlay(){document.getElementById('cy-onboarding-overlay')?.remove()}
  function mountShell(){
    closeOverlay();
    const overlay=document.createElement('div');overlay.id='cy-onboarding-overlay';
    overlay.innerHTML='<section class="cy-onboarding-shell" role="dialog" aria-modal="true"><header class="cy-onboarding-head"><div><strong>长缨新手教学</strong><small>虚拟演示账户 · 不写真实数据</small></div><button class="btn" id="cy-onboarding-close">退出并保存</button></header><div class="cy-onboarding-body"></div></section>';
    document.body.appendChild(overlay);
    overlay.querySelector('#cy-onboarding-close').onclick=closeOverlay;
    return overlay;
  }

  function roleCards(){
    return personas.map(p=>{
      const c=completion(p);
      return '<button class="cy-role-card" data-persona="'+p.id+'"><span class="cy-role-icon">'+p.icon+'</span><b>'+esc(p.name)+'</b><span class="cy-role-meta">'+esc(p.account)+' · '+c.settled+'/'+c.total+' 步</span><p>'+esc(p.desc)+'</p><span class="cy-role-progress"><i style="width:'+c.pct+'%"></i></span></button>';
    }).join('');
  }

  function showCurrentIntro({firstVisit=false}={}){
    const persona=currentPersona();
    if(!persona)return;
    markSeen(persona.id);
    const overlay=mountShell(),body=overlay.querySelector('.cy-onboarding-body'),progress=completion(persona);
    body.innerHTML='<section class="cy-lesson-card" style="max-width:760px;margin:0 auto"><span class="tag">'+(firstVisit?'首次登录引导':'继续新手教学')+'</span><h1 style="margin:10px 0 7px">'+persona.icon+' '+esc(persona.name)+'：系统会按顺序带你走完整条主线</h1><p class="subtitle">这是与你当前登录身份匹配的虚拟教学流程。不会让你先自己挑功能；系统会从第 1 步开始解释“为什么先做这一步”，完成后再带到下一步。每一步可以跳过，退出后会保存进度。</p><div class="cy-guide-summary"><div><b>'+progress.total+' 个连续步骤</b><small>按真实使用顺序建立整体产品概览</small></div><div><b>'+progress.settled+' 步已处理</b><small>完成与跳过都会保留在本机浏览器</small></div><div><b>0 条真实业务写入</b><small>全部使用虚拟演示页面与合成数据</small></div></div><div class="cy-guide-actions"><button class="btn primary" id="cy-current-start">'+(progress.settled?'继续当前进度':'从第 1 步开始')+'</button><button class="btn" id="cy-current-exit">暂不学习</button></div></section>';
    body.querySelector('#cy-current-start').onclick=()=>startPersona(persona.id);
    body.querySelector('#cy-current-exit').onclick=closeOverlay;
  }

  function startPersona(id,index=null){
    markSeen(id);
    const persona=personas.find(p=>p.id===id);if(!persona)return;
    const st=personaState(id);
    const firstIncomplete=persona.steps.findIndex(step=>!['done','skipped'].includes(st.status?.[step[0]]));
    const target=index===null?(firstIncomplete>=0?firstIncomplete:Math.min(Number(st.index)||0,persona.steps.length-1)):index;
    renderLesson(persona,Math.max(0,Math.min(persona.steps.length-1,target)));
  }

  function updatePersona(id,updater){
    const state=loadState(),current=state[id]||{index:0,status:{}};
    state[id]=updater({...current,status:{...(current.status||{})}})||current;
    saveState(state);
  }

  function renderLesson(persona,index){
    const overlay=document.getElementById('cy-onboarding-overlay')||mountShell();
    const body=overlay.querySelector('.cy-onboarding-body');
    const st=personaState(persona.id),step=persona.steps[index],stepId=step[0],pct=Math.round(((index+1)/persona.steps.length)*100);
    updatePersona(persona.id,s=>({...s,index}));
    const rail=persona.steps.map((x,i)=>{
      const status=personaState(persona.id).status?.[x[0]]||'';
      return '<div class="cy-step-item '+(i===index?'active ':'')+(status||'')+'"><span class="cy-step-no">'+(i+1)+'</span><span><b>'+esc(x[1])+'</b><small class="cy-step-state">'+statusText(status)+'</small></span><span class="cy-step-state">'+(status==='done'?'✓':status==='skipped'?'↷':'')+'</span></div>';
    }).join('');
    const items=String(step[5]).split('|').map(x=>{const parts=x.split('：');return '<div class="cy-demo-card"><b>'+esc(parts.shift())+'</b><small>'+esc(parts.join('：'))+'</small></div>'}).join('');
    body.innerHTML='<div class="cy-tutorial-layout"><aside class="cy-tutorial-rail"><div><span class="cy-badge">'+persona.icon+' '+esc(persona.name)+'</span><p style="font-size:12px;color:var(--muted);line-height:1.5;margin:8px 2px">'+esc(persona.account)+'</p><p style="font-size:11px;color:var(--muted);line-height:1.5">步骤路线仅用于查看进度，系统会按顺序引导，不需要你自己选择下一项。</p></div><div class="cy-step-list">'+rail+'</div></aside><section class="cy-tutorial-stage"><article class="cy-lesson-card"><div class="cy-lesson-top"><div><span class="tag">新手任务 '+(index+1)+'</span><h2>'+esc(step[1])+'</h2><p>'+esc(step[2])+'</p></div><span class="cy-badge">'+(st.status?.[stepId]==='done'?'✓ 已完成':st.status?.[stepId]==='skipped'?'↷ 已跳过':'进行中')+'</span></div><div class="cy-progress-row"><span>第 '+(index+1)+' / '+persona.steps.length+' 步</span><div class="cy-progress-track"><i style="width:'+pct+'%"></i></div><span>'+pct+'%</span></div><div class="cy-mission"><strong>这一关你要做</strong><p>'+esc(step[3])+'</p></div><section class="cy-demo-app"><div class="cy-demo-appbar"><b>'+persona.icon+' '+esc(persona.account)+'</b><span>虚拟演示 · '+esc(persona.name)+'</span></div><div class="cy-demo-canvas"><div class="cy-demo-screen-title">'+esc(step[4])+'</div><div class="cy-demo-screen-sub">以下均为演示数据，不会写入真实学生、积分、作业、课堂或学习证据。</div><div class="cy-demo-cards">'+items+'</div><div class="cy-demo-action"><button class="btn primary" id="cy-do-action">'+esc(step[3])+'</button></div><div class="cy-demo-feedback" id="cy-demo-feedback">'+esc(step[6])+'</div></div></section><div class="cy-lesson-notes"><div class="cy-note"><strong>你刚做了什么</strong><p>'+esc(step[3])+'</p></div><div class="cy-note"><strong>系统为什么这样做</strong><p>'+esc(step[7])+'</p></div><div class="cy-note"><strong>真实使用时注意</strong><p>演示不会产生真实业务写入；进入真实系统后仍按当前账号权限、教师审核和审计规则执行。</p></div></div><div class="cy-lesson-actions"><button class="btn" id="cy-prev" '+(index===0?'disabled':'')+'>上一步</button><button class="btn" id="cy-skip">跳过本步</button><button class="btn primary" id="cy-next" disabled>完成本步并继续</button></div><p class="cy-skip-note">“跳过本步”只影响新手教学进度；退出后仍可从右上角“新手教学”继续整条引导，完成后也可以重新开始。</p></article></section></div>';
    let actionDone=false;
    const doAction=body.querySelector('#cy-do-action'),feedback=body.querySelector('#cy-demo-feedback'),next=body.querySelector('#cy-next');
    doAction.onclick=()=>{actionDone=true;doAction.disabled=true;doAction.textContent='演示操作已完成 ✓';feedback.classList.add('show');next.disabled=false};
    if(st.status?.[stepId]==='done'){actionDone=true;doAction.disabled=true;doAction.textContent='演示操作已完成 ✓';feedback.classList.add('show');next.disabled=false}
     body.querySelector('#cy-prev').onclick=()=>index>0&&renderLesson(persona,index-1);
    body.querySelector('#cy-skip').onclick=()=>{
      updatePersona(persona.id,s=>{s.status[stepId]='skipped';s.index=Math.min(index+1,persona.steps.length-1);return s});
      if(index===persona.steps.length-1)showCompletion(persona);else renderLesson(persona,index+1);
    };
    next.onclick=()=>{
      if(!actionDone)return;
      updatePersona(persona.id,s=>{s.status[stepId]='done';s.index=Math.min(index+1,persona.steps.length-1);return s});
      if(index===persona.steps.length-1)showCompletion(persona);else renderLesson(persona,index+1);
    };
  }

  function showCompletion(persona){
    const overlay=document.getElementById('cy-onboarding-overlay')||mountShell(),body=overlay.querySelector('.cy-onboarding-body'),c=completion(persona);
    body.innerHTML='<section class="cy-lesson-card" style="max-width:720px;margin:0 auto"><span class="cy-badge">'+persona.icon+' '+esc(persona.name)+'</span><h1 style="margin:12px 0 8px">你已经建立了这个身份的完整使用概览</h1><p class="subtitle">本轮已处理 '+c.settled+' / '+c.total+' 步。跳过的步骤仍保留记录；以后登录这个身份时，可以从右上角“新手教学”重新开始或继续复习。</p><div class="cy-guide-actions"><button class="btn primary" id="cy-complete-restart">重新开始本身份教学</button><button class="btn" id="cy-complete-exit">退出并保存</button></div></section>';
    body.querySelector('#cy-complete-restart').onclick=()=>{
      updatePersona(persona.id,s=>({...s,index:0,status:{}}));
      renderLesson(persona,0);
    };
    body.querySelector('#cy-complete-exit').onclick=closeOverlay;
  }

  function renderPersistentGuide(){
    if(!screen||screen.querySelector('#cy-v1-product-guide-page'))return;
    const persona=currentPersona();
    if(!persona){
      screen.innerHTML='<main id="cy-v1-product-guide-page"><section class="cy-guide-hero"><span class="tag">新手教学</span><h1>请先完成账号登录并选择身份</h1><p>新手教学会根据你真实登录后的身份显示对应流程；未登录或尚未选择身份时不会提前展示。</p></section></main>';
      return;
    }
    const progress=completion(persona);
    screen.innerHTML='<main id="cy-v1-product-guide-page"><section class="cy-guide-hero"><span class="tag">'+persona.icon+' '+esc(persona.name)+'</span><h1>当前身份的新手教学</h1><p>系统会按顺序带你走完整流程，而不是让你先自己选择功能。每一步都有“为什么先做这一步 / 现在要做什么 / 完成后得到什么”。</p><div class="cy-guide-actions"><button class="btn primary" id="cy-guide-start">'+(progress.settled?'继续新手教学':'开始新手教学')+'</button><button class="btn" id="cy-guide-restart">从头开始</button></div><div class="cy-guide-summary"><div><b>'+progress.total+' 步</b><small>当前身份完整主线</small></div><div><b>'+progress.settled+' 步已处理</b><small>包含完成和主动跳过</small></div><div><b>随时可回来</b><small>右上角“新手教学”长期保留</small></div></div></section><section class="card" style="margin-top:18px"><h2>为什么采用顺序引导？</h2><p style="color:var(--muted);line-height:1.75">新用户先建立整体使用方向，再进入真实操作。路线图只负责显示进度，不作为自由功能菜单；真正的功能入口仍由当前身份的工作台和快捷导航承担。</p></section></main>';
    screen.querySelector('#cy-guide-start').onclick=()=>startPersona(persona.id);
    screen.querySelector('#cy-guide-restart').onclick=()=>{updatePersona(persona.id,s=>({...s,index:0,status:{}}));startPersona(persona.id,0)};
  }

  function renderPersistentGuideRefresh(){
    const old=screen?.querySelector('#cy-v1-product-guide-page');if(old)old.remove();renderPersistentGuide();
  }

  function sync(){
    const ready=identityReady(),persona=currentPersona();
    if(tutorialButton)tutorialButton.hidden=!ready;
    if(!ready)return;
    if(location.pathname==='/v1/guide'){markSeen(persona.id);renderPersistentGuide();return}
    if(localStorage.getItem(seenKey(persona.id))!=='1')showCurrentIntro({firstVisit:true});
  }

  if(tutorialButton)tutorialButton.onclick=()=>showCurrentIntro();
  if(screen)new MutationObserver(()=>queueMicrotask(sync)).observe(screen,{childList:true,subtree:false});
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
