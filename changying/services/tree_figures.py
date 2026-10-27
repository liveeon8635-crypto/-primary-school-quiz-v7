"""植树问题：线段图上画出每一棵树（两端都种、只种一端、两端都不种、围成一圈），数据和答案由系统给出和计算.

The picture is a plain ``gridshape`` drawing: one grid unit is one gap between trees. Small cases are drawn in
full so pupils can count; for large numbers the picture shows a small case of the same kind ("先画图找规律").
"""
from __future__ import annotations

import random
from typing import Any

from changying.services.area_figures import fmt
from changying.services.grid_figures import FIGURE_TYPE, LETTERS

NODE_KINDS = {"8-6": "trees"}
KIND_LABELS = {"trees": "植树问题（画线段图找规律）"}
MODES = ("both", "one", "none", "loop")
MODE_TEXT = {"both": "两端都种", "one": "只在一端种", "none": "两端都不种"}
W, H = 12, 6


def count(mode: str, gaps: int) -> int:
    """Trees for a number of gaps: both ends +1, one end =, neither end −1, a closed loop =."""
    return gaps + {"both": 1, "one": 0, "none": -1, "loop": 0}[mode]


def _line_figure(mode: str, gaps: int, step: str, length: str, title: str = "") -> dict[str, Any]:
    x0, y = 0, 2
    xs = range(gaps + 1)
    keep = {"both": xs, "one": xs[:-1], "none": xs[1:-1]}[mode]
    fig: dict[str, Any] = {"type": FIGURE_TYPE, "width": W, "height": H, "hideGrid": True,
                           "dots": [[x0 + x, y] for x in keep],
                           "marks": [{"from": [x0, y], "to": [x0 + gaps, y], "text": length, "style": "seg"},
                                     {"from": [x0, y], "to": [x0 + 1, y], "text": step, "style": "dim"}]}
    if title:
        fig["title"] = title
    return fig


def _loop_figure(a: int, b: int, step: str, title: str = "") -> dict[str, Any]:
    x0, y0 = 0, 1
    ring = ([[x0 + i, y0] for i in range(a)] + [[x0 + a, y0 + j] for j in range(b)]
            + [[x0 + a - i, y0 + b] for i in range(a)] + [[x0, y0 + b - j] for j in range(b)])
    fig: dict[str, Any] = {"type": FIGURE_TYPE, "width": W, "height": H, "hideGrid": True,
                           "shapes": [{"points": [[x0, y0], [x0 + a, y0], [x0 + a, y0 + b], [x0, y0 + b]], "tone": "ghost", "label": ""}],
                           "dots": ring,
                           "marks": [{"from": [x0, y0], "to": [x0 + 1, y0], "text": step, "style": "dim"}]}
    if title:
        fig["title"] = title
    return fig


def _choice(rng: random.Random, text: str, right: int, why: str, figure: dict[str, Any], unit: str) -> dict[str, Any] | None:
    wrong = [v for v in dict.fromkeys([right - 1, right + 1, right - 2, right + 2]) if v > 0 and v != right][:3]
    if len(wrong) < 3:
        return None
    opts = [right] + wrong
    order = list(range(4))
    rng.shuffle(order)
    options = [f"{opts[i]} {unit}" for i in order]
    k = order.index(0)
    return {"question_type": "single_choice", "text": text, "options": options, "correct_index": k,
            "explanation": why + f"所以选 {LETTERS[k]}。", "figure": figure}


def _fill(text: str, answer: float, why: str, figure: dict[str, Any]) -> dict[str, Any]:
    return {"question_type": "fill_blank", "text": text, "options": [], "correct_index": -1, "answer": fmt(answer),
            "explanation": why + f"答案是 {fmt(answer)}。", "figure": figure}


RULE = {"both": "两端都种：棵数 = 间隔数 + 1", "one": "只种一端：棵数 = 间隔数", "none": "两端都不种：棵数 = 间隔数 − 1",
        "loop": "围成一圈（首尾相接）：棵数 = 间隔数"}


