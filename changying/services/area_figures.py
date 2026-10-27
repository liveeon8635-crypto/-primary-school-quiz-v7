"""多边形的面积：方格图数面积、标尺寸图选公式/填结果，数据和答案都由系统给出和计算.

Figures reuse the squared-paper type (``gridshape``): on squared paper each square is 1 cm²; plain drawings
(``hideGrid``) carry the measurements as marks (底/上底/下底 as dimension lines, 高 as a dashed line with a right
angle). The slanted side is labelled too, because 底 × 斜边 is the classic mistake the distractors are built from.
"""
from __future__ import annotations

import math
import random
from typing import Any

from changying.services.grid_figures import FIGURE_TYPE, LETTERS

NODE_KINDS = {"6-1": "parallelogram", "6-2": "triangle", "6-3": "trapezoid", "6-4": "composite", "6-5": "estimate", "6-6": "lattice"}
KIND_LABELS = {"parallelogram": "平行四边形的面积（方格图、标尺寸）", "triangle": "三角形的面积（方格图、标尺寸）",
               "trapezoid": "梯形的面积（方格图、标尺寸）", "composite": "组合图形的面积（分割、添补）",
               "estimate": "估计不规则图形的面积（满格按 1 格、不满按半格）", "lattice": "格点多边形的面积（方格图）"}
W, H = 12, 8


def fmt(x: float) -> str:
    return str(int(x)) if float(x).is_integer() else f"{x:g}"


def _fig(points: list[list[int]], marks: list[dict[str, Any]] | None = None, grid: bool = True, title: str = "") -> dict[str, Any]:
    f: dict[str, Any] = {"type": FIGURE_TYPE, "width": W, "height": H, "shapes": [{"points": points, "tone": "a", "label": ""}]}
    if not grid:
        f["hideGrid"] = True
    if marks:
        f["marks"] = marks
    if title:
        f["title"] = title
    return f


def _dim(a: list[int], b: list[int], text: str) -> dict[str, Any]:
    return {"from": a, "to": b, "text": text, "style": "dim"}


def _height(top: list[int], foot: list[int], text: str) -> dict[str, Any]:
    return {"from": top, "to": foot, "text": text, "style": "height"}


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


GRID_TITLE = "每个小方格表示 1 平方厘米"


