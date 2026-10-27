"""小正方体组合体：图示数据、三视图计算与“观察物体”图形题生成.

A solid is a grid of column heights: ``heights[r][c]`` is the number of unit cubes stacked on cell (r, c); row 0 is
the back row, the last row faces the viewer, column 0 is on the left. Views are 0/1 pictures, top row first:

- 前面: one column per grid column, as tall as the tallest stack in that column;
- 上面: the footprint, back row at the top;
- 左面: standing on the left and facing the solid, its front is on the viewer's right, so the columns run
  back → front (the front row is the right-most column).

The question figure is drawn by the browser from this data (no picture is stored), and the answer and the
distractors are computed here, so the picture and the answer always agree. Nothing is asked of a model.
"""
from __future__ import annotations

import random
from functools import lru_cache
from typing import Any

FIGURE_TYPE = "cubes"
DIRECTIONS = {"front": "前面", "top": "上面", "left": "左面"}
LETTERS = "ABCD"
MAX_GRID = 4
MAX_HEIGHT = 4
MAX_VIEW = 6
MAX_PANELS = 7

# Which knowledge points get which kind of picture question (template keys of the RJ 2026 grade-5 map).
NODE_KINDS = {"1-1": "view", "1-2": "same_view", "1-3": "two_views", "1-4": "three_views", "8-3": "three_views"}
KIND_LABELS = {"view": "看组合体选视图", "same_view": "选同一方向看到相同图形的组合体",
               "two_views": "根据两个方向的视图选组合体", "three_views": "根据三视图选组合体"}

Grid = list[list[int]]


# ---------------------------------------------------------------- data checks
def _heights(value: Any) -> Grid | None:
    if not isinstance(value, list) or not 1 <= len(value) <= MAX_GRID:
        return None
    width = len(value[0]) if isinstance(value[0], list) else 0
    if not 1 <= width <= MAX_GRID:
        return None
    out = []
    for row in value:
        if not isinstance(row, list) or len(row) != width:
            return None
        if any(isinstance(v, bool) or not isinstance(v, int) or not 0 <= v <= MAX_HEIGHT for v in row):
            return None
        out.append([int(v) for v in row])
    return out if any(any(r) for r in out) else None


def _view(value: Any) -> Grid | None:
    if not isinstance(value, list) or not 1 <= len(value) <= MAX_VIEW:
        return None
    width = len(value[0]) if isinstance(value[0], list) else 0
    if not 1 <= width <= MAX_VIEW:
        return None
    out = []
    for row in value:
        if not isinstance(row, list) or len(row) != width or any(v not in (0, 1) or isinstance(v, bool) for v in row):
            return None
        out.append([int(v) for v in row])
    return out if any(any(r) for r in out) else None


def sanitize(value: Any) -> dict[str, Any]:
    """The stored form of a cubes figure, or {} when anything is off (the question then has no figure)."""
    if not isinstance(value, dict) or str(value.get("type") or "").strip().lower() != FIGURE_TYPE:
        return {}
    out: dict[str, Any] = {"type": FIGURE_TYPE}
    if value.get("solid") is not None:
        solid = _heights(value.get("solid"))
        if solid is None:
            return {}
        out["solid"] = solid
    panels = value.get("panels") or []
    if not isinstance(panels, list) or len(panels) > MAX_PANELS:
        return {}
    clean = []
    for p in panels:
        if not isinstance(p, dict):
            return {}
        label = str(p.get("label") or "")[:6]
        if "view" in p:
            view = _view(p.get("view"))
            if view is None:
                return {}
            clean.append({"label": label, "view": view})
        elif "solid" in p:
            solid = _heights(p.get("solid"))
            if solid is None:
                return {}
            clean.append({"label": label, "solid": solid})
        else:
            return {}
    if clean:
        out["panels"] = clean
    if "solid" not in out and not clean:
        return {}
    title = str(value.get("title") or "").strip()[:40]
    if title:
        out["title"] = title
    return out


