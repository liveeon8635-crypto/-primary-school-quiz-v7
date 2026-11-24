"""周末课课堂环节、课型映射与计时。"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

MATH_STAGES: list[dict[str, Any]] = [
    {"no": 1, "key": "warmup", "name": "到课与热身", "minutes": 10, "goal": "点名，回顾上周错题"},
    {"no": 2, "key": "intro", "name": "知识点介绍", "minutes": 20, "goal": "讲清本节知识点"},
    {"no": 3, "key": "examples", "name": "例题讲解", "minutes": 25, "goal": "跟着例题学方法"},
    {"no": 4, "key": "practice", "name": "随堂练习", "minutes": 25, "goal": "独立完成，卡住时用提示"},
    {"no": 5, "key": "review", "name": "练习复盘", "minutes": 15, "goal": "代表性学生讲题，当堂订正"},
    {"no": 6, "key": "interact", "name": "课堂互动", "minutes": 15, "goal": "集中讨论共性错题，继续订正达标"},
    {"no": 7, "key": "homework", "name": "布置课后", "minutes": 10, "goal": "简短总结，按未订正错题下发个性化练习"},
]
READING_STAGES: list[dict[str, Any]] = [
    {"no": 1, "key": "recall", "name": "点名与回顾", "minutes": 10, "goal": "点名并回顾上次阅读方法"},
    {"no": 2, "key": "short_reading", "name": "短文阅读", "minutes": 20, "goal": "阅读不超过三篇短文，可提前布置"},
    {"no": 3, "key": "long_reading", "name": "长文阅读", "minutes": 35, "goal": "先展示媒体，再由教师逐步开放题目、提示和解析"},
    {"no": 4, "key": "key_points", "name": "考点总结", "minutes": 20, "goal": "归纳阅读方法并回到文本证据"},
    {"no": 5, "key": "integrated_practice", "name": "综合练习", "minutes": 25, "goal": "独立完成综合阅读任务"},
    {"no": 6, "key": "feedback", "name": "课后反馈", "minutes": 10, "goal": "教师审核并发布本课反馈"},
]
WRITING_STAGES: list[dict[str, Any]] = [
    {"no": 1, "key": "recall", "name": "点名与回顾", "minutes": 10, "goal": "点名并回顾上次写作任务"},
    {"no": 2, "key": "model", "name": "范文导览", "minutes": 25, "goal": "图文对照范文，记忆并模仿表达"},
    {"no": 3, "key": "picture_writing", "name": "看图写话", "minutes": 20, "goal": "观察图片并按图景引导构思"},
    {"no": 4, "key": "techniques", "name": "技法梳理", "minutes": 20, "goal": "整理并练习写作方法"},
    {"no": 5, "key": "writing_practice", "name": "随堂练习", "minutes": 35, "goal": "围绕一个主题写作并提交文字或照片"},
    {"no": 6, "key": "feedback", "name": "课后反馈", "minutes": 10, "goal": "教师审核并发布本课反馈"},
]
STAGES: list[dict[str, Any]] = MATH_STAGES
COURSE_STAGES = {"math": MATH_STAGES, "reading": READING_STAGES, "writing": WRITING_STAGES}
MAX_EXTEND_MIN = 30
STAGE_COUNT = len(STAGES)


def stages_for(course_type: str | None = "math") -> list[dict[str, Any]]:
    """Return a copy of the selected workflow; unset Chinese plans have no stages."""
    if course_type in COURSE_STAGES:
        return [dict(stage) for stage in COURSE_STAGES[course_type]]
    if course_type == "legacy":
        return [dict(stage) for stage in MATH_STAGES]
    return []


def stage_by_no(no: int, course_type: str | None = "math") -> dict[str, Any] | None:
    stages = stages_for(course_type)
    return stages[no - 1] if 1 <= no <= len(stages) else None


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


def stage_content(stage_no: int, lesson: dict[str, Any], course_type: str | None = "math") -> list[str]:
    """Lines the big screen shows for a stage, taken from the lesson plan the teacher prepared."""
    title = str(lesson.get("title") or "")
    if course_type == "reading":
        if stage_no == 1:
            return [title, "点名并回顾上次阅读方法"]
        if stage_no == 2:
            return _lines(lesson.get("reading_plan"))[:3] or ["短文阅读：最多三篇；材料和配图须经教师确认"]
        if stage_no == 3:
            return ["长文阅读：先展示已审核的幻灯片或媒体", "题目、提示、答案和解析由教师按题逐步开放"]
        if stage_no == 4:
            return _lines(lesson.get("core_target")) or ["回到文本证据，总结本课阅读考点"]
        if stage_no == 5:
            return ["综合练习：学生独立完成已审核任务"]
        if stage_no == 6:
            return ["课后反馈：教师核对完成情况并审核反馈草稿"]
        return []
    if course_type == "writing":
        if stage_no == 1:
            return [title, "点名并回顾上次写作任务"]
        if stage_no == 2:
            return _lines(lesson.get("examples_json")) or ["范文及配图待教师配置"]
        if stage_no == 3:
            return _lines(lesson.get("ppt_json")) or ["看图写话：图片和图景引导待教师配置"]
        if stage_no == 4:
            return _lines(lesson.get("reading_plan")) or ["写作方法待教师配置"]
        if stage_no == 5:
            return [str(lesson.get("writing_plan") or lesson.get("closure_training") or "写作主题待教师配置")]
        if stage_no == 6:
            return ["课后反馈：教师核对完成情况并审核反馈草稿"]
        return []
    if stage_no == 1:
        return [title, "点名、回顾上周错题"]
    if stage_no == 2:
        return [x for x in [str(lesson.get("core_target") or "").strip(), *_lines(lesson.get("teacher_plan")), *_lines(lesson.get("ppt_json"))] if x][:12]
    if stage_no == 3:
        return _lines(lesson.get("examples_json")) or ["（教案里还没有例题）"]
    if stage_no == 4:
        return ["随堂练习：在自己的设备上独立完成", "卡住时可以按“提示”，不要直接问答案"]
    if stage_no == 5:
        return ["练习复盘（10–15分钟）：请有代表性的同学讲解思路，其余同学边听边订正"]
    if stage_no == 6:
        return ["课堂互动（10–15分钟）：集中讨论第 5 环节未解决的共性错题，本环节内仍可继续订正"]
    if stage_no == 7:
        return [x for x in _lines(lesson.get("closure_training")) or [str(lesson.get("closure_training") or "").strip()] if x] or ["布置课后 · 本课简短总结：课堂订正已截止，未能订正的错题将生成个性化巩固练习下发到“作业”。"]
    return []


__all__ = ["MAX_EXTEND_MIN", "STAGES", "MATH_STAGES", "READING_STAGES", "WRITING_STAGES", "STAGE_COUNT",
           "stages_for", "remaining_seconds", "stage_by_no", "stage_content"]