def make_question(kind: str, level: str, seed: int) -> dict[str, Any] | None:
    rng = random.Random(seed)
    x0, y0 = 1, 1
    style = "grid" if level == "basic" else ("choice" if level == "medium" else rng.choice(["choice", "reverse"]))
    cm = "平方厘米"

    if kind == "parallelogram":
        a, h, t = rng.randint(4, 7), rng.randint(2, 5), rng.randint(1, 3)
        pts = [[x0, y0], [x0 + a, y0], [x0 + a + t, y0 + h], [x0 + t, y0 + h]]
        area, s = a * h, h + rng.randint(1, 2)
        why = f"平行四边形的面积 = 底 × 高 = {a} × {h} = {fmt(area)}（{cm}）。"
        if style == "grid":
            return _fill("下面平行四边形的面积是（　　）平方厘米。", area, f"数一数：底 {a} 格，高 {h} 格。" + why,
                         _fig(pts, title=GRID_TITLE))
        marks = [_dim(pts[0], pts[1], f"{a} cm"), _height(pts[3], [x0 + t, y0], f"{h} cm"), _dim(pts[1], pts[2], f"{s} cm")]
        if style == "choice":
            return _choice(rng, "下面平行四边形的面积是（　　）。", f"{fmt(area)} {cm}",
                           [f"{fmt(a * s)} {cm}", f"{fmt(area / 2)} {cm}", f"{fmt(2 * (a + s))} {cm}"],
                           f"要用底和对应的高相乘，不能用斜边 {s} cm。" + why, _fig(pts, marks, grid=False))
        marks[1] = _height(pts[3], [x0 + t, y0], "? cm")
        return _fill(f"平行四边形的面积是 {fmt(area)} 平方厘米，底是 {a} 厘米，高是（　　）厘米。", h,
                     f"高 = 面积 ÷ 底 = {fmt(area)} ÷ {a} = {h}（厘米）。", _fig(pts, marks[:2], grid=False))

    if kind == "triangle":
        a, h = rng.choice([4, 5, 6, 7, 8]), rng.randint(2, 5)
        p = rng.randint(0, a)
        pts = [[x0, y0], [x0 + a, y0], [x0 + p, y0 + h]]
        area, s = a * h / 2, h + rng.randint(1, 2)
        why = f"三角形的面积 = 底 × 高 ÷ 2 = {a} × {h} ÷ 2 = {fmt(area)}（{cm}）。"
        if style == "grid":
            return _fill("下面三角形的面积是（　　）平方厘米。", area, f"数一数：底 {a} 格，高 {h} 格。" + why,
                         _fig(pts, title=GRID_TITLE))
        # Label the side farther from the foot of the height: it is always slanted and longer than the height.
        side = pts[1] if p <= a / 2 else pts[0]
        marks = [_dim(pts[0], pts[1], f"{a} cm"), _height(pts[2], [x0 + p, y0], f"{h} cm"), _dim(side, pts[2], f"{s} cm")]
        if style == "choice":
            return _choice(rng, "下面三角形的面积是（　　）。", f"{fmt(area)} {cm}",
                           [f"{fmt(a * h)} {cm}", f"{fmt(a * s / 2)} {cm}", f"{fmt(a * s)} {cm}"],
                           "三角形的面积是同底等高平行四边形面积的一半，别忘了除以 2；高要用和底垂直的那条。" + why,
                           _fig(pts, marks, grid=False))
        marks[1] = _height(pts[2], [x0 + p, y0], "? cm")
        return _fill(f"三角形的面积是 {fmt(area)} 平方厘米，底是 {a} 厘米，高是（　　）厘米。", h,
                     f"高 = 面积 × 2 ÷ 底 = {fmt(area)} × 2 ÷ {a} = {h}（厘米）。", _fig(pts, marks[:2], grid=False))

    if kind == "trapezoid":
        b = rng.randint(6, 9)
        a = rng.randint(2, b - 2)
        h, t = rng.randint(2, 5), rng.randint(0, b - a)
        pts = [[x0, y0], [x0 + b, y0], [x0 + t + a, y0 + h], [x0 + t, y0 + h]]
        area, s = (a + b) * h / 2, h + rng.randint(1, 2)
        why = f"梯形的面积 = （上底 + 下底）× 高 ÷ 2 = （{a} + {b}）× {h} ÷ 2 = {fmt(area)}（{cm}）。"
        if style == "grid":
            return _fill("下面梯形的面积是（　　）平方厘米。", area, f"数一数：上底 {a} 格，下底 {b} 格，高 {h} 格。" + why,
                         _fig(pts, title=GRID_TITLE))
        foot_x = x0 + t if t > 0 else x0 + t + a
        slanted = (pts[1], pts[2]) if pts[2][0] != pts[1][0] else (pts[0], pts[3])      # never label a vertical leg as 斜边
        marks = [_dim(pts[3], pts[2], f"{a} cm"), _dim(pts[0], pts[1], f"{b} cm"),
                 _height([foot_x, y0 + h], [foot_x, y0], f"{h} cm"), _dim(slanted[0], slanted[1], f"{s} cm")]
        if style == "choice":
            return _choice(rng, "下面梯形的面积是（　　）。", f"{fmt(area)} {cm}",
                           [f"{fmt((a + b) * h)} {cm}", f"{fmt(b * h)} {cm}", f"{fmt((a + b) * s / 2)} {cm}"],
                           "上底和下底都要加上，乘高以后还要除以 2；不能用斜边当高。" + why, _fig(pts, marks, grid=False))
        marks[2] = _height([foot_x, y0 + h], [foot_x, y0], "? cm")
        return _fill(f"梯形的面积是 {fmt(area)} 平方厘米，上底 {a} 厘米，下底 {b} 厘米，高是（　　）厘米。", h,
                     f"高 = 面积 × 2 ÷（上底 + 下底）= {fmt(area)} × 2 ÷ {a + b} = {h}（厘米）。",
                     _fig(pts, marks[:3], grid=False))

    if kind == "composite":
        bw, bh = rng.randint(6, 9), rng.randint(4, 6)
        cw, ch = rng.randint(2, bw - 3), rng.randint(1, bh - 2)
        corner = rng.choice(["tr", "tl"])
        if corner == "tr":       # notch cut from the top right corner
            pts = [[x0, y0], [x0 + bw, y0], [x0 + bw, y0 + bh - ch], [x0 + bw - cw, y0 + bh - ch], [x0 + bw - cw, y0 + bh], [x0, y0 + bh]]
        else:
            pts = [[x0, y0], [x0 + bw, y0], [x0 + bw, y0 + bh], [x0 + cw, y0 + bh], [x0 + cw, y0 + bh - ch], [x0, y0 + bh - ch]]
        area = bw * bh - cw * ch
        why = (f"可以先算大长方形 {bw} × {bh} = {bw * bh}，再减去缺掉的小长方形 {cw} × {ch} = {cw * ch}，"
               f"{bw * bh} − {cw * ch} = {area}（{cm}）；也可以分成两个长方形相加。")
        if style == "grid":
            return _fill("下面组合图形的面积是（　　）平方厘米。", area, why, _fig(pts, title=GRID_TITLE))
        # Outer edges only (as in the textbook): the notch's own sizes are worked out by subtraction.
        if corner == "tr":
            marks = [_dim(pts[0], pts[1], f"{bw} cm"), _dim(pts[0], pts[5], f"{bh} cm"), _dim(pts[4], pts[5], f"{bw - cw} cm"),
                     _dim(pts[1], pts[2], f"{bh - ch} cm")]
        else:
            marks = [_dim(pts[0], pts[1], f"{bw} cm"), _dim(pts[1], pts[2], f"{bh} cm"), _dim(pts[2], pts[3], f"{bw - cw} cm"),
                     _dim(pts[5], pts[0], f"{bh - ch} cm")]
        why = (f"缺掉的小长方形长 {bw} − {bw - cw} = {cw}，宽 {bh} − {bh - ch} = {ch}。" + why) if style != "grid" else why
        if style == "choice":
            return _choice(rng, "下面组合图形的面积是（　　）。", f"{fmt(area)} {cm}",
                           [f"{fmt(bw * bh)} {cm}", f"{fmt(bw * bh + cw * ch)} {cm}", f"{fmt(2 * (bw + bh))} {cm}"],
                           "缺掉的部分要减去，不能直接用长 × 宽；周长和面积也不要混淆。" + why, _fig(pts, marks, grid=False))
        return _fill("下面组合图形的面积是（　　）平方厘米。", area, why, _fig(pts, marks, grid=False))
    if kind == "lattice":
        size = {"basic": (4, 3), "medium": (5, 4), "hard": (6, 5)}[level]
        pts = [[x0 + rng.randint(0, size[0]), y0 + rng.randint(0, size[1])] for _ in range(rng.randint(4, 6))]
        hull = _hull(pts)
        if len(hull) < (3 if level == "basic" else 4):
            return None
        area = _area(hull)
        if area < 3:
            return None
        border = sum(_gcd(abs(b[0] - a[0]), abs(b[1] - a[1])) for a, b in zip(hull, hull[1:] + hull[:1]))
        inner = int(area - border / 2 + 1)
        why = (f"可以用添补法：先算把它围住的长方形，再减去四周的直角三角形和长方形。也可以数格点：图形内部有 {inner} 个格点，"
               f"边上有 {border} 个格点，面积 = {inner} + {border} ÷ 2 − 1 = {fmt(area)}（平方厘米）。")
        return _fill("下面格点多边形的面积是（　　）平方厘米。", area, why, _fig(hull, title=GRID_TITLE))

    if kind == "estimate":
        k = rng.randint(6, 8)
        r0 = {"basic": 2.2, "medium": 2.6, "hard": 3.0}[level]
        cx, cy = rng.randint(5, 7), 4
        pts = []
        for i in range(k):
            t = 2 * math.pi * (i + rng.uniform(-0.2, 0.2)) / k
            r = r0 * rng.uniform(0.75, 1.2)
            # Through the middle of a square, not a corner, so the curve rarely just grazes a square.
            pts.append([math.floor(cx + r * 1.3 * math.cos(t)) + 0.5, math.floor(cy + r * math.sin(t)) + 0.5])
        if any(p == q for p, q in zip(pts, pts[1:] + pts[:1])):
            return None
        counted = count_cells(pts, W, H)
        if counted is None:
            return None
        full, part, unsure = counted
        est = full + part / 2
        wrong = [full, full + part, part / 2]
        # A pupil may read a grazed or nearly full square differently; keep every other option out of that reach.
        if full < 3 or min(abs(est - v) for v in wrong) < unsure + 1.5:
            return None
        why = f"满格的有 {full} 个，不满整格的有 {part} 个，不满整格的都按半格算：{full} + {part} ÷ 2 = {fmt(est)}（平方厘米）。"
        fig = {**_fig([], title=GRID_TITLE), "shapes": [{"points": pts, "tone": "a", "label": "", "smooth": True}]}
        return _choice(rng, "估一估，下面不规则图形的面积大约是（　　）。（不满整格的按半格计算）", f"{fmt(est)} {cm}",
                       [f"{fmt(v)} {cm}" for v in wrong], "不满整格的不能丢掉，也不能都按一整格算。" + why, fig)
    raise ValueError(kind)


