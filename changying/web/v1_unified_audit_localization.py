"""Chinese presentation for the actual top-level unified Classic audit surface."""
from __future__ import annotations
from changying.web import v1_classic_gzip_embed

V1_UNIFIED_AUDIT_LOCALIZATION_MARKER = "changying_v1_unified_audit_localization_v1"

_SNIPPET = r'''
<script id="changying_v1_unified_audit_localization_v1-script">
(function(){
 var params=new URLSearchParams(location.search);if(params.get('unified')!=='1')return;
 var labels={'points.record':'记录学生积分','auto.reward.grant':'发放自动奖励','auto.reward.cancel':'取消自动奖励','points.class_rule.create':'新建班级积分规则','points.class_rule.update':'修改班级积分规则','ai.lesson.generate':'生成 AI 教学内容'};
 var keys={students:'学生',student:'学生',points:'积分',reason:'原因',grant:'奖励记录',reward:'奖励',value:'数值',class:'班级',rule:'规则'};
 function detail(raw){
  var prefix='',payload=String(raw||''),cut=payload.indexOf(' · ');if(cut>=0){prefix=payload.slice(0,cut+3);payload=payload.slice(cut+3)}
  if(payload.indexOf('=')<0)return raw;var changed=false;
  var body=payload.split(';').map(function(part){var i=part.indexOf('=');if(i<1)return part;var k=part.slice(0,i).trim(),v=part.slice(i+1).trim();if(!keys[k])return part;changed=true;return keys[k]+'：'+v}).join(' · ');
  return changed?prefix+body:raw;
 }
 function run(){
  var page='';try{page=String((typeof state!=='undefined'&&state.page)||params.get('page')||'')}catch(_e){page=String(params.get('page')||'')}
  if(page!=='audit'&&page!=='adminAudit')return;
  document.querySelectorAll('body *').forEach(function(el){if(el.children.length)return;var raw=(el.textContent||'').trim();if(!raw)return;if(labels[raw]){el.title='原始事件：'+raw;el.textContent=labels[raw];return}var human=detail(raw);if(human!==raw){el.title='原始记录：'+raw;el.textContent=human}});
 }
 function start(){run();var root=document.body;if(root&&!root.__cyAuditZh){var pending=false,obs=new MutationObserver(function(){if(pending)return;pending=true;setTimeout(function(){pending=false;run()},30)});obs.observe(root,{childList:true,subtree:true});root.__cyAuditZh=obs}setTimeout(run,180);setTimeout(run,700)}
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start,{once:true});else start();
})();
</script>
'''

def inject_v1_unified_audit_localization(html: str) -> str:
    if V1_UNIFIED_AUDIT_LOCALIZATION_MARKER in html:
        return html
    marker = _SNIPPET + f"\n<!-- {V1_UNIFIED_AUDIT_LOCALIZATION_MARKER} -->"
    return html.replace("</body>", marker + "</body>", 1) if "</body>" in html else html + marker

def install_v1_unified_audit_localization() -> None:
    if getattr(v1_classic_gzip_embed, "_v1_unified_audit_localization_installed", False):
        return
    original = v1_classic_gzip_embed.enhance_unified_classic_html
    def patched(html: str) -> str:
        return inject_v1_unified_audit_localization(original(html))
    v1_classic_gzip_embed.enhance_unified_classic_html = patched
    v1_classic_gzip_embed._v1_unified_audit_localization_installed = True

__all__=["V1_UNIFIED_AUDIT_LOCALIZATION_MARKER","inject_v1_unified_audit_localization","install_v1_unified_audit_localization"]
