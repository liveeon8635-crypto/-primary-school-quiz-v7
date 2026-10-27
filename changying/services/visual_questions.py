"""系统画图的图形题：按知识点分派到各类图示（组合体、方格纸上的图形运动和面积），并统一保存校验."""
from __future__ import annotations

from typing import Any

from changying.services import area_figures as af
from changying.services import cube_figures as cf
from changying.services import grid_figures as gf
from changying.services import tiling_figures as tl
from changying.services import tree_figures as tf

_FAMILIES = (cf, gf)                          # one per figure type: generation and saving checks
_GENERATORS = (cf, gf, af, tf, tl)            # area, tree and tiling questions draw on the gridshape type
FIGURE_TYPES = {m.FIGURE_TYPE for m in _FAMILIES}
# Review points mix the kinds of the units they review (8-4 图形的运动与测量).
REVIEW = {"8-4": [(gf, "translate"), (gf, "rotate"), (gf, "reflect"), (af, "parallelogram"), (af, "triangle"),
                  (af, "trapezoid"), (af, "composite")]}
NODE_KINDS = {**cf.NODE_KINDS, **gf.NODE_KINDS, **af.NODE_KINDS, **tf.NODE_KINDS, **tl.NODE_KINDS, **{k: "review" for k in REVIEW}}
NODE_LABELS = {**{key: fam.KIND_LABELS[kind] for fam in _GENERATORS for key, kind in fam.NODE_KINDS.items()},
               "8-4": "复习：图形的运动和面积混合"}


def _review(node_key: str, level: str, n: int, seed: int) -> list[dict[str, Any]]:
    mix = REVIEW[node_key]
    out, tries = [], 0
    while len(out) < n and tries < n * 40:
        fam, kind = mix[(seed + tries) % len(mix)]
        q = fam.make_question(kind, level, seed * 1000 + tries)
        tries += 1
        if q is not None and all(q["text"] != o["text"] or q["figure"] != o["figure"] for o in out):
            out.append(q)
    return out


def generate(node_key: str, level: str, n: int, seed: int) -> list[dict[str, Any]]:
    if node_key in REVIEW:
        return _review(node_key, level, n, seed)
    for fam in _GENERATORS:
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
