"""知识点讲解卡片 (周末课 阶段 1).

One card per (school, grade, subject, knowledge name). The knowledge name is the same string the question bank
(``questions.knowledge``) and the student's wrong-question records use, so wrong questions, statistics and cards
line up without a separate mapping. A card is invisible to students until a teacher approves it.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, LargeBinary, String, Table, Text, UniqueConstraint

CARDS = "kp_cards"
IMAGES = "kp_card_images"
MAX_IMAGES = 4
MAX_IMAGE_BYTES = 600_000
MAX_LIST_ITEMS = 12
MAX_ITEM_CHARS = 400
SUBJECTS = ("语文", "数学", "英语")


def _utcnow() -> datetime:
    return datetime.utcnow()


def register_kp_tables(implementation: Any) -> dict[str, Table]:
    metadata = implementation.Base.metadata
    cards = metadata.tables.get(CARDS)
    if cards is None:
        cards = Table(
            CARDS,
            metadata,
            Column("id", Integer, primary_key=True),
            Column("school_id", Integer, ForeignKey("schools.id"), nullable=False, index=True),
            Column("grade", Integer, nullable=False, index=True),
            Column("subject", String(30), nullable=False, index=True),
            Column("knowledge_key", String(160), nullable=False, index=True),
            Column("summary", Text, nullable=False, default=""),
            Column("steps_json", Text, nullable=False, default="[]"),
            Column("mistakes_json", Text, nullable=False, default="[]"),
            Column("examples_json", Text, nullable=False, default="[]"),
            Column("status", String(12), nullable=False, default="draft", index=True),
            Column("created_by", Integer, nullable=True),
            Column("approved_by", Integer, nullable=True),
            Column("approved_at", DateTime, nullable=True),
            Column("created_at", DateTime, nullable=False, default=_utcnow),
            Column("updated_at", DateTime, nullable=False, default=_utcnow),
            UniqueConstraint("school_id", "grade", "subject", "knowledge_key", name="uq_kp_card_key"),
        )
    images = metadata.tables.get(IMAGES)
    if images is None:
        images = Table(
            IMAGES,
            metadata,
            Column("id", Integer, primary_key=True),
            Column("school_id", Integer, ForeignKey("schools.id"), nullable=False, index=True),
            Column("card_id", Integer, ForeignKey(f"{CARDS}.id"), nullable=False, index=True),
            Column("mime", String(30), nullable=False, default="image/jpeg"),
            Column("caption", String(120), nullable=False, default=""),
            Column("data", LargeBinary, nullable=False),
            Column("created_at", DateTime, nullable=False, default=_utcnow),
        )
    return {"cards": cards, "images": images}


def clean_list(raw: Any) -> list[str]:
    if not isinstance(raw, list):
        return []
    out = []
    for item in raw:
        text = " ".join(str(item or "").split())[:MAX_ITEM_CHARS]
        if text:
            out.append(text)
    return out[:MAX_LIST_ITEMS]


def load_list(raw: str | None) -> list[str]:
    try:
        return clean_list(json.loads(raw or "[]"))
    except Exception:  # noqa: BLE001 - a damaged row must not break the page
        return []


def card_json(row: Any, image_ids: list[int] | None = None, *, with_status: bool = False) -> dict[str, Any]:
    m = row._mapping if hasattr(row, "_mapping") else row
    data = {
        "id": m["id"],
        "grade": m["grade"],
        "subject": m["subject"],
        "knowledge": m["knowledge_key"],
        "summary": m["summary"] or "",
        "steps": load_list(m["steps_json"]),
        "mistakes": load_list(m["mistakes_json"]),
        "examples": load_list(m["examples_json"]),
        "images": image_ids or [],
    }
    if with_status:
        data["status"] = m["status"]
        data["updatedAt"] = m["updated_at"].strftime("%Y-%m-%d %H:%M") if m["updated_at"] else ""
    return data


def is_filled(row: Any) -> bool:
    m = row._mapping if hasattr(row, "_mapping") else row
    return bool((m["summary"] or "").strip() or load_list(m["steps_json"]))


def search_text(row: Any) -> str:
    m = row._mapping if hasattr(row, "_mapping") else row
    return " ".join([m["knowledge_key"], m["summary"] or "", *load_list(m["steps_json"]), *load_list(m["mistakes_json"])]).lower()


__all__ = [
    "MAX_IMAGES", "MAX_IMAGE_BYTES", "SUBJECTS", "card_json", "clean_list", "is_filled", "load_list",
    "register_kp_tables", "search_text",
]