def make_question(kind: str, level: str, seed: int) -> dict[str, Any] | None:
    if kind != "trees":
        raise ValueError(kind)
    rng = random.Random(seed)
    mode = rng.choice(MODES)
    d = rng.choice([2, 3, 4, 5, 6, 10])
    step = f"{d} 米"

    if mode == "loop":
        if level == "basic":
            a, b = rng.randint(3, 5), rng.randint(2, 3)
            gaps = 2 * (a + b)
            text = f"一个长方形花坛长 {a * d} 米，宽 {b * d} 米。沿着花坛四周每隔 {d} 米摆一盆花（四个角都摆），一共要摆（　　）盆。"
            why = f"周长 ({a * d} + {b * d}) × 2 = {gaps * d}（米），有 {gaps * d} ÷ {d} = {gaps} 个间隔。{RULE['loop']}，是 {gaps} 盆。"
            return _fill(text, count("loop", gaps), why, _loop_figure(a, b, step))
        gaps = rng.randint(12, 40)
        title = "先看简单的情况：一圈 14 个间隔，摆 14 盆"
        fig = _loop_figure(4, 3, step, title)
        if level == "medium":
            text = f"一个圆形水池的周长是 {gaps * d} 米，沿着水池一周每隔 {d} 米栽一棵树，一共要栽（　　）。"
            why = f"间隔数 = {gaps * d} ÷ {d} = {gaps}。{RULE['loop']}，是 {gaps} 棵。"
            return _choice(rng, text, gaps, why, fig, "棵")
        text = f"沿着一个圆形水池一周每隔 {d} 米栽一棵树，一共栽了 {gaps} 棵。水池的周长是（　　）米。"
        why = f"{RULE['loop']}，所以有 {gaps} 个间隔，周长 = {gaps} × {d} = {gaps * d}（米）。"
        return _fill(text, gaps * d, why, fig)

    what = MODE_TEXT[mode]
    if level == "basic":
        gaps = rng.randint(3 if mode != "none" else 4, 8)
        text = f"一条小路长 {gaps * d} 米，在路的一边每隔 {d} 米种一棵树（{what}），一共要种（　　）棵。"
        why = f"间隔数 = {gaps * d} ÷ {d} = {gaps}。{RULE[mode]}，是 {count(mode, gaps)} 棵。"
        return _fill(text, count(mode, gaps), why, _line_figure(mode, gaps, step, f"{gaps * d} 米"))
    gaps = rng.randint(12, 50)
    small = 4
    title = f"先看简单的情况：{small} 个间隔，{what}，种 {count(mode, small)} 棵"
    fig = _line_figure(mode, small, step, f"{small * d} 米", title)
    trees = count(mode, gaps)
    if level == "medium":
        text = f"一条小路长 {gaps * d} 米，在路的一边每隔 {d} 米种一棵树（{what}），一共要种（　　）。"
        why = f"间隔数 = {gaps * d} ÷ {d} = {gaps}。{RULE[mode]}，是 {trees} 棵。"
        return _choice(rng, text, trees, why, fig, "棵")
    text = f"在一条小路的一边每隔 {d} 米种一棵树（{what}），一共种了 {trees} 棵。这条小路长（　　）米。"
    why = f"{RULE[mode]}，所以间隔数是 {gaps}，路长 = {gaps} × {d} = {gaps * d}（米）。"
    return _fill(text, gaps * d, why, fig)


def generate(node_key: str, level: str, n: int, seed: int) -> list[dict[str, Any]]:
    kind = NODE_KINDS[node_key]
    out, seen, tries = [], set(), 0
    while len(out) < n and tries < n * 40:
        q = make_question(kind, level, seed * 1000 + tries)
        tries += 1
        if q is None or q["text"] in seen:
            continue
        seen.add(q["text"])
        out.append(q)
    return out


__all__ = ["KIND_LABELS", "NODE_KINDS", "count", "generate", "make_question"]
