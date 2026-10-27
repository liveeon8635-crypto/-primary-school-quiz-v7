"""方格纸上的图形运动：图示数据、平移/旋转/轴对称计算与“图形的运动”图形题生成.

A figure is a W×H square grid (y pointing up, like the textbook's 方格纸) with polygons given by integer vertices:

    {"type": "gridshape", "width": 10, "height": 8,
     "shapes": [{"points": [[x, y], ...], "tone": "a" | "b" | "ghost", "label": "A"}],
     "axis": [[x1, y1], [x2, y2]],        # optional symmetry axis l (drawn dashed across the grid)
     "center": [x, y],                    # optional rotation centre O
     "panels": [{"label": "图A", "shapes": [...], "axis": ..., "center": ...}],   # optional answer pictures
     "hideGrid": true,                    # optional: a plain drawing with measurements instead of squared paper
     "marks": [{"from": [x, y], "to": [x, y], "text": "8 cm", "style": "dim" | "height"}]}   # optional measurements

The moved shapes, the answer and the distractors are computed here (typical mistakes: one square too few or too
many, wrong direction, wrong turning direction, flipped instead of turned), so the picture and the answer agree.
"""
from __future__ import annotations

import random
from typing import Any

FIGURE_TYPE = "gridshape"
LETTERS = "ABCD"
MAX_SIDE = 12
MAX_POINTS = 10
MAX_SHAPES = 3
MAX_PANELS = 4
TONES = ("a", "b", "ghost")

NODE_KINDS = {"4-1": "reflect", "4-2": "translate", "4-3": "rotate", "4-4": "combo"}
KIND_LABELS = {"reflect": "选轴对称图形", "translate": "平移：选位置或说出怎样平移", "rotate": "旋转：选位置或说出怎样旋转",
               "combo": "先平移再旋转：说出图形怎样变换"}

# Asymmetric shapes (no mirror or turn of one equals another), so every move draws differently.
SHAPES = [
    [[0, 0], [2, 0], [2, 1], [1, 1], [1, 3], [0, 3]],          # L
    [[0, 0], [3, 0], [1, 2], [0, 2]],                          # right trapezoid
    [[0, 0], [1, 0], [1, 2], [3, 3], [0, 3]],                  # flag
    [[0, 0], [2, 0], [3, 1], [1, 1], [1, 2], [0, 2]],          # boot
]

Pts = list[list[int]]
DIR_TEXT = {(1, 0): "右", (-1, 0): "左", (0, 1): "上", (0, -1): "下"}


# ---------------------------------------------------------------- data checks
def _pt(v: Any, w: int, h: int) -> list[int] | None:
    if not isinstance(v, list) or len(v) != 2 or any(isinstance(x, bool) or not isinstance(x, int) for x in v):
        return None
    return [v[0], v[1]] if 0 <= v[0] <= w and 0 <= v[1] <= h else None


def _shapes(value: Any, w: int, h: int) -> list[dict[str, Any]] | None:
    if not isinstance(value, list) or len(value) > MAX_SHAPES:
        return None
    out = []
    for s in value:
        if not isinstance(s, dict) or s.get("tone", "a") not in TONES:
            return None
        pts = s.get("points")
        if not isinstance(pts, list) or not 3 <= len(pts) <= MAX_POINTS:
            return None
        clean = [_pt(p, w, h) for p in pts]
        if any(p is None for p in clean):
            return None
        out.append({"points": clean, "tone": s.get("tone", "a"), "label": str(s.get("label") or "")[:4]})
    return out


MAX_MARKS = 6


def _marks(value: Any, w: int, h: int) -> list[dict[str, Any]] | None:
    if not isinstance(value, list) or len(value) > MAX_MARKS:
        return None
    out = []
    for m in value:
        if not isinstance(m, dict) or m.get("style") not in ("dim", "height"):
            return None
        a, b = _pt(m.get("from"), w, h), _pt(m.get("to"), w, h)
        text = str(m.get("text") or "").strip()[:12]
        if a is None or b is None or a == b or not text:
            return None
        out.append({"from": a, "to": b, "text": text, "style": m["style"]})
    return out


def _extras(src: dict[str, Any], dst: dict[str, Any], w: int, h: int) -> bool:
    if src.get("axis") is not None:
        a = src["axis"]
        if not isinstance(a, list) or len(a) != 2:
            return False
        ends = [_pt(p, w, h) for p in a]
        if any(p is None for p in ends) or ends[0] == ends[1]:
            return False
        dst["axis"] = ends
    if src.get("center") is not None:
        c = _pt(src["center"], w, h)
        if c is None:
            return False
        dst["center"] = c
    if src.get("marks") is not None:
        marks = _marks(src["marks"], w, h)
        if marks is None:
            return False
        if marks:
            dst["marks"] = marks
    return True


