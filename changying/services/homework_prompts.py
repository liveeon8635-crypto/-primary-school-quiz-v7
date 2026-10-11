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


__all__ = [
    "FIELD_LIMITS",
    "MAX_ITEMS",
    "MAX_NOTICE_CHARS",
    "build_parse_prompt",
    "clean_items",
    "clean_parse_result",
    "scrub_notice_text",
]
