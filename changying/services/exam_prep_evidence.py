"""Cross-scene learning evidence lookup for exam prep analysis (read-only).

Collects supporting evidence from Knowledge Map runs, Homework AI help records,
and Weekend Class written/practice records for a student's focus knowledge points
without altering exam scores, loss rankings, or drill/retest selection.
"""
from __future__ import annotations

import json
from typing import Any

from sqlalchemy import desc, select


EVIDENCE_DISCLAIMER = (
    "以下跨场景学习证据仅作讲评与辅导参考，不改变本次模拟卷/再测卷成绩，"
    "也不改变失分点排名和专项/再测组卷规则；未记录帮助情况的条目已标注为“未知”。"
)


def _node_lookup(map_dict: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    """Map node_key -> node dict and bankKey -> node_key."""
    by_key: dict[str, dict[str, Any]] = {}
    bank_to_node: dict[str, str] = {}
    for node in map_dict.get("nodes") or []:
        key = str(node.get("key") or "")
        if not key:
            continue
        by_key[key] = node
        for bank in node.get("bankKeys") or []:
            if bank:
                bank_to_node.setdefault(str(bank), key)
        if node.get("name"):
            bank_to_node.setdefault(str(node["name"]), key)
    return by_key, bank_to_node


def _iso(implementation: Any, value: Any) -> str | None:
    if value is None:
        return None
    if hasattr(implementation, "school_local_iso"):
        return implementation.school_local_iso(value)
    return value.strftime("%Y-%m-%d %H:%M") if hasattr(value, "strftime") else str(value)


def collect_exam_prep_evidence(
    db: Any,
    implementation: Any,
    school_id: int,
    map_id: int,
    map_dict: dict[str, Any],
    student_ids: list[int],
) -> dict[int, dict[str, list[dict[str, Any]]]]:
    """Return {student_id: {point_key: [evidence_item, ...]}} for the given students."""
    out: dict[int, dict[str, list[dict[str, Any]]]] = {sid: {} for sid in student_ids}
    if not student_ids:
        return out

    md = implementation.Base.metadata
    by_key, bank_to_node = _node_lookup(map_dict)
    sids = set(student_ids)

    def add(sid: int, point_key: str, item: dict[str, Any]) -> None:
        if sid not in out or not point_key:
            return
        bucket = out[sid].setdefault(point_key, [])
        if len(bucket) < 8:
            bucket.append(item)

    # 1. Knowledge map diagnostic / quiz runs
    km_runs = md.tables.get("knowledge_map_runs")
    if km_runs is not None:
        rows = db.execute(
            select(km_runs)
            .where(
                km_runs.c.school_id == school_id,
                km_runs.c.map_id == map_id,
                km_runs.c.student_id.in_(sids),
            )
            .order_by(desc(km_runs.c.id))
            .limit(200)
        ).all()
        for r in rows:
            try:
                items = json.loads(r.items_json or "[]")
            except ValueError:
                items = []
            seen_nodes: set[str] = set()
            for pair in items:
                if not isinstance(pair, (list, tuple)) or not pair:
                    continue
                nkey = str(pair[0])
                if nkey in seen_nodes or nkey not in by_key:
                    continue
                seen_nodes.add(nkey)
                add(int(r.student_id), nkey, {
                    "source": "知识地图测验",
                    "time": _iso(implementation, r.created_at),
                    "status": "已提交" if r.status == "submitted" else "进行中",
                    "correct": r.correct,
                    "helpStatus": "未知",
                })

    # 2. Homework AI help knowledge records
    hw_know = md.tables.get("homework_ai_knowledge")
    if hw_know is not None:
        rows = db.execute(
            select(hw_know)
            .where(
                hw_know.c.school_id == school_id,
                hw_know.c.student_id.in_(sids),
            )
            .order_by(desc(hw_know.c.id))
            .limit(300)
        ).all()
        for r in rows:
            nkey = str(r.knowledge_key or "")
            if nkey not in by_key:
                nkey = bank_to_node.get(str(r.raw_knowledge or ""), "")
            if nkey not in by_key:
                continue
            add(int(r.student_id), nkey, {
                "source": "晚托作业求助",
                "time": _iso(implementation, r.created_at),
                "status": str(r.verify_status or "已记录"),
                "helpStatus": "接受过AI讲解",
                "excerpt": str(r.question_excerpt or "")[:40],
            })

    # 3. Weekend written submissions + hint logs
    wk_sub = md.tables.get("weekend_written_submissions")
    wk_q = md.tables.get("weekend_written_questions")
    wk_hint = md.tables.get("weekend_written_hint_log")
    if wk_sub is not None and wk_q is not None:
        hint_counts: dict[tuple[int, int, int], int] = {}
        if wk_hint is not None:
            for hr in db.execute(
                select(wk_hint.c.session_id, wk_hint.c.student_id, wk_hint.c.question_id)
                .where(wk_hint.c.school_id == school_id, wk_hint.c.student_id.in_(sids))
            ).all():
                hk = (int(hr.session_id), int(hr.student_id), int(hr.question_id))
                hint_counts[hk] = hint_counts.get(hk, 0) + 1
        rows = db.execute(
            select(wk_sub, wk_q.c.stem)
            .join(wk_q, wk_q.c.id == wk_sub.c.question_id)
            .where(wk_sub.c.school_id == school_id, wk_sub.c.student_id.in_(sids))
            .order_by(desc(wk_sub.c.id))
            .limit(300)
        ).all()
        for r in rows:
            stem = str(r.stem or "")
            nkey = next((nk for bname, nk in bank_to_node.items() if bname and bname in stem), "")
            if nkey not in by_key:
                continue
            hints = hint_counts.get((int(r.session_id), int(r.student_id), int(r.question_id)), 0)
            add(int(r.student_id), nkey, {
                "source": "周末课书写练习",
                "time": _iso(implementation, r.submitted_at),
                "status": str(r.result or "已提交"),
                "helpStatus": f"查看提示 {hints} 次" if hints > 0 else "独立作答（未用提示）",
            })

    return out
