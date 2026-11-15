"""Cross-scene learning evidence collector for Knowledge Map teacher views.

Collects raw, per-source evidence from:
- 周末课 (weekend_answers, weekend_written_submissions + hint logs)
- 晚托作业助手 (homework_ai_knowledge)
- 知识地图 (knowledge_map_runs, map-bound Submission attempts)
- 应试专项 (exam_goals, exam_goal_papers, exam_goal_drills + Submission)

Never modifies or merges into the Knowledge Map mastery formula.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any

from sqlalchemy import func, select

_STRIP = re.compile(r"[\s·・、，,。.：:；;（）()\[\]【】\-—_/]+")
_WRITTEN_RESULT_LABEL = {
    "correct": "已批改（正确）",
    "partial": "已批改（部分正确）",
    "wrong": "已批改（有误）",
    "pending": "待批改",
}


def _norm(text: Any) -> str:
    return _STRIP.sub("", str(text or "")).lower()


def _iso(dt: Any) -> str:
    if isinstance(dt, datetime):
        return dt.isoformat(timespec="seconds")
    return str(dt or "")


def _map_indexes(map_dict: dict[str, Any]) -> tuple[dict[str, str], dict[int, list[str]]]:
    """Build normalized-node-name -> nodeKey and questionId -> [nodeKeys] maps."""
    name_to_key: dict[str, str] = {}
    qid_to_keys: dict[int, list[str]] = {}
    for node in map_dict.get("nodes") or []:
        nkey = str(node.get("key") or "")
        nname = _norm(node.get("name"))
        if nkey and nname:
            name_to_key[nname] = nkey
        levels = node.get("questions") or {}
        if isinstance(levels, dict):
            for qids in levels.values():
                for qid in qids or []:
                    try:
                        qid_to_keys.setdefault(int(qid), [])
                        if nkey and nkey not in qid_to_keys[int(qid)]:
                            qid_to_keys[int(qid)].append(nkey)
                    except (TypeError, ValueError):
                        continue
    return name_to_key, qid_to_keys


def _match_node_keys(text: Any, name_to_key: dict[str, str]) -> list[str]:
    normed = _norm(text)
    if not normed:
        return []
    if normed in name_to_key:
        return [name_to_key[normed]]
    matched: list[str] = []
    for nname, nkey in name_to_key.items():
        if len(nname) >= 2 and (nname in normed or normed in nname):
            if nkey not in matched:
                matched.append(nkey)
    return matched


def collect_cross_scene_evidence(
    db: Any,
    implementation: Any,
    map_row: Any,
    map_dict: dict[str, Any],
    student_ids: list[int],
) -> dict[int, list[dict[str, Any]]]:
    """Return per-student cross-scene learning evidence items without altering mastery."""
    out: dict[int, list[dict[str, Any]]] = {int(sid): [] for sid in student_ids}
    if not student_ids:
        return out

    md = implementation.Base.metadata
    school_id = int(map_row.school_id)
    name_to_key, qid_to_keys = _map_indexes(map_dict)
    Submission = implementation.Submission
    TQ = implementation.TeachingQuestion

    # 1. 周末课选择题作答 + 提示记录
    w_ans = md.tables.get("weekend_answers")
    if w_ans is not None:
        tq_rows = {
            int(q.id): q
            for q in db.scalars(select(TQ).where(TQ.school_id == school_id)).all()
        }
        rows = db.execute(
            select(
                w_ans.c.student_id, w_ans.c.question_id, w_ans.c.correct,
                w_ans.c.max_hint, w_ans.c.created_at,
            ).where(w_ans.c.school_id == school_id, w_ans.c.student_id.in_(student_ids))
        ).all()
        for r in rows:
            tq = tq_rows.get(int(r.question_id))
            kp = str(getattr(tq, "knowledge", "") or "")
            hint_lvl = int(r.max_hint or 0)
            out[int(r.student_id)].append({
                "source": "weekend",
                "sourceLabel": "周末课（选择题）",
                "nodeKeys": _match_node_keys(kp, name_to_key),
                "time": _iso(r.created_at),
                "count": 1,
                "gradingStatus": "已判分（正确）" if r.correct else "已判分（待巩固）",
                "helpStatus": f"使用过提示（{hint_lvl}级）" if hint_lvl > 0 else "独立完成（无提示）",
                "summary": kp or str(getattr(tq, "stem", "") or "周末课随堂选择题")[:40],
            })

    # 2. 周末课文字/照片题作答 + 提示记录
    w_sub = md.tables.get("weekend_written_submissions")
    w_q = md.tables.get("weekend_written_questions")
    w_hlog = md.tables.get("weekend_written_hint_log")
    if w_sub is not None and w_q is not None:
        hint_max: dict[tuple[int, int, int], int] = {}
        if w_hlog is not None:
            for sid, stid, qid, lvl in db.execute(
                select(
                    w_hlog.c.session_id, w_hlog.c.student_id, w_hlog.c.question_id,
                    func.max(w_hlog.c.level),
                ).where(w_hlog.c.school_id == school_id, w_hlog.c.student_id.in_(student_ids))
                .group_by(w_hlog.c.session_id, w_hlog.c.student_id, w_hlog.c.question_id)
            ).all():
                hint_max[(int(sid), int(stid), int(qid))] = int(lvl or 0)
        q_meta: dict[int, tuple[str, str]] = {}
        for qid, stem, hjson in db.execute(
            select(w_q.c.id, w_q.c.stem, w_q.c.hints_json).where(w_q.c.school_id == school_id)
        ).all():
            kp = ""
            try:
                meta = json.loads(hjson or "{}")
                if isinstance(meta, dict):
                    kp = str(meta.get("knowledge") or "")
            except ValueError:
                pass
            q_meta[int(qid)] = (kp, str(stem or "").split("\n\n")[-1][:40])
        for r in db.execute(
            select(
                w_sub.c.session_id, w_sub.c.student_id, w_sub.c.question_id,
                w_sub.c.result, w_sub.c.submitted_at,
            ).where(w_sub.c.school_id == school_id, w_sub.c.student_id.in_(student_ids))
        ).all():
            kp, short_stem = q_meta.get(int(r.question_id), ("", "周末课文字/照片题"))
            lvl = hint_max.get((int(r.session_id), int(r.student_id), int(r.question_id)), 0)
            out[int(r.student_id)].append({
                "source": "weekend",
                "sourceLabel": "周末课（文字/照片题）",
                "nodeKeys": _match_node_keys(kp or short_stem, name_to_key),
                "time": _iso(r.submitted_at),
                "count": 1,
                "gradingStatus": _WRITTEN_RESULT_LABEL.get(str(r.result or "pending"), str(r.result or "未知")),
                "helpStatus": f"使用过提示（{lvl}级）" if lvl > 0 else "独立完成（无提示记录）",
                "summary": kp or short_stem,
            })

    # 3. 晚托作业助手 AI/老师辅导记录
    hw_know = md.tables.get("homework_ai_knowledge")
    if hw_know is not None:
        for r in db.execute(
            select(
                hw_know.c.student_id, hw_know.c.knowledge_key, hw_know.c.raw_knowledge,
                hw_know.c.question_excerpt, hw_know.c.verify_status, hw_know.c.created_at,
            ).where(hw_know.c.school_id == school_id, hw_know.c.student_id.in_(student_ids))
        ).all():
            kp = str(r.knowledge_key or r.raw_knowledge or "")
            out[int(r.student_id)].append({
                "source": "homework",
                "sourceLabel": "晚托作业助手",
                "nodeKeys": _match_node_keys(kp, name_to_key),
                "time": _iso(r.created_at),
                "count": 1,
                "gradingStatus": "已核验" if r.verify_status == "verified" else "不适用（辅导求助）",
                "helpStatus": "使用过 AI/老师辅导",
                "summary": kp or str(r.question_excerpt or "作业求助")[:40],
            })

    # 4. 知识地图诊断记录
    km_runs = md.tables.get("knowledge_map_runs")
    if km_runs is not None:
        for r in db.execute(
            select(
                km_runs.c.student_id, km_runs.c.status, km_runs.c.items_json,
                km_runs.c.correct, km_runs.c.created_at, km_runs.c.submitted_at,
            ).where(
                km_runs.c.school_id == school_id,
                km_runs.c.map_id == map_row.id,
                km_runs.c.student_id.in_(student_ids),
            )
        ).all():
            try:
                items = json.loads(r.items_json or "[]")
            except ValueError:
                items = []
            node_keys = list(dict.fromkeys(str(pair[0]) for pair in items if isinstance(pair, list) and pair))
            total = len(items)
            g_status = (
                f"已判分（{int(r.correct or 0)}/{total}）"
                if r.status == "submitted"
                else "进行中（未提交）"
            )
            out[int(r.student_id)].append({
                "source": "knowledge_map",
                "sourceLabel": "知识地图诊断",
                "nodeKeys": node_keys,
                "time": _iso(r.submitted_at or r.created_at),
                "count": total,
                "gradingStatus": g_status,
                "helpStatus": "未知",
                "summary": f"入门诊断共 {total} 题",
            })

    # 5. 应试专项（模拟卷 / 再测 / 专项练习）
    ex_goals = md.tables.get("exam_goals")
    ex_papers = md.tables.get("exam_goal_papers")
    ex_drills = md.tables.get("exam_goal_drills")
    if ex_goals is not None and ex_papers is not None:
        goal_ids = [
            int(g.id)
            for g in db.execute(
                select(ex_goals.c.id).where(ex_goals.c.school_id == school_id, ex_goals.c.map_id == map_row.id)
            ).all()
        ]
        if goal_ids:
            papers = db.execute(
                select(ex_papers.c.assignment_id, ex_papers.c.kind, ex_papers.c.plan_json, ex_papers.c.created_at)
                .where(ex_papers.c.school_id == school_id, ex_papers.c.goal_id.in_(goal_ids))
            ).all()
            assign_meta: dict[int, tuple[str, list[str]]] = {}
            for p in papers:
                try:
                    plan = json.loads(p.plan_json or "[]")
                except ValueError:
                    plan = []
                nkeys = list(dict.fromkeys(str(x[0]) for x in plan if isinstance(x, list) and x))
                label = "应试专项（再测）" if p.kind == "retest" else "应试专项（模拟卷）"
                assign_meta[int(p.assignment_id)] = (label, nkeys)
            if ex_drills is not None:
                for d in db.execute(
                    select(ex_drills.c.assignment_id, ex_drills.c.plan_json)
                    .where(ex_drills.c.school_id == school_id, ex_drills.c.goal_id.in_(goal_ids))
                ).all():
                    try:
                        plan = json.loads(d.plan_json or "[]")
                    except ValueError:
                        plan = []
                    nkeys = list(dict.fromkeys(str(x[0]) for x in plan if isinstance(x, list) and x))
                    assign_meta[int(d.assignment_id)] = ("应试专项（专项练习）", nkeys)
            if assign_meta:
                subs = db.execute(
                    select(
                        Submission.student_id, Submission.assignment_id, Submission.score,
                        Submission.submitted_at, Submission.answers_json,
                    ).where(
                        Submission.school_id == school_id,
                        Submission.student_id.in_(student_ids),
                        Submission.assignment_id.in_(list(assign_meta.keys())),
                    )
                ).all()
                for s in subs:
                    label, nkeys = assign_meta[int(s.assignment_id)]
                    try:
                        ans_list = json.loads(s.answers_json or "[]")
                    except ValueError:
                        ans_list = []
                    out[int(s.student_id)].append({
                        "source": "exam",
                        "sourceLabel": label,
                        "nodeKeys": nkeys,
                        "time": _iso(s.submitted_at),
                        "count": len(ans_list) if isinstance(ans_list, list) else 0,
                        "gradingStatus": f"已评分（{s.score}分）" if s.score is not None else "已提交",
                        "helpStatus": "未知",
                        "summary": f"{label} · 得分 {s.score if s.score is not None else '未知'}",
                    })

    for sid in out:
        out[sid].sort(key=lambda item: item.get("time") or "", reverse=True)
    return out
