"""有趣的密铺：在方格纸上铺出图形，判断哪幅是密铺、补全密铺图案；空隙和重叠由系统逐点检查.

Every tile is a lattice polygon whose edges run along the grid or at 45°, so a tiling cut off at the edge of the
paper still has whole-number corners. A picture is checked by sampling points (off every grid and 45° line):
a tiling covers each point exactly once, a picture with gaps leaves some points uncovered.
"""
from __future__ import annotations

import random
from typing import Any

from changying.services.grid_figures import FIGURE_TYPE, LETTERS, rotate, translate

NODE_KINDS = {"T-1": "which", "T-2": "complete"}
KIND_LABELS = {"which": "密铺：判断哪幅图是密铺（没有空隙、不重叠）", "complete": "设计密铺图案：补上空缺的图形"}
W, H = 10, 6

Pts = list[list[int]]

# Each tile with the lattice that repeats it (a tile and its half-turn partner fill one repeat).
TILES: dict[str, dict[str, Any]] = {
    "平行四边形": {"tiles": [[[0, 0], [2, 0], [4, 2], [2, 2]]], "u": (2, 0), "v": (2, 2)},
    "三角形": {"tiles": [[[0, 0], [4, 0], [2, 2]], [[4, 0], [6, 2], [2, 2]]], "u": (4, 0), "v": (2, 2)},
    "梯形": {"tiles": [[[0, 0], [4, 0], [2, 2], [0, 2]], [[6, 2], [2, 2], [4, 0], [6, 0]]], "u": (6, 0), "v": (0, 2)},
    "六边形": {"tiles": [[[0, 0], [2, 0], [3, 1], [2, 2], [0, 2], [-1, 1]]], "u": (3, 1), "v": (0, 2)},
}
# Not tilings: octagons leave square gaps; trapezoids all facing one way leave triangles.
OCTAGON = {"tiles": [[[1, 0], [2, 0], [3, 1], [3, 2], [2, 3], [1, 3], [0, 2], [0, 1]]], "u": (3, 0), "v": (0, 3)}
ONE_WAY = {"tiles": [[[0, 0], [4, 0], [2, 2], [0, 2]]], "u": (4, 0), "v": (0, 2)}


# ---------------------------------------------------------------- geometry
def _clip(poly: list[tuple[float, float]], w: int, h: int) -> list[tuple[float, float]]:
    """Cut a polygon to the paper (Sutherland–Hodgman)."""
    def cut(pts: list[tuple[float, float]], inside: Any, cross: Any) -> list[tuple[float, float]]:
        out = []
        for i, p in enumerate(pts):
            q = pts[i - 1]
            if inside(p):
                if not inside(q):
                    out.append(cross(q, p))
                out.append(p)
            elif inside(q):
                out.append(cross(q, p))
        return out

    def at_x(k: float) -> Any:
        return lambda a, b: (k, a[1] + (b[1] - a[1]) * (k - a[0]) / (b[0] - a[0]))

    def at_y(k: float) -> Any:
        return lambda a, b: (a[0] + (b[0] - a[0]) * (k - a[1]) / (b[1] - a[1]), k)

    for inside, cross in ((lambda p: p[0] >= 0, at_x(0)), (lambda p: p[0] <= w, at_x(w)),
                          (lambda p: p[1] >= 0, at_y(0)), (lambda p: p[1] <= h, at_y(h))):
        poly = cut(poly, inside, cross) if poly else poly
    return poly


def _area(pts: list[Any]) -> float:
    return abs(sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1]))) / 2


def _tidy(poly: list[tuple[float, float]]) -> Pts | None:
    """Whole-number corners with repeated and in-line corners dropped, or None for nothing left."""
    pts: Pts = []
    for x, y in poly:
        if abs(x - round(x)) > 1e-9 or abs(y - round(y)) > 1e-9:
            raise ValueError("tile edge leaves the grid")
        p = [round(x), round(y)]
        if not pts or pts[-1] != p:
            pts.append(p)
    if len(pts) > 1 and pts[0] == pts[-1]:
        pts.pop()
    changed = True
    while changed and len(pts) >= 3:
        changed = False
        for i in range(len(pts)):
            a, b, c = pts[i - 1], pts[i], pts[(i + 1) % len(pts)]
            if (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0]) == 0:
                del pts[i]
                changed = True
                break
    return pts if len(pts) >= 3 and _area(pts) > 0 else None


def lay(spec: dict[str, Any], shift: tuple[int, int], w: int = W, h: int = H, tones: bool = True) -> list[dict[str, Any]]:
    """The tiles of a pattern that show on the paper, cut at its edges."""
    (ux, uy), (vx, vy) = spec["u"], spec["v"]
    out = []
    for i in range(-8, 12):
        for j in range(-8, 12):
            dx, dy = i * ux + j * vx + shift[0], i * uy + j * vy + shift[1]
            for k, t in enumerate(spec["tiles"]):
                pts = _tidy(_clip([(x + dx, y + dy) for x, y in t], w, h))
                if pts:
                    out.append({"points": pts, "tone": ("a", "b")[(k + i + j) % 2] if tones else "a", "label": ""})
    return out


def _inside(x: float, y: float, poly: Pts) -> bool:
    hit = False
    for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1]):
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            hit = not hit
    return hit


def coverage(shapes: list[dict[str, Any]], w: int = W, h: int = H, sub: int = 4) -> tuple[int, int, int]:
    """(points covered once, points left uncovered, points covered twice or more) over the paper."""
    once = gaps = over = 0
    for i in range(w * sub):
        for j in range(h * sub):
            x, y = (i + 0.13) / sub, (j + 0.21) / sub          # never on a grid line or a 45° line
            n = sum(_inside(x, y, s["points"]) for s in shapes)
            once += n == 1
            gaps += n == 0
            over += n > 1
    return once, gaps, over


