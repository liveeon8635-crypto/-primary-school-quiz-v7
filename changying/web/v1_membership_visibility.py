"""Keep the core V1 student roster complete without unbounded fan-out.

The base V1 shell still had an early safety cap that only loaded students from
the first 30 teacher classes.  That cap could make the homepage student count
and the full student roster disagree with the newer operational panels once a
teacher could see more than 30 teaching affiliations.

This patch removes only that silent cap.  It keeps the existing protected read
APIs, active-student filtering, stable ``student_id`` aggregation, and loads
class memberships in small batches so request concurrency stays bounded.
"""

from __future__ import annotations

from changying.web import v1 as v1_module


V1_MEMBERSHIP_VISIBILITY_MARKER = "changying_v1_membership_visibility_v1"

_OLD = "const classRows=await Promise.all(classes.slice(0,30).map(async c=>{try{return{classInfo:c,students:await api('/teacher/classes/'+c.id+'/students')}}catch{return{classInfo:c,students:[]}}}));"
_NEW = "const classRows=[];for(let i=0;i<classes.length;i+=8){const batch=await Promise.all(classes.slice(i,i+8).map(async c=>{try{return{classInfo:c,students:await api('/teacher/classes/'+c.id+'/students')}}catch{return{classInfo:c,students:[]}}}));classRows.push(...batch)}"


def patch_v1_membership_visibility(html: str) -> str:
    """Read every visible teacher class in bounded batches."""

    if V1_MEMBERSHIP_VISIBILITY_MARKER in html:
        return html
    if _OLD not in html:
        raise RuntimeError("V1 membership visibility patch: class membership marker not found")
    html = html.replace(_OLD, _NEW, 1)
    return html.replace("</body>", f"<!-- {V1_MEMBERSHIP_VISIBILITY_MARKER} --></body>", 1)


def install_v1_membership_visibility_patch() -> None:
    """Install the complete core membership read exactly once."""

    if getattr(v1_module, "_membership_visibility_patch_installed", False):
        return
    original = v1_module.v1_html

    def patched_v1_html() -> str:
        return patch_v1_membership_visibility(original())

    v1_module.v1_html = patched_v1_html
    v1_module._membership_visibility_patch_installed = True


__all__ = [
    "V1_MEMBERSHIP_VISIBILITY_MARKER",
    "install_v1_membership_visibility_patch",
    "patch_v1_membership_visibility",
]
