"""Role-specific, game-like onboarding for Changying V1.

The tutorial is presentation-only. It uses synthetic demo identities and keeps
progress in localStorage. It never writes school, student, teaching, billing,
authorization, score, points, classroom, or learning-evidence data.
"""

from __future__ import annotations

from changying.web import v1 as v1_module
from changying.web import v1_classic_gzip_embed as classic_embed_module


V1_PRODUCT_GUIDE_MARKER = "changying_v1_product_guide_v5"
GUIDE_PATH = "/v1/guide"
CLASSIC_GUIDE_RESUME_MARKER = "changying_v1_live_guide_resume_v1"

_CLASSIC_GUIDE_RESUME_SNIPPET = r'''
<style id="changying_v1_live_guide_resume_v1-css">
  #cy-live-guide-resume{position:fixed;right:12px;bottom:calc(78px + env(safe-area-inset-bottom));z-index:124;display:none;align-items:center;gap:7px;border:1px solid #bfd2f4;border-radius:999px;background:#fff;color:#173a78;padding:9px 12px;font:700 12px -apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif;box-shadow:0 10px 28px rgba(23,58,120,.16);text-decoration:none}
  @media(max-width:640px){#cy-live-guide-resume{left:12px;right:auto;bottom:calc(78px + env(safe-area-inset-bottom));max-width:52vw;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
</style>
<a id="cy-live-guide-resume" href="/v1/guide?resume=1">▶ 继续新手教学</a>
<script id="changying_v1_live_guide_resume_v1-script">
(()=>{
  const ACTIVE='cyV1RoleTutorialActivePersonaV5';
  const el=document.getElementById('cy-live-guide-resume');
  const sync=()=>{if(el)el.style.display=localStorage.getItem(ACTIVE)?'inline-flex':'none'};
  window.addEventListener('pageshow',sync);window.addEventListener('storage',sync);sync();
})();
</script>
'''


def patch_classic_guide_resume(html: str) -> str:
    if CLASSIC_GUIDE_RESUME_MARKER in html:
        return html
    if "</body>" not in html:
        raise RuntimeError("V1 live guide resume: closing body marker not found")
    return html.replace(
        "</body>",
        _CLASSIC_GUIDE_RESUME_SNIPPET + f"\n<!-- {CLASSIC_GUIDE_RESUME_MARKER} -->\n</body>",
        1,
    )


