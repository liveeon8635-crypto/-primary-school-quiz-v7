"""Final mobile polish for V1 student acceptance.

This patch keeps the existing role-aware workflows intact while making account
switching, mobile navigation and student record detail explicit on phones.
It is presentation/read-path only; it does not alter learning evidence.
"""

from __future__ import annotations

from changying.web import v1 as v1_module

V1_STUDENT_MOBILE_POLISH_MARKER = "changying_v1_student_mobile_polish_v1"

_STUDENT_MOBILE_POLISH = r'''
<style id="changying_v1_student_mobile_polish_v1-style">
#cy-v1-account-switch{
  border:1px solid #d5deec;background:#fff;color:#173c78;border-radius:12px;
  padding:9px 11px;font-size:12px;font-weight:850;white-space:nowrap;min-height:40px
}
.cy-mobile-assignment-card{
  display:grid;gap:9px;padding:13px 14px;border:1px solid #e1e7f0;border-radius:15px;
  background:#fff;text-align:left
}
.cy-mobile-assignment-head{display:flex;align-items:flex-start;justify-content:space-between;gap:10px}
.cy-mobile-assignment-head b{font-size:14px;line-height:1.45}
.cy-mobile-assignment-status{flex:none;display:inline-flex;padding:5px 8px;border-radius:999px;background:#f1f5f9;color:#526178;font-size:11px;font-weight:850}
.cy-mobile-assignment-status.is-done{background:#ecfdf3;color:#166534}
.cy-mobile-assignment-status.is-overdue{background:#fff1f1;color:#991b1b}
.cy-mobile-assignment-meta{display:flex;gap:6px;flex-wrap:wrap}
.cy-mobile-assignment-meta span{display:inline-flex;padding:4px 7px;border:1px solid #e2e8f0;border-radius:999px;background:#f8fafc;color:#526178;font-size:11px}
.cy-mobile-assignment-detail{display:grid;gap:4px;color:#667085;font-size:12px;line-height:1.55}
.cy-mobile-assignment-detail b{color:#344054}
.cy-mobile-timeline-detail{display:grid;gap:4px}
@media(max-width:720px){
  .top{padding:0 10px!important;gap:7px!important}
  .top-actions{gap:6px!important;min-width:0}
  .identity-chip{max-width:112px!important;padding:7px 8px!important;font-size:11px!important}
  #cy-v1-account-switch{padding:7px 9px;font-size:11px;min-height:36px}
  main{padding-bottom:calc(104px + env(safe-area-inset-bottom))!important}
  .bottom{
    left:0!important;right:0!important;bottom:0!important;border-radius:18px 18px 0 0!important;
    border-left:0!important;border-right:0!important;border-bottom:0!important;
    padding:6px 8px calc(7px + env(safe-area-inset-bottom))!important;
    box-shadow:0 -8px 28px rgba(23,60,120,.10)!important;background:rgba(255,255,255,.98)!important
  }
  .bottom a{position:relative;min-height:50px;display:flex!important;flex-direction:column;align-items:center;justify-content:center;
    gap:2px;font-size:11px!important;padding:6px 2px!important;border-radius:10px!important}
  .bottom a span{font-size:18px!important;line-height:1;margin:0!important}
  .bottom a.active{background:transparent!important;color:var(--navy)!important;font-weight:900}
  .bottom a.active:before{content:"";position:absolute;top:-6px;left:28%;right:28%;height:3px;border-radius:0 0 999px 999px;background:var(--navy)}
  #assignments{overflow:visible!important}
}
</style>
<script id="changying_v1_student_mobile_polish_v1-script">
(()=>{
  if(window.__cyV1StudentMobilePolishInstalled)return;window.__cyV1StudentMobilePolishInstalled=true;
  const token=()=>{const remember=localStorage.getItem('v717Remember')==='1';return (remember?localStorage.getItem('v717Token'):sessionStorage.getItem('v717Token'))||sessionStorage.getItem('v717Token')||localStorage.getItem('v717Token')||sessionStorage.getItem('v6Token')||localStorage.getItem('v6Token')||''};
  const esc=v=>String(v??'').replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  const assignmentType=x=>{const title=String(x?.title||'');if(title.includes('AI')||title.includes('针对性'))return 'AI 针对性练习';if(title.includes('综合测试'))return '综合测试';if(title.includes('专项')||title.includes('模块'))return '知识模块练习';return x?.submissionModeName||'学习任务'};
  function switchAccount(){
    if(!confirm('切换账号会退出当前登录，但不会删除任何学习记录。确定继续吗？'))return;
    ['v717Token','v717User','v717Remember','v6Token','v6User','cyV1Identity'].forEach(k=>{try{localStorage.removeItem(k)}catch(_e){}try{sessionStorage.removeItem(k)}catch(_e){}});
    location.replace('/v1');
  }
  function mountAccountSwitch(){
    const actions=document.querySelector('.top-actions');if(!actions||document.getElementById('cy-v1-account-switch')||!token())return;
    const btn=document.createElement('button');btn.type='button';btn.id='cy-v1-account-switch';btn.textContent='切换账号';btn.onclick=switchAccount;actions.appendChild(btn);
  }
  async function api(path){
    const t=token();if(!t||t==='demo')return null;
    const r=await fetch(path,{headers:{Authorization:'Bearer '+t},cache:'no-store'});if(!r.ok)return null;return await r.json();
  }
  function renderAssignments(rows){
    const box=document.getElementById('assignments');if(!box||!Array.isArray(rows))return;
    if(!rows.length){box.innerHTML='<div class="empty">暂无作业记录</div>';return}
    box.innerHTML=rows.map(x=>{
      const paper=x.paper||{},subject=x.subject||paper.subject||'',textbook=x.textbook||paper.textbook||'',unit=x.unit||paper.unit||'';
      const qn=Number(x.questionCount??(paper.questionIDs||[]).length||0),status=x.status||((x.completed)?'已完成':'待完成');
      const statusClass=x.completed?' is-done':(x.overdue?' is-overdue':'');
      const assigned=x.assignedAt||x.createdAt||'',submitted=x.submittedAt||x.quizSubmittedAt||x.mediaSubmittedAt||'';
      const meta=[subject,textbook,assignmentType(x)].filter(Boolean);
      const details=[];
      if(assigned)details.push('<span><b>布置：</b>'+esc(assigned)+'</span>');
      if(x.dueDate)details.push('<span><b>截止：</b>'+esc(x.dueDate)+'</span>');
      if(submitted)details.push('<span><b>提交：</b>'+esc(submitted)+'</span>');
      if(x.assignedClassName)details.push('<span><b>班级：</b>'+esc(x.assignedClassName)+'</span>');
      if(qn)details.push('<span><b>题量：</b>'+qn+' 题</span>');
      if(x.score!==null&&x.score!==undefined)details.push('<span><b>成绩：</b>'+esc(x.score)+' 分</span>');
      if(unit)details.push('<span><b>内容：</b>'+esc(unit)+'</span>');
      if(x.instructions)details.push('<span><b>要求：</b>'+esc(x.instructions)+'</span>');
      return '<div class="cy-mobile-assignment-card"><div class="cy-mobile-assignment-head"><b>'+esc(x.title||'作业')+'</b><span class="cy-mobile-assignment-status'+statusClass+'">'+esc(status)+'</span></div><div class="cy-mobile-assignment-meta">'+meta.map(v=>'<span>'+esc(v)+'</span>').join('')+'</div><div class="cy-mobile-assignment-detail">'+details.join('')+'</div></div>';
    }).join('');
  }
  function renderTimeline(rows){
    const box=document.getElementById('timeline');if(!box||!Array.isArray(rows)||box.dataset.cyStudentTimeline==='1')return;
    const events=rows.map(x=>{
      const paper=x.paper||{},subject=x.subject||paper.subject||'',textbook=x.textbook||paper.textbook||'',qn=Number(x.questionCount??(paper.questionIDs||[]).length||0);
      const done=!!x.completed,time=(done?(x.submittedAt||x.quizSubmittedAt||x.mediaSubmittedAt):(x.assignedAt||x.createdAt||x.dueDate))||'';
      const parts=[subject,textbook,assignmentType(x),qn?qn+'题':'',x.status||'',x.score!==null&&x.score!==undefined?x.score+'分':''].filter(Boolean);
      return {time,title:done?'完成：'+(x.title||'学习任务'):'布置：'+(x.title||'学习任务'),detail:parts.join(' · ')};
    });
    if(!events.length)return;
    box.dataset.cyStudentTimeline='1';
    box.innerHTML=events.map(e=>'<div class="event"><time>'+esc(e.time)+'</time><b>'+esc(e.title)+'</b><p class="cy-mobile-timeline-detail">'+esc(e.detail)+'</p></div>').join('');
  }
  let loading=false;
  async function enhance(){
    mountAccountSwitch();
    if(loading||!location.pathname.includes('/v1/student')||!document.getElementById('assignments'))return;
    loading=true;
    try{const s=await api('/session');if(!s||s.role!=='student')return;const rows=await api('/student/assignments');if(Array.isArray(rows)){renderAssignments(rows);renderTimeline(rows)}}catch(_e){}finally{loading=false}
  }
  const observer=new MutationObserver(()=>{mountAccountSwitch();enhance()});observer.observe(document.documentElement,{subtree:true,childList:true});
  window.addEventListener('popstate',enhance);setTimeout(enhance,0);setTimeout(enhance,500);
})();
</script>
'''


def patch_v1_student_mobile_polish(html: str) -> str:
    if V1_STUDENT_MOBILE_POLISH_MARKER in html:
        return html
    if "</body>" not in html:
        raise RuntimeError("V1 student mobile polish: closing body marker not found")
    return html.replace(
        "</body>",
        _STUDENT_MOBILE_POLISH + f"\n<!-- {V1_STUDENT_MOBILE_POLISH_MARKER} -->\n</body>",
        1,
    )


def install_v1_student_mobile_polish_patch() -> None:
    if getattr(v1_module, "_student_mobile_polish_patch_installed", False):
        return
    original = v1_module.v1_html

    def patched_v1_html() -> str:
        return patch_v1_student_mobile_polish(original())

    v1_module.v1_html = patched_v1_html
    v1_module._student_mobile_polish_patch_installed = True


__all__ = [
    "V1_STUDENT_MOBILE_POLISH_MARKER",
    "install_v1_student_mobile_polish_patch",
    "patch_v1_student_mobile_polish",
]
