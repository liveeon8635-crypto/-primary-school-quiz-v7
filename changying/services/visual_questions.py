"""系统画图的图形题：按知识点分派到各类图示（组合体、方格纸上的图形运动），并统一保存校验."""
from __future__ import annotations

from typing import Any

from changying.services import cube_figures as cf
from changying.services import grid_figures as gf

_FAMILIES = (cf, gf)
FIGURE_TYPES = {m.FIGURE_TYPE for m in _FAMILIES}
NODE_KINDS = {**cf.NODE_KINDS, **gf.NODE_KINDS}
NODE_LABELS = {key: fam.KIND_LABELS[kind] for fam in _FAMILIES for key, kind in fam.NODE_KINDS.items()}


def generate(node_key: str, level: str, n: int, seed: int) -> list[dict[str, Any]]:
    for fam in _FAMILIES:
        if node_key in fam.NODE_KINDS:
            return fam.generate(node_key, level, n, seed)
    raise ValueError("这个知识点暂时没有系统画图题")


def sanitize(value: Any) -> dict[str, Any]:
    kind = str(value.get("type") or "").strip().lower() if isinstance(value, dict) else ""
    for fam in _FAMILIES:
        if kind == fam.FIGURE_TYPE:
            return fam.sanitize(value)
    return {}


__all__ = ["FIGURE_TYPES", "NODE_KINDS", "NODE_LABELS", "generate", "sanitize"]