# ---------------------------------------------------------------- geometry
def _trim(h: Grid) -> Grid:
    rows = [r for r in h if any(r)]
    cols = [c for c in range(len(rows[0])) if any(r[c] for r in rows)]
    return [[r[c] for c in cols] for r in rows]


def _bars(heights: list[int]) -> Grid:
    top = max(heights)
    return [[1 if h >= top - i else 0 for h in heights] for i in range(top)]


def view(h: Grid, direction: str) -> Grid:
    h = _trim(h)
    if direction == "front":
        return _bars([max(r[c] for r in h) for c in range(len(h[0]))])
    if direction == "left":
        return _bars([max(r) for r in h])
    if direction == "top":
        return [[1 if v else 0 for v in r] for r in h]
    raise ValueError(direction)


def _key(g: Grid) -> tuple[tuple[int, ...], ...]:
    return tuple(tuple(r) for r in g)


def _connected(h: Grid) -> bool:
    cells = {(r, c) for r, row in enumerate(h) for c, v in enumerate(row) if v}
    if not cells:
        return False
    seen, stack = set(), [next(iter(cells))]
    while stack:
        r, c = stack.pop()
        if (r, c) in seen:
            continue
        seen.add((r, c))
        stack.extend(n for n in ((r + 1, c), (r - 1, c), (r, c + 1), (r, c - 1)) if n in cells)
    return seen == cells


def count(h: Grid) -> int:
    return sum(sum(r) for r in h)


# Oblique drawing used by the page (cube edge s, depth step DEPTH*s up and to the right); kept in step with the JS.
DEPTH = 0.45


def _faces(h: Grid, s: float = 20.0) -> list[tuple[tuple[int, int, int], list[tuple[float, float]]]]:
    rows, cols, top = len(h), len(h[0]), max(max(r) for r in h)
    dx = dy = DEPTH * s
    oy = top * s + rows * dy
    out = []
    for r in range(rows):
        d = rows - 1 - r
        for c in range(cols):
            for z in range(h[r][c]):
                x, y = c * s + d * dx, oy - (z + 1) * s - d * dy
                cube = (r, c, z)
                out.append((cube, [(x, y), (x + s, y), (x + s, y + s), (x, y + s)]))
                out.append((cube, [(x, y), (x + dx, y - dy), (x + s + dx, y - dy), (x + s, y)]))
                out.append((cube, [(x + s, y), (x + s + dx, y - dy), (x + s + dx, y + s - dy), (x + s, y + s)]))
    return out


def _inside(px: float, py: float, poly: list[tuple[float, float]]) -> bool:
    hit = False
    for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1]):
        if (y1 > py) != (y2 > py) and px < (x2 - x1) * (py - y1) / (y2 - y1) + x1:
            hit = not hit
    return hit


def all_visible(h: Grid) -> bool:
    """Every cube shows at least a little in the drawing (painter's order as on the page): no hidden cube, so two
    different solids never look the same."""
    return _visible(_key(h))


@lru_cache(maxsize=4096)
def _visible(k: tuple[tuple[int, ...], ...], min_px: int = 10) -> bool:
    h = [list(r) for r in k]
    faces = _faces(h, 10.0)
    xs = [x for _, poly in faces for x, _ in poly]
    ys = [y for _, poly in faces for _, y in poly]
    seen: dict[tuple[int, int, int], int] = {}
    for py in range(int(min(ys)), int(max(ys)) + 1):
        for px in range(int(min(xs)), int(max(xs)) + 1):
            owner = None
            for cube, poly in faces:
                if _inside(px + 0.5, py + 0.5, poly):
                    owner = cube
            if owner is not None:
                seen[owner] = seen.get(owner, 0) + 1
    return all(seen.get((r, c, z), 0) >= min_px for r in range(len(h)) for c in range(len(h[0])) for z in range(h[r][c]))


