"""Expose retained Classic teaching capabilities from the V1 workspace.

This is the fast compatibility stage of V1 unification: no existing teaching
feature is deleted or reimplemented.  Role-scoped cards deep-link into the exact
Classic page that already owns the mature workflow, while keeping the same
account, database and permission model.  Native V1 replacements can then be
migrated incrementally without hiding proven functionality from daily use.
"""

from __future__ import annotations

from changying.web import v1 as v1_module

V1_LEGACY_CAPABILITIES_MARKER = "changying_v1_legacy_capabilities_v1"

_LEGACY_CAPABILITIES_SNIPPET = r'''
<style id="changying_v1_legacy_capabilities_v1-style">
  .cy-cap-card{margin-top:22px}.cy-cap-head{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;margin-bottom:12px}
  .cy-cap-head h2{margin:0;font-size:18px}.cy-cap-head p{margin:4px 0 0;color:#667085;font-size:13px;line-height:1.55}.cy-cap-badge{white-space:nowrap;font-size:11px;font-weight:800;color:#285078;background:#eef6ff;border:1px solid #d4e7ff;border-radius:999px;padding:7px 9px}
  .cy-cap-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px}.cy-cap-link{display:flex;flex-direction:column;gap:5px;min-height:94px;padding:13px;border:1px solid #e4e9f2;border-radius:14px;background:#fff;color:#172033;text-decoration:none}.cy-cap-link:hover{border-color:#a9bde1;box-shadow:0 8px 24px rgba(23,60,120,.08)}.cy-cap-link b{font-size:14px}.cy-cap-link small{color:#667085;line-height:1.45}.cy-cap-link span{margin-top:auto;color:#2563eb;font-size:11px;font-weight:800}
  .cy-cap-note{margin-top:10px;padding:11px 12px;border-radius:12px;background:#f8fafc;border:1px solid #e7ebf2;color:#667085;font-size:12px;line-height:1.6}
  @media(max-width:980px){.cy-cap-grid{grid-template-columns:repeat(3,minmax(0,1fr))}}
  @media(max-width:720px){.cy-cap-head{flex-direction:column}.cy-cap-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.cy-cap-link{min-height:88px;padding:12px}}
</style>
<script id="changying_v1_legacy_capabilities_v1-script">
(()=>{
  if(window.__cyV1LegacyCapabilitiesInstalled)return;window.__cyV1LegacyCapabilitiesInstalled=true;
  const token=()=>localStorage.getItem('v717Token')||sessionStorage.getItem('v717Token')||localStorage.getItem('v6Token')||sessionStorage.getItem('v6Token')||'';
  const esc=v=>String(v??'').replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  const capabilities={
    teacher:[
      ['classes','班级学生','建班、学生账号、家长关联、调班与毕业归档'],
      ['classPoints','课堂积分','课堂表现、积分规则、小组、成长看板与奖励'],
      ['ai','AI 助手','AI 出题、教案、批改辅助与个性化巩固'],
      ['teaching','定制教学','教学方案、课时内容与分层教学'],
      ['resources','教材教案','教材、教案、课件与练习资料库'],
      ['catalog','教材题库','题库维护、知识点与题目管理'],
      ['papers','组卷作业','组卷、布置作业、检查提交与成绩导出'],
      ['analytics','学情分析','班级完成率、成绩、薄弱知识与学生提醒'],
      ['audit','操作记录','查看本人教学操作审计记录'],
      ['leaderboard','排行榜','课堂积分与班级表现排行'],
      ['account','我的','账号、安全、通知与个人数据功能']
    ],
    student:[
      ['syncLearning','同步课堂','查看教师发布的同步课堂内容'],
      ['rewards','积分奖励','查看课堂积分、奖励与兑换记录'],
      ['assignments','我的作业','在线答题、照片/视频作业与提交状态'],
      ['wrongbook','我的错题','查看错题与巩固进度'],
      ['practice','自主练习','按年级、学科与知识点练习'],
      ['progress','我的学情','查看成绩、知识点与学习变化'],
      ['leaderboard','班级排行','查看允许展示的班级排行'],
      ['account','我的','账号、安全、通知与个人数据功能']
    ],
    parent:[
      ['childLearning','孩子课程','查看孩子当前课程与同步课堂'],
      ['childRewards','课堂表现','查看孩子课堂积分、奖励与表现变化'],
      ['childProgress','孩子学情','查看成绩、知识点与成长趋势'],
      ['childAssignments','孩子作业','查看作业、完成情况与逾期状态'],
      ['account','我的','账号、安全、通知与个人数据功能']
    ],
    admin:[
      ['admin','平台总览','学校教学与账号数据概览'],
      ['subscription','套餐授权','查看当前学校功能授权与容量'],
      ['users','账号管理','教师、学生、家长账号与学生恢复'],
      ['pointsAdmin','积分奖励','全校积分规则、奖励与自动奖励'],
      ['ai','AI 设置','学校级 AI 配置、安全边界与教学助手'],
      ['teaching','定制教学','教学方案、课时与分层教学'],
      ['resources','教材教案','学校资料库与官方教材导航'],
      ['imports','批量导入','批量导入账号、题目与教学数据'],
      ['catalog','教材题库','教材、知识点与题库管理'],
      ['adminAudit','全校审计','查看全校关键教学与账号操作记录'],
      ['system','系统设置','学校级系统维护与安全设置']
    ]
  };
  async function role(){
    const t=token();if(!t||t==='demo')return 'teacher';
    try{const r=await fetch('/session',{headers:{Authorization:'Bearer '+t},cache:'no-store'});if(!r.ok)return '';const s=await r.json();return String(s.role||'')}catch{return ''}
  }
  function href(page){return '/classic?legacy=1&page='+encodeURIComponent(page)+'&from=v1'}
  async function mount(){
    if(location.pathname!='/v1/workspace'||document.getElementById('cy-capabilities'))return;
    const screen=document.getElementById('screen');if(!screen)return;
    const r=await role();const items=capabilities[r]||[];if(!items.length)return;
    const section=document.createElement('section');section.id='cy-capabilities';section.className='section card cy-cap-card';
    section.innerHTML=`<div class="cy-cap-head"><div><h2>完整功能中心</h2><p>旧版已经成熟的教学功能全部保留，并从这里按当前身份直接进入；使用同一账号、同一数据库和原有权限。</p></div><span class="cy-cap-badge">同一数据 · 不丢功能</span></div><div class="cy-cap-grid">${items.map(x=>`<a class="cy-cap-link" data-cy-capability="${esc(x[0])}" href="${href(x[0])}"><b>${esc(x[1])}</b><small>${esc(x[2])}</small><span>打开完整功能 →</span></a>`).join('')}</div><div class="cy-cap-note">统一分两步进行：先保证原有可用能力一个不漏地接回统一入口；随后按实际使用频率逐项改造成 V1 原生界面。当前入口不会复制数据，也不会创建第二套业务系统。</div>`;
    const currentStudents=[...screen.querySelectorAll('.section')].find(x=>x.querySelector('.section-head h2')?.textContent.trim()==='当前学生');
    if(currentStudents)currentStudents.insertAdjacentElement('beforebegin',section);else screen.querySelector('main')?.appendChild(section);
  }
  let timer=null;const run=()=>{clearTimeout(timer);timer=setTimeout(mount,80)};
  new MutationObserver(run).observe(document.getElementById('screen')||document.body,{childList:true,subtree:true});
  window.addEventListener('popstate',run);run();
})();
</script>
'''


def patch_v1_legacy_capabilities(html: str) -> str:
    """Add role-scoped access to retained Classic capabilities."""
    if V1_LEGACY_CAPABILITIES_MARKER in html:
        return html
    if "</body>" not in html:
        raise RuntimeError("V1 legacy capabilities patch: closing body marker not found")
    return html.replace("</body>", _LEGACY_CAPABILITIES_SNIPPET + "\n</body>", 1)


def install_v1_legacy_capabilities_patch() -> None:
    if getattr(v1_module, "_legacy_capabilities_patch_installed", False):
        return
    original = v1_module.v1_html

    def patched_v1_html() -> str:
        return patch_v1_legacy_capabilities(original())

    v1_module.v1_html = patched_v1_html
    v1_module._legacy_capabilities_patch_installed = True


__all__ = [
    "V1_LEGACY_CAPABILITIES_MARKER",
    "install_v1_legacy_capabilities_patch",
    "patch_v1_legacy_capabilities",
]
