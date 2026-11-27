"""Read-only guardian visibility on the V1 student detail surface.

The existing growth-profile response already carries legacy ``student.parents``
rows after the caller has passed the existing authorization checks.  This patch
only renders that already-visible relationship metadata; it adds no endpoint,
permission, credential, database write, or relationship mutation.
"""

from __future__ import annotations

from changying.web import v1 as v1_module

V1_GUARDIAN_VISIBILITY_MARKER = "changying_v1_guardian_visibility_v1"

_SNIPPET = r'''
<style id="changying_v1_guardian_visibility_v1-style">
  .cy-guardian-list{display:grid;gap:9px}.cy-guardian-row{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:11px 12px;border:1px solid #e4e9f2;border-radius:12px;background:#fff}
  .cy-guardian-row b{font-size:14px}.cy-guardian-row small{display:block;color:#667085;margin-top:3px}.cy-guardian-badge{font-size:11px;color:#173c78;background:#edf3ff;border-radius:999px;padding:6px 8px;white-space:nowrap}
</style>
<script id="changying_v1_guardian_visibility_v1-script">
(()=>{
  if(window.__cyV1GuardianVisibilityInstalled)return;window.__cyV1GuardianVisibilityInstalled=true;
  const token=()=>{const remember=localStorage.getItem('v717Remember')==='1';return (remember?localStorage.getItem('v717Token'):sessionStorage.getItem('v717Token'))||sessionStorage.getItem('v717Token')||localStorage.getItem('v717Token')||sessionStorage.getItem('v6Token')||localStorage.getItem('v6Token')||''};
  const isStaff=()=>{try{const raw=sessionStorage.getItem('v717User')||localStorage.getItem('v717User')||sessionStorage.getItem('v6User')||localStorage.getItem('v6User');const r=raw?String((JSON.parse(raw)||{}).role||''):'';return r==='teacher'||r==='admin'}catch{return false}};
  const esc=v=>String(v??'').replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  const accountID=row=>Number(row?.guardian_account_id||row?.account_id||row?.user_id||row?.id||0);
  const relation=row=>{const x=String(row?.relationship||row?.relation||'').trim().toLowerCase();if(['parent','父亲','母亲','家长'].includes(x))return'家长';if(['grandparent','祖父','祖母','外祖父','外祖母'].includes(x))return'祖辈监护人';return'其他监护人'};
  function normalize(rows){const seen=new Set(),out=[];for(const row of (Array.isArray(rows)?rows:[])){const id=accountID(row);if(!Number.isInteger(id)||id<=0||seen.has(id))continue;seen.add(id);out.push({id,name:String(row?.name||row?.display_name||'').trim(),relationship:relation(row),primary:Boolean(row?.is_primary_contact||row?.primary)})}return out}
  async function readProfile(id){if(!isStaff())return null;const t=token();if(!t)throw new Error('no-session');if(t==='demo')return null;const r=await fetch('/teacher/students/'+id+'/growth-profile',{headers:{Authorization:'Bearer '+t}});if(!r.ok)throw new Error('read-failed-'+r.status);return await r.json()}
  function render(items){if(!items.length)return'<div class="empty">当前档案没有可展示的有效监护关系。</div>';return'<div class="cy-guardian-list">'+items.map(x=>`<div class="cy-guardian-row"><div><b>${esc(x.name||'监护人')}</b><small>${esc(x.relationship)} · 账号 #${esc(x.id)}</small></div>${x.primary?'<span class="cy-guardian-badge">主要联系人</span>':''}</div>`).join('')+'</div>'}
  function renderHistory(rows){if(!Array.isArray(rows)||!rows.length)return'';return'<div style="margin-top:14px"><h3 style="margin:0 0 8px">家长关联历史</h3><div class="cy-guardian-list">'+rows.map(x=>{const start=x.startKnown?esc(x.startedAt||''):'起始时间未知',end=x.current?'当前':(x.endKnown?esc(x.endedAt||''):'结束时间未知'),badge=x.current?'当前关联':(x.endReason==='replaced'?'已换绑':'历史关联');return `<div class="cy-guardian-row"><div><b>${esc(x.parentName||'家长')}</b><small>账号 #${esc(x.parentID||'')} · ${start} → ${end}</small></div><span class="cy-guardian-badge">${badge}</span></div>`}).join('')+'</div></div>'}
  async function install(){
    if(location.pathname!='/v1/student')return;const id=Number(new URLSearchParams(location.search).get('id')||0);if(!id||document.getElementById('cy-guardian-section'))return;
    const main=document.querySelector('#screen main');if(!main)return;
    let profile=null;try{profile=await readProfile(id)}catch{return}if(!profile)return;
    const items=normalize(profile?.student?.parents||profile?.parents||[]),history=profile?.parentHistory||[];
    const section=document.createElement('section');section.className='section';section.id='cy-guardian-section';section.innerHTML='<div class="section-head"><div><h2>家庭关联</h2><p>展示当前监护关系与可追溯历史；未知时间保持未知，不代表新增授权。</p></div></div>'+render(items)+renderHistory(history);main.appendChild(section)
  }
  let timer=null;const run=()=>{clearTimeout(timer);timer=setTimeout(install,100)};new MutationObserver(run).observe(document.getElementById('screen')||document.body,{childList:true,subtree:true});window.addEventListener('popstate',run);run();
})();
</script>
'''


def patch_v1_guardian_visibility(html: str) -> str:
    """Add the read-only guardian section exactly once."""
    if V1_GUARDIAN_VISIBILITY_MARKER in html:
        return html
    if "</body>" not in html:
        raise RuntimeError("V1 guardian visibility patch: closing body marker not found")
    return html.replace("</body>", _SNIPPET + "\n</body>", 1)


def install_v1_guardian_visibility_patch() -> None:
    """Wrap the installed V1 renderer without changing route authorization."""
    if getattr(v1_module, "_guardian_visibility_patch_installed", False):
        return
    original = v1_module.v1_html

    def patched_v1_html() -> str:
        return patch_v1_guardian_visibility(original())

    v1_module.v1_html = patched_v1_html
    v1_module._guardian_visibility_patch_installed = True


__all__ = ["V1_GUARDIAN_VISIBILITY_MARKER", "install_v1_guardian_visibility_patch", "patch_v1_guardian_visibility"]
