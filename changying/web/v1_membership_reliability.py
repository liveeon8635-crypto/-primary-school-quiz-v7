"""Surface partial teacher-membership read failures in V1.

Teacher student rosters are assembled from the students endpoint of every visible
teaching affiliation.  Those requests are intentionally isolated so one failing
class does not take down the whole V1 screen, but silently turning a failed read
into an empty list can make a partial result look complete.  This presentation
patch keeps the resilient behavior and adds an explicit warning whenever one or
more class-membership reads fail.

The patch does not add API requests, write data, or change authorization.
"""

from __future__ import annotations

from changying.web import v1 as v1_module


V1_MEMBERSHIP_RELIABILITY_MARKER = "changying_v1_membership_reliability_v1"

_LOAD_PEOPLE = "    async function loadPeople(){"
_LOAD_PEOPLE_WITH_WARNING_STATE = """    let peopleLoadWarnings=[];
    const peopleLoadWarningHtml=()=>peopleLoadWarnings.length?`<section class=\"section\"><div class=\"notice warn\"><b>有 ${peopleLoadWarnings.length} 个教学归属暂时读取失败，当前学生统计可能不完整。</b><div style=\"margin-top:6px\">${peopleLoadWarnings.slice(0,5).map(x=>esc(x)).join(' / ')}${peopleLoadWarnings.length>5?` 等 ${peopleLoadWarnings.length} 个`:''}</div><div style=\"margin-top:6px\">这是读取失败提示，不代表这些教学归属没有学生；刷新页面可重新尝试。</div></div></section>`:'';
    async function loadPeople(){peopleLoadWarnings=[];"""

_BATCH_FAILURE = "catch{return{classInfo:c,students:[]}}"
_BATCH_FAILURE_FLAGGED = "catch{return{classInfo:c,students:[],failed:true}}"

_TEACHER_RETURN = "return [...byId.values()]"
_TEACHER_RETURN_WITH_WARNING = "peopleLoadWarnings=classRows.filter(item=>item.failed).map(item=>item.classInfo?.name||('教学归属 #'+String(item.classInfo?.id??'未知')));return [...byId.values()]"

_AUDIT_RENDER = "${duplicateAuditHtml(people)}"
_WARNING_AND_AUDIT_RENDER = "${peopleLoadWarningHtml()}${duplicateAuditHtml(people)}"


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

    audit_count = html.count(_AUDIT_RENDER)
    if audit_count != 2:
        raise RuntimeError(
            f"V1 membership reliability patch: expected 2 roster audit render points, found {audit_count}"
        )
    html = html.replace(_AUDIT_RENDER, _WARNING_AND_AUDIT_RENDER)

    return html.replace(
        "</body>",
        f"<!-- {V1_MEMBERSHIP_RELIABILITY_MARKER} --></body>",
        1,
    )


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