def sanitize(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or str(value.get("type") or "").strip().lower() != FIGURE_TYPE:
        return {}
    w, h = value.get("width"), value.get("height")
    if any(isinstance(x, bool) or not isinstance(x, int) or not 3 <= x <= MAX_SIDE for x in (w, h)):
        return {}
    out: dict[str, Any] = {"type": FIGURE_TYPE, "width": w, "height": h}
    if value.get("hideGrid") is True:
        out["hideGrid"] = True
    shapes = _shapes(value.get("shapes") or [], w, h)
    if shapes is None or not _extras(value, out, w, h):
        return {}
    if shapes:
        out["shapes"] = shapes
    panels = value.get("panels") or []
    if not isinstance(panels, list) or len(panels) > MAX_PANELS:
        return {}
    clean = []
    for p in panels:
        if not isinstance(p, dict):
            return {}
        ps = _shapes(p.get("shapes") or [], w, h)
        if not ps:
            return {}
        item: dict[str, Any] = {"label": str(p.get("label") or "")[:6], "shapes": ps}
        if not _extras(p, item, w, h):
            return {}
        clean.append(item)
    if clean:
        out["panels"] = clean
    if not shapes and not clean:
        return {}
    title = str(value.get("title") or "").strip()[:40]
    if title:
        out["title"] = title
    return out


# ---------------------------------------------------------------- moves
def translate(pts: Pts, dx: int, dy: int) -> Pts:
    return [[x + dx, y + dy] for x, y in pts]


def rotate(pts: Pts, center: list[int], clockwise: bool, angle: int) -> Pts:
    turns = (angle // 90) % 4
    if not clockwise:
        turns = (4 - turns) % 4
    out = []
    for x, y in pts:
        rx, ry = x - center[0], y - center[1]
        for _ in range(turns):                 # one clockwise quarter turn: (x, y) -> (y, -x)
            rx, ry = ry, -rx
        out.append([center[0] + rx, center[1] + ry])
    return out


def reflect(pts: Pts, axis: tuple[str, int]) -> Pts:
    kind, k = axis
    return [[2 * k - x, y] for x, y in pts] if kind == "x" else [[x, 2 * k - y] for x, y in pts]


def _key(pts: Pts) -> frozenset[tuple[int, int]]:
    return frozenset((x, y) for x, y in pts)


def _inside(pts: Pts, w: int, h: int) -> bool:
    return all(0 <= x <= w and 0 <= y <= h for x, y in pts)


def _apart(p: Pts, q: Pts) -> bool:
    """The bounding boxes of the two shapes at most touch."""
    return (max(x for x, _ in p) <= min(x for x, _ in q) or max(x for x, _ in q) <= min(x for x, _ in p)
            or max(y for _, y in p) <= min(y for _, y in q) or max(y for _, y in q) <= min(y for _, y in p))


def _distinct(cands: list[Pts], n: int = 4) -> bool:
    return len({_key(c) for c in cands[:n]}) == n


# ---------------------------------------------------------------- questions
W, H = 10, 8


def _shape(rng: random.Random) -> Pts:
    base = rng.choice(SHAPES)
    return rotate(base, [0, 0], True, rng.choice([0, 90, 180, 270]))


def _place(rng: random.Random, pts: Pts, x_range: tuple[int, int], y_range: tuple[int, int]) -> Pts:
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return translate(pts, rng.randint(*x_range) - min(xs), rng.randint(*y_range) - min(ys))


def _options(rng: random.Random, correct: Any, wrong: list[Any]) -> tuple[list[Any], int]:
    items = [correct] + wrong[:3]
    order = list(range(4))
    rng.shuffle(order)
    return [items[i] for i in order], order.index(0)


def _panel_q(rng: random.Random, original: Pts, correct: Pts, wrong: list[Pts], extra: dict[str, Any]) -> tuple[dict[str, Any], int] | None:
    if not all(_inside(c, W, H) for c in [correct] + wrong) or not _distinct([correct] + wrong):
        return None
    if any(_key(c) == _key(original) for c in [correct] + wrong):
        return None
    options, right = _options(rng, correct, wrong)
    main = {"type": FIGURE_TYPE, "width": W, "height": H, "shapes": [{"points": original, "tone": "a", "label": "A"}], **extra}
    main["panels"] = [{"label": f"图{LETTERS[i]}", "shapes": [{"points": original, "tone": "ghost", "label": ""},
                                                           {"points": c, "tone": "b", "label": ""}], **extra} for i, c in enumerate(options)]
    return main, right


def _q(text: str, options: list[str], right: int, why: str, figure: dict[str, Any]) -> dict[str, Any]:
    return {"question_type": "single_choice", "text": text, "options": options, "correct_index": right,
            "explanation": why + f"所以选 {LETTERS[right]}。", "figure": figure}


def make_question(kind: str, level: str, seed: int) -> dict[str, Any] | None:
    rng = random.Random(seed)
    a = _shape(rng)
    if kind == "reflect":
        vertical = level == "basic" or rng.random() < 0.6
        if vertical:
            k = 5
            original = _place(rng, a, (1, 2 if level == "basic" else 3), (1, 4))
            if max(p[0] for p in original) > k:
                return None
            axis_line, axis = [[k, 0], [k, H]], ("x", k)
            lo, hi = min(p[0] for p in original), max(p[0] for p in original)
            slid = translate(original, 2 * k - lo - hi, 0)                 # moved across, not flipped
            ylo, yhi = min(p[1] for p in original), max(p[1] for p in original)
            upside = [[x, ylo + yhi - y] for x, y in reflect(original, axis)]
            wrong = [reflect(original, ("x", k + 1)), slid, upside]
        else:
            k = 4
            original = _place(rng, a, (2, 6), (k, k))
            if max(p[1] for p in original) > H:
                return None
            axis_line, axis = [[0, k], [W, k]], ("y", k)
            lo, hi = min(p[1] for p in original), max(p[1] for p in original)
            slid = translate(original, 0, 2 * k - lo - hi)
            xlo, xhi = min(p[0] for p in original), max(p[0] for p in original)
            sideways = [[xlo + xhi - x, y] for x, y in reflect(original, axis)]
            wrong = [reflect(original, ("y", k - 1)), slid, sideways]
        correct = reflect(original, axis)
        built = _panel_q(rng, original, correct, wrong, {"axis": axis_line})
        if built is None:
            return None
        figure, right = built
        figure["title"] = "直线 l 是对称轴"
        why = "轴对称图形的对应点到对称轴的距离相等，连线和对称轴垂直；图形要“翻过去”，不是平移过去。"
        return _q("以直线 l 为对称轴，哪幅图画出了图形 A 的轴对称图形？（　　）", [f"图{c}" for c in LETTERS], right, why, figure)

    if kind == "translate":
        d = rng.choice(list(DIR_TEXT))
        n = rng.randint(2, 3) if level == "basic" else rng.randint(3, 5)
        original = _place(rng, a, (1, 5), (1, 4))
        moved = translate(original, d[0] * n, d[1] * n)
        if not _inside(moved, W, H):
            return None
        if level == "basic" or rng.random() < 0.5:
            wrong = [translate(original, d[0] * (n - 1), d[1] * (n - 1)), translate(original, d[0] * (n + 1), d[1] * (n + 1)),
                     rotate(moved, moved[0], True, 90)]
            built = _panel_q(rng, original, moved, wrong, {})
            if built is None:
                return None
            figure, right = built
            why = f"平移时图形的形状、大小和方向都不变，每个点都向{DIR_TEXT[d]}移动 {n} 格。数格子时数对应点之间的格数，不是数两个图形之间空了几格。"
            return _q(f"把图形 A 向{DIR_TEXT[d]}平移 {n} 格，得到的图形是（　　）。", [f"图{c}" for c in LETTERS], right, why, figure)
        size = (max(p[0] for p in original) - min(p[0] for p in original)) if d[0] else (max(p[1] for p in original) - min(p[1] for p in original))
        gap = n - size                      # squares left empty between the two shapes: the usual miscount
        opts = [f"向{DIR_TEXT[d]}平移 {n} 格", f"向{DIR_TEXT[d]}平移 {gap if 0 < gap < n else n - 1} 格",
                f"向{DIR_TEXT[(-d[0], -d[1])]}平移 {n} 格", f"向{DIR_TEXT[(d[1], d[0])]}平移 {n} 格"]
        if len(set(opts)) < 4:
            return None
        options, right = _options(rng, opts[0], opts[1:])
        figure = {"type": FIGURE_TYPE, "width": W, "height": H,
                  "shapes": [{"points": original, "tone": "a", "label": "A"}, {"points": moved, "tone": "b", "label": "B"}]}
        why = f"找一组对应点（比如两个图形的同一个顶点），数它们之间相隔几格：向{DIR_TEXT[d]} {n} 格。"
        return _q("图形 A 怎样平移得到图形 B？（　　）", options, right, why, figure)

    if kind == "rotate":
        original = _place(rng, a, (3, 5), (2, 4))
        o = rng.choice(original)
        cw = rng.random() < 0.5
        angle = 90 if level != "hard" or rng.random() < 0.6 else 180
        moved = rotate(original, o, cw, angle)
        turn = "顺时针" if cw else "逆时针"
        if level == "basic" or rng.random() < 0.5:
            wrong = [rotate(original, o, not cw, angle) if angle == 90 else rotate(original, o, cw, 90),
                     rotate(original, o, cw, 180) if angle == 90 else rotate(original, o, not cw, 90),
                     reflect(original, ("x", o[0]))]
            built = _panel_q(rng, original, moved, wrong, {"center": o})
            if built is None:
                return None
            figure, right = built
            what = f"{turn}旋转 90°" if angle == 90 else "旋转 180°"
            why = f"旋转时点 O 不动，每条边都绕点 O 转同样的角度。先看和点 O 相连的边转到哪里，再画出其他部分：{what}。"
            return _q(f"图形 A 绕点 O {what}后得到的图形是（　　）。", [f"图{c}" for c in LETTERS], right, why, figure)
        if angle == 180:
            return None
        if not _inside(moved, W, H):
            return None
        opts = [f"绕点 O {turn}旋转 90°", f"绕点 O {'逆时针' if cw else '顺时针'}旋转 90°", "绕点 O 旋转 180°", f"绕点 O {turn}旋转 45°"]
        options, right = _options(rng, opts[0], opts[1:])
        figure = {"type": FIGURE_TYPE, "width": W, "height": H, "center": o,
                  "shapes": [{"points": original, "tone": "a", "label": "A"}, {"points": moved, "tone": "b", "label": "B"}]}
        why = f"看和点 O 相连的一条边：从图形 A 到图形 B，它按{turn}方向转了一个直角（90°）。"
        return _q("图形 A 怎样旋转得到图形 B？（　　）", options, right, why, figure)
    if kind == "combo":
        d = rng.choice(list(DIR_TEXT))
        span = (max(p[0] for p in a) - min(p[0] for p in a)) if d[0] else (max(p[1] for p in a) - min(p[1] for p in a))
        n = span + rng.randint(1, 2)
        original = _place(rng, a, (0, 6), (0, 5))
        moved = translate(original, d[0] * n, d[1] * n)
        o = rng.choice(moved)                       # O marks a vertex of the shape after the move
        cw = rng.random() < 0.5
        final = rotate(moved, o, cw, 90)
        if not (_inside(moved, W, H) and _inside(final, W, H)) or not _apart(original, final):
            return None                              # A and B must not overlap, or the picture is unreadable
        turn, other = ("顺时针", "逆时针") if cw else ("逆时针", "顺时针")
        back = DIR_TEXT[(-d[0], -d[1])]

        def apply(dd: tuple[int, int], k: int, clockwise: bool | None) -> Pts:
            t = translate(original, dd[0] * k, dd[1] * k)
            return rotate(t, o, True, 180) if clockwise is None else rotate(t, o, clockwise, 90)

        plans = [(f"先向{DIR_TEXT[d]}平移 {n} 格，再绕点 O {turn}旋转 90°", apply(d, n, cw)),
                 (f"先向{DIR_TEXT[d]}平移 {n} 格，再绕点 O {other}旋转 90°", apply(d, n, not cw)),
                 (f"先向{DIR_TEXT[d]}平移 {n - 1} 格，再绕点 O {turn}旋转 90°", apply(d, n - 1, cw)),
                 (f"先向{back}平移 {n} 格，再绕点 O {turn}旋转 90°", apply((-d[0], -d[1]), n, cw)),
                 (f"先向{DIR_TEXT[d]}平移 {n} 格，再绕点 O 旋转 180°", apply(d, n, None))]
        right_key = _key(final)
        wrong = [t for t, r in plans[1:] if _key(r) != right_key][:3]
        if len(wrong) < 3:
            return None
        options, k = _options(rng, plans[0][0], wrong)
        figure = {"type": FIGURE_TYPE, "width": W, "height": H, "center": o,
                  "shapes": [{"points": original, "tone": "a", "label": "A"}, {"points": final, "tone": "b", "label": "B"}]}
        why = (f"先把图形 A 向{DIR_TEXT[d]}平移 {n} 格，这时它的一个顶点正好落在点 O；再绕点 O {turn}旋转 90°，就和图形 B 重合。"
               "做这类题可以先找平移后的位置，再看绕点 O 转的方向和角度。")
        return _q("图形 A 怎样变换得到图形 B？（　　）", options, k, why, figure)
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


__all__ = ["FIGURE_TYPE", "KIND_LABELS", "NODE_KINDS", "generate", "make_question", "reflect", "rotate", "sanitize", "translate"]
