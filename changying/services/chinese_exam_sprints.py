"""语文强应试专项引擎：按试卷四大板块、混合计时（基础单题限时，古诗/阅读/微写作整体倒计时）、AI 主观批改与地图联动."""
from __future__ import annotations

from typing import Any

from changying.services import arena_grade_profiles as agp
from changying.services import chinese_ai_grader as caig
from changying.services import chinese_builtin_map as cbm
from changying.services import chinese_grade_curricula as cgc
from changying.services import chinese_low_grade_curricula as clgc
from changying.services import exam_sprints as math_sprints

GRACE_SECONDS = math_sprints.GRACE_SECONDS
TOP_LOSSES = math_sprints.TOP_LOSSES
TIERS = math_sprints.TIERS
TIER_BY_CODE = math_sprints.TIER_BY_CODE

CHINESE_G5_SPRINTS: list[dict[str, Any]] = [
    {
        "slug": "chinese-foundation-sprint",
        "subject": "语文",
        "grade": 5,
        "section": "foundation",
        "sectionLabel": "基",
        "title": "基础 · 字词句速通专项",
        "subtitle": "听写词语、多音字形近字、成语辨析与病句修辞，单题限时 20 秒快节奏抢答",
        "icon": "⚡",
        "timingMode": "per_question",
        "perQuestionSec": 20,
        "maxPlays": 2,
        "timeLimitSec": 360,
        "questionCount": 10,
        "nodeKeys": ["C1-1", "C1-2", "C1-3", "C1-4", "C2-1", "C2-2", "C2-3", "C2-4"],
        "typeMix": {"dictation_spell": 3, "basic_choice": 4, "error_spot": 2, "sentence_choice": 1},
    },
    {
        "slug": "chinese-poetry-sprint",
        "subject": "语文",
        "grade": 5,
        "section": "poetry",
        "sectionLabel": "诗",
        "title": "古诗文 · 名句默写与赏析专项",
        "subtitle": "配普通话朗诵音频，精准默写必背古诗名句、理解诗意与小古文实词，10 分钟整体倒计时",
        "icon": "📜",
        "timingMode": "overall",
        "perQuestionSec": 0,
        "maxPlays": 0,
        "timeLimitSec": 600,
        "questionCount": 10,
        "nodeKeys": ["C3-1", "C3-2", "C3-3", "C3-4"],
        "typeMix": {"poem_fill": 4, "reading_choice": 6},
    },
    {
        "slug": "chinese-reading-sprint",
        "subject": "语文",
        "grade": 5,
        "section": "reading",
        "sectionLabel": "读",
        "title": "阅读 · 现代文阅读理解专项",
        "subtitle": "记叙文 + 说明文双篇实战，客观细节定位 + AI 实时批改简答题，15 分钟整体倒计时",
        "icon": "📖",
        "timingMode": "overall",
        "perQuestionSec": 0,
        "maxPlays": 0,
        "timeLimitSec": 900,
        "questionCount": 8,
        "nodeKeys": ["C4-1", "C4-2", "C4-3"],
        "typeMix": {"reading_choice": 6, "reading_short": 2},
    },
    {
        "slug": "chinese-writing-sprint",
        "subject": "语文",
        "grade": 5,
        "section": "writing",
        "sectionLabel": "写",
        "title": "表达 · 审题润色与微写作专项",
        "subtitle": "审题立意、病句修改、句子升格 + AI 实时批改 100 字微片段写作，15 分钟整体倒计时",
        "icon": "🖋️",
        "timingMode": "overall",
        "perQuestionSec": 0,
        "maxPlays": 0,
        "timeLimitSec": 900,
        "questionCount": 8,
        "nodeKeys": ["C2-2", "C2-4", "C4-3", "C4-4"],
        "typeMix": {"error_spot": 2, "sentence_choice": 2, "reading_choice": 2, "micro_writing": 2},
    },
]

SPRINTS_BY_GRADE: dict[int, list[dict[str, Any]]] = {
    1: clgc.CHINESE_G1_SPRINTS,
    2: clgc.CHINESE_G2_SPRINTS,
    3: cgc.CHINESE_G3_SPRINTS,
    4: cgc.CHINESE_G4_SPRINTS,
    5: CHINESE_G5_SPRINTS,
    6: cgc.CHINESE_G6_SPRINTS,
}

ALL_CHINESE_SPRINTS: list[dict[str, Any]] = (
    list(clgc.CHINESE_G1_SPRINTS)
    + list(clgc.CHINESE_G2_SPRINTS)
    + list(cgc.CHINESE_G3_SPRINTS)
    + list(cgc.CHINESE_G4_SPRINTS)
    + list(CHINESE_G5_SPRINTS)
    + list(cgc.CHINESE_G6_SPRINTS)
)

SPRINT_BY_SLUG: dict[str, dict[str, Any]] = {s["slug"]: s for s in ALL_CHINESE_SPRINTS}


