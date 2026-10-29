"""知识地图：教师维护的单元—知识点—前置关系，以及每个知识点的题目分档。

A map is one JSON document per (school, grade, subject, term):

    {"version": 1,
     "units": [{"key": "U1", "name": "观察简单组合体", "kind": "unit|activity|review", "learned": true}],
     "nodes": [{"key": "1-1", "unit": "U1", "name": "...", "detail": "...", "kind": "core|optional|display|review",
                "prereqs": ["..."], "bankKeys": ["..."], "levels": {"<question id>": "basic|medium|hard"},
                "enabled": false}]}

Only teachers write it. Diagnosis and mastery (later PRs) read the published copy: learned units, core/review
nodes and the nodes the teacher enabled among the optional ones. Display-only nodes never get questions.
"""
from __future__ import annotations

import copy
import re
from typing import Any, Iterable

UNIT_KINDS = {"unit": "单元", "activity": "综合实践", "review": "复习与关联"}
NODE_KINDS = {"core": "必学", "optional": "选学", "display": "只展示", "review": "综合"}
LEVELS = {"basic": "基础", "medium": "中等", "hard": "提高"}
MIN_PER_LEVEL = 2
MIN_PER_NODE = 6
MAX_UNITS = 20
MAX_NODES = 120
_KEY = re.compile(r"^[0-9A-Za-z一-鿿-]{1,12}$")


def _u(key: str, name: str, learned: bool, kind: str = "unit") -> dict[str, Any]:
    return {"key": key, "name": name, "kind": kind, "learned": learned}


def _n(key: str, unit: str, name: str, detail: str, prereqs: Iterable[str] = (), kind: str = "core") -> dict[str, Any]:
    return {"key": key, "unit": unit, "name": name, "detail": detail, "kind": kind, "prereqs": list(prereqs),
            "bankKeys": [name], "levels": {}, "enabled": kind != "optional"}


