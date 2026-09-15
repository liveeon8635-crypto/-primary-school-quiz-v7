"""Surface partial teacher-membership read failures in V1.

Teacher student rosters are assembled from the students endpoint of every visible
teaching affiliation. Those requests stay isolated so one failing class does not
take down the whole V1 screen, but a failed read must not look like a confirmed
empty roster. This presentation-only patch records those partial failures and
shows a clear warning after the screen renders.

The patch does not add API requests, write data, or change authorization.
"""

from __future__ import annotations

from changying.web import v1 as v1_module


V1_MEMBERSHIP_RELIABILITY_MARKER = "changying_v1_membership_reliability_v1"

_LOAD_PEOPLE = "    async function loadPeople(){"
_LOAD_PEOPLE_WITH_WARNING_STATE = (
    "    async function loadPeople(){window.__cyV1PeopleLoadWarnings=[];"
)

_BATCH_FAILURE = "catch{return{classInfo:c,students:[]}}"
_BATCH_FAILURE_FLAGGED = "catch{return{classInfo:c,students:[],failed:true}}"

_TEACHER_RETURN = "return [...byId.values()]"
_TEACHER_RETURN_WITH_WARNING = (
    "window.__cyV1PeopleLoadWarnings=classRows.filter(item=>item.failed)"
    ".map(item=>item.classInfo?.name||('教学归属 #'+String(item.classInfo?.id??'未知')));"
    "return [...byId.values()]"
)

_RELIABILITY_SNIPPET = r'''
<script id="changying_v1_membership_reliability_v1-script">
(()=>{
  if(window.__cyV1MembershipReliabilityInstalled)return;
  window.__cyV1MembershipReliabilityInstalled=true;
  const esc=v=>String(v??'').replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  function showMembershipWarning(){
    const current=document.getElementById('cy-v1-membership-warning');
    const failures=Array.isArray(window.__cyV1PeopleLoadWarnings)?window.__cyV1PeopleLoadWarnings:[];
    const path=location.pathname;
    if(!failures.length||!['/v1/workspace','/v1/student','/v1/history'].includes(path)){current?.remove();return}
    if(current)return;
    const screen=document.getElementById('screen'),main=screen?.querySelector('main');if(!main)return;
    const anchor=main.querySelector('.notice')||main.querySelector('.page-head');if(!anchor)return;
    const names=failures.slice(0,5).map(esc).join(' / '),extra=failures.length>5?` 等 ${failures.length} 个`:'';
    anchor.insertAdjacentHTML('afterend',`<section class="section" id="cy-v1-membership-warning"><div class="notice warn"><b>有 ${failures.length} 个教学归属暂时读取失败，当前学生统计可能不完整。</b><div style="margin-top:6px">${names}${extra}</div><div style="margin-top:6px">这是读取失败提示，不代表这些教学归属没有学生；刷新页面可重新尝试。</div></div></section>`);
  }
  let timer=null;const schedule=()=>{clearTimeout(timer);timer=setTimeout(showMembershipWarning,40)};
  const screen=document.getElementById('screen');if(screen)new MutationObserver(schedule).observe(screen,{childList:true,subtree:true});
  window.addEventListener('popstate',schedule);schedule();
})();
</script>
'''


def patch_v1_membership_reliability(html: str) -> str:
    """Make partial teacher-roster failures visible without failing the page."""

    if V1_MEMBERSHIP_RELIABILITY_MARKER in html:
        return html

    if _LOAD_PEOPLE not in html:
        raise RuntimeError("V1 membership reliability patch: loadPeople marker not found")
    html = html.replace(_LOAD_PEOPLE, _LOAD_PEOPLE_WITH_WARNING_STATE, 1)

    if _BATCH_FAILURE not in html:
        raise RuntimeError("V1 membership reliability patch: membership failure marker not found")
    html = html.replace(_BATCH_FAILURE, _BATCH_FAILURE_FLAGGED, 1)

    if _TEACHER_RETURN not in html:
        raise RuntimeError("V1 membership reliability patch: teacher return marker not found")
    html = html.replace(_TEACHER_RETURN, _TEACHER_RETURN_WITH_WARNING, 1)

    if "</body>" not in html:
        raise RuntimeError("V1 membership reliability patch: closing body marker not found")
    return html.replace("</body>", _RELIABILITY_SNIPPET + "\n</body>", 1)


def install_v1_membership_reliability_patch() -> None:
    """Install the partial-read warning exactly once before V1 routes bind."""

    if getattr(v1_module, "_membership_reliability_patch_installed", False):
        return
    original = v1_module.v1_html

    def patched_v1_html() -> str:
        return patch_v1_membership_reliability(original())

    v1_module.v1_html = patched_v1_html
    v1_module._membership_reliability_patch_installed = True


__all__ = [
    "V1_MEMBERSHIP_RELIABILITY_MARKER",
    "install_v1_membership_reliability_patch",
    "patch_v1_membership_reliability",
]
