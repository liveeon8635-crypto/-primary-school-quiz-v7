"""Persistence model installer for teacher-authored transition plans.

The table is additive and keyed by the durable student id. Saving a plan never
changes student grade, class membership, learning evidence, points, or mastery.
"""

from __future__ import annotations

from datetime import datetime
from types import ModuleType


def install_transition_plan_model(implementation: ModuleType):
    Base = implementation.Base
    existing = Base.metadata.tables.get("student_transition_plans")
    if existing is not None:
        return existing

    sa = implementation
    table = sa.Table(
        "student_transition_plans",
        Base.metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("school_id", sa.Integer, nullable=False, index=True),
        sa.Column("student_id", sa.Integer, nullable=False, index=True),
        sa.Column("teacher_id", sa.Integer, nullable=False, index=True),
        sa.Column("transition_type", sa.String(40), nullable=False, default="阶段衔接"),
        sa.Column("status", sa.String(20), nullable=False, default="active", index=True),
        sa.Column("previous_stage", sa.Text, nullable=False, default=""),
        sa.Column("next_stage_requirement", sa.Text, nullable=False, default=""),
        sa.Column("prerequisite_check_json", sa.Text, nullable=False, default="[]"),
        sa.Column("gaps_json", sa.Text, nullable=False, default="[]"),
        sa.Column("plan_json", sa.Text, nullable=False, default="[]"),
        sa.Column("holiday_intervention_json", sa.Text, nullable=False, default="[]"),
        sa.Column("opening_diagnosis_json", sa.Text, nullable=False, default="[]"),
        sa.Column("next_stage", sa.Text, nullable=False, default=""),
        sa.Column("created_at", sa.DateTime, nullable=False, default=datetime.utcnow),
        sa.Column("updated_at", sa.DateTime, nullable=False, default=datetime.utcnow),
        sa.Column("closed_at", sa.DateTime, nullable=True),
    )
    return table


__all__ = ["install_transition_plan_model"]
