"""英语强应试专项引擎：按听/说/读/写四大能力入口、混合计时（听/说单题限时，读/写整体倒计时）、L1-L4 分级与地图双向联动."""
from __future__ import annotations

from typing import Any

from changying.services import arena_grade_profiles as agp
from changying.services import english_builtin_map as ebm
from changying.services import english_grade_curricula as egc
from changying.services import exam_sprints as math_sprints

GRACE_SECONDS = math_sprints.GRACE_SECONDS
TOP_LOSSES = math_sprints.TOP_LOSSES
TIERS = math_sprints.TIERS
TIER_BY_CODE = math_sprints.TIER_BY_CODE

ENGLISH_G5_SPRINTS: list[dict[str, Any]] = [
    {
        "slug": "listening-sprint",
        "subject": "英语",
        "grade": 5,
        "ability": "listening",
        "abilityLabel": "听",
        "title": "听 · 听力实战专项",
        "subtitle": "听音选词、听句选答语、短对话判断与短文理解，每题限播 2 遍 + 单题 20 秒作答",
        "icon": "🎧",
        "timingMode": "per_question",
        "perQuestionSec": 20,
        "maxPlays": 2,
        "timeLimitSec": 360,
        "questionCount": 10,
        "nodeKeys": ["E1-1", "E1-2", "E1-3", "E1-4", "E2-1", "E2-2", "E2-3", "E2-4", "E4-1", "E4-2", "E4-3"],
        "typeMix": {"listen_choice": 7, "listen_tf": 3},
    },
    {
        "slug": "speaking-phonics-sprint",
        "subject": "英语",
        "grade": 5,
        "ability": "speaking",
        "abilityLabel": "说",
        "title": "说 · 语音辨音与跟读专项",
        "subtitle": "自然拼读辨音、划线发音辨析与原声示范跟读，单题 20 秒节奏（老设备自动平滑降级）",
        "icon": "🎙️",
        "timingMode": "per_question",
        "perQuestionSec": 20,
        "maxPlays": 2,
        "timeLimitSec": 360,
        "questionCount": 10,
        "nodeKeys": ["E1-1", "E1-2", "E1-3", "E1-4", "E4-1"],
        "typeMix": {"phonics_choice": 6, "speak_read": 4},
    },
    {
        "slug": "reading-sprint",
        "subject": "英语",
        "grade": 5,
        "ability": "reading",
        "abilityLabel": "读",
        "title": "读 · 交际与阅读理解专项",
        "subtitle": "情景补全对话、短文细节定位与语篇完形选词，10 分钟整体倒计时可回看检查",
        "icon": "📖",
        "timingMode": "overall",
        "perQuestionSec": 0,
        "maxPlays": 0,
        "timeLimitSec": 600,
        "questionCount": 10,
        "nodeKeys": ["E2-1", "E2-2", "E2-3", "E2-4", "E4-1", "E4-2", "E4-3", "E4-4"],
        "typeMix": {"reading_choice": 7, "sentence_bank": 3},
    },
    {
        "slug": "writing-sprint",
        "subject": "英语",
        "grade": 5,
        "ability": "writing",
        "abilityLabel": "写",
        "title": "写 · 单词拼写与句子填空专项",
        "subtitle": "纯键盘单词拼写、词形语法填空与连词成句混合实战，12 分钟整体倒计时严判词形与时态",
        "icon": "✍️",
        "timingMode": "overall",
        "perQuestionSec": 0,
        "maxPlays": 2,
        "timeLimitSec": 720,
        "questionCount": 10,
        "nodeKeys": ["E1-4", "E2-1", "E2-2", "E2-3", "E2-4", "E3-1", "E3-2", "E3-3", "E3-4", "E4-2"],
        "typeMix": {"word_spell": 3, "sentence_fill": 4, "sentence_order": 3},
    },
]