def _norm(pts: Pts) -> frozenset[tuple[int, int]]:
    mx, my = min(p[0] for p in pts), min(p[1] for p in pts)
    return frozenset((x - mx, y - my) for x, y in pts)


def _mirror(pts: Pts) -> Pts:
    return [[-x, y] for x, y in pts]


# ---------------------------------------------------------------- questions
def _q(text: str, right: int, why: str, figure: dict[str, Any]) -> dict[str, Any]:
    return {"question_type": "single_choice", "text": text, "options": [f"图{c}" for c in LETTERS], "correct_index": right,
            "explanation": why + f"所以选 {LETTERS[right]}。", "figure": figure}


def _spread(spec: dict[str, Any]) -> dict[str, Any]:
    """The same tiles set a little apart: gaps open up between them."""
    (ux, uy), (vx, vy) = spec["u"], spec["v"]
    return {**spec, "u": (ux + 1, uy), "v": (vx, vy + 1)}


def make_question(kind: str, level: str, seed: int) -> dict[str, Any] | None:
    rng = random.Random(seed)
    names = list(TILES)
    if kind == "which":
        name = rng.choice(names[:2] if level == "basic" else names)
        good, bad = TILES[name], [_spread(TILES[name]), OCTAGON, ONE_WAY]
        odd_one_out = level == "hard" and rng.random() < 0.5
        if odd_one_out:                                   # three tilings and one with gaps: pick the one that is not
            others = [TILES[n] for n in names if n != name]
            rng.shuffle(others)
            pictures, k = [good] + others[:2], rng.randrange(4)
            pictures.insert(k, rng.choice(bad))
        else:
            pictures, k = list(bad), rng.randrange(4)
            pictures.insert(k, good)
        panels = []
        for i, spec in enumerate(pictures):
            shapes = lay(spec, (rng.randint(-2, 0), rng.randint(-1, 0)), tones=spec is not OCTAGON and spec is not ONE_WAY)
            _, gaps, over = coverage(shapes)
            tiled = gaps == 0 and over == 0
            if tiled != ((i == k) != odd_one_out) or over:   # every picture is checked to be what it claims
                return None
            panels.append({"label": f"图{LETTERS[i]}", "shapes": shapes})
        figure = {"type": FIGURE_TYPE, "width": W, "height": H, "panels": panels}
        rule = "密铺要求图形之间既没有空隙，也不重叠。"
        if odd_one_out:
            return _q("下面哪幅图不是密铺？（　　）", k, rule + "有空隙的那幅不是密铺。", figure)
        return _q(f"下面哪幅图是用{name}密铺的？（　　）" if level == "basic" else "下面哪幅图是密铺？（　　）", k,
                  rule + "其他几幅图里图形之间都留有空隙。", figure)

    if kind == "complete":
        name = rng.choice(["三角形", "梯形"] if level == "basic" else ["三角形", "梯形", "平行四边形"])
        spec = TILES[name]
        shapes = lay(spec, (rng.randint(-2, 0), rng.randint(-1, 0)))
        whole = [s for s in shapes if 1 <= min(p[0] for p in s["points"]) and max(p[0] for p in s["points"]) <= W - 1
                 and 1 <= min(p[1] for p in s["points"]) and max(p[1] for p in s["points"]) <= H - 1
                 and _area(s["points"]) == _area(spec["tiles"][0])]
        if not whole:
            return None
        gap = rng.choice(whole)
        rest = [s for s in shapes if s is not gap]
        hole = gap["points"]
        # Options: the tile turned or flipped four different ways; exactly one fills the gap.
        cands = [rotate(hole, [0, 0], True, a) for a in (0, 90, 180, 270)] + [rotate(_mirror(hole), [0, 0], True, a) for a in (0, 90, 180, 270)]
        uniq: list[Pts] = []
        for c in cands:
            if all(_norm(c) != _norm(u) for u in uniq):
                uniq.append(c)
        if len(uniq) < 4:
            return None
        right, wrong = uniq[0], uniq[1:]
        rng.shuffle(wrong)
        opts = [right] + wrong[:3]
        order = list(range(4))
        rng.shuffle(order)
        opts = [opts[i] for i in order]
        k = order.index(0)
        panels = []
        for i, o in enumerate(opts):
            xs, ys = [p[0] for p in o], [p[1] for p in o]
            placed = translate(o, (W - max(xs) - min(xs)) // 2, (H - max(ys) - min(ys)) // 2)
            panels.append({"label": f"图{LETTERS[i]}", "shapes": [{"points": placed, "tone": "a", "label": ""}]})
        # The pattern is a tiling only with the right piece in the gap.
        filled = rest + [{"points": hole, "tone": "a", "label": ""}]
        if coverage(filled)[1:] != (0, 0) or coverage(rest)[1] == 0:
            return None
        figure = {"type": FIGURE_TYPE, "width": W, "height": H, "shapes": rest, "panels": panels,
                  "title": "空白处缺了一块"}
        why = f"这是用{name}密铺的图案。看空白处的形状和朝向：要和旁边的{name}拼在一起，既不留空隙也不重叠。"
        return _q("照样子把密铺图案补完整，空白处应该放（　　）。", k, why, figure)
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


__all__ = ["KIND_LABELS", "NODE_KINDS", "coverage", "generate", "lay", "make_question"]
