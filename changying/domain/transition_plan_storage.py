"""Persistence model installer for teacher-authored transition plans.

The table is additive and keyed by the durable student id. Saving a plan never
changes student grade, class membership, learning evidence, points, or mastery.
"""

from __future__ import annotations

from datetime import datetime
from types import ModuleType

from sqlalchemy import Column, DateTime, Integer, String, Table, Text


def install_transition_plan_model(implementation: ModuleType):
    Base = implementation.Base
    existing = Base.metadata.tables.get("student_transition_plans")
    if existing is not None:
        return existing

    table = Table(
        "student_transition_plans",
        Base.metadata,
        Column("id", Integer, primary_key=True),
        Column("school_id", Integer, nullable=False, index=True),
        Column("student_id", Integer, nullable=False, index=True),
        Column("teacher_id", Integer, nullable=False, index=True),
        Column("transition_type", String(40), nullable=False, default="阶段衔接"),
        Column("status", String(20), nullable=False, default="active", index=True),
        Column("previous_stage", Text, nullable=False, default=""),
        Column("next_stage_requirement", Text, nullable=False, default=""),
        Column("prerequisite_check_json", Text, nullable=False, default="[]"),
        Column("gaps_json", Text, nullable=False, default="[]"),
        Column("plan_json", Text, nullable=False, default="[]"),
        Column("holiday_intervention_json", Text, nullable=False, default="[]"),
        Column("opening_diagnosis_json", Text, nullable=False, default="[]"),
        Column("next_stage", Text, nullable=False, default=""),
        Column("created_at", DateTime, nullable=False, default=datetime.utcnow),
        Column("updated_at", DateTime, nullable=False, default=datetime.utcnow),
        Column("closed_at", DateTime, nullable=True),
    )
    return table


__all__ = ["install_transition_plan_model"]
