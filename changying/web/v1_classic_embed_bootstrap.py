"""Self-bootstrap Classic when embedded inside the V1 unified tool shell."""
from __future__ import annotations
from changying.web import classic_ui

V1_CLASSIC_EMBED_MARKER = "changying_v1_classic_embed_bootstrap_v1"

V1_CLASSIC_EMBED_SNIPPET = r'''
<style id="changying_v1_classic_embed_bootstrap_v1-style">
html.cy-v1-embedded #changying_classic_ui_v2-ribbon,
html.cy-v1-embedded #changying_classic_ui_v2-workflow,
html.cy-v1-embedded .cy-classic-ribbon,
html.cy-v1-embedded .cy-workflow-panel,
html.cy-v1-embedded .sidebar,
html.cy-v1-embedded .mobile-header,
html.cy-v1-embedded .bottom-nav{display:none!important}
html.cy-v1-embedded .shell:not(.hidden){display:block!important;min-height:100%!important}
html.cy-v1-embedded .main{padding:14px!important;min-height:100%!important}
html.cy-v1-embedded body{background:#f3f6fb!important}
html.cy-v1-embedded .page-head{margin-top:0!important}
@media(max-width:650px){html.cy-v1-embedded .main{padding:12px 10px 28px!important}.card{border-radius:16px!important}}
</style>
<script id="changying_v1_classic_embed_bootstrap_v1-script">
(function(){
 var params=new URLSearchParams(location.search);if(params.get('embedded')!=='1')return;
 document.documentElement.classList.add('cy-v1-embedded');
 function report(type,detail){try{parent.postMessage({source:'changying-classic',type:type,detail:detail||''},location.origin)}catch(_e){}}
 function begin(attempt){
  if(typeof window.markNetwork!=='function'||typeof window.validateSavedSession!=='function'){
   if(attempt<30){setTimeout(function(){begin(attempt+1)},50);return}report('error','旧版初始化函数未就绪');return;
  }
  try{window.markNetwork(true);Promise.resolve(window.validateSavedSession()).then(function(ok){if(ok){setTimeout(function(){report('ready','')},80)}else{report('not-ready','登录状态未就绪')}}).catch(function(){report('error','登录状态验证失败')})}catch(_e){report('error','旧版初始化失败')}
 }
 if(document.readyState==='loading'){document.addEventListener('DOMContentLoaded',function(){begin(0)},{once:true})}else{begin(0)}
})();
</script>
'''

def inject_v1_classic_embed(html: str) -> str:
    if V1_CLASSIC_EMBED_MARKER in html:
        return html
    marker = V1_CLASSIC_EMBED_SNIPPET + f"\n<!-- {V1_CLASSIC_EMBED_MARKER} -->"
    return html.replace("</body>", marker + "</body>", 1) if "</body>" in html else html + marker

def install_v1_classic_embed_bootstrap() -> None:
    if getattr(classic_ui, "_v1_classic_embed_bootstrap_installed", False):
        return
    original = classic_ui.inject_classic_ui
    def patched(html: str) -> str:
        return inject_v1_classic_embed(original(html))
    classic_ui.inject_classic_ui = patched
    classic_ui._v1_classic_embed_bootstrap_installed = True

__all__ = ["V1_CLASSIC_EMBED_MARKER","inject_v1_classic_embed","install_v1_classic_embed_bootstrap"]