ENGLISH_G3_SPRINTS = egc.ENGLISH_G3_SPRINTS
ENGLISH_G4_SPRINTS = egc.ENGLISH_G4_SPRINTS
ENGLISH_G6_SPRINTS = egc.ENGLISH_G6_SPRINTS

SPRINTS_BY_GRADE: dict[int, list[dict[str, Any]]] = {
    3: ENGLISH_G3_SPRINTS,
    4: ENGLISH_G4_SPRINTS,
    5: ENGLISH_G5_SPRINTS,
    6: ENGLISH_G6_SPRINTS,
}

ALL_ENGLISH_SPRINTS: list[dict[str, Any]] = (
    list(ENGLISH_G3_SPRINTS)
    + list(ENGLISH_G4_SPRINTS)
    + list(ENGLISH_G5_SPRINTS)
    + list(ENGLISH_G6_SPRINTS)
)

SPRINT_BY_SLUG = {s["slug"]: s for s in ALL_ENGLISH_SPRINTS}


def list_sprints(subject: str = "英语", grade: int | None = None) -> list[dict[str, Any]]:
    target_grade = agp.clamp_arena_grade(grade, ebm.DEFAULT_GRADE) if grade is not None else ebm.DEFAULT_GRADE
    pool = SPRINTS_BY_GRADE.get(target_grade, ENGLISH_G5_SPRINTS)
    return [dict(s) for s in pool if s["subject"] == subject]


def list_all_sprints(subject: str = "英语") -> list[dict[str, Any]]:
    return [dict(s) for s in ALL_ENGLISH_SPRINTS if s["subject"] == subject]


def get_sprint(slug: str) -> dict[str, Any] | None:
    s = SPRINT_BY_SLUG.get(slug)
    return dict(s) if s else None


def compose_sprint_questions(slug: str, seed: int = 0) -> list[dict[str, Any]]:
    """按听/说/读/写专项的多题型配额与节点轮转组卷."""
    sprint = SPRINT_BY_SLUG.get(slug)
    if not sprint:
        raise ValueError(f"Unknown English sprint: {slug}")
    nodes = list(sprint["nodeKeys"])
    targets = dict(sprint["typeMix"])
    want_count = int(sprint["questionCount"])
    picked: list[dict[str, Any]] = []
    used_ids: set[str] = set()
    used_texts: set[str] = set()

    turn = 0
    for qtype, quota in targets.items():
        got = 0
        attempts = 0
        while got < quota and len(picked) < want_count and attempts < len(nodes) * 4:
            nk = nodes[turn % len(nodes)]
            turn += 1
            attempts += 1
            cands = ebm.generate_node_questions(
                nk,
                count=3,
                seed=seed + turn,
                exclude_ids=used_ids,
                types={qtype},
            )
            hit = next((q for q in cands if q["text"] not in used_texts), None)
            if hit:
                picked.append(hit)
                used_ids.add(hit["id"])
                used_texts.add(hit["text"])
                got += 1

    # 若题型配额未凑满总题数，从目标节点池兜底补齐
    allowed_types = set(targets.keys())
    round_idx = 0
    while len(picked) < want_count and round_idx < len(nodes) * 4:
        nk = nodes[round_idx % len(nodes)]
        round_idx += 1
        cands = ebm.generate_node_questions(
            nk,
            count=3,
            seed=seed + round_idx + 17,
            exclude_ids=used_ids,
            types=allowed_types,
        )
        if not cands:
            cands = ebm.generate_node_questions(
                nk,
                count=2,
                seed=seed + round_idx + 31,
                exclude_ids=used_ids,
            )
        hit = next((q for q in cands if q["text"] not in used_texts), None)
        if hit:
            picked.append(hit)
            used_ids.add(hit["id"])
            used_texts.add(hit["text"])

    return picked