# ---------------------------------------------------------------- irregular shapes (6-5)
def curve(pts: list[list[int]], steps: int = 24) -> list[tuple[float, float]]:
    """The closed Catmull-Rom curve the browser draws through the points (as cubic Béziers), sampled."""
    n, out = len(pts), []
    for i in range(n):
        p0, p1, p2, p3 = pts[i - 1], pts[i], pts[(i + 1) % n], pts[(i + 2) % n]
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
        for j in range(steps):
            t = j / steps
            u = 1 - t
            out.append((u ** 3 * p1[0] + 3 * u * u * t * c1[0] + 3 * u * t * t * c2[0] + t ** 3 * p2[0],
                        u ** 3 * p1[1] + 3 * u * u * t * c1[1] + 3 * u * t * t * c2[1] + t ** 3 * p2[1]))
    return out


def _inside_poly(x: float, y: float, poly: list[tuple[float, float]]) -> bool:
    hit = False
    for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1]):
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            hit = not hit
    return hit


def _crosses(poly: list[tuple[float, float]]) -> bool:
    segs = list(zip(poly, poly[1:] + poly[:1]))

    def ccw(a: tuple[float, float], b: tuple[float, float], c: tuple[float, float]) -> float:
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

    for i, (a, b) in enumerate(segs):
        for j in range(i + 2, len(segs)):
            if i == 0 and j == len(segs) - 1:
                continue
            c, d = segs[j]
            if ccw(a, b, c) * ccw(a, b, d) < 0 and ccw(c, d, a) * ccw(c, d, b) < 0:
                return True
    return False


