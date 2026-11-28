"""数学通用知识地图（去教材版本强绑定）与节点自带测试题引擎.

作为基础模块开箱即用：
- 按课标核心知识域组织节点（数与运算 / 图形与几何 / 数量关系 / 统计与概率），不强制依赖教材版本与教师逐题导入。
- 每个节点自带确定性参数化题目生成器，覆盖 5 种小学数学核心题型（选择/判断/填空/计算/解决问题）与 3 个难度档。
- 提供游戏化点亮状态机：未探索 -> 探索中 -> 已点亮(★) -> 精通(★★★)，支持应试专项双向联动与待修补标记。
"""
from __future__ import annotations

import copy
from decimal import Decimal, InvalidOperation
import re
from typing import Any, Iterable

from changying.services import math_grade_curricula as mgc
from changying.services import visual_questions as vq
from changying.services.arena_grade_profiles import infer_grade_from_node_key

SUBJECT_MATH = "数学"
DEFAULT_GRADE = 5

# 通用数学节点到系统画图题族的映射（保证图、选项、答案全部由系统精确计算，零幻觉）
VISUAL_NODE_MAP: dict[str, tuple[str, ...]] = {
    "M1-1": ("2-2",),
    "M2-1": ("4-1", "4-2", "4-3", "1-1"),
    "M2-2": ("6-1",),
    "M2-3": ("6-2",),
    "M2-4": ("6-3",),
    "M2-5": ("6-4", "6-7"),
    "M2-7": ("1-2", "1-3"),
    "M3-1": ("5-1",),
    "M4-1": ("7-1",),
    "M4-2": ("7-2", "7-3"),
    **mgc.GRADE_VISUAL_NODE_MAP,
}

LIGHT_STATES = {
    "unexplored": "未探索",
    "exploring": "探索中",
    "lit": "已点亮",
    "mastered": "精通",
}

LEVEL_LABELS = {"basic": "基础", "medium": "中等", "hard": "提高"}

TYPE_POINTS = {
    "single_choice": 2,
    "true_false": 1,
    "fill_blank": 2,
    "calculation": 3,
    "error_diagnosis": 3,
    "short_answer": 5,
    "multi_step": 5,
}
TYPE_LABELS = {
    "single_choice": "选择",
    "true_false": "判断",
    "fill_blank": "填空",
    "calculation": "计算",
    "error_diagnosis": "易错辨析",
    "short_answer": "解决问题",
    "multi_step": "综合推理",
}


def _d(v: Any) -> Decimal:
    return Decimal(str(v))


def _fmt(v: Decimal | int | float | str) -> str:
    n = _d(v).normalize()
    s = format(n, "f")
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s or "0"


def _u(key: str, name: str, domain: str, icon: str) -> dict[str, Any]:
    return {
        "key": key,
        "name": name,
        "domain": domain,
        "icon": icon,
        "kind": "unit",
        "learned": True,
    }


def _n(key: str, unit: str, name: str, detail: str, prereqs: Iterable[str] = ()) -> dict[str, Any]:
    return {
        "key": key,
        "unit": unit,
        "name": name,
        "detail": detail,
        "kind": "core",
        "prereqs": list(prereqs),
        "bankKeys": [name],
        "levels": {},
        "enabled": True,
        "builtin": True,
    }


MATH_G5_CORE_MAP: dict[str, Any] = {
    "version": 2,
    "subject": SUBJECT_MATH,
    "grade": DEFAULT_GRADE,
    "textbookAgnostic": True,
    "title": "小学数学通用知识地图（五年级·算理星图）",
    "units": [
        _u("D1", "数与运算", "number_ops", "⚡"),
        _u("D2", "图形与几何", "geometry", "📐"),
        _u("D3", "数量关系与方程", "algebra_word", "🧩"),
        _u("D4", "统计与概率", "stats_prob", "🎲"),
    ],
    "nodes": [
        # D1 数与运算（8 节点）
        _n("M1-1", "D1", "小数乘整数与小数", "掌握小数乘法算理、积的小数位数与补 0 规则"),
        _n("M1-2", "D1", "积的近似数与大小规律", "四舍五入求积的近似数；判断乘大于 1 或小于 1 的数后积的变化", ["M1-1"]),
        _n("M1-3", "D1", "小数乘法简便运算", "把整数乘法交换律、结合律、分配律迁移到小数计算", ["M1-1"]),
        _n("M1-4", "D1", "小数除法核心算理", "除数是整数/小数的小数除法，商的小数点定位与转化", ["M1-1"]),
        _n("M1-5", "D1", "商的变化与循环小数", "商与被除数的大小关系、有限小数与循环小数辨析", ["M1-4"]),
        _n("M1-6", "D1", "因数与倍数、质数与合数", "掌握 2/3/5 的倍数特征、质数合数及最大公因数与最小公倍数"),
        _n("M1-7", "D1", "分数的意义、约分与通分", "理解单位“1”、分数基本性质、最简分数及分数大小比较", ["M1-6"]),
        _n("M1-8", "D1", "分数的加法和减法", "同分母与异分母分数加减法、分数加减简便运算", ["M1-7"]),
        # D2 图形与几何（7 节点）
        _n("M2-1", "D2", "观察物体与图形运动", "三视图还原组合体；识别轴对称、平移、旋转特征及运动不变性"),
        _n("M2-2", "D2", "平行四边形的面积", "割补法推导 S=ah，会已知面积反求底或高", ["M1-1", "M2-1"]),
        _n("M2-3", "D2", "三角形的面积", "掌握 S=ah÷2，会已知面积反求底或高", ["M2-2"]),
        _n("M2-4", "D2", "梯形的面积", "掌握 S=(a+b)h÷2，会反求高或上下底", ["M2-2"]),
        _n("M2-5", "D2", "组合图形与面积单位换算", "分割法/添补法求组合图形面积；公顷与平方千米换算", ["M2-2", "M2-3", "M2-4"]),
        _n("M2-6", "D2", "用数对确定位置", "理解列与行规则，用数对 (列, 行) 表示及平移后的位置", ["M2-1"]),
        _n("M2-7", "D2", "长方体和正方体的表面积与体积", "掌握棱长和、表面积、体积与容积单位换算（L/mL/dm³/cm³）", ["M2-5"]),
        # D3 数量关系与方程（6 节点）
        _n("M3-1", "D3", "用字母表示数与数量关系", "用含字母的式子表示数量关系、公式与代值计算", ["M1-3"]),
        _n("M3-2", "D3", "简易方程求解", "理解等式性质并求解一步/两步简易方程", ["M3-1"]),
        _n("M3-3", "D3", "分段计费与估算应用", "出租车/水电费分段计费与购物估算问题", ["M1-2", "M1-3"]),
        _n("M3-4", "D3", "进一法与去尾法解决问题", "根据实际场景灵活选择进一法或去尾法取近似值", ["M1-4"]),
        _n("M3-5", "D3", "植树问题（直线与封闭）", "区分两端都栽、只栽一端、两端不栽及封闭图形的棵数与间隔数关系", ["M3-1"]),
        _n("M3-6", "D3", "找次品与最优策略", "用天平三分法求保证找出次品的最少称量次数", ["M1-6"]),
        # D4 统计与概率（3 节点）
        _n("M4-1", "D4", "确定现象与随机现象", "用“一定”“可能”“不可能”判断事件性质"),
        _n("M4-2", "D4", "可能性大小与游戏公平性", "比较不同事件发生的可能性大小，判断规则是否公平", ["M4-1"]),
        _n("M4-3", "D4", "折线统计图与趋势分析", "读懂单式/复式折线统计图，分析增减变化幅度与趋势", ["M4-2"]),
    ],
}


def get_builtin_math_map(grade: int | None = None) -> dict[str, Any]:
    """返回去教材版本的通用数学知识地图副本（支持 3、4、5、6 年级）."""
    if grade is not None:
        try:
            g = int(grade)
        except (TypeError, ValueError):
            g = DEFAULT_GRADE
        if g in (3, 4, 6):
            grade_map = mgc.get_grade_math_map(g)
            if grade_map is not None:
                return grade_map
    data = copy.deepcopy(MATH_G5_CORE_MAP)
    if grade is not None and int(grade) != DEFAULT_GRADE:
        data["grade"] = int(grade)
        data["title"] = f"小学数学通用知识地图（{int(grade)}年级·算理星图）"
    return data


def get_all_math_nodes() -> dict[str, dict[str, Any]]:
    """返回 G3/G4/G5/G6 所有数学节点的字典映射 (key -> node dict)."""
    out: dict[str, dict[str, Any]] = {}
    for m in (mgc.MATH_G3_CORE_MAP, mgc.MATH_G4_CORE_MAP, MATH_G5_CORE_MAP, mgc.MATH_G6_CORE_MAP):
        for n in m["nodes"]:
            out[n["key"]] = copy.deepcopy(n)
    return out


