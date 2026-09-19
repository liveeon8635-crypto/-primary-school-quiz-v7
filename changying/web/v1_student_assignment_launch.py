"""Add a real student-side action to V1 assignment rows."""

from __future__ import annotations

from changying.web import v1 as v1_module

V1_STUDENT_ASSIGNMENT_LAUNCH_MARKER = "changying_v1_student_assignment_launch_v1"

_OLD_ROW = (
    '<div class="row"><span class="row-main"><b>${esc(x.title||\'作业\')}</b>'
    '<small>${esc((x.subject||\'\')+\' \'+(x.dueDate||\'\'))}</small></span>'
    '<span class="tag">${esc(x.status||((x.completed)?\'已完成\':\'待完成\'))}</span></div>'
)

_NEW_ROW = (
    '<div class="row"><span class="row-main"><b>${esc(x.title||\'作业\')}</b>'
    '<small>${esc((x.subject||\'\')+\' \'+(x.dueDate||\'\'))}</small></span>'
    '<span style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;justify-content:flex-end">'
    '<span class="tag">${esc(x.status||((x.completed)?\'已完成\':\'待完成\'))}</span>'
    '${session.role===\'student\'&&!x.completed&&!x.quizSubmitted&&(x.submissionMode||\'quiz\')!==\'media\'?'
    '`<a class="btn primary" href="/v1/tool?page=assignments&assignment=${x.id}">开始答题</a>`:\'\'}'
    '</span></div>'
)


def patch_v1_student_assignment_launch(html: str) -> str:
    if V1_STUDENT_ASSIGNMENT_LAUNCH_MARKER in html:
        return html
    if _OLD_ROW not in html:
        raise RuntimeError("V1 student assignment launch patch: assignment row anchor not found")
    html = html.replace(_OLD_ROW, _NEW_ROW, 1)
    return html.replace(
        "</body>",
        f"<!-- {V1_STUDENT_ASSIGNMENT_LAUNCH_MARKER} --></body>",
        1,
    )


def install_v1_student_assignment_launch_patch() -> None:
    if getattr(v1_module, "_student_assignment_launch_patch_installed", False):
        return
    original = v1_module.v1_html

    def patched_v1_html() -> str:
        return patch_v1_student_assignment_launch(original())

    v1_module.v1_html = patched_v1_html
    v1_module._student_assignment_launch_patch_installed = True


__all__ = [
    "V1_STUDENT_ASSIGNMENT_LAUNCH_MARKER",
    "install_v1_student_assignment_launch_patch",
    "patch_v1_student_assignment_launch",
]
