"""Bounded, non-scoring circle-area support kept in the original help conversation."""
from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, Field

CIRCLE_GAPS = {"radius": "半径与直径", "square": "平方与面积", "circumference": "圆周长", "unit": "面积单位", "application": "套用面积公式"}


class CircleRounds(BaseModel):
    radius: int = Field(default=0, ge=0, le=2)
    square: int = Field(default=0, ge=0, le=2)
    circumference: int = Field(default=0, ge=0, le=2)
    unit: int = Field(default=0, ge=0, le=2)
    application: int = Field(default=0, ge=0, le=2)


class CircleSupportBody(BaseModel):
    entry: Literal["before", "after"] = "after"
    focus: Literal["concept", "formula", "calculation"] = "concept"
    gaps: list[Literal["radius", "square", "circumference", "unit", "application"]] = Field(default_factory=list, max_length=5)
    rounds: CircleRounds = Field(default_factory=CircleRounds)
    outcome: Literal["in_progress", "practice_passed", "needs_teacher", "teacher_requested", "stopped"] = "in_progress"
    unitChecked: bool = False


def circle_area_question(question: str, grade: int | None) -> bool:
    text = str(question or "")
    return grade == 6 and "圆" in text and "面积" in text and not re.search(r"圆柱|圆锥|球体", text)


def circle_support_record(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict) or value.get("version", 1) != 1:
        return None
    try:
        body = CircleSupportBody.model_validate(value)
    except (ValueError, TypeError):
        return None
    out = body.model_dump()
    out["gaps"] = list(dict.fromkeys(out["gaps"]))
    return {"version": 1, **out}


def circle_support_summary(value: Any) -> str:
    record = circle_support_record(value)
    if record is None:
        return ""
    gaps = "、".join(CIRCLE_GAPS[k] for k in record["gaps"]) or "未定位到卡点"
    used = "、".join(CIRCLE_GAPS[k] + str(n) + "轮" for k, n in record["rounds"].items() if n) or "固定前置检查"
    state = {"in_progress": "辅导中", "practice_passed": "本次补救确认通过，尚未独立小测",
             "needs_teacher": "两轮补救后仍需老师帮助", "teacher_requested": "学生主动求助，尚未独立验证",
             "stopped": "已退出补救，尚未独立验证"}[record["outcome"]]
    return "卡点：" + gaps + "\n已用帮助：" + used + "\n当前状态：" + state


def circle_prompt_context(question: str, grade: int | None, value: Any) -> str:
    if not circle_area_question(question, grade):
        return ""
    rule = ("圆面积辅导：π取值严格按原题；要求保留π或未明确近似取值时，不擅自换成3.14，"
            "不可程序核对的符号步骤仅讲解，不判断学生答错。数字校验不代表面积单位或概念已核对。")
    summary = circle_support_summary(value)
    if summary:
        record = circle_support_record(value)
        focus = {"concept": "回忆基础", "formula": "理解公式来历", "calculation": "计算支持"}[record["focus"]]
        rule += "学生本次选择" + focus + "。本次固定练习反馈（非长期掌握结论）：" + summary.replace("\n", "；") + "。从卡点衔接回原题，不用固定示例替换原题条件，不直接泄露最终答案。"
    return rule
