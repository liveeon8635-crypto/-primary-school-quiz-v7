"""可能性：摸球盒、转盘和摸球结果统计图，题目数据和答案都由系统给出和判断.

    {"type": "chance", "kind": "box", "balls": [{"color": "red", "count": 5}, ...]}       # balls in a box
    {"type": "chance", "kind": "spinner", "sectors": ["red", "yellow", ...]}               # equal sectors
    {"type": "chance", "kind": "tally", "rows": [{"color": "red", "count": 16}, ...]}     # results of drawing

Every ball and sector also carries its colour's character (红、黄…), so the picture still reads in black and white.
"""
from __future__ import annotations

import random
from typing import Any

FIGURE_TYPE = "chance"
LETTERS = "ABCD"
COLORS = {"red": "红", "yellow": "黄", "blue": "蓝", "green": "绿", "white": "白"}
MAX_BALLS = 20
MAX_SECTORS = 12
MAX_TALLY = 100

NODE_KINDS = {"7-1": "certain", "7-2": "compare", "7-3": "infer"}
KIND_LABELS = {"certain": "一定、可能、不可能（摸球）", "compare": "可能性的大小（摸球、转盘）",
               "infer": "根据摸球结果推测盒子里的球"}


# ---------------------------------------------------------------- data checks
def _count(v: Any, top: int) -> int | None:
    return v if isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= top else None


def _rows(value: Any, top: int, total: int) -> list[dict[str, Any]] | None:
    if not isinstance(value, list) or not 1 <= len(value) <= len(COLORS):
        return None
    out, seen = [], set()
    for r in value:
        if not isinstance(r, dict) or r.get("color") not in COLORS or r["color"] in seen:
            return None
        n = _count(r.get("count"), top)
        if n is None:
            return None
        seen.add(r["color"])
        out.append({"color": r["color"], "count": n})
    s = sum(r["count"] for r in out)
    return out if 1 <= s <= total else None


