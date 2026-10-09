"""Teacher workspace: compact vertical list with a sliding 当前教学 / 全部功能 switch.

The teaching tasks are shown as a single-column list and the full feature list
lives behind a segmented switch on the same page (``?view=all``), so the
sidebar no longer needs a separate "全部功能" entry and the screen stays short.
"""
from __future__ import annotations

import json

from changying.web import v1 as v1_module
from changying.web.v1_tool_hub import TOOL_HUB_MENUS

V1_WORKSPACE_TABS_MARKER = "changying_v1_workspace_tabs_v1"

_SNIPPET = r'''
<style id="changying_v1_workspace_tabs_v1-style">
#cy-ws-tabs{position:relative;display:inline-grid;grid-template-columns:1fr 1fr;padding:4px;margin:0 0 16px;border-radius:14px;background:linear-gradient(180deg,#e7edf6,#eef3f9);box-shadow:inset 0 1px 2px rgba(23,60,120,.14);min-width:260px}
#cy-ws-tabs .cy-ws-thumb{position:absolute;top:4px;bottom:4px;left:4px;width:calc(50% - 4px);border-radius:10px;background:linear-gradient(180deg,#fff,#f4f8ff);box-shadow:0 1px 3px rgba(23,60,120,.18),0 6px 14px rgba(23,60,120,.10),inset 0 1px 0 #fff;transition:transform .22s cubic-bezier(.4,0,.2,1)}
#cy-ws-tabs[data-view="all"] .cy-ws-thumb{transform:translateX(100%)}
#cy-ws-tabs button{position:relative;z-index:1;border:0;background:transparent;padding:9px 18px;font:inherit;font-weight:800;color:#667085;border-radius:10px;cursor:pointer}
#cy-ws-tabs button[aria-selected="true"]{color:#173c78}
main.cy-ws-view-all>*:not(#cy-ws-tabs):not(#cy-ws-all){display:none!important}
main:not(.cy-ws-view-all)>#cy-ws-all{display:none}
.cy-ws-rows{display:flex!important;flex-direction:column;gap:8px}
.cy-ws-rows>.card[data-feature]{display:grid;grid-template-columns:30px minmax(0,1fr) auto;grid-template-areas:"i t r" "i p r";column-gap:12px;align-items:center;padding:12px 16px;min-height:0;border-radius:14px}
.cy-ws-rows>.card[data-feature]>span:first-child{grid-area:i;font-size:20px!important}
.cy-ws-rows>.card[data-feature]>h3{grid-area:t;margin:0!important;font-size:15px}
.cy-ws-rows>.card[data-feature]>p{grid-area:p;margin:2px 0 0!important;font-size:12px;color:#667085}
.cy-ws-rows>.card[data-feature]>*:not(span):not(h3):not(p){grid-area:r;margin:0!important;font-size:12px;white-space:nowrap}
#cy-ws-all .cy-ws-list{display:flex;flex-direction:column;gap:8px}
#cy-ws-all .cy-ws-row{display:grid;grid-template-columns:minmax(0,1fr) auto;align-items:center;column-gap:12px;padding:12px 16px;border:1px solid #e4e9f2;border-radius:14px;background:#fff;color:inherit;text-decoration:none}
#cy-ws-all .cy-ws-row b{font-size:15px}
#cy-ws-all .cy-ws-row small{grid-column:1;color:#667085;font-size:12px;line-height:1.45}
#cy-ws-all .cy-ws-row i{grid-column:2;grid-row:1 / span 2;font-style:normal;color:#9aa6ba;font-size:20px}
#cy-ws-all .cy-ws-row:active{background:#eaf1ff}
@media(max-width:640px){#cy-ws-tabs{display:grid;width:100%}}
@media(prefers-reduced-motion:reduce){#cy-ws-tabs .cy-ws-thumb{transition:none}}
</style>
<script id="changying_v1_workspace_tabs_v1-script">
(()=>{
  if(window.__cyV1WorkspaceTabs)return;window.__cyV1WorkspaceTabs=true;
  const ITEMS=__ITEMS__;
  const esc=v=>String(v??'').replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  const viewFromUrl=()=>new URLSearchParams(location.search).get('view')==='all'?'all':'now';
  function setView(main,view,writeUrl){
    main.classList.toggle('cy-ws-view-all',view==='all');
    const tabs=document.getElementById('cy-ws-tabs');
    if(tabs){tabs.dataset.view=view;tabs.querySelectorAll('button').forEach(b=>b.setAttribute('aria-selected',b.dataset.view===view?'true':'false'))}
    if(writeUrl){const u=new URL(location.href);if(view==='all')u.searchParams.set('view','all');else u.searchParams.delete('view');history.replaceState(null,'',u.pathname+u.search)}
  }
  function mount(){
    if(location.pathname!=='/v1/workspace')return;
    const main=document.querySelector('#screen main');if(!main)return;
    const first=main.querySelector('[data-feature]');if(!first)return;
    first.parentElement.classList.add('cy-ws-rows');
    if(!document.getElementById('cy-ws-tabs')){
      const tabs=document.createElement('div');tabs.id='cy-ws-tabs';tabs.setAttribute('role','tablist');
      tabs.innerHTML='<span class="cy-ws-thumb"></span><button type="button" role="tab" data-view="now">当前教学</button><button type="button" role="tab" data-view="all">全部功能</button>';
      tabs.querySelectorAll('button').forEach(b=>b.onclick=()=>setView(main,b.dataset.view,true));
      const all=document.createElement('section');all.id='cy-ws-all';all.className='section';
      all.innerHTML='<div class="cy-ws-list">'+ITEMS.map(x=>'<a class="cy-ws-row" href="/v1/tool?page='+encodeURIComponent(x[0])+'"><b>'+esc(x[1])+'</b><i>›</i><small>'+esc(x[2])+'</small></a>').join('')+'</div>';
      main.insertBefore(all,main.firstChild);main.insertBefore(tabs,main.firstChild);
    }
    setView(main,viewFromUrl(),false);
  }
  let timer=null;const run=()=>{clearTimeout(timer);timer=setTimeout(mount,60)};
  new MutationObserver(run).observe(document.getElementById('screen')||document.body,{childList:true,subtree:true});
  window.addEventListener('popstate',run);run();
})();
</script>
'''


def patch_v1_workspace_tabs(html: str) -> str:
    if V1_WORKSPACE_TABS_MARKER in html:
        return html
    if "</body>" not in html:
        raise RuntimeError("V1 workspace tabs patch: closing body marker not found")
    items = [list(x) for x in TOOL_HUB_MENUS["teacher"]]
    snippet = _SNIPPET.replace("__ITEMS__", json.dumps(items, ensure_ascii=False))
    return html.replace("</body>", snippet + f"\n<!-- {V1_WORKSPACE_TABS_MARKER} --></body>", 1)


def install_v1_workspace_tabs_patch() -> None:
    if getattr(v1_module, "_workspace_tabs_patch_installed", False):
        return
    original = v1_module.v1_html

    def patched_v1_html() -> str:
        return patch_v1_workspace_tabs(original())

    v1_module.v1_html = patched_v1_html
    v1_module._workspace_tabs_patch_installed = True


__all__ = ["V1_WORKSPACE_TABS_MARKER", "install_v1_workspace_tabs_patch", "patch_v1_workspace_tabs"]