def count_cells(pts: list[list[float]], w: int, h: int, sub: int = 8) -> tuple[int, int, int] | None:
    """(full squares, part squares, squares a pupil might read either way) for the drawn curve, or None when the
    curve leaves the paper or crosses itself. A part square is one the curve passes through."""
    poly = curve(pts)
    if _crosses(poly) or any(not (0.3 <= x <= w - 0.3 and 0.3 <= y <= h - 0.3) for x, y in poly):
        return None
    touched = {(math.floor(x), math.floor(y)) for x, y in curve(pts, 160)}
    xs, ys = [x for x, _ in poly], [y for _, y in poly]
    full = part = unsure = 0
    for i in range(math.floor(min(xs)), math.ceil(max(xs))):
        for j in range(math.floor(min(ys)), math.ceil(max(ys))):
            if (i, j) in touched:
                inside = sum(_inside_poly(i + (a + 0.5) / sub, j + (b + 0.5) / sub, poly) for a in range(sub) for b in range(sub))
                part += 1
                unsure += not 0.06 <= inside / sub / sub <= 0.94
            elif _inside_poly(i + 0.5, j + 0.5, poly):
                full += 1
    return full, part, unsure


def _gcd(a: int, b: int) -> int:
    while b:
        a, b = b, a % b
    return a


def _area(pts: list[list[int]]) -> float:
    return abs(sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1]))) / 2


def _hull(pts: list[list[int]]) -> list[list[int]]:
    """Convex hull of lattice points (counter-clockwise), collinear points dropped."""
    p = sorted({(x, y) for x, y in pts})
    if len(p) < 3:
        return []

    def cross(o: tuple[int, int], a: tuple[int, int], b: tuple[int, int]) -> int:
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower: list[tuple[int, int]] = []
    for q in p:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], q) <= 0:
            lower.pop()
        lower.append(q)
    upper: list[tuple[int, int]] = []
    for q in reversed(p):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], q) <= 0:
            upper.pop()
        upper.append(q)
    return [list(q) for q in lower[:-1] + upper[:-1]]


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


__all__ = ["KIND_LABELS", "NODE_KINDS", "fmt", "generate", "make_question"]
