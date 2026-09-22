"""Teacher-confirmed transition-plan history for one durable student record."""

from __future__ import annotations

import json
from datetime import datetime
from types import ModuleType

from fastapi import Depends, HTTPException, Request

from changying.domain.transition_plan_storage import install_transition_plan_model
from changying.services.transition_plans import TransitionPlanService
from changying.web.v1_transition_snapshot import _authorized_student


_FIELDS = (
    "prerequisiteCheck", "gaps", "plan", "holidayIntervention", "openingDiagnosis",
)


def _json_list(value):
    if not isinstance(value, list):
        return []
    return [str(x).strip() for x in value if str(x).strip()][:50]


def _row(row):
    m = row._mapping if hasattr(row, "_mapping") else row
    return {
        "id": int(m["id"]),
        "studentID": int(m["student_id"]),
        "teacherID": int(m["teacher_id"]),
        "transitionType": m["transition_type"],
        "status": m["status"],
        "previousStage": m["previous_stage"],
        "nextStageRequirement": m["next_stage_requirement"],
        "prerequisiteCheck": json.loads(m["prerequisite_check_json"] or "[]"),
        "gaps": json.loads(m["gaps_json"] or "[]"),
        "plan": json.loads(m["plan_json"] or "[]"),
        "holidayIntervention": json.loads(m["holiday_intervention_json"] or "[]"),
        "openingDiagnosis": json.loads(m["opening_diagnosis_json"] or "[]"),
        "nextStage": m["next_stage"],
        "createdAt": m["created_at"].isoformat() if m["created_at"] else None,
        "updatedAt": m["updated_at"].isoformat() if m["updated_at"] else None,
        "closedAt": m["closed_at"].isoformat() if m["closed_at"] else None,
    }


def install_v1_transition_plan_routes(implementation: ModuleType) -> None:
    app = implementation.app
    if getattr(app.state, "v1_transition_plan_routes_installed", False):
        return

    table = install_transition_plan_model(implementation)
    # Additive table creation only. Existing tables/data are untouched.
    table.create(bind=implementation.engine, checkfirst=True)
    service = TransitionPlanService(table=table, select_fn=implementation.select, audit_log_model=implementation.AuditLog)

    @app.get("/v1/students/{sid}/transition-plans", include_in_schema=False)
    def list_transition_plans(sid: int, user=Depends(implementation.current_user), db=Depends(implementation.get_db)):
        _authorized_student(implementation, db, user, sid)
        rows = service.list_rows(db, school_id=int(user.school_id), student_id=int(sid))
        return {"studentID": sid, "plans": [_row(x) for x in rows]}

    @app.post("/v1/students/{sid}/transition-plans", include_in_schema=False)
    async def create_transition_plan(sid: int, request: Request, user=Depends(implementation.current_user), db=Depends(implementation.get_db)):
        if user.role not in {"teacher", "admin"}:
            raise HTTPException(403, "仅教师或管理员可保存衔接计划")
        _authorized_student(implementation, db, user, sid)
        body = await request.json()
        now = datetime.utcnow()
        values = {
            "school_id": int(user.school_id),
            "student_id": int(sid),
            "teacher_id": int(user.id),
            "transition_type": str(body.get("transitionType") or "阶段衔接")[:40],
            "status": "active",
            "previous_stage": str(body.get("previousStage") or "")[:4000],
            "next_stage_requirement": str(body.get("nextStageRequirement") or "")[:4000],
            "prerequisite_check_json": json.dumps(_json_list(body.get("prerequisiteCheck")), ensure_ascii=False),
            "gaps_json": json.dumps(_json_list(body.get("gaps")), ensure_ascii=False),
            "plan_json": json.dumps(_json_list(body.get("plan")), ensure_ascii=False),
            "holiday_intervention_json": json.dumps(_json_list(body.get("holidayIntervention")), ensure_ascii=False),
            "opening_diagnosis_json": json.dumps(_json_list(body.get("openingDiagnosis")), ensure_ascii=False),
            "next_stage": str(body.get("nextStage") or "")[:4000],
            "created_at": now,
            "updated_at": now,
        }
        saved = service.create(
            db, school_id=int(user.school_id), student_id=int(sid),
            teacher_id=int(user.id), values=values,
        )
        return _row(saved)

    @app.post("/v1/students/{sid}/transition-plans/{plan_id}/close", include_in_schema=False)
    def close_transition_plan(sid: int, plan_id: int, user=Depends(implementation.current_user), db=Depends(implementation.get_db)):
        if user.role not in {"teacher", "admin"}:
            raise HTTPException(403, "仅教师或管理员可关闭衔接计划")
        _authorized_student(implementation, db, user, sid)
        saved = service.close(
            db, school_id=int(user.school_id), student_id=int(sid),
            teacher_id=int(user.id), plan_id=int(plan_id),
        )
        if saved is None:
            raise HTTPException(404, "衔接计划不存在")
        return _row(saved)

    app.state.v1_transition_plan_routes_installed = True


__all__ = ["install_v1_transition_plan_routes"]
