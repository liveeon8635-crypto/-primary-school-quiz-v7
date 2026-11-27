"""语文知识地图与应试专项的全站 PointLedger 里程碑积分结算（幂等 + 语文独立每日 30 分上限）."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from changying.services import math_arena_points as mapts

CHINESE_MAP_SOURCE = "chinese_star_map"
CHINESE_SPRINT_SOURCE = "chinese_exam_sprint"
ARENA_POINT_SOURCES = (CHINESE_MAP_SOURCE, CHINESE_SPRINT_SOURCE)
ARENA_POINT_CATEGORY = "learning"

DAILY_POINTS_CAP = 30

NODE_LIT_POINTS = mapts.NODE_LIT_POINTS
NODE_MASTERED_POINTS = mapts.NODE_MASTERED_POINTS
NODE_REPAIR_POINTS = mapts.NODE_REPAIR_POINTS
SPRINT_TIER_POINTS = mapts.SPRINT_TIER_POINTS
SPRINT_TIER_LABELS = mapts.SPRINT_TIER_LABELS


def _today_earned(implementation: Any, db: Any, user: Any, now_utc: datetime | None = None) -> int:
    PointLedger = implementation.PointLedger
    start_utc, end_utc, _ = mapts._school_day_bounds_utc(now_utc)
    val = db.scalar(
        select(func.coalesce(func.sum(PointLedger.points), 0)).where(
            PointLedger.school_id == int(user.school_id),
            PointLedger.student_id == int(user.id),
            PointLedger.source.in_(ARENA_POINT_SOURCES),
            PointLedger.created_at >= start_utc,
            PointLedger.created_at < end_utc,
        )
    )
    return max(0, int(val or 0))


def _award_once(
    implementation: Any,
    db: Any,
    user: Any,
    *,
    source: str,
    raw_points: int,
    reason: str,
    note: str,
    idempotency_key: str,
    related_id: int | None = None,
    now_utc: datetime | None = None,
) -> dict[str, Any]:
    PointLedger = implementation.PointLedger
    existing = db.scalar(
        select(PointLedger.id).where(PointLedger.idempotency_key == idempotency_key)
    )
    if existing is not None:
        return {"awarded": 0, "reason": reason, "status": "already_awarded"}

    today_sum = _today_earned(implementation, db, user, now_utc=now_utc)
    room = max(0, DAILY_POINTS_CAP - today_sum)
    if room <= 0:
        return {"awarded": 0, "reason": reason, "status": "daily_cap_reached"}

    grant = min(int(raw_points), room)
    if grant <= 0:
        return {"awarded": 0, "reason": reason, "status": "zero"}

    class_id = mapts._student_class_id(implementation, db, user)
    row = PointLedger(
        school_id=int(user.school_id),
        student_id=int(user.id),
        class_id=class_id,
        actor_id=int(user.id),
        rule_id=None,
        category=ARENA_POINT_CATEGORY,
        points=grant,
        reason=reason[:160],
        note=(note + ("（已触及语文今日上限截断）" if grant < raw_points else ""))[:1000],
        source=source,
        related_id=related_id,
        idempotency_key=idempotency_key,
    )
    try:
        with db.begin_nested():
            db.add(row)
            db.flush()
    except IntegrityError:
        return {"awarded": 0, "reason": reason, "status": "already_awarded"}

    reconcile = getattr(implementation, "reconcile_auto_rewards", None)
    if callable(reconcile):
        try:
            reconcile(db, int(user.school_id), int(user.id), class_id=class_id)
        except Exception:
            pass

    return {
        "awarded": grant,
        "reason": reason,
        "status": "capped" if grant < raw_points else "awarded",
    }


def settle_map_node_milestones(
    implementation: Any,
    db: Any,
    user: Any,
    *,
    node_key: str,
    node_name: str,
    prev_state: str,
    next_state: str,
    repaired: bool = False,
    related_id: int | None = None,
    now_utc: datetime | None = None,
) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    uid = int(user.id)
    _, _, day_key = mapts._school_day_bounds_utc(now_utc)

    if next_state in ("lit", "mastered") and prev_state not in ("lit", "mastered"):
        entries.append(
            _award_once(
                implementation,
                db,
                user,
                source=CHINESE_MAP_SOURCE,
                raw_points=NODE_LIT_POINTS,
                reason=f"语文地图点亮：{node_key} {node_name}",
                note="首次点亮该语文知识节点",
                idempotency_key=f"{CHINESE_MAP_SOURCE}:lit:{uid}:{node_key}",
                related_id=related_id,
                now_utc=now_utc,
            )
        )

    if next_state == "mastered" and prev_state != "mastered":
        entries.append(
            _award_once(
                implementation,
                db,
                user,
                source=CHINESE_MAP_SOURCE,
                raw_points=NODE_MASTERED_POINTS,
                reason=f"语文地图精通：{node_key} {node_name}",
                note="首次将该语文知识节点升至精通三星",
                idempotency_key=f"{CHINESE_MAP_SOURCE}:mastered:{uid}:{node_key}",
                related_id=related_id,
                now_utc=now_utc,
            )
        )

    if repaired:
        entries.append(
            _award_once(
                implementation,
                db,
                user,
                source=CHINESE_MAP_SOURCE,
                raw_points=NODE_REPAIR_POINTS,
                reason=f"语文地图修补：{node_key} {node_name}",
                note="回图微测消除语文应试专项失分红标",
                idempotency_key=f"{CHINESE_MAP_SOURCE}:repair:{uid}:{node_key}:{day_key}",
                related_id=related_id,
                now_utc=now_utc,
            )
        )

    total = sum(int(e["awarded"]) for e in entries)
    capped = any(e["status"] in ("daily_cap_reached", "capped") for e in entries)
    return {
        "total": total,
        "capped": capped,
        "entries": [e for e in entries if e["awarded"] > 0],
    }


def settle_sprint_tier_milestones(
    implementation: Any,
    db: Any,
    user: Any,
    *,
    slug: str,
    title: str,
    tier_code: str,
    attempt_id: int | None = None,
    now_utc: datetime | None = None,
) -> dict[str, Any]:
    order = {"L2": 2, "L3": 3, "L4": 4}
    rank = order.get(tier_code, 0)
    if rank <= 0:
        return {"total": 0, "capped": False, "entries": []}

    uid = int(user.id)
    entries: list[dict[str, Any]] = []
    for code in ("L2", "L3", "L4"):
        if order[code] <= rank:
            pts = SPRINT_TIER_POINTS[code]
            entries.append(
                _award_once(
                    implementation,
                    db,
                    user,
                    source=CHINESE_SPRINT_SOURCE,
                    raw_points=pts,
                    reason=f"语文专项{code}({SPRINT_TIER_LABELS[code]})：{title}",
                    note=f"首次在《{title}》达到 {code} {SPRINT_TIER_LABELS[code]}",
                    idempotency_key=f"{CHINESE_SPRINT_SOURCE}:tier:{uid}:{slug}:{code}",
                    related_id=attempt_id,
                    now_utc=now_utc,
                )
            )
    total = sum(int(e["awarded"]) for e in entries)
    capped = any(e["status"] in ("daily_cap_reached", "capped") for e in entries)
    return {
        "total": total,
        "capped": capped,
        "entries": [e for e in entries if e["awarded"] > 0],
    }


def student_arena_points_summary(implementation: Any, db: Any, user: Any) -> dict[str, Any]:
    PointLedger = implementation.PointLedger
    sid, uid = int(user.school_id), int(user.id)
    balance = int(
        db.scalar(
            select(func.coalesce(func.sum(PointLedger.points), 0)).where(
                PointLedger.school_id == sid,
                PointLedger.student_id == uid,
            )
        )
        or 0
    )
    map_total = int(
        db.scalar(
            select(func.coalesce(func.sum(PointLedger.points), 0)).where(
                PointLedger.school_id == sid,
                PointLedger.student_id == uid,
                PointLedger.source == CHINESE_MAP_SOURCE,
            )
        )
        or 0
    )
    sprint_total = int(
        db.scalar(
            select(func.coalesce(func.sum(PointLedger.points), 0)).where(
                PointLedger.school_id == sid,
                PointLedger.student_id == uid,
                PointLedger.source == CHINESE_SPRINT_SOURCE,
            )
        )
        or 0
    )
    today_earned = _today_earned(implementation, db, user)
    return {
        "balance": balance,
        "todayEarned": today_earned,
        "dailyCap": DAILY_POINTS_CAP,
        "dailyRemaining": max(0, DAILY_POINTS_CAP - today_earned),
        "mapTotal": map_total,
        "sprintTotal": sprint_total,
    }


__all__ = [
    "ARENA_POINT_CATEGORY",
    "ARENA_POINT_SOURCES",
    "CHINESE_MAP_SOURCE",
    "CHINESE_SPRINT_SOURCE",
    "DAILY_POINTS_CAP",
    "NODE_LIT_POINTS",
    "NODE_MASTERED_POINTS",
    "NODE_REPAIR_POINTS",
    "SPRINT_TIER_POINTS",
    "settle_map_node_milestones",
    "settle_sprint_tier_milestones",
    "student_arena_points_summary",
]
