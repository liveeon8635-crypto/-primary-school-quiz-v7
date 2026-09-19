"""Read-only V2.2 class evidence coverage on the V1 student list."""

from __future__ import annotations

from changying.web import v1 as v1_module


V22_EVIDENCE_COVERAGE_MARKER = "changying_v22_evidence_coverage_v1"

_SNIPPET = r'''
<style id="changying_v22_evidence_coverage_v1-style">
  .cy-coverage{margin-top:18px}.cy-coverage-controls{display:grid;grid-template-columns:1fr 180px;gap:10px;margin:12px 0}
  .cy-coverage-summary{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin:12px 0}
  .cy-coverage-row{display:flex;justify-content:space-between;gap:12px;align-items:flex-start}
  .cy-coverage-dims{display:flex;gap:6px;flex-wrap:wrap;margin-top:6px}
  .cy-coverage-missing{font-size:12px;color:#667085;margin-top:6px}
  .cy-coverage-actions{display:flex;gap:6px;flex-wrap:wrap;justify-content:flex-end;align-items:center;max-width:340px}
  .cy-coverage-actions small{color:#667085;max-width:180px;text-align:right}
  @media(max-width:720px){.cy-coverage-controls,.cy-coverage-summary{grid-template-columns:1fr}.cy-coverage-row{flex-direction:column}.cy-coverage-actions{justify-content:flex-start;max-width:none}.cy-coverage-actions small{text-align:left;max-width:none}}
</style>
<script id="changying_v22_evidence_coverage_v1-script">
(()=>{
  if(window.__cyV22EvidenceCoverageInstalled)return;
  window.__cyV22EvidenceCoverageInstalled=true;
  let timer=null,lastKey='';
  const token=()=>{const remember=localStorage.getItem('v717Remember')==='1';return (remember?localStorage.getItem('v717Token'):sessionStorage.getItem('v717Token'))||sessionStorage.getItem('v717Token')||localStorage.getItem('v717Token')||sessionStorage.getItem('v6Token')||localStorage.getItem('v6Token')||''};
  const esc=v=>String(v??'').replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  const dimName={performance:'学习表现',independent:'独立完成',retention:'跨时保持',transfer:'迁移应用'};
  function rowHtml(x){
    const dims=(x.availableDimensions||[]).map(d=>'<span class="tag">'+esc(dimName[d]||d)+'</span>').join('');
    const missingDims=x.missingDimensions||[],missing=missingDims.map(d=>dimName[d]||d).join('、');
    const classes=(x.classNames||[]).join(' / ')||'未标注班级';
    const latest=x.latestEvidenceAt?('最近记录 '+x.latestEvidenceAt):'暂无标准化证据记录';
    const sid=encodeURIComponent(x.studentID);
    const manual=missingDims.filter(d=>['independent','retention','transfer'].includes(d));
    const manualLinks=manual.map(d=>'<a class="btn secondary" href="/v1/student?id='+sid+'&focus=evidence&evidenceType='+encodeURIComponent(d)+'">记录'+esc(dimName[d]||d)+'</a>').join('');
    const performanceNote=missingDims.includes('performance')?'<small>学习表现：等待作业/测验自动形成</small>':'';
    return '<div class="row cy-coverage-row"><span class="row-main"><b>'+esc(x.studentName||'学生')+'</b><small>'+esc(classes)+' · '+esc(latest)+' · 来源事件 '+esc(x.sourceEventCount||0)+'</small><span class="cy-coverage-dims">'+(dims||'<span class="tag">暂无维度</span>')+'</span><span class="cy-coverage-missing">'+(missing?'待补充记录：'+esc(missing):'四类证据维度均已有记录')+'</span></span><span class="cy-coverage-actions"><a class="btn secondary" href="/v1/student?id='+sid+'">打开连续档案</a>'+manualLinks+performanceNote+'</span></div>';
  }
  function draw(section,data){
    const q=(section.querySelector('#cyCoverageQ')?.value||'').trim().toLowerCase();
    const cid=section.querySelector('#cyCoverageClass')?.value||'';
    const rows=(data.students||[]).filter(x=>{
      if(cid&&!((x.classIDs||[]).map(String).includes(cid)))return false;
      if(!q)return true;
      const hay=[x.studentName||'',...(x.classNames||[]),...((x.availableDimensions||[]).map(d=>dimName[d]||d)),...((x.missingDimensions||[]).map(d=>dimName[d]||d))].join(' ').toLowerCase();
      return hay.includes(q);
    });
    section.querySelector('#cyCoverageList').innerHTML=rows.map(rowHtml).join('')||'<div class="empty">没有匹配的学生记录。</div>';
    section.querySelector('#cyCoverageVisibleCount').textContent=rows.length+' 名学生';
  }
  async function install(){
    if(location.pathname!='/v1/student')return;
    if(new URLSearchParams(location.search).get('id'))return;
    if(document.getElementById('cy-evidence-coverage'))return;
    const t=token();if(!t||t==='demo')return;
    let session;
    try{
      const sr=await fetch('/session',{headers:{Authorization:'Bearer '+t},cache:'no-store'});
      if(!sr.ok)return;session=await sr.json();
    }catch(_){return}
    if(!['teacher','admin'].includes(session.role))return;
    let data;
    try{
      const r=await fetch('/v2/teacher/evidence-coverage',{headers:{Authorization:'Bearer '+t},cache:'no-store'});
      if(!r.ok)return;data=await r.json();
    }catch(_){return}
    const main=document.querySelector('#screen main');if(!main)return;
    const section=document.createElement('section');
    section.id='cy-evidence-coverage';
    section.className='section cy-coverage';
    const summary=data.summary||{};
    section.innerHTML='<div class="section-head"><div><h2>班级学习证据覆盖</h2><p>只看“系统已经记录了什么”，不做能力排名或自动诊断。</p></div><span class="tag" id="cyCoverageVisibleCount"></span></div><div class="notice">'+esc(data.boundary||'')+'</div><div class="cy-coverage-summary"><div class="card kpi"><span>当前学生</span><strong>'+esc(summary.studentCount||0)+'</strong></div><div class="card kpi"><span>四维均有记录</span><strong>'+esc(summary.allDimensionsRecordedCount||0)+'</strong><small>仅代表记录覆盖</small></div><div class="card kpi"><span>暂无标准化记录</span><strong>'+esc(summary.noEvidenceRecordedCount||0)+'</strong><small>不等于能力不足</small></div></div><div class="card"><div class="cy-coverage-controls"><input id="cyCoverageQ" placeholder="搜索学生、班级或证据维度"><select id="cyCoverageClass"><option value="">全部可见班级</option>'+((data.classes||[]).map(x=>'<option value="'+esc(x.id)+'">'+esc(x.name)+' · '+esc(x.grade)+'年级</option>').join(''))+'</select></div><div id="cyCoverageList" class="list"></div></div>';
    main.appendChild(section);
    section.querySelector('#cyCoverageQ').addEventListener('input',()=>draw(section,data));
    section.querySelector('#cyCoverageClass').addEventListener('change',()=>draw(section,data));
    draw(section,data);
    lastKey=location.pathname+location.search;
  }
  const run=()=>{clearTimeout(timer);timer=setTimeout(install,120)};
  new MutationObserver(run).observe(document.getElementById('screen')||document.body,{childList:true,subtree:true});
  window.addEventListener('popstate',run);
  run();
})();
</script>
'''


def patch_v22_evidence_coverage_view(html: str) -> str:
    if V22_EVIDENCE_COVERAGE_MARKER in html:
        return html
    if "</body>" not in html:
        raise RuntimeError("V2.2 evidence coverage: closing body not found")
    return html.replace("</body>", _SNIPPET + "\n</body>", 1)


def install_v22_evidence_coverage_view_patch() -> None:
    if getattr(v1_module, "_v22_evidence_coverage_view_installed", False):
        return
    original = v1_module.v1_html

    def patched_v1_html() -> str:
        return patch_v22_evidence_coverage_view(original())

    v1_module.v1_html = patched_v1_html
    v1_module._v22_evidence_coverage_view_installed = True


__all__ = [
    "V22_EVIDENCE_COVERAGE_MARKER",
    "install_v22_evidence_coverage_view_patch",
    "patch_v22_evidence_coverage_view",
]
