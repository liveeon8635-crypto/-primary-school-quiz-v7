"""Operational V1 enhancement built only on existing read APIs and classic actions.

The V1 shell intentionally started as a thin reviewable surface.  This module
turns the visible teaching cards into real navigation, surfaces existing teacher
reminders, enriches student/guardian continuity, and makes history/transition
pages useful without introducing new production tables or write paths.
"""

from __future__ import annotations

from changying.web import v1 as v1_module

V1_OPERATIONAL_MARKER = "changying_v1_operational_v1"

_OPERATIONAL_SNIPPET = r'''
<style id="changying_v1_operational_v1-style">
  .cy-op-card{margin-top:16px}.cy-op-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px}.cy-op-stat{padding:13px;border:1px solid #e4e9f2;border-radius:14px;background:#fff}.cy-op-stat b{display:block;font-size:23px}.cy-op-stat span{font-size:12px;color:#667085}.cy-op-list{display:grid;gap:8px;margin-top:12px}.cy-op-row{display:flex;justify-content:space-between;gap:10px;padding:11px 12px;border:1px solid #e4e9f2;border-radius:12px;background:#f8faff}.cy-op-row small{color:#667085}.cy-op-route{font-size:11px;color:#2563eb;font-weight:800;margin-top:9px}.cy-op-fact{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.cy-op-fact>div{padding:12px;border-radius:12px;background:#f8faff;border:1px solid #e8edf6}.cy-op-fact b{display:block;margin-bottom:4px}.cy-op-muted{color:#667085;font-size:12px;line-height:1.55}
  @media(max-width:720px){.cy-op-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.cy-op-fact{grid-template-columns:1fr}.cy-op-row{align-items:flex-start;flex-direction:column}}
</style>
<script id="changying_v1_operational_v1-script">
(()=>{
  if(window.__cyV1OperationalInstalled)return;window.__cyV1OperationalInstalled=true;
  const token=()=>localStorage.getItem('v717Token')||localStorage.getItem('v6Token')||'';
  const esc=v=>String(v??'').replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  async function readJson(url){const t=token();if(!t||t==='demo')throw new Error('no-real-session');const r=await fetch(url,{headers:{Authorization:'Bearer '+t}});if(!r.ok)throw new Error('read-failed-'+r.status);return await r.json()}
  function classic(page){location.href='/classic?legacy=1&page='+encodeURIComponent(page)}
  function v1(path){history.pushState({},'',path);window.dispatchEvent(new PopStateEvent('popstate'))}
  const routes={
    '当前学生':()=>v1('/v1/student'),'学生':()=>v1('/v1/student'),'学习进度':()=>v1('/v1/student'),'教学进度':()=>v1('/v1/student'),
    '晚托':()=>classic('classes'),'周末课':()=>classic('classes'),'寒假班':()=>classic('classes'),'暑假班':()=>classic('classes'),'当前班级':()=>classic('classes'),'我的班级':()=>classic('classes'),'今日课程':()=>classic('classes'),'今日/本周教学':()=>classic('teacher'),'今日课表':()=>classic('teacher'),
    '作业与错题':()=>classic('papers'),'作业/练习':()=>classic('papers'),'作业':()=>classic('papers'),'备课':()=>classic('papers'),'批改/订正':()=>classic('papers'),'测验':()=>classic('papers'),
    '待办事项':()=>classic('teacher'),'待办':()=>classic('teacher'),'教学评价':()=>classic('analytics')
  };
  document.addEventListener('click',e=>{const b=e.target.closest('[data-feature]');if(!b)return;const fn=routes[(b.dataset.feature||'').trim()];if(!fn)return;e.preventDefault();e.stopImmediatePropagation();fn()},true);
  function visibleScreen(){return document.getElementById('screen')}
  function insertAfterNotice(html,id){const s=visibleScreen();if(!s||document.getElementById(id))return false;const notices=s.querySelectorAll('.notice');const anchor=notices.length?notices[notices.length-1]:s.querySelector('.page-head');if(!anchor)return false;anchor.insertAdjacentHTML('afterend',html);return true}
  async function enhanceWorkspace(){if(location.pathname!='/v1/workspace'||document.getElementById('cy-op-workbench'))return;const buttons=[...document.querySelectorAll('[data-feature]')];buttons.forEach(b=>{if(routes[(b.dataset.feature||'').trim()]&&!b.querySelector('.cy-op-route'))b.insertAdjacentHTML('beforeend','<div class="cy-op-route">点击进入可用功能 →</div>')});try{const data=await readJson('/teacher/workbench-summary'),s=data.summary||{},rows=(data.classes||[]).slice(0,6);insertAfterNotice(`<section class="card cy-op-card" id="cy-op-workbench"><div class="section-head"><div><h2>今日待办与主动提醒</h2><p>直接读取现有教师工作台，不生成虚构数据。</p></div><button class="btn" id="cy-op-open-teacher">打开完整工作台</button></div><div class="cy-op-grid"><div class="cy-op-stat"><b>${esc(s.overdue||0)}</b><span>已逾期</span></div><div class="cy-op-stat"><b>${esc((s.dueToday||0)+(s.dueSoon||0))}</b><span>即将到期</span></div><div class="cy-op-stat"><b>${esc(s.callbacks||0)}</b><span>待回访</span></div><div class="cy-op-stat"><b>${esc(s.openTodos||0)}</b><span>班级待办</span></div></div><div class="cy-op-list">${rows.map(x=>`<div class="cy-op-row"><span><b>${esc(x.class?.name||'班级')}</b><small>提醒 ${esc(x.summary?.reminders||0)} · 逾期 ${esc(x.summary?.overdue||0)} · 待回访 ${esc(x.summary?.callbacks||0)}</small></span><small>待办 ${esc(x.summary?.openTodos||0)}</small></div>`).join('')||'<div class="empty">当前没有班级提醒</div>'}</div></section>`,'cy-op-workbench');const open=document.getElementById('cy-op-open-teacher');if(open)open.onclick=()=>classic('teacher')}catch{}
  }
  async function enhanceStudent(){if(!location.pathname.includes('/v1/student')||document.getElementById('cy-op-guardians'))return;const id=Number(new URLSearchParams(location.search).get('id')||0);if(!id)return;try{const p=await readJson('/teacher/students/'+id+'/growth-profile'),s=p.student||{},parents=s.parents||[],history=p.classHistory||[];const head=document.querySelector('.student-head');if(!head)return;head.insertAdjacentHTML('afterend',`<section class="section card" id="cy-op-guardians"><div class="section-head"><div><h2>家长关联与教学连续性</h2><p>沿用同一 student_id 查看监护人与班级历史。</p></div></div><div class="cy-op-fact"><div><b>监护人</b><span>${parents.length?parents.map(x=>esc(x.name||x.username||'家长')).join(' / '):'暂无已关联监护人'}</span></div><div><b>历史教学归属</b><span>${history.length} 条记录</span></div></div>${parents.length?`<div class="cy-op-list">${parents.map(x=>`<div class="cy-op-row"><span><b>${esc(x.name||'家长')}</b><small>${esc(x.username||'已关联账号')}</small></span><small>已关联</small></div>`).join('')}</div>`:''}</section>`)}catch{}
  }
  async function enhanceHistory(){if(location.pathname!='/v1/history'||document.getElementById('cy-op-history'))return;const links=[...document.querySelectorAll('a[data-student]')].slice(0,10);if(!links.length)return;const records=[];for(const a of links){const id=Number(new URL(a.href,location.origin).searchParams.get('id')||0);if(!id)continue;try{const p=await readJson('/teacher/students/'+id+'/growth-profile'),h=p.classHistory||[],t=p.timeline||[],s=p.student||{};records.push({id,name:s.name||a.querySelector('b')?.textContent||'学生',history:h,last:h[0]||null,timeline:t})}catch{}}
    if(!records.length)return;const content=`<section class="section card" id="cy-op-history"><div class="section-head"><div><h2>真实历史摘要</h2><p>从现有班级历史与学生时间线读取，不再使用固定演示学年。</p></div></div><div class="cy-op-list">${records.map(r=>`<a class="cy-op-row" href="/v1/student?id=${r.id}"><span><b>${esc(r.name)}</b><small>${r.history.length} 条班级历史 · ${r.timeline.length} 条时间线</small></span><small>${esc(r.last?.className||r.last?.name||'打开连续档案')}</small></a>`).join('')}</div></section>`;const s=visibleScreen();if(s)s.insertAdjacentHTML('beforeend',content)
  }
  function transitionName(grade){grade=Number(grade||0);if(grade<=0)return'待教师确认';if(grade<=2)return'低段到中段';if(grade<=4)return'中段到高段';if(grade===5)return'五升六';return'小升初'}
  async function enhanceTransition(){if(location.pathname!='/v1/transition'||document.getElementById('cy-op-transition'))return;const id=Number(new URLSearchParams(location.search).get('id')||0);if(!id)return;try{const p=await readJson('/teacher/students/'+id+'/growth-profile'),s=p.student||{},a=p.academic||{},weak=a.weakKnowledge||[],history=p.classHistory||[],suggestions=p.suggestions||[],name=transitionName(s.grade);insertAfterNotice(`<section class="card cy-op-card" id="cy-op-transition"><div class="section-head"><div><h2>当前档案事实</h2><p>衔接判断只使用现有学生事实，不自动修改年级或班级。</p></div><span class="tag">建议衔接：${esc(name)}</span></div><div class="cy-op-fact"><div><b>学生</b><span>${esc(s.name||'学生')} · 档案 #${esc(s.id||id)}</span></div><div><b>当前年级</b><span>${s.grade?esc(s.grade)+'年级':'待完善'}</span></div><div><b>班级历史</b><span>${history.length} 条</span></div><div><b>阶段成绩</b><span>${a.avgScore??'暂无记录'}</span></div><div><b>前置知识关注</b><span>${weak.length?weak.slice(0,3).map(x=>esc(x.knowledge||'知识点')).join(' / '):'暂无明确薄弱项'}</span></div><div><b>下一步教学</b><span>${suggestions.length?esc(suggestions[0]):'继续积累课堂与作业事实'}</span></div></div><p class="cy-op-muted" style="margin-top:12px">V1 当前提供“读取事实 → 教师判断 → 衔接准备”的可用只读流程；真正改变年级、学校或教学归属仍沿用受权限保护的原系统操作，避免误改学生长期档案。</p></section>`,'cy-op-transition')}catch{}
  }
  let timer=null;async function enhance(){clearTimeout(timer);timer=setTimeout(async()=>{await enhanceWorkspace();await enhanceStudent();await enhanceHistory();await enhanceTransition()},60)}
  new MutationObserver(enhance).observe(document.getElementById('screen')||document.body,{childList:true,subtree:true});window.addEventListener('popstate',enhance);enhance();
})();
</script>
'''


def patch_v1_operational_html(html: str) -> str:
    """Add operational, read-mostly V1 behavior once."""
    if V1_OPERATIONAL_MARKER in html:
        return html
    if "</body>" not in html:
        raise RuntimeError("V1 operational patch: closing body marker not found")
    html = html.replace("2025—2026（演示）", "按现有档案时间线读取", 1)
    return html.replace("</body>", _OPERATIONAL_SNIPPET + "\n</body>", 1)


def install_v1_operational_patch() -> None:
    """Wrap the current V1 renderer without altering auth or database behavior."""
    if getattr(v1_module, "_operational_patch_installed", False):
        return
    original = v1_module.v1_html

    def patched_v1_html() -> str:
        return patch_v1_operational_html(original())

    v1_module.v1_html = patched_v1_html
    v1_module._operational_patch_installed = True


__all__ = ["V1_OPERATIONAL_MARKER", "install_v1_operational_patch", "patch_v1_operational_html"]
