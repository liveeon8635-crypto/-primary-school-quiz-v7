"""Remove obsolete V1 placeholder panels once real V2 data panels are available.

Demo mode is intentionally left untouched. Real accounts should not see
historical/transition placeholder copy beside the real data-backed modules.
"""

from __future__ import annotations

from changying.web import v1 as v1_module


V28_REAL_WORKSPACE_CLEANUP_MARKER = "changying_v28_real_workspace_cleanup_v1"

_SNIPPET = r'''
<script id="changying_v28_real_workspace_cleanup_v1-script">
(()=>{
  if(window.__cyV28RealWorkspaceCleanupInstalled)return;
  window.__cyV28RealWorkspaceCleanupInstalled=true;
  let timer=null;

  const token=()=>{
    const remember=localStorage.getItem('v717Remember')==='1';
    return (remember?localStorage.getItem('v717Token'):sessionStorage.getItem('v717Token'))
      ||sessionStorage.getItem('v717Token')
      ||localStorage.getItem('v717Token')
      ||sessionStorage.getItem('v6Token')
      ||localStorage.getItem('v6Token')
      ||'';
  };

  const isReal=()=>{
    const t=token();
    return !!t && t!=='demo';
  };

  function removeSectionByHeading(main,text){
    const heading=[...main.querySelectorAll('h2')].find(x=>x.textContent.trim()===text);
    if(!heading)return false;
    const section=heading.closest('section');
    if(section){section.remove();return true}
    return false;
  }

  function cleanHistory(){
    if(location.pathname!='/v1/history'||!isReal())return;
    const main=document.querySelector('#screen main');
    const real=document.getElementById('cy-historical-teaching-section');
    if(!main||!real)return;

    const queryHeading=[...main.querySelectorAll('h2')].find(x=>x.textContent.trim()==='查询层级');
    if(queryHeading){
      const grid=queryHeading.closest('.grid');
      if(grid&&grid!==real)grid.remove();
      else removeSectionByHeading(main,'查询层级');
    }

    const head=main.querySelector('.page-head .tag');
    if(head&&/只读查询|演示/.test(head.textContent||'')){
      head.textContent='真实历史';
      head.classList.remove('demo');
    }
  }

  function transitionEmpty(main){
    if(document.getElementById('cy-transition-real-empty'))return;
    const section=document.createElement('section');
    section.className='section card';
    section.id='cy-transition-real-empty';
    section.innerHTML='<h2>选择学生查看衔接事实</h2><p>请从“学生”进入一名学生的连续档案，再打开“升学衔接”。这里不会使用演示占位数据替代真实学生记录。</p>';
    main.appendChild(section);
  }

  function cleanTransition(){
    if(location.pathname!='/v1/transition'||!isReal())return;
    const main=document.querySelector('#screen main');if(!main)return;
    const sid=new URLSearchParams(location.search).get('id')||'';

    removeSectionByHeading(main,'衔接类型');
    removeSectionByHeading(main,'衔接流程');

    const tag=main.querySelector('.page-head .tag');
    if(tag&&/结构占位|demo|占位/.test(tag.textContent||'')){
      tag.textContent=sid?'连续档案衔接':'请选择学生';
      tag.classList.remove('demo');
    }

    if(!sid){
      transitionEmpty(main);
      return;
    }

    const empty=document.getElementById('cy-transition-real-empty');
    if(empty)empty.remove();
  }

  function runNow(){
    cleanHistory();
    cleanTransition();
  }

  const schedule=()=>{clearTimeout(timer);timer=setTimeout(runNow,160)};
  new MutationObserver(schedule).observe(
    document.getElementById('screen')||document.body,
    {childList:true,subtree:true}
  );
  window.addEventListener('popstate',schedule);
  schedule();
})();
</script>
'''


def patch_v28_real_workspace_cleanup(html: str) -> str:
    if V28_REAL_WORKSPACE_CLEANUP_MARKER in html:
        return html
    if "</body>" not in html:
        raise RuntimeError("V2.8 workspace cleanup: closing body not found")
    return html.replace("</body>", _SNIPPET + "\n</body>", 1)


def install_v28_real_workspace_cleanup_patch() -> None:
    if getattr(v1_module, "_v28_real_workspace_cleanup_installed", False):
        return

    original = v1_module.v1_html

    def patched_v1_html() -> str:
        return patch_v28_real_workspace_cleanup(original())

    v1_module.v1_html = patched_v1_html
    v1_module._v28_real_workspace_cleanup_installed = True


__all__ = [
    "V28_REAL_WORKSPACE_CLEANUP_MARKER",
    "install_v28_real_workspace_cleanup_patch",
    "patch_v28_real_workspace_cleanup",
]
