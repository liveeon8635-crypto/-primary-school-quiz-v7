"""数和数量关系的图示：小数乘法的面积模型、用字母表示数量关系的线段图、公顷和平方千米的标尺寸图.

All three are drawn on the ``gridshape`` type, so the figures are checked and stored like the other grid pictures:
- 小数乘法: a 10 × 10 square stands for 1; a tenths × tenths rectangle is shaded, so 0.3 × 0.4 = 0.12 is 12 small squares;
- 线段图: one bar is x, the other is x + a, x − a or k copies of x, drawn to scale with x as 4 squares;
- 公顷: a field drawn to scale with its sides marked in metres or kilometres.
"""
from __future__ import annotations

import random
from typing import Any

from changying.services.area_figures import fmt
from changying.services.grid_figures import FIGURE_TYPE, LETTERS

NODE_KINDS = {"2-2": "decimal", "8-1": "decimal", "5-1": "letters", "8-2": "letters", "6-7": "hectare"}
KIND_LABELS = {"decimal": "小数乘法的面积模型（10×10 方格表示 1）", "letters": "用字母表示数量关系（线段图）",
               "hectare": "公顷和平方千米（按比例画的土地）"}


def _choice(rng: random.Random, text: str, right: str, wrong: list[str], why: str, figure: dict[str, Any]) -> dict[str, Any] | None:
    opts = [right] + [w for w in dict.fromkeys(wrong) if w != right][:3]
    if len(opts) < 4:
        return None
    order = list(range(4))
    rng.shuffle(order)
    options = [opts[i] for i in order]
    k = options.index(right)
    return {"question_type": "single_choice", "text": text, "options": options, "correct_index": k,
            "explanation": why + f"所以选 {LETTERS[k]}。", "figure": figure}


def _fill(text: str, answer: float, why: str, figure: dict[str, Any]) -> dict[str, Any]:
    return {"question_type": "fill_blank", "text": text, "options": [], "correct_index": -1, "answer": fmt(answer),
            "explanation": why + f"答案是 {fmt(answer)}。", "figure": figure}


def _rect(x0: int, y0: int, w: int, h: int, tone: str = "a", label: str = "") -> dict[str, Any]:
    return {"points": [[x0, y0], [x0 + w, y0], [x0 + w, y0 + h], [x0, y0 + h]], "tone": tone, "label": label}


def tenths(n: int) -> str:
    return fmt(n / 10)


