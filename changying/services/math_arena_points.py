"""数学知识地图与应试专项的全站 PointLedger 里程碑积分结算（基于 arena_points_core 薄配置）."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from changying.services import arena_points_core as core

MATH_MAP_SOURCE = "math_star_map"
MATH_SPRINT_SOURCE = "math_exam_sprint"
ARENA_POINT_SOURCES = (MATH_MAP_SOURCE, MATH_SPRINT_SOURCE)
ARENA_POINT_CATEGORY = core.ARENA_POINT_CATEGORY
DAILY_POINTS_CAP = core.DAILY_POINTS_CAP
NODE_LIT_POINTS = core.NODE_LIT_POINTS
NODE_MASTERED_POINTS = core.NODE_MASTERED_POINTS
NODE_REPAIR_POINTS = core.NODE_REPAIR_POINTS
SPRINT_TIER_POINTS = core.SPRINT_TIER_POINTS
SPRINT_TIER_LABELS = core.SPRINT_TIER_LABELS

_CFG = core.SubjectPointsConfig(
    subject="数学",
    map_source=MATH_MAP_SOURCE,
    sprint_source=MATH_SPRINT_SOURCE,
    map_reason_prefix="知识地图",
    sprint_reason_prefix="应试专项",
    daily_cap=DAILY_POINTS_CAP,
)

_school_day_bounds_utc = core.school_day_bounds_utc
_student_class_id = core.student_class_id


def settle_map_node_milestones(
    implementation: Any, db: Any, user: Any, *,
    node_key: str, node_name: str, prev_state: str, next_state: str,
    repaired: bool = False, related_id: int | None = None, now_utc: datetime | None = None,
) -> dict[str, Any]:
    return core.settle_map_node_milestones(
        _CFG, implementation, db, user,
        node_key=node_key, node_name=node_name, prev_state=prev_state, next_state=next_state,
        repaired=repaired, related_id=related_id, now_utc=now_utc,
    )


def settle_sprint_tier_milestones(
    implementation: Any, db: Any, user: Any, *,
    slug: str, title: str, tier_code: str,
    attempt_id: int | None = None, now_utc: datetime | None = None,
) -> dict[str, Any]:
    return core.settle_sprint_tier_milestones(
        _CFG, implementation, db, user,
        slug=slug, title=title, tier_code=tier_code,
        attempt_id=attempt_id, now_utc=now_utc,
    )


def student_arena_points_summary(implementation: Any, db: Any, user: Any) -> dict[str, Any]:
    return core.student_arena_points_summary(_CFG, implementation, db, user)


__all__ = [
    "ARENA_POINT_CATEGORY", "ARENA_POINT_SOURCES", "DAILY_POINTS_CAP",
    "MATH_MAP_SOURCE", "MATH_SPRINT_SOURCE",
    "NODE_LIT_POINTS", "NODE_MASTERED_POINTS", "NODE_REPAIR_POINTS", "SPRINT_TIER_POINTS",
    "settle_map_node_milestones", "settle_sprint_tier_milestones", "student_arena_points_summary",
]
