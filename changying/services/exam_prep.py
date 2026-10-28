"""应试专项：在考试范围内组模拟卷、按知识点拆出失分点、专项练习、再测对比（纯函数，不连数据库）.

An exam goal covers some units of the school's published knowledge map. The mock paper spreads its questions
over the knowledge points in those units; after the pupils hand it in, every wrong or unanswered question costs
its marks (by question type, like a printed paper) against its knowledge point. Each pupil gets at most
``TOP_LOSSES`` points to work on, the ones that lost the most marks, so the advice stays short enough to act on.
A retest asks the same number of questions per point with questions not used before, so the two can be compared.
"""
from __future__ import annotations

from typing import Any, Iterable

TOP_LOSSES = 3
MOCK_MIN, MOCK_MAX = 6, 40
LEVEL_CYCLE = ("medium", "basic", "hard", "medium", "basic")      # per point: mostly medium and basic, some hard
DRILL_ORDER = {"basic": 0, "medium": 1, "hard": 2}                 # practice climbs: basic first
# Marks per question type, as on a printed primary maths paper.
TYPE_POINTS = {"single_choice": 2, "true_false": 1, "fill_blank": 2, "calculation": 3, "short_answer": 5}
TYPE_LABELS = {"single_choice": "选择", "true_false": "判断", "fill_blank": "填空", "calculation": "计算", "short_answer": "解决问题"}

Pool = list[tuple[int, str] | tuple[int, str, str]]


def scope_nodes(m: dict[str, Any], unit_keys: Iterable[str]) -> list[dict[str, Any]]:
    """The knowledge points an exam covers: every enabled, question-bearing point of the chosen units, in map order."""
    wanted = set(unit_keys)
    return [n for n in m["nodes"] if n["unit"] in wanted and n["kind"] != "display" and n["enabled"]]


def type_targets(sample_types: list[str], count: int) -> dict[str, int]:
    """How many questions of each type a paper of ``count`` questions needs to follow a sample paper's mix."""
    known = [t for t in sample_types if t in TYPE_POINTS]
    if not known:
        return {}
    share = {t: known.count(t) / len(known) for t in dict.fromkeys(known)}
    out = {t: int(count * s) for t, s in share.items()}
    for t in sorted(share, key=lambda t: -(count * share[t] - out[t]))[: count - sum(out.values())]:
        out[t] += 1                                          # largest remainders get the leftover questions
    return out


def compose(nodes: list[dict[str, Any]], pools: dict[str, Pool], count: int,
            targets: dict[str, int] | None = None, avoid: set[int] | None = None) -> list[tuple[str, int]]:
    """Pick ``count`` questions spread evenly over the points (round robin), each point cycling through levels.

    ``pools`` maps a point to its usable questions as (question id, level[, type]). A question is used once even
    when it sits under two points; ``avoid`` holds questions that must not be used (an earlier paper). With
    ``targets`` (type -> count) a type that has reached its share is only taken when nothing else is left.
    """
    left = {n["key"]: sorted(pools.get(n["key"], []), key=lambda p: p[0]) for n in nodes}
    turn = {n["key"]: 0 for n in nodes}
    used: set[int] = set(avoid or ())
    have: dict[str, int] = {}
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
            if targets:
                room = [p for p in options if len(p) > 2 and have.get(p[2], 0) < targets.get(p[2], 0)]
                options = room or options
            want = LEVEL_CYCLE[turn[key] % len(LEVEL_CYCLE)]
            pick = next((p for p in options if p[1] == want), options[0])
            turn[key] += 1
            used.add(pick[0])
            if len(pick) > 2:
                have[pick[2]] = have.get(pick[2], 0) + 1
            out.append((key, pick[0]))
            moved = True
        if not moved:
            break
    return out