LEVELS = {  # rows, cols, tallest stack, cube count range
    "basic": {"rows": (1, 2), "cols": (2, 3), "height": 2, "cubes": (3, 5)},
    "medium": {"rows": (2, 2), "cols": (2, 3), "height": 2, "cubes": (4, 6)},
    "hard": {"rows": (2, 3), "cols": (3, 3), "height": 3, "cubes": (5, 8)},
}


def random_solid(rng: random.Random, level: str) -> Grid:
    p = LEVELS[level]
    for _ in range(500):
        rows, cols = rng.randint(*p["rows"]), rng.randint(*p["cols"])
        h = [[rng.choice([0, 1, 1, 1] + list(range(2, p["height"] + 1))) for _ in range(cols)] for _ in range(rows)]
        if not any(any(r) for r in h):
            continue
        h = _trim(h)
        if len(h) == rows and len(h[0]) == cols and _connected(h) and p["cubes"][0] <= count(h) <= p["cubes"][1] and all_visible(h):
            return h
    return [[1, 1], [1, 0]]


def mutate(rng: random.Random, h: Grid, level: str) -> Grid:
    """A nearby solid: one cube added, removed or moved (still connected, still within the level's size)."""
    p = LEVELS[level]
    for _ in range(200):
        g = [row[:] for row in h]
        if rng.random() < 0.3 and len(g) < p["rows"][1] + 1:
            g = [[0] * len(g[0])] + g if rng.random() < 0.5 else g + [[0] * len(g[0])]
        if rng.random() < 0.3 and len(g[0]) < 4:
            g = [row + [0] for row in g] if rng.random() < 0.5 else [[0] + row for row in g]
        cells = [(r, c) for r in range(len(g)) for c in range(len(g[0]))]
        r, c = rng.choice(cells)
        op = rng.random()
        if op < 0.45 and g[r][c] < p["height"]:
            g[r][c] += 1
        elif op < 0.8 and g[r][c] > 0:
            g[r][c] -= 1
        else:
            r2, c2 = rng.choice(cells)
            if g[r][c] == 0 or g[r2][c2] >= p["height"]:
                continue
            g[r][c] -= 1
            g[r2][c2] += 1
        if not any(any(x) for x in g):
            continue
        g = _trim(g)
        if _connected(g) and _key(g) != _key(h) and len(g) <= MAX_GRID and len(g[0]) <= MAX_GRID and all_visible(g):
            return g
    return h


# ---------------------------------------------------------------- questions
def _describe(direction: str, v: Grid) -> str:
    if direction == "top":
        return "从上面看，有 %d 行：%s。" % (len(v), "；".join("第 %d 行 %d 个" % (i + 1, sum(r)) for i, r in enumerate(v)))
    cols = [sum(v[i][c] for i in range(len(v))) for c in range(len(v[0]))]
    side = "从左往右" if direction == "front" else "从左往右（站在左面看，右边是组合体的前面）"
    return "从%s看，%s各列分别有 %s 个正方形。" % (DIRECTIONS[direction], side, "、".join(map(str, cols)))


def _shuffle_options(rng: random.Random, correct: Any, wrong: list[Any]) -> tuple[list[Any], int]:
    items = [correct] + wrong[:3]
    order = list(range(4))
    rng.shuffle(order)
    return [items[i] for i in order], order.index(0)


def _distinct_views(rng: random.Random, h: Grid, direction: str, level: str) -> list[Grid] | None:
    answer = view(h, direction)
    seen = {_key(answer)}
    pool = [view(h, d) for d in DIRECTIONS if d != direction]
    pool.append([list(reversed(r)) for r in answer])
    for _ in range(60):
        pool.append(view(mutate(rng, h, level), direction))
    out = []
    for g in pool:
        if _key(g) not in seen:
            seen.add(_key(g))
            out.append(g)
        if len(out) == 3:
            return out
    return None