def make_question(kind: str, level: str, seed: int) -> dict[str, Any] | None:
    rng = random.Random(seed)

    if kind == "decimal":
        a, b = rng.randint(2, 9), rng.randint(2, 9)
        if a == b:
            return None
        cells = a * b
        product = fmt(cells / 100)
        fig = {"type": FIGURE_TYPE, "width": 10, "height": 10, "title": "整个大正方形表示 1",
               "shapes": [_rect(0, 0, 10, 10, "ghost"), _rect(0, 0, a, b)],
               "marks": [{"from": [0, 0], "to": [a, 0], "text": tenths(a), "style": "dim"},
                         {"from": [0, 0], "to": [0, b], "text": tenths(b), "style": "dim"}]}
        why = (f"大正方形平均分成 100 份，每份是 0.01。涂色部分宽 {tenths(a)}、高 {tenths(b)}，"
               f"有 {a} × {b} = {cells} 个小方格，就是 {product}：{tenths(a)} × {tenths(b)} = {product}。")
        if level == "basic":
            return _choice(rng, "涂色部分用小数表示是（　　）。", product,
                           [fmt(cells / 10), str(cells), tenths(a + b)], why, fig)
        if level == "medium":
            return _choice(rng, "涂色部分可以表示哪个算式？（　　）", f"{tenths(a)} × {tenths(b)}",
                           [f"{tenths(a)} + {tenths(b)}", f"{a} × {b}", f"{fmt(a / 100)} × {tenths(b)}"], why, fig)
        return _fill(f"看图计算：{tenths(a)} × {tenths(b)} =（　　）。", cells / 100,
                     why + "两个一位小数相乘，积有两位小数。", fig)

    if kind == "letters":
        how = rng.choice(["more", "less", "times"])
        a = rng.randint(1, 3) if how != "times" else rng.randint(2, 3)
        unit = 3 if how == "times" and a == 3 else 4    # x is drawn 3 or 4 squares long, so the bars fit
        name1, name2 = rng.choice([("小明", "小红"), ("甲", "乙"), ("红花", "黄花"), ("苹果", "梨")])
        if how == "more":
            length, expr, wrong = unit + a, f"x + {a}", [f"x − {a}", f"{a}x", f"x + {a + 1}"]
            say = f"比{name1}多 {a}"
        elif how == "less":
            if a >= unit:
                return None
            length, expr, wrong = unit - a, f"x − {a}", [f"x + {a}", f"x ÷ {a}" if a > 1 else f"{a + 1}x", f"{a} − x"]
            say = f"比{name1}少 {a}"
        else:
            length, expr, wrong = unit * a, f"{a}x", [f"x + {a}", f"x ÷ {a}", f"{a + 1}x"]
            say = f"是{name1}的 {a} 倍"
        y1, y2 = 4, 1
        shapes = [_rect(2, y1, unit, 1, "a", ""), _rect(2, y2, length, 1, "b", "")]
        marks = [{"from": [2, y1 + 1], "to": [2 + unit, y1 + 1], "text": "x", "style": "dim"}]
        if how == "times":
            shapes[1] = _rect(2, y2, unit, 1, "b", "")
            shapes += [_rect(2 + unit * i, y2, unit, 1, "b", "") for i in range(1, a)]
        elif how == "more":
            marks.append({"from": [2 + unit, y2], "to": [2 + length, y2], "text": str(a), "style": "dim"})
        else:
            marks.append({"from": [2 + length, y2 + 1], "to": [2 + unit, y2 + 1], "text": str(a), "style": "dim"})
        fig = {"type": FIGURE_TYPE, "width": 12, "height": 6, "hideGrid": True, "title": f"上面一条是{name1}，下面一条是{name2}",
               "shapes": shapes, "marks": marks}
        why = f"{name1}是 x，{name2}{say}，所以{name2}是 {expr}。"
        if level != "hard":
            return _choice(rng, f"{name1}有 x 个，看线段图，{name2}有（　　）个。", expr, wrong, why, fig)
        total_x = rng.randint(5, 20)
        if how == "less" and total_x <= a:
            return None
        other = total_x + a if how == "more" else (total_x - a if how == "less" else total_x * a)
        total = total_x + other
        sol = {"more": f"x + x + {a} = {total}，2x = {total - a}，x = {total_x}",
               "less": f"x + x − {a} = {total}，2x = {total + a}，x = {total_x}",
               "times": f"x + {a}x = {total}，{a + 1}x = {total}，x = {total_x}"}[how]
        return _fill(f"看线段图，{name1}和{name2}一共有 {total} 个，{name1}有（　　）个。", total_x,
                     why + "列方程：" + sol + "。", fig)

    if kind == "hectare":
        if level == "hard":
            a, b = rng.randint(3, 10), rng.randint(2, 6)              # tenths of a kilometre, one square each
            km2 = a * b / 100
            fig = {"type": FIGURE_TYPE, "width": 12, "height": 8, "hideGrid": True, "shapes": [_rect(1, 1, a, b)],
                   "marks": [{"from": [1, 1], "to": [1 + a, 1], "text": f"{tenths(a)} km", "style": "dim"},
                             {"from": [1 + a, 1], "to": [1 + a, 1 + b], "text": f"{tenths(b)} km", "style": "dim"}]}
            why = (f"面积 = {tenths(a)} × {tenths(b)} = {fmt(km2)}（平方千米）；1 平方千米 = 100 公顷，"
                   f"{fmt(km2)} 平方千米 = {fmt(km2 * 100)} 公顷。")
            return _fill("这块长方形土地的面积是（　　）公顷。", a * b, why, fig)
        step = 100 if level == "basic" else 50
        a, b = rng.randint(2, 8), rng.randint(2, 6)
        ma, mb = a * step, b * step
        m2 = ma * mb
        if m2 % 100:
            return None
        ha = m2 / 10000
        fig = {"type": FIGURE_TYPE, "width": 12, "height": 8, "hideGrid": True, "shapes": [_rect(1, 1, a, b)],
               "marks": [{"from": [1, 1], "to": [1 + a, 1], "text": f"{ma} m", "style": "dim"},
                         {"from": [1 + a, 1], "to": [1 + a, 1 + b], "text": f"{mb} m", "style": "dim"}]}
        why = f"面积 = {ma} × {mb} = {m2}（平方米）；1 公顷 = 10000 平方米，{m2} 平方米 = {fmt(ha)} 公顷。"
        return _choice(rng, "这块长方形土地的面积是（　　）。", f"{fmt(ha)} 公顷",
                       [f"{fmt(ha * 10)} 公顷", f"{fmt(ha / 10)} 公顷", f"{fmt(ha)} 平方千米"],
                       "边长 100 米的正方形面积是 1 公顷。" + why, fig)
    raise ValueError(kind)


def generate(node_key: str, level: str, n: int, seed: int) -> list[dict[str, Any]]:
    kind = NODE_KINDS[node_key]
    out, seen, tries = [], set(), 0
    while len(out) < n and tries < n * 40:
        q = make_question(kind, level, seed * 1000 + tries)
        tries += 1
        if q is None:
            continue
        fp = repr(q["figure"]) + q["text"]
        if fp in seen:
            continue
        seen.add(fp)
        out.append(q)
    return out


__all__ = ["KIND_LABELS", "NODE_KINDS", "generate", "make_question", "tenths"]