def list_sprints(subject: str = "语文", grade: int | None = None) -> list[dict[str, Any]]:
    target_grade = cbm.DEFAULT_GRADE if grade is None else agp.clamp_arena_grade(grade, cbm.DEFAULT_GRADE)
    pool = SPRINTS_BY_GRADE.get(target_grade, CHINESE_G5_SPRINTS)
    return [dict(s) for s in pool if s["subject"] == subject]


def list_all_sprints(subject: str = "语文") -> list[dict[str, Any]]:
    return [dict(s) for s in ALL_CHINESE_SPRINTS if s["subject"] == subject]


def get_sprint(slug: str) -> dict[str, Any] | None:
    s = SPRINT_BY_SLUG.get(slug)
    return dict(s) if s else None


def compose_sprint_questions(slug: str, seed: int = 0) -> list[dict[str, Any]]:
    sprint = SPRINT_BY_SLUG.get(slug)
    if not sprint:
        raise ValueError(f"Unknown Chinese sprint: {slug}")
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
            cands = cbm.generate_node_questions(
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

    allowed_types = set(targets.keys())
    round_idx = 0
    while len(picked) < want_count and round_idx < len(nodes) * 4:
        nk = nodes[round_idx % len(nodes)]
        round_idx += 1
        cands = cbm.generate_node_questions(
            nk,
            count=3,
            seed=seed + round_idx + 17,
            exclude_ids=used_ids,
            types=allowed_types,
        )
        if not cands:
            cands = cbm.generate_node_questions(
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
    implementation: Any | None = None,
    db: Any | None = None,
    school_id: int | None = None,
    ai_caller: Any | None = None,
) -> dict[str, Any]:
    """统一判分语文专项（客观瞬时判分 + 主观 AI 批改/规则兜底）并输出 L1-L4 与地图联动."""
    timed_out = bool(auto_submitted) or int(elapsed_sec) > int(time_limit_sec) + GRACE_SECONDS

    # 先批量批改本卷所有主观题（阅读简答 / 微片段写作）
    subj_pairs: list[tuple[dict[str, Any], str]] = []
    for q in questions:
        if q.get("questionType") in cbm.SUBJECTIVE_TYPES:
            ans_obj = answers_by_id.get(q["id"]) or {}
            subj_pairs.append((q, str(ans_obj.get("text_answer") or "")))
    subj_grades = caig.grade_subjective_items(
        subj_pairs,
        implementation=implementation,
        db=db,
        school_id=school_id,
        ai_caller=ai_caller,
    )

    total_marks = 0
    earned_marks = 0
    correct_count = 0
    answered_count = 0
    hard_total = 0
    hard_correct = 0

    type_stats: dict[str, dict[str, Any]] = {}
    node_stats: dict[str, dict[str, Any]] = {}
    node_names = {k: n["name"] for k, n in cbm.NODE_BY_KEY.items()}
    details: list[dict[str, Any]] = []

    for q in questions:
        qid = q["id"]
        qt = q["questionType"]
        marks = int(q.get("marks", cbm.TYPE_POINTS.get(qt, 2)))
        total_marks += marks
        ans_obj = answers_by_id.get(qid) or {}
        sel = ans_obj.get("selected_index")
        txt = str(ans_obj.get("text_answer") or "").strip()
        has_answer = (sel is not None) or bool(txt)
        if has_answer:
            answered_count += 1

        ai_comment = ""
        grading_mode = "objective"
        if qt in cbm.SUBJECTIVE_TYPES:
            sg = subj_grades.get(qid) or cbm.grade_subjective_rule_fallback(q, txt)
            got_marks = int(sg["earnedMarks"])
            ok = bool(sg["passed"])
            ai_comment = str(sg.get("comment") or "")
            grading_mode = str(sg.get("gradingMode") or "rule_fallback")
        else:
            ok = has_answer and cbm.grade_objective_answer(q, selected_index=sel, text_answer=txt)
            got_marks = marks if ok else 0

        earned_marks += got_marks
        if ok:
            correct_count += 1

        if q.get("level") == "hard":
            hard_total += 1
            if ok:
                hard_correct += 1

        ts = type_stats.setdefault(
            qt,
            {"type": qt, "label": cbm.TYPE_LABELS.get(qt, qt), "total": 0, "correct": 0, "marks": 0, "earned": 0},
        )
        ts["total"] += 1
        ts["marks"] += marks
        ts["earned"] += got_marks
        if ok:
            ts["correct"] += 1

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
        if got_marks < marks:
            ns["lostMarks"] += (marks - got_marks)

        details.append({
            "id": qid,
            "nodeKey": nk,
            "nodeName": node_names.get(nk, nk),
            "questionType": qt,
            "typeLabel": cbm.TYPE_LABELS.get(qt, qt),
            "text": q["text"],
            "marks": marks,
            "earnedMarks": got_marks,
            "answered": has_answer,
            "correct": ok,
            "answer": q.get("sampleAnswer") or q["answer"],
            "explanation": q.get("explanation", ""),
            "aiComment": ai_comment,
            "gradingMode": grading_mode,
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
    "ALL_CHINESE_SPRINTS",
    "CHINESE_G5_SPRINTS",
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
