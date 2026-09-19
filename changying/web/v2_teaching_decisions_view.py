"""Teacher-authored planning decision editor for V1 student detail."""

from __future__ import annotations

from changying.web import v1 as v1_module


V22_TEACHING_DECISION_MARKER = "changying_v22_teaching_decision_v1"

_SNIPPET = r'''
<style id="changying_v22_teaching_decision_v1-style">
  .cy-teach-decision{margin-top:16px}.cy-teach-decision-form{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;margin-top:12px}
  .cy-teach-decision-form .full{grid-column:1/-1}.cy-teach-decision-form label{display:grid;gap:5px;font-size:13px;color:#475467}
  .cy-teach-decision-form input,.cy-teach-decision-form textarea{width:100%;box-sizing:border-box}.cy-teach-decision-form textarea{min-height:86px;resize:vertical}
  .cy-teach-decision-list{display:grid;gap:10px;margin-top:12px}.cy-teach-decision-row{border:1px solid #e4e9f2;border-radius:12px;padding:12px}
  .cy-teach-decision-meta{font-size:12px;color:#667085;margin-top:5px}.cy-teach-decision-plan{white-space:pre-wrap;line-height:1.6;margin-top:8px}
  .cy-teach-decision-actions{display:flex;gap:8px;flex-wrap:wrap;margin-top:10px}
  @media(max-width:720px){.cy-teach-decision-form{grid-template-columns:1fr}}
</style>
<script id="changying_v22_teaching_decision_v1-script">
(()=>{
  if(window.__cyV22TeachingDecisionInstalled)return;
  window.__cyV22TeachingDecisionInstalled=true;
  let timer=null,lastKey='';
  const token=()=>{const remember=localStorage.getItem('v717Remember')==='1';return (remember?localStorage.getItem('v717Token'):sessionStorage.getItem('v717Token'))||sessionStorage.getItem('v717Token')||localStorage.getItem('v717Token')||sessionStorage.getItem('v6Token')||localStorage.getItem('v6Token')||''};
  const esc=v=>String(v??'').replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  const dimName={performance:'学习表现',independent:'独立完成',retention:'跨时保持',transfer:'迁移应用'};
  async function api(url,options={}){
    const t=token();if(!t||t==='demo')throw new Error('未登录');
    const r=await fetch(url,{...options,headers:{'Content-Type':'application/json',Authorization:'Bearer '+t,...(options.headers||{})},cache:'no-store'});
    let body=null;try{body=await r.json()}catch(_){}
    if(!r.ok)throw new Error(body?.detail||'请求失败');
    return body;
  }
  function decisionHtml(x,session){
    const snap=x.evidenceSnapshot||{},dims=(snap.dimensions||[]).map(y=>dimName[y]||y).join(' / ')||'保存时暂无标准化证据';
    const meta=[x.subject||'',x.plannedFor?'计划 '+x.plannedFor:'',x.actorName?'教师 '+x.actorName:'',(x.createdAt||'').slice(0,16).replace('T',' ')].filter(Boolean).join(' · ');
    const canRetract=session.role==='admin'||Number(x.actorID)===Number(session.userID);
    return '<div class="cy-teach-decision-row"><b>'+esc(x.goal||'教师教学目标')+'</b><div class="cy-teach-decision-meta">'+esc(meta)+'</div><div class="cy-teach-decision-plan">'+esc(x.plan||'')+'</div>'+(x.note?'<div class="notice" style="margin-top:8px">'+esc(x.note)+'</div>':'')+'<div class="cy-teach-decision-meta">保存时证据：'+esc(dims)+' · 样本 '+esc(snap.sampleCount||0)+'。该快照仅说明当时参考事实，不代表系统建议。</div>'+(canRetract?'<div class="cy-teach-decision-actions"><button type="button" class="btn secondary" data-decision-retract="'+esc(x.id)+'">撤回此决定</button></div>':'')+'</div>';
  }
  async function install(){
    if(location.pathname!='/v1/student')return;
    const sid=new URLSearchParams(location.search).get('id');if(!sid)return;
    const key=sid+'|'+location.search;
    if(lastKey===key&&document.getElementById('cy-teach-decision'))return;
    const t=token();if(!t||t==='demo')return;
    let session;
    try{session=await api('/session')}catch(_){return}
    if(!['teacher','admin'].includes(session.role))return;
    let data;
    try{data=await api('/v2/students/'+encodeURIComponent(sid)+'/teaching-decisions')}catch(_){return}
    const anchor=document.getElementById('cy-plan-facts')||document.getElementById('learningEvidence')||document.querySelector('#screen main');
    if(!anchor||document.getElementById('cy-teach-decision'))return;
    const section=document.createElement('section');section.id='cy-teach-decision';section.className='card cy-teach-decision';
    section.innerHTML='<div class="section-head"><div><h3>教师备课决定记录</h3><p>这里保存的是教师自己的教学决定，不是系统建议。保存时系统只冻结当前证据快照，便于以后追溯依据。</p></div><span class="tag">教师填写 · 追加式</span></div><form id="cyTeachDecisionForm" class="cy-teach-decision-form"><label>学科<input name="subject" maxlength="80" placeholder="如：数学"></label><label>计划日期<input name="plannedFor" type="date"></label><label class="full">本次教学目标<textarea name="goal" maxlength="1500" required placeholder="由教师填写本次希望完成的教学目标。"></textarea></label><label class="full">教学安排<textarea name="plan" maxlength="4000" required placeholder="由教师填写材料、任务、节奏、课堂组织或检查方式。系统不会自动生成。"></textarea></label><label class="full">教师备注<textarea name="note" maxlength="1500" placeholder="可记录需要现场确认的事项。"></textarea></label><div class="full cy-teach-decision-actions"><button type="submit" class="btn primary">保存教师决定</button><span id="cyTeachDecisionStatus" class="muted"></span></div></form><div style="margin-top:18px"><h3>当前有效的教师决定</h3><div id="cyTeachDecisionList" class="cy-teach-decision-list">'+((data.decisions||[]).map(x=>decisionHtml(x,session)).join('')||'<div class="empty">尚无教师备课决定记录。</div>')+'</div></div>';
    anchor.insertAdjacentElement('afterend',section);
    const form=section.querySelector('#cyTeachDecisionForm'),status=section.querySelector('#cyTeachDecisionStatus');
    form.addEventListener('submit',async e=>{
      e.preventDefault();status.textContent='正在保存…';const fd=new FormData(form);
      const payload={subject:String(fd.get('subject')||''),plannedFor:String(fd.get('plannedFor')||''),goal:String(fd.get('goal')||''),plan:String(fd.get('plan')||''),note:String(fd.get('note')||'')};
      try{
        await api('/v2/students/'+encodeURIComponent(sid)+'/teaching-decisions',{method:'POST',body:JSON.stringify(payload)});
        status.textContent='已保存教师决定；正在刷新…';setTimeout(()=>location.reload(),250);
      }catch(err){status.textContent=err.message||'保存失败'}
    });
    section.querySelectorAll('[data-decision-retract]').forEach(btn=>btn.addEventListener('click',async()=>{
      const reason=prompt('请填写撤回原因。原决定不会删除，系统会追加一条撤回事件。','计划调整');
      if(!reason)return;btn.disabled=true;
      try{
        await api('/v2/teaching-decisions/'+encodeURIComponent(btn.dataset.decisionRetract)+'/retract',{method:'POST',body:JSON.stringify({reason})});
        location.reload();
      }catch(err){btn.disabled=false;status.textContent=err.message||'撤回失败'}
    }));
    lastKey=key;
  }
  const run=()=>{clearTimeout(timer);timer=setTimeout(install,120)};
  new MutationObserver(run).observe(document.getElementById('screen')||document.body,{childList:true,subtree:true});
  window.addEventListener('popstate',run);run();
})();
</script>
'''


def patch_v22_teaching_decision_view(html: str) -> str:
    if V22_TEACHING_DECISION_MARKER in html:
        return html
    if "</body>" not in html:
        raise RuntimeError("V2.2 teaching decision: closing body not found")
    return html.replace("</body>", _SNIPPET + "\n</body>", 1)


def install_v22_teaching_decision_view_patch() -> None:
    if getattr(v1_module, "_v22_teaching_decision_view_installed", False):
        return
    original = v1_module.v1_html

    def patched_v1_html() -> str:
        return patch_v22_teaching_decision_view(original())

    v1_module.v1_html = patched_v1_html
    v1_module._v22_teaching_decision_view_installed = True


__all__ = [
    "V22_TEACHING_DECISION_MARKER",
    "install_v22_teaching_decision_view_patch",
    "patch_v22_teaching_decision_view",
]
