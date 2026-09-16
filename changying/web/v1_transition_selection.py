"""Make the V1 transition-type chips behave like real selectable controls.

The transition page is still a presentation-only V1 surface: choosing a type
must not pretend that a persisted transition-plan model already exists.  This
patch therefore keeps the selection in sessionStorage, clearly labels that
boundary, and lets the user change the active transition type on mobile.
"""

from __future__ import annotations

from changying.web import v1 as v1_module

V1_TRANSITION_SELECTION_MARKER = "changying_v1_transition_selection_v1"

_TRANSITION_SELECTION_SNIPPET = r'''
<style id="changying_v1_transition_selection_v1-style">
  [data-transition].cy-transition-selected{background:#173c78;color:#fff;border-color:#173c78;box-shadow:0 8px 22px rgba(23,60,120,.18)}
  .cy-transition-choice{margin-top:12px;padding:11px 12px;border-radius:12px;background:#eef6ff;border:1px solid #d4e7ff;color:#285078;font-size:12px;line-height:1.6}
</style>
<script id="changying_v1_transition_selection_v1-script">
(()=>{
  if(window.__cyV1TransitionSelectionInstalled)return;
  window.__cyV1TransitionSelectionInstalled=true;
  const key=()=>`changying.v1.transition.${new URLSearchParams(location.search).get('id')||'general'}`;
  const buttons=()=>[...document.querySelectorAll('[data-transition]')];
  function showChoice(value){
    const list=buttons();if(!list.length)return;
    list.forEach(b=>{const active=b.textContent.trim()===value;b.classList.toggle('cy-transition-selected',active);b.setAttribute('aria-pressed',active?'true':'false')});
    const host=list[0].parentElement;if(!host)return;
    let note=document.getElementById('cy-transition-choice');
    if(!note){note=document.createElement('div');note.id='cy-transition-choice';note.className='cy-transition-choice';host.insertAdjacentElement('afterend',note)}
    const text=value?`已选择：${value}。当前仅保存在本次浏览会话，不写入学生档案；正式衔接计划数据模型将在后续版本单独建立。`:'请选择一个衔接类型。';
    if(note.textContent!==text)note.textContent=text;
  }
  function restore(){const list=buttons();if(!list.length)return;const saved=sessionStorage.getItem(key())||'';showChoice(saved)}
  document.addEventListener('click',e=>{
    const b=e.target.closest('[data-transition]');if(!b)return;
    e.preventDefault();e.stopImmediatePropagation();
    const value=b.textContent.trim();sessionStorage.setItem(key(),value);showChoice(value);
  },true);
  const root=document.getElementById('screen')||document.body;
  const observer=new MutationObserver(()=>restore());
  observer.observe(root,{childList:true});
  restore();
})();
</script>
'''


def patch_v1_transition_selection(html: str) -> str:
    """Add real transition selection without introducing persistence claims."""
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
