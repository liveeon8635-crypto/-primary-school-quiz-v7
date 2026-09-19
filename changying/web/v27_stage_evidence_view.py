"""Presentation-only stage evidence comparison on the V1 transition page."""

from __future__ import annotations

from changying.web import v1 as v1_module


V27_STAGE_EVIDENCE_VIEW_MARKER = "changying_v27_stage_evidence_view_v1"

_SNIPPET = r'''
<style id="changying_v27_stage_evidence_view_v1-style">
  .cy-stage-evidence{margin-top:18px}
  .cy-stage-evidence-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}
  .cy-stage-dims{display:flex;gap:7px;flex-wrap:wrap;margin-top:10px}
  .cy-stage-facts{display:grid;gap:8px;margin-top:12px}
  @media(max-width:720px){.cy-stage-evidence-grid{grid-template-columns:1fr}}
</style>
<script id="changying_v27_stage_evidence_view_v1-script">
(()=>{
  if(window.__cyV27StageEvidenceInstalled)return;
  window.__cyV27StageEvidenceInstalled=true;
  let timer=null,lastKey='';
  const token=()=>{const remember=localStorage.getItem('v717Remember')==='1';return (remember?localStorage.getItem('v717Token'):sessionStorage.getItem('v717Token'))||sessionStorage.getItem('v717Token')||localStorage.getItem('v717Token')||sessionStorage.getItem('v6Token')||localStorage.getItem('v6Token')||''};
  const esc=v=>String(v??'').replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  const dimName={performance:'学习表现',independent:'独立完成',retention:'跨时保持',transfer:'迁移应用'};
  const dimTags=rows=>(rows||[]).map(x=>'<span class="tag">'+esc(dimName[x]||x)+'</span>').join('')||'<span class="tag">暂无标准化证据</span>';
  function stageCard(title,row){
    if(!row)return '<div class="card"><h3>'+esc(title)+'</h3><div class="empty">暂无对应阶段记录</div></div>';
    const s=row.stage||{},e=row.evidence||{};
    const subjects=(e.subjects||[]).slice(0,4).map(x=>'<div class="row"><span class="row-main"><b>'+esc(x.subject||'未标注学科')+'</b><small>样本 '+esc(x.sampleCount||0)+' · 最近 '+esc((x.latestAt||'').slice(0,10))+'</small></span><span class="tag">观测均分 '+esc(x.averageObservedScore??'—')+'</span></div>').join('');
    return '<div class="card"><div class="section-head"><div><h3>'+esc(title)+'</h3><p>'+esc(s.className||'班级')+' · '+esc((s.grade??'—')+'年级')+'</p></div><span class="tag">样本 '+esc(e.sampleCount||0)+'</span></div><div class="cy-stage-dims">'+dimTags(e.dimensions)+'</div><div class="cy-stage-facts">'+(subjects||'<div class="empty">该阶段暂无学科证据</div>')+'</div></div>';
  }
  async function install(){
    if(location.pathname!='/v1/transition')return;
    if(document.getElementById('cy-stage-evidence'))return;
    let sid=new URLSearchParams(location.search).get('id')||'';
    const t=token();if(!t||t==='demo')return;
    if(!sid){
      try{
        const r=await fetch('/session',{headers:{Authorization:'Bearer '+t},cache:'no-store'});
        if(r.ok){const body=await r.json();if(body.role==='student')sid=String(body.userID||'')}
      }catch(_e){}
    }
    if(!sid)return;
    const key=sid+'|'+location.search;
    if(lastKey===key&&document.getElementById('cy-stage-evidence'))return;
    try{
      const r=await fetch('/v2/students/'+encodeURIComponent(sid)+'/stage-evidence-comparison',{headers:{Authorization:'Bearer '+t},cache:'no-store'});
      if(!r.ok)return;
      const data=await r.json(),cmp=data.comparison||{};
      const main=document.querySelector('#screen main');if(!main)return;
      const currentOnly=dimTags(cmp.newlyRecordedDimensions);
      const previousOnly=dimTags(cmp.previousOnlyDimensions);
      const shared=dimTags(cmp.sharedDimensions);
      const section=document.createElement('section');
      section.id='cy-stage-evidence';
      section.className='section cy-stage-evidence';
      section.innerHTML='<div class="section-head"><div><h2>阶段证据对比</h2><p>比较不同班级/年级阶段实际记录到的证据，不自动判断进步、退步或掌握。</p></div></div><div class="cy-stage-evidence-grid">'+stageCard('上一阶段',data.previousStage)+stageCard('当前阶段',data.currentStage)+'</div><div class="section grid cols-2"><div class="card"><h3>记录覆盖变化</h3><p class="muted" style="margin-top:10px">本阶段新增记录维度</p><div class="cy-stage-dims">'+currentOnly+'</div><p class="muted" style="margin-top:14px">上一阶段有、本阶段尚无同类记录</p><div class="cy-stage-dims">'+previousOnly+'</div><p class="muted" style="margin-top:14px">两阶段均有记录</p><div class="cy-stage-dims">'+shared+'</div></div><div class="card"><h3>解释边界</h3><div class="notice">'+esc(cmp.note||'')+'</div><p class="cy-fact-note">未归入明确班级阶段的历史证据：'+esc(cmp.unassignedEvidenceCount||0)+' 条。此数字只反映历史记录完整度。</p></div></div>';
      main.appendChild(section);
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


def patch_v27_stage_evidence_view(html: str) -> str:
    if V27_STAGE_EVIDENCE_VIEW_MARKER in html:
        return html
    if "</body>" not in html:
        raise RuntimeError("V2.7 stage evidence view: closing body not found")
    return html.replace("</body>", _SNIPPET + "\n</body>", 1)


def install_v27_stage_evidence_view_patch() -> None:
    if getattr(v1_module, "_v27_stage_evidence_view_installed", False):
        return
    original = v1_module.v1_html

    def patched_v1_html() -> str:
        return patch_v27_stage_evidence_view(original())

    v1_module.v1_html = patched_v1_html
    v1_module._v27_stage_evidence_view_installed = True


__all__ = [
    "V27_STAGE_EVIDENCE_VIEW_MARKER",
    "install_v27_stage_evidence_view_patch",
    "patch_v27_stage_evidence_view",
]