_GUIDE_SNIPPET = r'''
<style id="changying_v1_product_guide_css_v5">
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
  .cy-live-box{margin-top:14px;padding:13px;border:1px solid #cfe0f7;border-radius:15px;background:#f4f8ff}.cy-live-box strong{display:block;color:#173a78;font-size:13px;margin-bottom:5px}.cy-live-box p{margin:0;color:#526178;font-size:12px;line-height:1.6}.cy-live-actions{display:flex;gap:8px;flex-wrap:wrap;margin-top:10px}.cy-live-actions .btn{min-height:40px}.cy-finish-sign{margin-top:10px;padding:10px 12px;border-radius:12px;background:#fff8e8;border:1px solid #f5d79a;color:#7a4a00;font-size:12px;line-height:1.55}
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
<script id="changying_v1_product_guide_v5-script">
(()=>{
  if(window.__cyV1ProductGuideInstalled)return;
  window.__cyV1ProductGuideInstalled=true;

  const STATE_KEY='cyV1RoleTutorialStateV5';
  const ACTIVE_PERSONA_KEY='cyV1RoleTutorialActivePersonaV5';
  const screen=document.getElementById('screen');
  const tutorialButton=document.getElementById('tutorialButton');
  const identityButton=document.getElementById('identityButton');
  const identityChip=document.getElementById('identityChip');
  const esc=v=>String(v??'').replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));

  const teacherSteps=[
    ['intro','先认识长缨解决什么问题','先建立产品全局概念：把班级、学生、作业、学情、AI针对练习、课堂与历史连成一条连续闭环。','看一遍教师完整闭环地图','教师使用全景','起点：班级与学生|中段：组卷 / 作业 / 提交|反馈：学情 / 错题 / 针对练习|延伸：课堂 / 积分 / 历史','你已经知道这不是单一题库，而是一套围绕学生连续档案运行的教学闭环。','先理解闭环，再学习按钮，后面的操作才不会变成“功能找功能”。','/v1/workspace','你能说清“班级→学生→组卷/作业→提交→学情→针对练习→课堂→连续档案”这条主线。'],
    ['createClass','建立第一个班级','班级是教师组织学生、作业、积分和课堂数据的第一层容器。','进入“全部功能 → 班级学生”并建立一个真实班级','班级学生','班级名称：按你的真实教学场景填写|年级：与学生当前年级一致|教师：当前登录教师','建立班级后，后续学生、作业、积分与课堂都有明确归属。','长缨不会用“测试数据班级”替代你的实际教学关系；真实班级由你决定是否创建。','/v1/tool?page=classes','页面中能看到你准备使用的班级；如果暂时不需要，可直接跳过。'],
    ['addStudent','添加学生账号并加入班级','学生账号同时是登录身份和长期连续档案入口；以后换班、换老师、升年级都沿用同一学生。','在“班级学生”里添加至少一个学生账号，或确认已有学生已在正确班级','学生账号','姓名：真实学生姓名|账号：供学生登录|初始密码：首次登录后应修改|班级：刚刚建立或已有班级','学生建立后，教师端和学生端开始围绕同一 student_id 累积记录。','这一步决定后续所有成绩、错题、积分、课堂表现能否正确回到同一名学生。','/v1/tool?page=classes','班级中能看到学生，且学生有可用登录账号。'],
    ['parentLink','按需绑定家长','如果需要家长查看课程、作业、学情与课堂表现，可把家长账号绑定到学生；不需要时可跳过。','确认是否需要家长参与，并在需要时完成家长关联','家校协同','家长：只看已授权孩子|学生：仍保持独立连续档案|教师：保留教学操作权','你已经知道家长端是查看与支持角色，不替学生作答，也不替教师发布。','家长关系是可选协同层，不应改变学生本人档案。','/v1/tool?page=classes','需要家长协同时，学生记录中能看到正确家长；否则本步可跳过。'],
    ['resources','准备教材与教学资料','先确认年级、科目和教材，再使用题库、AI出题或教案，能减少“内容对不上版”的问题。','进入“教材教案”，确认你真实使用的教材与资料','教材教案','科目：语文 / 数学 / 英语|教材：以实际使用版本为准|资料：教材 / 教案 / 课件 / 练习','后续 AI 与组卷都有了更明确的教学上下文。','教材和教学目标是内容生成的约束条件，不是装饰信息。','/v1/tool?page=resources','你知道当前班级实际使用什么教材，并能找到对应资料入口。'],
    ['questionBank','准备题目：题库或 AI 出题','你可以使用题库已有题，也可以让 AI 按年级、科目、教材、知识点和题型生成草稿。','进入“AI 助手”或“教材题库”，准备一批用于本次教学的题目','AI / 题库','AI：生成草稿|题库：复用已审核题|题型：选择 / 判断 / 填空 / 计算 / 应用|图示：按需','题目来源准备完成后，下一步进入教师审核与组卷。','AI 生成不能替代教师审核；题干、答案方式、教材版本、难度和图示都要能人工确认。','/v1/tool?page=ai','至少知道如何获得题目，并能区分“AI草稿”和“已审核可用题”。'],
    ['paper','组卷并布置作业','把题目组织成试卷/练习，再明确班级、学生、截止时间和提交方式。','进入“组卷作业”，创建或选择试卷并布置给目标学生','组卷作业','试卷：选择已审核题目|对象：班级或个别学生|截止：按教学安排|积分：按规则记录','作业发布后，学生端会出现待完成任务。','“生成题目”和“真正布置给学生”是两个边界；教师应在发布前做最后确认。','/v1/tool?page=papers','目标学生能收到正确的作业/测试，题数、对象和截止时间都符合预期。'],
    ['studentExperience','理解学生实际会经历什么','学生看到的是课堂/作业入口，逐题作答，可切换上下题；提交后才显示结果，并把证据回流档案。','查看学生侧操作预览，确认题干、答案输入方式和提交体验','学生作答','开始：打开待完成作业|过程：逐题作答 / 上下题|提交：一次确认|结果：分数 / 错题 / 积分','你已经从学生角度检查了教师布置最终会变成什么体验。','教师端配置是否正确，最终要以学生能否顺畅完成为准。','','你能解释学生从收到作业到提交结果的全过程。'],
    ['evidence','查看提交、错题和学情反馈','学生提交后，教师不只看总分，还要看知识点正确率、具体错题和长期变化。','进入学生档案或学情分析，查看一次真实/已有提交如何回流','学习反馈','成绩：本次结果|知识点：正确率与薄弱点|错题：具体题目|档案：长期累计','一次练习已经变成后续教学可继续使用的学习证据。','长缨的价值在“反馈继续驱动下一步”，而不是做完一张卷子就结束。','/v1/student','你能找到某名学生最近一次作业/测试以及对应薄弱知识点。'],
    ['targeted','生成并审核 AI 针对性练习','针对性练习应关联最近测试、教材、知识点正确率和具体错题，而不是随机再出一套题。','进入 AI 助手，基于最近学习反馈生成针对性练习，并理解教师审核边界','AI 针对练习','依据：最近测试 + 错题|目标：薄弱知识点|对象：个别学生|发布：教师审核后','下一轮练习与上一轮真实反馈形成关联。','AI 负责给建议，教师负责判断是否合适以及是否布置。','/v1/tool?page=ai','你能说清“为什么给这个学生这些题”，并知道发布前需要审核。'],
    ['classroom','把练习反馈带回课堂','同班学生完成练习后，可以汇总共同问题，由教师决定是否生成课堂复盘讲义，并进一步进入互动讲解与随堂检测。','回到当前教学，了解“数据汇总→复盘讲义→互动课堂→随堂检测”的课堂闭环','课堂复盘','汇总：班级共同薄弱点|讲义：教师决定生成/发布|讲解：教师 / 学生 / 共讲 / 讨论|检测：随堂 quick check','课后数据已经能反过来支持下一堂课。','课堂环节不会自动替教师发布、指定学生或推进流程。','/v1/workspace','你知道一份学生练习数据怎样转化为课堂复盘和即时检测。'],
    ['points','理解积分与教师评价','练习、课堂参与和教师自定义评价可以进入积分动态，但来源必须清楚、重复提交不能重复加分。','进入“课堂积分”，查看规则与学生积分来源','积分与激励','来源：练习 / 课堂 / 教师评价|规则：可配置|历史：可追溯|重复：防重复','你已经知道积分是教学激励记录，不是孤立排行榜。','积分应服务学习行为反馈，并保持来源和审计可追溯。','/v1/tool?page=classPoints','你能找到一条积分记录的来源，并知道如何查看或设置班级规则。'],
    ['history','学会回看往期教学','班级结束、换老师或换学期后，旧教学进入只读历史，但学生本人仍是同一份连续档案。','进入“往期教学”，看看历史是怎样保留的','往期教学','学年 / 学期：按时间查|旧班级：保留|作业与成绩：保留|学生 ID：不变','你已经知道当前工作台和历史记录如何分工。','“当前教学”只负责现在；历史事实不应因新学期被覆盖。','/v1/history','你能找到历史入口，并理解旧记录为何不应被重新编辑成当前状态。'],
    ['transition','处理升年级与升学衔接','升年级不重新创建学生，而是在同一档案上记录阶段变化、差距和衔接计划。','进入“升学衔接”，理解同一学生如何跨阶段继续','升学衔接','上一阶段：已有事实|下一阶段：新要求|衔接：检查 / 计划 / 诊断|学生：同一 ID','你已经理解长期档案为什么能跨班级、教师和年级连续。','连续性是长缨区别于“一次性题库/作业工具”的核心之一。','/v1/transition','你能解释升年级后为什么不能新建一个重复学生。'],
    ['feedback','学会边用边反馈','使用过程中遇到“不好懂、找不到、流程不顺、功能不符合预期”时，可以直接把当前页面和步骤一起反馈。','打开产品助手的“提反馈”，写一句你真实遇到的问题或建议','产品反馈','问产品：随时问怎么用|提反馈：附带当前页与身份|Freeman：汇总进项目反馈|改进：供后续筛选','新手教学不是一次性说明书，而是可以随着真实使用持续改进。','产品教学和真实使用之间应形成反馈闭环。','','你知道以后不需要退出产品或另找文档，就能随时提问和反馈。']
  ];



  const adminSteps=[
    ['introAdmin','先认识管理员在系统里的作用','管理员负责账号、权限、班级归属、规则与审计，不替教师完成教学判断。','查看管理员产品地图','管理员全景','账号：建立身份|班级：组织归属|规则：积分 / AI / 系统|审计：追溯关键操作','你已经知道管理员负责“搭好环境和治理边界”。','管理能力与教师教学能力必须分层。','/v1/tool?page=admin','你能区分管理员和教师各自负责什么。'],
    ['users','建立教师/家长等账号','先让需要使用系统的人获得正确角色账号，再进入后续班级和教学关系。','进入“账号管理”，检查或建立所需账号','账号管理','教师：教学操作|学生：学习与连续档案|家长：授权查看|管理员：系统治理','账号角色明确后，权限边界才稳定。','不要用共享账号替代角色体系。','/v1/tool?page=users','所需人员都有正确角色账号，且无明显重复账号。'],
    ['classes','建立班级与教学归属','班级、教师、学生关系决定谁能看到和操作哪些教学数据。','在账号/班级相关入口确认班级、教师和学生归属','班级归属','班级：年级明确|教师：当前负责人|学生：加入正确班级|历史：变更可追溯','组织关系建立后，教师工作台才有正确数据。','换班或换教师应改变关系，不应复制学生。','/v1/tool?page=users','能确认一个班级的教师和学生归属是否正确。'],
    ['aiAdmin','按需配置 AI 能力','AI 是可选能力；管理员负责模型与额度等安全配置，教师负责具体内容审核。','进入“AI 设置”检查当前是否可用；不使用 AI 可跳过','AI 设置','状态：启用 / 未启用|模型：按配置|安全：调用限制|教师：只审核业务内容','你已经知道系统在没有 AI 时仍可使用基础教学能力。','模型配置和教学内容审核是两层责任。','/v1/tool?page=ai','你知道当前 AI 是否可用，以及教师遇到不可用时应该找谁。'],
    ['pointsAdmin','设置积分规则','积分规则决定哪些学习和课堂行为形成激励记录。','进入“积分奖励”查看学校/班级规则','积分规则','作业完成：按规则|课堂表现：可自定义|重复提交：不重复|历史：不回写改造','规则调整有明确边界，不应改写过去事实。','积分是可审计激励机制。','/v1/tool?page=pointsAdmin','你能找到积分规则并解释一条积分为什么产生。'],
    ['audit','学会用审计追溯操作','发布、评分、账号与关系变化等关键动作应能追溯。','进入“全校审计”查看最近关键操作','全校审计','谁：操作人|何时：时间|做了什么：动作|对象：班级 / 学生 / 作业','出了问题时有事实可查。','审计记录用于追溯，不是替代业务页面。','/v1/tool?page=adminAudit','你能从审计里找到最近一条关键操作的来源。'],
    ['system','认识系统设置边界','系统设置用于全局体验与安全，不应绕过业务权限直接改学习事实。','进入“系统设置”浏览可配置项','系统设置','登录安全|功能开关|教学周期|其他全局设置','你知道什么应在设置里改，什么必须回业务流程改。','避免用“后台万能修改”破坏业务事实。','/v1/tool?page=system','你能区分系统配置和学生/教学数据。'],
    ['feedbackAdmin','建立管理反馈闭环','管理员也可以把账号、权限、班级、审计或流程问题直接反馈给产品。','用产品助手提交一条管理侧问题或建议','管理反馈','当前页面：自动附带|身份：管理员|问题：一句话描述|项目反馈：同步汇总','系统治理问题也进入持续改进列表。','真实使用者的反馈比预设功能清单更能暴露管理缺口。','','你知道如何随时反馈管理侧问题。']
  ];



  const studentSteps=[
    ['introStudent','先认识学生端是做什么的','学生端把课堂、作业、练习、错题、学情和积分放在同一学习路径里。','查看学生学习地图','学生使用全景','课堂：跟随当前教学|作业：完成教师任务|练习：自主或针对性|反馈：错题 / 学情 / 积分','你已经知道学生端不是只有“答题”一个功能。','每次学习结果都会继续回到自己的长期档案。','','你能说清课堂、作业、练习、学情之间的关系。'],
    ['classroom','进入课堂','当前课堂用于接收教师互动邀请、讲解任务和随堂检测。','进入“同步课堂”，看看当前是否有课堂任务','同步课堂','邀请：可接受或拒绝|讲解：按教师安排|随堂检测：课堂即时作答','你知道课堂互动不会自动给你负面评价。','拒绝邀请不扣分，也不形成负面学习证据。','/v1/tool?page=syncLearning','你能找到同步课堂入口。'],
    ['assignments','查看待完成作业','先区分待完成、已完成和逾期，再选择当前要做的任务。','进入“我的作业”打开一份待完成任务','我的作业','待完成：优先处理|已完成：可回看|逾期：按教师规则补交','你已经知道作业从哪里进入。','作业和教师布置对象、截止时间、提交方式有关。','/v1/tool?page=assignments','你能找到一份待完成或历史作业。'],
    ['answer','逐题作答并检查输入方式','选择题、填空、计算、简答应使用匹配的作答方式，必要时题目会有图示。','在作业中完成至少一题，体验上下题切换','逐题作答','选择：点选|填空/计算：输入|应用题：简答|导航：上一题 / 下一题','你知道提交前如何检查是否漏题。','题干和答案输入方式必须匹配。','/v1/tool?page=assignments','你能顺利完成一题并切换到下一题。'],
    ['submit','提交并查看结果','提交后才进入成绩、错题、知识点和积分反馈。','完成一份可提交任务，或查看已完成任务的结果','提交结果','成绩：本次结果|错题：具体题目|知识点：掌握反馈|积分：按规则增加','一次学习已经进入自己的连续档案。','重复提交不会重复加分。','/v1/tool?page=assignments','你知道提交后去哪里看结果。'],
    ['practice','使用自主/针对性练习','自主练习用于主动巩固；针对性练习说明为什么给你这些题。','进入“自主练习”，看看可以选择哪些内容','自主练习','自主：自己选内容|针对性：来自教师审核和薄弱点|题型：按内容匹配','你知道什么时候适合主动练，什么时候是在完成针对性任务。','练习不是孤立刷题，应与学情反馈关联。','/v1/tool?page=practice','你能找到自主练习入口并理解针对性练习来源。'],
    ['wrongbook','使用错题本','错题本帮助回看真正做错过的内容，并继续巩固。','进入“我的错题”查看已有错题','我的错题','题目：错误记录|知识点：关联|状态：后续可处理','你知道错题不会因为做了新练习而丢失。','错题是后续针对性练习的重要依据。','/v1/tool?page=wrongbook','你能找到历史错题。'],
    ['progress','查看长期学情','学情不是只看一次分数，而是看知识点和一段时间的变化。','进入“我的学情”查看近期变化','我的学情','成绩：阶段结果|知识点：正确率|趋势：持续变化|档案：跨学期保留','你已经知道如何看自己的学习趋势。','长期趋势比单次排名更适合决定下一步练什么。','/v1/tool?page=progress','你能指出一个最近需要继续加强的知识点。'],
    ['rewards','查看积分与来源','积分用于记录学习和课堂行为激励，重点是来源清楚。','进入“积分奖励”查看最近积分动态','积分奖励','总积分：累计|最近变化：逐条记录|来源：练习 / 课堂 / 教师评价','你知道为什么积分发生变化。','积分来源应该可追溯。','/v1/tool?page=rewards','你能找到最近一条积分来源。'],
    ['feedbackStudent','学会求助与反馈','看不懂产品、找不到入口或流程不顺时，可直接问产品助手或提反馈。','用产品助手问一个使用问题，或反馈一个不顺的地方','产品助手','问产品：怎么用|提反馈：哪里不好用|上下文：自动带当前页面','你知道以后可以边用边问。','产品说明应该伴随真实使用，而不是只在第一次登录出现。','','你知道如何随时获得使用帮助。']
  ];



  const parentSteps=[
    ['introParent','先认识家长端能做什么','家长端用于了解已授权孩子的课程、作业、学情与课堂表现，不替孩子作答，也不替教师做教学决定。','查看家长使用地图','家长使用全景','课程：现在学什么|作业：是否完成|学情：哪里需要支持|课堂：表现与积分','你已经知道家长端重点是理解和支持。','家长看到的是被授权孩子的数据。','','你能说清家长端与学生端、教师端的区别。'],
    ['childLearning','查看孩子课程','先确认孩子当前班级、教师和课程。','进入“孩子课程”查看当前学习安排','孩子课程','孩子：已授权|班级：当前归属|教师：当前教学负责人','你知道孩子目前在哪个教学环境中。','换班或换老师不会新建一个孩子档案。','/v1/tool?page=childLearning','你能看到当前课程/班级信息。'],
    ['childAssignments','查看孩子作业','查看待完成、已完成和截止时间，用来提醒和支持。','进入“孩子作业”查看近期任务','孩子作业','待完成：需要关注|已完成：可回看|截止：按教师安排','你知道孩子近期有哪些任务。','家长查看状态，不替学生直接完成提交。','/v1/tool?page=childAssignments','你能找到一份近期作业及其状态。'],
    ['childProgress','查看孩子学情','重点看知识点和趋势，而不是只盯一次分数或排名。','进入“孩子学情”查看一个需要支持的知识点','孩子学情','成绩：阶段结果|知识点：正确率|趋势：持续变化|建议：结合教师教学','你知道该关注哪里。','学情用于帮助沟通和支持，不是给孩子贴标签。','/v1/tool?page=childProgress','你能指出一个近期可与孩子或教师沟通的学习点。'],
    ['childRewards','查看课堂表现与积分','课堂参与、教师评价和积分可以帮助理解学习过程。','进入“课堂表现”查看最近记录','课堂表现','参与：课堂事实|积分：变化记录|教师评价：有时间和来源','你知道课堂反馈从哪里看。','课堂表现应看事实和来源，不只看一个总分。','/v1/tool?page=childRewards','你能找到最近一条课堂/积分记录。'],
    ['historyParent','理解连续档案','孩子升年级、换班或换老师后，历史仍应保留在同一学生档案里。','回顾当前页面中的历史或阶段信息','连续档案','旧班级：保留|新班级：继续|学生身份：不变|家长关系：按授权持续','你知道为什么历史不会丢。','连续档案帮助家庭看见长期变化。','','你能解释升年级后为什么不需要创建“新孩子”。'],
    ['account','检查自己的账号与关联','确认自己登录的是正确家长账号，并且关联的是正确孩子。','进入“我的”检查账号与关联关系','我的','账号：家长本人|关联：已授权孩子|安全：密码等设置','你知道账号问题和学习问题分别去哪里处理。','账号安全与孩子学习数据是不同层级。','/v1/tool?page=account','你能确认当前家长账号和孩子关联。'],
    ['feedbackParent','随时提问与反馈','如果某个数据看不懂、入口不好找或希望增加家长能力，可直接使用产品助手。','向产品助手问一个问题或提交一条家长侧建议','家长反馈','问产品：解释页面|提反馈：描述问题|上下文：自动带身份和页面','你知道产品帮助会伴随日常使用。','家长反馈也是产品优化的重要来源。','','你知道如何随时获得帮助。']
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
    if(label.includes('学校管理员'))return 'school_admin';
    if(label.includes('机构管理员'))return 'institution_admin';
    if(label.includes('机构老师'))return 'institution_teacher';
    if(label.includes('管理员'))return 'institution_admin';
    if(label.includes('教师')||label.includes('老师'))return 'institution_teacher';
    if(label.includes('家长'))return 'parent';
    if(label.includes('学生'))return 'student';
    return '';
  };
  const currentPersona=()=>personas.find(p=>p.id===currentPersonaId())||null;
  const seenKey=id=>'cyV1RoleTutorialSeenV5:'+id;
  const SESSION_SHOWN_KEY='cyV1RoleTutorialShownThisLoginV7';
  const authToken=()=>sessionStorage.getItem('v717Token')||localStorage.getItem('v717Token')||sessionStorage.getItem('v6Token')||localStorage.getItem('v6Token')||'';
  const loginMarker=()=>currentPersonaId()+':'+authToken().slice(-24);
  const sessionShownFor=()=>sessionStorage.getItem(SESSION_SHOWN_KEY)||'';
  const markSessionShown=()=>sessionStorage.setItem(SESSION_SHOWN_KEY,loginMarker());
  const clearSessionShown=()=>sessionStorage.removeItem(SESSION_SHOWN_KEY);
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
    window.dispatchEvent(new CustomEvent('cy:collapse-product-assistant'));
    const overlay=document.createElement('div');overlay.id='cy-onboarding-overlay';
    overlay.innerHTML='<section class="cy-onboarding-shell" role="dialog" aria-modal="true"><header class="cy-onboarding-head"><div><strong>长缨新手教学 · 边用边学</strong><small>可以进入真实功能操作；教学本身不自动写业务数据</small></div><button class="btn" id="cy-onboarding-close">退出并保存</button></header><div class="cy-onboarding-body"></div></section>';
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
    body.innerHTML='<section class="cy-lesson-card" style="max-width:760px;margin:0 auto"><span class="tag">'+(firstVisit?'首次登录引导':'继续新手教学')+'</span><h1 style="margin:10px 0 7px">'+persona.icon+' '+esc(persona.name)+'：先知道产品能帮你做什么，再边用边学</h1><p class="subtitle">默认走完整真实使用主线：每一步先解释产品作用和操作路径，再允许你直接进入对应真实页面操作。觉得繁琐可以跳过；退出会保存进度，以后从“新手教学”继续复习。</p><div class="cy-guide-summary"><div><b>'+progress.total+' 个连续步骤</b><small>覆盖当前身份从开始到形成闭环的主要操作</small></div><div><b>'+progress.settled+' 步已处理</b><small>完成与主动跳过都会保存</small></div><div><b>边用边学</b><small>教学不替你写数据；真实页面由你自己决定保存什么</small></div></div><div class="cy-guide-actions"><button class="btn primary" id="cy-current-start">'+(progress.settled?'继续当前进度':'开始完整流程')+'</button><button class="btn" id="cy-current-exit">暂不学习</button></div></section>';
    body.querySelector('#cy-current-start').onclick=()=>startPersona(persona.id);
    body.querySelector('#cy-current-exit').onclick=closeOverlay;
  }

  function startPersona(id,index=null){
    markSeen(id);
    localStorage.setItem(ACTIVE_PERSONA_KEY,id);
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
    const st=personaState(persona.id),step=persona.steps[index],stepId=step[0],pct=Math.round(((index+1)/persona.steps.length)*100),liveRoute=String(step[8]||''),finishSign=String(step[9]||'理解本步用途并知道下一步去哪里。');
    updatePersona(persona.id,s=>({...s,index}));
    localStorage.setItem(ACTIVE_PERSONA_KEY,persona.id);
    const rail=persona.steps.map((x,i)=>{
      const status=personaState(persona.id).status?.[x[0]]||'';
      return '<div class="cy-step-item '+(i===index?'active ':'')+(status||'')+'"><span class="cy-step-no">'+(i+1)+'</span><span><b>'+esc(x[1])+'</b><small class="cy-step-state">'+statusText(status)+'</small></span><span class="cy-step-state">'+(status==='done'?'✓':status==='skipped'?'↷':'')+'</span></div>';
    }).join('');
    const items=String(step[5]).split('|').map(x=>{const parts=x.split('：');return '<div class="cy-demo-card"><b>'+esc(parts.shift())+'</b><small>'+esc(parts.join('：'))+'</small></div>'}).join('');
    const liveActions=(liveRoute?'<button class="btn primary" id="cy-live-action">去真实页面边用边学 →</button>':'')+'<button class="btn" id="cy-step-feedback">这一步不清楚 / 提建议</button>';
    body.innerHTML='<div class="cy-tutorial-layout"><aside class="cy-tutorial-rail"><div><span class="cy-badge">'+persona.icon+' '+esc(persona.name)+'</span><p style="font-size:12px;color:var(--muted);line-height:1.5;margin:8px 2px">'+esc(persona.account)+'</p><p style="font-size:11px;color:var(--muted);line-height:1.5">路线只显示进度。默认按顺序学习；任一步都可以跳过，以后再回来复习。</p></div><div class="cy-step-list">'+rail+'</div></aside><section class="cy-tutorial-stage"><article class="cy-lesson-card"><div class="cy-lesson-top"><div><span class="tag">新手任务 '+(index+1)+'</span><h2>'+esc(step[1])+'</h2><p>'+esc(step[2])+'</p></div><span class="cy-badge">'+(st.status?.[stepId]==='done'?'✓ 已完成':st.status?.[stepId]==='skipped'?'↷ 已跳过':'进行中')+'</span></div><div class="cy-progress-row"><span>第 '+(index+1)+' / '+persona.steps.length+' 步</span><div class="cy-progress-track"><i style="width:'+pct+'%"></i></div><span>'+pct+'%</span></div><div class="cy-mission"><strong>这一关你要做</strong><p>'+esc(step[3])+'</p></div><section class="cy-demo-app"><div class="cy-demo-appbar"><b>'+persona.icon+' '+esc(persona.name)+' · 操作预览</b><span>先理解，再决定是否进入真实功能</span></div><div class="cy-demo-canvas"><div class="cy-demo-screen-title">'+esc(step[4])+'</div><div class="cy-demo-screen-sub">下面先告诉你会看到什么；如果进入真实页面，是否保存真实数据由你自己决定。</div><div class="cy-demo-cards">'+items+'</div><div class="cy-demo-action"><button class="btn primary" id="cy-do-action">先看懂本步操作</button></div><div class="cy-demo-feedback" id="cy-demo-feedback">'+esc(step[6])+'</div></div></section><div class="cy-lesson-notes"><div class="cy-note"><strong>产品在这里帮什么</strong><p>'+esc(step[2])+'</p></div><div class="cy-note"><strong>为什么要这样做</strong><p>'+esc(step[7])+'</p></div><div class="cy-note"><strong>真实使用完成标志</strong><p>'+esc(finishSign)+'</p></div></div><div class="cy-live-box"><strong>边用边学</strong><p>'+(liveRoute?'可以直接跳到对应真实功能操作。离开教学后会出现“继续新手教学”，回来会从本步继续。':'本步主要建立产品概念；看懂后可直接完成，也可以提出反馈。')+'</p><div class="cy-live-actions">'+liveActions+'</div></div><div class="cy-lesson-actions"><button class="btn" id="cy-prev" '+(index===0?'disabled':'')+'>上一步</button><button class="btn" id="cy-skip">暂时跳过</button><button class="btn primary" id="cy-next" disabled>我已理解/完成，继续</button></div><p class="cy-skip-note">跳过不会删除本步；以后可从右上角“新手教学”或真实功能页的“继续新手教学”回来。所有进度只保存在当前浏览器。</p></article></section></div>';
    let actionDone=false;
    const doAction=body.querySelector('#cy-do-action'),feedback=body.querySelector('#cy-demo-feedback'),next=body.querySelector('#cy-next');
    doAction.onclick=()=>{actionDone=true;doAction.disabled=true;doAction.textContent='本步说明已看懂 ✓';feedback.classList.add('show');next.disabled=false};
    if(st.status?.[stepId]==='done'){actionDone=true;doAction.disabled=true;doAction.textContent='本步说明已看懂 ✓';feedback.classList.add('show');next.disabled=false}
    body.querySelector('#cy-prev').onclick=()=>index>0&&renderLesson(persona,index-1);
    body.querySelector('#cy-skip').onclick=()=>{
      updatePersona(persona.id,s=>{s.status[stepId]='skipped';s.index=Math.min(index+1,persona.steps.length-1);return s});
      if(index===persona.steps.length-1)showCompletion(persona);else renderLesson(persona,index+1);
    };
    const live=body.querySelector('#cy-live-action');
    if(live)live.onclick=()=>{
      updatePersona(persona.id,s=>{s.index=index;return s});
      localStorage.setItem(ACTIVE_PERSONA_KEY,persona.id);
      closeOverlay();
      location.href=liveRoute+(liveRoute.includes('?')?'&':'?')+'tutorial=1';
    };
    body.querySelector('#cy-step-feedback').onclick=()=>{
      closeOverlay();
      setTimeout(()=>window.dispatchEvent(new CustomEvent('cy:open-product-feedback',{detail:{step:step[1]}})),0);
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
    body.querySelector('#cy-complete-exit').onclick=()=>{localStorage.removeItem(ACTIVE_PERSONA_KEY);closeOverlay()};
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
    const progress=completion(persona);
    screen.innerHTML='<main id="cy-v1-product-guide-page" data-guide-version="v7"><section class="cy-guide-hero"><span class="tag">'+persona.icon+' '+esc(persona.name)+'</span><h1>当前身份的新手教学：边用边学</h1><p>默认按真实使用顺序带你走完整流程：先讲产品作用，再告诉你具体操作路径，并可直接进入真实功能。某一步暂时不需要就跳过，以后再回来复习。</p><div class="cy-guide-actions"><button class="btn primary" id="cy-guide-start">'+(progress.settled?'继续新手教学':'开始完整流程')+'</button><button class="btn" id="cy-guide-restart">从头开始</button></div><div class="cy-guide-summary"><div><b>'+progress.total+' 步</b><small>当前身份完整主线</small></div><div><b>'+progress.settled+' 步已处理</b><small>完成和主动跳过都会保留</small></div><div><b>随时可回来</b><small>V1 顶部或全部功能页都能继续</small></div></div></section><section class="card" style="margin-top:18px"><h2>教学不是演示视频，而是操作陪练</h2><p style="color:var(--muted);line-height:1.75">你可以先看懂，再直接进入真实页面做自己的班级、学生、组卷和作业；教学不会自动替你保存业务数据。真实操作完再回来继续下一步，遇到不顺可当场提反馈。</p></section></main>';
    screen.querySelector('#cy-guide-start').onclick=()=>startPersona(persona.id);
    screen.querySelector('#cy-guide-restart').onclick=()=>{updatePersona(persona.id,s=>({...s,index:0,status:{}}));startPersona(persona.id,0)};
  }

  function renderPersistentGuideRefresh(){
    const old=screen?.querySelector('#cy-v1-product-guide-page');if(old)old.remove();renderPersistentGuide();
  }

  function sync(){
    const ready=identityReady(),persona=currentPersona();
    if(tutorialButton)tutorialButton.hidden=!ready;
    if(!ready){clearSessionShown();return}
    if(location.pathname==='/v1/guide'){
      markSeen(persona.id);renderPersistentGuide();
      if(new URLSearchParams(location.search).get('resume')==='1'){
        history.replaceState(null,'','/v1/guide');
        queueMicrotask(()=>startPersona(persona.id));
      }
      return
    }
    if(sessionShownFor()!==loginMarker()){
      markSessionShown();
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
    if not getattr(v1_module, "_product_guide_patch_installed", False):
        original = v1_module.v1_html

        def patched_v1_html() -> str:
            return patch_v1_product_guide(original())

        v1_module.v1_html = patched_v1_html
        if GUIDE_PATH not in v1_module.V1_PATHS:
            v1_module.V1_PATHS = (*v1_module.V1_PATHS, GUIDE_PATH)
        v1_module._product_guide_patch_installed = True

    if not getattr(classic_embed_module, "_live_product_guide_resume_installed", False):
        original_unified = classic_embed_module.enhance_unified_classic_html

        def patched_unified_classic_html(html: str) -> str:
            return patch_classic_guide_resume(original_unified(html))

        classic_embed_module.enhance_unified_classic_html = patched_unified_classic_html
        classic_embed_module._live_product_guide_resume_installed = True


__all__ = [
    "CLASSIC_GUIDE_RESUME_MARKER",
    "GUIDE_PATH",
    "V1_PRODUCT_GUIDE_MARKER",
    "patch_classic_guide_resume",
    "install_v1_product_guide_patch",
    "patch_v1_product_guide",
]
