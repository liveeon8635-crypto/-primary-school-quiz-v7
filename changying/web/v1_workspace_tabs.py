"""Teacher workspace: compact vertical list plus the 全部功能 view.

The sidebar is gone; ``shell()`` in ``v1.py`` renders one sliding capsule with
the 当前教学 / 全部功能 segments. This patch turns the teaching tasks into a single-column
list and adds the 全部功能 view (``/v1/workspace?view=all``) that the capsule's
last segment switches to without re-rendering the page.
"""
from __future__ import annotations

import json

from changying.web import v1 as v1_module
from changying.web.v1_tool_hub import TOOL_HUB_MENUS

V1_WORKSPACE_TABS_MARKER = "changying_v1_workspace_tabs_v1"

# V1 pages that used to be separate sidebar entries. 学生 belongs to the current
# teaching cycle (it is also reachable from 当前学生 · 查看全部); 往期教学 and 升学衔接
# are cross-cycle records, so they live under 全部功能.
WORKSPACE_RECORD_LINKS: list[tuple[str, str, str]] = [
    ("/v1/student", "学生", "当前学生与每人的长期档案"),
    ("/v1/history", "往期教学", "已结束教学周期的历史记录"),
    ("/v1/transition", "升学衔接", "升年级与升学阶段衔接"),
]