def _choice_q(
    qid: str,
    node_key: str,
    level: str,
    text: str,
    answer: str,
    distractors: list[str],
    explanation: str,
    seed: int,
) -> dict[str, Any]:
    ans = str(answer)
    pool: list[str] = []
    for d in distractors:
        s = str(d)
        if s != ans and s not in pool:
            pool.append(s)
    for fb in ("0", "1", "10", "无法确定"):
        if len(pool) >= 3:
            break
        if fb != ans and fb not in pool:
            pool.append(fb)
    opts = pool[:3]
    cidx = seed % 4
    opts.insert(cidx, ans)
    return {
        "id": qid,
        "nodeKey": node_key,
        "level": level,
        "questionType": "single_choice",
        "text": text,
        "options": opts,
        "correctIndex": cidx,
        "answer": ans,
        "acceptableAnswers": [ans],
        "explanation": explanation,
        "marks": TYPE_POINTS["single_choice"],
        "figure": None,
    }


def _tf_q(
    qid: str,
    node_key: str,
    level: str,
    text: str,
    is_true: bool,
    explanation: str,
) -> dict[str, Any]:
    cidx = 0 if is_true else 1
    ans = "正确" if is_true else "错误"
    return {
        "id": qid,
        "nodeKey": node_key,
        "level": level,
        "questionType": "true_false",
        "text": text,
        "options": ["正确", "错误"],
        "correctIndex": cidx,
        "answer": ans,
        "acceptableAnswers": [ans, "对" if is_true else "错", "√" if is_true else "×"],
        "explanation": explanation,
        "marks": TYPE_POINTS["true_false"],
        "figure": None,
    }


def _text_q(
    qid: str,
    node_key: str,
    level: str,
    qtype: str,
    text: str,
    answer: str,
    explanation: str,
    extra_answers: Iterable[str] = (),
) -> dict[str, Any]:
    ans = str(answer)
    acc = [ans] + [str(x) for x in extra_answers if str(x) != ans]
    return {
        "id": qid,
        "nodeKey": node_key,
        "level": level,
        "questionType": qtype,
        "text": text,
        "options": [],
        "correctIndex": None,
        "answer": ans,
        "acceptableAnswers": acc,
        "explanation": explanation,
        "marks": TYPE_POINTS.get(qtype, 2),
        "figure": None,
    }


