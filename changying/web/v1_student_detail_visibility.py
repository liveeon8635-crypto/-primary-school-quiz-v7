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

_DETAIL_CLARITY_REPLACEMENTS = (
    (
        '<span class="tag">监护人 ${s.parents?.length??\'—\'}</span>',
        '<span class="tag">家庭关联 · 监护人 ${s.parents?.length??\'—\'}</span>',
    ),
    (
        "<h2>历史时间线</h2><p>换班、换老师或升年级后仍保留在同一档案</p>",
        "<h2>成长档案时间线</h2><p>按时间倒序展示 · 最新记录在前；换班、换老师或升年级后仍保留在同一档案</p>",
    ),
)

_DETAIL_MOBILE_TARGETS = (
    (
        '<div class="card"><h2>需要关注 / 下一步教学</h2><div class="list" style="margin-top:12px">',
        '<div class="card"><h2>需要关注 / 下一步教学</h2><div id="suggestions" class="list" style="margin-top:12px">',
    ),
    (
        '<div class="card"><h2>作业情况</h2><div class="list" style="margin-top:12px">',
        '<div class="card"><h2>作业情况</h2><div id="assignments" class="list" style="margin-top:12px">',
    ),
    (
        '<div class="card"><h2>薄弱内容 / 错题</h2><div class="list" style="margin-top:12px">',
        '<div class="card"><h2>薄弱内容 / 错题</h2><div id="weak" class="list" style="margin-top:12px">',
    ),
    (
        '<div class="card"><div class="timeline">',
        '<div class="card"><div id="timeline" class="timeline">',
    ),
)


STUDENT_DETAIL_MOBILE_CSS_MARKER = "changying_v1_student_detail_mobile_css_v2"

_MOBILE_LAYOUT_CSS = (
    f"<style id='{STUDENT_DETAIL_MOBILE_CSS_MARKER}'>"
    "@media (max-width:640px){"
    "html,body{overflow-x:hidden;overflow-y:auto;-webkit-overflow-scrolling:touch;"
    "overscroll-behavior-y:auto;height:auto;max-height:none}"
    "#suggestions,#assignments,#weak,#timeline{min-width:0;max-width:100%;"
    "overflow-x:auto;overflow-y:visible;max-height:none;height:auto;"
    "-webkit-overflow-scrolling:touch;overscroll-behavior:contain}"
    "#suggestions>*,#assignments>*,#weak>*,#timeline>*{min-width:0;overflow-wrap:anywhere}"
    ".card{overflow:visible;max-height:none}"
    "body{padding-bottom:calc(72px + env(safe-area-inset-bottom,0px))}"
    "}"
    "</style>"
)


def patch_v1_student_detail_visibility(html: str) -> str:
    """Remove caps and keep the full record readable on narrow phone screens."""

    if V1_STUDENT_DETAIL_VISIBILITY_MARKER in html:
        return html

    for old, new in (*_DETAIL_CAPS, *_DETAIL_CLARITY_REPLACEMENTS, *_DETAIL_MOBILE_TARGETS):
        if old not in html:
            raise RuntimeError(f"V1 student detail visibility patch: marker not found: {old}")
        html = html.replace(old, new, 1)

    return html.replace(
        "</body>",
        f"{_MOBILE_LAYOUT_CSS}<!-- {V1_STUDENT_DETAIL_VISIBILITY_MARKER} --></body>",
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


WORKSPACE_ATTACHMENT_MARKER = "changying_v1_workspace_attachment_affordance_v1"

_ATTACHMENT_AFFORDANCE = (
    f"<div id='{WORKSPACE_ATTACHMENT_MARKER}' class='card' "
    "style='margin-top:12px'>"
    "<h2>发送照片或文件</h2>"
    "<p>选择照片或文件后随本次教学记录一起提交；未选择时不产生任何记录。</p>"
    "<input type='file' id='workspace-attachment-input' "
    "accept='image/*,.pdf,.doc,.docx,.txt' multiple>"
    "<div id='workspace-attachment-list' class='list' style='margin-top:8px'></div>"
    "</div>"
)


def patch_v1_workspace_attachment_affordance(html: str) -> str:
    """Add a presentation-only photo/file picker to the V1 workspace.

    This is an additive UI affordance only: it renders a file input and a
    local list of chosen file names.  It performs no upload, no API call, no
    data write, and changes no authorization behavior.
    """

    if WORKSPACE_ATTACHMENT_MARKER in html:
        return html

    return html.replace(
        "</body>",
        f"{_ATTACHMENT_AFFORDANCE}<!-- {WORKSPACE_ATTACHMENT_MARKER} --></body>",
        1,
    )


__all__ = [
    "STUDENT_DETAIL_MOBILE_CSS_MARKER",
    "V1_STUDENT_DETAIL_VISIBILITY_MARKER",
    "WORKSPACE_ATTACHMENT_MARKER",
    "install_v1_student_detail_visibility_patch",
    "patch_v1_student_detail_visibility",
    "patch_v1_workspace_attachment_affordance",
]
