"""V2 teacher learning-evidence recorder for the V1 student detail page."""

from __future__ import annotations

from changying.web import v1 as v1_module


V2_EVIDENCE_RECORDER_MARKER = "changying_v2_evidence_recorder_v1"

_SNIPPET = r'''
<style id="changying_v2_evidence_recorder_v1-style">
  .cy-evidence-recorder{margin-top:16px}
  .cy-evidence-form{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;margin-top:12px}
  .cy-evidence-form .full{grid-column:1/-1}
  .cy-evidence-form label{display:grid;gap:5px;font-size:13px;color:#475467}
  .cy-evidence-form input,.cy-evidence-form select,.cy-evidence-form textarea{width:100%;box-sizing:border-box}
  .cy-evidence-form textarea{min-height:82px;resize:vertical}
  .cy-evidence-actions{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
  .cy-evidence-manual-list{display:grid;gap:8px;margin-top:12px}
  .cy-evidence-manual-row{border:1px solid #e4e9f2;border-radius:12px;padding:10px 12px;display:flex;justify-content:space-between;gap:12px;align-items:flex-start}
  .cy-evidence-manual-row small{display:block;color:#667085;margin-top:4px}
  @media(max-width:720px){.cy-evidence-form{grid-template-columns:1fr}.cy-evidence-manual-row{flex-direction:column}}
</style>
<script id="changying_v2_evidence_recorder_v1-script">
(()=>{
  if(window.__cyV2EvidenceRecorderInstalled)return;
  window.__cyV2EvidenceRecorderInstalled=true;
  let timer=null,lastKey='';
  const token=()=>{const remember=localStorage.getItem('v717Remember')==='1';return (remember?localStorage.getItem('v717Token'):sessionStorage.getItem('v717Token'))||sessionStorage.getItem('v717Token')||localStorage.getItem('v717Token')||sessionStorage.getItem('v6Token')||localStorage.getItem('v6Token')||''};
  const esc=v=>String(v??'').replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  const names={independent:'独立完成',retention:'跨时保持',transfer:'迁移应用'};
  async function api(url,options={}){
    const t=token();if(!t||t==='demo')throw new Error('未登录');
    const r=await fetch(url,{...options,headers:{'Content-Type':'application/json',Authorization:'Bearer '+t,...(options.headers||{})},cache:'no-store'});
    let body=null;try{body=await r.json()}catch(_){}
    if(!r.ok)throw new Error(body?.detail||'请求失败');
    return body;
  }
  const successText=v=>v===true?'观察到成功表现':v===false?'本次未观察到成功表现':'未记录成功/失败';
  function recordHtml(x,session){
    const meta=[names[x.evidenceType]||x.evidenceType,x.subject||'',x.knowledgeKey||'',(x.occurredAt||'').slice(0,16).replace('T',' ')].filter(Boolean).join(' · ');
    const canRetract=session.role==='admin'||Number(x.actorID)===Number(session.userID);
    return '<div class="cy-evidence-manual-row"><div><b>'+esc(x.note||'教师学习证据')+'</b><small>'+esc(meta)+'</small><small>'+esc(successText(x.success))+(x.context?' · '+esc(x.context):'')+(x.actorName?' · 记录人 '+esc(x.actorName):'')+'</small></div>'+(canRetract?'<button class="btn secondary" type="button" data-retract="'+esc(x.id)+'">撤回记录</button>':'')+'</div>';
  }
  async function install(){
    if(location.pathname!='/v1/student')return;
    const sid=new URLSearchParams(location.search).get('id');if(!sid)return;
    const key=sid+'|'+location.search;
    if(lastKey===key&&document.getElementById('cy-evidence-recorder'))return;
    const t=token();if(!t||t==='demo')return;
    let session;
    try{session=await api('/session')}catch(_){return}
    if(!['teacher','admin'].includes(session.role))return;
    let manual;
    try{manual=await api('/v2/students/'+encodeURIComponent(sid)+'/learning-evidence/manual')}catch(_){return}
    const host=document.getElementById('learningEvidence')||document.querySelector('#screen main');
    if(!host||document.getElementById('cy-evidence-recorder'))return;
    const now=new Date();now.setMinutes(now.getMinutes()-now.getTimezoneOffset());
    const box=document.createElement('div');
    box.id='cy-evidence-recorder';
    box.className='card cy-evidence-recorder';
    box.innerHTML='<div class="section-head"><div><h3>教师学习证据记录</h3><p>手工只记录“独立完成、跨时保持、迁移应用”；学习表现继续由作业/测验自动形成。</p></div><span class="tag">追加式记录</span></div><form id="cyEvidenceForm" class="cy-evidence-form"><label>证据类型<select name="evidenceType" required><option value="independent">独立完成</option><option value="retention">跨时保持</option><option value="transfer">迁移应用</option></select></label><label>发生时间<input name="occurredAt" type="datetime-local" required value="'+now.toISOString().slice(0,16)+'"></label><label>学科<input name="subject" maxlength="80" placeholder="如：数学"></label><label>知识点<input name="knowledgeKey" maxlength="160" placeholder="如：异分母分数加法"></label><label>观察结果<select name="success"><option value="">不记录成功/失败</option><option value="true">观察到成功表现</option><option value="false">本次未观察到成功表现</option></select></label><label>情境<input name="context" maxlength="500" placeholder="如：周末课 / 新题型 / 一周后复测"></label><label class="full">观察记录<textarea name="note" maxlength="1000" required placeholder="描述学生实际完成了什么、是否有提示、材料或情境有什么变化。"></textarea></label><div class="full cy-evidence-actions"><button class="btn primary" type="submit">保存学习证据</button><span id="cyEvidenceStatus" class="muted"></span></div></form><div style="margin-top:18px"><h3>当前有效的教师记录</h3><div id="cyEvidenceManualList" class="cy-evidence-manual-list">'+((manual.records||[]).map(x=>recordHtml(x,session)).join('')||'<div class="empty">尚无教师手工证据。</div>')+'</div></div>';
    host.appendChild(box);
    const form=box.querySelector('#cyEvidenceForm'),status=box.querySelector('#cyEvidenceStatus');
    form.addEventListener('submit',async e=>{
      e.preventDefault();status.textContent='正在保存…';
      const fd=new FormData(form),rawSuccess=fd.get('success'),rawTime=String(fd.get('occurredAt')||'');
      const payload={
        evidenceType:String(fd.get('evidenceType')||''),
        subject:String(fd.get('subject')||''),
        knowledgeKey:String(fd.get('knowledgeKey')||''),
        success:rawSuccess===''?null:rawSuccess==='true',
        note:String(fd.get('note')||''),
        context:String(fd.get('context')||''),
        occurredAt:rawTime?new Date(rawTime).toISOString():null
      };
      try{
        await api('/v2/students/'+encodeURIComponent(sid)+'/learning-evidence',{method:'POST',body:JSON.stringify(payload)});
        status.textContent='已保存，正在刷新连续档案…';
        setTimeout(()=>location.reload(),250);
      }catch(err){status.textContent=err.message||'保存失败'}
    });
    box.querySelectorAll('[data-retract]').forEach(btn=>btn.addEventListener('click',async()=>{
      const reason=prompt('请填写撤回原因。原记录不会删除，系统会追加一条撤回事件。','记录有误');
      if(!reason)return;
      btn.disabled=true;
      try{
        await api('/v2/learning-evidence/'+encodeURIComponent(btn.dataset.retract)+'/retract',{method:'POST',body:JSON.stringify({reason})});
        location.reload();
      }catch(err){btn.disabled=false;status.textContent=err.message||'撤回失败'}
    }));
    lastKey=key;
  }
  const run=()=>{clearTimeout(timer);timer=setTimeout(install,120)};
  new MutationObserver(run).observe(document.getElementById('screen')||document.body,{childList:true,subtree:true});
  window.addEventListener('popstate',run);
  run();
})();
</script>
'''


def patch_v2_learning_evidence_recorder(html: str) -> str:
    if V2_EVIDENCE_RECORDER_MARKER in html:
        return html
    if "</body>" not in html:
        raise RuntimeError("V2 evidence recorder: closing body not found")
    return html.replace("</body>", _SNIPPET + "\n</body>", 1)


def install_v2_learning_evidence_recorder_patch() -> None:
    if getattr(v1_module, "_v2_learning_evidence_recorder_installed", False):
        return
    original = v1_module.v1_html

    def patched_v1_html() -> str:
        return patch_v2_learning_evidence_recorder(original())

    v1_module.v1_html = patched_v1_html
    v1_module._v2_learning_evidence_recorder_installed = True


__all__ = [
    "V2_EVIDENCE_RECORDER_MARKER",
    "install_v2_learning_evidence_recorder_patch",
    "patch_v2_learning_evidence_recorder",
]
