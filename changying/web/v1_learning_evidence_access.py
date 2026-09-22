"""Role-safe read endpoint for one continuous student evidence record."""

from __future__ import annotations

from types import ModuleType

from fastapi import APIRouter, Depends, HTTPException

from changying.domain.learning_evidence_growth_profile import growth_profile_learning_evidence
from changying.domain.learning_evidence_read_model import student_evidence_snapshot
from changying.domain.learning_evidence_visibility import learning_evidence_for_role
from changying.web.v1_learning_evidence_profile import legacy_student_evidence
from changying.web import v1 as v1_module


def _authorized_student(implementation: ModuleType, db, user, sid: int):
    student = db.scalar(
        implementation.select(implementation.User).where(
            implementation.User.id == sid,
            implementation.User.school_id == user.school_id,
            implementation.User.role == "student",
        )
    )
    if student is None:
        raise HTTPException(404, "学生不存在")

    if user.role in ("teacher", "admin"):
        return implementation.can_manage_student_points(db, user, sid, None)
    if user.role == "parent":
        linked = db.scalar(
            implementation.select(implementation.ParentStudent.id).where(
                implementation.ParentStudent.parent_id == user.id,
                implementation.ParentStudent.student_id == sid,
            )
        )
        if not linked:
            raise HTTPException(403, "未绑定该学生")
        return student
    if user.role == "student":
        if int(user.id) != int(sid):
            raise HTTPException(403, "无权查看其他学生")
        return student
    raise HTTPException(403, "无权查看学生证据")


V1_LEARNING_EVIDENCE_ACCESS_MARKER = "changying_v1_learning_evidence_access_v1"
_PROFILE_ANCHOR = (
    "const s=profile.student||{},a=profile.academic||{},weak=a.weakKnowledge||[],"
    "assignments=a.recentAssignments||[],timeline=profile.timeline||[],"
    "suggestions=profile.suggestions||[];"
)


def patch_v1_learning_evidence_access(html: str) -> str:
    if V1_LEARNING_EVIDENCE_ACCESS_MARKER in html:
        return html
    if _PROFILE_ANCHOR not in html:
        raise RuntimeError("V1 learning evidence access patch: profile anchor not found")
    fetch_line = (
        "if(!profile.learningEvidence&&id){try{profile.learningEvidence="
        "await api('/v1/students/'+id+'/learning-evidence')}catch(_){}}"
    )
    html = html.replace(_PROFILE_ANCHOR, fetch_line + _PROFILE_ANCHOR, 1)
    return html.replace(
        "</body>",
        f"<!-- {V1_LEARNING_EVIDENCE_ACCESS_MARKER} --></body>",
        1,
    )


def install_v1_learning_evidence_access_patch() -> None:
    if getattr(v1_module, "_learning_evidence_access_patch_installed", False):
        return
    original = v1_module.v1_html

    def patched_v1_html() -> str:
        return patch_v1_learning_evidence_access(original())

    v1_module.v1_html = patched_v1_html
    v1_module._learning_evidence_access_patch_installed = True


def install_v1_learning_evidence_access_routes(implementation: ModuleType) -> None:
    app = implementation.app
    if getattr(app.state, "v1_learning_evidence_access_installed", False):
        return

    router = APIRouter()

    @router.get("/v1/students/{sid}/learning-evidence", include_in_schema=False)
    def read_learning_evidence(
        sid: int,
        user=Depends(implementation.current_user),
        db=Depends(implementation.get_db),
    ):
        student = _authorized_student(implementation, db, user, sid)
        items = legacy_student_evidence(
            implementation,
            db,
            int(student.id),
            int(user.school_id),
        )
        evidence = growth_profile_learning_evidence(
            student_evidence_snapshot(items)
        )
        return learning_evidence_for_role(evidence, user.role)

    app.include_router(router)
    app.state.v1_learning_evidence_access_installed = True


__all__ = [
    "install_v1_learning_evidence_access_routes",
]