# 人教版 2026 五年级上册数学，按教材“整理和复习”知识梳理与教学安排表整理，教师已确认（学生学完第四单元）。
RJ2026_G5_MATH_UP = {
    "version": 1,
    "units": [
        _u("U1", "观察简单组合体", True), _u("U2", "小数乘法", True), _u("U3", "小数除法", True), _u("U4", "图形的运动", True),
        _u("U5", "用字母表示数和数量关系", False), _u("U6", "多边形的面积", False),
        _u("UT", "有趣的密铺", False, "activity"), _u("U7", "可能性", False), _u("U8", "复习与关联", False, "review"),
    ],
    "nodes": [
        _n("1-1", "U1", "从不同位置观察同一组合体", "从前面、上面、左面观察同一个组合体，看到的图形可能不同"),
        _n("1-2", "U1", "从同一位置观察不同组合体", "不同的组合体从同一方向看，看到的图形可能相同"),
        _n("1-3", "U1", "根据三个方向的图形确定组合体",
           "只看一个方向的图形不能确定组合体；上面看几行几列，前面看几层几列，左面看几行几层", ["1-1", "1-2"]),
        _n("1-4", "U1", "根据三个方向的图形还原组合体", "先从上面看到的图形入手推测，再补全、调整，最后从三个方向验证", ["1-3"]),
        _n("2-1", "U2", "小数乘整数", "意义和算法"),
        _n("2-2", "U2", "小数乘小数", "积的小数位数；位数不够补 0；末尾的 0 去掉", ["2-1"]),
        _n("2-3", "U2", "积的近似数", "用四舍五入法求积的近似数", ["2-2"]),
        _n("2-4", "U2", "积与乘数的大小关系", "一个数（0 除外）乘大于 1 的数、小于 1 的数，积与这个数的大小关系", ["2-2"]),
        _n("2-5", "U2", "整数乘法运算律推广到小数", "交换律、结合律、分配律用于小数乘法的简便计算", ["2-2"]),
        _n("2-6", "U2", "小数乘法解决问题", "求小数倍、估算、分段计费", ["2-2", "2-3", "2-5"]),
        _n("3-1", "U3", "除数是整数的小数除法", "商的小数点和被除数的小数点对齐；用 0 占位；添 0 继续除", ["2-1"]),
        _n("3-2", "U3", "除数是小数的除法", "用商不变的性质把除数转化成整数", ["3-1"]),
        _n("3-3", "U3", "商与被除数的大小关系", "一个数（0 除外）除以大于 1 的数、小于 1 的数，商与被除数的大小关系", ["3-2"]),
        _n("3-4", "U3", "用近似值解决问题", "进一法、去尾法、四舍五入法", ["3-2", "2-3"]),
        _n("3-5", "U3", "有限小数、无限小数、循环小数", "认识循环节，用简便写法表示循环小数", ["3-1"]),
        _n("4-1", "U4", "轴对称", "对应点到对称轴的距离相等；补全轴对称图形（找点、定点、连线）"),
        _n("4-2", "U4", "平移", "平移的特点；在方格纸上画平移后的图形；用平移、割补的方法求面积"),
        _n("4-3", "U4", "旋转", "旋转的三要素（旋转中心、方向、角度）；旋转的特征；在方格纸上画旋转后的图形"),
        _n("4-4", "U4", "用平移和旋转解决问题", "图形的拼组；欣赏和设计图案", ["4-2", "4-3"]),
        _n("5-1", "U5", "用字母表示数和数量关系", "用字母表示某个量、数量关系、运算律、周长和面积公式、规律", ["2-5"]),
        _n("5-2", "U5", "用含字母的式子解决实际问题", "例如华氏温度和摄氏温度的换算", ["5-1"]),
        _n("6-1", "U6", "平行四边形的面积", "割补法转化成长方形，S=ah；会反求底和高（a=S÷h，h=S÷a）", ["4-2", "2-2", "5-1"]),
        _n("6-2", "U6", "三角形的面积", "两个完全一样的三角形拼成平行四边形，S=ah÷2；会反求高和底（h=2S÷a，a=2S÷h）", ["6-1", "3-2"]),
        _n("6-3", "U6", "梯形的面积", "两个完全一样的梯形拼成平行四边形，S=(a+b)h÷2；会反求高、上底、下底", ["6-1", "3-2"]),
        _n("6-4", "U6", "组合图形的面积", "分割法、添补法、等积变形", ["6-1", "6-2", "6-3"]),
        _n("6-5", "U6", "估计不规则图形的面积", "数格子法；转化为近似的规则图形", ["6-4"]),
        _n("6-6", "U6", "格点多边形的面积", "数学活动：用学过的方法计算格点多边形面积，简要介绍皮克定理", ["6-1", "6-2", "6-3"], "optional"),
        _n("6-7", "U6", "公顷和平方千米", "1 公顷 = 10000 m²；1 km² = 100 公顷 = 1000000 m²"),
        _n("T-1", "UT", "密铺", "认识密铺现象，探索可以密铺的图形的特征"),
        _n("T-2", "UT", "设计密铺图案", "由可以密铺的图形变化得到：借助平移、旋转，或者割补", ["T-1", "4-2", "4-3", "6-1"]),
        _n("T-3", "UT", "密铺小讲堂", "基于密铺的艺术作品；数学上关于密铺的更多知识（拓展阅读）", ["T-1"], "display"),
        _n("7-1", "U7", "认识确定现象和随机现象", "用“可能”“不可能”“一定”描述事件发生的可能性"),
        _n("7-2", "U7", "可能性的大小", "判断事件发生的可能性大小；数量越多可能性越大；抽奖、游戏公平性", ["7-1"]),
        _n("7-3", "U7", "根据试验结果推测可能性的大小", "逆向推理，强化辨析", ["7-2"]),
        _n("7-4", "U7", "掷一掷", "数学活动：类比推理、归纳推理（统计）、演绎推理", ["7-2"], "optional"),
        _n("8-1", "U8", "数与运算：小数的乘、除法", "小数乘、除法运算综合",
           ["2-1", "2-2", "2-3", "2-4", "2-5", "3-1", "3-2", "3-3"], "review"),
        _n("8-2", "U8", "数量关系：表示数量关系的新方法", "用字母和含有字母的式子表示数量关系", ["5-1", "5-2"], "review"),
        _n("8-3", "U8", "图形的位置：还原简单组合体", "根据从不同角度观察的结果还原简单组合体，结果可能不唯一", ["1-3", "1-4"], "review"),
        _n("8-4", "U8", "图形的运动与测量", "借助平移和旋转研究多边形的面积公式；图形在运动中面积不变",
           ["4-2", "4-3", "6-1", "6-2", "6-3"], "review"),
        _n("8-5", "U8", "可能性综合", "不同现象发生的可能性有大有小", ["7-1", "7-2", "7-3"], "review"),
        _n("8-6", "U8", "植树问题", "数学广角：两端都种；两端都不种；一端种另一端不种（与封闭曲线上种相同）", (), "optional"),
    ],
}

