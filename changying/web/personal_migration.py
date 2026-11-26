"""Audited operator workflow for converting a single-teacher school to Personal Free Edition."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select


class OperatorConvertPersonalBody(BaseModel):
    confirm: bool = False
    deactivate_extra_admins: bool = True
    note: str = ""


def install_personal_migration_routes(implementation: Any) -> APIRouter:
    app = implementation.app
    if getattr(app.state, "personal_migration_installed", False):
        return app.state.personal_migration_router

    School = implementation.School
    User = implementation.User
    SchoolClass = implementation.SchoolClass
    SubscriptionEvent = implementation.SubscriptionEvent
    commercial_operator = implementation.commercial_operator
    get_db = implementation.get_db
    ensure_subscription = implementation.ensure_subscription
    ensure_personal_student_list = implementation.ensure_personal_student_list
    operator_school_payload = implementation.operator_school_payload
    operator_snapshot = implementation._operator_snapshot
    commercial_operation = implementation.commercial_operation

    router = APIRouter()

    def _evaluate_conversion(db: Any, school_id: int) -> tuple[Any, dict[str, Any], Any, list[Any]]:
        school = db.get(School, school_id)
        if not school:
            raise HTTPException(404, "学校不存在")

        active_teachers = list(
            db.scalars(
                select(User)
                .where(User.school_id == school_id, User.role == "teacher", User.active == True)
                .order_by(User.id)
            ).all()
        )
        active_admins = list(
            db.scalars(
                select(User)
                .where(User.school_id == school_id, User.role == "admin", User.active == True)
                .order_by(User.id)
            ).all()
        )
        students_count = (
            db.scalar(
                select(func.count())
                .select_from(User)
                .where(User.school_id == school_id, User.role == "student", User.active == True)
            )
            or 0
        )
        parents_count = (
            db.scalar(
                select(func.count())
                .select_from(User)
                .where(User.school_id == school_id, User.role == "parent", User.active == True)
            )
            or 0
        )
        classes_count = (
            db.scalar(
                select(func.count())
                .select_from(SchoolClass)
                .where(SchoolClass.school_id == school_id)
            )
            or 0
        )

        owner = None
        extra_admins: list[Any] = []
        eligible = False
        reason = ""

        if school.individual:
            reason = "该工作室已经是个人免费版，无需重复转换"
        elif len(active_teachers) > 1:
            reason = (
                f"该校存在 {len(active_teachers)} 名活跃教师，不能直接整校转为个人免费版"
                "（请先停用多余教师账号，或为独立老师另行注册个人工作室）"
            )
        elif len(active_teachers) == 1:
            owner = active_teachers[0]
            extra_admins = active_admins
            eligible = True
        elif len(active_admins) == 1:
            owner = active_admins[0]
            extra_admins = []
            eligible = True
        elif len(active_admins) > 1:
            reason = f"该校没有活跃教师，且存在 {len(active_admins)} 名活跃管理员，请先保留 1 名负责人后再转换"
        else:
            reason = "该校没有活跃的教师或管理员账号，无法转为个人免费版"

        preview = {
            "schoolID": int(school.id),
            "schoolName": school.name,
            "alreadyIndividual": bool(school.individual),
            "eligible": eligible,
            "reason": reason,
            "owner": (
                {"id": int(owner.id), "name": owner.name, "username": owner.username, "role": owner.role}
                if owner is not None
                else None
            ),
            "extraAdmins": [
                {"id": int(a.id), "name": a.name, "username": a.username}
                for a in extra_admins
            ],
            "activeTeachers": [
                {"id": int(t.id), "name": t.name, "username": t.username}
                for t in active_teachers
            ],
            "counts": {
                "students": int(students_count),
                "parents": int(parents_count),
                "classes": int(classes_count),
            },
        }
        return school, preview, owner, extra_admins

    @router.get("/operator/schools/{school_id}/convert-personal/preview")
    def operator_convert_personal_preview(
        school_id: int,
        _ok: bool = Depends(commercial_operator),
        db: Any = Depends(get_db),
    ):
        _school, preview, _owner, _extra = _evaluate_conversion(db, school_id)
        return preview

    @router.post("/operator/schools/{school_id}/convert-personal")
    def operator_convert_personal(
        school_id: int,
        b: OperatorConvertPersonalBody,
        _ok: bool = Depends(commercial_operator),
        db: Any = Depends(get_db),
    ):
        if not b.confirm:
            raise HTTPException(400, "请勾选确认后再执行转为个人免费版")
        school, preview, owner, extra_admins = _evaluate_conversion(db, school_id)
        if not preview["eligible"] or owner is None:
            raise HTTPException(400, preview["reason"] or "当前学校不满足转为个人免费版的条件")
        if extra_admins and not b.deactivate_extra_admins:
            raise HTTPException(400, "该校存在旧管理员账号，请确认停用多余管理员后再转换")

        before = operator_snapshot(db, school_id)
        before["individual"] = bool(school.individual)
        before["ownerBefore"] = {"id": int(owner.id), "username": owner.username, "role": owner.role}

        school.individual = True
        school.active = True
        owner.role = "teacher"

        deactivated: list[str] = []
        extra_ids = [int(a.id) for a in extra_admins]
        for adm in extra_admins:
            adm.active = False
            deactivated.append(adm.username)

        if extra_ids:
            orphan_classes = db.scalars(
                select(SchoolClass).where(
                    SchoolClass.school_id == school_id,
                    SchoolClass.teacher_id.in_(extra_ids),
                )
            ).all()
            for cls in orphan_classes:
                cls.teacher_id = owner.id

        has_any_class = db.scalar(
            select(SchoolClass.id).where(SchoolClass.school_id == school_id, SchoolClass.teacher_id == owner.id).limit(1)
        )
        if not has_any_class:
            ensure_personal_student_list(db, school_id, owner.id)

        sub = ensure_subscription(db, school_id)
        sub.plan_code = "free"
        sub.status = "active"
        sub.trial_ends_at = None
        sub.current_period_ends_at = None
        sub.grace_ends_at = None
        sub.updated_at = datetime.utcnow()

        detail_parts = [f"owner={owner.username}"]
        if deactivated:
            detail_parts.append("deactivated_admins=" + ",".join(deactivated))
        if (b.note or "").strip():
            detail_parts.append((b.note or "").strip()[:400])
        detail = "; ".join(detail_parts)

        db.flush()
        after = operator_snapshot(db, school_id)
        after["individual"] = True
        after["ownerAfter"] = {"id": int(owner.id), "username": owner.username, "role": owner.role}
        after["deactivatedAdmins"] = deactivated

        db.add(
            SubscriptionEvent(
                school_id=school_id,
                action="convert_personal",
                plan_code="free",
                status="active",
                detail=detail[:1000],
            )
        )
        commercial_operation(db, school_id, "convert_personal", before, after, detail[:1000])
        db.commit()

        return {
            "ok": True,
            "school": operator_school_payload(db, school_id),
            "owner": {"id": int(owner.id), "name": owner.name, "username": owner.username, "role": owner.role},
            "deactivatedAdmins": deactivated,
        }

    app.include_router(router)
    app.state.personal_migration_installed = True
    app.state.personal_migration_router = router
    return router


__all__ = ["install_personal_migration_routes"]
