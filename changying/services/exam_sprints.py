"""强应试专项引擎：独立多题型限时挑战、严格倒计时判分、L1-L4 分级达标与地图联动.

设计原则：
- 与知识地图入口解耦：学生无需先点亮地图即可直接进入应试专项；
- 强应试：严格限时（倒计时归零自动交卷），未答题按 0 分计入失分；
- 分级达标：按限时得分率、难题表现与交卷配速评定 L1(铜) / L2(银·达标) / L3(金) / L4(钻)；
- 双向联动：达标专项中全对的知识点自动反哺点亮地图，Top-3 失分点标红为“待修补”并支持一键跳回地图。
"""
from __future__ import annotations

from typing import Any

from changying.services import math_builtin_map as mbm

GRACE_SECONDS = 15
TOP_LOSSES = 3

TIERS: list[dict[str, Any]] = [
    {"code": "L0", "rank": 0, "name": "未达标", "badge": "🎯", "passed": False, "color": "#667085"},
    {"code": "L1", "rank": 1, "name": "入门·铜章", "badge": "🥉", "passed": False, "color": "#b54708"},
    {"code": "L2", "rank": 2, "name": "达标·银章", "badge": "🥈", "passed": True, "color": "#344054"},
    {"code": "L3", "rank": 3, "name": "熟练·金章", "badge": "🥇", "passed": True, "color": "#d97706"},
    {"code": "L4", "rank": 4, "name": "冲刺·钻章", "badge": "💎", "passed": True, "color": "#1d4ed8"},
]
TIER_BY_CODE = {t["code"]: t for t in TIERS}

MATH_G5_SPRINTS: list[dict[str, Any]] = [
    {
        "slug": "calc-speed",
        "subject": "数学",
        "grade": 5,
        "title": "小数乘除速算专项",
        "subtitle": "围绕小数乘除、简便运算与大小规律的高频速算训练",
        "icon": "⚡",
        "timeLimitSec": 600,
        "questionCount": 10,
        "nodeKeys": ["M1-1", "M1-2", "M1-3", "M1-4", "M1-5"],
        "typeMix": {"calculation": 4, "single_choice": 2, "true_false": 2, "fill_blank": 2},
    },
    {
        "slug": "geometry-area",
        "subject": "数学",
        "grade": 5,
        "title": "多边形与图形运动专项",
        "subtitle": "对称平移旋转、平行四边形/三角形/梯形面积与单位换算",
        "icon": "📐",
        "timeLimitSec": 900,
        "questionCount": 10,
        "nodeKeys": ["M2-1", "M2-2", "M2-3", "M2-4", "M2-5"],
        "typeMix": {"single_choice": 2, "true_false": 2, "fill_blank": 2, "calculation": 2, "short_answer": 2},
    },
    {
        "slug": "word-algebra",
        "subject": "数学",
        "grade": 5,
        "title": "方程与应用题攻坚专项",
        "subtitle": "字母表示数、解方程、分段计费与进一/去尾法实战",
        "icon": "🧩",
        "timeLimitSec": 900,
        "questionCount": 10,
        "nodeKeys": ["M3-1", "M3-2", "M3-3", "M3-4"],
        "typeMix": {"single_choice": 2, "true_false": 1, "fill_blank": 2, "calculation": 2, "short_answer": 3},
    },
    {
        "slug": "visual-geometry-boss",
        "subject": "数学",
        "grade": 5,
        "title": "看图攻坚·图形与概率压轴专项",
        "subtitle": "系统精准画图：方格面积、图形运动、立体视图与转盘概率限时挑战",
        "icon": "🎨",
        "timeLimitSec": 900,
        "questionCount": 10,
        "preferVisual": True,
        "nodeKeys": ["M2-1", "M2-2", "M2-3", "M2-4", "M2-5", "M4-1", "M4-2"],
        "typeMix": {"single_choice": 5, "fill_blank": 3, "calculation": 1, "short_answer": 1},
    },
    {
        "slug": "fraction-solid-advanced",
        "subject": "数学",
        "grade": 5,
        "title": "因数、分数与长方体进阶专项",
        "subtitle": "覆盖因数倍数、分数通分加减、长方体体积、植树与找次品综合题型",
        "icon": "📚",
        "timeLimitSec": 900,
        "questionCount": 12,
        "nodeKeys": ["M1-6", "M1-7", "M1-8", "M2-6", "M2-7", "M3-5", "M3-6", "M4-3"],
        "typeMix": {"single_choice": 2, "fill_blank": 2, "calculation": 2, "error_diagnosis": 2, "short_answer": 2, "multi_step": 2},
    },
    {
        "slug": "math-comprehensive",
        "subject": "数学",
        "grade": 5,
        "title": "五年级数学全真限时模拟",
        "subtitle": "覆盖全部 24 个核心考点与 7 类题型的 20 分钟强应试全真模考",
        "icon": "🏆",
        "timeLimitSec": 1200,
        "questionCount": 15,
        "nodeKeys": [
            "M1-1", "M1-2", "M1-3", "M1-4", "M1-5", "M1-6", "M1-7", "M1-8",
            "M2-1", "M2-2", "M2-3", "M2-4", "M2-5", "M2-6", "M2-7",
            "M3-1", "M3-2", "M3-3", "M3-4", "M3-5", "M3-6",
            "M4-1", "M4-2", "M4-3",
        ],
        "typeMix": {"single_choice": 3, "true_false": 2, "fill_blank": 2, "calculation": 3, "error_diagnosis": 2, "short_answer": 2, "multi_step": 1},
    },
]
SPRINT_BY_SLUG = {s["slug"]: s for s in MATH_G5_SPRINTS}