TEMPLATES = {
    "rj2026-g5-math-up": {"label": "人教版 2026 五年级上册数学", "grade": 5, "subject": "数学", "term": "上册",
                          "textbook": "人教版2026", "map": RJ2026_G5_MATH_UP},
}


def template(key: str) -> dict[str, Any]:
    if key not in TEMPLATES:
        raise ValueError("没有这个知识地图模板")
    return copy.deepcopy(TEMPLATES[key]["map"])


def _text(value: Any, field: str, limit: int, required: bool = True) -> str:
    text = " ".join(str(value or "").split())
    if required and not text:
        raise ValueError(f"{field}不能为空")
    if len(text) > limit:
        raise ValueError(f"{field}不能超过 {limit} 个字")
    return text


def _key(value: Any, field: str) -> str:
    key = str(value or "").strip()
    if not _KEY.match(key):
        raise ValueError(f"{field}“{key}”只能用 1—12 个字母、数字、汉字或短横线")
    return key


def clean_map(raw: Any) -> dict[str, Any]:
    """Validate a teacher-edited map; raises ValueError with a message the teacher can act on."""
    if not isinstance(raw, dict) or not isinstance(raw.get("units"), list) or not isinstance(raw.get("nodes"), list):
        raise ValueError("知识地图格式不对")
    if not raw["units"] or len(raw["units"]) > MAX_UNITS:
        raise ValueError(f"单元数量应为 1—{MAX_UNITS} 个")
    if len(raw["nodes"]) > MAX_NODES:
        raise ValueError(f"知识点不能超过 {MAX_NODES} 个")
    units: list[dict[str, Any]] = []
    for u in raw["units"]:
        if not isinstance(u, dict):
            raise ValueError("单元格式不对")
        key = _key(u.get("key"), "单元编号")
        if any(x["key"] == key for x in units):
            raise ValueError(f"单元编号“{key}”重复")
        kind = u.get("kind") or "unit"
        if kind not in UNIT_KINDS:
            raise ValueError(f"单元“{key}”的类型不对")
        units.append({"key": key, "name": _text(u.get("name"), f"单元“{key}”的名称", 40), "kind": kind, "learned": bool(u.get("learned"))})
    unit_keys = {u["key"] for u in units}
    nodes: list[dict[str, Any]] = []
    for n in raw["nodes"]:
        if not isinstance(n, dict):
            raise ValueError("知识点格式不对")
        key = _key(n.get("key"), "知识点编号")
        if any(x["key"] == key for x in nodes):
            raise ValueError(f"知识点编号“{key}”重复")
        if n.get("unit") not in unit_keys:
            raise ValueError(f"知识点“{key}”所属的单元不存在")
        kind = n.get("kind") or "core"
        if kind not in NODE_KINDS:
            raise ValueError(f"知识点“{key}”的类型不对")
        name = _text(n.get("name"), f"知识点“{key}”的名称", 40)
        prereqs = [str(p).strip() for p in (n.get("prereqs") or []) if str(p).strip()]
        if len(set(prereqs)) != len(prereqs) or key in prereqs:
            raise ValueError(f"知识点“{key}”的前置重复或指向自己")
        bank = [_text(b, f"知识点“{key}”的题库知识点名", 120) for b in (n.get("bankKeys") or []) if str(b or "").strip()]
        levels: dict[str, str] = {}
        if kind != "display":
            for qid, level in (n.get("levels") or {}).items():
                if not str(qid).isdigit() or level not in LEVELS:
                    raise ValueError(f"知识点“{key}”的题目分档不对")
                levels[str(int(qid))] = level
        nodes.append({"key": key, "unit": n["unit"], "name": name, "detail": _text(n.get("detail"), f"知识点“{key}”的说明", 200, False),
                      "kind": kind, "prereqs": prereqs, "bankKeys": list(dict.fromkeys(bank or [name])), "levels": levels,
                      "enabled": kind in ("core", "review") or (kind == "optional" and bool(n.get("enabled")))})
    keys = {n["key"] for n in nodes}
    for n in nodes:
        missing = [p for p in n["prereqs"] if p not in keys]
        if missing:
            raise ValueError(f"知识点“{n['key']}”的前置“{'、'.join(missing)}”不存在")
    cycle = _cycle(nodes)
    if cycle:
        raise ValueError("前置关系出现循环：" + " → ".join(cycle))
    return {"version": 1, "units": units, "nodes": nodes}


