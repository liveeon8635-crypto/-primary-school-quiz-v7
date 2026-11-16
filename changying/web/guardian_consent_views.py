"""Guardian AI consent endpoints for teachers and linked parents (P0-2)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import desc, select

from changying.services.guardian_consent import (
    DEFAULT_VALID_DAYS,
    TOKEN_TTL_HOURS,
    compliance_student_ai_enabled,
    confirm_consent_token,
    create_consent_token,
    record_proof_consent,
    register_guardian_consent_tables,
    revoke_student_consent,
)


class TokenCreateBody(BaseModel):
    scope: str = Field(default="student_ai_all", max_length=64)
    policyVersion: str = Field(default="v1.0", max_length=32)
    validDays: int = Field(default=DEFAULT_VALID_DAYS, ge=1, le=365)
    ttlHours: int = Field(default=TOKEN_TTL_HOURS, ge=1, le=720)


class ProofConsentBody(BaseModel):
    verificationMethod: str = Field(default="written_proof", max_length=32)
    proofDigest: str = Field(min_length=6, max_length=128)
    scope: str = Field(default="student_ai_all", max_length=64)
    policyVersion: str = Field(default="v1.0", max_length=32)
    validDays: int = Field(default=DEFAULT_VALID_DAYS, ge=1, le=365)


class TokenConfirmBody(BaseModel):
    token: str = Field(min_length=16, max_length=256)
    studentId: int | None = None


class RevokeBody(BaseModel):
    scope: str | None = Field(default=None, max_length=64)
    reason: str = Field(default="", max_length=200)


def install_guardian_consent_views(implementation: Any) -> APIRouter:
    app = implementation.app
    if getattr(app.state, "guardian_consent_installed", False):
        return app.state.guardian_consent_router

    tables = register_guardian_consent_tables(implementation)
    consents_t, audits_t = tables["consents"], tables["audits"]
    User = implementation.User
    ParentStudent = implementation.ParentStudent
    SchoolClass = implementation.SchoolClass
    ClassStudent = implementation.ClassStudent
    current_user = implementation.current_user
    get_db = implementation.get_db
    need = implementation.need

    router = APIRouter()

    def _teacher_owns_student(db: Any, teacher: Any, student_id: int) -> Any:
        stu = db.scalar(
            select(User).where(
                User.id == int(student_id),
                User.school_id == int(teacher.school_id),
                User.role == "student",
            )
        )
        if not stu:
            raise HTTPException(404, "未找到该学生")
        if teacher.role != "admin":
            in_my_class = db.scalar(
                select(ClassStudent.id)
                .join(SchoolClass, SchoolClass.id == ClassStudent.class_id)
                .where(
                    ClassStudent.student_id == stu.id,
                    SchoolClass.school_id == teacher.school_id,
                    SchoolClass.teacher_id == teacher.id,
                )
            )
            if not in_my_class:
                raise HTTPException(403, "无权管理其他教师名下学生的授权")
        return stu

    def _parent_linked_student(db: Any, parent: Any, student_id: int) -> None:
        link = db.scalar(
            select(ParentStudent.id).where(
                ParentStudent.parent_id == int(parent.id),
                ParentStudent.student_id == int(student_id),
            )
        )
        if not link:
            raise HTTPException(403, "无权访问未关联学生的授权记录")

    def _serialize_consents(db: Any, school_id: int, student_id: int) -> list[dict[str, Any]]:
        rows = db.execute(
            select(consents_t)
            .where(
                consents_t.c.school_id == int(school_id),
                consents_t.c.student_id == int(student_id),
            )
            .order_by(desc(consents_t.c.id))
            .limit(20)
        ).all()
        return [
            {
                "id": int(r.id),
                "studentId": int(r.student_id),
                "status": str(r.status),
                "scope": str(r.scope),
                "policyVersion": str(r.policy_version),
                "verificationMethod": str(r.verification_method),
                "verifiedAt": r.verified_at.isoformat(timespec="seconds") if r.verified_at else None,
                "validUntil": r.valid_until.isoformat(timespec="seconds") if r.valid_until else None,
                "retentionUntil": r.retention_until.isoformat(timespec="seconds") if r.retention_until else None,
                "revokedAt": r.revoked_at.isoformat(timespec="seconds") if r.revoked_at else None,
            }
            for r in rows
        ]

    @router.get("/teacher/students/{student_id}/ai-consent")
    def teacher_get_consent(student_id: int, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "teacher", "admin")
        _teacher_owns_student(db, u, student_id)
        audits = db.execute(
            select(audits_t)
            .where(
                audits_t.c.school_id == int(u.school_id),
                audits_t.c.student_id == int(student_id),
            )
            .order_by(desc(audits_t.c.id))
            .limit(20)
        ).all()
        return {
            "complianceApproved": compliance_student_ai_enabled(),
            "consents": _serialize_consents(db, int(u.school_id), int(student_id)),
            "audits": [
                {
                    "action": str(a.action),
                    "scope": str(a.scope),
                    "detail": str(a.detail),
                    "createdAt": a.created_at.isoformat(timespec="seconds") if a.created_at else None,
                }
                for a in audits
            ],
        }

    @router.post("/teacher/students/{student_id}/ai-consent/token")
    def teacher_create_consent_token(
        student_id: int,
        b: TokenCreateBody,
        u: Any = Depends(current_user),
        db: Any = Depends(get_db),
    ):
        need(u, "teacher", "admin")
        _teacher_owns_student(db, u, student_id)
        return create_consent_token(
            db,
            implementation,
            teacher=u,
            student_id=student_id,
            scope=b.scope,
            policy_version=b.policyVersion,
            valid_days=b.validDays,
            ttl_hours=b.ttlHours,
        )

    @router.post("/teacher/students/{student_id}/ai-consent/proof")
    def teacher_record_proof_consent(
        student_id: int,
        b: ProofConsentBody,
        u: Any = Depends(current_user),
        db: Any = Depends(get_db),
    ):
        need(u, "teacher", "admin")
        _teacher_owns_student(db, u, student_id)
        return record_proof_consent(
            db,
            implementation,
            teacher=u,
            student_id=student_id,
            verification_method=b.verificationMethod,
            proof_digest=b.proofDigest,
            scope=b.scope,
            policy_version=b.policyVersion,
            valid_days=b.validDays,
        )

    @router.post("/teacher/students/{student_id}/ai-consent/revoke")
    def teacher_revoke_consent(
        student_id: int,
        b: RevokeBody,
        u: Any = Depends(current_user),
        db: Any = Depends(get_db),
    ):
        need(u, "teacher", "admin")
        _teacher_owns_student(db, u, student_id)
        return revoke_student_consent(
            db,
            implementation,
            school_id=int(u.school_id),
            student_id=int(student_id),
            actor_user_id=int(u.id),
            scope=b.scope,
            reason=b.reason,
        )

    @router.post("/parent/ai-consent/confirm")
    def parent_confirm_consent(
        b: TokenConfirmBody,
        u: Any = Depends(current_user),
        db: Any = Depends(get_db),
    ):
        need(u, "parent")
        return confirm_consent_token(
            db,
            implementation,
            raw_token=b.token,
            parent_user=u,
            expected_student_id=b.studentId,
        )

    @router.get("/parent/children/{student_id}/ai-consent")
    def parent_get_consent(student_id: int, u: Any = Depends(current_user), db: Any = Depends(get_db)):
        need(u, "parent")
        _parent_linked_student(db, u, student_id)
        return {
            "complianceApproved": compliance_student_ai_enabled(),
            "consents": _serialize_consents(db, int(u.school_id), int(student_id)),
        }

    @router.post("/parent/children/{student_id}/ai-consent/revoke")
    def parent_revoke_consent(
        student_id: int,
        b: RevokeBody,
        u: Any = Depends(current_user),
        db: Any = Depends(get_db),
    ):
        need(u, "parent")
        _parent_linked_student(db, u, student_id)
        return revoke_student_consent(
            db,
            implementation,
            school_id=int(u.school_id),
            student_id=int(student_id),
            actor_user_id=int(u.id),
            scope=b.scope,
            reason=b.reason or "parent_revoked",
        )

    app.include_router(router)
    app.state.guardian_consent_installed = True
    app.state.guardian_consent_router = router
    return router


__all__ = ["install_guardian_consent_views"]