def list_sprints(subject: str = "数学") -> list[dict[str, Any]]:
    return [dict(s) for s in MATH_G5_SPRINTS if s["subject"] == subject]


def get_sprint(slug: str) -> dict[str, Any] | None:
    s = SPRINT_BY_SLUG.get(slug)
    return dict(s) if s else None


def compose_sprint_questions(slug: str, seed: int = 0) -> list[dict[str, Any]]:
    """按专项配置的多题型配比与知识节点轮转组卷."""
    sprint = SPRINT_BY_SLUG.get(slug)
    if not sprint:
        raise ValueError(f"Unknown sprint: {slug}")
    nodes = list(sprint["nodeKeys"])
    targets = dict(sprint["typeMix"])
    want_count = int(sprint["questionCount"])
    picked: list[dict[str, Any]] = []
    used_ids: set[str] = set()
    used_texts: set[str] = set()
    have_type: dict[str, int] = {t: 0 for t in targets}

    # 按题型配额轮转节点抽题
    turn = 0
    for qtype, quota in targets.items():
        got_for_type = 0
        attempts = 0
        while got_for_type < quota and len(picked) < want_count and attempts < len(nodes) * 3:
            nk = nodes[turn % len(nodes)]
            turn += 1
            attempts += 1
            cands = mbm.generate_node_questions(
                nk,
                count=2,
                seed=seed + turn,
                exclude_ids=used_ids,
                types={qtype},
                prefer_visual=bool(sprint.get("preferVisual")),
            )
            hit = next((q for q in cands if q["text"] not in used_texts), None)
            if hit:
                picked.append(hit)
                used_ids.add(hit["id"])
                used_texts.add(hit["text"])
                have_type[qtype] = have_type.get(qtype, 0) + 1
                got_for_type += 1

    # 若题型配额未凑满总题数，兜底补齐
    round_idx = 0
    while len(picked) < want_count and round_idx < len(nodes) * 3:
        nk = nodes[round_idx % len(nodes)]
        round_idx += 1
        cands = mbm.generate_node_questions(nk, count=1, seed=seed + 100 + round_idx, exclude_ids=used_ids)
        if cands and cands[0]["text"] not in used_texts:
            picked.append(cands[0])
            used_ids.add(cands[0]["id"])
            used_texts.add(cands[0]["text"])

    # 按应试试卷常见顺序排题：选择 -> 判断 -> 填空 -> 计算 -> 易错辨析 -> 解决问题 -> 综合推理
    order = {
        "single_choice": 0,
        "true_false": 1,
        "fill_blank": 2,
        "calculation": 3,
        "error_diagnosis": 4,
        "short_answer": 5,
        "multi_step": 6,
    }
    picked.sort(key=lambda q: (order.get(q["questionType"], 9), q["nodeKey"]))
    return picked


def evaluate_tier(*, score_rate: float, hard_rate: float, elapsed_sec: int, time_limit_sec: int, timed_out: bool) -> dict[str, Any]:
    """根据强应试标准评定 L0-L4 分级达标等级."""
    if not timed_out and score_rate >= 0.95 and elapsed_sec <= int(time_limit_sec * 0.85):
        return dict(TIER_BY_CODE["L4"])
    if not timed_out and score_rate >= 0.85 and hard_rate >= 0.5:
        return dict(TIER_BY_CODE["L3"])
    if not timed_out and score_rate >= 0.75:
        return dict(TIER_BY_CODE["L2"])
    if score_rate >= 0.60:
        return dict(TIER_BY_CODE["L1"])
    return dict(TIER_BY_CODE["L0"])


