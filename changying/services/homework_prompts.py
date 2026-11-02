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


def build_solve_prompt(grade: int, question: str, *, recheck: bool = False, known_map: str = "", learning_context: str = "") -> str:
    """The only text sent to the model when a student asks for help: the grade, the question and, when the school
    has published a knowledge map for this grade, the map with the pupil's own mastery (``known_map``, no names)."""
    grade_name = GRADE_NAMES[int(grade) - 1] + "年级"
    prompt = (
        f"你是一位小学{grade_name}的老师，正在晚托辅导一个学生做下面这道题（可能是数学、语文、英语或科学等科目）。"
        "目标不是替他做完，而是引导他自己想明白、自己算出答案，以后遇到同类题也会做。\n"
        "要求：\n"
        "1. 只给一种解法，不要列出多种方法。\n"
        f"2. 只使用{grade_name}学生已经学过的知识和方法，不要出现初中及以上的知识（例如数学题低年级不要设未知数列方程）。\n"
        "3. 从学生已经会的知识讲起：start 用一句话把这道题和他已经会的知识联系起来；"
        "life 给一个贴近小学生生活的例子帮他理解（一句话，没有合适的就留空）。\n"
        "4. 把思路拆成 2～6 个小步骤。每一步先问学生一个小问题（ask），让他自己想或算；他回答以后再给这一步的讲解（text）。\n"
        "   - 要算出一个数的步骤：kind 填 number，answer 填这一步的结果（一个数，可带单位），expression 填这一步的算式（只用数字和 + - × ÷ ( )）；\n"
        "   - 要判断或选择的步骤（例如“这道题求什么”“该用乘法还是除法”）：kind 填 choice，options 给 2～4 个选项，correct 填正确选项的序号（从 0 开始）；\n"
        "   - 只需要读懂、不用回答的步骤：kind 填 read。\n"
        "   每一步再写一句 hint，学生答错时给他看，hint 不能直接说出这一步的答案。\n"
        "5. 步骤里不要直接说出整道题的最终答案，留给学生自己算出来。语气亲切，每句话短，学生能看懂。\n"
    )
    if learning_context:
        prompt += learning_context[:500] + "\n"
    if known_map:
        prompt += (
            "下面是这个学生所用教材的知识点（编号 名称｜要先学的知识点｜他的掌握情况：已会、薄弱、未测）。"
            "nodeKey 填这道题对应的知识点编号（对不上就留空）；start 优先从他“已会”的前置知识讲起；"
            "如果这道题要用到他“薄弱”的知识点，第一步先帮他回忆这个知识点。\n" + known_map + "\n"
        )
    prompt += (
        "只输出一个 JSON 对象，不要任何解释，格式：\n"
        '{"method":"解法名称（几个字）","knowledgePoint":"这道题考的知识点（短语）","nodeKey":"",'
        '"start":"从他已经会的知识讲起的一句话","life":"生活中的例子（可留空）",'
        '"steps":[{"n":1,"kind":"choice","ask":"先想一想：…？","options":["…","…"],"correct":0,"hint":"…","text":"这一步的讲解"},'
        '{"n":2,"kind":"number","ask":"…等于多少？","answer":"7","expression":"12-5","hint":"…","text":"这一步的讲解"}],'
        '"answer":"最终答案（带单位）",'
        '"expression":"能直接计算整道题的算式，只用数字和 + - × ÷ ( )，例如 12-5；需要列方程时用 x，例如 x+3=10；只有数学计算题才填算式；语文、英语、科学等题目，或无法用算式表示的，就留空"}\n'
    )
    if recheck:
        prompt += "注意：上一次给出的算式与答案不一致。请重新仔细计算，确保 expression 的计算结果与 answer 完全一致。\n"
    return prompt + "题目：\n" + scrub_question(question)[:1000]


def _clean_step(item: Any) -> dict[str, Any]:
    """One guided step; anything the page could not ask properly becomes a plain read-only step."""
    if not isinstance(item, dict):
        return {"text": _clip(item, 400), "kind": "read"}
    step = {"text": _clip(item.get("text"), 400), "ask": _clip(item.get("ask"), 200), "hint": _clip(item.get("hint"), 150)}
    kind = str(item.get("kind") or "").strip()
    options = [_clip(o, 40) for o in item.get("options")] if isinstance(item.get("options"), list) else []
    correct = item.get("correct")
    if kind == "choice" and step["ask"] and 2 <= len(options) <= 4 and all(options) \
            and isinstance(correct, int) and not isinstance(correct, bool) and 0 <= correct < len(options):
        step.update(kind="choice", options=options, correct=correct)
    elif kind == "number" and step["ask"] and _clip(item.get("answer"), 40):
        step.update(kind="number", answer=_clip(item.get("answer"), 40), expression=_clip(item.get("expression"), 120))
    else:
        step["kind"] = "read"
    if not step["text"] and step["kind"] == "read":
        step["text"] = step["ask"]
    return step


def clean_solution(raw: Any) -> dict[str, Any]:
    """Normalise a model solution; empty dict when it is unusable."""
    if not isinstance(raw, dict):
        return {}
    steps: list[dict[str, Any]] = []
    for item in raw.get("steps") if isinstance(raw.get("steps"), list) else []:
        step = _clean_step(item)
        if step["text"]:
            steps.append({"n": len(steps) + 1, **step})
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
        "nodeKey": _clip(raw.get("nodeKey"), 12),
        "start": _clip(raw.get("start"), 150),
        "life": _clip(raw.get("life"), 150),
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

