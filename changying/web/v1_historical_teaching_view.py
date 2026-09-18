"""Presentation-only historical teaching query on the V1 history page."""

from __future__ import annotations

from changying.web import v1 as v1_module


V1_HISTORICAL_TEACHING_VIEW_MARKER = "changying_v1_historical_teaching_view_v1"

_SNIPPET = r'''
<style id="changying_v1_historical_teaching_view_v1-style">
  .cy-history-query{margin-top:18px}.cy-history-controls{display:grid;grid-template-columns:1fr 180px;gap:10px;margin:12px 0}
  .cy-history-student{border:1px solid #e4e9f2;border-radius:14px;background:#fff;padding:0 14px}
  .cy-history-student summary{cursor:pointer;list-style:none;padding:14px 0;display:flex;justify-content:space-between;gap:12px;align-items:center}
  .cy-history-student summary::-webkit-details-marker{display:none}.cy-history-records{border-top:1px solid #eef1f6;padding:10px 0 14px;display:grid;gap:8px}
  .cy-history-record{display:flex;justify-content:space-between;gap:12px;padding:9px 0}.cy-history-record small{display:block;color:#667085;margin-top:3px}
  @media(max-width:720px){.cy-history-controls{grid-template-columns:1fr}.cy-history-record{align-items:flex-start;flex-direction:column}}
</style>
<script id="changying_v1_historical_teaching_view_v1-script">
(()=>{
  if(window.__cyV1HistoricalTeachingViewInstalled)return;
  window.__cyV1HistoricalTeachingViewInstalled=true;
  let cached=null,loading=false,timer=null;
  const token=()=>{const remember=localStorage.getItem('v717Remember')==='1';return (remember?localStorage.getItem('v717Token'):sessionStorage.getItem('v717Token'))||sessionStorage.getItem('v717Token')||localStorage.getItem('v717Token')||sessionStorage.getItem('v6Token')||localStorage.getItem('v6Token')||''};
  const esc=v=>String(v??'').replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  async function load(){
    if(cached)return cached;
    if(loading)return null;
    const t=token();if(!t||t==='demo')return null;
    loading=true;
    try{
      const r=await fetch('/v1/teacher/history/students',{headers:{Authorization:'Bearer '+t},cache:'no-store'});
      if(!r.ok)return null;
      cached=await r.json();
      return cached;
    }catch(_e){return null}finally{loading=false}
  }
  function scoreText(v){return v===null||v===undefined?'—':esc(v)+'分'}
  function recordHtml(x){
    const meta=[x.className||'',x.subject||'',x.unit||'',x.assignedAt||''].filter(Boolean).join(' · ');
    const result=x.submitted?('已提交 · '+scoreText(x.score)):'历史接收快照 · 未记录提交';
    return '<div class="cy-history-record"><div><b>'+esc(x.title||'历史教学任务')+'</b><small>'+esc(meta)+'</small></div><span class="tag">'+esc(result)+'</span></div>';
  }
  function studentHtml(x){
    const meta=[(x.classes||[]).join(' / '),(x.subjects||[]).join(' / '),x.lastAssignedAt||''].filter(Boolean).join(' · ');
    return '<details class="cy-history-student"><summary><span class="row-main"><b>'+esc(x.studentName||'学生')+'</b><small>'+esc(meta)+'</small></span><span class="tag">'+esc(x.assignmentCount||0)+' 项历史任务</span></summary><div class="cy-history-records">'+((x.records||[]).map(recordHtml).join('')||'<div class="empty">暂无历史教学记录</div>')+'</div></details>';
  }
  function draw(section,data){
    const q=(section.querySelector('#cyHistoryQ')?.value||'').trim().toLowerCase();
    const subject=section.querySelector('#cyHistorySubject')?.value||'';
    const rows=(data.students||[]).filter(x=>{
      if(subject&&!(x.subjects||[]).includes(subject))return false;
      if(!q)return true;
      const hay=[x.studentName||'',...(x.classes||[]),...(x.subjects||[]),...((x.records||[]).map(r=>r.title||''))].join(' ').toLowerCase();
      return hay.includes(q);
    });
    const list=section.querySelector('#cyHistoryList');
    list.innerHTML=rows.map(studentHtml).join('')||'<div class="empty">没有匹配的历史教学记录。</div>';
    section.querySelector('#cyHistoryCount').textContent=rows.length+' 名学生';
  }
  async function install(){
    if(location.pathname!='/v1/history')return;
    if(document.getElementById('cy-historical-teaching-section'))return;
    const data=await load();if(!data)return;
    const main=document.querySelector('#screen main');if(!main)return;
    const subjects=[...new Set((data.students||[]).flatMap(x=>x.subjects||[]))].filter(Boolean).sort();
    const section=document.createElement('section');
    section.className='section cy-history-query';
    section.id='cy-historical-teaching-section';
    section.innerHTML='<div class="section-head"><div><h2>真实历史教学记录</h2><p>只显示当前教师当时实际布置并形成接收快照的任务；不包含学生离班后的新档案内容。</p></div><span class="tag" id="cyHistoryCount"></span></div><div class="card"><div class="cy-history-controls"><input id="cyHistoryQ" placeholder="搜索学生、班级、学科或历史任务"><select id="cyHistorySubject"><option value="">全部学科</option>'+subjects.map(x=>'<option value="'+esc(x)+'">'+esc(x)+'</option>').join('')+'</select></div><div class="notice">权限依据：本教师拥有的试卷/任务 + 当时的 AssignmentRecipient 快照。学生换班后仍可查询这些既有教学事实，但不会获得其后续新档案。</div><div class="list" id="cyHistoryList" style="margin-top:12px"></div></div>';
    main.appendChild(section);
    section.querySelector('#cyHistoryQ').addEventListener('input',()=>draw(section,data));
    section.querySelector('#cyHistorySubject').addEventListener('change',()=>draw(section,data));
    draw(section,data);
  }
  const run=()=>{clearTimeout(timer);timer=setTimeout(install,120)};
  new MutationObserver(run).observe(document.getElementById('screen')||document.body,{childList:true,subtree:true});
  window.addEventListener('popstate',run);
  run();
})();
</script>
'''


def patch_v1_historical_teaching_view(html: str) -> str:
    if V1_HISTORICAL_TEACHING_VIEW_MARKER in html:
        return html
    if "</body>" not in html:
        raise RuntimeError("V1 historical teaching view: closing body not found")
    return html.replace("</body>", _SNIPPET + "\n</body>", 1)


def install_v1_historical_teaching_view_patch() -> None:
    if getattr(v1_module, "_historical_teaching_view_patch_installed", False):
        return
    original = v1_module.v1_html

    def patched_v1_html() -> str:
        return patch_v1_historical_teaching_view(original())

    v1_module.v1_html = patched_v1_html
    v1_module._historical_teaching_view_patch_installed = True


__all__ = [
    "V1_HISTORICAL_TEACHING_VIEW_MARKER",
    "install_v1_historical_teaching_view_patch",
    "patch_v1_historical_teaching_view",
]