_SNIPPET = r'''
<style id="changying_v1_workspace_tabs_v1-style">
main.cy-ws-view-all>*:not(#cy-ws-all){display:none!important}
main.cy-ws-page .page-head .subtitle,main.cy-ws-page .section-head p{display:none!important}
main.cy-ws-page:has(#cy-cycle-empty) #cy-op-workbench{display:none!important}
main:not(.cy-ws-view-all)>#cy-ws-all{display:none}
.cy-ws-rows{display:flex!important;flex-direction:column;gap:8px}
.cy-ws-rows>.card[data-feature]{display:grid;grid-template-columns:30px minmax(0,1fr) auto;grid-template-areas:"i t r" "i p r";column-gap:12px;align-items:center;padding:12px 16px;min-height:0;border-radius:14px}
.cy-ws-rows>.card[data-feature]>span:first-child{grid-area:i;font-size:20px!important}
.cy-ws-rows>.card[data-feature]>h3{grid-area:t;margin:0!important;font-size:15px}
.cy-ws-rows>.card[data-feature]>p{grid-area:p;margin:2px 0 0!important;font-size:12px;color:#7a625c}
.cy-ws-rows>.card[data-feature]>*:not(span):not(h3):not(p){grid-area:r;margin:0!important;font-size:12px;white-space:nowrap}
#cy-ws-all .cy-ws-h{margin:14px 2px 8px;font-size:13px;color:#7a625c;font-weight:800}
#cy-ws-all .cy-ws-list{display:flex;flex-direction:column;gap:8px}
#cy-ws-all .cy-ws-row{display:grid;grid-template-columns:minmax(0,1fr) auto;align-items:center;column-gap:12px;padding:12px 16px;border:1px solid #eadfd8;border-radius:14px;background:#fff;color:inherit;text-decoration:none}
#cy-ws-all .cy-ws-row b{font-size:15px}
#cy-ws-all .cy-ws-row small{grid-column:1;color:#7a625c;font-size:12px;line-height:1.45}
#cy-ws-all .cy-ws-row i{grid-column:2;grid-row:1 / span 2;font-style:normal;color:#c9a39b;font-size:20px}
#cy-ws-all .cy-ws-row:active{background:#fdebe7}
#cy-ws-all .cy-ws-row[hidden]{display:none}
</style>
<script id="changying_v1_workspace_tabs_v1-script">
(()=>{
  if(window.__cyV1WorkspaceTabs)return;window.__cyV1WorkspaceTabs=true;
  const ITEMS=__ITEMS__;
  const RECORDS=__RECORDS__;
  const esc=v=>String(v??'').replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  const viewFromUrl=()=>new URLSearchParams(location.search).get('view')==='all'?'all':'now';
  function setView(main,view,writeUrl){
    main.classList.toggle('cy-ws-view-all',view==='all');
    const seg=document.getElementById('cy-seg');
    if(seg){
      const links=[...seg.querySelectorAll('a[data-seg]')];
      const target=view==='all'?'tools':'workspace';
      links.forEach((a,i)=>{const on=a.dataset.seg===target;a.classList.toggle('active',on);if(on)seg.style.setProperty('--i',i)});
    }
    if(writeUrl){const u=new URL(location.href);if(view==='all')u.searchParams.set('view','all');else u.searchParams.delete('view');history.replaceState(null,'',u.pathname+u.search)}
  }
  function mount(){
    if(location.pathname!=='/v1/workspace')return;
    const main=document.querySelector('#screen main');if(!main)return;
    const first=main.querySelector('[data-feature]');
    if(!first&&!main.querySelector('#termSelect'))return;
    main.classList.add('cy-ws-page');
    if(first)first.parentElement.classList.add('cy-ws-rows');
    if(!document.getElementById('cy-ws-all')){
      const all=document.createElement('section');all.id='cy-ws-all';all.className='section';
      const recRows=RECORDS.map(x=>'<a class="cy-ws-row" data-nav href="'+esc(x[0])+'"><b>'+esc(x[1])+'</b><i>›</i><small>'+esc(x[2])+'</small></a>').join('');
      all.innerHTML='<h3 class="cy-ws-h">档案与衔接</h3><div class="cy-ws-list">'+recRows+'</div><h3 class="cy-ws-h">教学功能</h3><div class="cy-ws-list">'+ITEMS.map(x=>'<a class="cy-ws-row" href="/v1/tool?page='+encodeURIComponent(x[0])+'"><b>'+esc(x[1])+'</b><i>›</i><small>'+esc(x[2])+'</small></a>').join('')+'</div>';
      const paperRow=all.querySelector('a.cy-ws-row[href$="page=papers"]');
      if(paperRow){
        const hw=document.createElement('a');hw.className='cy-ws-row';hw.href='/v1/homework';hw.hidden=true;hw.setAttribute('data-homework-entry','1');
        hw.innerHTML='<b>晚托作业助手</b><i>›</i><small>粘贴或拍照家长转发的作业通知，AI 整理成清单后布置给学生；查看学生的求助</small>';
        paperRow.after(hw);
        // Only shown while the feature is switched on (the config endpoint answers 404 otherwise).
        fetch('/homework/config',{cache:'no-store'}).then(r=>{if(r.ok)hw.hidden=false}).catch(()=>{});
        const wk=document.createElement('a');wk.className='cy-ws-row';wk.href='/v1/weekend';
        wk.innerHTML='<b>周末课</b><i>›</i><small>备课、上课、下课结算都从这里开始：按步骤告诉你下一次课准备到哪一步</small>';
        paperRow.after(wk);
        const curRole=(()=>{try{const raw=sessionStorage.getItem('v717User')||localStorage.getItem('v717User')||sessionStorage.getItem('v6User')||localStorage.getItem('v6User');return raw?String((JSON.parse(raw)||{}).role||''):''}catch{return ''}})();
        const ma=document.createElement('a');ma.className='cy-ws-row';ma.href='/v1/math-star-map';ma.setAttribute('data-math-arena-entry','1');
        ma.innerHTML=curRole==='student'
          ?'<b>数学知识地图与应试专项</b><i>›</i><small>点亮 24 个数学核心考点，挑战多题型限时专项赢全站积分</small>'
          :'<b>数学知识地图与应试专项</b><i>›</i><small>查看全班 24 考点点亮进度、限时专项分级段位与全站学习积分</small>';
        wk.after(ma);
        const ea=document.createElement('a');ea.className='cy-ws-row';ea.href='/v1/english-star-map';ea.setAttribute('data-english-arena-entry','1');
        ea.innerHTML=curRole==='student'
          ?'<b>英语知识地图与听说读写专项</b><i>›</i><small>点亮 16 个英语核心考点，练习听力、发音、单词与句子填空</small>'
          :'<b>英语知识地图与听说读写专项</b><i>›</i><small>查看全班 16 英语考点点亮进度、听说读写专项分级段位与学习积分</small>';
        ma.after(ea);
        const ca=document.createElement('a');ca.className='cy-ws-row';ca.href='/v1/chinese-star-map';ca.setAttribute('data-chinese-arena-entry','1');
        ca.innerHTML=curRole==='student'
          ?'<b>语文知识地图与四大板块专项</b><i>›</i><small>点亮 16 个语文核心考点，练习听写、古诗默写、现代文阅读与微写作</small>'
          :'<b>语文知识地图与四大板块专项</b><i>›</i><small>查看全班 16 语文考点点亮进度、基础/古诗文/阅读/微写作分级段位与积分</small>';
        ea.after(ca);
      }
      main.insertBefore(all,main.firstChild);
    }
    setView(main,viewFromUrl(),false);
  }
  document.addEventListener('click',e=>{
    const a=e.target.closest('#cy-seg a[data-seg]');if(!a||location.pathname!=='/v1/workspace')return;
    const s=a.dataset.seg;if(s!=='workspace'&&s!=='tools')return;
    const main=document.querySelector('#screen main');if(!main||!document.getElementById('cy-ws-all'))return;
    e.preventDefault();e.stopImmediatePropagation();setView(main,s==='tools'?'all':'now',true);
  },true);
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
    records = [list(x) for x in WORKSPACE_RECORD_LINKS]
    snippet = _SNIPPET.replace("__ITEMS__", json.dumps(items, ensure_ascii=False)).replace(
        "__RECORDS__", json.dumps(records, ensure_ascii=False)
    )
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