def restore_unit(m: dict[str, Any], template_map: dict[str, Any], unit_key: str) -> tuple[dict[str, Any], list[str]]:
    """Add back the template's knowledge points of one unit that are missing now, with the prerequisite links that
    touch them (also from other units, e.g. 8-3 ← 1-3). Existing points, their edits and their levels stay as they are."""
    out = copy.deepcopy(m)
    have = {n["key"] for n in out["nodes"]}
    restored = []
    for n in template_map["nodes"]:
        if n["unit"] == unit_key and n["key"] not in have:
            out["nodes"].append({**copy.deepcopy(n), "prereqs": [], "levels": {}})
            restored.append(n["key"])
    if not restored:
        return out, []
    keys = {n["key"] for n in out["nodes"]}
    now = {n["key"]: n for n in out["nodes"]}
    for n in template_map["nodes"]:
        if n["key"] not in now:
            continue
        for p in n["prereqs"]:
            if p in keys and p not in now[n["key"]]["prereqs"] and (n["key"] in restored or p in restored):
                now[n["key"]]["prereqs"].append(p)
    return out, restored


def _cycle(nodes: list[dict[str, Any]]) -> list[str]:
    graph = {n["key"]: n["prereqs"] for n in nodes}
    state: dict[str, int] = {}
    stack: list[str] = []

    def visit(k: str) -> list[str]:
        state[k] = 1
        stack.append(k)
        for p in graph[k]:
            if state.get(p) == 1:
                return stack[stack.index(p):] + [p]
            if p not in state:
                found = visit(p)
                if found:
                    return found
        stack.pop()
        state[k] = 2
        return []

    for k in graph:
        if k not in state:
            found = visit(k)
            if found:
                return found
    return []


def assessed(m: dict[str, Any], node: dict[str, Any]) -> bool:
    """Whether a node takes part in diagnosis and mastery: learned unit, not display-only, optional only when enabled."""
    unit = next(u for u in m["units"] if u["key"] == node["unit"])
    return bool(unit["learned"]) and node["kind"] != "display" and bool(node["enabled"])


def coverage(node: dict[str, Any], existing_ids: set[int]) -> dict[str, Any]:
    """How many reviewed questions each level has; questions deleted from the bank no longer count."""
    counts = {k: 0 for k in LEVELS}
    for qid, level in node["levels"].items():
        if int(qid) in existing_ids:
            counts[level] += 1
    total = sum(counts.values())
    ready = node["kind"] == "display" or (total >= MIN_PER_NODE and all(c >= MIN_PER_LEVEL for c in counts.values()))
    return {"counts": counts, "total": total, "ready": ready}


