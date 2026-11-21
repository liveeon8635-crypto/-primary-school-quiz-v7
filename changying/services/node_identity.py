"""最小稳定节点身份层（块四：lesson_nodes 与稳定 node_id 派生）。"""

from __future__ import annotations

from datetime import datetime
import hashlib
import importlib
import json
import re
from typing import Any
import unicodedata

from sqlalchemy import Column, DateTime, Integer, String, Table, Text, UniqueConstraint, select


VALID_NODE_KINDS = ("stem", "option", "hint", "answer", "analysis", "material")
VALID_QUESTION_TYPES = ("choice", "written", "material")

_FULLWIDTH_PUNCT_MAP = str.maketrans(
    {
        "\u3000": " ",
        "，": ",",
        "。": ".",
        "：": ":",
        "；": ";",
        "？": "?",
        "！": "!",
        "（": "(",
        "）": ")",
        "【": "[",
        "】": "]",
        "“": '"',
        "”": '"',
        "‘": "'",
        "’": "'",
        "、": ",",
        "｜": "|",
    }
)

_default_implementation: Any = None


def _resolve_implementation(implementation: Any = None) -> Any:
    global _default_implementation
    if implementation is not None:
        _default_implementation = implementation
        return implementation
    if _default_implementation is not None:
        return _default_implementation
    _default_implementation = importlib.import_module("app_v924")
    return _default_implementation


def normalize_node_text(content_text: Any) -> str:
    """统一全半角字符与标点、折叠连续空白并去掉首尾空白。"""
    raw = "" if content_text is None else str(content_text)
    normalized = unicodedata.normalize("NFKC", raw).translate(_FULLWIDTH_PUNCT_MAP)
    collapsed = re.sub(r"\s+", " ", normalized).strip()
    return re.sub(r"\s*([,:;.?!()\[\]|])\s*", r"\1", collapsed)


def stable_node_id(node_kind: str, question_ref: Any, content_text: str) -> str:
    """根据节点类型、题目引用和归一化内容派生 40 位稳定节点 ID。

    规则：sha1(f"{normalized_kind}|{normalized_ref}|{normalized_text}")[:40]。
    同一题干内容重复导入得到相同 ID；内容一旦变更则得到新 ID。
    """
    kind = normalize_node_text(node_kind).lower()
    if not kind:
        raise ValueError("节点类型不能为空")
    ref = normalize_node_text(question_ref).lower()
    text = normalize_node_text(content_text)
    payload = f"{kind}|{ref}|{text}"
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:40]


def compute_content_hash(content_text: Any) -> str:
    """计算归一化节点内容的 SHA-256 指纹（64 位十六进制）。"""
    normalized = normalize_node_text(content_text)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def validate_node_kind_and_question_type(node_kind: str, question_type: str) -> tuple[str, str]:
    """校验节点类型与题型分类（选择题与文字题必须严格区分）。"""
    clean_kind = normalize_node_text(node_kind).lower()
    if clean_kind not in VALID_NODE_KINDS:
        raise ValueError(f"节点类型不合法：{node_kind}，必须为 {', '.join(VALID_NODE_KINDS)}")
    clean_qtype = normalize_node_text(question_type).lower()
    if clean_qtype not in VALID_QUESTION_TYPES:
        raise ValueError(f"题型不合法：{question_type}，必须为 {', '.join(VALID_QUESTION_TYPES)}（选择题与文字题必须区分）")
    return clean_kind, clean_qtype


def register_lesson_nodes_table(implementation: Any = None) -> Table:
    """在 implementation.Base.metadata 中注册 lesson_nodes 表。"""
    impl = _resolve_implementation(implementation)
    md = impl.Base.metadata
    table = md.tables.get("lesson_nodes")
    if table is None:
        table = Table(
            "lesson_nodes",
            md,
            Column("id", Integer, primary_key=True),
            Column("school_id", Integer, nullable=False, index=True, default=0),
            Column("lesson_id", Integer, nullable=False, index=True),
            Column("node_id", String(40), nullable=False, index=True),
            Column("node_kind", String(24), nullable=False),
            Column("question_type", String(16), nullable=False),
            Column("content_hash", String(64), nullable=False, default=""),
            Column("location_json", Text, nullable=False, default="{}"),
            Column("created_at", DateTime, nullable=False, default=datetime.utcnow),
            UniqueConstraint("lesson_id", "node_id", name="uq_lesson_nodes_lesson_node"),
        )
    return table


def _row_to_dict(row: Any) -> dict[str, Any]:
    data = dict(row._mapping) if hasattr(row, "_mapping") else dict(row)
    return {
        "id": int(data["id"]),
        "school_id": int(data["school_id"]),
        "lesson_id": int(data["lesson_id"]),
        "node_id": str(data["node_id"]),
        "node_kind": str(data["node_kind"]),
        "question_type": str(data["question_type"]),
        "content_hash": str(data["content_hash"]),
        "location_json": str(data["location_json"] or "{}"),
        "created_at": data["created_at"],
    }


def upsert_lesson_node(
    lesson_id: int,
    node_kind: str,
    question_type: str,
    content_text: str,
    *,
    question_ref: Any = "",
    node_id: str | None = None,
    school_id: int = 1,
    location: dict[str, Any] | str | None = None,
    db: Any = None,
    implementation: Any = None,
) -> dict[str, Any]:
    """创建或更新课次稳定节点记录，区分 choice / written / material。"""
    impl = _resolve_implementation(implementation)
    table = register_lesson_nodes_table(impl)
    clean_kind, clean_qtype = validate_node_kind_and_question_type(node_kind, question_type)
    resolved_node_id = str(node_id or "").strip() or stable_node_id(clean_kind, question_ref, content_text)
    if len(resolved_node_id) > 40:
        raise ValueError("节点 ID 长度不能超过 40 个字符")
    content_hash = compute_content_hash(content_text)
    if isinstance(location, str):
        location_json = location
    else:
        location_json = json.dumps(location or {}, ensure_ascii=False, sort_keys=True)

    def _run(session: Any) -> dict[str, Any]:
        existing = session.execute(
            select(table).where(
                table.c.lesson_id == int(lesson_id),
                table.c.node_id == resolved_node_id,
            )
        ).first()
        now = datetime.utcnow()
        if existing is None:
            session.execute(
                table.insert().values(
                    school_id=int(school_id),
                    lesson_id=int(lesson_id),
                    node_id=resolved_node_id,
                    node_kind=clean_kind,
                    question_type=clean_qtype,
                    content_hash=content_hash,
                    location_json=location_json,
                    created_at=now,
                )
            )
        else:
            session.execute(
                table.update()
                .where(
                    table.c.lesson_id == int(lesson_id),
                    table.c.node_id == resolved_node_id,
                )
                .values(
                    school_id=int(school_id),
                    node_kind=clean_kind,
                    question_type=clean_qtype,
                    content_hash=content_hash,
                    location_json=location_json,
                )
            )
        session.commit()
        row = session.execute(
            select(table).where(
                table.c.lesson_id == int(lesson_id),
                table.c.node_id == resolved_node_id,
            )
        ).first()
        return _row_to_dict(row)

    if db is not None:
        return _run(db)
    with impl.SessionLocal() as session:
        return _run(session)


__all__ = [
    "VALID_NODE_KINDS",
    "VALID_QUESTION_TYPES",
    "compute_content_hash",
    "normalize_node_text",
    "register_lesson_nodes_table",
    "stable_node_id",
    "upsert_lesson_node",
    "validate_node_kind_and_question_type",
]
