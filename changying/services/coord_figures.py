"""数对（用有序数对确定位置）图形题。

复用现有 gridshape 图：每格画成描边方块，形成网格；把其中一个格子填色并标 A，
让学生读它在第几列第几行。答案由同一个 (列, 行) 直接生成，图形与答案同源。
"""
from __future__ import annotations

import random
from typing import Any

from changying.services import grid_figures as gf

FIGURE_TYPE = "gridshape"
NODE_KINDS = {"coord": "pair"}
KIND_LABELS = {"pair": "看图写数对（第几列第几行）"}
LEVELS = ("basic", "medium", "hard")
CELL = 1   # gridshape 用格子坐标，宽度/高度就是格数


def _cell_shape(col: int, row: int, rows: int, tone: str, label: str = "") -> dict[str, Any]:
    x, y = col * CELL, (rows - row - 1) * CELL
    return {"points": [[x, y], [x + CELL, y], [x + CELL, y + CELL], [x, y + CELL]], "tone": tone, "label": label}


def make_question(level: str, seed: int) -> dict[str, Any] | None:
    rng = random.Random(seed)
    cols = rng.randint(4, 7) if level != "hard" else rng.randint(6, 9)
    rows = rng.randint(3, 5) if level != "hard" else rng.randint(4, 6)
    col = rng.randint(1, cols)
    row = rng.randint(1, rows)

    shapes = [_cell_shape(c, r, rows, "ghost") for c in range(cols) for r in range(rows)]
    shapes.append(_cell_shape(col - 1, row - 1, rows, "a", "A"))
    figure = {"type": FIGURE_TYPE, "width": cols * CELL, "height": rows * CELL, "shapes": shapes}

    options = [f"（{col}, {row}）"]
    while len(options) < 4:
        cand = (f"（{rng.randint(1, cols)}, {rng.randint(1, rows)}）")
        if cand not in options:
            options.append(cand)
    rng.shuffle(options)
    answer = options.index(f"（{col}, {row}）")

    return {
        "text": "图中标有 A 的格子在第几列第几行？用数对表示。",
        "options": options,
        "answer": answer,
        "explanation": f"A 在第 {col} 列、第 {row} 行，数对写作（{col}, {row}），列在前、行在后。",
        "figure": figure,
        # 供测试核对：答案与图形同源
        "check": {"col": col, "row": row},
    }


def generate(level: str, n: int, seed: int) -> list[dict[str, Any]]:
    out, tries = [], 0
    while len(out) < n and tries < n * 30:
        q = make_question(level, seed * 100 + tries)
        tries += 1
        if q and all(q["text"] + str(q["answer"]) != o["text"] + str(o["answer"]) or q["figure"] != o["figure"] for o in out):
            out.append(q)
    return out


def sanitize(value: Any) -> dict[str, Any]:
    """图形本身按 gridshape 校验；这里只确认类型对得上。"""
    if not isinstance(value, dict) or str(value.get("type", "")).lower() != FIGURE_TYPE:
        return {}
    return gf.sanitize(value)
