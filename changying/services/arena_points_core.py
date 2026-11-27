"""语数英通用知识地图与应试专项公共 PointLedger 里程碑积分结算内核（幂等 + 各科独立日上限）."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

ARENA_POINT_CATEGORY = "learning"
DAILY_POINTS_CAP = 30

NODE_LIT_POINTS = 3
NODE_MASTERED_POINTS = 5
NODE_REPAIR_POINTS = 2

SPRINT_TIER_POINTS: dict[str, int] = {
    "L2": 5,
    "L3": 8,
    "L4": 12,
}
SPRINT_TIER_LABELS: dict[str, str] = {
    "L2": "达标·银章",
    "L3": "熟练·金章",
    "L4": "冲刺·钻章",
}


@dataclass(frozen=True)
class SubjectPointsConfig:
    subject: str
    map_source: str
    sprint_source: str
    map_reason_prefix: str
    sprint_reason_prefix: str
    daily_cap: int = DAILY_POINTS_CAP

    @property
    def sources(self) -> tuple[str, str]:
        return (self.map_source, self.sprint_source)


def school_day_bounds_utc(now_utc: datetime | None = None) -> tuple[datetime, datetime, str]:
    """按学校本地时区（UTC+8）计算当日 UTC 起止时间与日期键."""
    now = now_utc or datetime.utcnow()
    local = now + timedelta(hours=8)
    day_key = local.strftime("%Y-%m-%d")
    start_local = datetime(local.year, local.month, local.day)
    start_utc = start_local - timedelta(hours=8)
    end_utc = start_utc + timedelta(days=1)
    return start_utc, end_utc, day_key


def student_class_id(implementation: Any, db: Any, user: Any) -> int | None:
    fn = getattr(implementation, "current_class_for", None)
    if callable(fn):
        try:
            cls = fn(db, int(user.id), int(user.school_id))
            if cls is not None:
                return int(cls.id)
        except Exception:
            pass
    return None


def today_earned(
    cfg: SubjectPointsConfig,
    implementation: Any,
    db: Any,
    user: Any,
    now_utc: datetime | None = None,
) -> int:
    PointLedger = implementation.PointLedger
    start_utc, end_utc, _ = school_day_bounds_utc(now_utc)
    val = db.scalar(
        select(func.coalesce(func.sum(PointLedger.points), 0)).where(
            PointLedger.school_id == int(user.school_id),
            PointLedger.student_id == int(user.id),
            PointLedger.source.in_(cfg.sources),
            PointLedger.created_at >= start_utc,
            PointLedger.created_at < end_utc,
        )
    )
    return max(0, int(val or 0))


def award_once(
    cfg: SubjectPointsConfig,
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

    today_sum = today_earned(cfg, implementation, db, user, now_utc=now_utc)
    room = max(0, cfg.daily_cap - today_sum)
    if room <= 0:
        return {"awarded": 0, "reason": reason, "status": "daily_cap_reached"}

    grant = min(int(raw_points), room)
    if grant <= 0:
        return {"awarded": 0, "reason": reason, "status": "zero"}

    class_id = student_class_id(implementation, db, user)
    row = PointLedger(
        school_id=int(user.school_id),
        student_id=int(user.id),
        class_id=class_id,
        actor_id=int(user.id),
        rule_id=None,
        category=ARENA_POINT_CATEGORY,
        points=grant,
        reason=reason[:160],
        note=(note + (f"（已触及{cfg.subject}今日上限截断）" if grant < raw_points else ""))[:1000],
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
    cfg: SubjectPointsConfig,
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
    _, _, day_key = school_day_bounds_utc(now_utc)

    if next_state in ("lit", "mastered") and prev_state not in ("lit", "mastered"):
        entries.append(
            award_once(
                cfg, implementation, db, user,
                source=cfg.map_source,
                raw_points=NODE_LIT_POINTS,
                reason=f"{cfg.map_reason_prefix}点亮：{node_key} {node_name}",
                note=f"首次点亮该{cfg.subject}知识节点",
                idempotency_key=f"{cfg.map_source}:lit:{uid}:{node_key}",
                related_id=related_id,
                now_utc=now_utc,
            )
        )

    if next_state == "mastered" and prev_state != "mastered":
        entries.append(
            award_once(
                cfg, implementation, db, user,
                source=cfg.map_source,
                raw_points=NODE_MASTERED_POINTS,
                reason=f"{cfg.map_reason_prefix}精通：{node_key} {node_name}",
                note=f"首次将该{cfg.subject}知识节点升至精通三星",
                idempotency_key=f"{cfg.map_source}:mastered:{uid}:{node_key}",
                related_id=related_id,
                now_utc=now_utc,
            )
        )

    if repaired:
        entries.append(
            award_once(
                cfg, implementation, db, user,
                source=cfg.map_source,
                raw_points=NODE_REPAIR_POINTS,
                reason=f"{cfg.map_reason_prefix}修补：{node_key} {node_name}",
                note=f"回图微测消除{cfg.subject}应试专项失分红标",
                idempotency_key=f"{cfg.map_source}:repair:{uid}:{node_key}:{day_key}",
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
    cfg: SubjectPointsConfig,
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
            entries.append(
                award_once(
                    cfg, implementation, db, user,
                    source=cfg.sprint_source,
                    raw_points=SPRINT_TIER_POINTS[code],
                    reason=f"{cfg.sprint_reason_prefix}{code}({SPRINT_TIER_LABELS[code]})：{title}",
                    note=f"首次在《{title}》达到 {code} {SPRINT_TIER_LABELS[code]}",
                    idempotency_key=f"{cfg.sprint_source}:tier:{uid}:{slug}:{code}",
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


def student_arena_points_summary(
    cfg: SubjectPointsConfig,
    implementation: Any,
    db: Any,
    user: Any,
) -> dict[str, Any]:
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
                PointLedger.source == cfg.map_source,
            )
        )
        or 0
    )
    sprint_total = int(
        db.scalar(
            select(func.coalesce(func.sum(PointLedger.points), 0)).where(
                PointLedger.school_id == sid,
                PointLedger.student_id == uid,
                PointLedger.source == cfg.sprint_source,
            )
        )
        or 0
    )
    earned = today_earned(cfg, implementation, db, user)
    return {
        "balance": balance,
        "todayEarned": earned,
        "dailyCap": cfg.daily_cap,
        "dailyRemaining": max(0, cfg.daily_cap - earned),
        "mapTotal": map_total,
        "sprintTotal": sprint_total,
    }


__all__ = [
    "ARENA_POINT_CATEGORY",
    "DAILY_POINTS_CAP",
    "NODE_LIT_POINTS",
    "NODE_MASTERED_POINTS",
    "NODE_REPAIR_POINTS",
    "SPRINT_TIER_LABELS",
    "SPRINT_TIER_POINTS",
    "SubjectPointsConfig",
    "award_once",
    "school_day_bounds_utc",
    "settle_map_node_milestones",
    "settle_sprint_tier_milestones",
    "student_arena_points_summary",
    "student_class_id",
    "today_earned",
]
