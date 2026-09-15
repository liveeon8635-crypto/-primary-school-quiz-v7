"""Small, read-only completion layer for the V1 teaching workspace.

This patch deliberately stays on top of the existing V1 shell and protected
read APIs.  It improves mobile usability, adds client-side filtering for
visible students/history, and turns the transition placeholder into an
explicit eight-step readiness view without creating new production tables or
writing student data.
"""

from __future__ import annotations

from changying.web import v1 as v1_module

V1_COMPLETION_MARKER = "changying_v1_completion_v1"

_COMPLETION_SNIPPET = r'''
<style id="changying_v1_completion_v1-style">
  .cy-cmp-toolbar{display:flex;gap:9px;align-items:center;flex-wrap:wrap;margin:12px 0 14px}
  .cy-cmp-input,.cy-cmp-select{min-height:42px;border:1px solid #d7dfeb;border-radius:12px;background:#fff;padding:9px 11px;color:#172033;min-width:180px}
  .cy-cmp-input{flex:1 1 230px}.cy-cmp-select{flex:0 1 240px}
  .cy-cmp-count{font-size:12px;color:#667085;margin-left:auto}
  .cy-cmp-note{padding:11px 12px;border-radius:12px;background:#fff8e8;border:1px solid #f5d79a;color:#7a4a00;font-size:12px;line-height:1.6;margin-bottom:12px}
  .cy-cmp-steps{display:grid!important;grid-template-columns:repeat(2,minmax(0,1fr))!important;gap:10px!important;margin-top:12px}
  .cy-cmp-step{padding:13px;border:1px solid #e4e9f2;border-radius:13px;background:#fff;min-height:0}
  .cy-cmp-step.done{background:#f0f9f3;border-color:#cfe8d5}.cy-cmp-step.wait{background:#fbfcfe}
  .cy-cmp-step em{font-style:normal;font-size:10px;font-weight:900;color:#2563eb}.cy-cmp-step b{display:block;margin:5px 0 4px}.cy-cmp-step small{color:#667085;line-height:1.5}
  @media(max-width:720px){.cy-cmp-toolbar{display:grid;grid-template-columns:1fr}.cy-cmp-input,.cy-cmp-select{width:100%;min-width:0}.cy-cmp-count{margin-left:0}.cy-cmp-steps{grid-template-columns:1fr!important}}
</style>
<script id="changying_v1_completion_v1-script">
(()=>{
  if(window.__cyV1CompletionInstalled)return;window.__cyV1CompletionInstalled=true;
  const token=()=>localStorage.getItem('v717Token')||localStorage.getItem('v6Token')||'';
  const esc=v=>String(v??'').replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  async function readJson(url){const t=token();if(!t||t==='demo')throw new Error('no-real-session');const r=await fetch(url,{headers:{Authorization:'Bearer '+t}});if(!r.ok)throw new Error('read-failed-'+r.status);return await r.json()}
  function projectText(row){const el=[...row.children].find(x=>x.tagName==='SMALL');return(el?.textContent||'').trim()}
  function studentListFilter(){
    if(location.pathname!='/v1/student'||new URLSearchParams(location.search).get('id')||document.getElementById('cy-cmp-student-filter'))return;
    const screen=document.getElementById('screen');if(!screen)return;const list=screen.querySelector('.list');if(!list)return;
    list.insertAdjacentHTML('beforebegin','<div class="cy-cmp-toolbar" id="cy-cmp-student-filter"><input class="cy-cmp-input" id="cy-cmp-student-q" placeholder="搜索学生、年级或教学归属" autocomplete="off"><span class="cy-cmp-count" id="cy-cmp-student-count"></span></div>');
    const q=document.getElementById('cy-cmp-student-q'),count=document.getElementById('cy-cmp-student-count');
    const apply=()=>{const term=(q.value||'').trim().toLowerCase();const rows=[...list.querySelectorAll('a[data-student]')];let visible=0;rows.forEach(row=>{const ok=!term||row.textContent.toLowerCase().includes(term);row.hidden=!ok;if(ok)visible++});count.textContent=`显示 ${visible}/${rows.length} 名学生`};q.addEventListener('input',apply);apply();
  }
  function historyFilter(){
    if(location.pathname!='/v1/history'||document.getElementById('cy-cmp-history-filter'))return;
    const block=document.getElementById('cy-op-history');if(!block)return;const list=block.querySelector('.cy-op-list');if(!list)return;const rows=[...list.querySelectorAll('a.cy-op-row')];if(!rows.length)return;
    const projects=[...new Set(rows.map(projectText).filter(Boolean))].sort((a,b)=>a.localeCompare(b,'zh-CN'));
    block.querySelector('.section-head')?.insertAdjacentHTML('afterend',`<div id="cy-cmp-history-filter"><div class="cy-cmp-note">当前历史事实还没有标准化的“学年/学期”字段；本轮先对真实可见记录提供学生与教学归属筛选，不伪造学年数据。</div><div class="cy-cmp-toolbar"><input class="cy-cmp-input" id="cy-cmp-history-q" placeholder="搜索学生或教学归属" autocomplete="off"><select class="cy-cmp-select" id="cy-cmp-history-project"><option value="">全部教学归属</option>${projects.map(x=>`<option value="${esc(x)}">${esc(x)}</option>`).join('')}</select><span class="cy-cmp-count" id="cy-cmp-history-count"></span></div></div>`);
    const q=document.getElementById('cy-cmp-history-q'),sel=document.getElementById('cy-cmp-history-project'),count=document.getElementById('cy-cmp-history-count');
    const apply=()=>{const term=(q.value||'').trim().toLowerCase(),project=sel.value;let visible=0;rows.forEach(row=>{const text=row.textContent.toLowerCase(),p=projectText(row);const ok=(!term||text.includes(term))&&(!project||p===project);row.hidden=!ok;if(ok)visible++});count.textContent=`显示 ${visible}/${rows.length} 条学生历史摘要`};q.addEventListener('input',apply);sel.addEventListener('change',apply);apply();
  }
  async function transitionReadiness(){
    if(location.pathname!='/v1/transition'||document.getElementById('cy-cmp-transition-readiness'))return;
    const id=Number(new URLSearchParams(location.search).get('id')||0);if(!id)return;const facts=document.getElementById('cy-op-transition');if(!facts)return;const stepsBox=document.querySelector('.steps');if(!stepsBox)return;
    try{const p=await readJson('/teacher/students/'+id+'/growth-profile'),s=p.student||{},a=p.academic||{},weak=a.weakKnowledge||[],history=p.classHistory||[],suggestions=p.suggestions||[];
      const steps=[
        ['上一阶段状态',`已读取档案 #${esc(s.id||id)}，班级历史 ${history.length} 条。`,true],
        ['下一阶段要求','目标学段要求仍由教师确认，系统不自动替教师决定。',false],
        ['前置知识检查',weak.length?`当前有 ${weak.length} 个需关注知识点。`:'现有记录未识别明确薄弱知识点。',true],
        ['差距识别',a.avgScore!=null?`阶段成绩 ${esc(a.avgScore)}；结合薄弱项继续人工判断。`:'暂无足够成绩事实，继续积累测验和作业记录。',a.avgScore!=null||weak.length>0],
        ['衔接计划',suggestions.length?`已有 ${suggestions.length} 条教学建议可作为计划输入。`:'尚无明确教学建议；当前不生成虚构计划。',suggestions.length>0],
        ['假期干预','可复用寒暑假班与现有作业/测验能力；尚未保存为独立衔接计划。',false],
        ['开学诊断','等待真实开学测验或课堂记录后更新，不预填诊断结果。',false],
        ['进入下一阶段','保持同一 student_id；年级、学校和教学归属不会被此页面自动修改。',true]
      ];
      stepsBox.id='cy-cmp-transition-readiness';stepsBox.classList.add('cy-cmp-steps');stepsBox.innerHTML=steps.map((x,i)=>`<div class="cy-cmp-step ${x[2]?'done':'wait'}"><em>STEP ${String(i+1).padStart(2,'0')}</em><b>${x[0]}</b><small>${x[1]}</small></div>`).join('');
      const head=stepsBox.closest('.section')?.querySelector('.section-head p');if(head)head.textContent='已有事实、教师判断与尚未落表的步骤分开显示。';
      stepsBox.insertAdjacentHTML('afterend','<div class="cy-cmp-note" style="margin-top:12px;margin-bottom:0">绿色只表示“已有事实可读取”，不代表自动诊断完成。计划保存、自动分析和年级变更仍未开放。</div>')
    }catch{}
  }
  let timer=null;function run(){clearTimeout(timer);timer=setTimeout(()=>{studentListFilter();historyFilter();transitionReadiness()},90)}
  new MutationObserver(run).observe(document.getElementById('screen')||document.body,{childList:true,subtree:true});window.addEventListener('popstate',run);run();
})();
</script>
'''


def patch_v1_completion_html(html: str) -> str:
    """Add read-only V1 completion behavior exactly once."""
    if V1_COMPLETION_MARKER in html:
        return html
    if "</body>" not in html:
        raise RuntimeError("V1 completion patch: closing body marker not found")
    return html.replace("</body>", _COMPLETION_SNIPPET + "\n</body>", 1)


def install_v1_completion_patch() -> None:
    """Wrap the currently installed V1 renderer without changing auth or data writes."""
    if getattr(v1_module, "_completion_patch_installed", False):
        return
    original = v1_module.v1_html

    def patched_v1_html() -> str:
        return patch_v1_completion_html(original())

    v1_module.v1_html = patched_v1_html
    v1_module._completion_patch_installed = True


__all__ = ["V1_COMPLETION_MARKER", "install_v1_completion_patch", "patch_v1_completion_html"]