def dependents(m: dict[str, Any]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {n["key"]: [] for n in m["nodes"]}
    for n in m["nodes"]:
        for p in n["prereqs"]:
            out[p].append(n["key"])
    return out


def summary(m: dict[str, Any], ready: dict[str, bool]) -> dict[str, Any]:
    """Counts for the page header: assessed nodes now and how many already have enough reviewed questions."""
    now = [n for n in m["nodes"] if assessed(m, n)]
    return {"units": len(m["units"]), "nodes": len(m["nodes"]), "assessed": len(now),
            "assessedReady": sum(1 for n in now if ready.get(n["key"])), "learnedUnits": sum(1 for u in m["units"] if u["learned"])}


# 掌握度：只看每道题的第一次作答；基础 1、中等 1.5、提高 2 加权。
WEIGHTS = {"basic": 1.0, "medium": 1.5, "hard": 2.0}
MASTERY_LABELS = {"weak": "薄弱", "pass": "达标", "fluent": "熟练"}
CONFIDENCE_LABELS = {"reliable": "可信", "preliminary": "初步", "insufficient": "证据不足"}
DIAGNOSIS_SIZE = 12
# Figures the diagnosis and knowledge-map pages can show: photos, and system-drawn figures (cubes, grid moves).
SHOWN_FIGURES = {"uploaded_image", "cubes", "gridshape", "chance"}
AGREEMENT_TARGET = 0.8          # 验收：系统判断与教师判断一致率
DIAGNOSIS_MIN = 6


def node_mastery(levels: dict[str, str], first: dict[int, bool]) -> dict[str, Any]:
    """Weighted first-attempt rate of one node: <0.6 薄弱, 0.6—0.85 达标, >0.85 熟练; 5+ answers 可信, 3—4 初步."""
    seen = [(WEIGHTS[level], first[int(qid)]) for qid, level in levels.items() if int(qid) in first]
    n = len(seen)
    if n < 3:
        return {"evidence": n, "rate": None, "level": None, "confidence": "insufficient"}
    rate = sum(w for w, ok in seen if ok) / sum(w for w, _ in seen)
    level = "weak" if rate < 0.6 else "pass" if rate <= 0.85 else "fluent"
    return {"evidence": n, "rate": round(rate, 2), "level": level, "confidence": "reliable" if n >= 5 else "preliminary"}


def mastery_view(m: dict[str, Any], first: dict[int, bool]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Mastery of every assessed node, and of every unit with all its assessed nodes' questions pooled.

    Twelve diagnosis questions give most nodes a single answer; pooled per unit they already say something."""
    nodes = {n["key"]: node_mastery(n["levels"], first) for n in m["nodes"] if assessed(m, n)}
    units = {}
    for u in m["units"]:
        pooled = {q: lv for n in m["nodes"] if n["unit"] == u["key"] and assessed(m, n) for q, lv in n["levels"].items()}
        units[u["key"]] = node_mastery(pooled, first) if pooled else None
    return nodes, units


def first_attempts(answer_lists: Iterable[list[Any]]) -> dict[int, bool]:
    """answer_lists in submission order; the first answer to each question wins."""
    out: dict[int, bool] = {}
    for answers in answer_lists:
        for a in answers if isinstance(answers, list) else []:
            if isinstance(a, dict) and str(a.get("question_id", "")).isdigit() and isinstance(a.get("correct"), bool):
                out.setdefault(int(a["question_id"]), a["correct"])
    return out


def _spread(seed: int, qid: int) -> int:
    return (qid * 2654435761 + seed * 40503) % 4294967296


def pick_diagnosis(m: dict[str, Any], usable: set[int], attempted: set[int], seed: int, size: int = DIAGNOSIS_SIZE) -> list[tuple[str, int]]:
    """Choose up to `size` questions over the learned units, in proportion to each unit's assessed nodes.

    Within a unit the nodes take turns; each node prefers 中等, then 基础, then 提高, and questions the pupil
    has never answered (so the answer is a first attempt)."""
    queues: list[list[tuple[str, int]]] = []
    for unit in m["units"]:
        lists = []
        for n in m["nodes"]:
            if n["unit"] != unit["key"] or not assessed(m, n):
                continue
            qs = [(int(q), lv) for q, lv in n["levels"].items() if int(q) in usable]
            order = {"medium": 0, "basic": 1, "hard": 2}
            qs.sort(key=lambda x: (x[0] in attempted, order[x[1]], _spread(seed, x[0])))
            if qs:
                lists.append([(n["key"], q) for q, _ in qs])
        if lists:
            start = seed % len(lists)
            lists = lists[start:] + lists[:start]
            queue, depth = [], max(len(x) for x in lists)
            for i in range(depth):
                queue.extend(x[i] for x in lists if i < len(x))
            queues.append(queue)
    if not queues:
        return []
    weights = [len({k for k, _ in q}) for q in queues]
    total = sum(weights)
    exact = [size * w / total for w in weights]
    quota = [int(x) for x in exact]
    for i in sorted(range(len(queues)), key=lambda i: -(exact[i] - quota[i]))[: size - sum(quota)]:
        quota[i] += 1
    if size >= len(queues):
        for i in range(len(queues)):
            if quota[i] == 0:
                quota[max(range(len(queues)), key=lambda j: quota[j])] -= 1
                quota[i] = 1
    picked, used = [], set()
    for i, q in enumerate(queues):
        for key, qid in q[: quota[i]]:
            picked.append((key, qid)); used.add(qid)
    for q in queues:                                   # a short unit leaves room for the others
        for key, qid in q:
            if len(picked) >= size:
                break
            if qid not in used:
                picked.append((key, qid)); used.add(qid)
    return picked[:size]


# ---------------------------------------------------------------- AI drafts for a point
AI_MIN_STEPS = {"basic": 1, "medium": 2, "hard": 3}
AI_TYPE_LABELS = {"single_choice": "选择", "true_false": "判断", "fill_blank": "填空", "calculation": "计算", "short_answer": "解决问题"}

# 数学命题角度（考法）。Teachers found drafts repeating one way of asking ("列竖式算 a÷b" six times) and 提高 that
# was 中等 with one more step. Each draft names its angle; the level only accepts its own angles (提高 has angles
# 中等 does not, as in a workbook's 智慧加油站), and one batch uses an angle at most once.
MATH_ANGLES: dict[str, list[tuple[str, str]]] = {
    "basic": [
        ("直接求结果", "口算、列竖式，或直接读出、数出结果"),
        ("意义填空", "填出算理或概念的意义（如几个十分之一、小数点为什么对齐、旋转的三要素）"),
        ("概念判断", "判断一个说法或一步算法对不对"),
        ("一步解决问题", "生活情境，一步算出结果"),
    ],
    "medium": [
        ("计算并验算", "列竖式或按步骤求出结果，再用另一种方法（如乘法验算除法）检验"),
        ("两步解决问题", "生活情境，两步算出结果"),
        ("不计算比较", "用规律直接比较或判断（如乘数是否大于 1、被除数与除数的大小），不用算出结果"),
        ("找错并改正", "给出一个有错的计算过程或结论，找出错在哪里并改正"),
        ("选择有用信息", "给出多条信息（含多余信息），选出解题需要的再计算"),
        ("推断未知", "根据结果的特点（如商的整数部分是 0、商是两位小数）推断□里的数或缺少的条件"),
        ("看表计算", "从表格或几组数据中取数计算"),
        ("模型识别", "几个情境里，判断哪个能（或不能）用同一个算式解决"),
    ],
    "hard": [
        ("等量代换", "两组搭配给出两个总量（如 3 大 3 小共多少、1 大 3 小共多少），求其中一个的量"),
        ("和差倍关系", "已知两数的和或差，以及倍数关系（含小数点移动引起的 10 倍、100 倍关系），求两个数"),
        ("逆向推理", "已知结果和部分过程，倒推原来的数或条件"),
        ("方案比较", "两三种方案或包装，分别算出单价或总价再比较，并说明理由"),
        ("多步综合", "三步及以上、要综合表格或多组数据，含易错的单位或近似数"),
        ("规律探究", "从几组算式发现规律，再用规律解决新问题"),
        ("取值范围", "□里能填哪些数，要找全所有可能，并说明理由"),
    ],
}


# 图形单元（观察物体、图形的运动、多边形的面积、密铺）：考法要用到图形本身，不能把图形当情境外衣去考乘除。
SHAPE_ANGLES: dict[str, list[tuple[str, str]]] = {
    "basic": [
        ("认识要素", "说出或填出要素，如旋转中心、方向、角度，平行四边形的底和对应的高"),
        ("判断运动或特征", "判断是平移、旋转还是轴对称，或判断一个关于图形的说法对不对"),
        ("数格读位置", "在用文字说清的方格里数格子，读出点的位置、移动的格数或边长"),
        ("一步套用", "一步用公式或定义求结果，如已知底和高求面积"),
    ],
    "medium": [
        ("描述运动过程", "用完整的话描述图形怎样运动：绕哪一点、哪个方向、转多少度，或向哪个方向移几格"),
        ("确定运动后位置", "运动后点或图形到了第几列第几行、指针指向哪里"),
        ("找错并改正", "给出一个有错的描述、画法或计算，找出错在哪里并改正"),
        ("对应关系", "找出运动前后对应的点、边、角，或判断哪些量（形状、大小、位置）变了、哪些不变"),
        ("两步求解", "先求出一个需要的量，再求结果，如先由面积求底，再求另一个图形的面积"),
        ("性质判断", "不画图、不计算，用图形的性质判断能否重合、能否拼成、面积是否相等"),
    ],
    "hard": [
        ("逆向推理", "已知运动后的位置或结果，倒推原来的位置、旋转中心、方向或角度"),
        ("多次运动组合", "两三次运动连续进行，或交换运动的顺序后结果是否相同"),
        ("规律探究", "连续旋转、重复排列或图形变化中找规律，再解决新问题"),
        ("方案设计", "设计或比较几种拼法、分割法、运动路线，并说明理由"),
        ("找全所有可能", "找全所有满足条件的位置、图形或拼法，并说明理由"),
        ("转化思想", "通过割补、平移、旋转把图形转化成会算的图形，再求面积或周长"),
    ],
}

# 可能性、统计单元。小学只定性比较可能性的大小（课标第二学段），不用分数、小数、百分数表示可能性。
CHANCE_ANGLES: dict[str, list[tuple[str, str]]] = {
    "basic": [
        ("判断可能性", "用“一定、可能、不可能”描述事件"),
        ("列举结果", "列出所有可能出现的结果"),
        ("概念判断", "判断一个关于可能性的说法对不对"),
    ],
    "medium": [
        ("比较可能性大小", "根据数量多少比较哪种结果的可能性大，不用分数或小数表示可能性"),
        ("按要求设计", "按“摸到红球的可能性最大”“不可能摸到黄球”这类要求放球、涂色或写数字"),
        ("由记录推断", "根据多次摸球或转盘的记录，推断袋中哪种可能多、哪种可能少（不算具体个数）"),
        ("找错并改正", "给出一个有错的判断，找出错在哪里并改正"),
    ],
    "hard": [
        ("公平性判断", "判断游戏规则是否公平，不公平时怎样修改"),
        ("逆向推理", "已知可能性大小的要求（如红球的可能性最大），倒推每种至少或最多放几个"),
        ("找全所有可能", "找全满足条件的所有放法或结果，并说明理由"),
        ("综合推理", "结合数量、条件多步推理，判断可能性并说明理由"),
    ],
}

_CHANCE_NUMBER = re.compile(r"可能性\s*(?:是|为|等于|约是|约为)\s*[\d一二三四五六七八九十百]|用(?:百分数|分数|小数)表示")
_SHAPE_WORDS = ("图形", "观察", "面积", "密铺", "周长", "体积", "表面积", "对称", "平移", "旋转", "位置", "方向", "角的", "三角形", "四边形", "圆", "长方体", "正方体")
_CHANCE_WORDS = ("可能性", "统计", "数据", "条形图", "折线图", "扇形图")


def math_angles(unit: str = "") -> dict[str, list[tuple[str, str]]]:
    """The angle lists for a maths unit: shapes, chance and data, or calculation (the default)."""
    name = str(unit or "")
    if any(w in name for w in _CHANCE_WORDS):
        return CHANCE_ANGLES
    if any(w in name for w in _SHAPE_WORDS):
        return SHAPE_ANGLES
    return MATH_ANGLES


def angle_cap(level: str, count: int, unit: str = "") -> int:
    """How often one angle may appear in a batch of ``count``: once, unless the level has fewer angles than drafts."""
    return max(1, -(-count // max(1, len(math_angles(unit).get(level, [])))))


def angle_brief(level: str, count: int, unit: str = "") -> str:
    """The angles a level accepts, for the request, and how often one may be used in this batch."""
    names = math_angles(unit).get(level, [])
    if not names:
        return ""
    lines = "\n".join(f"- {n}：{d}" for n, d in names)
    cap = angle_cap(level, count, unit)
    rule = "每道题用不同的角度" if cap == 1 else f"同一个角度最多用 {cap} 次"
    return (f"【命题角度】每道题必须从下面的角度里选一个，并在 \"angle\" 字段写出角度名称（原样照写）；"
            f"这一批 {count} 道题{rule}，不要多道题都是同一种考法。每道题都要真正用到这个知识点本身，"
            f"不能只把它当情境、实际考的是别的计算。数据要像练习册一样好算：中间结果和答案最多两位小数"
            f"（题目要求保留的除外）；难度来自思路，不靠繁琐的数。"
            + ("可能性只用“一定、可能、不可能”和“大、小、相等”描述，不要用分数、小数、百分数表示可能性。"
                 "情境要换着用（摸球、转盘、抽卡片、掷小正方体、涂色、生活中的事件），同一批里同一种情境不超过 2 道；"
                 "试验记录只能用来推测“可能多、可能少”，不能据此断定个数或断定规则一定公平。" if math_angles(unit) is CHANCE_ANGLES else "")
            + f"\n{lines}")


def check_ai_question(item: dict[str, Any], level: str, subject: str, unit: str = "") -> tuple[dict[str, Any] | None, str]:
    """Keep an AI draft only when it is as hard as its level says and, in maths, its answer adds up.

    Maths angles come from the unit's list (``math_angles``): calculation, shapes, or chance.
    Steps: 中等 needs 2, 提高 3 (the prompt asks for them; a draft without them is a recall question in disguise).
    A numeric maths answer is recomputed from the draft's expression; a wrong one is dropped. Fill-in, calculation and
    problem-solving drafts above 基础 must carry an expression; the rest without one are kept, marked as unchecked.
    """
    from changying.services import weekend_question_gen as qg

    out = dict(item)
    qtype = str(out.get("question_type") or "")
    steps = [s for s in out.get("steps") or [] if str(s).strip()]
    angles = math_angles(unit)
    if "数学" in str(subject or "") and level in angles:
        said = re.sub(r"\s+", "", str(out.get("angle") or ""))
        angle = next((n for n, _ in angles[level] if said and (n in said or said in n)), "")
        if not angle:
            return None, "命题角度不属于这一难度"
        out["angle"] = angle                                     # the listed name, so the per-batch cap counts it
        said_all = " ".join(str(out.get(k) or "") for k in ("text", "answer", "explanation")) + " ".join(map(str, steps))
        if angles is CHANCE_ANGLES and _CHANCE_NUMBER.search(said_all):
            return None, "可能性用数表示（小学只比较大小）"
    if len(steps) < AI_MIN_STEPS.get(level, 1):
        return None, "步骤太少（中等至少 2 步、提高至少 3 步）"
    if qtype == "single_choice" and len({str(o).strip() for o in out.get("options") or []}) != 4:
        return None, "选项有重复"
    out["verified"] = False
    if "数学" not in str(subject or "") or qtype == "true_false":
        return out, ""
    answer = out["options"][out["correct_index"]] if qtype == "single_choice" else out.get("answer", "")
    target = qg.number(answer)
    if target is None:
        return out, ""
    value = qg.evaluate(out.get("expression"))
    if value is None:
        if qtype != "single_choice" and level != "basic" and angles is MATH_ANGLES:
            return None, "数学答案没有可验算的算式"            # shapes and chance: an answer such as 90° is kept, unchecked
        return out, ""
    if not qg.agrees(value, target, str(out.get("text") or ""), str(answer)):
        return None, "验算不对"
    out["verified"] = True
    return out, ""


def pick_ai_drafts(items: list[dict[str, Any]], count: int, level: str = "", existing: list[str] = (), unit: str = "") -> list[dict[str, Any]]:
    """Up to ``count`` drafts, taking the question types in turn so one type cannot fill the set; checked ones first.
    An angle (way of asking) is used at most ``angle_cap`` times per batch, so a set does not repeat one kind of question;
    a draft whose stem the point already has is skipped."""
    cap = angle_cap(level, count, unit)
    known = {re.sub(r"\s+", "", t) for t in existing}
    by_type: dict[str, list[dict[str, Any]]] = {}
    for it in sorted(items, key=lambda x: not x.get("verified")):
        by_type.setdefault(str(it.get("question_type")), []).append(it)
    out: list[dict[str, Any]] = []
    angles: dict[str, int] = {}
    while len(out) < count and any(by_type.values()):
        for t in list(by_type):
            while by_type[t] and len(out) < count:
                it = by_type[t].pop(0)
                angle = str(it.get("angle") or "").strip()
                stem = re.sub(r"\s+", "", str(it.get("text") or ""))
                if (angle and angles.get(angle, 0) >= cap) or (stem and stem in known):
                    continue                                   # same way of asking, or a repeat: try this type's next draft
                if angle:
                    angles[angle] = angles.get(angle, 0) + 1
                known.add(stem)
                out.append(it)
                break
    return out


__all__ = ["AGREEMENT_TARGET", "SHOWN_FIGURES", "CONFIDENCE_LABELS", "DIAGNOSIS_MIN", "LEVELS", "MASTERY_LABELS", "NODE_KINDS", "TEMPLATES", "UNIT_KINDS", "assessed", "clean_map", "coverage", "dependents", "first_attempts", "mastery_view", "node_mastery",
           "pick_diagnosis", "restore_unit", "summary", "template", "AI_MIN_STEPS", "AI_TYPE_LABELS", "MATH_ANGLES", "SHAPE_ANGLES", "CHANCE_ANGLES", "math_angles", "angle_brief", "angle_cap", "check_ai_question", "pick_ai_drafts"]
