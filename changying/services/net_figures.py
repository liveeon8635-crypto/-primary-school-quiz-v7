"""展开图（长方体纸盒的展开）图形题：固定画一个 1-4-1 型正方体展开图。

同一行里隔一格的两面是相对的；上下两个盖面互相相对。这是折叠的必然结果，
所以答案由布局位置直接算出，不靠猜。
"""
from __future__ import annotations

import random
from typing import Any

from changying.services import grid_figures as gf

FIGURE_TYPE = "gridshape"
NODE_KINDS = {"opposite": "opposite"}
KIND_LABELS = {"opposite": "展开图：找相对的面"}
LEVELS = ("basic", "medium", "hard")

# 1-4-1 型：上面 1 格 + 中间横排 4 格 + 下面 1 格
_FACES = {
    "A": (0, 1),
    "B": (1, 0), "C": (1, 1), "D": (1, 2), "E": (1, 3),
    "F": (2, 1),
}
_OPPOSITE = {"A": "F", "F": "A", "B": "D", "D": "B", "C": "E", "E": "C"}


def _cell(x: int, y: int, label: str) -> dict[str, Any]:
    return {"points": [[x, y], [x + 1, y], [x + 1, y + 1], [x, y + 1]], "tone": "a", "label": label}


def make_question(level: str, seed: int) -> dict[str, Any] | None:
    rng = random.Random(seed)
    marked = rng.choice(sorted(_FACES))
    target = _OPPOSITE[marked]

    shapes = [_cell(c, r, name) for name, (r, c) in _FACES.items()]
    figure = {"type": FIGURE_TYPE, "width": 6, "height": 5, "shapes": shapes}
    if not gf.sanitize(figure):
        return None

    others = [k for k in sorted(_FACES) if k != marked]
    options = [target] + [k for k in others if k != target][:3]
    rng.shuffle(options)

    return {
        "text": f"下图是正方体的展开图，把它折成正方体后，与标 {marked} 的面相对的是哪个面？",
        "options": options,
        "answer": options.index(target),
        "explanation": f"{marked} 的对立面是 {target}：同一横排里隔一格的两面相对，上下两个盖面也相对。",
        "figure": figure,
        "check": {"marked": marked, "opposite": target},
    }


def generate(level: str, n: int, seed: int) -> list[dict[str, Any]]:
    base = rng_seed = seed
    out, tries = [], 0
    while len(out) < n and tries < n * 20:
        q = make_question(level, base + tries)
        tries += 1
        if q and all(q["check"]["marked"] != o["check"]["marked"] for o in out):
            out.append(q)
    return out[:n]


def sanitize(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or str(value.get("type", "")).lower() != FIGURE_TYPE:
        return {}
    return gf.sanitize(value)