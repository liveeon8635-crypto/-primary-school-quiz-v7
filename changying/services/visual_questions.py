"""系统画图的图形题：按知识点分派到各类图示（组合体、方格纸上的图形运动/面积/植树/密铺、可能性），并统一保存校验."""
from __future__ import annotations

from typing import Any

from changying.services import area_figures as af
from changying.services import chance_figures as ch
from changying.services import bearing_figures as bear
from changying.services import coord_figures as coord
from changying.services import cube_figures as cf
from changying.services import grid_figures as gf
from changying.services import number_figures as nf
from changying.services import tiling_figures as tl
from changying.services import tree_figures as tf

_FAMILIES = (cf, gf, ch)                      # one per figure type: generation and saving checks
_GENERATORS = (cf, gf, af, tf, tl, ch, nf)    # area, tree, tiling and number questions draw on the gridshape type
FIGURE_TYPES = {m.FIGURE_TYPE for m in _FAMILIES}
# Review points mix the kinds of the units they review (8-4 图形的运动与测量, 8-5 可能性综合).
REVIEW = {"8-4": [(gf, "translate"), (gf, "rotate"), (gf, "reflect"), (af, "parallelogram"), (af, "triangle"),
                  (af, "trapezoid"), (af, "composite")],
          "8-5": [(ch, "certain"), (ch, "compare"), (ch, "infer")]}
NODE_KINDS = {**cf.NODE_KINDS, **gf.NODE_KINDS, **af.NODE_KINDS, **tf.NODE_KINDS, **tl.NODE_KINDS, **ch.NODE_KINDS, **nf.NODE_KINDS,
              **{k: "review" for k in REVIEW}}
NODE_LABELS = {**{key: fam.KIND_LABELS[kind] for fam in _GENERATORS for key, kind in fam.NODE_KINDS.items()},
               "8-4": "复习：图形的运动和面积混合", "8-5": "复习：可能性综合（摸球、转盘、推测）"}


# 跨年级：同一个键在不同年级含义不同，不能只按键分派。
# 这里给三年级地图里语义与现有图形族完全一致的节点显式补上路由。
TEMPLATE_ROUTES = {
    "rj2026-g3-math-up": {"1-1": (cf, "view")},      # 从不同方向观察物体 == 看组合体选视图
    "rj2026-g6-math-up": {"1-1": (coord, "pair"),
                             "1-2": (bear, "direction"),   # 用方向和距离确定位置（1）
                             "1-3": (bear, "direction")},  # 用方向和距离确定位置（2）
}


def _route_for(template_key: str | None, node_key: str):
    if template_key:
        hit = TEMPLATE_ROUTES.get(template_key, {}).get(node_key)
        if hit:
            return hit
    return None


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


def supports(template_key: str | None, node_key: str) -> bool:
    """这张地图的该知识点能不能出系统画图题。有专属路由表的年级以路由表为准。"""
    if template_key and node_key in TEMPLATE_ROUTES.get(template_key, {}):
        return True
    if template_key in TEMPLATE_ROUTES:
        return False
    return node_key in NODE_KINDS


def generate(node_key: str, level: str, n: int, seed: int, template_key: str | None = None) -> list[dict[str, Any]]:
    route = _route_for(template_key, node_key)
    if route:
        fam, kind = route
        out, tries = [], 0
        custom = (coord, bear)
        while len(out) < n and tries < n * 40:
            q = fam.make_question(level, seed * 1000 + tries) if fam in custom else fam.make_question(kind, level, seed * 1000 + tries)
            tries += 1
            if q is not None and all(q["text"] != o["text"] or q["figure"] != o["figure"] for o in out):
                out.append(q)
        return out
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


__all__ = ["FIGURE_TYPES", "NODE_KINDS", "NODE_LABELS", "TEMPLATE_ROUTES", "generate", "sanitize", "supports"]
