"""周末课 7 环节模板与计时 (阶段 3a).

A weekend lesson is 120 minutes in seven fixed stages. This module owns the template and the pure timing
arithmetic; the tables and routes live in ``changying/web/weekend_views.py``.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

STAGES: list[dict[str, Any]] = [
    {"no": 1, "key": "warmup", "name": "到课与热身", "minutes": 10, "goal": "点名，回顾上周错题"},
    {"no": 2, "key": "intro", "name": "知识点介绍", "minutes": 20, "goal": "讲清本节知识点"},
    {"no": 3, "key": "examples", "name": "例题讲解", "minutes": 25, "goal": "跟着例题学方法"},
    {"no": 4, "key": "practice", "name": "随堂练习", "minutes": 25, "goal": "独立完成，卡住时用提示"},
    {"no": 5, "key": "review", "name": "练习复盘", "minutes": 15, "goal": "讲错题，会的帮不会的"},
    {"no": 6, "key": "interact", "name": "课堂互动", "minutes": 15, "goal": "全班一起完成目标"},
    {"no": 7, "key": "homework", "name": "布置课后", "minutes": 10, "goal": "明确课后练习"},
]
MAX_EXTEND_MIN = 30
STAGE_COUNT = len(STAGES)


def stage_by_no(no: int) -> dict[str, Any] | None:
    return STAGES[no - 1] if 1 <= no <= STAGE_COUNT else None


def remaining_seconds(planned_min: int, extend_min: int, started_at: datetime | None, now: datetime) -> int:
    """Seconds left in the stage; negative once overtime. Not started -> the full planned time."""
    total = (int(planned_min) + int(extend_min)) * 60
    if started_at is None:
        return total
    return total - int((now - started_at).total_seconds())


def _lines(raw: Any) -> list[str]:
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except Exception:  # noqa: BLE001
            return [x.strip() for x in raw.splitlines() if x.strip()]
    out: list[str] = []
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict):
                text = " ".join(str(item.get(k) or "") for k in ("title", "question", "stem", "text", "answer") if item.get(k)).strip()
            else:
                text = str(item or "").strip()
            if text:
                out.append(text[:300])
    return out[:12]


def stage_content(stage_no: int, lesson: dict[str, Any]) -> list[str]:
    """Lines the big screen shows for a stage, taken from the lesson plan the teacher prepared."""
    title = str(lesson.get("title") or "")
    if stage_no == 1:
        return [title, "点名、回顾上周错题"]
    if stage_no == 2:
        return [x for x in [str(lesson.get("core_target") or "").strip(), *_lines(lesson.get("teacher_plan")), *_lines(lesson.get("ppt_json"))] if x][:12]
    if stage_no == 3:
        return _lines(lesson.get("examples_json")) or ["（教案里还没有例题）"]
    if stage_no == 4:
        return ["随堂练习：在自己的设备上独立完成", "卡住时可以按“提示”，不要直接问答案"]
    if stage_no == 5:
        return ["练习复盘：先自己订正，再互相讲错题"]
    if stage_no == 6:
        return ["课堂互动：全班一起完成今天的目标"]
    if stage_no == 7:
        return [x for x in _lines(lesson.get("closure_training")) or [str(lesson.get("closure_training") or "").strip()] if x] or ["课后练习：见老师布置"]
    return []


__all__ = ["MAX_EXTEND_MIN", "STAGES", "STAGE_COUNT", "remaining_seconds", "stage_by_no", "stage_content"]