def _build_node_pool(node_key: str, seed: int) -> list[dict[str, Any]]:
    """为单个知识节点确定性生成覆盖 5 题型、3 难度档的 6 道自带题."""
    k = str(node_key or "").strip().upper()
    if k.startswith(("G3-", "G4-", "G6-")):
        return mgc.build_grade_node_pool(k, seed)
    if k.startswith("G5-"):
        node_key = k[3:]
    s = abs(int(seed))
    a = 2 + (s % 7)          # 2..8
    b = 3 + ((s * 3) % 6)    # 3..8
    c = 4 + ((s * 5) % 5)    # 4..8

    if node_key == "M1-1":
        x1 = _d(f"{a}.{b}")
        y1 = c
        p1 = _fmt(x1 * y1)
        x2 = _d(f"0.{a}")
        y2 = _d(f"0.{b}")
        p2 = _fmt(x2 * y2)
        x3 = _d(f"{a}.5")
        y3 = _d(f"1.{b % 4 + 2}")
        p3 = _fmt(x3 * y3)
        return [
            _text_q(f"bi:{node_key}:calc:{s}", node_key, "basic", "calculation",
                    f"直接写出得数：{_fmt(x1)} × {y1} =", p1, f"先按整数相乘，再点出 1 位小数，得 {p1}。"),
            _choice_q(f"bi:{node_key}:sc:{s}", node_key, "basic",
                      f"计算 {_fmt(x2)} × {_fmt(y2)} 的结果是（ ）。", p2,
                      [_fmt(x2 * y2 * 10), _fmt(x2 * y2 / 10), _fmt(x2 + y2)],
                      f"两个因数共有 2 位小数，积为 {p2}。", s + 1),
            _tf_q(f"bi:{node_key}:tf:{s}", node_key, "basic",
                  f"判断：计算 {_fmt(x2)} × {_fmt(y2)} 时，积的小数位数一定等于两个因数小数位数之和（未去掉末尾 0 前）。",
                  True, "小数乘法先按整数乘法算出积，再从积的右边起数出因数中一共有几位小数点上小数点。"),
            _text_q(f"bi:{node_key}:fb:{s}", node_key, "medium", "fill_blank",
                    f"填空：{_fmt(x3)} × {_fmt(y3)} 的积是（ ）。", p3, f"{_fmt(x3)} × {_fmt(y3)} = {p3}。"),
            _text_q(f"bi:{node_key}:sa:{s}", node_key, "hard", "short_answer",
                    f"解决问题：每千克苹果 {_fmt(x1)} 元，买 {y1} 千克苹果需要多少元？（只填数字）", p1,
                    f"单价 × 数量 = {_fmt(x1)} × {y1} = {p1}（元）。", [f"{p1}元"]),
            _choice_q(f"bi:{node_key}:sc2:{s}", node_key, "medium",
                      f"如果 25 × 14 = 350，那么 2.5 × 0.14 =（ ）。", "0.35",
                      ["3.5", "0.035", "35"], "两个因数共有 3 位小数，350 缩小到千分之一是 0.35。", s + 2),
        ]

    if node_key == "M1-2":
        x = _d(f"{a}.{b}")
        y = _d("1.2") if s % 2 == 0 else _d("0.8")
        bigger = y > 1
        prod = x * _d("0.6")
        rounded = _fmt(prod.quantize(Decimal("0.1")))
        return [
            _choice_q(f"bi:{node_key}:sc:{s}", node_key, "basic",
                      f"不计算，比较大小：{_fmt(x)} × {_fmt(y)} ○ {_fmt(x)}。",
                      ">" if bigger else "<", ["<" if bigger else ">", "=", "无法确定"],
                      f"一个非零数乘{'大于' if bigger else '小于'} 1 的数，积{'大于' if bigger else '小于'}原数。", s),
            _tf_q(f"bi:{node_key}:tf:{s}", node_key, "basic",
                  "判断：一个非零数乘 0.99，积一定比这个数小。", True, "0.99 < 1，非零数乘小于 1 的数，积变小。"),
            _text_q(f"bi:{node_key}:fb:{s}", node_key, "medium", "fill_blank",
                    f"填空：{_fmt(x)} × 0.6 的积保留一位小数约是（ ）。", rounded,
                    f"{_fmt(x)} × 0.6 = {_fmt(prod)}，四舍五入保留一位小数是 {rounded}。"),
            _text_q(f"bi:{node_key}:calc:{s}", node_key, "medium", "calculation",
                    f"计算并保留整数：{_fmt(x)} × 2.5 ≈", _fmt((x * _d("2.5")).quantize(Decimal("1"))),
                    f"精确值 {_fmt(x * _d('2.5'))}，四舍五入取整。"),
            _choice_q(f"bi:{node_key}:sc2:{s}", node_key, "hard",
                      "一个两位小数“四舍五入”保留一位小数是 5.0，这个两位小数最大是（ ）。",
                      "5.04", ["5.05", "4.99", "5.09"], "四舍得到 5.0，百分位最大为 4，即 5.04。", s + 3),
            _text_q(f"bi:{node_key}:sa:{s}", node_key, "hard", "short_answer",
                    f"解决问题：一块布每米 {_fmt(x)} 元，买 0.6 米大约需要多少元？（保留一位小数，只填数字）",
                    rounded, f"{_fmt(x)} × 0.6 ≈ {rounded}（元）。", [f"{rounded}元"]),
        ]

    if node_key == "M1-3":
        k = a + 1
        ans1 = _fmt(_d(k) * _d("10"))
        ans2 = _fmt(_d(b) * _d("10.1"))
        ans3 = _fmt(_d("0.25") * _d(4 * c))
        return [
            _text_q(f"bi:{node_key}:calc:{s}", node_key, "basic", "calculation",
                    f"简便计算：{k}.6 × 6.4 + {k}.6 × 3.6 =" if False else f"简便计算：{_fmt(_d(k))} × 6.4 + {_fmt(_d(k))} × 3.6 =",
                    ans1, f"用乘法分配律：{k} × (6.4 + 3.6) = {k} × 10 = {ans1}。"),
            _choice_q(f"bi:{node_key}:sc:{s}", node_key, "basic",
                      f"计算 0.25 × {4 * c} 时，最简便的方法是（ ）。",
                      f"(0.25 × 4) × {c}", [f"0.25 × 4 + {c}", f"0.25 × ({4 * c} + 1)", "直接竖式计算"],
                      f"把 {4 * c} 拆成 4 × {c}，利用 0.25 × 4 = 1 凑整。", s),
            _tf_q(f"bi:{node_key}:tf:{s}", node_key, "basic",
                  "判断：1.25 × 8.8 = 1.25 × 8 + 1.25 × 0.8 运用了乘法分配律。", True, "8.8 = 8 + 0.8，拆开分别相乘再相加正是乘法分配律。"),
            _text_q(f"bi:{node_key}:fb:{s}", node_key, "medium", "fill_blank",
                    f"填空：0.25 × {4 * c} =（ ）。", ans3, f"0.25 × 4 × {c} = 1 × {c} = {ans3}。"),
            _text_q(f"bi:{node_key}:calc2:{s}", node_key, "hard", "calculation",
                    f"简便计算：{b} × 10.1 =", ans2, f"{b} × (10 + 0.1) = {b * 10} + {_fmt(_d(b) * _d('0.1'))} = {ans2}。"),
            _text_q(f"bi:{node_key}:sa:{s}", node_key, "hard", "short_answer",
                    f"解决问题：学校买 {k} 套桌椅，每张桌子 64.5 元，每把椅子 35.5 元，一共花多少元？（只填数字）",
                    str(k * 100), f"{k} × (64.5 + 35.5) = {k} × 100 = {k * 100}（元）。", [f"{k * 100}元"]),
        ]

    if node_key == "M1-4":
        q1 = _d(f"{a}.{b}")
        div1 = c
        dvd1 = _fmt(q1 * div1)
        q2 = a + 3
        div2 = _d("0.5")
        dvd2 = _fmt(_d(q2) * div2)
        return [
            _text_q(f"bi:{node_key}:calc:{s}", node_key, "basic", "calculation",
                    f"计算：{dvd1} ÷ {div1} =", _fmt(q1), f"{dvd1} ÷ {div1} = {_fmt(q1)}。"),
            _choice_q(f"bi:{node_key}:sc:{s}", node_key, "basic",
                      f"计算 {dvd2} ÷ 0.5 时，把除数变成整数 5，被除数应变成（ ）。",
                      _fmt(_d(dvd2) * 10), [dvd2, _fmt(_d(dvd2) * 100), _fmt(_d(dvd2) / 10)],
                      "除数小数点向右移动 1 位，被除数也要向右移动 1 位，商不变。", s),
            _tf_q(f"bi:{node_key}:tf:{s}", node_key, "basic",
                  "判断：小数除以小数，商的小数点要和移动后的被除数的小数点对齐。", True, "利用商不变性质同时移动小数点后对齐。"),
            _text_q(f"bi:{node_key}:fb:{s}", node_key, "medium", "fill_blank",
                    f"填空：{dvd2} ÷ 0.5 =（ ）。", str(q2), f"转化为 {_fmt(_d(dvd2) * 10)} ÷ 5 = {q2}。"),
            _text_q(f"bi:{node_key}:sa:{s}", node_key, "hard", "short_answer",
                    f"解决问题：一根绳子长 {dvd1} 米，平均剪成 {div1} 段，每段长多少米？（只填数字）",
                    _fmt(q1), f"{dvd1} ÷ {div1} = {_fmt(q1)}（米）。", [f"{_fmt(q1)}米"]),
            _choice_q(f"bi:{node_key}:sc2:{s}", node_key, "medium",
                      "下面算式中，与 3.6 ÷ 0.12 商相等的是（ ）。",
                      "360 ÷ 12", ["36 ÷ 12", "3.6 ÷ 12", "360 ÷ 120"],
                      "被除数和除数同时扩大 100 倍，商不变。", s + 1),
        ]

    if node_key == "M1-5":
        smaller_div = s % 2 == 0
        div = "0.6" if smaller_div else "1.6"
        return [
            _choice_q(f"bi:{node_key}:sc:{s}", node_key, "basic",
                      f"不计算，比较大小：{a}.{b} ÷ {div} ○ {a}.{b}。",
                      ">" if smaller_div else "<", ["<" if smaller_div else ">", "=", "无法确定"],
                      f"非零数除以{'小于' if smaller_div else '大于'} 1 的数，商{'大于' if smaller_div else '小于'}被除数。", s),
            _tf_q(f"bi:{node_key}:tf:{s}", node_key, "basic",
                  "判断：循环小数一定是无限小数。", True, "循环小数的小数部分有数字不断重复出现，属于无限小数。"),
            _choice_q(f"bi:{node_key}:sc2:{s}", node_key, "medium",
                      "下面各数中，属于循环小数的是（ ）。",
                      "0.3636…", ["3.1415926", "0.25", "1.202002"],
                      "0.3636… 从十分位起“36”依次不断重复出现。", s + 2),
            _text_q(f"bi:{node_key}:fb:{s}", node_key, "medium", "fill_blank",
                    "填空：1 ÷ 3 的商用循环小数表示，保留两位小数约是（ ）。", "0.33", "1 ÷ 3 = 0.333…，保留两位小数是 0.33。"),
            _text_q(f"bi:{node_key}:calc:{s}", node_key, "medium", "calculation",
                    "计算并保留两位小数：10 ÷ 3 ≈", "3.33", "10 ÷ 3 = 3.333…，四舍五入保留两位小数是 3.33。"),
            _text_q(f"bi:{node_key}:sa:{s}", node_key, "hard", "short_answer",
                    "解决问题：把 2 ÷ 11 的商写成循环小数 0.1818…，小数部分第 10 位上的数字是几？",
                    "8", "循环节“18”每 2 位一循环，10 ÷ 2 = 5 正好整除，所以第 10 位是 8。"),
        ]

    if node_key == "M2-1":
        return [
            _choice_q(f"bi:{node_key}:sc:{s}", node_key, "basic",
                      "下面哪种图形运动只改变位置，不改变图形的形状、大小和方向？（ ）",
                      "平移", ["旋转", "放大", "拉长"], "平移只改变位置，形状、大小和方向都不变。", s),
            _tf_q(f"bi:{node_key}:tf:{s}", node_key, "basic",
                  "判断：在轴对称图形中，对应点到对称轴的距离相等。", True, "轴对称图形沿对称轴对折后完全重合，对应点到对称轴距离相等。"),
            _choice_q(f"bi:{node_key}:sc2:{s}", node_key, "medium",
                      "正方形有（ ）条对称轴。", "4", ["2", "1", "8"], "正方形有横、竖和两条对角线共 4 条对称轴。", s + 1),
            _text_q(f"bi:{node_key}:fb:{s}", node_key, "medium", "fill_blank",
                    "填空：钟面上的分针从“12”顺时针旋转到“3”，旋转了（ ）度。（只填数字）", "90",
                    "一大格 30°，3 大格是 90°。", ["90°", "90度"]),
            _text_q(f"bi:{node_key}:calc:{s}", node_key, "medium", "calculation",
                    f"填空计算：一个长方形长 {a + 2} cm、宽 {b} cm，向右平移 5 格后，它的面积是（ ）cm²。（只填数字）",
                    str((a + 2) * b), f"平移不改变图形面积，仍为 {(a + 2)} × {b} = {(a + 2) * b}。"),
            _text_q(f"bi:{node_key}:sa:{s}", node_key, "hard", "short_answer",
                    "解决问题：钟面上的时针从“2”顺时针旋转 90° 后，指向数字几？", "5",
                    "90° 是 3 个大格，2 + 3 = 5。"),
        ]

    if node_key == "M2-2":
        base, h = a + 3, b + 1
        area = base * h
        return [
            _text_q(f"bi:{node_key}:calc:{s}", node_key, "basic", "calculation",
                    f"计算：平行四边形的底是 {base} cm，高是 {h} cm，面积是多少 cm²？（只填数字）",
                    str(area), f"S = a × h = {base} × {h} = {area}。"),
            _choice_q(f"bi:{node_key}:sc:{s}", node_key, "basic",
                      "把一个平行四边形沿高剪开拼成长方形后，面积（ ）。",
                      "不变", ["变大", "变小", "无法确定"], "割补转化前后面积不变。", s),
            _tf_q(f"bi:{node_key}:tf:{s}", node_key, "basic",
                  "判断：把一个长方形框架拉成平行四边形，周长不变，面积变小。", True, "拉斜后底不变但高变短，所以面积变小。"),
            _text_q(f"bi:{node_key}:fb:{s}", node_key, "medium", "fill_blank",
                    f"填空：一个平行四边形面积是 {area} cm²，底是 {base} cm，高是（ ）cm。",
                    str(h), f"h = S ÷ a = {area} ÷ {base} = {h}。"),
            _text_q(f"bi:{node_key}:sa:{s}", node_key, "hard", "short_answer",
                    f"解决问题：一块平行四边形菜地，底 {base * 2} 米，高 {h} 米，如果每平方米收菜 5 千克，一共收菜多少千克？（只填数字）",
                    str(base * 2 * h * 5), f"面积 {base * 2 * h} 平方米，共收 {base * 2 * h * 5} 千克。", [f"{base * 2 * h * 5}千克"]),
            _choice_q(f"bi:{node_key}:sc2:{s}", node_key, "medium",
                      "等底等高的两个平行四边形，它们的面积（ ）。", "一定相等", ["一定不相等", "可能相等", "周长也相等"],
                      "平行四边形面积只由底和高决定，等底等高则面积一定相等。", s + 2),
        ]

    if node_key == "M2-3":
        base = (a + 2) * 2
        h = b + 1
        area = (base * h) // 2
        return [
            _text_q(f"bi:{node_key}:calc:{s}", node_key, "basic", "calculation",
                    f"计算：三角形的底是 {base} cm，高是 {h} cm，面积是多少 cm²？（只填数字）",
                    str(area), f"S = a × h ÷ 2 = {base} × {h} ÷ 2 = {area}。"),
            _choice_q(f"bi:{node_key}:sc:{s}", node_key, "basic",
                      "两个完全一样的三角形一定可以拼成一个（ ）。",
                      "平行四边形", ["正方形", "梯形", "圆形"], "两个完全一样的三角形必能拼成平行四边形。", s),
            _tf_q(f"bi:{node_key}:tf:{s}", node_key, "basic",
                  "判断：三角形的面积总是平行四边形面积的一半。", False, "必须加上前提“等底等高”。"),
            _text_q(f"bi:{node_key}:fb:{s}", node_key, "medium", "fill_blank",
                    f"填空：一个三角形面积是 {area} cm²，高是 {h} cm，它的底是（ ）cm。",
                    str(base), f"a = 2S ÷ h = {area * 2} ÷ {h} = {base}。"),
            _text_q(f"bi:{node_key}:sa:{s}", node_key, "hard", "short_answer",
                    f"解决问题：一块三角形警示牌底 {base} 分米、高 {h} 分米，给正反两面都刷漆，刷漆总面积是多少平方分米？（只填数字）",
                    str(area * 2), f"单面面积 {area}，两面面积 {area * 2} 平方分米。"),
            _choice_q(f"bi:{node_key}:sc2:{s}", node_key, "medium",
                      f"一个三角形与一个平行四边形等底等高，平行四边形面积是 {area * 2} cm²，三角形面积是（ ）cm²。",
                      str(area), [str(area * 2), str(area * 4), str(area // 2)],
                      "等底等高时，三角形面积是平行四边形面积的一半。", s + 1),
        ]

    if node_key == "M2-4":
        top, bot, h = a + 1, a + 5, b * 2
        area = (top + bot) * h // 2
        return [
            _text_q(f"bi:{node_key}:calc:{s}", node_key, "basic", "calculation",
                    f"计算：梯形上底 {top} cm，下底 {bot} cm，高 {h} cm，面积是多少 cm²？（只填数字）",
                    str(area), f"S = ({top} + {bot}) × {h} ÷ 2 = {area}。"),
            _choice_q(f"bi:{node_key}:sc:{s}", node_key, "basic",
                      "梯形的面积公式是（ ）。",
                      "S = (a + b)h ÷ 2", ["S = ah", "S = (a + b)h", "S = ab ÷ 2"],
                      "两个完全一样的梯形拼成底为 (a+b)、高为 h 的平行四边形。", s),
            _tf_q(f"bi:{node_key}:tf:{s}", node_key, "basic",
                  "判断：梯形的上底和下底之和不变、高扩大到原来的 2 倍，面积也扩大到原来的 2 倍。", True, "面积与高成正比。"),
            _text_q(f"bi:{node_key}:fb:{s}", node_key, "medium", "fill_blank",
                    f"填空：梯形面积是 {area} cm²，上底 {top} cm，下底 {bot} cm，高是（ ）cm。",
                    str(h), f"h = 2S ÷ (a + b) = {area * 2} ÷ {top + bot} = {h}。"),
            _text_q(f"bi:{node_key}:sa:{s}", node_key, "hard", "short_answer",
                    f"解决问题：一堆钢管最上层有 {top} 根，最下层有 {bot} 根，每相邻两层相差 1 根，共有 {bot - top + 1} 层，这堆钢管共有多少根？（只填数字）",
                    str((top + bot) * (bot - top + 1) // 2),
                    f"按梯形公式计算：({top} + {bot}) × {bot - top + 1} ÷ 2 = {(top + bot) * (bot - top + 1) // 2}（根）。"),
            _choice_q(f"bi:{node_key}:sc2:{s}", node_key, "medium",
                      "当梯形的上底缩短为 0 时，它就变成了（ ）。", "三角形", ["平行四边形", "长方形", "正方形"],
                      "上底为 0 时，(0 + b)h ÷ 2 = bh ÷ 2，就是三角形。", s + 3),
        ]

    if node_key == "M2-5":
        ha = a + 2
        sqm = ha * 10000
        rect_w, rect_h = a + 4, b + 2
        tri_h = 4
        combo = rect_w * rect_h + rect_w * tri_h // 2
        return [
            _text_q(f"bi:{node_key}:fb:{s}", node_key, "basic", "fill_blank",
                    f"填空：{ha} 公顷 =（ ）平方米。", str(sqm), f"1 公顷 = 10000 平方米，{ha} 公顷 = {sqm} 平方米。"),
            _choice_q(f"bi:{node_key}:sc:{s}", node_key, "basic",
                      "1 平方千米等于（ ）公顷。", "100", ["10", "1000", "10000"],
                      "1 平方千米 = 1000000 平方米 = 100 公顷。", s),
            _tf_q(f"bi:{node_key}:tf:{s}", node_key, "basic",
                  "判断：求组合图形面积时，可以用“分割法”也可以用“添补法”。", True, "两种方法都能把组合图形转化为基本图形。"),
            _text_q(f"bi:{node_key}:calc:{s}", node_key, "medium", "calculation",
                    f"计算：一个组合图形由长 {rect_w} cm、宽 {rect_h} cm 的长方形和底 {rect_w} cm、高 {tri_h} cm 的三角形拼成，总面积是多少 cm²？（只填数字）",
                    str(combo), f"{rect_w} × {rect_h} + {rect_w} × {tri_h} ÷ 2 = {combo}。"),
            _text_q(f"bi:{node_key}:sa:{s}", node_key, "hard", "short_answer",
                    f"解决问题：一块长 400 米、宽 {a * 50} 米的长方形林地，面积是多少公顷？（只填数字）",
                    _fmt(_d(400 * a * 50) / _d(10000)),
                    f"400 × {a * 50} = {400 * a * 50} 平方米 = {_fmt(_d(400 * a * 50) / _d(10000))} 公顷。"),
            _choice_q(f"bi:{node_key}:sc2:{s}", node_key, "medium",
                      "我国陆地领土面积约 960 万（ ）。", "平方千米", ["公顷", "平方米", "平方分米"],
                      "衡量国土面积通常用平方千米。", s + 2),
        ]

    if node_key == "M3-1":
        val = a + 3
        res = 3 * val + b
        return [
            _choice_q(f"bi:{node_key}:sc:{s}", node_key, "basic",
                      f"每支钢笔 x 元，买 {a} 支钢笔一共需要（ ）元。",
                      f"{a}x", [f"x + {a}", f"x - {a}", f"{a} ÷ x"], "单价 × 数量，数字写在字母前面省略乘号。", s),
            _tf_q(f"bi:{node_key}:tf:{s}", node_key, "basic",
                  "判断：a² 一定等于 2a。", False, "a² 表示 a × a，2a 表示 2 × a，只有 a=0 或 a=2 时才相等。"),
            _text_q(f"bi:{node_key}:fb:{s}", node_key, "medium", "fill_blank",
                    f"填空：当 x = {val} 时，3x + {b} 的值是（ ）。", str(res), f"3 × {val} + {b} = {res}。"),
            _text_q(f"bi:{node_key}:calc:{s}", node_key, "medium", "calculation",
                    f"化简并求值：当 a = {c} 时，5a - 2a =", str(3 * c), f"5a - 2a = 3a = 3 × {c} = {3 * c}。"),
            _text_q(f"bi:{node_key}:sa:{s}", node_key, "hard", "short_answer",
                    f"解决问题：一本书共 120 页，小明每天看 m 页，看了 {a} 天，当 m = {b + 4} 时还剩多少页没看？（只填数字）",
                    str(120 - a * (b + 4)), f"120 - {a} × {b + 4} = {120 - a * (b + 4)}（页）。"),
            _choice_q(f"bi:{node_key}:sc2:{s}", node_key, "medium",
                      "用 a 表示正方形的边长，它的周长 C =（ ）。", "4a", ["a²", "2a", "a + 4"],
                      "正方形周长是边长的 4 倍，写作 4a。", s + 1),
        ]

    if node_key == "M3-2":
        x1 = a + 4
        rhs1 = x1 + b * 2
        x2 = c + 1
        rhs2 = 3 * x2 + a
        return [
            _text_q(f"bi:{node_key}:calc:{s}", node_key, "basic", "calculation",
                    f"解方程：x + {b * 2} = {rhs1}，x =", str(x1), f"两边同时减 {b * 2}，得 x = {x1}。"),
            _choice_q(f"bi:{node_key}:sc:{s}", node_key, "basic",
                      "下面式子中，是方程的是（ ）。",
                      "2x + 5 = 17", ["3x + 4 > 10", "5 + 7 = 12", "4x - 1"],
                      "方程必须同时满足：含有未知数、是等式。", s),
            _tf_q(f"bi:{node_key}:tf:{s}", node_key, "basic",
                  "判断：等式两边同时乘或除以同一个不为 0 的数，左右两边仍然相等。", True, "这是等式的性质 2。"),
            _text_q(f"bi:{node_key}:fb:{s}", node_key, "medium", "fill_blank",
                    f"填空：方程 3x + {a} = {rhs2} 的解是 x =（ ）。", str(x2),
                    f"3x = {rhs2 - a}，x = {x2}。"),
            _text_q(f"bi:{node_key}:sa:{s}", node_key, "hard", "short_answer",
                    f"解决问题：一个数的 3 倍加上 {a} 等于 {rhs2}，这个数是多少？（只填数字）",
                    str(x2), f"设这个数为 x，3x + {a} = {rhs2}，解得 x = {x2}。"),
            _choice_q(f"bi:{node_key}:sc2:{s}", node_key, "medium",
                      f"x = {x2} 是下面哪个方程的解？（ ）",
                      f"3x + {a} = {rhs2}", [f"3x - {a} = {rhs2}", f"2x + {a} = {rhs2}", f"x + {a} = {rhs2}"],
                      f"把 x = {x2} 代入 3x + {a} 得 {rhs2}。", s + 2),
        ]

    if node_key == "M3-3":
        km_dist = 5 + (s % 4)
        extra_km = km_dist - 3
        fare = 8 + extra_km * 2
        return [
            _text_q(f"bi:{node_key}:sa:{s}", node_key, "medium", "short_answer",
                    f"解决问题：出租车 3 千米以内收费 8 元，超过 3 千米的部分每千米 2 元（不足 1 千米按 1 千米算）。坐 {km_dist} 千米应付多少元？（只填数字）",
                    str(fare), f"8 + ({km_dist} - 3) × 2 = {fare}（元）。", [f"{fare}元"]),
            _choice_q(f"bi:{node_key}:sc:{s}", node_key, "basic",
                      "分段计费问题中，总费用通常等于（ ）。",
                      "起步价 + 超出部分费用", ["起步价 × 总里程", "超出部分单价 × 总里程", "起步价 - 超出费用"],
                      "先把路程或用量按分界点拆成两段，再分别计费相加。", s),
            _tf_q(f"bi:{node_key}:tf:{s}", node_key, "basic",
                  "判断：出租车规定不足 1 千米按 1 千米计费，那么 4.2 千米应按 5 千米计算。", True, "不足 1 千米按 1 千米算即向上取整。"),
            _text_q(f"bi:{node_key}:fb:{s}", node_key, "medium", "fill_blank",
                    f"填空：某停车场 1 小时内收 5 元，超过 1 小时每小时加收 3 元，停 {a + 1} 小时共收（ ）元。",
                    str(5 + a * 3), f"5 + ({a + 1} - 1) × 3 = {5 + a * 3}（元）。"),
            _text_q(f"bi:{node_key}:calc:{s}", node_key, "basic", "calculation",
                    f"计算：8 + ({km_dist} - 3) × 2 =", str(fare), f"先算括号内 {extra_km}，再乘 2 加 8 得 {fare}。"),
            _choice_q(f"bi:{node_key}:sc2:{s}", node_key, "hard",
                      "妈妈带 100 元买 2 袋大米（每袋 30.6 元）和 1 桶油（35.8 元），钱够吗？最稳妥的估算方法是（ ）。",
                      "把单价往大估（31×2+36=98<100），一定够",
                      ["把单价往小估，一定够", "无法估算", "只算大米价格"],
                      "判断“钱够不够”时往大估仍不超过预算，则一定够。", s + 1),
        ]

    if node_key == "M3-4":
        oil = 10 + (s % 5) * 3      # 10, 13, 16, 19, 22
        cap = 4
        bottles = (oil + cap - 1) // cap
        cloth = 20 + (s % 4) * 3    # 20, 23, 26, 29
        per_suit = 3
        suits = cloth // per_suit
        return [
            _text_q(f"bi:{node_key}:sa:{s}", node_key, "medium", "short_answer",
                    f"解决问题：有 {oil} 千克香油，每个瓶子最多装 {cap} 千克，至少需要准备几个瓶子？（只填数字）",
                    str(bottles), f"{oil} ÷ {cap} = {_fmt(_d(oil) / _d(cap))}，余下的油也要占 1 个瓶子，用进一法得 {bottles} 个。"),
            _text_q(f"bi:{node_key}:fb:{s}", node_key, "medium", "fill_blank",
                    f"填空：用 {cloth} 米布做礼服，每套需要 {per_suit} 米，最多能做（ ）套。",
                    str(suits), f"{cloth} ÷ {per_suit} = {suits} 余 {cloth % per_suit}，不够做 1 套要舍去，用去尾法得 {suits} 套。"),
            _choice_q(f"bi:{node_key}:sc:{s}", node_key, "basic",
                      "“运送货物至少需要几辆车”这类问题应采用（ ）取近似值。",
                      "进一法", ["去尾法", "四舍五入法", "直接舍去小数"],
                      "剩下的货物即使不满一车也需要多派一辆车，故用进一法。", s),
            _tf_q(f"bi:{node_key}:tf:{s}", node_key, "basic",
                  "判断：“一段丝带最多能包装几个礼盒”应该用去尾法。", True, "剩余丝带不够包装一个完整礼盒，必须舍去。"),
            _text_q(f"bi:{node_key}:calc:{s}", node_key, "basic", "calculation",
                    f"用进一法取整：{oil} ÷ {cap} ≈", str(bottles), f"{oil} ÷ {cap} 有余数，进一法得 {bottles}。"),
            _choice_q(f"bi:{node_key}:sc2:{s}", node_key, "hard",
                      f"每箱最多装 6 个苹果，装 {a * 6 + 1} 个苹果至少需要（ ）个箱子。",
                      str(a + 1), [str(a), str(a + 2), str(a - 1)],
                      f"{a} 个箱子装 {a * 6} 个，多出 1 个还需 1 个箱子，共 {a + 1} 个。", s + 2),
        ]

    if node_key == "M4-1":
        return [
            _choice_q(f"bi:{node_key}:sc:{s}", node_key, "basic",
                      "太阳从东边升起，这是（ ）现象。", "一定", ["可能", "不可能", "随机"],
                      "太阳东升西落是确定会发生的现象，用“一定”。", s),
            _tf_q(f"bi:{node_key}:tf:{s}", node_key, "basic",
                  "判断：袋子里全是红球，任意摸出一个球，可能是白球。", False, "袋子里没有白球，摸出白球是“不可能”事件。"),
            _choice_q(f"bi:{node_key}:sc2:{s}", node_key, "medium",
                      "掷一枚质地均匀的硬币，正面朝上（ ）。", "可能发生", ["一定发生", "不可能发生", "必然不发生"],
                      "硬币有正反两面，属于随机现象，可能发生。", s + 1),
            _text_q(f"bi:{node_key}:fb:{s}", node_key, "basic", "fill_blank",
                    "填空：盒子里只有 5 个黄球，任意摸 1 个，（ ）摸出黄球。（填“一定”“可能”或“不可能”）",
                    "一定", "盒中全是黄球，必然摸出黄球。"),
            _text_q(f"bi:{node_key}:calc:{s}", node_key, "medium", "calculation",
                    "填空：掷一枚 1～6 点的正方体骰子，朝上的点数（ ）大于 6。（填“一定”“可能”或“不可能”）",
                    "不可能", "骰子最大点数是 6，不可能大于 6。"),
            _text_q(f"bi:{node_key}:sa:{s}", node_key, "hard", "short_answer",
                    "解决问题：盒子里有红球和蓝球各 3 个，任意摸 1 个球，摸出红球是确定现象还是随机现象？（填“确定现象”或“随机现象”）",
                    "随机现象", "可能摸出红球也可能摸出蓝球，属于随机现象。", ["随机"]),
        ]

    if node_key == "M1-6":
        n_even = (a + 3) * 2
        g_a, g_b = 12, 18 if s % 2 == 0 else 20
        import math
        g_val = math.gcd(g_a, g_b)
        l_val = (g_a * g_b) // g_val
        return [
            _choice_q(f"bi:{node_key}:sc:{s}", node_key, "basic",
                      "下面各数中，既是 2 的倍数又是 5 的倍数的是（ ）。",
                      f"{a + 2}0", [f"{a + 2}5", f"{a + 2}2", f"{a + 2}3"],
                      "个位是 0 的数同时是 2 和 5 的倍数。", s),
            _tf_q(f"bi:{node_key}:tf:{s}", node_key, "basic",
                  "判断：1 既不是质数，也不是合数。", True, "质数只有 1 和它本身两个因数，1 只有 1 个因数。"),
            _text_q(f"bi:{node_key}:fb:{s}", node_key, "medium", "fill_blank",
                    f"填空：{g_a} 和 {g_b} 的最大公因数是（ ）。", str(g_val),
                    f"{g_a} 和 {g_b} 的最大公因数是 {g_val}。"),
            _text_q(f"bi:{node_key}:calc:{s}", node_key, "medium", "calculation",
                    f"计算：{g_a} 和 {g_b} 的最小公倍数是（ ）。", str(l_val),
                    f"最小公倍数 = {g_a} × {g_b} ÷ {g_val} = {l_val}。"),
            _text_q(f"bi:{node_key}:err:{s}", node_key, "hard", "error_diagnosis",
                    "易错辨析：小明说“所有的偶数都是合数”。请写出唯一一个不是合数的质偶数作为反例：",
                    "2", "2 是最小的质数，也是唯一的偶质数。"),
            _text_q(f"bi:{node_key}:ms:{s}", node_key, "hard", "multi_step",
                    f"综合推理：一个三位数 {a}2□ 既是 2 的倍数又是 3 的倍数，□ 里最大能填几？",
                    str(max(d for d in (0, 2, 4, 6, 8) if (a + 2 + d) % 3 == 0)),
                    f"同时满足个位为偶数且各位数字之和是 3 的倍数，最大为 {max(d for d in (0, 2, 4, 6, 8) if (a + 2 + d) % 3 == 0)}。"),
        ]

    if node_key == "M1-7":
        k_mul = 2 + (s % 4)
        num, den = 3, 4
        return [
            _choice_q(f"bi:{node_key}:sc:{s}", node_key, "basic",
                      f"把分数 {num * k_mul}/{den * k_mul} 约分成最简分数是（ ）。",
                      f"{num}/{den}", [f"{num * 2}/{den * 2}", f"{den}/{num}", f"1/{den}"],
                      f"分子分母同时除以最大公因数 {k_mul}，得 {num}/{den}。", s),
            _tf_q(f"bi:{node_key}:tf:{s}", node_key, "basic",
                  "判断：分数的分子和分母同时乘或除以同一个不为 0 的数，分数的大小不变。", True, "这是分数的基本性质。"),
            _text_q(f"bi:{node_key}:fb:{s}", node_key, "medium", "fill_blank",
                    f"填空：把 3 米长的绳子平均分成 {a + 3} 段，每段占全长的（ ）。（用 a/b 形式表示）",
                    f"1/{a + 3}", f"求每段占全长的几分之几，用 1 ÷ {a + 3} = 1/{a + 3}。"),
            _text_q(f"bi:{node_key}:calc:{s}", node_key, "medium", "calculation",
                    f"把分数 3/4 化成小数是（ ）。", "0.75", "3 ÷ 4 = 0.75。"),
            _text_q(f"bi:{node_key}:err:{s}", node_key, "hard", "error_diagnosis",
                    f"易错辨析：把 2/5 的分子加上 4，要使分数大小不变，分母应该加上几？（不要填乘几，只填加上几）",
                    "10", "分子 2 加 4 变成 6（扩大 3 倍），分母 5 也扩大 3 倍变成 15，15 - 5 = 10。"),
            _text_q(f"bi:{node_key}:ms:{s}", node_key, "hard", "multi_step",
                    "综合推理：把 5/8、0.6、3/4 按从小到大排列，排在中间的数是哪一个？（填原数）",
                    "5/8", "5/8 = 0.625，0.6 < 0.625 < 0.75，排在中间的是 5/8。", ["0.625"]),
        ]

    if node_key == "M1-8":
        return [
            _choice_q(f"bi:{node_key}:sc:{s}", node_key, "basic",
                      "计算 1/2 + 1/3 的结果是（ ）。", "5/6", ["2/5", "1/5", "2/6"],
                      "先通分：3/6 + 2/6 = 5/6。", s),
            _tf_q(f"bi:{node_key}:tf:{s}", node_key, "basic",
                  "判断：异分母分数相加减，必须先通分，化成同分母分数再计算。", True, "分数单位不同不能直接相加减，需先通分。"),
            _text_q(f"bi:{node_key}:calc:{s}", node_key, "medium", "calculation",
                    "计算（写成最简分数 a/b）：5/6 - 1/3 =", "1/2", "5/6 - 2/6 = 3/6 = 1/2。", ["0.5"]),
            _text_q(f"bi:{node_key}:fb:{s}", node_key, "medium", "fill_blank",
                    "填空：1 - 3/8 - 5/8 =（ ）。", "0", "连减等于减去两数之和：1 - (3/8 + 5/8) = 1 - 1 = 0。"),
            _text_q(f"bi:{node_key}:err:{s}", node_key, "hard", "error_diagnosis",
                    "易错辨析：小华算 1/4 + 1/4 = 2/8，他错把分母也相加了。正确结果化成最简分数是（ ）。",
                    "1/2", "同分母分数相加，分母不变分子相加：2/4 = 1/2。", ["0.5"]),
            _text_q(f"bi:{node_key}:sa:{s}", node_key, "hard", "short_answer",
                    "解决问题：一块菜地，1/4 种白菜，1/2 种萝卜，其余种黄瓜。种黄瓜的面积占这块菜地的几分之几？（用 a/b 表示）",
                    "1/4", "1 - 1/4 - 1/2 = 1/4。", ["0.25"]),
        ]

    if node_key == "M2-6":
        col, row = a, b
        move_r = 2 + (s % 3)
        return [
            _choice_q(f"bi:{node_key}:sc:{s}", node_key, "basic",
                      f"教室里小明坐在第 {col} 列第 {row} 行，用数对表示是（ ）。",
                      f"({col}, {row})", [f"({row}, {col})", f"({col + 1}, {row})", f"({col}, {row + 1})"],
                      "数对规则是“先列后行”，第几列写前面，第几行写后面。", s),
            _tf_q(f"bi:{node_key}:tf:{s}", node_key, "basic",
                  "判断：数对 (3, 5) 和 (5, 3) 表示的是同一个位置。", False, "(3, 5) 是第 3 列第 5 行，(5, 3) 是第 5 列第 3 行，位置不同。"),
            _text_q(f"bi:{node_key}:fb:{s}", node_key, "medium", "fill_blank",
                    f"填空：点 A({col}, {row}) 向右平移 {move_r} 格后，列数变为（ ）。（只填数字）",
                    str(col + move_r), f"向右平移列数加 {move_r}，行数不变，列数为 {col + move_r}。"),
            _text_q(f"bi:{node_key}:calc:{s}", node_key, "medium", "calculation",
                    f"计算：点 P({col}, {row}) 向上平移 3 格后的行数是（ ）。（只填数字）",
                    str(row + 3), f"向上平移列数不变，行数加 3，得 {row + 3}。"),
            _text_q(f"bi:{node_key}:err:{s}", node_key, "hard", "error_diagnosis",
                    f"易错辨析：小红说点 ({col}, {row}) 和点 ({col}, {row + 2}) 在同一行。实际上它们在同一（ ）（填“列”或“行”）。",
                    "列", "第一个数相同表示在同一列。"),
            _text_q(f"bi:{node_key}:ms:{s}", node_key, "hard", "multi_step",
                    f"综合推理：正方形的三个顶点分别是 (1, 1)、(4, 1)、(4, 4)，第四个顶点的列数是几？（只填数字）",
                    "1", "第四个顶点是 (1, 4)，列数为 1。"),
        ]

    if node_key == "M2-7":
        edge = 3 + (s % 4)   # 3..6
        l_len, w_len, h_len = a + 2, b, 2
        vol = l_len * w_len * h_len
        surf = 2 * (l_len * w_len + l_len * h_len + w_len * h_len)
        return [
            _text_q(f"bi:{node_key}:calc:{s}", node_key, "basic", "calculation",
                    f"计算：正方体棱长是 {edge} cm，它的体积是多少 cm³？（只填数字）",
                    str(edge ** 3), f"V = a³ = {edge} × {edge} × {edge} = {edge ** 3}。"),
            _choice_q(f"bi:{node_key}:sc:{s}", node_key, "basic",
                      f"一个正方体棱长是 {edge} cm，它的表面积是（ ）cm²。",
                      str(6 * edge * edge), [str(edge ** 3), str(4 * edge * edge), str(12 * edge)],
                      f"正方体表面积 = 6a² = 6 × {edge}² = {6 * edge * edge}。", s),
            _tf_q(f"bi:{node_key}:tf:{s}", node_key, "basic",
                  "判断：1 升（L）等于 1000 毫升（mL），也等于 1 立方分米（dm³）。", True, "1 L = 1 dm³ = 1000 mL = 1000 cm³。"),
            _text_q(f"bi:{node_key}:fb:{s}", node_key, "medium", "fill_blank",
                    f"填空：长方体长 {l_len} cm、宽 {w_len} cm、高 {h_len} cm，它的体积是（ ）cm³。",
                    str(vol), f"V = {l_len} × {w_len} × {h_len} = {vol}。"),
            _text_q(f"bi:{node_key}:err:{s}", node_key, "hard", "error_diagnosis",
                    "易错辨析：正方体的棱长扩大到原来的 2 倍，有人认为体积也扩大到原来的 2 倍。实际上体积会扩大到原来的（ ）倍。",
                    "8", "体积公式是 a³，棱长 ×2，体积 ×(2×2×2) = ×8。"),
            _text_q(f"bi:{node_key}:sa:{s}", node_key, "hard", "short_answer",
                    f"解决问题：做一个长 {l_len} dm、宽 {w_len} dm、高 {h_len} dm 的有盖长方体木箱，至少需要多少平方分米木板？（只填数字）",
                    str(surf), f"表面积 = 2 × ({l_len}×{w_len} + {l_len}×{h_len} + {w_len}×{h_len}) = {surf}（dm²）。"),
        ]

    if node_key == "M3-5":
        total_len = (a + 3) * 10   # 50..110
        gap = 5
        segs = total_len // gap
        return [
            _choice_q(f"bi:{node_key}:sc:{s}", node_key, "basic",
                      f"在长 {total_len} 米的小路一侧植树，每隔 {gap} 米栽一棵（两端都栽），一共要栽（ ）棵。",
                      str(segs + 1), [str(segs), str(segs - 1), str(segs + 2)],
                      f"间隔数 = {total_len} ÷ {gap} = {segs}，两端都栽：棵数 = 间隔数 + 1 = {segs + 1}。", s),
            _tf_q(f"bi:{node_key}:tf:{s}", node_key, "basic",
                  "判断：在圆形池塘周围植树（封闭图形），棵数正好等于间隔数。", True, "封闭图形一棵树对应一个间隔，棵数 = 间隔数。"),
            _text_q(f"bi:{node_key}:fb:{s}", node_key, "medium", "fill_blank",
                    f"填空：把一根木头锯成 {a + 2} 段，每锯一次需要 3 分钟，一共需要（ ）分钟。",
                    str((a + 1) * 3), f"锯成 {a + 2} 段只需锯 {a + 1} 次，{(a + 1)} × 3 = {(a + 1) * 3} 分钟。"),
            _text_q(f"bi:{node_key}:calc:{s}", node_key, "medium", "calculation",
                    f"计算：周长 {total_len} 米的圆形花坛每隔 {gap} 米摆一盆花，一共摆几盆？（只填数字）",
                    str(segs), f"封闭图形：盆数 = 间隔数 = {total_len} ÷ {gap} = {segs}。"),
            _text_q(f"bi:{node_key}:err:{s}", node_key, "hard", "error_diagnosis",
                    f"易错辨析：从 1 楼走到 5 楼，小亮以为走了 5 层楼梯。实际上走了（ ）层楼梯。",
                    "4", "楼层间隔数 = 5 - 1 = 4 层。"),
            _text_q(f"bi:{node_key}:sa:{s}", node_key, "hard", "short_answer",
                    f"解决问题：一条长 {total_len} 米的公路两旁都要安装路灯（两端都装），每隔 {gap} 米装一盏，一共需要多少盏路灯？（只填数字）",
                    str((segs + 1) * 2), f"一旁装 {segs + 1} 盏，两旁共 {(segs + 1) * 2} 盏。"),
        ]

    if node_key == "M3-6":
        return [
            _choice_q(f"bi:{node_key}:sc:{s}", node_key, "basic",
                      "有 9 瓶口香糖，其中 1 瓶少了 3 粒（较轻），用天平至少称（ ）次一定能找出这瓶次品。",
                      "2", ["1", "3", "4"], "9 瓶平均分成 (3, 3, 3) 三份，第 1 次确定在哪 3 瓶，第 2 次分 (1, 1, 1) 找出，共 2 次。", s),
            _tf_q(f"bi:{node_key}:tf:{s}", node_key, "basic",
                  "判断：用天平找次品时，把待测物品尽量平均分成 3 份通常最省次数。", True, "三分法每次可以把范围缩小到原来的 1/3。"),
            _text_q(f"bi:{node_key}:fb:{s}", node_key, "medium", "fill_blank",
                    "填空：用天平称 3 次，最多能从（ ）个零件中保证找出 1 个较轻的次品。",
                    "27", "3³ = 27，3 次最多保证在 27 个中找出次品。"),
            _text_q(f"bi:{node_key}:calc:{s}", node_key, "medium", "calculation",
                    "计算：有 8 个乒乓球，其中 1 个稍重，至少称几次一定能找出？（只填数字）",
                    "2", "8 分成 (3, 3, 2)，最多 2 次一定能找出。"),
            _text_q(f"bi:{node_key}:err:{s}", node_key, "hard", "error_diagnosis",
                    "易错辨析：10 盒饼干中 1 盒较轻，分成 (5, 5) 称需要 3 次；如果按最优三分法分成 (3, 3, 4)，至少称（ ）次一定能找出。",
                    "3", "9 以内 2 次，10～27 个至少需要 3 次。"),
            _text_q(f"bi:{node_key}:ms:{s}", node_key, "hard", "multi_step",
                    "综合推理：有 27 枚金币，其中 1 枚是较轻的假币，按三分法第一次在天平左右盘各放几枚？（只填数字）",
                    "9", "把 27 平均分成 (9, 9, 9)，左右盘各放 9 枚。"),
        ]

    if node_key == "M4-3":
        t1, t2, t3 = 18 + (s % 4), 24 + (s % 4), 20 + (s % 4)
        return [
            _choice_q(f"bi:{node_key}:sc:{s}", node_key, "basic",
                      "要清楚地反映某病人一周内体温的增减变化趋势，最适合选用（ ）统计图。",
                      "折线", ["条形", "扇形", "象形"], "折线统计图不仅能看出数量多少，还能清楚看出增减变化趋势。", s),
            _tf_q(f"bi:{node_key}:tf:{s}", node_key, "basic",
                  "判断：在折线统计图中，线段越陡，说明这一段时间内数量变化越大。", True, "斜率越陡代表单位时间内增减幅度越大。"),
            _text_q(f"bi:{node_key}:fb:{s}", node_key, "medium", "fill_blank",
                    f"填空：某地三天最高气温分别是 {t1}℃、{t2}℃、{t3}℃，最高气温与最低气温相差（ ）℃。（只填数字）",
                    str(t2 - t1), f"{t2} - {t1} = {t2 - t1}（℃）。"),
            _text_q(f"bi:{node_key}:calc:{s}", node_key, "medium", "calculation",
                    f"计算：三天最高气温分别为 {t1}℃、{t2}℃、{t3}℃，这三天的平均气温是多少℃？（保留整数）",
                    str(round((t1 + t2 + t3) / 3)), f"({t1} + {t2} + {t3}) ÷ 3 ≈ {round((t1 + t2 + t3) / 3)}℃。"),
            _text_q(f"bi:{node_key}:err:{s}", node_key, "hard", "error_diagnosis",
                    "易错辨析：要同时比较甲、乙两座城市一年 12 个月的气温变化趋势，应选用（ ）折线统计图。（填“单式”或“复式”）",
                    "复式", "两组数据的对比变化需要使用复式折线统计图。"),
            _text_q(f"bi:{node_key}:ms:{s}", node_key, "hard", "multi_step",
                    f"综合推理：一幅折线图记录了 1～4 月销量：20、35、30、50（台），销量上升幅度最大的是哪两个相邻月份之间？（填如“3-4”）",
                    "3-4", "1-2 月上升 15 台，2-3 月下降 5 台，3-4 月上升 20 台，故 3-4 月上升最快。", ["3-4月", "3到4月"]),
        ]

    # M4-2 可能性大小与游戏公平性
    red, blue = a + 4, 2
    return [
        _choice_q(f"bi:{node_key}:sc:{s}", node_key, "basic",
                  f"袋子里有 {red} 个红球和 {blue} 个蓝球，任意摸 1 个，摸到（ ）的可能性大。",
                  "红球", ["蓝球", "一样大", "无法判断"],
                  f"红球数量（{red}）多于蓝球（{blue}），摸到红球可能性大。", s),
        _tf_q(f"bi:{node_key}:tf:{s}", node_key, "basic",
              "判断：掷骰子规定“点数大于 3 甲赢，点数小于或等于 3 乙赢”，这个游戏规则是公平的。",
              True, "大于 3 有 4、5、6（3 种），小于等于 3 有 1、2、3（3 种），可能性相等，公平。"),
        _text_q(f"bi:{node_key}:fb:{s}", node_key, "medium", "fill_blank",
                f"填空：袋子里有 {red} 个红球和 {blue} 个蓝球，至少再放入（ ）个蓝球，摸到红球和蓝球的可能性才相等。",
                str(red - blue), f"数量相等时可能性相等，{red} - {blue} = {red - blue}（个）。"),
        _choice_q(f"bi:{node_key}:sc2:{s}", node_key, "medium",
                  "转盘平均分成 8 份，其中 5 份涂红色、2 份涂黄色、1 份涂绿色。指针停在（ ）区域的可能性最小。",
                  "绿色", ["红色", "黄色", "一样大"], "绿色占份数最少，可能性最小。", s + 2),
        _text_q(f"bi:{node_key}:calc:{s}", node_key, "medium", "calculation",
                f"计算：从标有 1～{red + blue} 的卡片中任抽 1 张，抽到偶数的卡片有几张？（只填数字）",
                str((red + blue) // 2), f"1～{red + blue} 中偶数有 {(red + blue) // 2} 张。"),
        _text_q(f"bi:{node_key}:sa:{s}", node_key, "hard", "short_answer",
                f"解决问题：袋子里有 {red} 个红球、{blue} 个蓝球。要使摸到蓝球的可能性比红球大，至少还要放进几个蓝球？（只填数字）",
                str(red - blue + 1), f"蓝球至少要有 {red + 1} 个，所以还要放 {red + 1 - blue} 个。"),
    ]


def _visual_questions_for_node(node_key: str, seed: int) -> list[dict[str, Any]]:
    """从仓库已验证的 visual_questions 引擎生成带 SVG 图示的精确题目."""
    mapped = VISUAL_NODE_MAP.get(node_key)
    if not mapped:
        return []
    out: list[dict[str, Any]] = []
    for idx, lv in enumerate(("medium", "hard")):
        src_key = mapped[(abs(int(seed)) + idx) % len(mapped)]
        try:
            items = vq.generate(src_key, lv, 1, abs(int(seed)) * 13 + idx + 1)
        except Exception:
            continue
        for k, raw in enumerate(items):
            qtype = raw.get("question_type") or "single_choice"
            opts = list(raw.get("options") or [])
            cidx = raw.get("correct_index")
            if qtype in ("single_choice", "true_false") and cidx is not None and 0 <= int(cidx) < len(opts):
                ans = str(opts[int(cidx)])
            else:
                ans = str(raw.get("answer") or "")
            out.append({
                "id": f"bi:{node_key}:vis:{src_key}:{lv}:{abs(int(seed))}:{k}",
                "nodeKey": node_key,
                "level": lv,
                "questionType": qtype,
                "text": str(raw.get("text") or ""),
                "options": opts,
                "correctIndex": int(cidx) if cidx is not None and qtype in ("single_choice", "true_false") else None,
                "answer": ans,
                "acceptableAnswers": [ans] if ans else [],
                "explanation": str(raw.get("explanation") or ""),
                "marks": TYPE_POINTS.get(qtype, 2) + (1 if lv == "hard" else 0),
                "figure": raw.get("figure"),
            })
    return out


def generate_node_questions(
    node_key: str,
    count: int = 5,
    seed: int = 0,
    exclude_ids: set[str] | None = None,
    types: set[str] | None = None,
    level: str | None = None,
    prefer_visual: bool = False,
) -> list[dict[str, Any]]:
    """按节点即时生成自带测试题（含系统画图题），免教师逐题导入."""
    skip = set(exclude_ids or ())
    out: list[dict[str, Any]] = []
    seen_text: set[str] = set()

    def _collect(pool: list[dict[str, Any]]) -> None:
        for q in pool:
            if len(out) >= count:
                return
            if q["id"] in skip or q["text"] in seen_text:
                continue
            if types and q["questionType"] not in types:
                continue
            if level and q["level"] != level:
                continue
            out.append(q)
            seen_text.add(q["text"])

    if prefer_visual:
        for offset in range(3):
            _collect(_visual_questions_for_node(node_key, seed + offset))
            if len(out) >= count:
                return out

    for offset in range(6):
        vis = _visual_questions_for_node(node_key, seed + offset) if offset < 2 else []
        base = _build_node_pool(node_key, seed + offset)
        # 穿插带图题，并确保前 5 题至少包含 1 道 hard 题（支撑一次全对即可三星精通）
        mixed: list[dict[str, Any]] = []
        if vis:
            mixed.append(vis[0])
        mixed.extend(base[:3])
        if len(vis) > 1:
            mixed.append(vis[1])
        mixed.extend(base[3:])
        if count >= 5 and len(mixed) > 5 and not any(q.get("level") == "hard" for q in mixed[:5]):
            hard_idx = next((i for i in range(5, len(mixed)) if mixed[i].get("level") == "hard"), None)
            if hard_idx is not None:
                mixed[4], mixed[hard_idx] = mixed[hard_idx], mixed[4]
        _collect(mixed)
        if len(out) >= count:
            return out
    return out


def public_question(q: dict[str, Any]) -> dict[str, Any]:
    """剥离答案，返回给学生端作答的公开题目结构."""
    base_label = TYPE_LABELS.get(q["questionType"], q["questionType"])
    ans_str = str(q.get("answer", ""))
    keypad_mode = "fraction" if "/" in ans_str else ("ratio" if ":" in ans_str else "number")
    return {
        "id": q["id"],
        "nodeKey": q["nodeKey"],
        "grade": infer_grade_from_node_key(q["nodeKey"]),
        "level": q["level"],
        "levelLabel": LEVEL_LABELS.get(q["level"], q["level"]),
        "questionType": q["questionType"],
        "typeLabel": f"看图·{base_label}" if q.get("figure") else base_label,
        "hasFigure": bool(q.get("figure")),
        "keypadMode": keypad_mode,
        "marks": q["marks"],
        "text": q["text"],
        "options": list(q.get("options") or []),
        "figure": q.get("figure"),
    }


def _normalize_text_answer(raw: Any) -> str:
    s = str(raw or "").strip()
    s = re.sub(r"\s+", "", s)
    s = s.replace("，", ",").replace("。", ".").replace("％", "%").replace("：", ":").replace("／", "/")
    # 分数（如 3/4 或 -1/2）精确保持，必要时化为最简分数比对
    m_frac = re.fullmatch(r"([+-]?\d+)/([1-9]\d*)", s)
    if m_frac:
        num = int(m_frac.group(1))
        den = int(m_frac.group(2))
        import math
        g = math.gcd(abs(num), den)
        num //= g
        den //= g
        return str(num) if den == 1 else f"{num}/{den}"
    # 去掉末尾常见单位以便比较纯数值
    unit_stripped = re.sub(
        r"(元|米|厘米|分米|千米|毫米|平方米|平方分米|平方厘米|公顷|平方千米|立方米|立方分米|立方厘米|千克|克|吨|个|套|根|张|页|人|名|本|棵|只|盒|块|袋|杯|天|小时|分钟|分|秒|度|°|℃|%|万|cm³|cm²|cm|dm³|dm²|dm|m³|m²|m|km)$",
        "",
        s,
        flags=re.IGNORECASE,
    )
    candidate = unit_stripped or s
    m_frac2 = re.fullmatch(r"([+-]?\d+)/([1-9]\d*)", candidate)
    if m_frac2:
        num = int(m_frac2.group(1))
        den = int(m_frac2.group(2))
        import math
        g = math.gcd(abs(num), den)
        num //= g
        den //= g
        return str(num) if den == 1 else f"{num}/{den}"
    try:
        return _fmt(Decimal(candidate))
    except (InvalidOperation, ValueError):
        return s.lower()


def grade_builtin_question(
    q: dict[str, Any],
    selected_index: int | None = None,
    text_answer: str = "",
) -> bool:
    """对自带题进行客观自动判分."""
    if q["questionType"] in ("single_choice", "true_false"):
        if selected_index is None:
            return False
        return int(selected_index) == int(q["correctIndex"])
    if not str(text_answer or "").strip():
        return False
    got = _normalize_text_answer(text_answer)
    accepted = {_normalize_text_answer(a) for a in (q.get("acceptableAnswers") or [q["answer"]])}
    return got in accepted


def compute_node_light_state(
    *,
    attempts: int,
    correct: int,
    best_quiz_rate: float = 0.0,
    hard_correct: int = 0,
    sprint_boost_stars: int = 0,
    needs_repair: bool = False,
) -> dict[str, Any]:
    """计算知识节点的游戏化点亮状态（未探索 / 探索中 / 已点亮★ / 精通★★★）."""
    rate = (correct / attempts) if attempts > 0 else 0.0
    effective_rate = max(rate, best_quiz_rate)
    if sprint_boost_stars >= 3 or (attempts >= 5 and effective_rate >= 0.95 and hard_correct >= 1 and not needs_repair):
        state, stars = "mastered", 3
    elif sprint_boost_stars >= 2 or (attempts >= 3 and effective_rate >= 0.8 and not needs_repair):
        state, stars = "lit", 2 if sprint_boost_stars >= 2 else 1
    elif sprint_boost_stars >= 1 and not needs_repair:
        state, stars = "lit", 1
    elif attempts > 0 or needs_repair:
        state, stars = "exploring", 0
    else:
        state, stars = "unexplored", 0
    return {
        "state": state,
        "stateLabel": LIGHT_STATES[state],
        "stars": stars,
        "attempts": attempts,
        "correct": correct,
        "accuracy": round(rate * 100),
        "needsRepair": bool(needs_repair),
    }


__all__ = [
    "DEFAULT_GRADE",
    "LEVEL_LABELS",
    "LIGHT_STATES",
    "MATH_G5_CORE_MAP",
    "SUBJECT_MATH",
    "TYPE_LABELS",
    "TYPE_POINTS",
    "VISUAL_NODE_MAP",
    "compute_node_light_state",
    "generate_node_questions",
    "get_all_math_nodes",
    "get_builtin_math_map",
    "grade_builtin_question",
    "public_question",
]
