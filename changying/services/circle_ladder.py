"""圆面积「退阶阶梯」：有序，不是平行选项。

学生卡在圆的面积时，从最简单的一级开始；答对上一级、答错退一级；
同一级连续错两次进兜底（微课 + 看答案拆解），看答案要打标，不计分。

这里是纯状态机 + 题目内容，不碰页面、不碰数据库；页面按它渲染即可。
"""
from __future__ import annotations

from typing import Any, Literal

# 每一级只比上一级多一个条件，数字统一用 r=4（L5 换回原题自己的数字）
LEVELS: list[dict[str, Any]] = [
    {"rank": 1, "gap": "square", "text": "边长 4 厘米的正方形，面积是多少？",
     "options": ["8 平方厘米", "12 平方厘米", "16 平方厘米"], "answer": 2,
     "why": "面积是边长乘边长，4×4=16"},
    {"rank": 2, "gap": "square", "text": "r = 4 厘米，r × r 是多少？",
     "answer_value": 16, "why": "r×r 就是 4×4；平方不是乘 2"},
    {"rank": 3, "gap": "circumference", "text": "3.14 × 16 是多少？",
     "answer_value": 50.24, "why": "先算 3.14×16；也可以拆成 3.14×10 + 3.14×6"},
    {"rank": 4, "gap": "application", "text": "r = 4 厘米的圆，面积是多少平方厘米？（π 取 3.14）",
     "answer_value": 50.24, "why": "S = πr² = 3.14 × 16 = 50.24 平方厘米"},
    {"rank": 5, "gap": "application", "text": "原题", "answer_value": None,
     "why": "用原题自己的数字与 π 取值"},
]

MAX_RANK = len(LEVELS)
MAX_MISSES = 2  # 同一级连续错两次 → 兜底
MISS_LIMIT_TEACHER = 4  # 整条阶梯累计错够这么多次 → 提醒老师
MAX_VISITS_PER_RANK = 3  # 同一级进入 3 次还没过 → 换讲法，不再上下打转
MAX_STEPS = 12  # 整条阶梯总步数上限；到顶直接转老师，不无限铺题


# 按知识点 key 取阶梯。圆面积（六上 4-3/4-4）先做一条；
# 其它知识点复用同一条内容前，必须先过老师审核，不能默默共享。
LADDERS: dict[str, list[dict[str, Any]]] = {
    "4-3": LEVELS,
    "4-4": LEVELS,
}
DEFAULT_LADDER_KEY = "4-3"


def ladder_for(node_key: str | None) -> list[dict[str, Any]]:
    """有专属阶梯就用；没有就退回默认那条（地图缺失/识别不出节点时也能用）。"""
    return LADDERS.get(str(node_key or "").strip(), LADDERS[DEFAULT_LADDER_KEY])


# 掌握度状态 → 起始级别。最高只跳到第 4 级：历史做对不等于今天不需要确认。
MAX_AUTO_START = 4
_START_BY_STATE = {"pass": 3, "fluent": 4, "weak": 1, "untested": 1}


def start_rank(node_state: str | None) -> int:
    rank = _START_BY_STATE.get(str(node_state or "").strip(), 1)
    return max(1, min(rank, MAX_AUTO_START))


def level_of(rank: int) -> dict[str, Any] | None:
    for item in LEVELS:
        if item["rank"] == rank:
            return item
    return None


def advance(rank: int, correct: bool, misses: int, total_misses: int = 0,
            visits: dict[str, int] | None = None, steps: int = 0) -> dict[str, Any]:
    """返回下一步：{action, rank, misses}。

    action:
      - "up"       答对，升一级（已到顶则 finished）
      - "down"     答错，退一级（已到底则 remains）
      - "finished" 到顶且答对
      - "fallback" 同一级连续错够次数，转兜底
    """
    rank = max(1, min(int(rank), MAX_RANK))
    misses = max(0, int(misses))
    total_misses = max(0, int(total_misses))
    steps = max(0, int(steps))
    if steps >= MAX_STEPS:
        return {"action": "handoff", "rank": max(1, min(int(rank), MAX_RANK)),
                "misses": max(0, int(misses)), "totalMisses": total_misses,
                "notifyTeacher": True, "visits": dict(visits or {})}

    visits = dict(visits or {})
    key = str(rank)
    visits[key] = int(visits.get(key, 0)) + 1

    def out(action: str, r: int, m: int, notify: bool) -> dict[str, Any]:
        return {"action": action, "rank": r, "misses": m,
                "totalMisses": total_misses, "notifyTeacher": notify, "visits": visits,
                "steps": steps + 1}

    if correct:
        notify = total_misses >= MISS_LIMIT_TEACHER
        if rank >= MAX_RANK:
            return out("finished", MAX_RANK, 0, notify)
        return out("up", rank + 1, 0, notify)

    misses += 1
    total_misses += 1
    # 累计错太多：即使还要继续，也要让老师知道这个学生卡在这一块
    notify = total_misses >= MISS_LIMIT_TEACHER
    if misses >= MAX_MISSES:
        return out("fallback", rank, misses, notify)
    # 这一级来过太多次，讲法该换了——而不是继续上下弹
    if visits[key] >= MAX_VISITS_PER_RANK:
        return out("fallback", rank, misses, notify)
    if rank <= 1:
        # 已经在最简单的一级，没得再退：再来一次同一级
        return out("remains", 1, misses, notify)
    return out("down", rank - 1, 0, notify)


def teacher_note(rank: int, total_misses: int) -> str:
    """给老师看的一行摘要：卡在哪一级、错了多少次。"""
    item = level_of(rank)
    gap = item["gap"] if item else "application"
    label = {"square": "平方与面积", "circumference": "圆周长",
             "application": "套用面积公式", "unit": "面积单位", "radius": "半径与直径"}.get(gap, gap)
    return f"圆面积退阶练习：停在第 {rank} 级（{label}），累计错 {total_misses} 次，尚未独立通过原题"


def fallback_actions() -> list[dict[str, str]]:
    """到底时给两个真实选项，不是一句"请老师"。"""
    return [
        {"key": "micro_lesson", "text": "看 15 秒微课：圆怎么拼成近似长方形",
         "note": "拼出来的是接近长方形，不是长方形本身"},
        {"key": "see_answer", "text": "看答案拆解",
         "note": "这次是看答案学会的，不算你已经掌握；下次自己再做对才算"},
    ]