def evaluate_sprint_attempt(
    *,
    questions: list[dict[str, Any]],
    answers_by_id: dict[str, dict[str, Any]],
    elapsed_sec: int,
    time_limit_sec: int,
    auto_submitted: bool = False,
) -> dict[str, Any]:
    """对一次强应试专项作答进行逐题判分、失分归因、分级达标评定与地图联动计算."""
    node_names = {n["key"]: n["name"] for n in mbm.MATH_G5_CORE_MAP["nodes"]}
    timed_out = elapsed_sec > (time_limit_sec + GRACE_SECONDS)

    total_marks = 0
    earned_marks = 0
    correct_count = 0
    answered_count = 0
    hard_total = 0
    hard_correct = 0

    type_stats: dict[str, dict[str, Any]] = {}
    node_stats: dict[str, dict[str, Any]] = {}
    details: list[dict[str, Any]] = []

    for q in questions:
        qid = q["id"]
        marks = int(q.get("marks") or mbm.TYPE_POINTS.get(q["questionType"], 2))
        total_marks += marks
        ans = answers_by_id.get(qid) or {}
        sel = ans.get("selected_index")
        txt = ans.get("text_answer", "")
        has_answer = (sel is not None) if q["questionType"] in ("single_choice", "true_false") else bool(str(txt).strip())
        if has_answer:
            answered_count += 1
        ok = mbm.grade_builtin_question(q, selected_index=sel, text_answer=txt) if has_answer else False
        if ok:
            earned_marks += marks
            correct_count += 1

        if q.get("level") == "hard":
            hard_total += 1
            if ok:
                hard_correct += 1

        qt = q["questionType"]
        ts = type_stats.setdefault(qt, {"type": qt, "label": mbm.TYPE_LABELS.get(qt, qt), "total": 0, "correct": 0, "marks": 0, "earned": 0})
        ts["total"] += 1
        ts["marks"] += marks
        if ok:
            ts["correct"] += 1
            ts["earned"] += marks

        nk = q["nodeKey"]
        ns = node_stats.setdefault(nk, {
            "key": nk,
            "name": node_names.get(nk, nk),
            "total": 0,
            "correct": 0,
            "marks": 0,
            "lostMarks": 0,
            "hardCorrect": 0,
        })
        ns["total"] += 1
        ns["marks"] += marks
        if ok:
            ns["correct"] += 1
            if q.get("level") == "hard":
                ns["hardCorrect"] += 1
        else:
            ns["lostMarks"] += marks

        details.append({
            "id": qid,
            "nodeKey": nk,
            "nodeName": node_names.get(nk, nk),
            "questionType": qt,
            "typeLabel": mbm.TYPE_LABELS.get(qt, qt),
            "text": q["text"],
            "marks": marks,
            "answered": has_answer,
            "correct": ok,
            "answer": q["answer"],
            "explanation": q.get("explanation", ""),
        })

    score_rate = (earned_marks / total_marks) if total_marks > 0 else 0.0
    hard_rate = (hard_correct / hard_total) if hard_total > 0 else score_rate
    tier = evaluate_tier(
        score_rate=score_rate,
        hard_rate=hard_rate,
        elapsed_sec=max(0, int(elapsed_sec)),
        time_limit_sec=int(time_limit_sec),
        timed_out=timed_out,
    )

    losses = sorted(
        (v for v in node_stats.values() if v["lostMarks"] > 0),
        key=lambda v: (-v["lostMarks"], v["key"]),
    )[:TOP_LOSSES]
    loss_keys = {x["key"] for x in losses}

    # 计算反哺知识地图的节点更新：专项达标(L2+)中全对节点点亮/升星，失分点标红待修补
    boost_by_tier = {"L2": 1, "L3": 2, "L4": 3}
    tier_boost = boost_by_tier.get(tier["code"], 0)
    map_updates: list[dict[str, Any]] = []
    for nk, ns in node_stats.items():
        if nk in loss_keys:
            map_updates.append({"nodeKey": nk, "attempts": ns["total"], "correct": ns["correct"],
                                "hardCorrect": ns["hardCorrect"], "boostStars": 0, "needsRepair": True})
        else:
            all_right = ns["correct"] == ns["total"] and ns["total"] > 0
            map_updates.append({"nodeKey": nk, "attempts": ns["total"], "correct": ns["correct"],
                                "hardCorrect": ns["hardCorrect"], "boostStars": tier_boost if all_right else 0,
                                "needsRepair": False})

    return {
        "earnedMarks": earned_marks,
        "totalMarks": total_marks,
        "scoreRate": round(score_rate * 100),
        "correctCount": correct_count,
        "questionCount": len(questions),
        "answeredCount": answered_count,
        "unansweredCount": len(questions) - answered_count,
        "elapsedSec": max(0, int(elapsed_sec)),
        "timeLimitSec": int(time_limit_sec),
        "timedOut": timed_out,
        "autoSubmitted": bool(auto_submitted),
        "tier": tier,
        "typeBreakdown": list(type_stats.values()),
        "topLosses": losses,
        "mapUpdates": map_updates,
        "details": details,
    }


__all__ = [
    "GRACE_SECONDS",
    "MATH_G5_SPRINTS",
    "TIERS",
    "TIER_BY_CODE",
    "TOP_LOSSES",
    "compose_sprint_questions",
    "evaluate_sprint_attempt",
    "evaluate_tier",
    "get_sprint",
    "list_sprints",
]