def retest_plan(base: list[tuple[str, int]], pools: dict[str, Pool], avoid: set[int]) -> list[tuple[str, int]]:
    """As many questions per point as the base paper asked, none of them used before; points short of fresh
    questions get what is left."""
    want: dict[str, int] = {}
    for key, _ in base:
        want[key] = want.get(key, 0) + 1
    used = set(avoid)
    out: list[tuple[str, int]] = []
    for key, n in want.items():
        fresh = sorted((p for p in pools.get(key, []) if p[0] not in used), key=lambda p: (DRILL_ORDER.get(p[1], 1), p[0]))
        for p in _spread_levels(fresh, n):
            used.add(p[0])
            out.append((key, p[0]))
    return out


def _spread_levels(options: list[Any], n: int) -> list[Any]:
    """Up to ``n`` of the options, cycling through the levels like a mock paper does."""
    left, out = list(options), []
    for i in range(n):
        if not left:
            break
        want = LEVEL_CYCLE[i % len(LEVEL_CYCLE)]
        pick = next((p for p in left if p[1] == want), left[0])
        left.remove(pick)
        out.append(pick)
    return out


def drill_picks(focus: list[str], pools: dict[str, Pool], avoid: set[int], per_point: int) -> list[tuple[str, int]]:
    """Practice for a pupil's focus points: per point up to ``per_point`` questions not seen before, basic first."""
    used = set(avoid)
    out: list[tuple[str, int]] = []
    for key in focus:
        fresh = sorted((p for p in pools.get(key, []) if p[0] not in used), key=lambda p: (DRILL_ORDER.get(p[1], 1), p[0]))
        for p in fresh[:per_point]:
            used.add(p[0])
            out.append((key, p[0]))
    return out


def losses(plan: list[tuple[str, int]], answers: dict[int, bool], points: dict[int, int] | None = None) -> dict[str, dict[str, int]]:
    """Per point: questions asked and lost (wrong or left unanswered), and the marks at stake and lost."""
    out: dict[str, dict[str, int]] = {}
    for key, qid in plan:
        w = (points or {}).get(qid, 1)
        row = out.setdefault(key, {"asked": 0, "lost": 0, "marks": 0, "lostMarks": 0})
        miss = answers.get(qid) is not True
        row["asked"] += 1
        row["lost"] += miss
        row["marks"] += w
        row["lostMarks"] += w if miss else 0
    return out


def top_losses(per_point: dict[str, dict[str, int]], order: list[str], limit: int = TOP_LOSSES) -> list[str]:
    """The points that lost the most marks (ties: higher share lost, then map order); points with no loss never."""
    rank = {k: i for i, k in enumerate(order)}

    def lost(k: str) -> int:
        return per_point[k].get("lostMarks", per_point[k]["lost"])

    def share(k: str) -> float:
        return lost(k) / (per_point[k].get("marks") or per_point[k]["asked"])

    keys = [k for k in per_point if lost(k) > 0]
    keys.sort(key=lambda k: (-lost(k), -share(k), rank.get(k, len(rank))))
    return keys[:limit]


def score(plan: list[tuple[str, int]], answers: dict[int, bool], points: dict[int, int] | None = None) -> int:
    """Percentage of the paper's marks earned."""
    total = sum((points or {}).get(q, 1) for _, q in plan)
    got = sum((points or {}).get(q, 1) for _, q in plan if answers.get(q) is True)
    return round(100 * got / total) if total else 0


def class_points(plan: list[tuple[str, int]], handed_in: list[dict[int, bool]], points: dict[int, int] | None = None) -> dict[str, dict[str, int]]:
    """Per point over the pupils who handed in: questions and marks, asked and lost, in total."""
    total: dict[str, dict[str, int]] = {}
    for answers in handed_in:
        for key, row in losses(plan, answers, points).items():
            t = total.setdefault(key, {"asked": 0, "lost": 0, "marks": 0, "lostMarks": 0})
            for k in t:
                t[k] += row[k]
    return total


