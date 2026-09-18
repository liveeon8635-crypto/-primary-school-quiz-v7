"""Role-safe read endpoint for one continuous student evidence record."""

from __future__ import annotations

from types import ModuleType

from fastapi import Depends, HTTPException

from changying.domain.learning_evidence_growth_profile import growth_profile_learning_evidence
from changying.domain.learning_evidence_read_model import student_evidence_snapshot
from changying.web.v1_learning_evidence_profile import legacy_student_evidence


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


def install_v1_learning_evidence_access_routes(implementation: ModuleType) -> None:
    app = implementation.app
    if getattr(app.state, "v1_learning_evidence_access_installed", False):
        return

    @app.get("/v1/students/{sid}/learning-evidence", include_in_schema=False)
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
        return growth_profile_learning_evidence(student_evidence_snapshot(items))

    app.state.v1_learning_evidence_access_installed = True


__all__ = [
    "install_v1_learning_evidence_access_routes",
]