"""V1 bridge for existing teaching write workflows.

This module deliberately reuses the production APIs and tables that already power
Classic.  It does not add a second homework store or invent a timetable model.
The bridge is installed before the read-only operational patch so selected V1
feature cards can open native V1 action panels while all other cards keep the
existing read-mostly behavior.
"""

from __future__ import annotations

from changying.web import v1 as v1_module

V1_TEACHING_ACTIONS_MARKER = "changying_v1_teaching_actions_v1"

_TEACHING_ACTIONS_SNIPPET = r'''
<style id="changying_v1_teaching_actions_v1-style">
  .cy-action-layer{position:fixed;inset:0;z-index:89;background:rgba(15,23,42,.38);display:flex;align-items:flex-end;justify-content:center;padding:18px}.cy-action-sheet{width:min(820px,100%);max-height:min(88dvh,900px);overflow:auto;background:#f7f9fc;border:1px solid #e4e9f2;border-radius:24px 24px 18px 18px;box-shadow:0 30px 90px rgba(15,23,42,.3);padding:18px}.cy-action-head{position:sticky;top:-18px;z-index:3;display:flex;justify-content:space-between;align-items:center;gap:12px;background:rgba(247,249,252,.96);backdrop-filter:blur(10px);padding:18px 0 12px}.cy-action-head h2{margin:0}.cy-action-close{border:1px solid #d8e0ec;background:#fff;border-radius:12px;padding:9px 12px;font-weight:800}.cy-action-note{padding:11px 12px;border-radius:12px;background:#eef6ff;border:1px solid #d4e7ff;color:#285078;font-size:12px;line-height:1.6}.cy-action-warn{background:#fff8e8;border-color:#f5d79a;color:#7a4a00}.cy-action-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.cy-action-field{display:grid;gap:6px}.cy-action-field label{font-size:12px;font-weight:800}.cy-action-field input,.cy-action-field select,.cy-action-field textarea{width:100%;border:1px solid #cfd7e5;border-radius:11px;background:#fff;padding:10px 11px;font:inherit}.cy-action-field textarea{min-height:82px;resize:vertical}.cy-action-list{display:grid;gap:9px;margin-top:12px}.cy-action-row{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;padding:12px;border:1px solid #e4e9f2;border-radius:13px;background:#fff}.cy-action-row b{display:block}.cy-action-row small{display:block;color:#667085;margin-top:4px}.cy-action-buttons{display:flex;gap:8px;flex-wrap:wrap}.cy-action-button{border:1px solid #d8e0ec;border-radius:10px;background:#fff;padding:8px 10px;font-weight:800;cursor:pointer}.cy-action-button.primary{background:#173c78;border-color:#173c78;color:#fff}.cy-action-button:disabled{opacity:.55;cursor:wait}.cy-action-section{margin-top:16px}.cy-action-section h3{margin:0 0 9px}.cy-action-error{padding:13px;border-radius:12px;background:#fff1f1;color:#991b1b;border:1px solid #fecaca}.cy-action-ok{padding:11px 12px;border-radius:12px;background:#ecfdf3;color:#166534;border:1px solid #bbf7d0}.cy-action-loading{padding:28px;text-align:center;color:#667085}
  @media(max-width:720px){.cy-action-layer{padding:0}.cy-action-sheet{max-height:92dvh;border-radius:24px 24px 0 0;padding:16px 14px calc(28px + env(safe-area-inset-bottom))}.cy-action-head{top:-16px;padding-top:16px}.cy-action-grid{grid-template-columns:1fr}.cy-action-row{flex-direction:column}.cy-action-buttons{width:100%}.cy-action-button{flex:1}}
</style>
<script id="changying_v1_teaching_actions_v1-script">
(()=>{
  if(window.__cyV1TeachingActionsInstalled)return;window.__cyV1TeachingActionsInstalled=true;
  const ACTION_FEATURES=new Set(['作业与错题','作业/练习','作业','批改/订正','备课','今日课程','今日课表','测验']);
  const token=()=>{const remember=localStorage.getItem('v717Remember')==='1';return (remember?localStorage.getItem('v717Token'):sessionStorage.getItem('v717Token'))||sessionStorage.getItem('v717Token')||localStorage.getItem('v717Token')||sessionStorage.getItem('v6Token')||localStorage.getItem('v6Token')||''};
  const esc=v=>String(v??'').replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  async function api(url,opt={}){
    const t=token();if(!t||t==='demo')throw new Error('演示会话不会写入真实教学数据');
    const headers={Authorization:'Bearer '+t,...(opt.headers||{})};if(opt.body&&!headers['Content-Type'])headers['Content-Type']='application/json';
    const r=await fetch(url,{...opt,headers,cache:'no-store'});if(!r.ok){let msg='操作失败 '+r.status;try{const d=await r.json();msg=d.detail||d.message||msg}catch{}throw new Error(msg)}
    if(r.status===204)return null;const ct=r.headers.get('content-type')||'';return ct.includes('application/json')?await r.json():await r.text();
  }
  function closeAction(){document.getElementById('cy-action-layer')?.remove();document.body.style.overflow=''}
  function openAction(title,subtitle='直接复用原教学系统的真实数据与权限。'){
    closeAction();document.getElementById('cy-feature-layer')?.remove();const layer=document.createElement('div');layer.id='cy-action-layer';layer.className='cy-action-layer';layer.innerHTML=`<section class="cy-action-sheet" role="dialog" aria-modal="true" aria-label="${esc(title)}"><div class="cy-action-head"><div><h2>${esc(title)}</h2><small style="color:#667085">${esc(subtitle)}</small></div><button class="cy-action-close" type="button">关闭</button></div><div id="cy-action-body" class="cy-action-loading">正在读取真实教学数据…</div></section>`;document.body.appendChild(layer);document.body.style.overflow='hidden';layer.querySelector('.cy-action-close').onclick=closeAction;layer.onclick=e=>{if(e.target===layer)closeAction()};return layer.querySelector('#cy-action-body')
  }
  function body(html){const b=document.getElementById('cy-action-body');if(b){b.className='';b.innerHTML=html}}
  function fail(err){body(`<div class="cy-action-error">${esc(err?.message||'操作失败')}</div>`)}
  function dueDefault(){return new Date(Date.now()+7*86400000).toISOString().slice(0,10)}
  function assignmentMeta(a){const due=a.dueDate||a.due_date||'';const mode=a.submissionMode||a.submission_mode||a.mode||'';const completed=a.completedCount??a.completed??'—';const total=a.studentCount??a.recipientCount??'—';return `${due?`截止 ${due} · `:''}${mode?`${mode} · `:''}完成 ${completed}/${total}`}
  async function showAssignments(title='作业与检查'){
    openAction(title);try{const [classes,assignments]=await Promise.all([api('/teacher/classes'),api('/teacher/assignments')]);const opts=classes.map(c=>`<option value="${c.id}" data-grade="${c.grade||5}">${esc(c.name||'班级')} · ${esc(c.grade||'—')}年级</option>`).join('');body(`<div class="cy-action-note">这里不是第二套作业系统：创建后仍写入原系统 assignments / papers，并继续出现在学生长期档案、待办和成绩统计中。</div><section class="cy-action-section card"><h3>布置新作业</h3><form id="cy-assignment-form"><div class="cy-action-grid"><div class="cy-action-field"><label>作业名称</label><input id="cy-at" required placeholder="例如：第二单元巩固"></div><div class="cy-action-field"><label>班级</label><select id="cy-ac" required>${opts||'<option value="">暂无可见班级</option>'}</select></div><div class="cy-action-field"><label>截止日期</label><input id="cy-ad" type="date" value="${dueDefault()}" required></div><div class="cy-action-field"><label>提交方式</label><select id="cy-am"><option value="media">拍照/视频</option><option value="quiz">在线答题</option><option value="mixed">在线答题 + 拍照/视频</option></select></div><div class="cy-action-field"><label>科目</label><select id="cy-as"><option>数学</option><option>语文</option><option>英语</option></select></div><div class="cy-action-field"><label>教材</label><input id="cy-ab" value="人教版"></div><div class="cy-action-field"><label>单元</label><input id="cy-au" placeholder="例如：第二单元"></div><div class="cy-action-field"><label>在线题数</label><input id="cy-an" type="number" min="1" max="30" value="5"></div></div><div class="cy-action-field" style="margin-top:10px"><label>作业说明</label><textarea id="cy-ai" placeholder="学生需要完成的要求"></textarea></div><button class="cy-action-button primary" id="cy-assign-submit" type="submit" style="margin-top:12px">确认布置</button></form></section><section class="cy-action-section"><h3>最近作业</h3><div class="cy-action-list">${assignments.slice(0,20).map(a=>`<div class="cy-action-row"><span><b>${esc(a.title||'作业')}</b><small>${esc(assignmentMeta(a))}</small></span><div class="cy-action-buttons"><button class="cy-action-button" data-cy-check="${a.id}">检查提交</button></div></div>`).join('')||'<div class="empty">暂无已布置作业</div>'}</div></section>`);document.querySelectorAll('[data-cy-check]').forEach(x=>x.onclick=()=>showSubmissions(Number(x.dataset.cyCheck),x.closest('.cy-action-row')?.querySelector('b')?.textContent||'作业检查'));const form=document.getElementById('cy-assignment-form');if(form)form.onsubmit=async e=>{e.preventDefault();const btn=document.getElementById('cy-assign-submit');btn.disabled=true;btn.textContent='正在布置…';try{const classID=Number(document.getElementById('cy-ac').value);if(!classID)throw new Error('请先选择班级');const classRow=classes.find(c=>Number(c.id)===classID)||{};const titleValue=document.getElementById('cy-at').value.trim();const mode=document.getElementById('cy-am').value;const subject=document.getElementById('cy-as').value;const textbook=document.getElementById('cy-ab').value.trim();const unit=document.getElementById('cy-au').value.trim();const due=document.getElementById('cy-ad').value;const instructions=document.getElementById('cy-ai').value.trim();let paperID=null;if(mode!=='media'){const params=new URLSearchParams({grade:String(classRow.grade||5),subject});if(textbook)params.set('textbook',textbook);if(unit)params.set('unit',unit);const qs=(await api('/questions?'+params.toString())).filter(q=>Array.isArray(q.options)&&q.options.length>=2&&q.questionType!=='non_choice');const count=Math.max(1,Math.min(30,Number(document.getElementById('cy-an').value)||5));const ids=qs.slice(0,count).map(q=>q.id);if(!ids.length)throw new Error('当前题库没有符合条件的在线题目，可先改用“拍照/视频”作业');const p=await api('/teacher/papers',{method:'POST',body:JSON.stringify({title:titleValue,grade:Number(classRow.grade||5),subject,textbook,unit,question_ids:ids})});paperID=p.id}await api('/teacher/assignments',{method:'POST',body:JSON.stringify({title:titleValue,class_id:classID,paper_id:paperID,due_date:due,submission_mode:mode,subject,textbook,unit,instructions})});body('<div class="cy-action-ok">作业已写入原教学系统，正在刷新列表…</div>');setTimeout(()=>showAssignments(title),450)}catch(err){fail(err)}finally{btn.disabled=false;btn.textContent='确认布置'}}}catch(err){fail(err)}
  }
  async function showReviewList(title='批改 / 订正'){
    openAction(title);try{const assignments=await api('/teacher/assignments');body(`<div class="cy-action-note">先选择作业，再检查每名学生的提交状态、成绩、错题和教师确认状态。</div><div class="cy-action-list">${assignments.slice(0,30).map(a=>`<div class="cy-action-row"><span><b>${esc(a.title||'作业')}</b><small>${esc(assignmentMeta(a))}</small></span><button class="cy-action-button primary" data-cy-review="${a.id}">打开检查</button></div>`).join('')||'<div class="empty">暂无作业</div>'}</div>`);document.querySelectorAll('[data-cy-review]').forEach(x=>x.onclick=()=>showSubmissions(Number(x.dataset.cyReview),x.closest('.cy-action-row')?.querySelector('b')?.textContent||'作业检查'))}catch(err){fail(err)}
  }
  async function showSubmissions(aid,title='作业检查'){
    openAction(title,'检查结果直接来自原系统的作业提交记录。');try{const rows=await api(`/teacher/assignments/${aid}/submissions`);body(`<div class="cy-action-note">共 ${rows.length} 名接收学生。在线题成绩沿用原系统自动判分；照片/视频作业仍需教师结合原件检查。</div><div class="cy-action-list">${rows.map(x=>`<div class="cy-action-row"><span><b>${esc(x.studentName||'学生')}</b><small>${esc(x.status||x.statusCode||'待检查')}${x.score!==null&&x.score!==undefined?` · ${esc(x.score)}分`:''}${x.wrongCount?` · 错题 ${esc(x.wrongCount)}`:''}${x.teacherConfirmed?' · 已教师确认':''}</small></span><div class="cy-action-buttons"><a class="cy-action-button" href="/v1/student?id=${encodeURIComponent(x.studentID)}">学生档案</a></div></div>`).join('')||'<div class="empty">暂无接收学生</div>'}</div>`)}catch(err){fail(err)}
  }
  async function showLessons(title='备课与课时编排'){
    openAction(title);try{const lessons=await api('/teaching/lessons');body(`<div class="cy-action-note">复用原系统“定制教学”的真实课时。这里可以修改课时名称、单元、核心目标与发布状态；这是课时内容编排，不等同于带日期/教室的日历排课。</div><div class="cy-action-list">${lessons.slice(0,40).map(l=>`<div class="cy-action-row"><span><b>${esc(l.subject||'课程')} · 第${esc(l.lessonNo||'—')}课时 · ${esc(l.title||'未命名')}</b><small>${esc(l.unit||'未设置单元')} · ${esc(l.durationMin||120)}分钟 · ${l.published?'已发布':'未发布'}</small></span><button class="cy-action-button" data-cy-lesson="${l.id}">编辑</button></div>`).join('')||'<div class="empty">当前没有可用定制课时</div>'}</div>`);document.querySelectorAll('[data-cy-lesson]').forEach(x=>x.onclick=()=>editLesson(Number(x.dataset.cyLesson)))}catch(err){fail(err)}
  }
  async function editLesson(id){
    openAction('编辑课时');try{const l=await api('/teaching/lessons/'+id);body(`<form id="cy-lesson-form"><div class="cy-action-grid"><div class="cy-action-field"><label>课时名称</label><input id="cy-lt" value="${esc(l.title||'')}"></div><div class="cy-action-field"><label>教材单元</label><input id="cy-lu" value="${esc(l.unit||'')}"></div><div class="cy-action-field"><label>时长（分钟）</label><input id="cy-ld" type="number" min="30" max="240" value="${esc(l.durationMin||120)}"></div><div class="cy-action-field"><label>发布给学生</label><select id="cy-lp"><option value="0" ${l.published?'':'selected'}>未发布</option><option value="1" ${l.published?'selected':''}>已发布</option></select></div></div><div class="cy-action-field" style="margin-top:10px"><label>核心目标</label><textarea id="cy-lc">${esc(l.coreTarget||'')}</textarea></div><div class="cy-action-field" style="margin-top:10px"><label>教师教案</label><textarea id="cy-lplan">${esc(l.teacherPlan||'')}</textarea></div><button class="cy-action-button primary" type="submit" style="margin-top:12px">保存课时</button></form>`);document.getElementById('cy-lesson-form').onsubmit=async e=>{e.preventDefault();const btn=e.submitter;btn.disabled=true;try{await api('/teaching/lessons/'+id,{method:'PUT',body:JSON.stringify({title:document.getElementById('cy-lt').value.trim(),unit:document.getElementById('cy-lu').value.trim(),core_target:document.getElementById('cy-lc').value.trim(),teacher_plan:document.getElementById('cy-lplan').value.trim(),duration_min:Number(document.getElementById('cy-ld').value)||120,published:document.getElementById('cy-lp').value==='1'})});body('<div class="cy-action-ok">课时已保存到原教学系统。</div>');setTimeout(()=>showLessons(),450)}catch(err){fail(err)}finally{btn.disabled=false}}}catch(err){fail(err)}
  }
  async function showTimetableBoundary(){
    openAction('今日课表','先核对现有能力边界，再进入真正的排课数据模型。');try{const [classes,lessons]=await Promise.all([api('/teacher/classes'),api('/teaching/lessons').catch(()=>[])]);body(`<div class="cy-action-note cy-action-warn">当前生产库没有标准化“日期 / 时段 / 教室 / 教师 / 班级”的课表表，因此不能把课时方案冒充真实日历排课。V1 继续显示真实班级和既有课时，正式排课应作为 V1.1 数据迁移单独推进。</div><section class="cy-action-section"><h3>当前真实班级</h3><div class="cy-action-list">${classes.map(c=>`<div class="cy-action-row"><span><b>${esc(c.name||'班级')}</b><small>${esc(c.grade||'—')}年级</small></span></div>`).join('')||'<div class="empty">暂无班级</div>'}</div></section><section class="cy-action-section"><h3>可用于编排的教学课时</h3><div class="cy-action-list">${lessons.slice(0,20).map(l=>`<div class="cy-action-row"><span><b>${esc(l.subject||'课程')} · 第${esc(l.lessonNo||'—')}课时 · ${esc(l.title||'未命名')}</b><small>${l.published?'已发布':'未发布'} · ${esc(l.durationMin||120)}分钟</small></span></div>`).join('')||'<div class="empty">暂无课时</div>'}</div></section>`)}catch(err){fail(err)}
  }
  async function handleFeature(name){const f=(name||'').trim();if(['作业与错题','作业/练习','作业','测验'].includes(f)){await showAssignments(f);return}if(f==='批改/订正'){await showReviewList(f);return}if(['备课','今日课程'].includes(f)){await showLessons(f);return}if(f==='今日课表'){await showTimetableBoundary();return}}
  document.addEventListener('click',e=>{const b=e.target.closest('[data-feature]');if(!b)return;const name=(b.dataset.feature||'').trim();if(!ACTION_FEATURES.has(name))return;e.preventDefault();e.stopImmediatePropagation();handleFeature(name)},true);
})();
</script>
'''


def patch_v1_teaching_actions_html(html: str) -> str:
    """Add the action bridge once without changing the V1 route set."""
    if V1_TEACHING_ACTIONS_MARKER in html:
        return html
    if "</body>" not in html:
        raise RuntimeError("V1 teaching actions patch: closing body marker not found")
    return html.replace("</body>", _TEACHING_ACTIONS_SNIPPET + "\n</body>", 1)


def install_v1_teaching_actions_patch() -> None:
    """Install before the operational patch so targeted cards win capture order."""
    if getattr(v1_module, "_teaching_actions_patch_installed", False):
        return
    original = v1_module.v1_html

    def patched_v1_html() -> str:
        return patch_v1_teaching_actions_html(original())

    v1_module.v1_html = patched_v1_html
    v1_module._teaching_actions_patch_installed = True


__all__ = [
    "V1_TEACHING_ACTIONS_MARKER",
    "install_v1_teaching_actions_patch",
    "patch_v1_teaching_actions_html",
]
