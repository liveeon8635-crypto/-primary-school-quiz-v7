"""Prompt builders and result cleaners for the after-school homework assistant.

This module is the only place that builds text sent to a model for this feature. Every builder
takes plain strings (never ORM rows or user objects), so student/teacher identity cannot leak
into a prompt by accident; the tests assert that.
"""

from __future__ import annotations

import re
from typing import Any

MAX_NOTICE_CHARS = 6000
MAX_ITEMS = 30
FIELD_LIMITS = {"subject": 20, "content": 300, "page": 40, "requirement": 200}

_PHONE = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
_LONG_DIGITS = re.compile(r"(?<!\d)\d{8,}(?!\d)")
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_URL = re.compile(r"https?://\S+", re.I)
_HIDDEN = "【已隐藏】"


def scrub_notice_text(text: str) -> str:
    """Hide phone numbers, long digit runs, e-mails and links before a notice leaves the server."""
    value = str(text or "")
    for pattern in (_URL, _EMAIL, _PHONE, _LONG_DIGITS):
        value = pattern.sub(_HIDDEN, value)
    return value.strip()[:MAX_NOTICE_CHARS]


def build_parse_prompt(notice_text: str) -> str:
    return (
        "你是小学晚托老师的助手。下面是学校发给家长的当日作业通知（可能是聊天文字）。"
        "请只提取作业条目，忽略聊天头像、昵称、手机号、问候语等无关内容。\n"
        "只输出一个 JSON 对象，不要任何解释，格式："
        '{"groupLabel":"学校+班级（通知里没有就留空）",'
        '"items":[{"subject":"学科","content":"作业内容","page":"页码或范围（没有就留空）",'
        '"requirement":"要求（没有就留空）"}]}\n'
        "每条作业一项；不要编造通知里没有的内容。\n"
        "通知原文：\n" + scrub_notice_text(notice_text)
    )


def _clip(value: Any, limit: int) -> str:
    return re.sub(r"\s+", " ", str(value if value is not None else "")).strip()[:limit]


def clean_items(raw_items: Any) -> list[dict[str, Any]]:
    """Normalise teacher/model supplied items to the stored shape; drops empty rows."""
    if not isinstance(raw_items, list):
        return []
    items: list[dict[str, Any]] = []
    for raw in raw_items:
        if not isinstance(raw, dict):
            continue
        item = {key: _clip(raw.get(key), limit) for key, limit in FIELD_LIMITS.items()}
        if not item["content"]:
            continue
        items.append(item)
        if len(items) >= MAX_ITEMS:
            break
    for seq, item in enumerate(items, start=1):
        item["seq"] = seq
    return items


def clean_parse_result(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {"groupLabel": "", "items": []}
    return {"groupLabel": _clip(raw.get("groupLabel"), 120), "items": clean_items(raw.get("items"))}


GRADE_NAMES = ("一", "二", "三", "四", "五", "六")
MAX_STEPS = 12
AI_WARNING = "AI 可能出错，请自己判断"


def scrub_question(text: str) -> str:
    """Hide phone numbers, e-mails and links in a student's question (keeps ordinary big numbers)."""
    value = str(text or "")
    for pattern in (_URL, _EMAIL, _PHONE):
        value = pattern.sub(_HIDDEN, value)
    return value.strip()


def build_solve_prompt(grade: int, question: str, *, recheck: bool = False) -> str:
    """The only text sent to the model when a student asks for help: the grade and the question."""
    grade_name = GRADE_NAMES[int(grade) - 1] + "年级"
    prompt = (
        f"你是一位小学{grade_name}的老师，请帮学生讲懂下面这道题（可能是数学、语文、英语或科学等科目）。\n"
        "要求：\n"
        "1. 只给一种解法，不要列出多种方法。\n"
        f"2. 只使用{grade_name}学生已经学过的知识和方法，不要出现初中及以上的知识（例如数学题低年级不要设未知数列方程）。\n"
        "3. 分步讲解，每一步一两句话，语气亲切，学生能看懂。\n"
        "4. 只输出一个 JSON 对象，不要任何解释，格式：\n"
        '{"method":"解法名称（几个字）","steps":[{"n":1,"text":"第一步…"}],'
        '"answer":"最终答案（带单位）",'
        '"expression":"能直接计算的算式，只用数字和 + - × ÷ ( )，例如 12-5；需要列方程时用 x，例如 x+3=10；只有数学计算题才填算式；语文、英语、科学等题目，或无法用算式表示的，就留空",'
        '"knowledgePoint":"这道题考的知识点（短语）"}\n'
    )
    if recheck:
        prompt += "注意：上一次给出的算式与答案不一致。请重新仔细计算，确保 expression 的计算结果与 answer 完全一致。\n"
    return prompt + "题目：\n" + scrub_question(question)[:1000]


def clean_solution(raw: Any) -> dict[str, Any]:
    """Normalise a model solution; empty dict when it is unusable."""
    if not isinstance(raw, dict):
        return {}
    steps: list[dict[str, Any]] = []
    for item in raw.get("steps") if isinstance(raw.get("steps"), list) else []:
        text = _clip(item.get("text") if isinstance(item, dict) else item, 400)
        if text:
            steps.append({"n": len(steps) + 1, "text": text})
        if len(steps) >= MAX_STEPS:
            break
    answer = _clip(raw.get("answer"), 120)
    if not steps or not answer:
        return {}
    return {
        "method": _clip(raw.get("method"), 40),
        "steps": steps,
        "answer": answer,
        "expression": _clip(raw.get("expression"), 120),
        "knowledgePoint": _clip(raw.get("knowledgePoint"), 60),
    }


__all__ = [
    "AI_WARNING",
    "GRADE_NAMES",
    "build_solve_prompt",
    "clean_solution",
    "scrub_question",
    "FIELD_LIMITS",
    "MAX_ITEMS",
    "MAX_NOTICE_CHARS",
    "build_parse_prompt",
    "clean_items",
    "clean_parse_result",
    "scrub_notice_text",
]
