"""Show the complete already-fetched student detail record in V1.

The student detail page historically rendered only the first few suggestions,
assignments, weak-knowledge rows, and timeline events even though the protected
growth-profile response had already delivered the full visible arrays.  Silent
truncation is misleading on a page whose purpose is the student's continuous
record, so this presentation-only patch removes those detail caps.

Homepage previews remain intentionally compact.  This patch adds no API calls,
writes no data, and changes no authorization behavior.
"""

from __future__ import annotations

from changying.web import v1 as v1_module


V1_STUDENT_DETAIL_VISIBILITY_MARKER = "changying_v1_student_detail_visibility_v1"

_DETAIL_CAPS = (
    ("suggestions.slice(0,4).map", "suggestions.map"),
    ("assignments.slice(0,6).map", "assignments.map"),
    ("weak.slice(0,6).map", "weak.map"),
    ("timeline.slice(0,10).map", "timeline.map"),
)


def patch_v1_student_detail_visibility(html: str) -> str:
    """Remove silent caps from the already-loaded continuous student record."""

    if V1_STUDENT_DETAIL_VISIBILITY_MARKER in html:
        return html

    for old, new in _DETAIL_CAPS:
        if old not in html:
            raise RuntimeError(f"V1 student detail visibility patch: marker not found: {old}")
        html = html.replace(old, new, 1)

    return html.replace(
        "</body>",
        f"<!-- {V1_STUDENT_DETAIL_VISIBILITY_MARKER} --></body>",
        1,
    )


def install_v1_student_detail_visibility_patch() -> None:
    """Install complete student-detail rendering once before V1 routes bind."""

    if getattr(v1_module, "_student_detail_visibility_patch_installed", False):
        return
    original = v1_module.v1_html

    def patched_v1_html() -> str:
        return patch_v1_student_detail_visibility(original())

    v1_module.v1_html = patched_v1_html
    v1_module._student_detail_visibility_patch_installed = True


__all__ = [
    "V1_STUDENT_DETAIL_VISIBILITY_MARKER",
    "install_v1_student_detail_visibility_patch",
    "patch_v1_student_detail_visibility",
]