def _distinct_solids(rng: random.Random, h: Grid, level: str, differs: Any) -> list[Grid] | None:
    out, seen = [], {_key(h)}
    for _ in range(300):
        g = mutate(rng, h if rng.random() < 0.7 else (out[-1] if out else h), level)
        if _key(g) in seen or not differs(g):
            continue
        seen.add(_key(g))
        out.append(g)
        if len(out) == 3:
            return out
    return None


def make_question(kind: str, level: str, seed: int) -> dict[str, Any] | None:
    """One single-choice question with its cubes figure, answer and explanation; None when no clean set exists."""
    rng = random.Random(seed)
    h = random_solid(rng, level)
    directions = ["front", "top"] if level == "basic" else ["front", "top", "left"]
    d = rng.choice(directions)
    if kind == "view":
        wrong = _distinct_views(rng, h, d, level)
        if wrong is None:
            return None
        options, right = _shuffle_options(rng, view(h, d), wrong)
        figure = {"type": FIGURE_TYPE, "solid": h, "panels": [{"label": LETTERS[i], "view": g} for i, g in enumerate(options)]}
        text = f"下面的组合体是用同样大的小正方体搭成的。从{DIRECTIONS[d]}看到的图形是（　　）。"
        why = _describe(d, view(h, d))
    elif kind == "same_view":
        target = view(h, d)
        wrong = _distinct_solids(rng, h, level, lambda g: _key(view(g, d)) != _key(target))
        if wrong is None:
            return None
        options, right = _shuffle_options(rng, h, wrong)
        figure = {"type": FIGURE_TYPE, "panels": [{"label": "图①", "view": target}] +
                  [{"label": LETTERS[i], "solid": g} for i, g in enumerate(options)]}
        text = f"图①是从{DIRECTIONS[d]}看到的图形。下面哪个组合体从{DIRECTIONS[d]}看到的也是图①？（　　）"
        why = _describe(d, target) + "其他组合体从这个方向看到的图形都不一样。"
    elif kind in ("two_views", "three_views"):
        dirs = ["front", "top"] if kind == "two_views" else ["front", "top", "left"]
        given = {x: view(h, x) for x in dirs}
        wrong = _distinct_solids(rng, h, level, lambda g: any(_key(view(g, x)) != _key(given[x]) for x in dirs))
        if wrong is None:
            return None
        options, right = _shuffle_options(rng, h, wrong)
        figure = {"type": FIGURE_TYPE, "panels": [{"label": DIRECTIONS[x], "view": given[x]} for x in dirs] +
                  [{"label": LETTERS[i], "solid": g} for i, g in enumerate(options)]}
        names = "、".join(DIRECTIONS[x] for x in dirs)
        text = f"一个组合体从{names}看到的图形如下。这个组合体是（　　）。"
        why = "".join(_describe(x, given[x]) for x in dirs) + "只有一个组合体同时符合这些图形。"
    else:
        raise ValueError(kind)
    return {"question_type": "single_choice", "text": text, "options": [f"图{LETTERS[i]}" for i in range(4)],
            "correct_index": right, "explanation": why + f"所以选 {LETTERS[right]}。", "figure": figure}


def generate(node_key: str, level: str, n: int, seed: int) -> list[dict[str, Any]]:
    if node_key not in NODE_KINDS:
        raise ValueError("这个知识点暂时没有系统画图题")
    if level not in LEVELS:
        raise ValueError("难度档不对")
    kind = NODE_KINDS[node_key]
    out, seen, tries = [], set(), 0
    while len(out) < n and tries < n * 30:
        q = make_question(kind, level, seed * 1000 + tries)
        tries += 1
        if q is None:
            continue
        fp = repr(q["figure"])
        if fp in seen:
            continue
        seen.add(fp)
        out.append(q)
    return out


__all__ = ["DEPTH", "DIRECTIONS", "FIGURE_TYPE", "KIND_LABELS", "NODE_KINDS", "all_visible", "count", "generate", "make_question", "sanitize", "view"]
