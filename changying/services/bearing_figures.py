"""方向与距离图形题：画 O 和 A 两个格子，方向角与距离由坐标算出。"""
from __future__ import annotations

import math
import random
from typing import Any

from changying.services import grid_figures as gf

FIGURE_TYPE = "gridshape"
NODE_KINDS = {"direction": "direction"}
KIND_LABELS = {"direction": "看图说出方向和距离"}
LEVELS = ("basic", "medium", "hard")
OFFSETS = [(0, 4), (4, 0), (0, 5), (5, 0), (3, 4), (4, 3), (6, 8), (8, 6), (4, 4)]


def _cell(x: int, y: int, tone: str, label: str) -> dict[str, Any]:
    """一格（整数格点），label 画在格子中间。"""
    return {"points": [[x, y], [x + 1, y], [x + 1, y + 1], [x, y + 1]], "tone": tone, "label": label}


def describe(dx: int, dy: int) -> tuple[str, int]:
    dist = int(round(math.hypot(dx, dy)))
    if dx == 0:
        return ("正北" if dy > 0 else "正南"), dist
    if dy == 0:
        return ("正东" if dx > 0 else "正西"), dist
    ang = int(round(math.degrees(math.atan2(abs(dx), abs(dy)))))
    return f"{'北' if dy > 0 else '南'}偏{'东' if dx > 0 else '西'} {ang}°", dist


def make_question(level: str, seed: int) -> dict[str, Any] | None:
    rng = random.Random(seed)
    pool = OFFSETS[:6] if level == "basic" else OFFSETS
    dx, dy = rng.choice(pool)

    ox, oy = 1, 1
    ax, ay = ox + dx, oy + dy
    w = max(ax, ox) + 2
    h = max(ay, oy) + 2
    w = max(w, 3)
    h = max(h, 3)
    if w > 12 or h > 12:
        return None

    shapes = [_cell(ox, oy, "b", "O"), _cell(ax, ay, "a", "A")]
    figure = {"type": FIGURE_TYPE, "width": w, "height": h, "shapes": shapes}

    direction, dist = describe(dx, dy)
    answer_text = f"{direction}，{dist} 格"
    options = [answer_text]
    for _ in range(40):
        if len(options) >= 4:
            break
        ddx, ddy = rng.choice(OFFSETS)
        d2, dist2 = describe(ddx, ddy)
        cand = f"{d2}，{dist2} 格"
        if cand not in options:
            options.append(cand)
    if len(options) < 4 or not gf.sanitize(figure):
        return None
    rng.shuffle(options)

    return {
        "text": "图中上方为北。A 在 O 的什么方向、距离多少格？",
        "options": options,
        "answer": options.index(answer_text),
        "explanation": f"从 O 向北 {dy} 格、向东 {dx} 格到 A，所以是 {direction} 方向，距离 {dist} 格。",
        "figure": figure,
        "check": {"dx": dx, "dy": dy, "dir": direction, "dist": dist},
    }


def generate(level: str, n: int, seed: int) -> list[dict[str, Any]]:
    out, tries = [], 0
    while len(out) < n and tries < n * 60:
        q = make_question(level, seed * 100 + tries)
        tries += 1
        if q and all(q["options"][q["answer"]] != o["options"][o["answer"]] for o in out):
            out.append(q)
    return out


def sanitize(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or str(value.get("type", "")).lower() != FIGURE_TYPE:
        return {}
    return gf.sanitize(value)
