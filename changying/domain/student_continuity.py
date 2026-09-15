"""Stable V1 vocabulary for a student's continuous development record.

These small, storage-neutral contracts let the existing legacy database feed the
V1 interface without prematurely changing production tables.  Future migrations
can map the same concepts to first-class tables while keeping student identity
stable across classes, terms, organisations and teaching modes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class TeachingMode(StrEnum):
    INSTITUTION = "institution"
    SCHOOL = "school"


class TeachingCycle(StrEnum):
    TERM = "term"
    WINTER = "winter"
    SUMMER = "summer"


class MasteryStage(StrEnum):
    NOT_YET = "not_yet"
    LEARNING = "learning"
    BASIC = "basic"
    STABLE = "stable"


class CompletionActor(StrEnum):
    STUDENT = "student"
    PARENT_ASSISTED = "parent_assisted"
    PARENT_SUBMITTED = "parent_submitted"
    TEACHER_RECORDED = "teacher_recorded"


class DataDomain(StrEnum):
    STUDENT = "student"
    SCHOOL = "school"
    INSTITUTION = "institution"
    FAMILY = "family"
    AUTHORIZED_SHARE = "authorized_share"


class IdentityRole(StrEnum):
    SCHOOL_ADMIN = "school_admin"
    SCHOOL_TEACHER = "school_teacher"
    INSTITUTION_ADMIN = "institution_admin"
    INSTITUTION_TEACHER = "institution_teacher"
    PARENT = "parent"
    STUDENT = "student"


@dataclass(frozen=True)
class UserIdentity:
    """One selectable identity owned by a real login account."""

    account_id: int
    role: IdentityRole
    domain_id: str
    display_name: str


@dataclass(frozen=True)
class StudentRecordRef:
    """The durable student key shared by all teaching-cycle references."""

    student_id: int
    current_grade: int | None
    active_cycle_ids: tuple[str, ...] = ()
    guardian_ids: tuple[int, ...] = ()


@dataclass
class TransitionPlan:
    """V1 placeholder shape for grade and school-transition planning."""

    student_id: int
    transition_type: str
    previous_stage: str = ""
    next_stage_requirement: str = ""
    prerequisite_check: list[str] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)
    plan: list[str] = field(default_factory=list)
    holiday_intervention: list[str] = field(default_factory=list)
    opening_diagnosis: list[str] = field(default_factory=list)
    next_stage: str = ""


__all__ = [
    "CompletionActor",
    "DataDomain",
    "IdentityRole",
    "MasteryStage",
    "StudentRecordRef",
    "TeachingCycle",
    "TeachingMode",
    "TransitionPlan",
    "UserIdentity",
]