def compare(before: dict[str, dict[str, int]], after: dict[str, dict[str, int]], focus: list[str]) -> list[dict[str, Any]]:
    """For the points a pupil was told to work on: share of marks lost before and after (None when not asked)."""
    def rate(row: dict[str, int] | None) -> int | None:
        if not row or not row.get("marks"):
            return None
        return round(100 * row["lostMarks"] / row["marks"])

    out = []
    for key in focus:
        b, a = rate(before.get(key)), rate(after.get(key))
        verdict = "未再测" if a is None else ("已补上" if a == 0 else ("有进步" if b is not None and a < b else "还要练"))
        out.append({"key": key, "before": b, "after": a, "verdict": verdict})
    return out


def countdown(days: int) -> dict[str, str]:
    """What the class should do now (advice, for the teacher) and at home (home, for parents), by days left to the exam."""
    if days < 0:
        return {"stage": "考后", "advice": "考试已经结束。可以把真题卷导入题库，再发一次对照，看看失分点有没有补上。",
                "home": "考试结束了，和孩子一起看看哪些题做对了、哪些还不会。"}
    if days == 0:
        return {"stage": "考试日", "advice": "今天考试：不再练新题，提醒学生看清题目、检查单位和计算。",
                "home": "今天考试，提醒孩子看清题目、写完后检查单位和计算。"}
    if days <= 3:
        return {"stage": "考前三天", "advice": "只回看错题和易错点，不做新难题，保证睡眠。",
                "home": "考前几天只回看错题，不做新的难题，保证睡眠。"}
    if days <= 7:
        return {"stage": "冲刺", "advice": "再测后仍失分的知识点继续补；每天少量、做对为主，控制难题比例。",
                "home": "每天花一点时间做老师布置的练习，以做对为主，不必加量。"}
    if days <= 21:
        return {"stage": "专项", "advice": "每个学生只练自己失分最多的 3 个知识点；练完发一次再测，看有没有补上。",
                "home": "每天花 15 分钟左右把老师布置的专项练习做完；不会的题先看讲解再做。"}
    return {"stage": "摸底", "advice": "先发一份模拟卷摸底，找出每个学生的失分点，再开始专项练习。",
            "home": "老师会先用模拟卷了解孩子的情况，请提醒孩子按时、独立完成。"}


def report(pupil: str, paper_title: str, now: dict[str, Any], before: dict[str, Any] | None, focus: list[dict[str, Any]],
           drill: dict[str, Any] | None, plan: dict[str, str], exam: str) -> dict[str, Any]:
    """A parent report built only from recorded results; nothing is guessed or ranked."""
    lines = [f"{pupil}完成了《{paper_title}》，得分 {now['score']} 分（按卷面分值计算）。"]
    if before is not None:
        diff = now["score"] - before["score"]
        lines.append(f"上一份卷子 {before['score']} 分，这次{'提高了 ' + str(diff) + ' 分' if diff > 0 else ('持平' if diff == 0 else '少了 ' + str(-diff) + ' 分')}。")
    if focus:
        lines.append("这次失分最多的地方：" + "；".join(f"{f['name']}（{f['lost']}/{f['asked']} 题没做对）" for f in focus) + "。")
    else:
        lines.append("这次卷子全部做对，保持节奏即可。")
    if drill:
        lines.append(f"老师已针对这些知识点布置专项练习（{drill['questionCount']} 题）" +
                     (f"，已完成，做对 {drill['correct']} 题。" if drill.get("handedIn") else "，孩子在“作业”里完成。"))
    return {"title": f"{exam} · 提分报告", "lines": lines, "stage": plan["stage"], "advice": plan["home"],
            "focus": [{"name": f["name"], "lost": f["lost"], "asked": f["asked"]} for f in focus]}


__all__ = ["DRILL_ORDER", "LEVEL_CYCLE", "MOCK_MAX", "MOCK_MIN", "TOP_LOSSES", "TYPE_LABELS", "TYPE_POINTS", "class_points",
           "compare", "compose", "countdown", "drill_picks", "losses", "report", "retest_plan", "scope_nodes", "score",
           "top_losses", "type_targets"]
