"""Presentation-only factual transition snapshot on the V1 transition page."""

from __future__ import annotations

from changying.web import v1 as v1_module


V1_TRANSITION_FACTS_MARKER = "changying_v1_transition_facts_v1"

_SNIPPET = r'''
<style id="changying_v1_transition_facts_v1-style">
  .cy-transition-facts{margin-top:18px}.cy-transition-history{display:grid;gap:8px}.cy-transition-history .row{align-items:flex-start}
  .cy-evidence-dims{display:flex;gap:8px;flex-wrap:wrap}.cy-fact-note{font-size:13px;color:#667085;margin-top:8px}
</style>
<script id="changying_v1_transition_facts_v1-script">
(()=>{
  if(window.__cyV1TransitionFactsInstalled)return;
  window.__cyV1TransitionFactsInstalled=true;
  let timer=null,lastKey='';
  const token=()=>{const remember=localStorage.getItem('v717Remember')==='1';return (remember?localStorage.getItem('v717Token'):sessionStorage.getItem('v717Token'))||sessionStorage.getItem('v717Token')||localStorage.getItem('v717Token')||sessionStorage.getItem('v6Token')||localStorage.getItem('v6Token')||''};
  const esc=v=>String(v??'').replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  const dimName={performance:'学习表现',independent:'独立完成',retention:'跨时保持',transfer:'迁移应用'};
  function stageHtml(title,x){
    if(!x)return '<div class="card"><h3>'+esc(title)+'</h3><div class="empty">暂无明确班级阶段记录</div></div>';
    const period=(x.joinedAt||'时间未记录')+' → '+(x.current?'至今':(x.leftAt||'结束时间未记录'));
    return '<div class="card"><h3>'+esc(title)+'</h3><div class="row"><span class="row-main"><b>'+esc(x.className||'班级')+'</b><small>'+esc(period)+'</small></span><span class="tag">'+esc((x.grade??'—')+'年级')+'</span></div></div>';
  }
  function render(data){
    const e=data.learningEvidence||{},availability=data.evidenceAvailability||{},t=data.transition||{};
    const subjects=(e.subjects||[]).slice(0,4).map(x=>'<div class="row"><span class="row-main"><b>'+esc(x.subject||'未标注学科')+'</b><small>样本 '+esc(x.sampleCount||0)+' · 最近 '+esc((x.latestAt||'').slice(0,10))+'</small></span><span class="tag">观测均分 '+esc(x.averageObservedScore??'—')+'</span></div>').join('');
    const knowledge=(e.knowledge||[]).slice(0,6).map(x=>'<div class="row"><span class="row-main"><b>'+esc(x.knowledgeKey||'知识点')+'</b><small>'+esc(x.subject||'')+' · 样本 '+esc(x.sampleCount||0)+'</small></span><span class="tag">'+(x.observedSuccessRate===null||x.observedSuccessRate===undefined?'正确率 —':'正确率 '+esc(x.observedSuccessRate)+'%')+'</span></div>').join('');
    const available=(availability.availableDimensions||[]).map(x=>'<span class="tag">'+esc(dimName[x]||x)+'</span>').join('');
    const missing=(availability.missingDimensions||[]).map(x=>'<span class="tag">'+esc(dimName[x]||x)+'：尚无记录</span>').join('');
    const history=(data.classHistory||[]).slice(0,8).map(x=>'<div class="row"><span class="row-main"><b>'+esc(x.className||'班级')+'</b><small>'+esc((x.joinedAt||'')+(x.current?' → 至今':(' → '+(x.leftAt||'时间未知'))))+'</small></span><span class="tag">'+esc(x.current?'当前阶段':(x.leaveReasonName||'历史阶段'))+'</span></div>').join('');
    return '<section class="section cy-transition-facts" id="cy-transition-facts"><div class="section-head"><div><h2>真实衔接事实</h2><p>读取同一 student_id 的班级历程与学习证据；只提供事实，不自动诊断或分流。</p></div><span class="tag">'+esc(t.typeCandidate||'阶段衔接')+'</span></div><div class="grid cols-2">'+stageHtml('上一阶段',data.previousStage)+stageHtml('当前阶段',data.currentStage)+'</div><div class="section grid cols-2"><div class="card"><h3>已记录的证据维度</h3><div class="cy-evidence-dims" style="margin-top:10px">'+(available||'<span class="tag">暂无标准化证据</span>')+'</div><h3 style="margin-top:16px">尚未形成记录的维度</h3><div class="cy-evidence-dims" style="margin-top:10px">'+(missing||'<span class="tag">四类证据均已有记录</span>')+'</div><p class="cy-fact-note">'+esc(availability.note||'')+'</p></div><div class="card"><h3>衔接边界</h3><div class="notice">系统不会依据这些数据自动给出升学分流、能力诊断或教学决定。下一步计划仍由教师/家长结合实际情况人工制定。</div><div class="grid cols-2" style="margin-top:12px"><div class="kpi"><span>当前年级</span><strong>'+esc(t.currentGrade??'—')+'</strong></div><div class="kpi"><span>下一年级候选</span><strong>'+esc(t.nextGradeCandidate??'—')+'</strong></div></div></div></div><div class="section grid cols-2"><div class="card"><h3>学科观测</h3><div class="list" style="margin-top:10px">'+(subjects||'<div class="empty">暂无学科证据</div>')+'</div></div><div class="card"><h3>知识点观测</h3><div class="list" style="margin-top:10px">'+(knowledge||'<div class="empty">暂无知识点证据</div>')+'</div></div></div><div class="section card"><h3>阶段历程</h3><div class="cy-transition-history" style="margin-top:10px">'+(history||'<div class="empty">暂无班级历程</div>')+'</div></div></section>';
  }
  async function install(){
    if(location.pathname!='/v1/transition')return;
    if(document.getElementById('cy-transition-facts'))return;
    let sid=new URLSearchParams(location.search).get('id')||'';
    const t=token();if(!t||t==='demo')return;
    if(!sid){
      try{
        const s=await fetch('/session',{headers:{Authorization:'Bearer '+t},cache:'no-store'});
        if(s.ok){const body=await s.json();if(body.role==='student')sid=String(body.userID||'')}
      }catch(_e){}
    }
    if(!sid)return;
    const key=sid+'|'+location.search;if(lastKey===key&&document.getElementById('cy-transition-facts'))return;
    try{
      const r=await fetch('/v1/students/'+encodeURIComponent(sid)+'/transition-snapshot',{headers:{Authorization:'Bearer '+t},cache:'no-store'});
      if(!r.ok)return;
      const data=await r.json();
      const main=document.querySelector('#screen main');if(!main)return;
      main.insertAdjacentHTML('beforeend',render(data));
      lastKey=key;
    }catch(_e){}
  }
  const run=()=>{clearTimeout(timer);timer=setTimeout(install,120)};
  new MutationObserver(run).observe(document.getElementById('screen')||document.body,{childList:true,subtree:true});
  window.addEventListener('popstate',run);
  run();
})();
</script>
'''


def patch_v1_transition_facts_view(html: str) -> str:
    if V1_TRANSITION_FACTS_MARKER in html:
        return html
    if "</body>" not in html:
        raise RuntimeError("V1 transition facts: closing body not found")
    return html.replace("</body>", _SNIPPET + "\n</body>", 1)


def install_v1_transition_facts_view_patch() -> None:
    if getattr(v1_module, "_transition_facts_view_patch_installed", False):
        return
    original = v1_module.v1_html

    def patched_v1_html() -> str:
        return patch_v1_transition_facts_view(original())

    v1_module.v1_html = patched_v1_html
    v1_module._transition_facts_view_patch_installed = True


__all__ = [
    "V1_TRANSITION_FACTS_MARKER",
    "install_v1_transition_facts_view_patch",
    "patch_v1_transition_facts_view",
]
