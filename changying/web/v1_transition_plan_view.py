"""Persistent, teacher-confirmed transition-plan UI for V1.

The factual transition snapshot stays read-only. This presentation layer adds
the missing product surface for the already-existing transition-plan API:
teacher/admin users can explicitly save and close plans, while student/parent
users can only read plans they are already authorized to view.
"""

from __future__ import annotations

from changying.web import v1 as v1_module


V1_TRANSITION_PLAN_VIEW_MARKER = "changying_v1_transition_plan_view_v1"

_SNIPPET = r'''
<style id="changying_v1_transition_plan_view_v1-style">
  .cy-transition-plans{margin-top:18px}
  .cy-transition-plan-list{display:grid;gap:10px}
  .cy-transition-plan-card{border:1px solid #e4e9f2;border-radius:14px;padding:13px;background:#fff}
  .cy-transition-plan-card h3{margin:0 0 6px;font-size:15px}
  .cy-transition-plan-card small{display:block;color:#667085;line-height:1.55}
  .cy-transition-plan-items{margin:8px 0 0;padding-left:20px;color:#344054}
  .cy-transition-plan-form{display:grid;gap:11px;margin-top:14px}
  .cy-transition-plan-form label{display:grid;gap:5px;font-size:12px;font-weight:750;color:#344054}
  .cy-transition-plan-form input,.cy-transition-plan-form textarea{width:100%;box-sizing:border-box;border:1px solid #d9e1ec;border-radius:10px;padding:10px;font:inherit;background:#fff;color:#172033}
  .cy-transition-plan-form textarea{min-height:72px;resize:vertical}
  .cy-transition-plan-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px}
  .cy-transition-plan-status{margin-top:9px;font-size:12px;color:#667085}
  @media(max-width:720px){.cy-transition-plan-grid{grid-template-columns:1fr}}
</style>
<script id="changying_v1_transition_plan_view_v1-script">
(()=>{
  if(window.__cyV1TransitionPlanViewInstalled)return;
  window.__cyV1TransitionPlanViewInstalled=true;
  let timer=null;
  const token=()=>{const remember=localStorage.getItem('v717Remember')==='1';return (remember?localStorage.getItem('v717Token'):sessionStorage.getItem('v717Token'))||sessionStorage.getItem('v717Token')||localStorage.getItem('v717Token')||sessionStorage.getItem('v6Token')||localStorage.getItem('v6Token')||''};
  const esc=v=>String(v??'').replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  const sidFromUrl=()=>{const raw=new URLSearchParams(location.search).get('id')||'';return /^\d+$/.test(raw)?raw:''};
  const selectedType=sid=>sessionStorage.getItem('changying.v1.transition.'+(sid||'general'))||'阶段衔接';
  const lines=value=>String(value||'').split(/\r?\n/).map(x=>x.trim()).filter(Boolean).slice(0,50);
  async function fetchJson(path,options={}){
    const t=token();const headers={...(options.headers||{})};
    if(t)headers.Authorization='Bearer '+t;
    if(options.body!==undefined)headers['Content-Type']='application/json';
    const r=await fetch(path,{...options,headers,cache:'no-store'});
    let data={};try{data=await r.json()}catch(_e){}
    if(!r.ok)throw new Error(data.detail||('HTTP '+r.status));
    return data;
  }
  function listItem(plan,editable,sid){
    const sections=[
      ['前置知识',plan.prerequisiteCheck],['差距',plan.gaps],['计划',plan.plan],
      ['假期干预',plan.holidayIntervention],['开学诊断',plan.openingDiagnosis]
    ].filter(x=>Array.isArray(x[1])&&x[1].length);
    const details=sections.map(([label,items])=>'<div style="margin-top:8px"><b>'+esc(label)+'</b><ul class="cy-transition-plan-items">'+items.map(x=>'<li>'+esc(x)+'</li>').join('')+'</ul></div>').join('');
    const close=editable&&plan.status==='active'?'<button class="btn" type="button" data-cy-close-plan="'+Number(plan.id)+'">关闭计划</button>':'';
    return '<article class="cy-transition-plan-card"><div class="section-head"><div><h3>'+esc(plan.transitionType||'阶段衔接')+'</h3><small>'+esc(plan.status==='active'?'进行中':'已关闭')+' · 创建 '+esc((plan.createdAt||'').slice(0,16).replace('T',' '))+'</small></div><span class="tag">'+esc(plan.status||'')+'</span></div>'
      +(plan.previousStage?'<small><b>上一阶段：</b>'+esc(plan.previousStage)+'</small>':'')
      +(plan.nextStageRequirement?'<small><b>下一阶段要求：</b>'+esc(plan.nextStageRequirement)+'</small>':'')
      +details
      +(plan.nextStage?'<small style="margin-top:8px"><b>下一阶段：</b>'+esc(plan.nextStage)+'</small>':'')
      +(close?'<div class="action-row" style="margin-top:10px">'+close+'</div>':'')
      +'</article>';
  }
  function formHtml(sid){
    return '<details class="card" style="margin-top:12px"><summary style="cursor:pointer;font-weight:850">新建教师确认的衔接计划</summary>'
      +'<div class="notice" style="margin-top:12px">系统只展示事实与已有证据，不自动生成升学分流或能力结论。以下内容由教师/管理员确认后才写入学生档案。</div>'
      +'<div class="cy-transition-plan-form">'
      +'<div class="cy-transition-plan-grid"><label>衔接类型<input id="cyTpType" value="'+esc(selectedType(sid))+'"></label><label>上一阶段事实<textarea id="cyTpPrevious" placeholder="例如：五年级上阶段事实回看"></textarea></label></div>'
      +'<label>下一阶段要求<textarea id="cyTpRequirement" placeholder="由教师填写下一阶段真实要求"></textarea></label>'
      +'<div class="cy-transition-plan-grid"><label>前置知识检查（每行一项）<textarea id="cyTpPrereq"></textarea></label><label>差距识别（每行一项）<textarea id="cyTpGaps"></textarea></label></div>'
      +'<label>衔接计划（每行一项）<textarea id="cyTpPlan" placeholder="例如：每周复查一次"></textarea></label>'
      +'<div class="cy-transition-plan-grid"><label>假期干预（每行一项）<textarea id="cyTpHoliday"></textarea></label><label>开学诊断（每行一项）<textarea id="cyTpOpening"></textarea></label></div>'
      +'<label>下一阶段<textarea id="cyTpNext"></textarea></label>'
      +'<button class="btn primary" type="button" id="cyTpSave">确认并保存衔接计划</button><div class="cy-transition-plan-status" id="cyTpStatus"></div>'
      +'</div></details>';
  }
  async function render(){
    if(location.pathname!='/v1/transition')return;
    if(document.getElementById('cy-transition-plan-section'))return;
    const t=token();if(!t||t==='demo')return;
    let session;try{session=await fetchJson('/session')}catch(_e){return}
    let sid=sidFromUrl();
    if(!sid&&session.role==='student')sid=String(session.userID||'');
    const main=document.querySelector('#screen main')
      ||document.querySelector('#screen .shell')
      ||document.getElementById('screen')
      ||document.getElementById('app')
      ||document.body;
    if(!main)return;
    function mountTP(root,sec){
      if(!root||!sec)return false;
      if(sec.id){var old=document.getElementById(sec.id);
        if(old&&old!==sec&&old.parentNode)old.parentNode.removeChild(old);}
      if(root.tagName!=='MAIN'&&!root.classList.contains('shell')){
        sec.setAttribute('data-standalone','1');
        var s=sec.style;s.boxSizing='border-box';s.width='100%';
        s.maxWidth='960px';s.margin='0 auto';s.padding='16px';
      }
      root.appendChild(sec);
      return true;
    }
    const section=document.createElement('section');section.id='cy-transition-plan-section';section.className='section cy-transition-plans';
    if(!sid){
      section.innerHTML='<div class="card"><h2>衔接计划</h2><div class="empty">请先选择一个学生，再查看或建立衔接计划。</div></div>';
      if(!mountTP(main,section))return;return;
    }
    const editable=session.role==='teacher'||session.role==='admin';
    let payload;try{payload=await fetchJson('/v1/students/'+encodeURIComponent(sid)+'/transition-plans')}catch(err){
      section.innerHTML='<div class="card"><h2>衔接计划</h2><div class="notice error">'+esc(err.message)+'</div></div>';if(!mountTP(main,section))return;return
    }
    const plans=payload.plans||[];
    section.innerHTML='<div class="section-head"><div><h2>教师确认的衔接计划</h2><p>与同一 student_id 绑定；已关闭计划仍作为历史保留。</p></div><span class="tag">'+plans.length+' 条</span></div>'
      +'<div class="cy-transition-plan-list">'+(plans.map(x=>listItem(x,editable,sid)).join('')||'<div class="empty">暂无已保存的衔接计划。</div>')+'</div>'
      +(editable?formHtml(sid):'<div class="notice" style="margin-top:12px">当前身份为只读查看；只有教师或管理员可保存/关闭衔接计划。</div>');
    if(!mountTP(main,section))return;
    section.querySelectorAll('[data-cy-close-plan]').forEach(btn=>btn.addEventListener('click',async()=>{
      if(!confirm('确认关闭这条衔接计划？关闭后仍保留历史记录。'))return;
      btn.disabled=true;
      try{await fetchJson('/v1/students/'+encodeURIComponent(sid)+'/transition-plans/'+encodeURIComponent(btn.dataset.cyClosePlan)+'/close',{method:'POST'});section.remove();render()}catch(err){btn.disabled=false;alert(err.message)}
    }));
    const save=section.querySelector('#cyTpSave');
    if(save)save.addEventListener('click',async()=>{
      const status=section.querySelector('#cyTpStatus');
      const payload={
        transitionType:section.querySelector('#cyTpType').value.trim()||'阶段衔接',
        previousStage:section.querySelector('#cyTpPrevious').value.trim(),
        nextStageRequirement:section.querySelector('#cyTpRequirement').value.trim(),
        prerequisiteCheck:lines(section.querySelector('#cyTpPrereq').value),
        gaps:lines(section.querySelector('#cyTpGaps').value),
        plan:lines(section.querySelector('#cyTpPlan').value),
        holidayIntervention:lines(section.querySelector('#cyTpHoliday').value),
        openingDiagnosis:lines(section.querySelector('#cyTpOpening').value),
        nextStage:section.querySelector('#cyTpNext').value.trim()
      };
      if(!payload.nextStageRequirement&&!payload.plan.length&&!payload.nextStage){
        status.textContent='请至少填写“下一阶段要求 / 衔接计划 / 下一阶段”中的一项。';return;
      }
      if(!confirm('确认把这份教师衔接计划写入该学生的连续档案？'))return;
      save.disabled=true;status.textContent='正在保存…';
      try{await fetchJson('/v1/students/'+encodeURIComponent(sid)+'/transition-plans',{method:'POST',body:JSON.stringify(payload)});section.remove();render()}catch(err){save.disabled=false;status.textContent=err.message}
    });
  }
  const run=()=>{clearTimeout(timer);timer=setTimeout(render,140)};
  new MutationObserver(run).observe(document.getElementById('screen')||document.body,{childList:true,subtree:true});
  window.addEventListener('popstate',run);
  run();
})();
</script>
'''


def patch_v1_transition_plan_view(html: str) -> str:
    if V1_TRANSITION_PLAN_VIEW_MARKER in html:
        return html
    if "</body>" not in html:
        raise RuntimeError("V1 transition plan view: closing body not found")
    html = html.replace(
        "未来每一步都引用同一个 student_id",
        "每一步都引用同一个 student_id；保存计划后继续留在这份连续档案中",
        1,
    )
    html = html.replace(
        "待教师录入或后续规则支持",
        "由教师确认后记录在下方衔接计划中",
    )
    return html.replace("</body>", _SNIPPET + "\n</body>", 1)


def install_v1_transition_plan_view_patch() -> None:
    if getattr(v1_module, "_transition_plan_view_patch_installed", False):
        return
    original = v1_module.v1_html

    def patched_v1_html() -> str:
        return patch_v1_transition_plan_view(original())

    v1_module.v1_html = patched_v1_html
    v1_module._transition_plan_view_patch_installed = True


__all__ = [
    "V1_TRANSITION_PLAN_VIEW_MARKER",
    "install_v1_transition_plan_view_patch",
    "patch_v1_transition_plan_view",
]
