"""Operational V1 enhancement built on existing authenticated read APIs.

V1 must stay inside the V1 shell for day-to-day teaching work.  The legacy
system remains available only through the explicit ``原系统`` entry.  This
module therefore turns teaching cards into native V1 panels, reuses the V1
Bearer token, adds short-lived read caches, and avoids the expensive legacy
page reload/login round-trip.
"""

from __future__ import annotations

from changying.web import v1 as v1_module

V1_OPERATIONAL_MARKER = "changying_v1_operational_v2"

_OPERATIONAL_SNIPPET = r'''
<style id="changying_v1_operational_v2-style">
  .cy-op-card{margin-top:16px}.cy-op-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px}.cy-op-stat{padding:13px;border:1px solid #e4e9f2;border-radius:14px;background:#fff}.cy-op-stat b{display:block;font-size:23px}.cy-op-stat span{font-size:12px;color:#667085}.cy-op-list{display:grid;gap:8px;margin-top:12px}.cy-op-row{display:flex;justify-content:space-between;gap:10px;padding:11px 12px;border:1px solid #e4e9f2;border-radius:12px;background:#f8faff}.cy-op-row small{color:#667085}.cy-op-route{font-size:11px;color:#c0262d;font-weight:800;margin-top:9px}.cy-op-fact{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.cy-op-fact>div{padding:12px;border-radius:12px;background:#f8faff;border:1px solid #e8edf6}.cy-op-fact b{display:block;margin-bottom:4px}.cy-op-muted{color:#667085;font-size:12px;line-height:1.55}
  .cy-feature-layer{position:fixed;inset:0;z-index:90;background:rgba(15,23,42,.34);display:flex;align-items:flex-end;justify-content:center;padding:18px}.cy-feature-sheet{width:min(760px,100%);max-height:min(86dvh,860px);overflow:auto;background:#f7f9fc;border:1px solid #e4e9f2;border-radius:24px 24px 18px 18px;box-shadow:0 30px 90px rgba(15,23,42,.28);padding:18px}.cy-feature-head{position:sticky;top:-18px;z-index:2;display:flex;align-items:center;justify-content:space-between;gap:12px;background:rgba(247,249,252,.96);backdrop-filter:blur(10px);padding:18px 0 12px}.cy-feature-head h2{margin:0}.cy-feature-close{border:1px solid #d8e0ec;background:#fff;border-radius:12px;padding:9px 12px;font-weight:800}.cy-feature-loading{padding:28px;text-align:center;color:#667085}.cy-feature-error{padding:14px;border-radius:12px;background:#fff1f1;color:#991b1b;border:1px solid #fecaca}.cy-feature-note{padding:11px 12px;border-radius:12px;background:#eef6ff;border:1px solid #d4e7ff;color:#285078;font-size:12px;line-height:1.55}.cy-feature-student{cursor:pointer;color:#172033;text-decoration:none}
  @media(max-width:720px){.cy-op-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.cy-op-fact{grid-template-columns:1fr}.cy-op-row{align-items:flex-start;flex-direction:column}.cy-feature-layer{padding:0;align-items:flex-end}.cy-feature-sheet{max-height:90dvh;border-radius:24px 24px 0 0;padding:16px 14px calc(28px + env(safe-area-inset-bottom))}.cy-feature-head{top:-16px;padding-top:16px}}
</style>
<script id="changying_v1_operational_v2-script">
(()=>{
  if(window.__cyV1OperationalV2Installed)return;window.__cyV1OperationalV2Installed=true;
  const token=()=>{const remember=localStorage.getItem('v717Remember')==='1';return (remember?localStorage.getItem('v717Token'):sessionStorage.getItem('v717Token'))||sessionStorage.getItem('v717Token')||localStorage.getItem('v717Token')||sessionStorage.getItem('v6Token')||localStorage.getItem('v6Token')||''};
  const esc=v=>String(v??'').replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  const cache=new Map();
  async function readJson(url,ttl=30000){
    const t=token();if(!t||t==='demo')throw new Error('当前为演示会话');
    const now=Date.now(),hit=cache.get(url);if(hit&&now-hit.at<ttl)return hit.value;
    const r=await fetch(url,{headers:{Authorization:'Bearer '+t},cache:'no-store'});if(!r.ok)throw new Error('读取失败 '+r.status);
    const value=await r.json();cache.set(url,{at:now,value});return value;
  }
  function v1(path){history.pushState({},'',path);window.dispatchEvent(new PopStateEvent('popstate'))}
  function visibleScreen(){return document.getElementById('screen')}
  function insertAfterNotice(html,id){const s=visibleScreen();if(!s||document.getElementById(id))return false;const notices=s.querySelectorAll('.notice');const anchor=notices.length?notices[notices.length-1]:s.querySelector('.page-head');if(!anchor)return false;anchor.insertAdjacentHTML('afterend',html);return true}
  function closeFeature(){document.getElementById('cy-feature-layer')?.remove();document.body.style.overflow=''}
  function openShell(title){closeFeature();const layer=document.createElement('div');layer.id='cy-feature-layer';layer.className='cy-feature-layer';layer.innerHTML=`<section class="cy-feature-sheet" role="dialog" aria-modal="true" aria-label="${esc(title)}"><div class="cy-feature-head"><div><h2>${esc(title)}</h2><div class="cy-op-muted">保持 V1 登录态，不再跳转旧系统。</div></div><button class="cy-feature-close" type="button">关闭</button></div><div id="cy-feature-body" class="cy-feature-loading">正在读取现有教学数据…</div></section>`;document.body.appendChild(layer);document.body.style.overflow='hidden';layer.querySelector('.cy-feature-close').onclick=closeFeature;layer.onclick=e=>{if(e.target===layer)closeFeature()};return layer.querySelector('#cy-feature-body')}
  function setFeature(html){const b=document.getElementById('cy-feature-body');if(b){b.className='';b.innerHTML=html}}
  function featureError(err){setFeature(`<div class="cy-feature-error">${esc(err?.message||'暂时无法读取此功能')}</div><p class="cy-op-muted" style="margin-top:10px">不会要求重新登录旧系统。可以关闭后继续使用 V1。</p>`)}
  async function classesAndStudents(filter=''){
    const classes=await readJson('/teacher/classes');const needle=filter.trim();const selected=(needle?classes.filter(c=>String(c.name||'').includes(needle)):classes).slice(0,12);const use=selected.length?selected:classes.slice(0,12);
    const rows=await Promise.all(use.map(async c=>{let students=[];try{students=await readJson('/teacher/classes/'+c.id+'/students')}catch{}return {class:c,students}}));return rows;
  }
  async function visibleStudents(){
    const rows=await classesAndStudents('');const map=new Map();for(const item of rows){for(const s of item.students||[]){if(!map.has(s.id))map.set(s.id,{...s,className:item.class?.name||''})}}return [...map.values()];
  }
  async function studentProfiles(limit=10){const students=(await visibleStudents()).slice(0,limit);return await Promise.all(students.map(async s=>{try{return {student:s,profile:await readJson('/teacher/students/'+s.id+'/growth-profile')}}catch{return {student:s,profile:null}}}))}
  function studentLink(s,detail='查看连续档案'){return `<a class="cy-op-row cy-feature-student" href="/v1/student?id=${encodeURIComponent(s.id)}" data-cy-v1-student><span><b>${esc(s.name||'学生')}</b><small>${esc(detail)}</small></span><small>打开档案 →</small></a>`}
  function bindFeatureStudentLinks(){document.querySelectorAll('[data-cy-v1-student]').forEach(a=>a.onclick=e=>{e.preventDefault();const href=a.getAttribute('href');closeFeature();v1(href)})}
  async function showClasses(title,filter=''){
    openShell(title);try{const rows=await classesAndStudents(filter);setFeature(`<div class="cy-feature-note">显示当前账号可见的真实班级与学生关系。${filter?'若没有名称匹配，会回退显示全部可见班级。':''}</div><div class="cy-op-list">${rows.map(x=>`<div class="card"><h3>${esc(x.class?.name||'班级')}</h3><p class="cy-op-muted">学生 ${x.students.length} 人</p><div class="cy-op-list">${x.students.slice(0,8).map(s=>studentLink(s,'当前教学归属：'+(x.class?.name||''))).join('')||'<div class="empty">暂无可见学生</div>'}</div></div>`).join('')||'<div class="empty">当前没有可见班级</div>'}</div>`);bindFeatureStudentLinks()}catch(err){featureError(err)}
  }
  async function showWorkbench(title='今日 / 本周教学'){
    openShell(title);try{const data=await readJson('/teacher/workbench-summary'),s=data.summary||{},rows=data.classes||[];setFeature(`<div class="cy-op-grid"><div class="cy-op-stat"><b>${esc(s.overdue||0)}</b><span>已逾期</span></div><div class="cy-op-stat"><b>${esc((s.dueToday||0)+(s.dueSoon||0))}</b><span>即将到期</span></div><div class="cy-op-stat"><b>${esc(s.callbacks||0)}</b><span>待回访</span></div><div class="cy-op-stat"><b>${esc(s.openTodos||0)}</b><span>班级待办</span></div></div><div class="cy-op-list">${rows.slice(0,12).map(x=>`<div class="cy-op-row"><span><b>${esc(x.class?.name||'班级')}</b><small>提醒 ${esc(x.summary?.reminders||0)} · 逾期 ${esc(x.summary?.overdue||0)} · 待回访 ${esc(x.summary?.callbacks||0)}</small></span><small>待办 ${esc(x.summary?.openTodos||0)}</small></div>`).join('')||'<div class="empty">当前没有班级提醒</div>'}</div>`)}catch(err){featureError(err)}
  }
  async function showStudentOverview(title,mode='progress'){
    openShell(title);try{const rows=await studentProfiles(10);const html=rows.map(({student,profile})=>{if(!profile)return studentLink(student,'档案暂未读取');const a=profile.academic||{},weak=a.weakKnowledge||[],pending=a.pendingAssignments??0,overdue=a.overdueAssignments??0;const detail=mode==='work'?`待完成 ${pending} · 逾期 ${overdue} · 薄弱项 ${weak.length}`:`阶段成绩 ${a.avgScore??'—'} · 薄弱项 ${weak.length}`;return studentLink(profile.student||student,detail)}).join('');setFeature(`<div class="cy-feature-note">${mode==='work'?'作业与错题从每位学生现有连续档案汇总。':'学习进度从现有成绩、作业和薄弱知识记录汇总。'} 不新增第二套学生数据。</div><div class="cy-op-list">${html||'<div class="empty">暂无可见学生</div>'}</div>`);bindFeatureStudentLinks()}catch(err){featureError(err)}
  }
  async function showFeature(name){
    const f=(name||'').trim();
    if(['当前学生','学生'].includes(f)){v1('/v1/student');return}
    if(['学习进度','教学进度','教学评价'].includes(f)){await showStudentOverview(f,'progress');return}
    if(['作业与错题','作业/练习','作业','备课','批改/订正','测验'].includes(f)){await showStudentOverview(f,'work');return}
    if(['待办事项','待办','今日/本周教学','今日课表'].includes(f)){await showWorkbench(f);return}
    const filterMap={'晚托':'晚托','周末课':'周末','寒假班':'寒假','暑假班':'暑假','当前班级':'','我的班级':'','今日课程':''};
    if(Object.prototype.hasOwnProperty.call(filterMap,f)){await showClasses(f,filterMap[f]);return}
    await showWorkbench(f||'教学工作台');
  }
  document.addEventListener('click',e=>{const b=e.target.closest('[data-feature]');if(!b)return;const name=(b.dataset.feature||'').trim();e.preventDefault();e.stopImmediatePropagation();if(name==='课堂复盘'){if(typeof navigate==='function')navigate('/v1/classroom-review');else location.href='/v1/classroom-review';return}showFeature(name)},true);
  async function enhanceWorkspace(){if(location.pathname!='/v1/workspace'||document.getElementById('cy-op-workbench'))return;try{const data=await readJson('/teacher/workbench-summary'),s=data.summary||{},rows=(data.classes||[]).slice(0,6);const main=visibleScreen()?.querySelector('main');if(!main||location.pathname!=='/v1/workspace'||document.getElementById('cy-op-workbench'))return;main.insertAdjacentHTML('beforeend',`<section class="section card cy-op-card" id="cy-op-workbench"><div class="section-head"><div><h2>今日待办与主动提醒</h2><p>直接读取现有教师工作台，不生成虚构数据。</p></div><button class="btn" id="cy-op-open-teacher">查看待办详情</button></div><div class="cy-op-grid"><div class="cy-op-stat"><b>${esc(s.overdue||0)}</b><span>已逾期</span></div><div class="cy-op-stat"><b>${esc((s.dueToday||0)+(s.dueSoon||0))}</b><span>即将到期</span></div><div class="cy-op-stat"><b>${esc(s.callbacks||0)}</b><span>待回访</span></div><div class="cy-op-stat"><b>${esc(s.openTodos||0)}</b><span>班级待办</span></div></div><div class="cy-op-list">${rows.map(x=>`<div class="cy-op-row"><span><b>${esc(x.class?.name||'班级')}</b><small>提醒 ${esc(x.summary?.reminders||0)} · 逾期 ${esc(x.summary?.overdue||0)} · 待回访 ${esc(x.summary?.callbacks||0)}</small></span><small>待办 ${esc(x.summary?.openTodos||0)}</small></div>`).join('')||'<div class="empty">当前没有班级提醒</div>'}</div></section>`);const open=document.getElementById('cy-op-open-teacher');if(open)open.onclick=()=>showWorkbench('待办事项')}catch{}
  }
  async function enhanceStudent(){if(!location.pathname.includes('/v1/student')||document.getElementById('cy-op-guardians'))return;const id=Number(new URLSearchParams(location.search).get('id')||0);if(!id)return;try{const p=await readJson('/teacher/students/'+id+'/growth-profile'),s=p.student||{},parents=s.parents||[],history=p.classHistory||[];const head=document.querySelector('.student-head');if(!head)return;head.insertAdjacentHTML('afterend',`<section class="section card" id="cy-op-guardians"><div class="section-head"><div><h2>家长关联与教学连续性</h2><p>沿用同一 student_id 查看监护人与班级历史。</p></div></div><div class="cy-op-fact"><div><b>监护人</b><span>${parents.length?parents.map(x=>esc(x.name||x.username||'家长')).join(' / '):'暂无已关联监护人'}</span></div><div><b>历史教学归属</b><span>${history.length} 条记录</span></div></div></section>`)}catch{}
  }
  async function enhanceHistory(){if(location.pathname!='/v1/history'||document.getElementById('cy-op-history'))return;const links=[...document.querySelectorAll('a[data-student]')].slice(0,10);if(!links.length)return;const jobs=links.map(async a=>{const id=Number(new URL(a.href,location.origin).searchParams.get('id')||0);if(!id)return null;try{const p=await readJson('/teacher/students/'+id+'/growth-profile'),h=p.classHistory||[],t=p.timeline||[],s=p.student||{};return{id,name:s.name||a.querySelector('b')?.textContent||'学生',history:h,last:h[0]||null,timeline:t}}catch{return null}});const records=(await Promise.all(jobs)).filter(Boolean);if(!records.length)return;const content=`<section class="section card" id="cy-op-history"><div class="section-head"><div><h2>真实历史摘要</h2><p>从现有班级历史与学生时间线并行读取，减少移动端等待。</p></div></div><div class="cy-op-list">${records.map(r=>`<a class="cy-op-row" href="/v1/student?id=${r.id}"><span><b>${esc(r.name)}</b><small>${r.history.length} 条班级历史 · ${r.timeline.length} 条时间线</small></span><small>${esc(r.last?.className||r.last?.name||'打开连续档案')}</small></a>`).join('')}</div></section>`;visibleScreen()?.insertAdjacentHTML('beforeend',content)
  }
  function transitionName(grade){grade=Number(grade||0);if(grade<=0)return'待教师确认';if(grade<=2)return'低段到中段';if(grade<=4)return'中段到高段';if(grade===5)return'五升六';return'小升初'}
  async function enhanceTransition(){if(location.pathname!='/v1/transition'||document.getElementById('cy-op-transition'))return;const id=Number(new URLSearchParams(location.search).get('id')||0);if(!id)return;try{const p=await readJson('/teacher/students/'+id+'/growth-profile'),s=p.student||{},a=p.academic||{},weak=a.weakKnowledge||[],history=p.classHistory||[],suggestions=p.suggestions||[],name=transitionName(s.grade);insertAfterNotice(`<section class="card cy-op-card" id="cy-op-transition"><div class="section-head"><div><h2>当前档案事实</h2><p>衔接判断只使用现有学生事实，不自动修改年级或班级。</p></div><span class="tag">建议衔接：${esc(name)}</span></div><div class="cy-op-fact"><div><b>学生</b><span>${esc(s.name||'学生')} · 档案 #${esc(s.id||id)}</span></div><div><b>当前年级</b><span>${s.grade?esc(s.grade)+'年级':'待完善'}</span></div><div><b>班级历史</b><span>${history.length} 条</span></div><div><b>阶段成绩</b><span>${a.avgScore??'暂无记录'}</span></div><div><b>前置知识关注</b><span>${weak.length?weak.slice(0,3).map(x=>esc(x.knowledge||'知识点')).join(' / '):'暂无明确薄弱项'}</span></div><div><b>下一步教学</b><span>${suggestions.length?esc(suggestions[0]):'继续积累课堂与作业事实'}</span></div></div><p class="cy-op-muted" style="margin-top:12px">V1 当前提供“读取事实 → 教师判断 → 衔接准备”的可用只读流程；真正改变年级、学校或教学归属仍通过受权限保护的维护流程完成。</p></section>`,'cy-op-transition')}catch{}
  }
  let timer=null;async function enhance(){clearTimeout(timer);timer=setTimeout(async()=>{await enhanceWorkspace();await enhanceStudent();await enhanceHistory();await enhanceTransition()},40)}
  new MutationObserver(enhance).observe(document.getElementById('screen')||document.body,{childList:true,subtree:true});window.addEventListener('popstate',enhance);enhance();
  const warm=()=>{readJson('/teacher/workbench-summary').catch(()=>{});readJson('/teacher/classes').catch(()=>{})};if('requestIdleCallback'in window)requestIdleCallback(warm,{timeout:1600});else setTimeout(warm,900);
})();
</script>
'''


def patch_v1_operational_html(html: str) -> str:
    """Add native, read-mostly V1 behavior once."""
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
