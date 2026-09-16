"""Make the V1 transition page selectable without inventing persisted plans.

Transition type remains session-only.  The student chooser reuses the existing
read-only V1 roster and returns to the same transition page with a stable
student id in the URL; it never writes student data.
"""

from __future__ import annotations

from changying.web import v1 as v1_module

V1_TRANSITION_SELECTION_MARKER = "changying_v1_transition_selection_v1"

_TRANSITION_SELECTION_SNIPPET = r'''
<style id="changying_v1_transition_selection_v1-style">
  [data-transition].cy-transition-selected{background:#173c78;color:#fff;border-color:#173c78;box-shadow:0 8px 22px rgba(23,60,120,.18)}
  [data-cy-select-student]{cursor:pointer}
  .cy-transition-choice{margin-top:12px;padding:11px 12px;border-radius:12px;background:#eef6ff;border:1px solid #d4e7ff;color:#285078;font-size:12px;line-height:1.6}
  .cy-student-picker-backdrop{position:fixed;inset:0;z-index:120;background:rgba(17,24,39,.42);display:flex;align-items:flex-end;justify-content:center;padding:18px}
  .cy-student-picker{width:min(560px,100%);max-height:min(72dvh,620px);overflow:auto;background:#fff;border-radius:22px;padding:18px;box-shadow:0 24px 70px rgba(17,24,39,.25)}
  .cy-student-picker-head{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:12px}.cy-student-picker-head h2{margin:0;font-size:20px}
  .cy-student-picker-list{display:grid;gap:9px}.cy-student-option{width:100%;text-align:left;border:1px solid #e4e9f2;border-radius:14px;background:#fff;padding:13px;min-height:52px;color:#172033}.cy-student-option b{display:block}.cy-student-option small{display:block;margin-top:4px;color:#667085}
  .cy-student-picker-status{padding:18px;text-align:center;color:#667085;line-height:1.6}
</style>
<script id="changying_v1_transition_selection_v1-script">
(()=>{
  if(window.__cyV1TransitionSelectionInstalled)return;
  window.__cyV1TransitionSelectionInstalled=true;
  const params=()=>new URLSearchParams(location.search);
  const studentId=()=>params().get('id')||'';
  const key=()=>`changying.v1.transition.${studentId()||'general'}`;
  const buttons=()=>[...document.querySelectorAll('[data-transition]')];
  const token=()=>localStorage.getItem('v717Token')||localStorage.getItem('v6Token')||'';
  function showChoice(value){
    const list=buttons();if(!list.length)return;
    list.forEach(b=>{const active=b.textContent.trim()===value;b.classList.toggle('cy-transition-selected',active);b.setAttribute('aria-pressed',active?'true':'false')});
    const host=list[0].parentElement;if(!host)return;
    let note=document.getElementById('cy-transition-choice');
    if(!note){note=document.createElement('div');note.id='cy-transition-choice';note.className='cy-transition-choice';host.insertAdjacentElement('afterend',note)}
    const text=value?`已选择：${value}。当前仅保存在本次浏览会话，不写入学生档案；正式衔接计划数据模型将在后续版本单独建立。`:'请选择一个衔接类型。';
    if(note.textContent!==text)note.textContent=text;
  }
  function restore(){const list=buttons();if(!list.length)return;showChoice(sessionStorage.getItem(key())||'')}
  function normalizeRoster(payload){
    if(Array.isArray(payload))return payload;
    for(const k of ['students','items','roster'])if(Array.isArray(payload?.[k]))return payload[k];
    return [];
  }
  function studentName(s){return s?.name||s?.studentName||s?.student_name||`学生 ${s?.id??s?.studentID??s?.student_id??''}`}
  function studentKey(s){return s?.id??s?.studentID??s?.studentId??s?.student_id??''}
  function studentMeta(s){const grade=s?.grade?`${s.grade}年级`:'';const cls=s?.className||s?.currentClassName||s?.class_name||'';return [grade,cls].filter(Boolean).join(' · ')}
  function closePicker(){document.getElementById('cy-student-picker-backdrop')?.remove()}
  async function openStudentPicker(){
    closePicker();
    const overlay=document.createElement('div');overlay.id='cy-student-picker-backdrop';overlay.className='cy-student-picker-backdrop';
    overlay.innerHTML='<section class="cy-student-picker" role="dialog" aria-modal="true" aria-label="选择学生"><div class="cy-student-picker-head"><h2>选择学生</h2><button class="btn" type="button" data-cy-picker-close>关闭</button></div><div class="cy-student-picker-status" data-cy-picker-status>正在读取学生档案…</div><div class="cy-student-picker-list" data-cy-picker-list></div></section>';
    document.body.appendChild(overlay);
    overlay.addEventListener('click',e=>{if(e.target===overlay||e.target.closest('[data-cy-picker-close]'))closePicker()});
    try{
      const headers=token()?{Authorization:`Bearer ${token()}`}:{ };
      const response=await fetch('/teacher/v1-roster',{headers});
      if(!response.ok)throw new Error(`HTTP ${response.status}`);
      const students=normalizeRoster(await response.json());
      const status=overlay.querySelector('[data-cy-picker-status]'),list=overlay.querySelector('[data-cy-picker-list]');
      if(!students.length){status.textContent='当前没有可选择的学生档案。';return}
      status.remove();
      students.forEach(s=>{const id=studentKey(s);if(id===''||id==null)return;const b=document.createElement('button');b.type='button';b.className='cy-student-option';b.dataset.cyStudentId=String(id);const strong=document.createElement('b');strong.textContent=studentName(s);const small=document.createElement('small');small.textContent=studentMeta(s)||'学生档案';b.append(strong,small);b.addEventListener('click',()=>{const q=new URLSearchParams(location.search);q.set('id',String(id));location.href=`/v1/transition?${q.toString()}`});list.appendChild(b)});
      if(!list.children.length){const empty=document.createElement('div');empty.className='cy-student-picker-status';empty.textContent='学生档案缺少可用编号，暂时无法选择。';list.appendChild(empty)}
    }catch(err){const status=overlay.querySelector('[data-cy-picker-status]');if(status)status.textContent='学生列表读取失败，请关闭后重试。'}
  }
  document.addEventListener('click',e=>{
    const b=e.target.closest('[data-transition]');
    if(b){e.preventDefault();e.stopImmediatePropagation();const value=b.textContent.trim();sessionStorage.setItem(key(),value);showChoice(value);return}
    if(location.pathname==='/v1/transition'){
      const target=e.target.closest('[data-cy-select-student]');
      if(target){e.preventDefault();e.stopImmediatePropagation();openStudentPicker()}
    }
  },true);
  const root=document.getElementById('screen')||document.body;
  const observer=new MutationObserver(()=>restore());
  observer.observe(root,{childList:true});
  restore();
})();
</script>
'''


def patch_v1_transition_selection(html: str) -> str:
    """Add transition selection and a read-only student chooser."""
    if V1_TRANSITION_SELECTION_MARKER in html:
        return html
    if "</body>" not in html:
        raise RuntimeError("V1 transition selection patch: closing body marker not found")
    old = "V1 预留结构，尚未启用自动分析"
    new = "可先选择衔接类型；当前选择仅保存在本次浏览会话，尚未写入学生档案"
    if old in html:
        html = html.replace(old, new, 1)
    return html.replace("</body>", _TRANSITION_SELECTION_SNIPPET + "\n</body>", 1)


def install_v1_transition_selection_patch() -> None:
    if getattr(v1_module, "_transition_selection_patch_installed", False):
        return
    original = v1_module.v1_html

    def patched_v1_html() -> str:
        return patch_v1_transition_selection(original())

    v1_module.v1_html = patched_v1_html
    v1_module._transition_selection_patch_installed = True


__all__ = [
    "V1_TRANSITION_SELECTION_MARKER",
    "install_v1_transition_selection_patch",
    "patch_v1_transition_selection",
]
