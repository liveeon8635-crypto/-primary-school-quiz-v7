"""Teacher-facing, read-only planning facts on the V1 student detail page."""

from __future__ import annotations

from changying.web import v1 as v1_module


V21_TEACHING_EVIDENCE_CONTEXT_MARKER = "changying_v21_teaching_evidence_context_v1"

_SNIPPET = r'''
<style id="changying_v21_teaching_evidence_context_v1-style">
  .cy-plan-facts{margin-top:16px}.cy-plan-dims{display:flex;gap:8px;flex-wrap:wrap;margin-top:10px}
  .cy-plan-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;margin-top:14px}
  .cy-plan-fact-list{display:grid;gap:8px;margin-top:10px}.cy-plan-fact-list .row{align-items:flex-start}
  .cy-plan-boundary{margin-top:12px}.cy-plan-actions{display:flex;gap:8px;flex-wrap:wrap;margin-top:12px}
  @media(max-width:720px){.cy-plan-grid{grid-template-columns:1fr}}
</style>
<script id="changying_v21_teaching_evidence_context_v1-script">
(()=>{
  if(window.__cyV21TeachingEvidenceContextInstalled)return;
  window.__cyV21TeachingEvidenceContextInstalled=true;
  let timer=null,lastKey='';
  const token=()=>{const remember=localStorage.getItem('v717Remember')==='1';return (remember?localStorage.getItem('v717Token'):sessionStorage.getItem('v717Token'))||sessionStorage.getItem('v717Token')||localStorage.getItem('v717Token')||sessionStorage.getItem('v6Token')||localStorage.getItem('v6Token')||''};
  const esc=v=>String(v??'').replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  const dimName={performance:'学习表现',independent:'独立完成',retention:'跨时保持',transfer:'迁移应用'};
  function successText(v){return v===true?'观察到成功表现':v===false?'本次未观察到成功表现':'未记录成功/失败'}
  function knowledgeHtml(x){
    const dims=(x.evidenceTypes||[]).map(y=>dimName[y]||y).join(' / ')||'未标注维度';
    const meta=[x.subject||'',dims,'样本 '+(x.sampleCount||0),(x.latestAt||'').slice(0,10)].filter(Boolean).join(' · ');
    const score=x.averageObservedScore===null||x.averageObservedScore===undefined?'观测均分 —':'观测均分 '+x.averageObservedScore;
    const rate=x.observedSuccessRate===null||x.observedSuccessRate===undefined?'成功率 —':'成功率 '+x.observedSuccessRate+'%';
    return '<div class="row"><span class="row-main"><b>'+esc(x.knowledgeKey||'未标注知识点')+'</b><small>'+esc(meta)+'</small></span><span class="tag">'+esc(score+' · '+rate)+'</span></div>';
  }
  function recentHtml(x){
    const title=(x.subject||'未标注学科')+(x.knowledgeKey?' · '+x.knowledgeKey:'');
    const meta=[dimName[x.evidenceType]||x.evidenceType||'学习证据',(x.occurredAt||'').slice(0,16).replace('T',' '),successText(x.success),x.context||''].filter(Boolean).join(' · ');
    return '<div class="row"><span class="row-main"><b>'+esc(title)+'</b><small>'+esc(meta)+'</small></span></div>';
  }
  async function install(){
    if(location.pathname!='/v1/student')return;
    const sid=new URLSearchParams(location.search).get('id');if(!sid)return;
    const key=sid+'|'+location.search;
    if(lastKey===key&&document.getElementById('cy-plan-facts'))return;
    const t=token();if(!t||t==='demo')return;
    let session;
    try{
      const sr=await fetch('/session',{headers:{Authorization:'Bearer '+t},cache:'no-store'});
      if(!sr.ok)return;session=await sr.json();
    }catch(_){return}
    if(!['teacher','admin'].includes(session.role))return;
    let data;
    try{
      const r=await fetch('/v2/students/'+encodeURIComponent(sid)+'/teaching-evidence-context',{headers:{Authorization:'Bearer '+t},cache:'no-store'});
      if(!r.ok)return;data=await r.json();
    }catch(_){return}
    const host=document.getElementById('learningEvidence')||document.querySelector('#screen main');
    if(!host||document.getElementById('cy-plan-facts'))return;
    const available=(data.availableDimensions||[]).map(x=>'<span class="tag">'+esc(dimName[x]||x)+'</span>').join('');
    const missing=(data.missingDimensions||[]).map(x=>'<span class="tag">'+esc(dimName[x]||x)+'：尚无记录</span>').join('');
    const knowledge=(data.knowledgeFacts||[]).map(knowledgeHtml).join('');
    const recent=(data.recentFacts||[]).slice(0,6).map(recentHtml).join('');
    const section=document.createElement('section');
    section.id='cy-plan-facts';
    section.className='card cy-plan-facts';
    section.innerHTML='<div class="section-head"><div><h3>教师备课事实参考</h3><p>把同一学生连续档案中的已记录证据带入备课，不生成自动教学结论。</p></div><span class="tag">事实参考 · '+esc(data.sampleCount||0)+' 条</span></div><div class="cy-plan-grid"><div><h3>已记录证据维度</h3><div class="cy-plan-dims">'+(available||'<span class="tag">暂无标准化证据</span>')+'</div></div><div><h3>尚无记录的维度</h3><div class="cy-plan-dims">'+(missing||'<span class="tag">四类维度均已有记录</span>')+'</div></div></div><div class="cy-plan-grid"><div><h3>知识点事实</h3><div class="cy-plan-fact-list">'+(knowledge||'<div class="empty">暂无知识点证据</div>')+'</div></div><div><h3>最近证据情境</h3><div class="cy-plan-fact-list">'+(recent||'<div class="empty">暂无最近证据</div>')+'</div></div></div><div class="notice cy-plan-boundary">'+esc(data.boundary||'')+'</div><div class="cy-plan-actions"><a class="btn primary" href="'+esc(data.teachingToolPath||'/v1/tool?page=teaching')+'">打开现有教学方案 →</a></div>';
    host.insertAdjacentElement('afterend',section);
    lastKey=key;
  }
  const run=()=>{clearTimeout(timer);timer=setTimeout(install,120)};
  new MutationObserver(run).observe(document.getElementById('screen')||document.body,{childList:true,subtree:true});
  window.addEventListener('popstate',run);
  run();
})();
</script>
'''


def patch_v21_teaching_evidence_context_view(html: str) -> str:
    if V21_TEACHING_EVIDENCE_CONTEXT_MARKER in html:
        return html
    if "</body>" not in html:
        raise RuntimeError("V2.1 teaching evidence context: closing body not found")
    return html.replace("</body>", _SNIPPET + "\n</body>", 1)


def install_v21_teaching_evidence_context_view_patch() -> None:
    if getattr(v1_module, "_v21_teaching_evidence_context_view_installed", False):
        return
    original = v1_module.v1_html

    def patched_v1_html() -> str:
        return patch_v21_teaching_evidence_context_view(original())

    v1_module.v1_html = patched_v1_html
    v1_module._v21_teaching_evidence_context_view_installed = True


__all__ = [
    "V21_TEACHING_EVIDENCE_CONTEXT_MARKER",
    "install_v21_teaching_evidence_context_view_patch",
    "patch_v21_teaching_evidence_context_view",
]