def evaluate_sprint_attempt(
    *,
    questions: list[dict[str, Any]],
    answers_by_id: dict[str, dict[str, Any]],
    elapsed_sec: int,
    time_limit_sec: int,
    auto_submitted: bool = False,
) -> dict[str, Any]:
    """统一判分英语专项并输出 L1-L4 段位、分题型统计、Top-3 失分点与地图反哺指令."""
    timed_out = bool(auto_submitted) or int(elapsed_sec) > int(time_limit_sec) + GRACE_SECONDS
    total_marks = 0
    earned_marks = 0
    correct_count = 0
    answered_count = 0
    hard_total = 0
    hard_correct = 0

    type_stats: dict[str, dict[str, Any]] = {}
    node_stats: dict[str, dict[str, Any]] = {}
    node_names = {k: n["name"] for k, n in ebm.NODE_BY_KEY.items()}
    details: list[dict[str, Any]] = []

    for q in questions:
        qid = q["id"]
        marks = int(q.get("marks", ebm.TYPE_POINTS.get(q["questionType"], 2)))
        total_marks += marks
        ans_obj = answers_by_id.get(qid) or {}
        sel = ans_obj.get("selected_index")
        txt = str(ans_obj.get("text_answer") or "").strip()
        has_answer = (sel is not None) or bool(txt)
        if has_answer:
            answered_count += 1
        ok = has_answer and ebm.grade_answer(q, selected_index=sel, text_answer=txt)
        if ok:
            earned_marks += marks
            correct_count += 1

        if q.get("level") == "hard":
            hard_total += 1
            if ok:
                hard_correct += 1

        qt = q["questionType"]
        ts = type_stats.setdefault(
            qt,
            {"type": qt, "label": ebm.TYPE_LABELS.get(qt, qt), "total": 0, "correct": 0, "marks": 0, "earned": 0},
        )
        ts["total"] += 1
        ts["marks"] += marks
        if ok:
            ts["correct"] += 1
            ts["earned"] += marks

        nk = q["nodeKey"]
        ns = node_stats.setdefault(
            nk,
            {
                "key": nk,
                "name": node_names.get(nk, nk),
                "total": 0,
                "correct": 0,
                "marks": 0,
                "lostMarks": 0,
                "hardCorrect": 0,
            },
        )
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
            "typeLabel": ebm.TYPE_LABELS.get(qt, qt),
            "text": q["text"],
            "marks": marks,
            "answered": has_answer,
            "correct": ok,
            "answer": q["answer"],
            "explanation": q.get("explanation", ""),
        })

    score_rate = (earned_marks / total_marks) if total_marks > 0 else 0.0
    hard_rate = (hard_correct / hard_total) if hard_total > 0 else score_rate
    tier = math_sprints.evaluate_tier(
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

    boost_by_tier = {"L2": 1, "L3": 2, "L4": 3}
    tier_boost = boost_by_tier.get(tier["code"], 0)
    map_updates: list[dict[str, Any]] = []
    for nk, ns in node_stats.items():
        if nk in loss_keys:
            map_updates.append({
                "nodeKey": nk,
                "attempts": ns["total"],
                "correct": ns["correct"],
                "hardCorrect": ns["hardCorrect"],
                "boostStars": 0,
                "needsRepair": True,
            })
        else:
            all_right = ns["correct"] == ns["total"] and ns["total"] > 0
            map_updates.append({
                "nodeKey": nk,
                "attempts": ns["total"],
                "correct": ns["correct"],
                "hardCorrect": ns["hardCorrect"],
                "boostStars": tier_boost if all_right else 0,
                "needsRepair": False,
            })

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
    "ALL_ENGLISH_SPRINTS",
    "ENGLISH_G3_SPRINTS",
    "ENGLISH_G4_SPRINTS",
    "ENGLISH_G5_SPRINTS",
    "ENGLISH_G6_SPRINTS",
    "GRACE_SECONDS",
    "SPRINTS_BY_GRADE",
    "SPRINT_BY_SLUG",
    "TIERS",
    "TIER_BY_CODE",
    "TOP_LOSSES",
    "compose_sprint_questions",
    "evaluate_sprint_attempt",
    "get_sprint",
    "list_all_sprints",
    "list_sprints",
]
