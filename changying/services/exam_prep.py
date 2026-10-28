"""应试专项：在考试范围内组模拟卷、按知识点拆出失分点（纯函数，不连数据库）.

An exam goal covers some units of the school's published knowledge map. The mock paper spreads its questions
over the knowledge points in those units (a mix of levels, easier first is not assumed); after the pupils hand
it in, every wrong or unanswered question is counted against its knowledge point. Each pupil gets at most
``TOP_LOSSES`` points to work on, the ones that lost the most marks, so the advice stays short enough to act on.
"""
from __future__ import annotations

from typing import Any, Iterable

TOP_LOSSES = 3
MOCK_MIN, MOCK_MAX = 6, 40
LEVEL_CYCLE = ("medium", "basic", "hard", "medium", "basic")      # per point: mostly medium and basic, some hard


def scope_nodes(m: dict[str, Any], unit_keys: Iterable[str]) -> list[dict[str, Any]]:
    """The knowledge points an exam covers: every enabled, question-bearing point of the chosen units, in map order."""
    wanted = set(unit_keys)
    return [n for n in m["nodes"] if n["unit"] in wanted and n["kind"] != "display" and n["enabled"]]


def compose(nodes: list[dict[str, Any]], pools: dict[str, list[tuple[int, str]]], count: int) -> list[tuple[str, int]]:
    """Pick ``count`` questions spread evenly over the points (round robin), each point cycling through levels.

    ``pools`` maps a point to its usable questions as (question id, level). A question is used once even when
    it sits under two points. Points that run out simply stop taking questions.
    """
    left = {n["key"]: sorted(pools.get(n["key"], []), key=lambda p: p[0]) for n in nodes}
    turn = {n["key"]: 0 for n in nodes}
    used: set[int] = set()
    out: list[tuple[str, int]] = []
    while len(out) < count:
        moved = False
        for n in nodes:
            if len(out) >= count:
                break
            key = n["key"]
            options = [p for p in left[key] if p[0] not in used]
            if not options:
                continue
            want = LEVEL_CYCLE[turn[key] % len(LEVEL_CYCLE)]
            pick = next((p for p in options if p[1] == want), options[0])
            turn[key] += 1
            used.add(pick[0])
            out.append((key, pick[0]))
            moved = True
        if not moved:
            break
    return out


def losses(plan: list[tuple[str, int]], answers: dict[int, bool]) -> dict[str, dict[str, int]]:
    """Per point: questions asked and questions lost (wrong or left unanswered)."""
    out: dict[str, dict[str, int]] = {}
    for key, qid in plan:
        row = out.setdefault(key, {"asked": 0, "lost": 0})
        row["asked"] += 1
        row["lost"] += answers.get(qid) is not True
    return out


def top_losses(per_point: dict[str, dict[str, int]], order: list[str], limit: int = TOP_LOSSES) -> list[str]:
    """The points that lost the most questions (ties: higher share lost, then map order); points with no loss never."""
    rank = {k: i for i, k in enumerate(order)}
    lost = [k for k, v in per_point.items() if v["lost"] > 0]
    lost.sort(key=lambda k: (-per_point[k]["lost"], -per_point[k]["lost"] / per_point[k]["asked"], rank.get(k, len(rank))))
    return lost[:limit]


def score(plan: list[tuple[str, int]], answers: dict[int, bool]) -> int:
    """Percentage of the paper answered correctly (every question weighs the same)."""
    return round(100 * sum(answers.get(q) is True for _, q in plan) / len(plan)) if plan else 0


def class_points(plan: list[tuple[str, int]], handed_in: list[dict[int, bool]]) -> dict[str, dict[str, int]]:
    """Per point over the pupils who handed in: questions asked in total and lost in total."""
    total: dict[str, dict[str, int]] = {}
    for answers in handed_in:
        for key, row in losses(plan, answers).items():
            t = total.setdefault(key, {"asked": 0, "lost": 0})
            t["asked"] += row["asked"]
            t["lost"] += row["lost"]
    return total


__all__ = ["LEVEL_CYCLE", "MOCK_MAX", "MOCK_MIN", "TOP_LOSSES", "class_points", "compose", "losses", "scope_nodes", "score",
           "top_losses"]
