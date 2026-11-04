"""晚托家庭作业的积分规则：按时完成 + 正确率阶梯调整。

只算数，不写库。加分的判定必须在服务端做，前端只展示。

规则（业务方 2026-11-03 定）：
- 按时完成：加基础分；超时不给这部分，但仍可做完。
- 正确率：以 60% 为中点，10 个百分点一档，上下各 3 分。
- 正确率要用首次批改结果；作业提交时正确率还未知，所以正确率部分**推迟到批改后结算**。
- 积分累计，扣分计入余额。
"""
from __future__ import annotations

from typing import Any

# 正确率阶梯：(最低百分比, 调整分)。降序匹配，第一个命中的生效。
ACCURACY_LADDER: list[tuple[int, int]] = [
    (90, 3),
    (80, 2),
    (70, 1),
    (60, 0),
    (50, -1),
    (40, -2),
    (0, -3),
]

MIDPOINT = 60
MAX_ADJUST = 3
FLOOR_AT_ZERO = True  # 业务方定：扣分扣到 0 为止，余额不为负
DEFAULT_ON_TIME_POINTS = 3  # 业务方定：按时完成 3 分
LATE_CARE_PRACTICE_MARKER = "晚托提问巩固练习"


def is_late_care_title(title: str | None) -> bool:
    """Whether an assignment title belongs to the late-care consolidation practice."""
    return LATE_CARE_PRACTICE_MARKER in str(title or "")


def accuracy_points(accuracy_percent: float) -> int:
    """正确率 → 调整分。60 附近为 0，>=90 加 3，<40 减 3。"""
    value = float(accuracy_percent)
    if value < 0:
        value = 0.0
    if value > 100:
        value = 100.0
    for floor, delta in ACCURACY_LADDER:
        if value >= floor:
            return delta
    return ACCURACY_LADDER[-1][1]


def pending_on_time(on_time: bool, base_points: int = DEFAULT_ON_TIME_POINTS) -> dict[str, Any]:
    """作业提交时只能结算"是否按时"；正确率留到批改后。"""
    points = int(base_points) if on_time else 0
    return {
        "source": "on_time_completion",
        "points": points,
        "onTime": bool(on_time),
        "settled": False,          # 还有正确率没结算
        "note": "按时完成" if on_time else "超时完成，不给按时分；仍可做完",
    }


def clamp_delta(delta: int, balance: int | None = None) -> int:
    """扣分不能把余额扣成负数：最多扣到 0。

    balance 为 None 时（还不知道余额）只做上限保护，不假设余额。
    """
    value = int(delta)
    if value >= 0:
        return value
    if balance is None:
        # 不知道余额就不敢扣：返回 0，由调用方补传余额后再结算。
        return 0
    return max(value, -max(0, int(balance)))


def settle_accuracy(
    accuracy_percent: float | None,
    *,
    graded: bool = True,
    balance: int | None = None,
) -> dict[str, Any]:
    """批改完成后结算正确率部分。

    - 没批改：不结算，返回 settled=False
    - 超期未批改（expired_days >= max_wait_days）：不再等，按 0 调整收口
    """
    if not graded or accuracy_percent is None:
        # 没批改就一直挂着，不设过期——过期会让迟批的作业永久失去结算机会。
        return {"source": "accuracy_adjustment", "points": 0, "settled": False,
                "note": "尚未批改，正确率部分待结算"}
    raw = accuracy_points(accuracy_percent)
    applied = clamp_delta(raw, balance)
    note = f"正确率 {round(float(accuracy_percent), 1)}%，调整 {applied:+d} 分"
    if applied != raw:
        note += f"（原本 {raw:+d}，扣到 0 为止）"
    return {
        "source": "accuracy_adjustment",
        "points": applied,
        "rawPoints": raw,
        "clamped": applied != raw,
        "settled": True,
        "accuracy": round(float(accuracy_percent), 1),
        "note": note,
    }


def total_for_assignment(
    on_time: bool,
    accuracy_percent: float | None,
    *,
    base_points: int = DEFAULT_ON_TIME_POINTS,
    graded: bool = True,
    balance: int | None = None,
) -> dict[str, Any]:
    """一次作业的总积分：按时部分 + 正确率部分。

    先计入按时分，再用"入账后的余额"限制定扣，避免先扣后加导致误判可扣额度。
    """
    first = pending_on_time(on_time, base_points)
    balance_after_on_time = None if balance is None else int(balance) + int(first["points"])
    second = settle_accuracy(accuracy_percent, graded=graded, balance=balance_after_on_time)
    return {
        "entries": [first, second],
        "total": int(first["points"]) + int(second["points"]),
        "fullySettled": bool(second["settled"]),
    }