def sanitize(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or str(value.get("type") or "").strip().lower() != FIGURE_TYPE:
        return {}
    kind = value.get("kind")
    out: dict[str, Any] = {"type": FIGURE_TYPE, "kind": kind}
    if kind == "box":
        rows = _rows(value.get("balls"), MAX_BALLS, MAX_BALLS)
        if rows is None:
            return {}
        out["balls"] = rows
    elif kind == "tally":
        rows = _rows(value.get("rows"), MAX_TALLY, MAX_TALLY * 5)
        if rows is None:
            return {}
        out["rows"] = rows
    elif kind == "spinner":
        sectors = value.get("sectors")
        if not isinstance(sectors, list) or not 2 <= len(sectors) <= MAX_SECTORS or any(c not in COLORS for c in sectors):
            return {}
        out["sectors"] = list(sectors)
    else:
        return {}
    title = str(value.get("title") or "").strip()[:40]
    if title:
        out["title"] = title
    return out


# ---------------------------------------------------------------- questions
def box(counts: dict[str, int], title: str = "") -> dict[str, Any]:
    f: dict[str, Any] = {"type": FIGURE_TYPE, "kind": "box", "balls": [{"color": c, "count": n} for c, n in counts.items() if n]}
    if title:
        f["title"] = title
    return f


def _q(rng: random.Random, text: str, right: str, wrong: list[str], why: str, figure: dict[str, Any]) -> dict[str, Any] | None:
    opts = [right] + [w for w in dict.fromkeys(wrong) if w != right][:3]
    if len(opts) < 4:
        return None
    order = list(range(4))
    rng.shuffle(order)
    options = [opts[i] for i in order]
    k = options.index(right)
    return {"question_type": "single_choice", "text": text, "options": options, "correct_index": k,
            "explanation": why + f"所以选 {LETTERS[k]}。", "figure": figure}


def _fill(text: str, answer: int, why: str, figure: dict[str, Any]) -> dict[str, Any]:
    return {"question_type": "fill_blank", "text": text, "options": [], "correct_index": -1, "answer": str(answer),
            "explanation": why + f"答案是 {answer}。", "figure": figure}


def statement_true(counts: dict[str, int], word: str, color: str) -> bool:
    """一定 / 可能 / 不可能 摸到 color (or 比: "c>d", c more likely than d), for the balls in the box."""
    if word == "比":
        c, d = color.split(">")
        return counts.get(c, 0) > counts.get(d, 0)
    n, total = counts.get(color, 0), sum(counts.values())
    return {"一定": n == total, "可能": 0 < n, "不可能": n == 0}[word]


def _desc(counts: dict[str, int]) -> str:
    return "、".join(f"{n} 个{COLORS[c]}球" for c, n in counts.items() if n)


def _mixes(total: int, k: int) -> list[tuple[int, ...]]:
    if k == 1:
        return [(total,)]
    return [(i,) + rest for i in range(total + 1) for rest in _mixes(total - i, k - 1)]


def _even(total: int, k: int) -> tuple[int, ...]:
    base = [total // k] * k
    base[0] += total - sum(base)
    return tuple(base)


def make_question(kind: str, level: str, seed: int) -> dict[str, Any] | None:
    rng = random.Random(seed)
    palette = list(COLORS)
    rng.shuffle(palette)

    if kind == "certain":
        k = {"basic": rng.choice([1, 2]), "medium": rng.choice([2, 3]), "hard": 3}[level]
        counts = {c: rng.randint(1, 5) for c in palette[:k]}
        absent = palette[k]
        stmts = [(w, c) for w in ("一定", "可能", "不可能") for c in list(counts) + [absent]]
        if level == "hard":                       # also compare two colours: 摸到红球的可能性比黄球大
            stmts += [("比", c + ">" + d) for c in counts for d in counts if c != d and counts[c] != counts[d]]
        true = [s for s in stmts if statement_true(counts, *s)]
        false = [s for s in stmts if not statement_true(counts, *s)]
        rng.shuffle(true)
        rng.shuffle(false)
        if not true or len(false) < 3:
            return None
        word, color = true[0]

        def say(s: tuple[str, str]) -> str:
            if s[0] == "比":
                c, d = s[1].split(">")
                return f"摸到{COLORS[c]}球的可能性比{COLORS[d]}球大"
            return f"{s[0]}摸到{COLORS[s[1]]}球"

        why = f"盒子里有 {_desc(counts)}。"
        if word == "比":
            c, d = color.split(">")
            why += f"{COLORS[c]}球（{counts[c]} 个）比{COLORS[d]}球（{counts[d]} 个）多，摸到{COLORS[c]}球的可能性就大。"
        else:
                why += {"一定": f"只有{COLORS[color]}球，摸出的一定是{COLORS[color]}球。",
                    "可能": f"盒子里有{COLORS[color]}球，所以可能摸到。",
                    "不可能": f"盒子里没有{COLORS[color]}球，所以不可能摸到。"}[word]
        return _q(rng, "从盒子里任意摸出一个球，下面说法正确的是（　　）。", say(true[0]), [say(s) for s in false[:3]], why, box(counts))

    if kind == "compare":
        spinner = level == "medium" and rng.random() < 0.5
        counts = dict(zip(palette[:4], rng.sample(range(1, 5) if spinner else range(1, 7), 4)))
        most, least = max(counts, key=counts.get), min(counts, key=counts.get)
        names = [f"{COLORS[c]}色" for c in counts]
        if level == "hard":
            others = max(n for c, n in counts.items() if c != least)
            need = others - counts[least] + 1
            why = f"现在{COLORS[least]}球最少，只有 {counts[least]} 个；最多的有 {others} 个。{COLORS[least]}球要比它多才能可能性最大：{others} + 1 − {counts[least]} = {need}（个）。"
            return _fill(f"盒子里有 {_desc(counts)}。至少再放入（　　）个{COLORS[least]}球，摸到{COLORS[least]}球的可能性才最大。",
                         need, why, box(counts))
        ask_most = rng.random() < 0.6
        target = most if ask_most else least
        if spinner:
            sectors = [c for c, n in counts.items() for _ in range(n)]
            rng.shuffle(sectors)
            fig = {"type": FIGURE_TYPE, "kind": "spinner", "sectors": sectors}
            why = f"转盘平均分成 {len(sectors)} 份，{COLORS[target]}色占 {counts[target]} 份，是{'最多' if ask_most else '最少'}的，所以指针停在{COLORS[target]}色区域的可能性{'最大' if ask_most else '最小'}。"
            return _q(rng, f"转动转盘，指针停在哪种颜色区域的可能性{'最大' if ask_most else '最小'}？（　　）",
                      f"{COLORS[target]}色", [n for n in names if n != f"{COLORS[target]}色"], why, fig)
        why = f"{COLORS[target]}球有 {counts[target]} 个，数量{'最多' if ask_most else '最少'}，摸到它的可能性就{'最大' if ask_most else '最小'}。"
        return _q(rng, f"从盒子里任意摸出一个球，摸到哪种颜色的球可能性{'最大' if ask_most else '最小'}？（　　）",
                  f"{COLORS[target]}色", [n for n in names if n != f"{COLORS[target]}色"], why, box(counts))

    if kind == "infer":
        trials = rng.choice([20, 30, 40, 50])
        if level == "basic":
            share = dict(zip(palette[:3], sorted(rng.sample([5, 3, 2, 1], 3), reverse=True)))
            total = sum(share.values())
            counts = {c: round(trials * s / total) for c, s in share.items()}
            counts[palette[0]] += trials - sum(counts.values())
            top = palette[0]
            if sorted(counts.values())[-1] < 1.4 * sorted(counts.values())[-2]:
                return None
            fig = {"type": FIGURE_TYPE, "kind": "tally", "rows": [{"color": c, "count": n} for c, n in counts.items()],
                   "title": f"摸 {trials} 次的结果（每次摸完放回）"}
            why = f"{COLORS[top]}球被摸到 {counts[top]} 次，比其他颜色多得多，说明盒子里{COLORS[top]}球可能最多。"
            return _q(rng, "根据摸球结果，盒子里哪种颜色的球可能最多？（　　）", f"{COLORS[top]}色",
                      [f"{COLORS[c]}色" for c in palette[1:4]], why, fig)
        cols = palette[:2] if level == "medium" else palette[:3]
        size = 10
        mixes = [m for m in _mixes(size, len(cols)) if min(m) >= 1]
        truth = rng.choice([m for m in mixes if max(m) >= 6])
        got = [round(trials * t / size) for t in truth]
        got[0] += trials - sum(got)
        if min(got) < 0:
            return None
        seen = [g / trials * size for g in got]

        def gap(m: tuple[int, ...]) -> float:
            return sum(abs(x - y) for x, y in zip(m, seen))

        ranked = sorted(mixes, key=gap)
        if ranked[0] != truth or gap(ranked[1]) - gap(truth) < 1:
            return None
        # Wrong answers: the colours swapped round, an even mix, and others clearly further from the results.
        wrong = [m for m in [tuple(reversed(truth)), _even(size, len(cols))] + ranked[3:] if m != truth and gap(m) >= gap(truth) + 2][:3]

        def fmt(m: tuple[int, ...]) -> str:
            return "，".join(f"{COLORS[c]}球 {n} 个" for c, n in zip(cols, m))

        fig = {"type": FIGURE_TYPE, "kind": "tally", "rows": [{"color": c, "count": n} for c, n in zip(cols, got)],
               "title": f"摸 {trials} 次的结果（每次摸完放回）"}
        why = (f"摸了 {trials} 次，" + "，".join(f"{COLORS[c]}球 {n} 次" for c, n in zip(cols, got))
               + f"。每种颜色被摸到的次数占的份数，大约就是它在 {size} 个球里占的个数：" + fmt(truth) + " 最接近。"
               "摸到次数越多的颜色，盒子里这种球可能越多。")
        names = "、".join(COLORS[c] for c in cols)
        return _q(rng, f"盒子里有 {size} 个球，只有{names}{'两' if len(cols) == 2 else '三'}种颜色。根据摸球结果，盒子里最可能是（　　）。",
                  fmt(truth), [fmt(m) for m in wrong], why, fig)
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


__all__ = ["COLORS", "FIGURE_TYPE", "KIND_LABELS", "NODE_KINDS", "box", "generate", "make_question", "sanitize", "statement_true"]
