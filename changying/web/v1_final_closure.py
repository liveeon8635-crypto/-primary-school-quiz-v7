"""Final V1 read-reliability closure.

The normal V1 path is intentionally read-heavy. Earlier patches already expose
partial class-membership failures; this final presentation layer covers the two
remaining cases that could still look like legitimate empty data:

* the top-level student roster request fails before any class can be read;
* the workspace read bundle fails after the page has started rendering.

It also adds a generic, user-retryable runtime fallback for unexpected browser
render/read failures. No API request, database write, or authorization rule is
added here.
"""

from __future__ import annotations

from changying.web import v1 as v1_module


V1_FINAL_CLOSURE_MARKER = "changying_v1_final_closure_v1"

_STUDENT_LIST_CATCH = "try{people=await loadPeople()}catch(err){}"
_STUDENT_LIST_CATCH_WITH_WARNING = (
    "try{people=await loadPeople()}catch(err){"
    "window.__cyV1PeopleLoadWarnings=['学生列表读取失败：'+(err?.message||'请刷新重试')]"
    "}"
)

_WORKSPACE_CATCH = "catch(err){if(err.status===428){await openClassic('/v1/tool?page=account');return}}"
_WORKSPACE_CATCH_WITH_WARNING = (
    "catch(err){if(err.status===428){await openClassic('/v1/tool?page=account');return}"
    "window.__cyV1PeopleLoadWarnings=['工作台读取失败：'+(err?.message||'请刷新重试')]"
    "}"
)

_RUNTIME_FALLBACK = r'''
<style id="changying_v1_final_closure_v1-style">
  .cy-v1-runtime-error{margin:12px 14px;padding:13px 14px;border:1px solid #fecaca;border-radius:14px;background:#fff1f1;color:#991b1b;font-size:13px;line-height:1.55}
  .cy-v1-runtime-error button{margin-top:9px;border:1px solid #f2b7b7;border-radius:10px;background:#fff;padding:8px 11px;font-weight:800;color:#7f1d1d}
</style>
<script id="changying_v1_final_closure_v1-script">
(()=>{
  if(window.__cyV1FinalClosureInstalled)return;window.__cyV1FinalClosureInstalled=true;
  function showRuntimeReadError(){
    const screen=document.getElementById('screen');
    if(!screen||document.getElementById('cy-v1-runtime-error'))return;
    screen.insertAdjacentHTML('afterbegin','<div class="cy-v1-runtime-error" id="cy-v1-runtime-error"><b>页面读取出现异常，当前显示可能不完整。</b><div>这不代表学生、班级或教学记录不存在。可以重新加载后再试。</div><button type="button" data-cy-v1-retry>重新加载</button></div>');
  }
  function isReadFailure(value){
    const msg=String(value?.message||value||'');
    return /读取失败|请求失败|failed to fetch|networkerror|load failed|aborterror|fetch is aborted/i.test(msg);
  }
  window.addEventListener('unhandledrejection',e=>{if(isReadFailure(e.reason))showRuntimeReadError()});
  window.addEventListener('error',e=>{if(isReadFailure(e.error||e.message))showRuntimeReadError()});
  document.addEventListener('click',e=>{if(e.target.closest('[data-cy-v1-retry]'))location.reload()});
})();
</script>
'''


def patch_v1_final_closure(html: str) -> str:
    """Make top-level read failures explicit and add a generic retry fallback."""

    if V1_FINAL_CLOSURE_MARKER in html:
        return html

    # This patch intentionally runs after the membership-reliability layer,
    # which owns the shared browser warning state and renders it on V1 roster
    # surfaces after each screen mutation.
    if "__cyV1PeopleLoadWarnings" not in html or "changying_v1_membership_reliability_v1" not in html:
        raise RuntimeError("V1 final closure patch: membership reliability layer not installed")

    if _STUDENT_LIST_CATCH not in html:
        raise RuntimeError("V1 final closure patch: student-list catch marker not found")
    html = html.replace(_STUDENT_LIST_CATCH, _STUDENT_LIST_CATCH_WITH_WARNING, 1)

    if _WORKSPACE_CATCH not in html:
        raise RuntimeError("V1 final closure patch: workspace catch marker not found")
    html = html.replace(_WORKSPACE_CATCH, _WORKSPACE_CATCH_WITH_WARNING, 1)

    if "</body>" not in html:
        raise RuntimeError("V1 final closure patch: closing body marker not found")
    return html.replace(
        "</body>",
        _RUNTIME_FALLBACK + f"<!-- {V1_FINAL_CLOSURE_MARKER} --></body>",
        1,
    )


def install_v1_final_closure_patch() -> None:
    """Install the final V1 reliability layer exactly once before routes bind."""

    if getattr(v1_module, "_final_closure_patch_installed", False):
        return
    original = v1_module.v1_html

    def patched_v1_html() -> str:
        return patch_v1_final_closure(original())

    v1_module.v1_html = patched_v1_html
    v1_module._final_closure_patch_installed = True


__all__ = [
    "V1_FINAL_CLOSURE_MARKER",
    "install_v1_final_closure_patch",
    "patch_v1_final_closure",
]
