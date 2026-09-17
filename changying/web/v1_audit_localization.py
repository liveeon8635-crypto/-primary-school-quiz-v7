"""Chinese presentation layer for Classic audit records embedded in V1.

This patch changes presentation only. Raw audit event names and details remain
untouched in storage and can still be inspected through the DOM title value.
"""

from __future__ import annotations

from changying.web import v1_unified_tools

V1_AUDIT_LOCALIZATION_MARKER = "changying_v1_audit_localization_v1"

_AUDIT_LOCALIZATION_SCRIPT = r'''
<script id="changying_v1_audit_localization_v1-script">
(()=>{
  if(window.__cyV1AuditLocalizationInstalled)return;window.__cyV1AuditLocalizationInstalled=true;
  const labels={
    'points.record':'记录学生积分',
    'auto.reward.grant':'发放自动奖励',
    'auto.reward.cancel':'取消自动奖励',
    'points.class_rule.create':'新建班级积分规则',
    'points.class_rule.update':'修改班级积分规则',
    'ai.lesson.generate':'生成 AI 教学内容'
  };
  const detailLabels={students:'学生',student:'学生',points:'积分',reason:'原因',grant:'奖励记录',reward:'奖励',value:'数值',class:'班级',rule:'规则'};
  function humanDetail(text){
    return String(text||'').split(';').map(part=>{
      const i=part.indexOf('=');if(i<1)return part;
      const key=part.slice(0,i).trim(),value=part.slice(i+1).trim();
      return (detailLabels[key]||key)+'：'+value;
    }).join(' · ');
  }
  function localize(doc){
    if(!doc||!doc.body)return;
    const walker=doc.createTreeWalker(doc.body,NodeFilter.SHOW_ELEMENT);
    let el;
    while((el=walker.nextNode())){
      if(el.children.length===0){
        const raw=(el.textContent||'').trim();
        if(labels[raw]){el.title='原始事件：'+raw;el.textContent=labels[raw];continue}
        if(/(?:^|;)\s*(?:students?|points|reason|grant|reward|value|class|rule)=/.test(raw)&&raw.includes('=')){
          el.title='原始记录：'+raw;el.textContent=humanDetail(raw);
        }
      }
    }
  }
  function attach(){
    const frame=document.getElementById('toolFrame');if(!frame)return;
    const run=()=>{try{const doc=frame.contentDocument;if(!doc)return;localize(doc);const root=doc.body;if(root&&!root.__cyAuditObserver){const obs=new MutationObserver(()=>localize(doc));obs.observe(root,{childList:true,subtree:true});root.__cyAuditObserver=obs}}catch{}};
    frame.addEventListener('load',()=>setTimeout(run,180));setTimeout(run,250);
  }
  attach();
})();
</script>
'''


def patch_v1_audit_localization(html: str) -> str:
    if V1_AUDIT_LOCALIZATION_MARKER in html:
        return html
    if "</body>" not in html:
        raise RuntimeError("V1 audit localization: closing body marker not found")
    return html.replace(
        "</body>",
        _AUDIT_LOCALIZATION_SCRIPT + f"\n<!-- {V1_AUDIT_LOCALIZATION_MARKER} --></body>",
        1,
    )


def install_v1_audit_localization() -> None:
    if getattr(v1_unified_tools, "_audit_localization_installed", False):
        return
    v1_unified_tools._TOOL_HTML = patch_v1_audit_localization(v1_unified_tools._TOOL_HTML)  # noqa: SLF001
    v1_unified_tools._audit_localization_installed = True


__all__ = [
    "V1_AUDIT_LOCALIZATION_MARKER",
    "install_v1_audit_localization",
    "patch_v1_audit_localization",
]
