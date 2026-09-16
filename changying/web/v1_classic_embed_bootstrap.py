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
 var validating=false;
 function report(type,detail){try{parent.postMessage({source:'changying-classic',type:type,detail:detail||''},location.origin)}catch(_e){}}
 function hasState(){try{return typeof state!=='undefined'}catch(_e){return false}}
 function requestSession(){report('session-needed','')}
 function begin(attempt){
  if(!hasState()||typeof markNetwork!=='function'||typeof validateSavedSession!=='function'){
   if(attempt<40){setTimeout(function(){begin(attempt+1)},50);return}report('error','旧版初始化函数未就绪');return;
  }
  if(!state.token||!state.user){requestSession();return}
  if(validating)return;
  validating=true;
  try{
   markNetwork(true);
   Promise.resolve(validateSavedSession()).then(function(ok){
    validating=false;
    if(ok){setTimeout(function(){report('ready','')},80)}else{report('not-ready','登录状态未就绪')}
   }).catch(function(){validating=false;report('error','登录状态验证失败')})
  }catch(_e){validating=false;report('error','旧版初始化失败')}
 }
 function hydrateSession(session,attempt){
  if(!session||!session.token||!session.user){report('error','统一登录状态缺失');return}
  if(!hasState()){
   if(attempt<40){setTimeout(function(){hydrateSession(session,attempt+1)},50);return}report('error','旧版登录状态容器未就绪');return;
  }
  try{
   state.token=String(session.token);
   state.user=session.user;
   state.remember=!!session.remember;
   if(typeof saveAuth==='function')saveAuth();
   begin(0);
  }catch(_e){report('error','旧版登录状态写入失败')}
 }
 window.addEventListener('message',function(event){
  if(event.origin!==location.origin||event.source!==parent)return;
  var data=event.data||{};
  if(data.source!=='changying-v1'||data.type!=='session')return;
  hydrateSession(data.session||{},0);
 });
 function boot(){
  if(hasState()&&state.token&&state.user){begin(0);return}
  requestSession();
 }
 if(document.readyState==='loading'){document.addEventListener('DOMContentLoaded',boot,{once:true})}else{boot()}
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
