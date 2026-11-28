"""数学 1、2、3、4、6 年级通用知识地图、确定性参数化题库与强应试/乐考专项定义.

核心约定：
- 每个年级 4 个知识域单元，每个域 4 个核心节点，共 16 个节点；
- 所有节点题目随 seed 确定性生成不同数值，覆盖 single_choice / true_false / fill_blank / calculation / short_answer 5 种题型与 basic / medium / hard 3 档难度；
- 1、2 年级所有非选择题（fill_blank / calculation / short_answer）标准答案均为纯数字，学生只用内嵌大号数字盘（0-9）即可 100% 独立作答；
- 所有数值由 Python 精确计算得出，零幻觉；
- 几何/图形节点支持系统画图题（VISUAL_NODE_MAP + 标准 gridshape 图形生成）。
"""
from __future__ import annotations

import copy
from decimal import Decimal
import math
from typing import Any, Iterable

from changying.services.arena_grade_profiles import GRADE_THEMES

SUBJECT_MATH = "数学"

TYPE_POINTS: dict[str, int] = {
    "single_choice": 2,
    "true_false": 1,
    "fill_blank": 2,
    "calculation": 3,
    "error_diagnosis": 3,
    "short_answer": 5,
    "multi_step": 5,
}

# G1 / G2 / G3 / G4 / G6 几何节点到 visual_questions 画图族的映射
GRADE_VISUAL_NODE_MAP: dict[str, tuple[str, ...]] = {
    "G1-M3-2": ("1-1",),
    "G1-M3-3": ("6-4", "4-2"),
    "G2-M3-2": ("4-1",),
    "G2-M3-3": ("1-1", "4-1", "4-2"),
    "G3-M2-3": ("6-4", "4-2"),
    "G3-M2-4": ("6-4", "6-6"),
    "G4-M2-3": ("6-1", "6-3"),
    "G4-M2-4": ("6-2", "4-1"),
    "G6-M2-1": ("6-6", "4-3"),
    "G6-M2-3": ("6-4", "6-5"),
    "G6-M2-4": ("1-2", "1-3"),
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


def _choice_q(
    qid: str,
    node_key: str,
    level: str,
    text: str,
    answer: str,
    distractors: list[str],
    explanation: str,
    seed: int,
    figure: dict[str, Any] | None = None,
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
    cidx = abs(int(seed)) % 4
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
        "figure": figure,
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
    figure: dict[str, Any] | None = None,
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
        "figure": figure,
    }


def _rect_grid_figure(w_cells: int, h_cells: int, title: str = "每个小方格边长 1 厘米") -> dict[str, Any]:
    x0, y0 = 1, 1
    pts = [[x0, y0], [x0 + w_cells, y0], [x0 + w_cells, y0 + h_cells], [x0, y0 + h_cells]]
    return {
        "type": "gridshape",
        "width": max(10, w_cells + 3),
        "height": max(8, h_cells + 3),
        "title": title,
        "shapes": [{"points": pts, "tone": "a", "label": ""}],
    }


def _bearing_grid_figure(dx: int, dy: int) -> dict[str, Any]:
    ox, oy = 1, 1
    ax, ay = ox + dx, oy + dy
    return {
        "type": "gridshape",
        "width": max(8, ax + 2),
        "height": max(8, ay + 2),
        "title": "上北下南，左西右东（每格代表 100 米）",
        "shapes": [
            {"points": [[ox, oy], [ox + 1, oy], [ox + 1, oy + 1], [ox, oy + 1]], "tone": "b", "label": "O"},
            {"points": [[ax, ay], [ax + 1, ay], [ax + 1, ay + 1], [ax, ay + 1]], "tone": "a", "label": "A"},
        ],
    }


# ==============================================================================
# 1. 一年级 / 二年级 / 三年级 / 四年级 / 六年级 数学通用知识地图定义（各 16 节点）
# ==============================================================================

MATH_G1_CORE_MAP: dict[str, Any] = {
    "version": 2,
    "subject": SUBJECT_MATH,
    "grade": 1,
    "textbookAgnostic": True,
    "title": GRADE_THEMES[1]["mathTitle"],
    "units": [
        _u("D1", "数与认数", "number_ops", "🔢"),
        _u("D2", "加减口算", "number_ops", "⚡"),
        _u("D3", "图形位置与钟表人民币", "geometry", "📐"),
        _u("D4", "看图列式与思维启蒙", "algebra_word", "🧩"),
    ],
    "nodes": [
        # D1 数与认数
        _n("G1-M1-1", "D1", "10以内数的认识与分合", "认识 0～10 各数的含义、顺序、大小比较及 2～10 各数的分与合"),
        _n("G1-M1-2", "D1", "11～20各数的组成（十位与个位）", "认识计数单位“一”和“十”，掌握 11～20 各数由 1 个十和几个一组成", ["G1-M1-1"]),
        _n("G1-M1-3", "D1", "100以内数的顺序与比大小", "掌握 100 以内数的读写、百数表顺序、几十几的组成及两位数大小比较", ["G1-M1-2"]),
        _n("G1-M1-4", "D1", "整十数加一位数及相应减法", "结合数的组成熟练计算整十数加一位数及相应的减法（如 30+5=35、35-5=30）", ["G1-M1-3"]),
        # D2 加减口算
        _n("G1-M2-1", "D2", "10以内加减法口算", "熟练口算 10 以内加法、减法、连加、连减及加减混合运算", ["G1-M1-1"]),
        _n("G1-M2-2", "D2", "20以内凑十法进位加法", "掌握“看大数，拆小数，凑成十，加剩数”的 9/8/7/6 加几进位加法", ["G1-M1-2", "G1-M2-1"]),
        _n("G1-M2-3", "D2", "20以内破十法退位减法", "掌握“破十法”与“想加算减法”口算十几减 9、8、7、6 等退位减法", ["G1-M2-2"]),
        _n("G1-M2-4", "D2", "100以内整十数与两位数加减一位数", "掌握整十数加减整十数、两位数加减一位数和整十数口算", ["G1-M1-4", "G1-M2-3"]),
        # D3 图形位置与钟表人民币
        _n("G1-M3-1", "D3", "上下前后左右位置辨析", "理解上下、前后、左右的相对位置关系，按顺序和方位确定物体位置"),
        _n("G1-M3-2", "D3", "认识立体图形（长方体/正方体/圆柱/球）", "直观辨认长方体、正方体、圆柱和球的特征，数出立体组合中积木的个数"),
        _n("G1-M3-3", "D3", "认识平面图形与拼组", "认识长方形、正方形、平行四边形、三角形和圆，掌握七巧板与简单图形拼组", ["G1-M3-2"]),
        _n("G1-M3-4", "D3", "认识整时与人民币元角分换算", "看钟面认读整时，掌握 1 元=10 角、1 角=10 分换算与简单购物计算", ["G1-M1-3"]),
        # D4 看图列式与思维启蒙
        _n("G1-M4-1", "D4", "一图四式与求和求部分应用", "看懂大括号与问号图意，用加法求总数、用减法求部分数", ["G1-M2-2", "G1-M2-3"]),
        _n("G1-M4-2", "D4", "比多少与相差几实际问题", "运用一一对应和减法解决“一个数比另一个数多几（少几）”的实际问题", ["G1-M4-1"]),
        _n("G1-M4-3", "D4", "找规律填数与图形规律", "发现图形或数字重复排列、依次递增或递减的规律并填出空缺项", ["G1-M1-3"]),
        _n("G1-M4-4", "D4", "排队问题（第几与有几人）", "区分“几个”和“第几”，解决排队求总人数及两人之间有几人问题", ["G1-M2-1"]),
    ],
}

MATH_G2_CORE_MAP: dict[str, Any] = {
    "version": 2,
    "subject": SUBJECT_MATH,
    "grade": 2,
    "textbookAgnostic": True,
    "title": GRADE_THEMES[2]["mathTitle"],
    "units": [
        _u("D1", "加减与乘法口诀", "number_ops", "⚡"),
        _u("D2", "表内除法与万以内数", "number_ops", "🔢"),
        _u("D3", "测量图形与时间质量", "geometry", "📐"),
        _u("D4", "混合运算与推理广角", "algebra_word", "🧩"),
    ],
    "nodes": [
        # D1 加减与乘法口诀
        _n("G2-M1-1", "D1", "100以内两位数进位加与退位减", "掌握两位数加两位数进位笔算、两位数减两位数退位笔算及求比一个数多（少）几"),
        _n("G2-M1-2", "D1", "连加连减与加减混合", "掌握 100 以内连加、连减、加减混合及带小括号的两步加减运算", ["G2-M1-1"]),
        _n("G2-M1-3", "D1", "乘法的初步认识与2～6乘法口诀", "理解乘法是求几个相同加数和的简便运算，熟记并运用 2～6 的乘法口诀"),
        _n("G2-M1-4", "D1", "7～9乘法口诀与表内乘法综合", "熟记 7、8、9 的乘法口诀，理解“倍”的含义并解决表内乘法应用题", ["G2-M1-3"]),
        # D2 表内除法与万以内数
        _n("G2-M2-1", "D2", "平均分与除法的初步认识", "理解“每份分得同样多叫平均分”，认识除法算式中的被除数、除数和商", ["G2-M1-3"]),
        _n("G2-M2-2", "D2", "用2～9乘法口诀求商", "熟练运用“想乘法口诀求商”计算表内除法，解决平均分与包含除问题", ["G2-M1-4", "G2-M2-1"]),
        _n("G2-M2-3", "D2", "有余数的除法（余数比除数小）", "掌握有余数除法的含义与试商，牢记“余数一定比除数小”及被除数=商×除数+余数", ["G2-M2-2"]),
        _n("G2-M2-4", "D2", "万以内数的读写组成与近似数", "认识千位和万位，掌握 10000 以内数的组成、读写、大小比较、近似数与整百整千加减"),
        # D3 测量图形与时间质量
        _n("G2-M3-1", "D3", "厘米和米的认识与换算", "建立 1 厘米和 1 米的长度观念，掌握 1 米=100 厘米及用尺子测量物体长度"),
        _n("G2-M3-2", "D3", "角的初步认识（直角/锐角/钝角）", "认识角的顶点和边，借助三角尺辨认直角、锐角和钝角，掌握角的大小与边长无关", ["G2-M3-1"]),
        _n("G2-M3-3", "D3", "观察物体与轴对称平移旋转", "从不同方向观察简单立体图形，辨认轴对称图形、平移现象与旋转现象", ["G2-M3-2"]),
        _n("G2-M3-4", "D3", "认识几时几分与克和千克", "掌握 1 时=60 分、钟面几时几分认读，以及 1 千克=1000 克的质量换算与比较"),
        # D4 混合运算与推理广角
        _n("G2-M4-1", "D4", "乘加乘减与两级混合运算", "掌握先算乘除后算加减、有小括号先算小括号里面的两步混合运算", ["G2-M1-4", "G2-M2-2"]),
        _n("G2-M4-2", "D4", "有余数除法周期与租船进一问题", "运用有余数除法解决租船“进一法”、购物“去尾法”及周期循环排列问题", ["G2-M2-3"]),
        _n("G2-M4-3", "D4", "简单的排列组合（搭配问题）", "运用固定十位法或连线法解决数字组数、衣服搭配与握手场次问题", ["G2-M1-3"]),
        _n("G2-M4-4", "D4", "简单逻辑推理（排除法与方格填数）", "运用排除法进行简单条件推理，掌握每行每列 1～4 不重复的四宫格填数"),
    ],
}

MATH_G3_CORE_MAP: dict[str, Any] = {
    "version": 2,
    "subject": SUBJECT_MATH,
    "grade": 3,
    "textbookAgnostic": True,
    "title": GRADE_THEMES[3]["mathTitle"],
    "units": [
        _u("D1", "数与运算", "number_ops", "⚡"),
        _u("D2", "图形与几何", "geometry", "📐"),
        _u("D3", "数量关系与分数", "algebra_word", "🧩"),
        _u("D4", "时间统计与广角", "stats_prob", "🎲"),
    ],
    "nodes": [
        # D1 数与运算
        _n("G3-M1-1", "D1", "万以内加减法与验算", "掌握三位数加减法（含连续进位与退位）及加减互逆验算方法"),
        _n("G3-M1-2", "D1", "多位数乘一位数", "掌握整十整百数乘一位数口算、两三位数乘一位数笔算及含 0 乘法", ["G3-M1-1"]),
        _n("G3-M1-3", "D1", "除数是一位数的除法", "掌握商是两三位数的笔算除法、商中间或末尾有 0 的除法与有余数验算", ["G3-M1-2"]),
        _n("G3-M1-4", "D1", "两位数乘两位数", "掌握两位数乘两位数不进位与进位笔算、整十数乘法速算", ["G3-M1-2"]),
        # D2 图形与几何
        _n("G3-M2-1", "D2", "毫米分米与千米换算", "建立毫米(mm)、厘米(cm)、分米(dm)、米(m)、千米(km)的长度量感与换算"),
        _n("G3-M2-2", "D2", "吨与质量单位换算", "掌握克(g)、千克(kg)、吨(t)之间的 1000 进率换算与载重问题", ["G3-M2-1"]),
        _n("G3-M2-3", "D2", "长方形与正方形周长", "理解周长概念，掌握长方形周长=(长+宽)×2、正方形周长=边长×4 及看图求周长", ["G3-M2-1"]),
        _n("G3-M2-4", "D2", "长方形与正方形面积", "掌握长方形和正方形面积公式，区分周长与面积并完成平方厘米/平方分米/平方米换算", ["G3-M2-3"]),
        # D3 数量关系与代数/分数
        _n("G3-M3-1", "D3", "四则混合运算顺序", "掌握同级运算、乘加乘减、除加除减及带小括号的两步混合运算顺序", ["G3-M1-2", "G3-M1-3"]),
        _n("G3-M3-2", "D3", "两步计算解决实际问题", "运用倍比关系、归一与归总模型解决两步计算应用题", ["G3-M3-1"]),
        _n("G3-M3-3", "D3", "分数的初步认识与简单加减", "认识几分之一和几分之几，比较同分母或同分子分数大小，计算同分母分数加减法與 1 减几分之几"),
        _n("G3-M3-4", "D3", "小数的初步认识与加减", "结合元角分与米制认识一位小数，比较大小并计算一位小数加减法", ["G3-M3-3"]),
        # D4 统计与数学广角
        _n("G3-M4-1", "D4", "时分秒与经过时间计算", "掌握 1 时=60 分、1 分=60 秒换算，计算同一天内的经过时间"),
        _n("G3-M4-2", "D4", "年月日与24时计时法", "掌握大月小月、平年闰年判断、普通计时法与 24 时计时法转换", ["G3-M4-1"]),
        _n("G3-M4-3", "D4", "复式统计表与数据分析", "读懂复式统计表中的行列汇总数据，进行求和与差值对比分析"),
        _n("G3-M4-4", "D4", "集合重叠问题（韦恩图）", "理解容斥原理：总人数 = A + B - 既A又B，解决重叠计数应用题", ["G3-M1-1"]),
    ],
}

MATH_G4_CORE_MAP: dict[str, Any] = {
    "version": 2,
    "subject": SUBJECT_MATH,
    "grade": 4,
    "textbookAgnostic": True,
    "title": GRADE_THEMES[4]["mathTitle"],
    "units": [
        _u("D1", "数与运算", "number_ops", "⚡"),
        _u("D2", "图形与几何", "geometry", "📐"),
        _u("D3", "数量关系与小数", "algebra_word", "🧩"),
        _u("D4", "统计与数学广角", "stats_prob", "🎲"),
    ],
    "nodes": [
        # D1 数与运算
        _n("G4-M1-1", "D1", "大数的认识与近似数", "掌握亿以内及亿以上数的读写、改写为“万”或“亿”作单位及四舍五入求近似数"),
        _n("G4-M1-2", "D1", "三位数乘两位数", "掌握三位数乘两位数笔算、积的变化规律及末尾有 0 的乘法巧算", ["G4-M1-1"]),
        _n("G4-M1-3", "D1", "除数是两位数的除法", "掌握试商调商方法、商是两位数或一位数的判断及商不变的规律", ["G4-M1-2"]),
        _n("G4-M1-4", "D1", "四则运算与乘法运算律", "掌握含中括号四则运算顺序，熟练运用加法和乘法交换律、结合律、分配律简算", ["G4-M1-2", "G4-M1-3"]),
        # D2 图形与几何
        _n("G4-M2-1", "D2", "公顷与平方千米换算", "掌握 1 公顷=10000 平方米、1 平方千米=100 公顷的换算与土地面积应用"),
        _n("G4-M2-2", "D2", "角的度量与分类", "认识锐角、直角、钝角、平角(180°)、周角(360°)的关系，会计算拼角与折角", ["G4-M2-1"]),
        _n("G4-M2-3", "D2", "平行四边形与梯形特征", "理解平行与垂直、点到直线的距离，掌握平行四边形易变形及梯形各部分特征", ["G4-M2-2"]),
        _n("G4-M2-4", "D2", "三角形特性与内角和", "掌握三角形三边关系（两边之和大于第三边）、按角与按边分类及三角形内角和 180°", ["G4-M2-2"]),
        # D3 数量关系与代数/小数
        _n("G4-M3-1", "D3", "小数的意义与性质（小数点移动）", "理解小数的计数单位、末尾添0去0性质及小数点移动引起大小变化的规律"),
        _n("G4-M3-2", "D3", "小数加减法与混合运算", "掌握小数点对齐的位数不同小数加减法、小数加减凑整简便运算", ["G4-M3-1"]),
        _n("G4-M3-3", "D3", "单价数量总价与速度时间路程", "熟练运用“单价×数量=总价”“速度×时间=路程”及逆运算解决行程与购物问题", ["G4-M1-2", "G4-M1-3"]),
        _n("G4-M3-4", "D3", "优化策略（烙饼与沏茶问题）", "掌握并行统筹（沏茶流程最短时间）与烙饼最短时间公式（饼数×单面时间）"),
        # D4 统计与数学广角
        _n("G4-M4-1", "D4", "条形统计图分析", "读懂 1 格代表多个单位的条形统计图，提取最值、总和与差值信息"),
        _n("G4-M4-2", "D4", "平均数与复式条形图", "理解“移多补少”与“总数÷总份数=平均数”，对比分析复式条形统计图", ["G4-M4-1"]),
        _n("G4-M4-3", "D4", "鸡兔同笼问题", "运用假设法或抬腿法解决经典鸡兔同笼及答对得分/答错扣分变式问题", ["G4-M1-4"]),
        _n("G4-M4-4", "D4", "和差倍与年龄还原问题", "掌握和差公式 (和+差)÷2、和倍差倍公式及逆向还原推理", ["G4-M1-4"]),
    ],
}

MATH_G6_CORE_MAP: dict[str, Any] = {
    "version": 2,
    "subject": SUBJECT_MATH,
    "grade": 6,
    "textbookAgnostic": True,
    "title": GRADE_THEMES[6]["mathTitle"],
    "units": [
        _u("D1", "数与运算", "number_ops", "⚡"),
        _u("D2", "图形与几何", "geometry", "📐"),
        _u("D3", "负数与比例代数", "algebra_word", "🧩"),
        _u("D4", "统计与小升初压轴", "stats_prob", "🎲"),
    ],
    "nodes": [
        # D1 数与运算
        _n("G6-M1-1", "D1", "分数乘法与混合运算", "掌握分数乘整数、分数乘分数、乘法分配律简算及连续求一个数的几分之几"),
        _n("G6-M1-2", "D1", "分数除法与倒数", "理解倒数意义，掌握除以一个不为 0 的数等于乘它的倒数及“已知一个数的几分之几求原数”", ["G6-M1-1"]),
        _n("G6-M1-3", "D1", "比的意义化简与按比分配", "掌握比与分数除法的关系、化简最简整数比、求比值及按比分配应用题", ["G6-M1-2"]),
        _n("G6-M1-4", "D1", "百分数与折扣税率利率", "掌握百分数与分数小数互化、合格率/增减幅度、折扣/成数及利息=本金×利率×存期", ["G6-M1-1"]),
        # D2 图形与几何
        _n("G6-M2-1", "D2", "位置与方向（偏角与距离）", "根据方向偏角（如北偏东30°）和距离精确描述位置及返程相对方向"),
        _n("G6-M2-2", "D2", "圆的认识与周长（π=3.14）", "掌握半径与直径关系 d=2r、圆周长公式 C=πd=2πr 及半圆周长计算"),
        _n("G6-M2-3", "D2", "圆与圆环扇形的面积", "掌握圆面积 S=πr²、圆环面积 S=π(R²-r²)、扇形面积及外方内圆/外圆内方", ["G6-M2-2"]),
        _n("G6-M2-4", "D2", "圆柱与圆锥的表面积和体积", "掌握圆柱侧面积与表面积、圆柱体积 V=Sh、圆锥体积 V=1/3Sh 及等底等高关系", ["G6-M2-3"]),
        # D3 数量关系与代数/比例
        _n("G6-M3-1", "D3", "负数的认识与数轴比较", "理解正负数表示相反意义的量，在数轴上比较负数、0、正数的大小并求温差"),
        _n("G6-M3-2", "D3", "比例的基本性质与解比例", "掌握在比例里“两内项之积等于两外项之积”，熟练求解含分数与小数的比例方程", ["G6-M1-3"]),
        _n("G6-M3-3", "D3", "正比例与反比例判断应用", "区分比值一定（正比例 y/x=k）与乘积一定（反比例 xy=k），用比例关系解应用题", ["G6-M3-2"]),
        _n("G6-M3-4", "D3", "比例尺与图形放大缩小", "掌握比例尺=图上距离:实际距离，已知任意两个量求第三个量及图形按比放大后的面积变化", ["G6-M3-2"]),
        # D4 统计与数学广角
        _n("G6-M4-1", "D4", "扇形统计图与数据分析", "理解扇形统计图表示各部分占总体的百分比，结合总量求各部分数量及圆心角度数", ["G6-M1-4"]),
        _n("G6-M4-2", "D4", "分数工程问题与合作效率", "把工作总量看作单位“1”，运用工作效率之和 1/(1/a+1/b) 解决合作工程问题", ["G6-M1-2"]),
        _n("G6-M4-3", "D4", "数与形规律推理", "掌握从 1 开始连续奇数求和等于 n²、点阵与等差/裂项规律推理"),
        _n("G6-M4-4", "D4", "鸽巢原理（抽屉原理）与行程压轴", "运用抽屉原理“商+1”求最不利保证值，解决相遇追及与小升初行程压轴问题", ["G6-M1-3"]),
    ],
}

GRADE_MATH_MAPS: dict[int, dict[str, Any]] = {
    1: MATH_G1_CORE_MAP,
    2: MATH_G2_CORE_MAP,
    3: MATH_G3_CORE_MAP,
    4: MATH_G4_CORE_MAP,
    6: MATH_G6_CORE_MAP,
}


def get_grade_math_map(grade: int) -> dict[str, Any] | None:
    """获取 G1/G2/G3/G4/G6 通用数学知识地图深拷贝."""
    m = GRADE_MATH_MAPS.get(int(grade))
    return copy.deepcopy(m) if m is not None else None


# ==============================================================================
# 2. G1 / G2 / G3 / G4 / G6 各 4 个应试/乐考专项（共 20 个分年级专项）
# ==============================================================================

MATH_G1_SPRINTS: list[dict[str, Any]] = [
    {
        "slug": "g1-math-add-sub-sprint",
        "subject": "数学",
        "grade": 1,
        "title": "20以内凑十破十速算乐考",
        "subtitle": "围绕 10 以内分合加减、20 以内凑十法进位加与破十法退位减的零打字速算乐考",
        "icon": "⚡",
        "timeLimitSec": 480,
        "questionCount": 8,
        "nodeKeys": ["G1-M1-1", "G1-M2-1", "G1-M2-2", "G1-M2-3"],
        "typeMix": {"calculation": 3, "single_choice": 2, "true_false": 1, "fill_blank": 2},
    },
    {
        "slug": "g1-math-hundred-num-sprint",
        "subject": "数学",
        "grade": 1,
        "title": "100以内认数与加减闯关",
        "subtitle": "11～20 数的组成、100 以内百数表顺序比大小、整十数与两位数加减一位数闯关",
        "icon": "🔢",
        "timeLimitSec": 480,
        "questionCount": 8,
        "nodeKeys": ["G1-M1-2", "G1-M1-3", "G1-M1-4", "G1-M2-4"],
        "typeMix": {"calculation": 2, "single_choice": 2, "true_false": 1, "fill_blank": 2, "short_answer": 1},
    },
    {
        "slug": "g1-math-shape-clock-sprint",
        "subject": "数学",
        "grade": 1,
        "title": "图形位置、钟表与人民币看图乐考",
        "subtitle": "上下前后左右位置、立体积木与七巧板平面拼组、整时钟面与元角分换算看图闯关",
        "icon": "📐",
        "timeLimitSec": 480,
        "questionCount": 8,
        "preferVisual": True,
        "nodeKeys": ["G1-M3-1", "G1-M3-2", "G1-M3-3", "G1-M3-4"],
        "typeMix": {"single_choice": 3, "true_false": 1, "fill_blank": 2, "calculation": 1, "short_answer": 1},
    },
    {
        "slug": "g1-math-word-logic-sprint",
        "subject": "数学",
        "grade": 1,
        "title": "看图列式、找规律与排队思维专项",
        "subtitle": "一图四式求和求部分、比多少相差几、数字图形找规律与排队第几思维乐考",
        "icon": "🏆",
        "timeLimitSec": 480,
        "questionCount": 8,
        "nodeKeys": ["G1-M4-1", "G1-M4-2", "G1-M4-3", "G1-M4-4"],
        "typeMix": {"single_choice": 2, "true_false": 1, "fill_blank": 2, "calculation": 1, "short_answer": 2},
    },
]

MATH_G2_SPRINTS: list[dict[str, Any]] = [
    {
        "slug": "g2-math-mul-calc-sprint",
        "subject": "数学",
        "grade": 2,
        "title": "100以内笔算与表内乘除速算乐考",
        "subtitle": "两位数进退位加减、连加连减混合、2～9 乘法口诀与用乘法口诀求商速算",
        "icon": "⚡",
        "timeLimitSec": 480,
        "questionCount": 8,
        "nodeKeys": ["G2-M1-1", "G2-M1-2", "G2-M1-3", "G2-M1-4", "G2-M2-2"],
        "typeMix": {"calculation": 3, "single_choice": 2, "true_false": 1, "fill_blank": 2},
    },
    {
        "slug": "g2-math-div-rem-sprint",
        "subject": "数学",
        "grade": 2,
        "title": "有余数除法与万以内数闯关",
        "subtitle": "平均分与除法算式、表内求商、有余数除法（余数比除数小）与万以内数读写组成",
        "icon": "🔢",
        "timeLimitSec": 480,
        "questionCount": 8,
        "nodeKeys": ["G2-M2-1", "G2-M2-2", "G2-M2-3", "G2-M2-4"],
        "typeMix": {"calculation": 2, "single_choice": 2, "true_false": 1, "fill_blank": 2, "short_answer": 1},
    },
    {
        "slug": "g2-math-measure-angle-sprint",
        "subject": "数学",
        "grade": 2,
        "title": "厘米和米、角与图形运动看图乐考",
        "subtitle": "厘米和米测量换算、直角锐角钝角辨析、观察物体与对称平移旋转、时分与克和千克",
        "icon": "📐",
        "timeLimitSec": 480,
        "questionCount": 8,
        "preferVisual": True,
        "nodeKeys": ["G2-M3-1", "G2-M3-2", "G2-M3-3", "G2-M3-4"],
        "typeMix": {"single_choice": 3, "true_false": 1, "fill_blank": 2, "calculation": 1, "short_answer": 1},
    },
    {
        "slug": "g2-math-cycle-logic-sprint",
        "subject": "数学",
        "grade": 2,
        "title": "周期租船、搭配与逻辑推理压轴专项",
        "subtitle": "两级混合运算、有余数除法周期与租船进一、排列组合搭配及四宫格填数逻辑推理",
        "icon": "🏆",
        "timeLimitSec": 480,
        "questionCount": 8,
        "nodeKeys": ["G2-M4-1", "G2-M4-2", "G2-M4-3", "G2-M4-4"],
        "typeMix": {"single_choice": 2, "true_false": 1, "fill_blank": 2, "calculation": 1, "short_answer": 2},
    },
]

MATH_G3_SPRINTS: list[dict[str, Any]] = [
    {
        "slug": "g3-math-calc-sprint",
        "subject": "数学",
        "grade": 3,
        "title": "万以内加减与乘除速算专项",
        "subtitle": "围绕万以内加减验算、多位数乘一位数、除数是一位数除法与两位数乘两位数的高频速算",
        "icon": "⚡",
        "timeLimitSec": 660,
        "questionCount": 10,
        "nodeKeys": ["G3-M1-1", "G3-M1-2", "G3-M1-3", "G3-M1-4"],
        "typeMix": {"calculation": 4, "single_choice": 2, "true_false": 2, "fill_blank": 2},
    },
    {
        "slug": "g3-math-measure-area-sprint",
        "subject": "数学",
        "grade": 3,
        "title": "单位换算与周长面积看图专项",
        "subtitle": "毫米千米、吨与千克换算、长方形与正方形周长面积看图实战",
        "icon": "📐",
        "timeLimitSec": 720,
        "questionCount": 10,
        "preferVisual": True,
        "nodeKeys": ["G3-M2-1", "G3-M2-2", "G3-M2-3", "G3-M2-4"],
        "typeMix": {"single_choice": 2, "true_false": 2, "fill_blank": 2, "calculation": 2, "short_answer": 2},
    },
    {
        "slug": "g3-math-fraction-mix-sprint",
        "subject": "数学",
        "grade": 3,
        "title": "混合运算与分数小数基础专项",
        "subtitle": "四则混合运算顺序、两步应用题、同分母分数加减与一位小数启蒙",
        "icon": "🧩",
        "timeLimitSec": 660,
        "questionCount": 10,
        "nodeKeys": ["G3-M3-1", "G3-M3-2", "G3-M3-3", "G3-M3-4"],
        "typeMix": {"single_choice": 2, "true_false": 1, "fill_blank": 2, "calculation": 3, "short_answer": 2},
    },
    {
        "slug": "g3-math-time-logic-sprint",
        "subject": "数学",
        "grade": 3,
        "title": "经过时间与集合应用压轴专项",
        "subtitle": "时分秒经过时间、年月日24时计时法、复式统计表与韦恩图重叠问题",
        "icon": "🏆",
        "timeLimitSec": 720,
        "questionCount": 10,
        "nodeKeys": ["G3-M4-1", "G3-M4-2", "G3-M4-3", "G3-M4-4"],
        "typeMix": {"single_choice": 2, "true_false": 2, "fill_blank": 2, "calculation": 1, "short_answer": 3},
    },
]

MATH_G4_SPRINTS: list[dict[str, Any]] = [
    {
        "slug": "g4-math-large-calc-sprint",
        "subject": "数学",
        "grade": 4,
        "title": "大数乘除与运算律巧算专项",
        "subtitle": "大数改写与近似数、三位数乘两位数、除数是两位数除法与乘法分配律巧算",
        "icon": "⚡",
        "timeLimitSec": 660,
        "questionCount": 10,
        "nodeKeys": ["G4-M1-1", "G4-M1-2", "G4-M1-3", "G4-M1-4"],
        "typeMix": {"calculation": 4, "single_choice": 2, "true_false": 2, "fill_blank": 2},
    },
    {
        "slug": "g4-math-angle-triangle-sprint",
        "subject": "数学",
        "grade": 4,
        "title": "角的度量与三角形几何专项",
        "subtitle": "公顷平方千米、角的度量分类、平行四边形梯形与三角形内角和看图攻坚",
        "icon": "📐",
        "timeLimitSec": 780,
        "questionCount": 10,
        "preferVisual": True,
        "nodeKeys": ["G4-M2-1", "G4-M2-2", "G4-M2-3", "G4-M2-4"],
        "typeMix": {"single_choice": 3, "true_false": 2, "fill_blank": 2, "calculation": 1, "short_answer": 2},
    },
    {
        "slug": "g4-math-decimal-word-sprint",
        "subject": "数学",
        "grade": 4,
        "title": "小数加减与行程价格应用专项",
        "subtitle": "小数点移动规律、小数加减混合运算、速度时间路程与烙饼沏茶优化策略",
        "icon": "🧩",
        "timeLimitSec": 780,
        "questionCount": 10,
        "nodeKeys": ["G4-M3-1", "G4-M3-2", "G4-M3-3", "G4-M3-4"],
        "typeMix": {"single_choice": 2, "true_false": 1, "fill_blank": 2, "calculation": 2, "short_answer": 3},
    },
    {
        "slug": "g4-math-stats-chicken-sprint",
        "subject": "数学",
        "grade": 4,
        "title": "平均数统计与鸡兔同笼压轴专项",
        "subtitle": "条形统计图、移多补少求平均数、经典鸡兔同笼与和差倍还原压轴挑战",
        "icon": "🏆",
        "timeLimitSec": 840,
        "questionCount": 10,
        "nodeKeys": ["G4-M4-1", "G4-M4-2", "G4-M4-3", "G4-M4-4"],
        "typeMix": {"single_choice": 2, "true_false": 1, "fill_blank": 2, "calculation": 2, "short_answer": 3},
    },
]

MATH_G6_SPRINTS: list[dict[str, Any]] = [
    {
        "slug": "g6-math-fraction-ratio-sprint",
        "subject": "数学",
        "grade": 6,
        "title": "分数百分数四则与解比例专项",
        "subtitle": "分数乘除混合简算、化简比、百分数折扣利率与解比例方程高频训练",
        "icon": "⚡",
        "timeLimitSec": 720,
        "questionCount": 10,
        "nodeKeys": ["G6-M1-1", "G6-M1-2", "G6-M1-3", "G6-M1-4", "G6-M3-2"],
        "typeMix": {"calculation": 4, "single_choice": 2, "true_false": 1, "fill_blank": 2, "short_answer": 1},
    },
    {
        "slug": "g6-math-circle-cylinder-sprint",
        "subject": "数学",
        "grade": 6,
        "title": "圆与圆柱圆锥立体几何专项",
        "subtitle": "位置偏角看图、圆的周长与圆环扇形面积、圆柱表面积与圆锥体积实战",
        "icon": "📐",
        "timeLimitSec": 900,
        "questionCount": 10,
        "preferVisual": True,
        "nodeKeys": ["G6-M2-1", "G6-M2-2", "G6-M2-3", "G6-M2-4"],
        "typeMix": {"single_choice": 2, "true_false": 2, "fill_blank": 2, "calculation": 2, "short_answer": 2},
    },
    {
        "slug": "g6-math-proportion-eng-sprint",
        "subject": "数学",
        "grade": 6,
        "title": "按比分配、比例尺与工程应用专项",
        "subtitle": "按比分配、正反比例判断、比例尺图上实际距离与分数合作工程问题",
        "icon": "🧩",
        "timeLimitSec": 900,
        "questionCount": 10,
        "nodeKeys": ["G6-M1-3", "G6-M3-1", "G6-M3-3", "G6-M3-4", "G6-M4-2"],
        "typeMix": {"single_choice": 2, "true_false": 2, "fill_blank": 2, "calculation": 1, "short_answer": 3},
    },
    {
        "slug": "g6-math-graduation-boss-sprint",
        "subject": "数学",
        "grade": 6,
        "title": "小升初综合压轴冲刺专项",
        "subtitle": "扇形统计图、分数工程合作、数与形规律推理、抽屉原理与行程压轴大考",
        "icon": "🏆",
        "timeLimitSec": 960,
        "questionCount": 12,
        "nodeKeys": [
            "G6-M1-4", "G6-M2-3", "G6-M2-4", "G6-M3-2",
            "G6-M4-1", "G6-M4-2", "G6-M4-3", "G6-M4-4",
        ],
        "typeMix": {"single_choice": 3, "true_false": 2, "fill_blank": 2, "calculation": 2, "short_answer": 3},
    },
]


# ==============================================================================
# 3. 确定性参数化题目生成器（G3 / G4 / G6 共 48 个节点 × 6 题）
# ==============================================================================

def _build_g3_node_pool(node_key: str, s: int) -> list[dict[str, Any]]:
    a = 2 + (s % 7)          # 2..8
    b = 3 + ((s * 3) % 6)    # 3..8
    c = 4 + ((s * 5) % 5)    # 4..8

    if node_key == "G3-M1-1":
        n1 = 230 + a * 15 + b
        n2 = 140 + c * 12 + a
        s_val = n1 + n2
        m1 = 600 + a * 20 + b
        m2 = 240 + c * 15 + a
        d_val = m1 - m2
        return [
            _text_q(f"bi:{node_key}:calc:{s}", node_key, "basic", "calculation",
                    f"直接写出得数：{n1} + {n2} =", str(s_val), f"{n1} + {n2} = {s_val}。"),
            _choice_q(f"bi:{node_key}:sc:{s}", node_key, "basic",
                      f"验算减法算式 {m1} - {m2} = {d_val} 时，下面方法不正确的是（ ）。",
                      f"{m1} + {d_val}", [f"{d_val} + {m2}", f"{m1} - {d_val}", f"{m2} + {d_val}"],
                      "减法可以用“差+减数=被减数”或“被减数-差=减数”验算，不能用被减数加差。", s),
            _tf_q(f"bi:{node_key}:tf:{s}", node_key, "basic",
                  "判断：三位数加三位数，和可能是三位数，也可能是四位数。", True, "例如 100+200=300（三位数），600+500=1100（四位数）。"),
            _text_q(f"bi:{node_key}:fb:{s}", node_key, "medium", "fill_blank",
                    f"填空：比 {n1} 多 {n2} 的数是（ ）。", str(s_val), f"{n1} + {n2} = {s_val}。"),
            _text_q(f"bi:{node_key}:calc2:{s}", node_key, "medium", "calculation",
                    f"计算：{m1} - {m2} =", str(d_val), f"列竖式对齐数位，不够减向前一位借 1，得 {d_val}。"),
            _text_q(f"bi:{node_key}:sa:{s}", node_key, "hard", "short_answer",
                    f"解决问题：科技馆上午迎来 {n1} 名游客，下午迎来 {n2} 名游客，全天一共迎来多少名游客？（只填数字）",
                    str(s_val), f"{n1} + {n2} = {s_val}（名）。", [f"{s_val}名"]),
        ]

    if node_key == "G3-M1-2":
        m1 = 100 * a + 10 * b + c
        k1 = 3 + (s % 4)
        p1 = m1 * k1
        m2 = 200 + a * 10
        p2 = m2 * b
        return [
            _text_q(f"bi:{node_key}:calc:{s}", node_key, "basic", "calculation",
                    f"计算：{m2} × {b} =", str(p2), f"{m2} × {b} = {p2}。"),
            _choice_q(f"bi:{node_key}:sc:{s}", node_key, "basic",
                      f"计算 0 × {m1} + {k1} 的结果是（ ）。",
                      str(k1), ["0", str(m1 + k1), str(m1 * k1)],
                      f"0 乘任何数都得 0，0 + {k1} = {k1}。", s),
            _tf_q(f"bi:{node_key}:tf:{s}", node_key, "basic",
                  "判断：0 和任何数相乘都得 0，0 和任何数相加也得 0。", False, "0 乘任何数得 0，但 0 加任何数得原数。"),
            _text_q(f"bi:{node_key}:fb:{s}", node_key, "medium", "fill_blank",
                    f"填空：{m1} × {k1} 的积是（ ）。", str(p1), f"{m1} × {k1} = {p1}。"),
            _choice_q(f"bi:{node_key}:sc2:{s}", node_key, "medium",
                      f"算式 20{a} × 4 的积中间有（ ）个 0。",
                      "1" if a * 4 >= 10 else "1",
                      ["0", "2", "3"],
                      f"20{a} × 4 = {200 * 4 + a * 4}，十位上是 { (a * 4) // 10 }。", s + 1) if (a * 4) < 10 else
            _choice_q(f"bi:{node_key}:sc2:{s}", node_key, "medium",
                      f"算式 250 × {4} 的积的末尾有（ ）个 0。",
                      "3", ["1", "2", "4"], "250 × 4 = 1000，末尾有 3 个 0。", s + 1),
            _text_q(f"bi:{node_key}:sa:{s}", node_key, "hard", "short_answer",
                    f"解决问题：每箱牛奶有 {k1} 盒，买 {m1} 箱一共有多少盒？（只填数字）",
                    str(p1), f"{m1} × {k1} = {p1}（盒）。", [f"{p1}盒"]),
        ]

    if node_key == "G3-M1-3":
        div = 3 + (s % 6)
        q1 = 100 + a * 10 + b
        dvd1 = q1 * div
        rem = 1 + (s % (div - 1))
        dvd2 = q1 * div + rem
        return [
            _text_q(f"bi:{node_key}:calc:{s}", node_key, "basic", "calculation",
                    f"计算：{dvd1} ÷ {div} =", str(q1), f"{dvd1} ÷ {div} = {q1}。"),
            _choice_q(f"bi:{node_key}:sc:{s}", node_key, "basic",
                      f"在有余数的除法 □ ÷ {div} = {a * 10} …… △ 中，余数 △ 最大是（ ）。",
                      str(div - 1), [str(div), str(div + 1), "1"],
                      f"余数必须比除数小，除数是 {div}，余数最大是 {div - 1}。", s),
            _tf_q(f"bi:{node_key}:tf:{s}", node_key, "basic",
                  "判断：0 除以任何不是 0 的数都得 0。", True, "0 不能作除数，0 除以任何非零数都等于 0。"),
            _text_q(f"bi:{node_key}:fb:{s}", node_key, "medium", "fill_blank",
                    f"填空：一个数除以 {div}，商是 {q1}，余数是 {rem}，这个被除数是（ ）。",
                    str(dvd2), f"被除数 = 商 × 除数 + 余数 = {q1} × {div} + {rem} = {dvd2}。"),
            _choice_q(f"bi:{node_key}:sc2:{s}", node_key, "medium",
                      f"三位数 {div}0{div} ÷ {div} 的商是（ ）。",
                      "101", ["11", "100", "110"],
                      f"百位商 1，十位 0 除以 {div} 商 0 占位，个位商 1，得 101。", s + 2),
            _text_q(f"bi:{node_key}:sa:{s}", node_key, "hard", "short_answer",
                    f"解决问题：果园摘了 {dvd1} 千克苹果，平均装在 {div} 个筐里，每筐装多少千克？（只填数字）",
                    str(q1), f"{dvd1} ÷ {div} = {q1}（千克）。", [f"{q1}千克"]),
        ]

    if node_key == "G3-M1-4":
        x1 = 10 + a * 2
        y1 = 10 + b
        p1 = x1 * y1
        x2 = (a + 2) * 10
        y2 = (b + 1) * 10
        p2 = x2 * y2
        return [
            _text_q(f"bi:{node_key}:calc:{s}", node_key, "basic", "calculation",
                    f"直接写出得数：{x2} × {y2} =", str(p2), f"先把 0 前面的数相乘，再在末尾添上 2 个 0，得 {p2}。"),
            _choice_q(f"bi:{node_key}:sc:{s}", node_key, "basic",
                      f"计算 {x1} × {y1} 时，用第二个因数十位上的“1”去乘 {x1}，表示的是（ ）。",
                      f"{x1 * 10}", [f"{x1}", f"{x1 * 100}", f"{y1 * 10}"],
                      f"十位上的 1 代表 1 个十，乘 {x1} 得 {x1 * 10}。", s),
            _tf_q(f"bi:{node_key}:tf:{s}", node_key, "basic",
                  "判断：两位数乘两位数，积可能是三位数，也可能是四位数。", True, "最小 10×10=100（三位数），最大 99×99=9801（四位数）。"),
            _text_q(f"bi:{node_key}:fb:{s}", node_key, "medium", "fill_blank",
                    f"填空：{x1} × {y1} =（ ）。", str(p1), f"{x1} × {y1} = {p1}。"),
            _text_q(f"bi:{node_key}:calc2:{s}", node_key, "medium", "calculation",
                    f"计算：25 × {4 * a} =", str(100 * a), f"25 × 4 × {a} = 100 × {a} = {100 * a}。"),
            _text_q(f"bi:{node_key}:sa:{s}", node_key, "hard", "short_answer",
                    f"解决问题：礼堂有 {x1} 排座位，每排能坐 {y1} 人，一共能坐多少人？（只填数字）",
                    str(p1), f"{x1} × {y1} = {p1}（人）。", [f"{p1}人"]),
        ]

    if node_key == "G3-M2-1":
        cm_val = a + 3
        mm_val = cm_val * 10
        km_val = b
        m_val = km_val * 1000
        dm_val = c * 10
        return [
            _text_q(f"bi:{node_key}:fb:{s}", node_key, "basic", "fill_blank",
                    f"填空：{cm_val} 厘米 =（ ）毫米。", str(mm_val), f"1 厘米 = 10 毫米，{cm_val} 厘米 = {mm_val} 毫米。"),
            _choice_q(f"bi:{node_key}:sc:{s}", node_key, "basic",
                      "银行卡或身份证的厚度大约是 1（ ）。",
                      "毫米", ["厘米", "分米", "千米"], "身份证厚度约 1 毫米。", s),
            _tf_q(f"bi:{node_key}:tf:{s}", node_key, "basic",
                  "判断：1 千米又叫 1 公里，等于 1000 米。", True, "1 km = 1000 m。"),
            _text_q(f"bi:{node_key}:calc:{s}", node_key, "medium", "calculation",
                    f"单位换算计算：{km_val} 千米 + {a * 100} 米 =（ ）米。",
                    str(m_val + a * 100), f"{km_val} 千米 = {m_val} 米，相加得 {m_val + a * 100} 米。"),
            _choice_q(f"bi:{node_key}:sc2:{s}", node_key, "medium",
                      f"把 {dm_val} 分米换算成米，结果是（ ）米。",
                      str(c), [str(c * 10), str(c * 100), "1"],
                      f"10 分米 = 1 米，{dm_val} 分米 = {c} 米。", s + 1),
            _text_q(f"bi:{node_key}:sa:{s}", node_key, "hard", "short_answer",
                    f"解决问题：一根木料长 {a} 米，锯掉 {b} 分米后，还剩多少分米？（只填数字）",
                    str(a * 10 - b), f"{a} 米 = {a * 10} 分米，{a * 10} - {b} = {a * 10 - b}（分米）。", [f"{a * 10 - b}分米"]),
        ]

    if node_key == "G3-M2-2":
        t_val = a + 1
        kg_val = t_val * 1000
        g_val = b * 1000
        return [
            _text_q(f"bi:{node_key}:fb:{s}", node_key, "basic", "fill_blank",
                    f"填空：{t_val} 吨 =（ ）千克。", str(kg_val), f"1 吨 = 1000 千克，{t_val} 吨 = {kg_val} 千克。"),
            _choice_q(f"bi:{node_key}:sc:{s}", node_key, "basic",
                      "计量大象、卡车载重等较重物品的质量，通常用（ ）作单位。",
                      "吨", ["克", "千克", "千米"], "大宗或较重物体用“吨”作质量单位。", s),
            _tf_q(f"bi:{node_key}:tf:{s}", node_key, "basic",
                  "判断：1 吨铁比 1000 千克棉花重。", False, "1 吨 = 1000 千克，两者一样重。"),
            _text_q(f"bi:{node_key}:calc:{s}", node_key, "medium", "calculation",
                    f"单位换算计算：{g_val} 克 =（ ）千克。", str(b), f"1000 克 = 1 千克，{g_val} 克 = {b} 千克。"),
            _choice_q(f"bi:{node_key}:sc2:{s}", node_key, "medium",
                      f"1 袋水泥重 50 千克，（ ）袋这样的水泥重 1 吨。",
                      "20", ["10", "50", "200"], "1000 ÷ 50 = 20（袋）。", s + 2),
            _text_q(f"bi:{node_key}:sa:{s}", node_key, "hard", "short_answer",
                    f"解决问题：一辆货车载重 {t_val} 吨，已经装了 {kg_val - c * 100} 千克货物，最多还能装多少千克货物？（只填数字）",
                    str(c * 100), f"{t_val} 吨 = {kg_val} 千克，{kg_val} - {kg_val - c * 100} = {c * 100}（千克）。", [f"{c * 100}千克"]),
        ]

    if node_key == "G3-M2-3":
        w_len = a + 3
        h_len = b
        perim = 2 * (w_len + h_len)
        sq_side = c + 2
        sq_perim = 4 * sq_side
        fig = _rect_grid_figure(w_len, h_len)
        return [
            _text_q(f"bi:{node_key}:calc:{s}", node_key, "basic", "calculation",
                    f"看图计算：方格纸中长方形的长是 {w_len} cm、宽是 {h_len} cm，它的周长是多少 cm？（只填数字）",
                    str(perim), f"周长 = ({w_len} + {h_len}) × 2 = {perim}（cm）。", [f"{perim}cm"], figure=fig),
            _choice_q(f"bi:{node_key}:sc:{s}", node_key, "basic",
                      f"一个正方形的边长是 {sq_side} 厘米，它的周长是（ ）厘米。",
                      str(sq_perim), [str(sq_side * sq_side), str(sq_side * 2), str(sq_perim + 4)],
                      f"正方形周长 = 边长 × 4 = {sq_side} × 4 = {sq_perim}（厘米）。", s),
            _tf_q(f"bi:{node_key}:tf:{s}", node_key, "basic",
                  "判断：周长相等的两个长方形，它们的长和宽也一定分别相等。", False, "例如长6宽2和长5宽3周长都是16，但长和宽不同。"),
            _text_q(f"bi:{node_key}:fb:{s}", node_key, "medium", "fill_blank",
                    f"填空：用一根长 {sq_perim} 厘米的铁丝围成一个最大的正方形，正方形的边长是（ ）厘米。",
                    str(sq_side), f"边长 = 周长 ÷ 4 = {sq_perim} ÷ 4 = {sq_side}（厘米）。"),
            _choice_q(f"bi:{node_key}:sc2:{s}", node_key, "medium",
                      f"把一个边长 {sq_side} cm 的正方形分成两个同样的长方形，两个长方形的周长之和比原来正方形周长（ ）。",
                      f"增加 {sq_side * 2} cm", ["不变", f"增加 {sq_side} cm", f"减少 {sq_side * 2} cm"],
                      f"剪开后多出 2 条正方形的边长，即增加 {sq_side * 2} cm。", s + 1),
            _text_q(f"bi:{node_key}:sa:{s}", node_key, "hard", "short_answer",
                    f"解决问题：一块长方形菜地长 {w_len} 米、宽 {h_len} 米，长边靠墙，其余三边围上篱笆，篱笆至少长多少米？（只填数字）",
                    str(w_len + 2 * h_len), f"长边靠墙最省篱笆：{w_len} + {h_len} × 2 = {w_len + 2 * h_len}（米）。", [f"{w_len + 2 * h_len}米"]),
        ]

    if node_key == "G3-M2-4":
        w_len = a + 2
        h_len = b
        area = w_len * h_len
        sq_side = c + 1
        sq_area = sq_side * sq_side
        fig = _rect_grid_figure(w_len, h_len, "每个小方格表示 1 平方厘米")
        return [
            _text_q(f"bi:{node_key}:calc:{s}", node_key, "basic", "calculation",
                    f"看图计算：图中长方形长 {w_len} 厘米、宽 {h_len} 厘米，面积是多少平方厘米？（只填数字）",
                    str(area), f"长方形面积 = 长 × 宽 = {w_len} × {h_len} = {area}（平方厘米）。", figure=fig),
            _choice_q(f"bi:{node_key}:sc:{s}", node_key, "basic",
                      f"边长是 {sq_side} 分米的正方形，它的面积是（ ）平方分米。",
                      str(sq_area), [str(sq_side * 4), str(sq_side * 2), str(sq_area * 10)],
                      f"正方形面积 = 边长 × 边长 = {sq_side} × {sq_side} = {sq_area}。", s),
            _tf_q(f"bi:{node_key}:tf:{s}", node_key, "basic",
                  "判断：边长 4 厘米的正方形，它的周长和面积相等。", False, "周长是 16 厘米，面积是 16 平方厘米，单位不同，不能比较大小。"),
            _text_q(f"bi:{node_key}:fb:{s}", node_key, "medium", "fill_blank",
                    f"填空：{a + 1} 平方米 =（ ）平方分米。", str((a + 1) * 100),
                    f"1 平方米 = 100 平方分米，{a + 1} 平方米 = {(a + 1) * 100} 平方分米。"),
            _choice_q(f"bi:{node_key}:sc2:{s}", node_key, "medium",
                      f"一个长方形面积是 {area} 平方厘米，长是 {w_len} 厘米，宽是（ ）厘米。",
                      str(h_len), [str(area - w_len), str(h_len * 2), str(w_len)],
                      f"宽 = 面积 ÷ 长 = {area} ÷ {w_len} = {h_len}（厘米）。", s + 2),
            _text_q(f"bi:{node_key}:sa:{s}", node_key, "hard", "short_answer",
                    f"解决问题：一间客厅长 {w_len} 米、宽 {h_len} 米，如果每平方米铺 4 块地砖，铺满客厅一共需要多少块地砖？（只填数字）",
                    str(area * 4), f"客厅面积 {w_len} × {h_len} = {area} 平方米，共需 {area} × 4 = {area * 4}（块）。", [f"{area * 4}块"]),
        ]

    if node_key == "G3-M3-1":
        res1 = a * 10 + b * c
        res2 = (a + b) * c
        return [
            _text_q(f"bi:{node_key}:calc:{s}", node_key, "basic", "calculation",
                    f"计算：{a * 10} + {b} × {c} =", str(res1), f"先算乘法 {b} × {c} = {b * c}，再加 {a * 10} 得 {res1}。"),
            _choice_q(f"bi:{node_key}:sc:{s}", node_key, "basic",
                      f"计算 ({a} + {b}) × {c} 时，第一步应该先算（ ）。",
                      f"{a} + {b}", [f"{b} × {c}", f"{a} × {c}", "从左往右随便算"],
                      "有小括号的混合运算，要先算小括号里面的。", s),
            _tf_q(f"bi:{node_key}:tf:{s}", node_key, "basic",
                  "判断：在没有括号的算式里，既有乘除法又有加减法，要先算乘除法，后算加减法。", True, "先乘除后加减是四则运算基本顺序。"),
            _text_q(f"bi:{node_key}:fb:{s}", node_key, "medium", "fill_blank",
                    f"填空：({a} + {b}) × {c} =（ ）。", str(res2), f"先算括号内 {a + b}，再乘 {c} 得 {res2}。"),
            _text_q(f"bi:{node_key}:calc2:{s}", node_key, "medium", "calculation",
                    f"计算：{c * 10} - {a * b} ÷ {a} =", str(c * 10 - b), f"先算除法 {a * b} ÷ {a} = {b}，再算 {c * 10} - {b} = {c * 10 - b}。"),
            _text_q(f"bi:{node_key}:sa:{s}", node_key, "hard", "short_answer",
                    f"解决问题：小华带了 50 元，买了 {a} 支单价 {b} 元的钢笔，还剩多少元？（只填数字）",
                    str(50 - a * b), f"50 - {a} × {b} = {50 - a * b}（元）。", [f"{50 - a * b}元"]),
        ]

    if node_key == "G3-M3-2":
        unit_val = a + 3
        cnt1 = 3
        tot1 = unit_val * cnt1
        cnt2 = b + 2
        tot2 = unit_val * cnt2
        return [
            _text_q(f"bi:{node_key}:sa:{s}", node_key, "medium", "short_answer",
                    f"解决问题：买 {cnt1} 本笔记本花了 {tot1} 元。照这样计算，买 {cnt2} 本同样的笔记本需要多少元？（只填数字）",
                    str(tot2), f"先求 1 本的单价：{tot1} ÷ {cnt1} = {unit_val}（元），再算 {cnt2} 本：{unit_val} × {cnt2} = {tot2}（元）。", [f"{tot2}元"]),
            _choice_q(f"bi:{node_key}:sc:{s}", node_key, "basic",
                      f"果园有桃树 {a * 10} 棵，梨树比桃树的 2 倍还多 {b} 棵，求梨树有多少棵，列式正确的是（ ）。",
                      f"{a * 10} × 2 + {b}", [f"{a * 10} × 2 - {b}", f"({a * 10} + {b}) × 2", f"{a * 10} ÷ 2 + {b}"],
                      f"桃树的 2 倍是 {a * 10} × 2，还多 {b} 棵再加 {b}。", s),
            _tf_q(f"bi:{node_key}:tf:{s}", node_key, "basic",
                  "判断：解决“照这样计算”的归一问题时，通常要先求出“单一量”（每份数）。", True, "先用除法求出 1 份是多少，再求多份。"),
            _text_q(f"bi:{node_key}:fb:{s}", node_key, "medium", "fill_blank",
                    f"填空：红花有 {a + 2} 朵，黄花的朵数是红花的 3 倍，红花和黄花一共有（ ）朵。",
                    str((a + 2) * 4), f"黄花有 {(a + 2) * 3} 朵，一共 {(a + 2)} + {(a + 2) * 3} = {(a + 2) * 4} 朵。"),
            _text_q(f"bi:{node_key}:calc:{s}", node_key, "basic", "calculation",
                    f"计算：{tot1} ÷ {cnt1} × {cnt2} =", str(tot2), f"{tot1} ÷ {cnt1} = {unit_val}，{unit_val} × {cnt2} = {tot2}。"),
            _choice_q(f"bi:{node_key}:sc2:{s}", node_key, "hard",
                      f"工人把一批货物装箱，如果每箱装 6 个，正好装 {a + 2} 箱；如果改用每箱装 {a + 2} 个的大箱子，需要（ ）个大箱子。",
                      "6", [str(a + 2), "12", str((a + 2) * 6)],
                      f"总个数是 6 × {a + 2}，除以每大箱 {a + 2} 个，正好需要 6 个大箱子。", s + 1),
        ]

    if node_key == "G3-M3-3":
        den = 5 + (s % 4)   # 5..8
        n1 = 1 + (s % 2)
        n2 = 2
        s_num = n1 + n2
        rem_num = den - s_num
        return [
            _text_q(f"bi:{node_key}:calc:{s}", node_key, "basic", "calculation",
                    f"计算（写成 a/b 形式）：{n1}/{den} + {n2}/{den} =",
                    f"{s_num}/{den}", f"同分母分数相加，分母不变，分子相加：({n1}+{n2})/{den} = {s_num}/{den}。"),
            _choice_q(f"bi:{node_key}:sc:{s}", node_key, "basic",
                      f"比较分数大小：1/{a + 1} ○ 1/{a + 3}。",
                      ">", ["<", "=", "无法比较"],
                      "分子都是 1 时，平均分的份数越少，每一份反而越大，即分母小的分数大。", s),
            _tf_q(f"bi:{node_key}:tf:{s}", node_key, "basic",
                  "判断：把一个蛋糕分成 4 份，每份一定是它的 1/4。", False, "必须强调“平均分”，没有平均分就不能用 1/4 表示。"),
            _text_q(f"bi:{node_key}:fb:{s}", node_key, "medium", "fill_blank",
                    f"填空：1 - {s_num}/{den} =（ ）。（用 a/b 形式表示）",
                    f"{rem_num}/{den}", f"把 1 看作 {den}/{den}，{den}/{den} - {s_num}/{den} = {rem_num}/{den}。"),
            _choice_q(f"bi:{node_key}:sc2:{s}", node_key, "medium",
                      f"把 {den * 2} 个苹果平均分成 {den} 份，每份有（ ）个苹果。",
                      "2", ["1", str(den), str(den * 2)],
                      f"{den * 2} ÷ {den} = 2（个）。", s + 2),
            _text_q(f"bi:{node_key}:sa:{s}", node_key, "hard", "short_answer",
                    f"解决问题：一张彩纸，折星星用了它的 {n1}/{den}，折千纸鹤用了它的 {n2}/{den}，一共用了这张纸的几分之几？（用 a/b 表示）",
                    f"{s_num}/{den}", f"{n1}/{den} + {n2}/{den} = {s_num}/{den}。"),
        ]

    if node_key == "G3-M3-4":
        d1 = _d(f"{a}.{b}")
        d2 = _d(f"1.{c % 5 + 1}")
        sum_d = _fmt(d1 + d2)
        diff_d = _fmt(d1 - d2)
        return [
            _text_q(f"bi:{node_key}:calc:{s}", node_key, "basic", "calculation",
                    f"直接写出得数：{_fmt(d1)} + {_fmt(d2)} =", sum_d, f"小数点对齐相加：{_fmt(d1)} + {_fmt(d2)} = {sum_d}。"),
            _choice_q(f"bi:{node_key}:sc:{s}", node_key, "basic",
                      f"{a} 元 {b} 角写成小数是（ ）元。",
                      f"{a}.{b}", [f"{a}.0{b}", f"0.{a}{b}", f"{a}{b}.0"],
                      f"几元是整数部分，几角是十分位，即 {a}.{b} 元。", s),
            _tf_q(f"bi:{node_key}:tf:{s}", node_key, "basic",
                  "判断：所有的小数都比 1 小。", False, "例如 1.5、3.8 都是小数，但它们都比 1 大。"),
            _text_q(f"bi:{node_key}:fb:{s}", node_key, "medium", "fill_blank",
                    f"填空：{_fmt(d1)} - {_fmt(d2)} =（ ）。", diff_d, f"小数点对齐相减得 {diff_d}。"),
            _choice_q(f"bi:{node_key}:sc2:{s}", node_key, "medium",
                      f"把 {a} 分米写成以“米”为单位的小数是（ ）米。",
                      f"0.{a}", [f"{a}.0", f"0.0{a}", f"1.{a}"],
                      f"1 分米 = 0.1 米，{a} 分米 = 0.{a} 米。", s + 1),
            _text_q(f"bi:{node_key}:sa:{s}", node_key, "hard", "short_answer",
                    f"解决问题：一支铅笔 {_fmt(d2)} 元，一本练习本 {_fmt(d1)} 元，买这两样一共需要多少元？（只填数字）",
                    sum_d, f"{_fmt(d2)} + {_fmt(d1)} = {sum_d}（元）。", [f"{sum_d}元"]),
        ]

    if node_key == "G3-M4-1":
        mins = a
        secs = mins * 60
        dur = 25 + (s % 20)
        end_m = 10 + dur
        return [
            _text_q(f"bi:{node_key}:fb:{s}", node_key, "basic", "fill_blank",
                    f"填空：{mins} 分 =（ ）秒。", str(secs), f"1 分 = 60 秒，{mins} 分 = {secs} 秒。"),
            _choice_q(f"bi:{node_key}:sc:{s}", node_key, "basic",
                      "秒针在钟面上走 1 小格是 1 秒，走 1 圈是（ ）秒，也就是 1 分钟。",
                      "60", ["12", "30", "100"], "钟面一圈 60 小格，秒针走一圈是 60 秒 = 1 分。", s),
            _tf_q(f"bi:{node_key}:tf:{s}", node_key, "basic",
                  "判断：分针从数字 12 走到数字 4，经过了 4 分钟。", False, "分针走 1 大格是 5 分钟，走到 4 是 4×5=20 分钟。"),
            _text_q(f"bi:{node_key}:calc:{s}", node_key, "medium", "calculation",
                    f"单位换算：1 时 {b * 5} 分 =（ ）分。", str(60 + b * 5), f"1 时 = 60 分，60 + {b * 5} = {60 + b * 5} 分。"),
            _text_q(f"bi:{node_key}:sa:{s}", node_key, "hard", "short_answer",
                    f"解决问题：早读课从 8:10 开始，8:{end_m} 结束，早读课一共持续了多少分钟？（只填数字）",
                    str(dur), f"8:{end_m} - 8:10 = {dur}（分钟）。", [f"{dur}分钟", f"{dur}分"]),
            _choice_q(f"bi:{node_key}:sc2:{s}", node_key, "medium",
                      "百米赛跑中，小明用了 15 秒，小亮用了 17 秒，跑得更快的是（ ）。",
                      "小明", ["小亮", "一样快", "无法判断"], "路程相同时，用时越短跑得越快。", s + 2),
        ]

    if node_key == "G3-M4-2":
        pm_hr = 2 + (s % 6)   # 下午 2..7 时
        hr24 = pm_hr + 12
        leap_yr = 2024 if s % 2 == 0 else 2028
        return [
            _text_q(f"bi:{node_key}:fb:{s}", node_key, "basic", "fill_blank",
                    f"填空：下午 {pm_hr} 时用 24 时计时法表示是（ ）时。（只填数字）",
                    str(hr24), f"下午时间加 12：{pm_hr} + 12 = {hr24} 时。", [f"{hr24}:00", f"{hr24}时"]),
            _choice_q(f"bi:{node_key}:sc:{s}", node_key, "basic",
                      "一年有 12 个月，其中有 31 天的大月共有（ ）个。",
                      "7", ["4", "5", "6"], "一三五七八十腊（12月），三十一天永不差，共 7 个大月。", s),
            _tf_q(f"bi:{node_key}:tf:{s}", node_key, "basic",
                  f"判断：{leap_yr} 年是闰年，全年共有 366 天。", True, f"{leap_yr} ÷ 4 能整除，是闰年，2 月有 29 天，全年 366 天。"),
            _text_q(f"bi:{node_key}:calc:{s}", node_key, "medium", "calculation",
                    f"计算：图书馆每天 9:00 开馆，{hr24}:00 闭馆，全天开放（ ）小时。",
                    str(hr24 - 9), f"{hr24} - 9 = {hr24 - 9}（小时）。"),
            _choice_q(f"bi:{node_key}:sc2:{s}", node_key, "medium",
                      "儿童节（6月1日）的前一天是（ ）。",
                      "5月31日", ["5月30日", "6月30日", "5月29日"], "5 月是大月，有 31 天，所以 6 月 1 日前一天是 5 月 31 日。", s + 1),
            _text_q(f"bi:{node_key}:sa:{s}", node_key, "hard", "short_answer",
                    f"解决问题：一个星期有 7 天，今年 5 月份有 31 天，最多有几个星期还余几天？请填写余下的天数（只填数字）：",
                    "3", "31 ÷ 7 = 4（个星期）…… 3（天），余下 3 天。"),
        ]

    if node_key == "G3-M4-3":
        boys_a, girls_a = 12 + a, 10 + b
        boys_b, girls_b = 15 + c, 11 + a
        tot_a = boys_a + girls_a
        tot_boys = boys_a + boys_b
        return [
            _text_q(f"bi:{node_key}:calc:{s}", node_key, "basic", "calculation",
                    f"统计表计算：三(1)班参加绘画组男生 {boys_a} 人、女生 {girls_a} 人，三(1)班共有多少人参加绘画组？（只填数字）",
                    str(tot_a), f"{boys_a} + {girls_a} = {tot_a}（人）。"),
            _choice_q(f"bi:{node_key}:sc:{s}", node_key, "basic",
                      "把两个或多个有联系的单式统计表合成一个统计表，便于对比分析，这种表叫（ ）。",
                      "复式统计表", ["条形图", "签到表", "时间表"], "合并后的统计表称为复式统计表。", s),
            _tf_q(f"bi:{node_key}:tf:{s}", node_key, "basic",
                  "判断：复式统计表左上角的表头通常分成三栏，分别表示横栏类别、纵栏类别和数据名称。", True, "表头三栏清晰区分行列维度与统计数值。"),
            _text_q(f"bi:{node_key}:fb:{s}", node_key, "medium", "fill_blank",
                    f"填空：复式统计表中，一班男生 {boys_a} 人，二班男生 {boys_b} 人，两个班男生合计（ ）人。",
                    str(tot_boys), f"{boys_a} + {boys_b} = {tot_boys}（人）。"),
            _choice_q(f"bi:{node_key}:sc2:{s}", node_key, "medium",
                      f"在统计表中，二班男生有 {boys_b} 人，女生有 {girls_b} 人，男生比女生多（ ）人。",
                      str(boys_b - girls_b), [str(boys_b + girls_b), str(girls_b), "2"],
                      f"{boys_b} - {girls_b} = {boys_b - girls_b}（人）。", s + 2),
            _text_q(f"bi:{node_key}:sa:{s}", node_key, "hard", "short_answer",
                    f"解决问题：阅读统计表中，一班共借书 {tot_a} 本，二班共借书 {boys_b + girls_b} 本，两个班一共借书多少本？（只填数字）",
                    str(tot_a + boys_b + girls_b), f"{tot_a} + {boys_b + girls_b} = {tot_a + boys_b + girls_b}（本）。", [f"{tot_a + boys_b + girls_b}本"]),
        ]

    # G3-M4-4 集合重叠问题（韦恩图）
    grp_a = 15 + a
    grp_b = 12 + b
    both = 4 + (s % 4)
    total = grp_a + grp_b - both
    only_a = grp_a - both
    return [
        _text_q(f"bi:{node_key}:calc:{s}", node_key, "basic", "calculation",
                f"计算：{grp_a} + {grp_b} - {both} =", str(total), f"{grp_a} + {grp_b} - {both} = {total}。"),
        _choice_q(f"bi:{node_key}:sc:{s}", node_key, "basic",
                  "在韦恩图（集合圈）中，两个圈重叠的中间部分表示（ ）。",
                  "两项都参加的人", ["只参加第一项的人", "两项都没参加的人", "总人数"],
                  "重叠区域代表同时属于两个集合的元素。", s),
        _tf_q(f"bi:{node_key}:tf:{s}", node_key, "basic",
              "判断：计算两个有重叠集合的总人数时，直接把两个集合的人数相加即可。", False, "重叠部分被加了两次，必须减去一次重叠人数。"),
        _text_q(f"bi:{node_key}:fb:{s}", node_key, "medium", "fill_blank",
                f"填空：参加跳绳的有 {grp_a} 人，两项都参加的有 {both} 人，只参加跳绳的有（ ）人。",
                str(only_a), f"{grp_a} - {both} = {only_a}（人）。"),
        _choice_q(f"bi:{node_key}:sc2:{s}", node_key, "medium",
                  f"两根长都是 20 厘米的木条钉在一起，中间重叠部分长 {a} 厘米，钉好后的木条总长（ ）厘米。",
                  str(40 - a), ["40", str(40 + a), str(20 - a)],
                  f"总长 = 两根长度之和 - 重叠长度 = 40 - {a} = {40 - a}（厘米）。", s + 1),
        _text_q(f"bi:{node_key}:sa:{s}", node_key, "hard", "short_answer",
                f"解决问题：三(2)班参加合唱队的有 {grp_a} 人，参加舞蹈队的有 {grp_b} 人，两队都参加的有 {both} 人，参加合唱和舞蹈的一共有多少人？（只填数字）",
                str(total), f"容斥原理：{grp_a} + {grp_b} - {both} = {total}（人）。", [f"{total}人"]),
    ]


def _build_g4_node_pool(node_key: str, s: int) -> list[dict[str, Any]]:
    a = 2 + (s % 7)          # 2..8
    b = 3 + ((s * 3) % 6)    # 3..8
    c = 4 + ((s * 5) % 5)    # 4..8

    if node_key == "G4-M1-1":
        wan_num = (a * 10 + b) * 10000
        round_src = a * 10000 + 4000 + b * 100
        return [
            _text_q(f"bi:{node_key}:fb:{s}", node_key, "basic", "fill_blank",
                    f"填空：把 {wan_num} 改写成用“万”作单位的数是（ ）万。（只填数字）",
                    str(a * 10 + b), f"去掉末尾 4 个 0，加上“万”字，得 {a * 10 + b} 万。", [f"{a * 10 + b}万"]),
            _choice_q(f"bi:{node_key}:sc:{s}", node_key, "basic",
                      "在数位顺序表中，从右边起第九位是（ ）。",
                      "亿位", ["千万位", "百万位", "十亿位"], "个、十、百、千、万、十万、百万、千万、亿，第九位是亿位。", s),
            _tf_q(f"bi:{node_key}:tf:{s}", node_key, "basic",
                  "判断：每相邻两个计数单位之间的进率都是 10。", True, "这是十进制计数法的基本特征。"),
            _text_q(f"bi:{node_key}:calc:{s}", node_key, "medium", "calculation",
                    f"用“四舍五入”法省略万位后面的尾数：{round_src} ≈（ ）万。（只填数字）",
                    str(a), f"千位上是 4，小于 5 直接舍去，约等于 {a} 万。", [f"{a}万"]),
            _choice_q(f"bi:{node_key}:sc2:{s}", node_key, "medium",
                      f"由 {a} 个千万和 {b} 个百组成的数是（ ）。",
                      str(a * 10000000 + b * 100),
                      [str(a * 1000000 + b * 100), str(a * 10000000 + b * 10), str(a * 100000 + b * 100)],
                      f"千万位是 {a}，百位是 {b}，其余数位补 0。", s + 1),
            _text_q(f"bi:{node_key}:sa:{s}", node_key, "hard", "short_answer",
                    f"解决问题：一个数“四舍五入”到万位约是 {a + 2} 万，这个数最大是多少？（只填数字）",
                    str((a + 2) * 10000 + 4999),
                    f"“四舍”时原数最大，千位填 4，百十个位填 9，即 {(a + 2) * 10000 + 4999}。"),
        ]

    if node_key == "G4-M1-2":
        m1 = 120 + a * 5
        m2 = 10 + b
        p1 = m1 * m2
        base_p = 360
        k_mul = a
        return [
            _text_q(f"bi:{node_key}:calc:{s}", node_key, "basic", "calculation",
                    f"计算：{m1} × {m2} =", str(p1), f"{m1} × {m2} = {p1}。"),
            _choice_q(f"bi:{node_key}:sc:{s}", node_key, "basic",
                      f"已知 A × B = {base_p}，如果 A 不变，B 乘 {k_mul}，那么积变成（ ）。",
                      str(base_p * k_mul), [str(base_p), str(base_p // 2), str(base_p + k_mul)],
                      f"一个因数不变，另一个因数乘 {k_mul}，积也乘 {k_mul}。", s),
            _tf_q(f"bi:{node_key}:tf:{s}", node_key, "basic",
                  "判断：三位数乘两位数，积一定是五位数。", False, "例如 100 × 10 = 1000，积是四位数。"),
            _text_q(f"bi:{node_key}:fb:{s}", node_key, "medium", "fill_blank",
                    f"填空：{100 + a} × {b * 10} =（ ）。", str((100 + a) * b * 10),
                    f"先算 {100 + a} × {b} = {(100 + a) * b}，末尾再添 1 个 0。"),
            _choice_q(f"bi:{node_key}:sc2:{s}", node_key, "medium",
                      "两个因数相乘，一个因数乘 4，另一个因数除以 4，积（ ）。",
                      "不变", ["乘 16", "除以 16", "乘 4"], "一个乘 4、一个除以 4，互相抵消，积不变。", s + 2),
            _text_q(f"bi:{node_key}:sa:{s}", node_key, "hard", "short_answer",
                    f"解决问题：一列火车每小时行驶 {m1} 千米，行驶 {m2} 小时一共行驶多少千米？（只填数字）",
                    str(p1), f"{m1} × {m2} = {p1}（千米）。", [f"{p1}千米"]),
        ]

    if node_key == "G4-M1-3":
        div = 10 + a * 2
        q_val = b + 4
        dvd = div * q_val
        return [
            _text_q(f"bi:{node_key}:calc:{s}", node_key, "basic", "calculation",
                    f"计算：{dvd} ÷ {div} =", str(q_val), f"{dvd} ÷ {div} = {q_val}。"),
            _choice_q(f"bi:{node_key}:sc:{s}", node_key, "basic",
                      f"根据商不变的规律，{dvd * 10} ÷ {div * 10} 的商是（ ）。",
                      str(q_val), [str(q_val * 10), str(q_val * 100), "1"],
                      "被除数和除数同时除以 10，商不变。", s),
            _tf_q(f"bi:{node_key}:tf:{s}", node_key, "basic",
                  "判断：被除数和除数同时乘或除以相同的数（0 除外），商不变。", True, "这是商不变的性质。"),
            _text_q(f"bi:{node_key}:fb:{s}", node_key, "medium", "fill_blank",
                    f"填空：要使 □45 ÷ 45 的商是两位数，□ 里最小填（ ）。",
                    "4", "被除数前两位 □4 ≥ 45 时商是两位数，由于个位是4<5，□4≥45 需 □≥5；等等：□45 前两位是 □4，要使 □4 ≥ 45，□ 最小填 5。") if False else
            _text_q(f"bi:{node_key}:fb:{s}", node_key, "medium", "fill_blank",
                    "填空：要使 □56 ÷ 45 的商是两位数，□ 里最小填（ ）。",
                    "4", "被除数前两位 □5 ≥ 45 时商是两位数，所以 □ 里最小填 4。"),
            _choice_q(f"bi:{node_key}:sc2:{s}", node_key, "hard",
                      "已知 70 ÷ 30 = 2 …… 10，那么 700 ÷ 300 的商和余数分别是（ ）。",
                      "商 2，余 100", ["商 2，余 10", "商 20，余 100", "商 20，余 10"],
                      "被除数和除数同时乘 10，商不变仍是 2，但余数也要乘 10 变成 100。", s + 1),
            _text_q(f"bi:{node_key}:sa:{s}", node_key, "hard", "short_answer",
                    f"解决问题：学校买来 {dvd} 本图书，平均分给 {div} 个班级，每个班级分到多少本？（只填数字）",
                    str(q_val), f"{dvd} ÷ {div} = {q_val}（本）。", [f"{q_val}本"]),
        ]

    if node_key == "G4-M1-4":
        k = a + 3
        p1 = 64 + (s % 10)
        p2 = 100 - p1
        ans1 = k * 100
        ans2 = 125 * 8 * b
        return [
            _text_q(f"bi:{node_key}:calc:{s}", node_key, "basic", "calculation",
                    f"简便计算：{k} × {p1} + {k} × {p2} =", str(ans1),
                    f"运用乘法分配律：{k} × ({p1} + {p2}) = {k} × 100 = {ans1}。"),
            _choice_q(f"bi:{node_key}:sc:{s}", node_key, "basic",
                      "算式 25 × 13 × 4 = 25 × 4 × 13 运用了（ ）。",
                      "乘法交换律", ["乘法分配律", "加法交换律", "减法性质"],
                      "交换了 13 和 4 的位置，使 25 和 4 先相乘，运用了乘法交换律。", s),
            _tf_q(f"bi:{node_key}:tf:{s}", node_key, "basic",
                  "判断：在既有小括号又有中括号的算式里，要先算小括号里面的，再算中括号里面的。", True, "括号优先级：先小括号，再中括号，最后括号外。"),
            _text_q(f"bi:{node_key}:fb:{s}", node_key, "medium", "fill_blank",
                    f"填空：125 × {b} × 8 =（ ）。", str(ans2), f"125 × 8 × {b} = 1000 × {b} = {ans2}。"),
            _text_q(f"bi:{node_key}:calc2:{s}", node_key, "medium", "calculation",
                    f"计算：300 - {120 + a} - {80 - a} =", "100",
                    f"连减性质：300 - ({120 + a} + {80 - a}) = 300 - 200 = 100。"),
            _text_q(f"bi:{node_key}:sa:{s}", node_key, "hard", "short_answer",
                    f"解决问题：运动服上衣每件 {p1} 元，裤子每条 {p2} 元，买 {k} 套这样的运动服一共需要多少元？（只填数字）",
                    str(ans1), f"({p1} + {p2}) × {k} = 100 × {k} = {ans1}（元）。", [f"{ans1}元"]),
        ]

    if node_key == "G4-M2-1":
        ha = a + 2
        sqm = ha * 10000
        sqkm = b
        ha_from_km = sqkm * 100
        return [
            _text_q(f"bi:{node_key}:fb:{s}", node_key, "basic", "fill_blank",
                    f"填空：{ha} 公顷 =（ ）平方米。", str(sqm), f"1 公顷 = 10000 平方米，{ha} 公顷 = {sqm} 平方米。"),
            _choice_q(f"bi:{node_key}:sc:{s}", node_key, "basic",
                      "边长是 100 米的正方形土地，它的面积是 1（ ）。",
                      "公顷", ["平方千米", "平方米", "平方分米"], "100 × 100 = 10000 平方米 = 1 公顷。", s),
            _tf_q(f"bi:{node_key}:tf:{s}", node_key, "basic",
                  "判断：1 平方千米等于 100 公顷，也等于 1000000 平方米。", True, "1 km² = 100 hm² = 1000000 m²。"),
            _text_q(f"bi:{node_key}:calc:{s}", node_key, "medium", "calculation",
                    f"单位换算：{sqkm} 平方千米 =（ ）公顷。", str(ha_from_km), f"{sqkm} × 100 = {ha_from_km} 公顷。"),
            _choice_q(f"bi:{node_key}:sc2:{s}", node_key, "medium",
                      "某小学校园的占地面积大约是 2（ ）。",
                      "公顷", ["平方千米", "平方米", "平方厘米"], "学校占地面积通常在几公顷左右。", s + 1),
            _text_q(f"bi:{node_key}:sa:{s}", node_key, "hard", "short_answer",
                    f"解决问题：一块长方形麦田长 500 米、宽 {a * 20} 米，它的面积是多少公顷？（只填数字）",
                    str((500 * a * 20) // 10000),
                    f"500 × {a * 20} = {500 * a * 20} 平方米 = {(500 * a * 20) // 10000} 公顷。"),
        ]

    if node_key == "G4-M2-2":
        ang1 = 30 + a * 5
        comp = 90 - ang1
        supp = 180 - ang1
        return [
            _text_q(f"bi:{node_key}:calc:{s}", node_key, "basic", "calculation",
                    f"已知 ∠1 与 ∠2 组成一个平角，∠1 = {ang1}°，则 ∠2 =（ ）°。（只填数字）",
                    str(supp), f"平角是 180°，180° - {ang1}° = {supp}°。", [f"{supp}°", f"{supp}度"]),
            _choice_q(f"bi:{node_key}:sc:{s}", node_key, "basic",
                      "1 个周角等于（ ）个平角，也等于 4 个直角。",
                      "2", ["1", "3", "4"], "周角 360°，平角 180°，360° ÷ 180° = 2。", s),
            _tf_q(f"bi:{node_key}:tf:{s}", node_key, "basic",
                  "判断：用放大 5 倍的放大镜看一个 30° 的角，看到的角是 150°。", False, "放大镜只放大边的长短视觉，不改变角的张口度数，仍是 30°。"),
            _text_q(f"bi:{node_key}:fb:{s}", node_key, "medium", "fill_blank",
                    f"填空：直角三角形中一个锐角是 {ang1}°，另一个锐角是（ ）°。（只填数字）",
                    str(comp), f"90° - {ang1}° = {comp}°。", [f"{comp}°", f"{comp}度"]),
            _choice_q(f"bi:{node_key}:sc2:{s}", node_key, "medium",
                      "大于 90° 而小于 180° 的角叫做（ ）。",
                      "钝角", ["锐角", "平角", "周角"], "钝角的范围是 90° < 钝角 < 180°。", s + 2),
            _text_q(f"bi:{node_key}:sa:{s}", node_key, "hard", "short_answer",
                    "解决问题：用一副三角尺（含 30°、45°、60°、90°）拼出一个最大的钝角，这个钝角是多少度？（只填数字）",
                    "150", "90° + 60° = 150°（90°+90°=180°是平角不是钝角）。", ["150°", "150度"]),
        ]

    if node_key == "G4-M2-3":
        s1 = a + 4
        s2 = b + 2
        perim = 2 * (s1 + s2)
        top_w, bot_w, leg_w = a + 1, a + 5, b + 1
        trap_p = top_w + bot_w + 2 * leg_w
        return [
            _text_q(f"bi:{node_key}:calc:{s}", node_key, "basic", "calculation",
                    f"计算：一个平行四边形相邻两条边的长度分别是 {s1} cm 和 {s2} cm，它的周长是多少 cm？（只填数字）",
                    str(perim), f"平行四边形对边相等，周长 = ({s1} + {s2}) × 2 = {perim}（cm）。"),
            _choice_q(f"bi:{node_key}:sc:{s}", node_key, "basic",
                      "电动伸缩门、升降机利用了平行四边形（ ）的特性。",
                      "容易变形（不稳定性）", ["稳定性", "对边平行", "四个角是直角"],
                      "平行四边形具有不稳定性，容易变形。", s),
            _tf_q(f"bi:{node_key}:tf:{s}", node_key, "basic",
                  "判断：从直线外一点到这条直线所画的所有线段中，垂直线段最短。", True, "垂线段最短，它的长度叫点到直线的距离。"),
            _text_q(f"bi:{node_key}:fb:{s}", node_key, "medium", "fill_blank",
                    "填空：只有一组对边平行的四边形叫做（ ）。",
                    "梯形", "只有一组对边平行的四边形是梯形。"),
            _choice_q(f"bi:{node_key}:sc2:{s}", node_key, "medium",
                      "在同一平面内，不相交的两条直线一定（ ）。",
                      "互相平行", ["互相垂直", "相交", "长度相等"],
                      "同一平面内两条直线的位置关系只有相交和平行。", s + 1),
            _text_q(f"bi:{node_key}:sa:{s}", node_key, "hard", "short_answer",
                    f"解决问题：一个等腰梯形的上底是 {top_w} 厘米，下底是 {bot_w} 厘米，一条腰长 {leg_w} 厘米，这个等腰梯形的周长是多少厘米？（只填数字）",
                    str(trap_p), f"周长 = 上底 + 下底 + 2 × 腰长 = {top_w} + {bot_w} + 2 × {leg_w} = {trap_p}（厘米）。", [f"{trap_p}厘米"]),
        ]

    if node_key == "G4-M2-4":
        ang_a = 40 + a * 5
        ang_b = 50 + b * 4
        ang_c = 180 - ang_a - ang_b
        top_ang = 40 + (a % 4) * 10
        base_ang = (180 - top_ang) // 2
        return [
            _text_q(f"bi:{node_key}:calc:{s}", node_key, "basic", "calculation",
                    f"计算：在三角形 ABC 中，∠A = {ang_a}°，∠B = {ang_b}°，则 ∠C =（ ）°。（只填数字）",
                    str(ang_c), f"三角形内角和为 180°，∠C = 180° - {ang_a}° - {ang_b}° = {ang_c}°。", [f"{ang_c}°"]),
            _choice_q(f"bi:{node_key}:sc:{s}", node_key, "basic",
                      "下面三组线段中（单位：cm），能围成三角形的是（ ）。",
                      "3、4、5", ["2、3、5", "1、2、4", "3、3、7"],
                      "三角形任意两边之和大于第三边：3 + 4 > 5。", s),
            _tf_q(f"bi:{node_key}:tf:{s}", node_key, "basic",
                  "判断：把一个大三角形剪成两个小三角形，每个小三角形的内角和是 90°。", False, "任何三角形的内角和都是 180°。"),
            _text_q(f"bi:{node_key}:fb:{s}", node_key, "medium", "fill_blank",
                    f"填空：一个等腰三角形的顶角是 {top_ang}°，它的一个底角是（ ）°。（只填数字）",
                    str(base_ang), f"等腰三角形两底角相等：(180° - {top_ang}°) ÷ 2 = {base_ang}°。", [f"{base_ang}°"]),
            _choice_q(f"bi:{node_key}:sc2:{s}", node_key, "medium",
                      "自行车车架、篮球架的支架做成三角形，是利用了三角形的（ ）。",
                      "稳定性", ["易变形性", "对称性", "内角和180°"], "三角形具有稳定性。", s + 2),
            _text_q(f"bi:{node_key}:sa:{s}", node_key, "hard", "short_answer",
                    f"解决问题：用一根长 {a * 3 + 12} 厘米的铁丝围成一个等边三角形，这个等边三角形的边长是多少厘米？（只填数字）",
                    str(a + 4), f"等边三角形三边相等：({a * 3 + 12}) ÷ 3 = {a + 4}（厘米）。", [f"{a + 4}厘米"]),
        ]

    if node_key == "G4-M3-1":
        base_d = _d(f"0.{a}{b}")
        mult100 = _fmt(base_d * 100)
        return [
            _text_q(f"bi:{node_key}:calc:{s}", node_key, "basic", "calculation",
                    f"直接写出得数：把 {_fmt(base_d)} 的小数点向右移动两位是（ ）。",
                    mult100, f"小数点向右移动两位，扩大到原来的 100 倍，得 {mult100}。"),
            _choice_q(f"bi:{node_key}:sc:{s}", node_key, "basic",
                      "下面各数中，把末尾的“0”去掉后大小不变的是（ ）。",
                      f"{a}.{b}0", [f"{a}00", f"{a}0.{b}", f"{a}0"],
                      "根据小数的性质，小数末尾添上 0 或去掉 0，小数大小不变。", s),
            _tf_q(f"bi:{node_key}:tf:{s}", node_key, "basic",
                  "判断：0.6 和 0.60 的大小相等，计数单位也相同。", False, "大小相等，但 0.6 的计数单位是 0.1，0.60 的计数单位是 0.01。"),
            _text_q(f"bi:{node_key}:fb:{s}", node_key, "medium", "fill_blank",
                    f"填空：0.{a}{b} 里面有（ ）个 0.01。", str(a * 10 + b),
                    f"0.{a}{b} 的计数单位是百分之一（0.01），共有 {a * 10 + b} 个 0.01。"),
            _choice_q(f"bi:{node_key}:sc2:{s}", node_key, "medium",
                      f"把 {a * 10 + b} 缩小到原来的 1/1000 是（ ）。",
                      f"0.0{a}{b}", [f"0.{a}{b}", f"{a}.{b}", f"0.00{a}{b}"],
                      f"小数点向左移动三位，得 0.0{a}{b}。", s + 1),
            _text_q(f"bi:{node_key}:sa:{s}", node_key, "hard", "short_answer",
                    f"解决问题：100 千克海水含盐 {_fmt(base_d * 10)} 千克，那么 1000 千克这样的海水含盐多少千克？（只填数字）",
                    _fmt(base_d * 100), f"海水质量扩大 10 倍，含盐量也乘 10：{_fmt(base_d * 10)} × 10 = {_fmt(base_d * 100)}（千克）。"),
        ]

    if node_key == "G4-M3-2":
        x1 = _d(f"{a}.{b}5")
        x2 = _d(f"2.{c}")
        s_val = _fmt(x1 + x2)
        d_val = _fmt(_d(10) - x2)
        return [
            _text_q(f"bi:{node_key}:calc:{s}", node_key, "basic", "calculation",
                    f"计算：{_fmt(x1)} + {_fmt(x2)} =", s_val, f"小数点对齐相加：{_fmt(x1)} + {_fmt(x2)} = {s_val}。"),
            _choice_q(f"bi:{node_key}:sc:{s}", node_key, "basic",
                      "计算小数加减法时，最关键的是要把（ ）对齐。",
                      "小数点", ["末位数字", "最高位", "小数位数"],
                      "小数点对齐才能保证相同数位对齐。", s),
            _tf_q(f"bi:{node_key}:tf:{s}", node_key, "basic",
                  "判断：整数加法的交换律和结合律对小数加法同样适用。", True, "运算律在小数加减法中同样适用，可用来凑整简算。"),
            _text_q(f"bi:{node_key}:fb:{s}", node_key, "medium", "fill_blank",
                    f"填空：10 - {_fmt(x2)} =（ ）。", d_val, f"把 10 看作 10.0，10.0 - {_fmt(x2)} = {d_val}。"),
            _text_q(f"bi:{node_key}:calc2:{s}", node_key, "medium", "calculation",
                    f"简便计算：3.6 + {a}.5 + 6.4 =", _fmt(_d("10") + _d(f"{a}.5")),
                    f"(3.6 + 6.4) + {a}.5 = 10 + {a}.5 = {_fmt(_d('10') + _d(f'{a}.5'))}。"),
            _text_q(f"bi:{node_key}:sa:{s}", node_key, "hard", "short_answer",
                    f"解决问题：一根绳子长 10 米，第一次剪去 3.2 米，第二次剪去 1.8 米，还剩多少米？（只填数字）",
                    "5", "10 - (3.2 + 1.8) = 10 - 5 = 5（米）。", ["5米"]),
        ]

    if node_key == "G4-M3-3":
        spd = 60 + a * 5
        tm = b
        dist = spd * tm
        price = c + 10
        qty = a + 2
        tot_p = price * qty
        return [
            _text_q(f"bi:{node_key}:calc:{s}", node_key, "basic", "calculation",
                    f"计算：一辆汽车的速度是 {spd} 千米/时，行驶 {tm} 小时的路程是多少千米？（只填数字）",
                    str(dist), f"路程 = 速度 × 时间 = {spd} × {tm} = {dist}（千米）。"),
            _choice_q(f"bi:{node_key}:sc:{s}", node_key, "basic",
                      "已知总价和数量，求单价的数量关系式是（ ）。",
                      "单价 = 总价 ÷ 数量", ["单价 = 总价 × 数量", "单价 = 数量 ÷ 总价", "单价 = 总价 - 数量"],
                      "总价 ÷ 数量 = 单价。", s),
            _tf_q(f"bi:{node_key}:tf:{s}", node_key, "basic",
                  "判断：“声音每秒传播 340 米”中，声音的速度可以写作 340 米/秒。", True, "速度单位由“路程单位/时间单位”组成。"),
            _text_q(f"bi:{node_key}:fb:{s}", node_key, "medium", "fill_blank",
                    f"填空：买 {qty} 个篮球共花了 {tot_p} 元，每个篮球的单价是（ ）元。",
                    str(price), f"单价 = {tot_p} ÷ {qty} = {price}（元）。"),
            _choice_q(f"bi:{node_key}:sc2:{s}", node_key, "medium",
                      f"甲地到乙地相距 {dist} 千米，汽车以 {spd} 千米/时的速度行驶，需要（ ）小时到达。",
                      str(tm), [str(tm + 1), str(tm - 1), str(dist // 10)],
                      f"时间 = 路程 ÷ 速度 = {dist} ÷ {spd} = {tm}（小时）。", s + 1),
            _text_q(f"bi:{node_key}:sa:{s}", node_key, "hard", "short_answer",
                    f"解决问题：王叔叔开车去郊区，去时速度是 {spd} 千米/时，用了 {tm} 小时；返回时只用了 {tm - 1} 小时，返回时的平均速度需要用总路程除以返回时间，请问去时的总路程是多少千米？（只填数字）",
                    str(dist), f"总路程 = {spd} × {tm} = {dist}（千米）。", [f"{dist}千米"]),
        ]

    if node_key == "G4-M3-4":
        cakes = 3 + (s % 5)   # 3..7 张饼
        per_side = 3
        tot_min = cakes * per_side
        tea_boil = 8 + (a % 3)
        tea_total = 1 + 1 + tea_boil + 1
        return [
            _text_q(f"bi:{node_key}:calc:{s}", node_key, "medium", "calculation",
                    f"烙饼问题：一只平底锅每次最多烙 2 张饼，两面都要烙，每面需要 {per_side} 分钟。烙 {cakes} 张饼至少需要多少分钟？（只填数字）",
                    str(tot_min), f"饼数 ≥ 2 时，最短时间 = 饼数 × 单面时间 = {cakes} × {per_side} = {tot_min}（分钟）。", [f"{tot_min}分钟"]),
            _choice_q(f"bi:{node_key}:sc:{s}", node_key, "basic",
                      "沏茶时：洗水壶 1 分钟，接水 1 分钟，烧水 8 分钟，洗茶杯 2 分钟，拿茶叶 1 分钟，泡茶 1 分钟。为了最省时间，烧水的同时可以（ ）。",
                      "洗茶杯和拿茶叶", ["泡茶", "洗水壶", "接水"],
                      "烧水等待的 8 分钟内可以同时完成洗茶杯和拿茶叶。", s),
            _tf_q(f"bi:{node_key}:tf:{s}", node_key, "basic",
                  "判断：一口锅每次能烙 2 张饼，每面 3 分钟，烙 3 张饼最快需要 12 分钟。", False, "采用交替烙法（正1正2 -> 反1正3 -> 反2反3），只需 3×3=9 分钟。"),
            _text_q(f"bi:{node_key}:fb:{s}", node_key, "medium", "fill_blank",
                    f"填空：洗水壶 1 分钟 -> 接水 1 分钟 -> 烧水 {tea_boil} 分钟（同时洗杯子 2 分钟）-> 泡茶 1 分钟，最快（ ）分钟能喝上茶。",
                    str(tea_total), f"1 + 1 + {tea_boil} + 1 = {tea_total}（分钟）。"),
            _choice_q(f"bi:{node_key}:sc2:{s}", node_key, "hard",
                      "田忌赛马故事中，田忌用下等马对齐王的上等马、上等马对中等马、中等马对下等马，最终 2:1 获胜，体现了（ ）数学思想。",
                      "对策论（最优博弈策略）", ["平均数", "抽屉原理", "鸡兔同笼"],
                      "合理调配出场顺序以弱耗强，属于对策论优化思想。", s + 2),
            _text_q(f"bi:{node_key}:sa:{s}", node_key, "hard", "short_answer",
                    f"解决问题：复印机每次能同时复印 2 张稿件，复印一面需要 2 秒。现在有 {a + 3} 张稿件正反两面都要复印，至少需要多少秒？（只填数字）",
                    str((a + 3) * 2), f"最短时间 = 张数 × 单面时间 = {a + 3} × 2 = {(a + 3) * 2}（秒）。", [f"{(a + 3) * 2}秒"]),
        ]

    if node_key == "G4-M4-1":
        step = 5
        bars = [step * a, step * (b + 1), step * c]
        return [
            _text_q(f"bi:{node_key}:calc:{s}", node_key, "basic", "calculation",
                    f"计算：条形统计图中三个小组的得分分别是 {bars[0]}、{bars[1]}、{bars[2]}，三个小组的总分是多少？（只填数字）",
                    str(sum(bars)), f"{bars[0]} + {bars[1]} + {bars[2]} = {sum(bars)}。"),
            _choice_q(f"bi:{node_key}:sc:{s}", node_key, "basic",
                      "条形统计图最大的优点是能够清楚、直观地看出（ ）。",
                      "各种数量的多少", ["数量的增减变化趋势", "各部分占总体的百分比", "平均数"],
                      "条形统计图通过直条长短直观反映数量的多少。", s),
            _tf_q(f"bi:{node_key}:tf:{s}", node_key, "basic",
                  "判断：在同一幅条形统计图中，纵轴上每一格代表的数量必须相同。", True, "同一坐标轴刻度间隔必须一致。"),
            _text_q(f"bi:{node_key}:fb:{s}", node_key, "medium", "fill_blank",
                    f"填空：条形统计图纵轴 1 格代表 {step} 人，表示 {step * a} 人的直条应该画（ ）格。",
                    str(a), f"{step * a} ÷ {step} = {a}（格）。"),
            _choice_q(f"bi:{node_key}:sc2:{s}", node_key, "medium",
                      "当统计的数据都在 100～500 之间且都是整百数时，纵轴 1 格代表（ ）最合适。",
                      "50 或 100", ["1", "2", "10000"], "根据数据范围合理设定每格单位。", s + 1),
            _text_q(f"bi:{node_key}:sa:{s}", node_key, "hard", "short_answer",
                    f"解决问题：条形图中故事书有 {bars[1]} 本，科技书有 {bars[0]} 本，故事书比科技书多多少本？（只填数字）",
                    str(bars[1] - bars[0]), f"{bars[1]} - {bars[0]} = {bars[1] - bars[0]}（本）。", [f"{bars[1] - bars[0]}本"]),
        ]

    if node_key == "G4-M4-2":
        avg_v = 15 + a
        n1, n2, n3 = avg_v - 2, avg_v, avg_v + 2
        return [
            _text_q(f"bi:{node_key}:calc:{s}", node_key, "basic", "calculation",
                    f"计算：{n1}、{n2}、{n3} 这三个数的平均数是多少？（只填数字）",
                    str(avg_v), f"({n1} + {n2} + {n3}) ÷ 3 = {avg_v}。"),
            _choice_q(f"bi:{node_key}:sc:{s}", node_key, "basic",
                      "小亮所在小队平均身高是 142 厘米，那么小亮本人的身高（ ）。",
                      "可能比 142 厘米高，也可能比 142 厘米低或正好 142 厘米",
                      ["一定是 142 厘米", "一定比 142 厘米高", "一定比 142 厘米低"],
                      "平均数反映一组数据的整体水平，不等于每个个体的具体数值。", s),
            _tf_q(f"bi:{node_key}:tf:{s}", node_key, "basic",
                  "判断：池塘的平均水深是 1.2 米，身高 1.4 米但不会游泳的小明下水一定没有危险。", False, "平均水深 1.2 米，深水区可能超过 1.6 米，非常危险。"),
            _text_q(f"bi:{node_key}:fb:{s}", node_key, "medium", "fill_blank",
                    f"填空：甲有 {avg_v + 3} 颗糖，乙有 {avg_v - 3} 颗糖，甲给乙（ ）颗糖，两人的糖就一样多。",
                    "3", "移多补少：相差 6 颗，甲给乙 6 ÷ 2 = 3 颗。"),
            _choice_q(f"bi:{node_key}:sc2:{s}", node_key, "medium",
                      "要同时对比四年级四个班男生和女生的人数多少，最适合绘制（ ）。",
                      "复式条形统计图", ["单式条形统计图", "单式折线图", "扇形图"],
                      "两组分类数据的数量对比适合用复式条形统计图。", s + 2),
            _text_q(f"bi:{node_key}:sa:{s}", node_key, "hard", "short_answer",
                    f"解决问题：前 3 次测验平均分是 {avg_v} 分，第 4 次得了 {avg_v + 4} 分，这 4 次测验的平均分是多少分？（只填数字）",
                    str(avg_v + 1), f"总分 = {avg_v} × 3 + ({avg_v + 4}) = {4 * avg_v + 4}，平均分 = {avg_v + 1}（分）。", [f"{avg_v + 1}分"]),
        ]

    if node_key == "G4-M4-3":
        chickens = a + 2
        rabbits = b
        heads = chickens + rabbits
        legs = 2 * chickens + 4 * rabbits
        return [
            _text_q(f"bi:{node_key}:sa:{s}", node_key, "hard", "short_answer",
                    f"鸡兔同笼：笼子里共有 {heads} 个头、{legs} 只脚。请问兔子有多少只？（只填数字）",
                    str(rabbits),
                    f"假设全是鸡，应有 {heads * 2} 只脚，多出 {legs - heads * 2} 只脚，每只兔比鸡多 2 只脚，兔有 ({legs} - {heads * 2}) ÷ 2 = {rabbits}（只）。",
                    [f"{rabbits}只"]),
            _text_q(f"bi:{node_key}:fb:{s}", node_key, "medium", "fill_blank",
                    f"填空：鸡和兔共 {heads} 只，共有 {legs} 只脚，其中鸡有（ ）只。",
                    str(chickens), f"兔子有 {rabbits} 只，鸡有 {heads} - {rabbits} = {chickens}（只）。"),
            _choice_q(f"bi:{node_key}:sc:{s}", node_key, "basic",
                      f"鸡兔同笼共 {heads} 个头，如果假设全部是鸡，那么一共算出了（ ）只脚。",
                      str(heads * 2), [str(heads * 4), str(heads * 3), str(legs)],
                      f"每只鸡 2 只脚，{heads} × 2 = {heads * 2} 只脚。", s),
            _tf_q(f"bi:{node_key}:tf:{s}", node_key, "basic",
                  "判断：用假设法解鸡兔同笼问题时，如果先假设全是鸡，第一步求出来的只数是兔子的只数。", True, "假设全是鸡，脚数差除以 (4-2) 得到的是另一方（兔子）的只数。"),
            _text_q(f"bi:{node_key}:calc:{s}", node_key, "medium", "calculation",
                    f"计算：({legs} - {heads} × 2) ÷ (4 - 2) =", str(rabbits),
                    f"({legs} - {heads * 2}) ÷ 2 = {rabbits}。"),
            _choice_q(f"bi:{node_key}:sc2:{s}", node_key, "medium",
                      "自行车（2轮）和三轮车（3轮）共 10 辆，总共有 24 个轮子，其中三轮车有（ ）辆。",
                      "4", ["6", "5", "3"], "假设全是自行车有 20 个轮子，多出 4 个轮子，即三轮车有 4 辆。", s + 1),
        ]

    # G4-M4-4 和差倍与年龄还原问题
    small_n = a + 5
    big_n = small_n + b * 2
    sum_n = small_n + big_n
    diff_n = big_n - small_n
    return [
        _text_q(f"bi:{node_key}:calc:{s}", node_key, "basic", "calculation",
                f"和差公式计算：({sum_n} + {diff_n}) ÷ 2 =", str(big_n), f"(和 + 差) ÷ 2 = 大数 = {big_n}。"),
        _choice_q(f"bi:{node_key}:sc:{s}", node_key, "basic",
                  "已知两个数的“和”与“差”，求较大数的公式是（ ）。",
                  "(和 + 差) ÷ 2", ["(和 - 差) ÷ 2", "和 + 差", "和 ÷ 2 + 差"],
                  "(和 + 差) ÷ 2 = 大数，(和 - 差) ÷ 2 = 小数。", s),
        _tf_q(f"bi:{node_key}:tf:{s}", node_key, "basic",
              "判断：今年爸爸比小明大 28 岁，再过 10 年，爸爸比小明大 38 岁。", False, "两人的年龄差永远不变，再过 10 年仍然相差 28 岁。"),
        _text_q(f"bi:{node_key}:fb:{s}", node_key, "medium", "fill_blank",
                f"填空：两数之和是 {sum_n}，两数之差是 {diff_n}，其中较小的数是（ ）。",
                str(small_n), f"({sum_n} - {diff_n}) ÷ 2 = {small_n}。"),
        _choice_q(f"bi:{node_key}:sc2:{s}", node_key, "medium",
                  f"果园里苹果树和梨树共 {(a + 3) * 4} 棵，苹果树是梨树的 3 倍，梨树有（ ）棵。",
                  str(a + 3), [str((a + 3) * 3), str((a + 3) * 2), "4"],
                  f"和倍问题：总份数 = 3 + 1 = 4 份，梨树 = {(a + 3) * 4} ÷ 4 = {a + 3}（棵）。", s + 2),
        _text_q(f"bi:{node_key}:sa:{s}", node_key, "hard", "short_answer",
                f"解决问题：某数加上 {a}，再乘 {b}，结果等于 {(c + a) * b}，这个数原来是多少？（只填数字）",
                str(c), f"倒推还原：{(c + a) * b} ÷ {b} - {a} = {c}。"),
    ]


def _build_g6_node_pool(node_key: str, s: int) -> list[dict[str, Any]]:
    a = 2 + (s % 7)          # 2..8
    b = 3 + ((s * 3) % 6)    # 3..8
    c = 4 + ((s * 5) % 5)    # 4..8

    if node_key == "G6-M1-1":
        tot = (a + 1) * 12
        part = (tot * 3) // 4
        dist_ans = a + b
        return [
            _text_q(f"bi:{node_key}:calc:{s}", node_key, "basic", "calculation",
                    f"计算：{tot} × 3/4 =", str(part), f"先约分再计算：{tot} ÷ 4 × 3 = {part}。"),
            _choice_q(f"bi:{node_key}:sc:{s}", node_key, "basic",
                      "计算 2/3 × 3/5 的结果是（ ）。",
                      "2/5", ["6/8", "5/8", "1/5"],
                      "分子相乘作分子，分母相乘作分母，约去 3 得 2/5。", s),
            _tf_q(f"bi:{node_key}:tf:{s}", node_key, "basic",
                  "判断：一个大于 0 的数乘真分数，积一定小于这个数。", True, "真分数小于 1，正数乘小于 1 的数，积比原数小。"),
            _text_q(f"bi:{node_key}:fb:{s}", node_key, "medium", "fill_blank",
                    f"填空：({a}/12 + {b}/12) × 12 =（ ）。", str(dist_ans),
                    f"利用乘法分配律：{a} + {b} = {dist_ans}。"),
            _choice_q(f"bi:{node_key}:sc2:{s}", node_key, "medium",
                      "一袋大米 20 千克，先吃去它的 1/2，又吃去 1/2 千克，一共吃去了（ ）千克。",
                      "10.5", ["10", "15", "20"],
                      "第一个 1/2 是分率（20×1/2=10千克），第二个 1/2 千克是具体数量（0.5千克），共 10.5 千克。", s + 1),
            _text_q(f"bi:{node_key}:sa:{s}", node_key, "hard", "short_answer",
                    f"解决问题：一本故事书有 {tot} 页，小明第一天看了全书的 3/4，第一天看了多少页？（只填数字）",
                    str(part), f"{tot} × 3/4 = {part}（页）。", [f"{part}页"]),
        ]

    if node_key == "G6-M1-2":
        orig = (a + 2) * 5
        part = (orig * 3) // 5
        return [
            _text_q(f"bi:{node_key}:calc:{s}", node_key, "basic", "calculation",
                    f"计算：{part} ÷ 3/5 =", str(orig), f"除以一个数等于乘它的倒数：{part} × 5/3 = {orig}。"),
            _choice_q(f"bi:{node_key}:sc:{s}", node_key, "basic",
                      f"真分数 {a}/{a + 3} 的倒数是（ ）。",
                      f"{a + 3}/{a}", [f"{a}/{a + 3}", "1", f"1/{a}"],
                      "乘积是 1 的两个数互为倒数，分子分母交换位置即可。", s),
            _tf_q(f"bi:{node_key}:tf:{s}", node_key, "basic",
                  "判断：1 的倒数是 1，0 的倒数是 0。", False, "1 的倒数是 1，但 0 没有倒数。"),
            _text_q(f"bi:{node_key}:fb:{s}", node_key, "medium", "fill_blank",
                    f"填空：一个数的 3/5 是 {part}，这个数是（ ）。", str(orig),
                    f"已知部分求单位“1”用除法：{part} ÷ 3/5 = {orig}。"),
            _choice_q(f"bi:{node_key}:sc2:{s}", node_key, "medium",
                      "当 a > 0 时，下面算式中得数最大的是（ ）。",
                      "a ÷ 1/2", ["a × 1/2", "a ÷ 3/2", "a - 1/2"],
                      "除以小于 1 的正数（1/2），商比原数大（等于 2a）。", s + 2),
            _text_q(f"bi:{node_key}:sa:{s}", node_key, "hard", "short_answer",
                    f"解决问题：果园里有桃树 {part} 棵，正好是梨树棵数的 3/5，梨树有多少棵？（只填数字）",
                    str(orig), f"{part} ÷ 3/5 = {orig}（棵）。", [f"{orig}棵"]),
        ]

    if node_key == "G6-M1-3":
        k_mul = a + 2
        r1, r2 = 2, 3
        tot_alloc = (r1 + r2) * k_mul * 4
        part_a = r1 * k_mul * 4
        part_b = r2 * k_mul * 4
        return [
            _text_q(f"bi:{node_key}:calc:{s}", node_key, "basic", "calculation",
                    f"求比值：{k_mul * 4} : {k_mul * 2} =", "2", f"{k_mul * 4} ÷ {k_mul * 2} = 2。"),
            _choice_q(f"bi:{node_key}:sc:{s}", node_key, "basic",
                      f"把 {r1 * k_mul} : {r2 * k_mul} 化成最简单的整数比是（ ）。",
                      f"{r1}:{r2}", [f"{r2}:{r1}", f"{r1 * 2}:{r2 * 2}", f"{r1}/{r2}"],
                      f"前项和后项同时除以最大公因数 {k_mul}，得 {r1}:{r2}。", s),
            _tf_q(f"bi:{node_key}:tf:{s}", node_key, "basic",
                  "判断：比的前项和后项同时乘或除以相同的数（0 除外），比值不变。", True, "这是比的基本性质。"),
            _text_q(f"bi:{node_key}:fb:{s}", node_key, "medium", "fill_blank",
                    f"填空：一个三角形三个内角度数的比是 1 : 2 : 3，最大的角是（ ）度。",
                    "90", "180° × 3/(1+2+3) = 90°，是直角三角形。", ["90°", "90度"]),
            _choice_q(f"bi:{node_key}:sc2:{s}", node_key, "medium",
                      "把 10 克盐溶解在 100 克水中，盐与盐水的质量比是（ ）。",
                      "1:11", ["1:10", "10:11", "1:9"],
                      "盐水质量 = 10 + 100 = 110 克，10 : 110 = 1 : 11。", s + 1),
            _text_q(f"bi:{node_key}:sa:{s}", node_key, "hard", "short_answer",
                    f"解决问题：按 {r1} : {r2} 的比把 {tot_alloc} 本图书分给甲、乙两班，乙班分到多少本？（只填数字）",
                    str(part_b), f"总份数 = {r1}+{r2}=5 份，乙班分得 {tot_alloc} × {r2}/5 = {part_b}（本）。", [f"{part_b}本"]),
        ]

    if node_key == "G6-M1-4":
        orig_p = (a + 1) * 100
        sale_p = int(orig_p * 80 // 100)
        principal = 1000 * b
        interest = int(principal * 2 // 100)
        return [
            _text_q(f"bi:{node_key}:calc:{s}", node_key, "basic", "calculation",
                    f"计算：{orig_p} × 80% =", str(sale_p), f"80% = 0.8，{orig_p} × 0.8 = {sale_p}。"),
            _choice_q(f"bi:{node_key}:sc:{s}", node_key, "basic",
                      "一件商品打“八五折”出售，就是按原价的（ ）出售。",
                      "85%", ["15%", "8.5%", "80%"], "几几折就是百分之几十几，八五折即 85%。", s),
            _tf_q(f"bi:{node_key}:tf:{s}", node_key, "basic",
                  "判断：一根绳子长 80% 米。", False, "百分数只能表示两个量之间的倍比关系，后面不能带具体单位。"),
            _text_q(f"bi:{node_key}:fb:{s}", node_key, "medium", "fill_blank",
                    "填空：植树小队种了 100 棵树，全部成活，成活率是（ ）%。（只填数字）",
                    "100", "100 ÷ 100 × 100% = 100%。", ["100%"]),
            _choice_q(f"bi:{node_key}:sc2:{s}", node_key, "medium",
                      "一种商品先提价 10%，再降价 10%，现价与原价相比（ ）。",
                      "比原价低", ["与原价相等", "比原价高", "无法比较"],
                      "1 × (1 + 10%) × (1 - 10%) = 1.1 × 0.9 = 0.99 < 1，比原价低 1%。", s + 2),
            _text_q(f"bi:{node_key}:sa:{s}", node_key, "hard", "short_answer",
                    f"解决问题：把 {principal} 元存入银行，年利率是 2%，存期 1 年，到期可获得利息多少元？（只填数字）",
                    str(interest), f"利息 = 本金 × 利率 × 存期 = {principal} × 2% × 1 = {interest}（元）。", [f"{interest}元"]),
        ]

    if node_key == "G6-M2-1":
        ang = 30 + (s % 3) * 15   # 30, 45, 60
        dx, dy = 3, 4
        dist_m = 500
        fig = _bearing_grid_figure(dx, dy)
        return [
            _choice_q(f"bi:{node_key}:sc:{s}", node_key, "basic",
                      f"如果甲在乙的北偏东 {ang}° 方向 {dist_m} 米处，那么乙在甲的（ ）方向 {dist_m} 米处。",
                      f"南偏西 {ang}°", [f"北偏西 {ang}°", f"南偏东 {ang}°", f"东偏北 {ang}°"],
                      "观测点互换时，方向相反（北对南、东对西），偏角和距离不变。", s, figure=fig),
            _tf_q(f"bi:{node_key}:tf:{s}", node_key, "basic",
                  "判断：“北偏东 30°”与“东偏北 60°”表示的是同一个方向。", True, "两角互余（30°+60°=90°），指向同一射线方向。"),
            _text_q(f"bi:{node_key}:fb:{s}", node_key, "medium", "fill_blank",
                    f"填空：看图或根据平面图，图上 1 格代表 100 米，相距 {a + 2} 格的两地实际相距（ ）米。",
                    str((a + 2) * 100), f"{a + 2} × 100 = {(a + 2) * 100}（米）。", figure=fig),
            _text_q(f"bi:{node_key}:calc:{s}", node_key, "medium", "calculation",
                    f"计算：北偏东 {ang}° 方向也可以说成东偏北（ ）°。（只填数字）",
                    str(90 - ang), f"90° - {ang}° = {90 - ang}°。", [f"{90 - ang}°"]),
            _choice_q(f"bi:{node_key}:sc2:{s}", node_key, "medium",
                      "要确定平面图上某个物体的准确位置，需要同时知道（ ）。",
                      "方向（角度）和距离", ["只看方向", "只看距离", "物体的大小"],
                      "确定位置有两大要素：方向（偏角）和距离。", s + 1),
            _text_q(f"bi:{node_key}:sa:{s}", node_key, "hard", "short_answer",
                    f"解决问题：小船从港口出发向正东航行 {a * 100} 米，再原路向正西航行 {100} 米，此时小船距离港口多少米？（只填数字）",
                    str((a - 1) * 100), f"{a * 100} - 100 = {(a - 1) * 100}（米）。", [f"{(a - 1) * 100}米"]),
        ]

    if node_key == "G6-M2-2":
        r = a + 1
        d = 2 * r
        c_len = _fmt(_d("3.14") * _d(d))
        semi_c = _fmt(_d("3.14") * _d(r) + _d(d))
        return [
            _text_q(f"bi:{node_key}:calc:{s}", node_key, "basic", "calculation",
                    f"计算（π 取 3.14）：直径 d = {d} cm 的圆，周长是多少 cm？（只填数字）",
                    c_len, f"C = πd = 3.14 × {d} = {c_len}（cm）。"),
            _choice_q(f"bi:{node_key}:sc:{s}", node_key, "basic",
                      "圆的周长与它的直径的比值是一个固定的数，叫做（ ）。",
                      "圆周率 π", ["半径", "扇形", "面积"], "任意圆的周长除以直径都等于圆周率 π。", s),
            _tf_q(f"bi:{node_key}:tf:{s}", node_key, "basic",
                  "判断：半圆的周长就等于圆周长的一半。", False, "半圆的周长不仅包含圆周长的一半（πr），还要加上一条直径（2r）。"),
            _text_q(f"bi:{node_key}:fb:{s}", node_key, "medium", "fill_blank",
                    f"填空（π 取 3.14）：一个圆的周长是 {c_len} cm，它的半径是（ ）cm。",
                    str(r), f"r = C ÷ (2π) = {c_len} ÷ 6.28 = {r}（cm）。"),
            _choice_q(f"bi:{node_key}:sc2:{s}", node_key, "medium",
                      "一个圆的半径扩大到原来的 3 倍，它的周长扩大到原来的（ ）倍。",
                      "3", ["6", "9", "不变"], "圆周长 C = 2πr 与半径成正比，半径扩大 3 倍，周长也扩大 3 倍。", s + 2),
            _text_q(f"bi:{node_key}:sa:{s}", node_key, "hard", "short_answer",
                    f"解决问题（π 取 3.14）：一个半圆形花坛的半径是 {r} 米，围这个半圆形花坛一圈需要篱笆多少米？（只填数字）",
                    semi_c, f"半圆周长 = 3.14 × {r} + 2 × {r} = {semi_c}（米）。", [f"{semi_c}米"]),
        ]

    if node_key == "G6-M2-3":
        r = a
        area = _fmt(_d("3.14") * _d(r * r))
        R_big, r_small = 5, 3
        ring_area = _fmt(_d("3.14") * _d(R_big ** 2 - r_small ** 2))   # 3.14 * 16 = 50.24
        return [
            _text_q(f"bi:{node_key}:calc:{s}", node_key, "basic", "calculation",
                    f"计算（π 取 3.14）：半径 r = {r} cm 的圆，它的面积是多少 cm²？（只填数字）",
                    area, f"S = πr² = 3.14 × {r}² = {area}（cm²）。"),
            _choice_q(f"bi:{node_key}:sc:{s}", node_key, "basic",
                      "一个圆的半径扩大到原来的 2 倍，它的面积扩大到原来的（ ）倍。",
                      "4", ["2", "6", "8"], "S = πr²，半径乘 2，面积乘 2² = 4。", s),
            _tf_q(f"bi:{node_key}:tf:{s}", node_key, "basic",
                  "判断：周长相等的长方形、正方形和圆中，圆的面积最大。", True, "周长一定时，越接近圆形，围成的面积越大。"),
            _text_q(f"bi:{node_key}:fb:{s}", node_key, "medium", "fill_blank",
                    f"填空（π 取 3.14）：一个圆环的外圆半径是 {R_big} cm，内圆半径是 {r_small} cm，圆环的面积是（ ）cm²。",
                    ring_area, f"S环 = 3.14 × ({R_big}² - {r_small}²) = 3.14 × 16 = {ring_area}（cm²）。"),
            _choice_q(f"bi:{node_key}:sc2:{s}", node_key, "medium",
                      "圆心角是 90° 的扇形，它的面积占所在整圆面积的（ ）。",
                      "1/4", ["1/2", "1/3", "1/6"], "90° ÷ 360° = 1/4。", s + 1),
            _text_q(f"bi:{node_key}:sa:{s}", node_key, "hard", "short_answer",
                    f"解决问题（π 取 3.14）：在一个边长 {r * 2} 厘米的正方形纸板里剪出一个最大的圆，这个圆的面积是多少平方厘米？（只填数字）",
                    area, f"最大圆的直径等于正方形边长 {r * 2} 厘米，半径 r = {r} 厘米，面积 = 3.14 × {r}² = {area}。", [f"{area}平方厘米"]),
        ]

    if node_key == "G6-M2-4":
        base_s = (a + 1) * 3   # 9..27
        h_val = b
        cyl_v = base_s * h_val
        cone_v = cyl_v // 3
        return [
            _text_q(f"bi:{node_key}:calc:{s}", node_key, "basic", "calculation",
                    f"计算：一个圆柱的底面积是 {base_s} cm²，高是 {h_val} cm，它的体积是多少 cm³？（只填数字）",
                    str(cyl_v), f"V柱 = Sh = {base_s} × {h_val} = {cyl_v}（cm³）。"),
            _choice_q(f"bi:{node_key}:sc:{s}", node_key, "basic",
                      "把圆柱的侧面沿高剪开，展开后得到一个（ ）。",
                      "长方形（或正方形）", ["梯形", "圆形", "扇形"],
                      "沿高剪开时，圆柱侧面展开图的长是底面周长，宽是圆柱的高。", s),
            _tf_q(f"bi:{node_key}:tf:{s}", node_key, "basic",
                  "判断：等底等高的圆锥体积是圆柱体积的 1/3。", True, "V锥 = 1/3 Sh，等底等高时是圆柱体积的 1/3。"),
            _text_q(f"bi:{node_key}:fb:{s}", node_key, "medium", "fill_blank",
                    f"填空：一个圆柱和一个圆锥等底等高，圆柱体积是 {cyl_v} cm³，圆锥体积是（ ）cm³。",
                    str(cone_v), f"{cyl_v} ÷ 3 = {cone_v}（cm³）。"),
            _choice_q(f"bi:{node_key}:sc2:{s}", node_key, "hard",
                      f"把一段体积是 {cyl_v} cm³ 的圆柱形木料削成一个最大的圆锥，削去部分的体积是（ ）cm³。",
                      str(cone_v * 2), [str(cone_v), str(cyl_v), str(cyl_v * 3)],
                      f"最大圆锥占 1/3，削去部分占 2/3，即 {cone_v} × 2 = {cone_v * 2}（cm³）。", s + 2),
            _text_q(f"bi:{node_key}:sa:{s}", node_key, "hard", "short_answer",
                    f"解决问题：一个圆锥形沙堆的底面积是 {base_s} 平方米，高是 {h_val} 米，这堆沙子的体积是多少立方米？（只填数字）",
                    str(cone_v), f"V锥 = 1/3 × {base_s} × {h_val} = {cone_v}（立方米）。", [f"{cone_v}立方米"]),
        ]

    if node_key == "G6-M3-1":
        t_high = a + 3
        t_low = -b
        diff_t = t_high - t_low
        return [
            _text_q(f"bi:{node_key}:calc:{s}", node_key, "basic", "calculation",
                    f"温差计算：某天最高气温是 +{t_high}℃，最低气温是 {t_low}℃，这一天的温差是多少℃？（只填数字）",
                    str(diff_t), f"零上 {t_high}℃ 与零下 {b}℃ 相差 {t_high} + {b} = {diff_t}（℃）。", [f"{diff_t}℃"]),
            _choice_q(f"bi:{node_key}:sc:{s}", node_key, "basic",
                      f"在数轴上比较大小：-{a} ○ -{a + 3}。",
                      ">", ["<", "=", "无法比较"],
                      f"在数轴上，-{a} 在 -{a + 3} 的右边，负号后面的数越小，这个负数反而越大。", s),
            _tf_q(f"bi:{node_key}:tf:{s}", node_key, "basic",
                  "判断：0 既不是正数，也不是负数，它是正数和负数的分界点。", True, "所有负数 < 0 < 所有正数。"),
            _text_q(f"bi:{node_key}:fb:{s}", node_key, "medium", "fill_blank",
                    f"填空：如果向东走 {a} 米记作 +{a} 米，那么向西走 {b} 米记作（ ）米。",
                    f"-{b}", f"东和西具有相反意义，向西走 {b} 米记作 -{b} 米。"),
            _choice_q(f"bi:{node_key}:sc2:{s}", node_key, "medium",
                      "在 -4、0、+2.5、-0.5 这四个数中，最接近 0 的数是（ ）。",
                      "-0.5", ["-4", "+2.5", "一样近"], "-0.5 到 0 的距离只有 0.5 个单位，最近。", s + 1),
            _text_q(f"bi:{node_key}:sa:{s}", node_key, "hard", "short_answer",
                    f"解决问题：电梯从地上 {a} 层（+{a}层）下降到地下 2 层（-2层），一共下降了多少层？（只填数字）",
                    str(a + 1), f"由于没有第 0 层，从地上 {a} 层到地下 2 层共下降 {a} + 2 - 1 = {a + 1} 层。"),
        ]

    if node_key == "G6-M3-2":
        x_ans = a * 3
        # 2 : 3 = (a*2) : x_ans
        return [
            _text_q(f"bi:{node_key}:calc:{s}", node_key, "basic", "calculation",
                    f"解比例：2 : 3 = {a * 2} : x，则 x =", str(x_ans),
                    f"根据比例基本性质：2x = 3 × {a * 2} = {a * 6}，解得 x = {x_ans}。"),
            _choice_q(f"bi:{node_key}:sc:{s}", node_key, "basic",
                      "下面哪组中的两个比可以组成比例？（ ）",
                      "2:3 和 4:6", ["1:2 和 3:4", "2:5 和 5:2", "3:4 和 6:10"],
                      "2:3 = 2/3，4:6 = 2/3，比值相等可以组成比例。", s),
            _tf_q(f"bi:{node_key}:tf:{s}", node_key, "basic",
                  "判断：在比例里，两个外项的积等于两个内项的积。", True, "这是比例的基本性质。"),
            _text_q(f"bi:{node_key}:fb:{s}", node_key, "medium", "fill_blank",
                    f"填空：在一个比例中，两个内项互为倒数，其中一个外项是 {a}，另一个外项是（ ）。（用 a/b 表示）",
                    f"1/{a}", f"两内项互为倒数则乘积为 1，故两外项乘积也为 1，另一个外项是 1/{a}。"),
            _choice_q(f"bi:{node_key}:sc2:{s}", node_key, "medium",
                      "如果 3a = 4b（a、b 均不为 0），那么 a : b =（ ）。",
                      "4:3", ["3:4", "3:7", "4:7"],
                      "根据内项积等于外项积，a : b = 4 : 3。", s + 2),
            _text_q(f"bi:{node_key}:sa:{s}", node_key, "hard", "short_answer",
                    f"解决问题：调制蜂蜜水，用 2 杯蜂蜜配 {b * 2} 杯水；照这样计算，用 {a} 杯蜂蜜需要配多少杯水？（只填数字）",
                    str(a * b), f"设需配水 x 杯，2 : {b * 2} = {a} : x，解得 x = {a * b}。", [f"{a * b}杯"]),
        ]

    if node_key == "G6-M3-3":
        unit_p = a + 3
        qty = b + 2
        tot_p = unit_p * qty
        return [
            _choice_q(f"bi:{node_key}:sc:{s}", node_key, "basic",
                      "当路程一定时，汽车行驶的速度和时间成（ ）关系。",
                      "反比例", ["正比例", "不成比例", "正比或反比"],
                      "速度 × 时间 = 路程（一定），乘积一定成反比例。", s),
            _tf_q(f"bi:{node_key}:tf:{s}", node_key, "basic",
                  "判断：单价一定时，购买商品的总价和数量成正比例关系。", True, "总价 ÷ 数量 = 单价（一定），比值一定成正比例。"),
            _choice_q(f"bi:{node_key}:sc2:{s}", node_key, "medium",
                      "一个人的身高和他的年龄（ ）。",
                      "不成比例", ["成正比例", "成反比例", "一定成正比"],
                      "身高和年龄的比值或乘积都不是固定常数，所以不成比例。", s + 1),
            _text_q(f"bi:{node_key}:fb:{s}", node_key, "medium", "fill_blank",
                    f"填空：如果 x 和 y 成正比例，当 x = 2 时 y = {unit_p * 2}；那么当 x = {qty} 时，y =（ ）。",
                    str(tot_p), f"y ÷ x = {unit_p}，当 x = {qty} 时，y = {unit_p} × {qty} = {tot_p}。"),
            _text_q(f"bi:{node_key}:calc:{s}", node_key, "medium", "calculation",
                    f"反比例计算：已知 x 与 y 成反比例，且 x × y = {a * 12}，当 x = {a} 时，y =",
                    "12", f"y = {a * 12} ÷ {a} = 12。"),
            _text_q(f"bi:{node_key}:sa:{s}", node_key, "hard", "short_answer",
                    f"解决问题：铺一间教室地面，用面积 4 平方分米的方砖需要 {a * 30} 块；如果改用面积 6 平方分米的方砖，需要多少块？（只填数字）",
                    str(a * 20), f"教室总面积一定（反比例）：4 × {a * 30} ÷ 6 = {a * 20}（块）。", [f"{a * 20}块"]),
        ]

    if node_key == "G6-M3-4":
        map_cm = a + 1
        scale_km = b   # 1 cm represents b km
        real_km = map_cm * scale_km
        rect_s = c * 2
        zoom_k = 2
        return [
            _text_q(f"bi:{node_key}:calc:{s}", node_key, "basic", "calculation",
                    f"计算：在比例尺 1 : {scale_km * 100000} 的地图上，量得两地距离是 {map_cm} 厘米，两地实际距离是多少千米？（只填数字）",
                    str(real_km), f"图上 1 厘米代表实际 {scale_km} 千米，{map_cm} × {scale_km} = {real_km}（千米）。", [f"{real_km}千米"]),
            _choice_q(f"bi:{node_key}:sc:{s}", node_key, "basic",
                      "比例尺的定义是（ ）。",
                      "图上距离 : 实际距离", ["实际距离 : 图上距离", "图上面积 : 实际面积", "图上距离 × 实际距离"],
                      "图上距离与实际距离的比叫做这幅图的比例尺。", s),
            _tf_q(f"bi:{node_key}:tf:{s}", node_key, "basic",
                  "判断：把一个图形按 2 : 1 放大后，图形各边的长度扩大到原来的 2 倍，但每个角的度数不变。", True, "图形放大或缩小只改变大小，不改变形状（内角度数不变）。"),
            _text_q(f"bi:{node_key}:fb:{s}", node_key, "medium", "fill_blank",
                    f"填空：把一个面积是 {rect_s} cm² 的长方形按 {zoom_k} : 1 放大，放大后的长方形面积是（ ）cm²。",
                    str(rect_s * zoom_k * zoom_k), f"边长放大 {zoom_k} 倍，面积扩大 {zoom_k}² = 4 倍，{rect_s} × 4 = {rect_s * 4}（cm²）。"),
            _choice_q(f"bi:{node_key}:sc2:{s}", node_key, "medium",
                      "精密零件图纸上的比例尺是 10 : 1，它表示（ ）。",
                      "图上距离是实际距离的 10 倍", ["实际距离是图上距离的 10 倍", "图上 1 厘米代表 10 米", "缩小比例尺"],
                      "前项大于后项是放大比例尺，图上距离是实际距离的 10 倍。", s + 2),
            _text_q(f"bi:{node_key}:sa:{s}", node_key, "hard", "short_answer",
                    f"解决问题：甲乙两城实际相距 {real_km} 千米，画在图上距离是 {map_cm} 厘米，这幅地图上 1 厘米代表实际多少千米？（只填数字）",
                    str(scale_km), f"{real_km} ÷ {map_cm} = {scale_km}（千米）。", [f"{scale_km}千米"]),
        ]

    if node_key == "G6-M4-1":
        tot_stu = (a + 1) * 100
        pct = 25
        cnt = (tot_stu * pct) // 100
        return [
            _text_q(f"bi:{node_key}:calc:{s}", node_key, "basic", "calculation",
                    f"扇形统计图计算：全校有 {tot_stu} 名学生，其中喜欢篮球的占 {pct}%，喜欢篮球的有多少人？（只填数字）",
                    str(cnt), f"{tot_stu} × {pct}% = {cnt}（人）。"),
            _choice_q(f"bi:{node_key}:sc:{s}", node_key, "basic",
                      "要清楚地表示牛奶中各种营养成分占总量的百分比，最适合选用（ ）统计图。",
                      "扇形", ["条形", "折线", "复式折线"],
                      "扇形统计图能清楚反映各部分数量与总数之间的百分比关系。", s),
            _tf_q(f"bi:{node_key}:tf:{s}", node_key, "basic",
                  "判断：在扇形统计图中，整个圆表示总体（单位“1”或 100%），各扇形百分比之和等于 100%。", True, "整个圆代表 100%。"),
            _text_q(f"bi:{node_key}:fb:{s}", node_key, "medium", "fill_blank",
                    "填空：扇形统计图中，某部分占总体的 25%，它所对应的扇形圆心角是（ ）度。",
                    "90", "360° × 25% = 90°。", ["90°", "90度"]),
            _choice_q(f"bi:{node_key}:sc2:{s}", node_key, "medium",
                      "扇形统计图中，A、B、C 三部分占总体的百分比分别是 50%、30%，则 C 部分占（ ）%。",
                      "20", ["30", "25", "10"], "100% - 50% - 30% = 20%。", s + 1),
            _text_q(f"bi:{node_key}:sa:{s}", node_key, "hard", "short_answer",
                    f"解决问题：家庭月度支出扇形图中，食品支出占 40%，正好是 {a * 400} 元，这个家庭本月的总支出是多少元？（只填数字）",
                    str(a * 1000), f"总支出 = {a * 400} ÷ 40% = {a * 1000}（元）。", [f"{a * 1000}元"]),
        ]

    if node_key == "G6-M4-2":
        # 经典整除工程对：(6, 3)->2, (10, 15)->6, (12, 6)->4, (20, 30)->12
        pairs = [(6, 3, 2), (10, 15, 6), (12, 6, 4), (20, 30, 12)]
        da, db, dc = pairs[s % len(pairs)]
        return [
            _text_q(f"bi:{node_key}:sa:{s}", node_key, "hard", "short_answer",
                    f"工程问题：修一条路，甲队单独修需要 {da} 天，乙队单独修需要 {db} 天。两队合修需要多少天完成？（只填数字）",
                    str(dc), f"把工作总量看作 1，合修时间 = 1 ÷ (1/{da} + 1/{db}) = {dc}（天）。", [f"{dc}天"]),
            _choice_q(f"bi:{node_key}:sc:{s}", node_key, "basic",
                      f"一项工程甲单独做 {da} 天完成，甲每天完成这项工程的（ ）。",
                      f"1/{da}", [str(da), f"1/{da + 1}", "1"],
                      f"工作效率 = 工作总量 1 ÷ 工作时间 {da} = 1/{da}。", s),
            _tf_q(f"bi:{node_key}:tf:{s}", node_key, "basic",
                  "判断：在分数工程问题中，未给出具体工作总量时，通常把工作总量看作单位“1”。", True, "设总量为单位“1”是分数工程问题的核心方法。"),
            _text_q(f"bi:{node_key}:fb:{s}", node_key, "medium", "fill_blank",
                    f"填空：甲工作效率是 1/{da}，乙工作效率是 1/{db}，两队合作 1 天能完成全工程的（ ）。（用最简分数 a/b 表示）",
                    f"1/{dc}", f"1/{da} + 1/{db} = 1/{dc}。"),
            _text_q(f"bi:{node_key}:calc:{s}", node_key, "medium", "calculation",
                    f"计算：1 ÷ (1/{da} + 1/{db}) =", str(dc), f"1 ÷ (1/{dc}) = {dc}。"),
            _choice_q(f"bi:{node_key}:sc2:{s}", node_key, "medium",
                      "水池有进水管和排水管，单开进水管 4 小时注满，单开排水管 6 小时排空，两管同时打开，每小时净注水占水池的（ ）。",
                      "1/12", ["1/10", "5/12", "1/2"], "1/4 - 1/6 = 1/12。", s + 2),
        ]

    if node_key == "G6-M4-3":
        n_cnt = a + 3   # 5..11 个连续奇数
        sq_sum = n_cnt * n_cnt
        last_odd = 2 * n_cnt - 1
        return [
            _text_q(f"bi:{node_key}:calc:{s}", node_key, "basic", "calculation",
                    f"数形规律计算：从 1 开始连续 {n_cnt} 个奇数相加：1 + 3 + 5 + … + {last_odd} =",
                    str(sq_sum), f"从 1 开始连续 n 个奇数的和等于 n² = {n_cnt}² = {sq_sum}。"),
            _choice_q(f"bi:{node_key}:sc:{s}", node_key, "basic",
                      "观察正方形点阵规律：第 1 个图有 1 个点，第 2 个图有 4 个点，第 3 个图有 9 个点，第 n 个图有（ ）个点。",
                      "n²", ["2n", "n + 3", "4n"],
                      "正方形点阵第 n 个图是 n 行 n 列，共 n² 个点。", s),
            _tf_q(f"bi:{node_key}:tf:{s}", node_key, "basic",
                  "判断：1 + 3 + 5 + 7 + 9 + 7 + 5 + 3 + 1 = 5² + 4² = 41。", True, "前半部分 5 个奇数是 5²=25，后半部分 4 个奇数是 4²=16，25+16=41。"),
            _text_q(f"bi:{node_key}:fb:{s}", node_key, "medium", "fill_blank",
                    f"填空：如果 1 + 3 + 5 + … + (2n-1) = {sq_sum}，那么算式中一共有（ ）个奇数相加。",
                    str(n_cnt), f"{n_cnt}² = {sq_sum}，共有 {n_cnt} 个连续奇数。"),
            _choice_q(f"bi:{node_key}:sc2:{s}", node_key, "medium",
                      "计算 1/2 + 1/4 + 1/8 + 1/16 的结果是（ ）。",
                      "15/16", ["1", "7/8", "31/32"],
                      "结合正方形分割图：1 - 1/16 = 15/16。", s + 1),
            _text_q(f"bi:{node_key}:sa:{s}", node_key, "hard", "short_answer",
                    f"解决问题：餐桌拼摆规律：1 张桌子坐 6 人，2 张拼一起坐 10 人，3 张拼一起坐 14 人（每多 1 张多坐 4 人）。请问 {a + 3} 张桌子拼在一起可以坐多少人？（只填数字）",
                    str(4 * (a + 3) + 2), f"人数 = 4n + 2 = 4 × {a + 3} + 2 = {4 * (a + 3) + 2}（人）。", [f"{4 * (a + 3) + 2}人"]),
        ]

    # G6-M4-4 鸽巢原理（抽屉原理）与行程压轴
    drawers = a + 2
    items = drawers * 2 + 1
    least_guarantee = 2 + 1
    colors = b
    v1, v2 = 50 + a * 5, 40 + b * 5
    t_meet = 3
    dist_all = (v1 + v2) * t_meet
    return [
        _text_q(f"bi:{node_key}:calc:{s}", node_key, "medium", "calculation",
                f"鸽巢原理计算：把 {items} 只鸽子放进 {drawers} 个鸽巢，总有一个鸽巢里至少有（ ）只鸽子。（只填数字）",
                str(least_guarantee), f"{items} ÷ {drawers} = 2 …… 1，至少有 2 + 1 = {least_guarantee}（只）。"),
        _choice_q(f"bi:{node_key}:sc:{s}", node_key, "basic",
                  f"袋子里有红、黄、蓝 {colors if colors == 3 else 3} 种颜色的球各 10 个，闭上眼睛至少摸出（ ）个球，才能保证一定有 2 个球颜色相同。",
                  "4", ["2", "3", "11"],
                  "最不利原则：先把 3 种颜色各摸出 1 个（共 3 个），再摸 1 个必有同色，3 + 1 = 4 个。", s),
        _tf_q(f"bi:{node_key}:tf:{s}", node_key, "basic",
              "判断：任意 13 名同学中，至少有 2 名同学是在同一个月出生的。", True, "一年有 12 个月（12个抽屉），13 ÷ 12 = 1 …… 1，1 + 1 = 2 名。"),
        _text_q(f"bi:{node_key}:fb:{s}", node_key, "medium", "fill_blank",
                f"填空：盒子里有 {colors} 种不同颜色的袜子各 10 只，至少拿出（ ）只才能保证配成一双同色袜子。",
                str(colors + 1), f"最不利情况每种颜色各拿 1 只（{colors}只），再拿 1 只必成双，共 {colors + 1} 只。"),
        _choice_q(f"bi:{node_key}:sc2:{s}", node_key, "medium",
                  "把 7 本书放进 3 个抽屉里，不管怎么放，总有一个抽屉里至少放进（ ）本书。",
                  "3", ["2", "4", "1"], "7 ÷ 3 = 2 …… 1，2 + 1 = 3（本）。", s + 2),
        _text_q(f"bi:{node_key}:sa:{s}", node_key, "hard", "short_answer",
                f"行程压轴：甲、乙两车同时从相距 {dist_all} 千米的两地相对开出，甲车每小时行 {v1} 千米，乙车每小时行 {v2} 千米，经过几小时两车相遇？（只填数字）",
                str(t_meet), f"相遇时间 = 总路程 ÷ 速度和 = {dist_all} ÷ ({v1} + {v2}) = {t_meet}（小时）。", [f"{t_meet}小时"]),
    ]


def _build_g1_node_pool(node_key: str, s: int) -> list[dict[str, Any]]:
    """一年级 16 个节点确定性参数化题目生成器（非选择题标准答案 100% 为纯数字）."""
    a = 2 + (s % 6)          # 2..7
    b = 2 + ((s * 3) % 5)    # 2..6
    c = 3 + ((s * 5) % 5)    # 3..7

    if node_key == "G1-M1-1":
        tot = min(10, a + b)
        left = a - 1
        right = tot - left
        return [
            _text_q(f"bi:{node_key}:calc:{s}", node_key, "basic", "calculation",
                    f"数的分合口算：{tot} 可以分成 {left} 和几？（只填数字）",
                    str(right), f"因为 {left} + {right} = {tot}，所以 {tot} 可以分成 {left} 和 {right}。"),
            _choice_q(f"bi:{node_key}:sc:{s}", node_key, "basic",
                      f"在 0～10 的数字顺序中，排在 {a} 和 {a + 2} 中间的数是（ ）。",
                      str(a + 1), [str(a - 1), str(a + 3), "10"],
                      f"按从小到大顺序数：{a}、{a + 1}、{a + 2}，中间是 {a + 1}。", s),
            _tf_q(f"bi:{node_key}:tf:{s}", node_key, "basic",
                  "判断：盘子里一个桃子也没有，可以用数字“0”来表示。", True, "0 表示一个物体也没有，也可以表示起点。"),
            _text_q(f"bi:{node_key}:fb:{s}", node_key, "medium", "fill_blank",
                    f"填空：把 {a} 和 {10 - a} 合起来是（ ）。",
                    "10", f"{a} 和 {10 - a} 凑成 10。"),
            _choice_q(f"bi:{node_key}:sc2:{s}", node_key, "medium",
                      f"下面各数中，比 {a} 大且比 {a + 2} 小的数是（ ）。",
                      str(a + 1), [str(a), str(a + 2), "0"],
                      f"{a} < {a + 1} < {a + 2}。", s + 1),
            _text_q(f"bi:{node_key}:sa:{s}", node_key, "hard", "short_answer",
                    f"解决问题：妈妈把 {tot} 颗草莓分给姐弟俩，姐姐分到 {left} 颗，弟弟分到几颗？（只填数字）",
                    str(right), f"{tot} 分成 {left} 和 {right}，弟弟分到 {right} 颗。", [f"{right}颗"]),
        ]

    if node_key == "G1-M1-2":
        ones = a
        num = 10 + ones
        return [
            _text_q(f"bi:{node_key}:calc:{s}", node_key, "basic", "calculation",
                    f"根据数的组成直接写得数：10 + {ones} =",
                    str(num), f"1 个十和 {ones} 个一合起来是 {num}。"),
            _choice_q(f"bi:{node_key}:sc:{s}", node_key, "basic",
                      "计数器上从右边起，第一位是个位，第二位是（ ）位。",
                      "十", ["百", "个", "一"],
                      "从右边起第一位是个位，第二位是十位。", s),
            _tf_q(f"bi:{node_key}:tf:{s}", node_key, "basic",
                  "判断：20 里面有 2 个十。", True, "2 个十合起来是 20。"),
            _text_q(f"bi:{node_key}:fb:{s}", node_key, "medium", "fill_blank",
                    f"填空：1 个十和 {ones} 个一合起来是（ ）。",
                    str(num), f"十位是 1，个位是 {ones}，这个数是 {num}。"),
            _choice_q(f"bi:{node_key}:sc2:{s}", node_key, "medium",
                      f"在两位数 {num} 中，十位上的“1”表示（ ）。",
                      "1个十", ["1个一", f"{ones}个一", "10个十"],
                      "十位上的 1 表示 1 个十（即 10）。", s + 1),
            _text_q(f"bi:{node_key}:sa:{s}", node_key, "hard", "short_answer",
                    f"解决问题：一个两位数，十位上是 1，个位上的数比十位上的数大 {ones}，这个两位数是多少？（只填数字）",
                    str(10 + 1 + ones), f"个位是 1 + {ones} = {1 + ones}，这个两位数是 {11 + ones}。"),
        ]

    if node_key == "G1-M1-3":
        tens = a + 1
        ones = b
        num = tens * 10 + ones
        return [
            _text_q(f"bi:{node_key}:calc:{s}", node_key, "basic", "calculation",
                    f"按顺序填数计算：比 {num} 大 1 的数是多少？（只填数字）",
                    str(num + 1), f"{num} 后面的一个数是 {num + 1}。"),
            _choice_q(f"bi:{node_key}:sc:{s}", node_key, "basic",
                      f"比较两位数大小：{tens * 10 + 8} ○ {tens * 10 + 2}，○ 里应填（ ）。",
                      ">", ["<", "=", "无法比较"],
                      "十位相同看个位，8 > 2，所以填“>”。", s),
            _tf_q(f"bi:{node_key}:tf:{s}", node_key, "basic",
                  "判断：100 里面有 10 个十，100 是最小的三位数。", True, "10 个十是一百（100），它是最小的三位数。"),
            _text_q(f"bi:{node_key}:fb:{s}", node_key, "medium", "fill_blank",
                    f"填空：{tens} 个十和 {ones} 个一组成的两位数是（ ）。",
                    str(num), f"{tens} 个十是 {tens * 10}，加上 {ones} 个一是 {num}。"),
            _choice_q(f"bi:{node_key}:sc2:{s}", node_key, "medium",
                      f"与 {tens * 10} 相邻的两个数是（ ）。",
                      f"{tens * 10 - 1} 和 {tens * 10 + 1}",
                      [f"{tens * 10 - 10} 和 {tens * 10 + 10}", f"{tens * 10 + 1} 和 {tens * 10 + 2}", f"{tens * 10 - 2} 和 {tens * 10 - 1}"],
                      f"与一个数相邻的数是比它小 1 和大 1 的数，即 {tens * 10 - 1} 和 {tens * 10 + 1}。", s + 1),
            _text_q(f"bi:{node_key}:sa:{s}", node_key, "hard", "short_answer",
                    f"解决问题：在百数表中，上下相邻两个数相差 10。数字 {num} 正下方那一格的数比它大 10，正下方那个数是多少？（只填数字）",
                    str(num + 10), f"{num} + 10 = {num + 10}。"),
        ]

    if node_key == "G1-M1-4":
        tens = (a + 1) * 10
        ones = b
        tot = tens + ones
        return [
            _text_q(f"bi:{node_key}:calc:{s}", node_key, "basic", "calculation",
                    f"直接写出得数：{tens} + {ones} =",
                    str(tot), f"{a + 1} 个十加 {ones} 个一等于 {tot}。"),
            _choice_q(f"bi:{node_key}:sc:{s}", node_key, "basic",
                      f"计算 {tot} - {ones} 的结果是（ ）。",
                      str(tens), [str(ones), str(tot + ones), str(tens - 10)],
                      f"从 {a + 1} 个十和 {ones} 个一里去掉 {ones} 个一，还剩 {tens}。", s),
            _tf_q(f"bi:{node_key}:tf:{s}", node_key, "basic",
                  f"判断：因为 {tens} + {ones} = {tot}，所以 {tot} - {tens} = {ones}。",
                  True, "根据加减法互逆和数的组成，去掉整十部分就剩个位部分。"),
            _text_q(f"bi:{node_key}:fb:{s}", node_key, "medium", "fill_blank",
                    f"填空：{tot} - {tens} =（ ）。",
                    str(ones), f"{tot} 减去 {tens} 等于 {ones}。"),
            _text_q(f"bi:{node_key}:calc2:{s}", node_key, "medium", "calculation",
                    f"计算：{tot} - {ones} =",
                    str(tens), f"{tot} - {ones} = {tens}。"),
            _text_q(f"bi:{node_key}:sa:{s}", node_key, "hard", "short_answer",
                    f"解决问题：班级图书角原来有 {tens} 本绘本，老师又拿来 {ones} 本，现在一共有多少本绘本？（只填数字）",
                    str(tot), f"{tens} + {ones} = {tot}（本）。", [f"{tot}本"]),
        ]

    if node_key == "G1-M2-1":
        x = a
        y = 10 - a
        z = 2
        return [
            _text_q(f"bi:{node_key}:calc:{s}", node_key, "basic", "calculation",
                    f"直接写出得数：{x} + {y} =",
                    "10", f"{x} + {y} = 10。"),
            _choice_q(f"bi:{node_key}:sc:{s}", node_key, "basic",
                      f"算式 10 - {x} 的得数是（ ）。",
                      str(y), [str(y - 1), str(y + 1), str(x)],
                      f"因为 {x} + {y} = 10，所以 10 - {x} = {y}。", s),
            _tf_q(f"bi:{node_key}:tf:{s}", node_key, "basic",
                  "判断：任何一个数加上 0 或者减去 0，结果都还是原来的数。",
                  True, "0 表示没有增减，任何数加 0 或减 0 都得原数。"),
            _text_q(f"bi:{node_key}:fb:{s}", node_key, "medium", "fill_blank",
                    f"填空：{x} +（ ）= 9。",
                    str(9 - x), f"9 - {x} = {9 - x}。"),
            _text_q(f"bi:{node_key}:calc2:{s}", node_key, "medium", "calculation",
                    f"连加口算：{x} + {z} + 1 =",
                    str(x + z + 1), f"从左往右算：{x} + {z} = {x + z}，再加 1 得 {x + z + 1}。"),
            _text_q(f"bi:{node_key}:sa:{s}", node_key, "hard", "short_answer",
                    f"解决问题：树上原来有 9 只小鸟，先飞走了 {a - 1} 只，又飞走了 2 只，树上还剩几只小鸟？（只填数字）",
                    str(9 - (a - 1) - 2), f"9 - {a - 1} - 2 = {9 - (a - 1) - 2}（只）。", [f"{9 - (a - 1) - 2}只"]),
        ]

    if node_key == "G1-M2-2":
        n1 = 8 if s % 2 == 0 else 9
        need = 10 - n1
        n2 = 3 + (s % 6)
        rem = n2 - need
        ans = n1 + n2
        return [
            _text_q(f"bi:{node_key}:calc:{s}", node_key, "basic", "calculation",
                    f"直接写出得数：{n1} + {n2} =",
                    str(ans), f"用凑十法：{n1} + {need} = 10，10 + {rem} = {ans}。"),
            _choice_q(f"bi:{node_key}:sc:{s}", node_key, "basic",
                      f"用“凑十法”计算 {n1} + {n2} 时，先把 {n2} 分成 {need} 和 {rem}，第一步先算（ ）。",
                      f"{n1} + {need} = 10", [f"10 - {n1} = {need}", f"{n1} + 10 = {n1 + 10}", f"{n2} - {need} = {rem}"],
                      f"看大数 {n1}，拆小数 {n2} 为 {need} 和 {rem}，先凑成 10：{n1} + {need} = 10。", s),
            _tf_q(f"bi:{node_key}:tf:{s}", node_key, "basic",
                  "判断：交换两个加数的位置，7 + 5 和 5 + 7 的得数相同，都等于 12。",
                  True, "交换加数位置，和不变，7 + 5 = 5 + 7 = 12。"),
            _text_q(f"bi:{node_key}:fb:{s}", node_key, "medium", "fill_blank",
                    f"填空：用凑十法算 {n1} + {n2} = {ans} 时，把 {n2} 分成 {need} 和（ ）。",
                    str(rem), f"{n2} 可以分成 {need} 和 {rem}。"),
            _text_q(f"bi:{node_key}:calc2:{s}", node_key, "medium", "calculation",
                    f"口算：7 + {b + 3} =",
                    str(7 + b + 3), f"7 凑 3 得 10，7 + {b + 3} = {7 + b + 3}。"),
            _text_q(f"bi:{node_key}:sa:{s}", node_key, "hard", "short_answer",
                    f"解决问题：小红折了 {n1} 只千纸鹤，小明折了 {n2} 只千纸鹤，他们一共折了多少只？（只填数字）",
                    str(ans), f"{n1} + {n2} = {ans}（只）。", [f"{ans}只"]),
        ]

    if node_key == "G1-M2-3":
        ones = 2 + (s % 5)
        dvd = 10 + ones
        sub = 8 if s % 2 == 0 else 9
        ans = dvd - sub
        return [
            _text_q(f"bi:{node_key}:calc:{s}", node_key, "basic", "calculation",
                    f"直接写出得数：{dvd} - {sub} =",
                    str(ans), f"用破十法：10 - {sub} = {10 - sub}，{10 - sub} + {ones} = {ans}。"),
            _choice_q(f"bi:{node_key}:sc:{s}", node_key, "basic",
                      f"用“破十法”计算 {dvd} - {sub} 时，把 {dvd} 分成 10 和 {ones}，先算 10 - {sub} = {10 - sub}，再算（ ）。",
                      f"{10 - sub} + {ones} = {ans}", [f"10 - {ones} = {10 - ones}", f"{sub} - {ones} = {sub - ones}", f"{ones} - {10 - sub}"],
                      f"破十后剩下的 {10 - sub} 再加上个位上的 {ones}，得 {ans}。", s),
            _tf_q(f"bi:{node_key}:tf:{s}", node_key, "basic",
                  "判断：计算 15 - 8 时，可以用“想加算减法”，想 8 + 7 = 15，所以 15 - 8 = 7。",
                  True, "想加算减法是计算 20 以内退位减法的常用方法。"),
            _text_q(f"bi:{node_key}:fb:{s}", node_key, "medium", "fill_blank",
                    f"填空：因为 {sub} +（ ）= {dvd}，所以 {dvd} - {sub} = {ans}。",
                    str(ans), f"{sub} + {ans} = {dvd}。"),
            _text_q(f"bi:{node_key}:calc2:{s}", node_key, "medium", "calculation",
                    f"口算：{11 + (s % 4)} - 7 =",
                    str(11 + (s % 4) - 7), f"10 - 7 = 3，3 + {1 + (s % 4)} = {11 + (s % 4) - 7}。"),
            _text_q(f"bi:{node_key}:sa:{s}", node_key, "hard", "short_answer",
                    f"解决问题：草地上原来有 {dvd} 只小兔，跑回窝里 {sub} 只，草地上还剩几只小兔？（只填数字）",
                    str(ans), f"{dvd} - {sub} = {ans}（只）。", [f"{ans}只"]),
        ]

    if node_key == "G1-M2-4":
        t1 = (a + 1) * 10
        n_base = t1 + 3
        add_one = b
        return [
            _text_q(f"bi:{node_key}:calc:{s}", node_key, "basic", "calculation",
                    f"整十数口算：{t1} + 20 =",
                    str(t1 + 20), f"{a + 1} 个十加 2 个十是 {t1 + 20}。"),
            _choice_q(f"bi:{node_key}:sc:{s}", node_key, "basic",
                      f"计算两位数加一位数 {t1 + 2} + 5 时，应该先把个位上的（ ）相加。",
                      "2 和 5", [f"{a + 1} 和 5", "2 和 50", f"{t1} 和 5"],
                      "相同数位相加，先把个位上的 2 和 5 相加得 7。", s),
            _tf_q(f"bi:{node_key}:tf:{s}", node_key, "basic",
                  "判断：口算 35 + 8 时，个位 5 + 8 = 13 满十，向十位进 1，得数是 43。",
                  True, "35 + 8 = 30 + (5 + 8) = 30 + 13 = 43。"),
            _text_q(f"bi:{node_key}:fb:{s}", node_key, "medium", "fill_blank",
                    f"填空：{n_base} + {add_one} =（ ）。",
                    str(n_base + add_one), f"个位 3 + {add_one} = {3 + add_one}，加上 {t1} 得 {n_base + add_one}。"),
            _text_q(f"bi:{node_key}:calc2:{s}", node_key, "medium", "calculation",
                    f"退位口算：{t1 + 2} - 5 =",
                    str(t1 + 2 - 5), f"从十位借 1 当十，12 - 5 = 7，加上 {t1 - 10} 得 {t1 + 2 - 5}。"),
            _text_q(f"bi:{node_key}:sa:{s}", node_key, "hard", "short_answer",
                    f"解决问题：果篮里有 {n_base} 个橘子，吃掉了 {add_one} 个，还剩多少个橘子？（只填数字）",
                    str(n_base - add_one), f"{n_base} - {add_one} = {n_base - add_one}（个）。", [f"{n_base - add_one}个"]),
        ]

    if node_key == "G1-M3-1":
        return [
            _choice_q(f"bi:{node_key}:sc:{s}", node_key, "basic",
                      "升国旗行少先队队礼时，我们应该举起（ ）手。",
                      "右", ["左", "两只", "任意一只"],
                      "行少先队队礼要右手五指并拢高举过头顶。", s),
            _tf_q(f"bi:{node_key}:tf:{s}", node_key, "basic",
                  "判断：小芳站在小明的后面，那么小明就站在小芳的前面。",
                  True, "前后是相对的位置关系。"),
            _choice_q(f"bi:{node_key}:sc2:{s}", node_key, "medium",
                      "在学校走廊和上下楼梯时，我们要靠（ ）边走最安全。",
                      "右", ["左", "中间", "随便哪边"],
                      "上下楼梯和走路靠右行是交通与校园安全常识。", s + 1),
            _text_q(f"bi:{node_key}:fb:{s}", node_key, "medium", "fill_blank",
                    f"填空：书架从下往上数共有 {a + 2} 层，最上面一层是第（ ）层。（只填数字）",
                    str(a + 2), f"从下往上数共 {a + 2} 层，最上面就是第 {a + 2} 层。"),
            _text_q(f"bi:{node_key}:calc:{s}", node_key, "basic", "calculation",
                    f"位置计数：一排有 {a + 3} 把椅子，小亮坐在最左边第 1 把椅子上，他的右边还有几把椅子？（只填数字）",
                    str(a + 2), f"{a + 3} - 1 = {a + 2}（把）。"),
            _text_q(f"bi:{node_key}:sa:{s}", node_key, "hard", "short_answer",
                    f"解决问题：这一列同学从前往后数，欢欢排第 {a} 个，她后面还有 {b} 个同学，这一列一共有多少个同学？（只填数字）",
                    str(a + b), f"{a} + {b} = {a + b}（个）。", [f"{a + b}个"]),
        ]

    if node_key == "G1-M3-2":
        c1 = a
        c2 = b
        tot_blocks = c1 + c2
        return [
            _choice_q(f"bi:{node_key}:sc:{s}", node_key, "basic",
                      "魔方有 6 个平平的面，而且每个面都是大小一样的正方形，它的形状是（ ）。",
                      "正方体", ["长方体", "圆柱", "球"],
                      "6 个面都是完全相同的正方形的立体图形是正方体。", s),
            _tf_q(f"bi:{node_key}:tf:{s}", node_key, "basic",
                  "判断：篮球、乒乓球这类“球”没有平平的面，可以向任意方向滚动。",
                  True, "球表面是曲面，能向四面八方滚动。"),
            _choice_q(f"bi:{node_key}:sc2:{s}", node_key, "medium",
                      "上下一样粗，两头是圆圆的、平平的面，放倒能滚动、立着放很稳的立体图形是（ ）。",
                      "圆柱", ["球", "正方体", "长方体"],
                      "圆柱上下两个底面是大小相等的圆，侧面是曲面。", s + 1),
            _text_q(f"bi:{node_key}:fb:{s}", node_key, "medium", "fill_blank",
                    "填空：用完全相同的小正方体拼成一个更大的正方体，至少需要（ ）个小正方体。（只填数字）",
                    "8", "上下两层各 4 个（2×2×2），至少需要 8 个小正方体。"),
            _text_q(f"bi:{node_key}:calc:{s}", node_key, "basic", "calculation",
                    f"数积木计算：搭积木时底层用了 {c1} 个正方体，上层用了 {c2} 个正方体，一共用了几个正方体？（只填数字）",
                    str(tot_blocks), f"{c1} + {c2} = {tot_blocks}（个）。"),
            _text_q(f"bi:{node_key}:sa:{s}", node_key, "hard", "short_answer",
                    f"解决问题：积木盒里有 {c1} 个长方体、{c2} 个正方体和 2 个球，长方体和正方体一共有多少个？（只填数字）",
                    str(tot_blocks), f"{c1} + {c2} = {tot_blocks}（个）。", [f"{tot_blocks}个"]),
        ]

    if node_key == "G1-M3-3":
        w_len = a + 1
        h_len = b
        fig = _rect_grid_figure(w_len, h_len, "方格纸上的平面图形")
        return [
            _choice_q(f"bi:{node_key}:sc:{s}", node_key, "basic",
                      "用正方体积木的一个面在纸上印一印，描出来的平面图形是（ ）。",
                      "正方形", ["长方形", "圆", "三角形"],
                      "正方体的每个面都是正方形。", s),
            _tf_q(f"bi:{node_key}:tf:{s}", node_key, "basic",
                  "判断：一套标准的七巧板共有 7 块板，由 5 个三角形、1 个正方形和 1 个平行四边形组成。",
                  True, "七巧板包含 5 块三角形、1 块正方形和 1 块平行四边形。"),
            _text_q(f"bi:{node_key}:fb:{s}", node_key, "medium", "fill_blank",
                    "看图填空：图中方格纸上的长方形一共有（ ）条边。（只填数字）",
                    "4", "长方形和正方形都有 4 条直直的边。", figure=fig),
            _text_q(f"bi:{node_key}:calc:{s}", node_key, "basic", "calculation",
                    f"图形分割计算：1 张正方形纸沿着对角线对折剪开能剪成 2 个三角形，{a} 张这样的正方形纸能剪成几个三角形？（只填数字）",
                    str(a * 2), f"{a} + {a} = {a * 2}（个）。"),
            _choice_q(f"bi:{node_key}:sc2:{s}", node_key, "medium",
                      "用圆柱的底面在印泥上印一下，印出的平面图形是（ ）。",
                      "圆", ["正方形", "三角形", "平行四边形"],
                      "圆柱上下两个平平的底面都是圆。", s + 1),
            _text_q(f"bi:{node_key}:sa:{s}", node_key, "hard", "short_answer",
                    "解决问题：一副七巧板共有 7 块板，拿走其中的 5 块三角形板后，还剩下几块板？（只填数字）",
                    "2", "7 - 5 = 2（块），剩下 1 块正方形和 1 块平行四边形。"),
        ]

    if node_key == "G1-M3-4":
        hr = 2 + (s % 9)
        yuan = a
        jiao = yuan * 10
        return [
            _text_q(f"bi:{node_key}:fb:{s}", node_key, "basic", "fill_blank",
                    f"填空：钟面上分针长长指着 12，时针短短指着 {hr}，这时是（ ）时。（只填数字）",
                    str(hr), f"分针指 12，时针指 {hr}，就是 {hr} 时整。"),
            _choice_q(f"bi:{node_key}:sc:{s}", node_key, "basic",
                      "人民币单位换算中，1 元等于（ ）角。",
                      "10", ["1", "5", "100"],
                      "1 元 = 10 角，1 角 = 10 分。", s),
            _tf_q(f"bi:{node_key}:tf:{s}", node_key, "basic",
                  "判断：1 张 10 元的人民币可以换 2 张 5 元的人民币。",
                  True, "5 元 + 5 元 = 10 元。"),
            _text_q(f"bi:{node_key}:calc:{s}", node_key, "medium", "calculation",
                    f"元角换算计算：{yuan} 元 =（ ）角。（只填数字）",
                    str(jiao), f"1 元 = 10 角，{yuan} 元 = {jiao} 角。"),
            _choice_q(f"bi:{node_key}:sc2:{s}", node_key, "medium",
                      f"买一块 {b} 角的橡皮，付了 1 元钱（10 角），应该找回（ ）角。",
                      str(10 - b), [str(b), str(10 + b), "1"],
                      f"1 元 = 10 角，10 - {b} = {10 - b}（角）。", s + 1),
            _text_q(f"bi:{node_key}:sa:{s}", node_key, "hard", "short_answer",
                    f"解决问题：一支铅笔 {b} 角，一块尺子 {c} 角，买这两样文具一共要付多少角？（只填数字）",
                    str(b + c), f"{b} + {c} = {b + c}（角）。", [f"{b + c}角"]),
        ]

    if node_key == "G1-M4-1":
        left = a + 3
        right = b + 2
        tot = left + right
        return [
            _text_q(f"bi:{node_key}:calc:{s}", node_key, "basic", "calculation",
                    f"看图列式计算：左边有 {left} 个苹果，右边有 {right} 个苹果，一共有多少个苹果？{left} + {right} =",
                    str(tot), f"求总数用加法：{left} + {right} = {tot}。"),
            _choice_q(f"bi:{node_key}:sc:{s}", node_key, "basic",
                      f"图上大括号下面写着“{tot} 只”，左边有 {left} 只，右边标着“？只”，求右边有几只，列式正确的是（ ）。",
                      f"{tot} - {left}", [f"{tot} + {left}", f"{left} - {right}", f"{tot} + {right}"],
                      f"已知总数 {tot} 和左边部分 {left}，求右边部分用减法：{tot} - {left}。", s),
            _tf_q(f"bi:{node_key}:tf:{s}", node_key, "basic",
                  "判断：根据一幅左右两部分的图（左 6 右 8），可以写出 6+8=14、8+6=14、14-6=8、14-8=6 四道算式。",
                  True, "这就是“一图四式”：两道加法算式和两道减法算式。"),
            _text_q(f"bi:{node_key}:fb:{s}", node_key, "medium", "fill_blank",
                    f"填空：笔袋里和笔袋外一共有 {tot} 支铅笔，笔袋外有 {right} 支，笔袋里有（ ）支。",
                    str(left), f"{tot} - {right} = {left}（支）。"),
            _choice_q(f"bi:{node_key}:sc2:{s}", node_key, "medium",
                      "看图列式时，问号“？”在大括号的尖尖下面，表示求的是（ ）。",
                      "两部分合起来的总数", ["左边的一部分", "右边的一部分", "两部分相差多少"],
                      "问号在大括号下方中间表示求合起来一共是多少，用加法。", s + 1),
            _text_q(f"bi:{node_key}:sa:{s}", node_key, "hard", "short_answer",
                    f"解决问题：荷叶上原来有 {left} 只青蛙，又跳上来 {right} 只，现在荷叶上一共有几只青蛙？（只填数字）",
                    str(tot), f"{left} + {right} = {tot}（只）。", [f"{tot}只"]),
        ]

    if node_key == "G1-M4-2":
        big = 11 + a
        small = 5 + (s % 4)
        diff = big - small
        return [
            _text_q(f"bi:{node_key}:calc:{s}", node_key, "basic", "calculation",
                    f"求相差多少计算：{big} 比 {small} 多几？{big} - {small} =",
                    str(diff), f"{big} - {small} = {diff}。"),
            _choice_q(f"bi:{node_key}:sc:{s}", node_key, "basic",
                      f"红气球有 {big} 个，黄气球有 {small} 个，求“黄气球比红气球少几个”与求“（ ）”是同一个算式。",
                      "红气球比黄气球多几个", ["红气球和黄气球一共几个", "黄气球有几个", "红气球有几个"],
                      "“甲比乙少几”和“乙比甲多几”都表示两数的相差量，用大数减小数。", s),
            _tf_q(f"bi:{node_key}:tf:{s}", node_key, "basic",
                  "判断：求一个数比另一个数多几（或少几），要用减法计算。",
                  True, "比多少求相差数，用大数减去小数。"),
            _text_q(f"bi:{node_key}:fb:{s}", node_key, "medium", "fill_blank",
                    f"填空：{small} 比 {big} 少（ ）。",
                    str(diff), f"{big} - {small} = {diff}。"),
            _choice_q(f"bi:{node_key}:sc2:{s}", node_key, "medium",
                      f"小猴摘了 {big} 个桃，小猪摘了 {small} 个桃，桃子相差（ ）个。",
                      str(diff), [str(big + small), str(small), str(diff + 2)],
                      f"{big} - {small} = {diff}（个）。", s + 1),
            _text_q(f"bi:{node_key}:sa:{s}", node_key, "hard", "short_answer",
                    f"解决问题：跳绳乐考中，小亮跳了 {big} 下，小芳跳了 {small} 下，小芳再跳几下就和小亮同样多？（只填数字）",
                    str(diff), f"相差 {big} - {small} = {diff}（下），再跳 {diff} 下就同样多。", [f"{diff}下"]),
        ]

    if node_key == "G1-M4-3":
        step = 2 if s % 2 == 0 else 3
        start = a
        n4 = start + 3 * step
        return [
            _text_q(f"bi:{node_key}:fb:{s}", node_key, "basic", "fill_blank",
                    f"找规律填数：{start}，{start + step}，{start + 2 * step}，（ ），{start + 4 * step}。",
                    str(n4), f"每次依次加 {step}，{start + 2 * step} + {step} = {n4}。"),
            _choice_q(f"bi:{node_key}:sc:{s}", node_key, "basic",
                      "按图形规律排列：○ △ ○ △ ○ △ ○（ ），括号里应该填（ ）。",
                      "△", ["○", "□", "☆"],
                      "图形按“○ △”两个一组重复排列，○ 后面是 △。", s),
            _tf_q(f"bi:{node_key}:tf:{s}", node_key, "basic",
                  "判断：数列 2，4，6，8，10 的排列规律是后一个数总比前一个数多 2。",
                  True, "这是依次加 2 的双数递增数列。"),
            _text_q(f"bi:{node_key}:calc:{s}", node_key, "medium", "calculation",
                    "倒着数找规律：20，18，16，14，（ ）。括号里应填几？（只填数字）",
                    "12", "每次减 2，14 - 2 = 12。"),
            _choice_q(f"bi:{node_key}:sc2:{s}", node_key, "medium",
                      "小彩旗按“红、黄、蓝、红、黄、蓝……”每 3 面一组重复排列，第 4 面是红色，第 5 面是（ ）色。",
                      "黄", ["红", "蓝", "绿"],
                      "第 4 面是第 2 组第 1 面（红），第 5 面是第 2 组第 2 面（黄）。", s + 1),
            _text_q(f"bi:{node_key}:sa:{s}", node_key, "hard", "short_answer",
                    f"解决问题：小袋鼠跳格子，第 1 次跳到 5，第 2 次跳到 10，第 3 次跳到 15……照这样每次加 5，第 {a} 次跳到数字几？（只填数字）",
                    str(a * 5), f"每次跳 5 格，第 {a} 次跳到 {a * 5}。"),
        ]

    # G1-M4-4 排队问题（第几与有几人）
    front = a
    back = b
    tot_q = front + back + 1
    p1 = 3
    p2 = 9 + (s % 5)
    between = p2 - p1 - 1
    return [
        _text_q(f"bi:{node_key}:calc:{s}", node_key, "basic", "calculation",
                f"排队计算：小华前面有 {front} 人，后面有 {back} 人，加上小华自己，这一队一共有多少人？（只填数字）",
                str(tot_q), f"前面 {front} 人 + 后面 {back} 人 + 自己 1 人 = {tot_q}（人）。"),
        _choice_q(f"bi:{node_key}:sc:{s}", node_key, "basic",
                  f"从前往后数，小明排第 {front + 1}，说明他前面有（ ）人。",
                  str(front), [str(front + 1), str(front + 2), "1"],
                  f"排第 {front + 1}，除去自己，前面有 {front + 1} - 1 = {front}（人）。", s),
        _tf_q(f"bi:{node_key}:tf:{s}", node_key, "basic",
              "判断：求“排第 3 和排第 8 的两人之间有几人”，算式是 8 - 3 - 1 = 4（人）。",
              True, "求两人之间的人数不包含两头的人，所以要再减 1。"),
        _text_q(f"bi:{node_key}:fb:{s}", node_key, "medium", "fill_blank",
                f"填空：小朋友排队做操，小丽排第 {p1}，小刚排第 {p2}，他们两人之间有（ ）人。",
                str(between), f"{p2} - {p1} - 1 = {between}（人）。"),
        _choice_q(f"bi:{node_key}:sc2:{s}", node_key, "medium",
                  "一队小朋友共 10 人，从左往右数小强排第 4，“10 人”和“第 4”分别表示（ ）。",
                  "总数量（几个）和排列位置（第几）",
                  ["都表示总数量", "都表示位置顺序", "小强前面有 10 人"],
                  "“几个”表示物体的多少（基数），“第几”表示其中一个所在的顺序位置（序数）。", s + 1),
        _text_q(f"bi:{node_key}:sa:{s}", node_key, "hard", "short_answer",
                f"解决问题：合唱队站成一排，从左数乐乐排第 {front}，从右数乐乐排第 {back}，这一排一共有多少人？（只填数字）",
                str(front + back - 1), f"乐乐被数了 2 次，总人数 = {front} + {back} - 1 = {front + back - 1}（人）。", [f"{front + back - 1}人"]),
    ]


def _build_g2_node_pool(node_key: str, s: int) -> list[dict[str, Any]]:
    """二年级 16 个节点确定性参数化题目生成器（非选择题标准答案 100% 为纯数字）."""
    a = 2 + (s % 7)          # 2..8
    b = 3 + ((s * 3) % 6)    # 3..8
    c = 4 + ((s * 5) % 5)    # 4..8

    if node_key == "G2-M1-1":
        n1 = 26 + a * 3
        n2 = 17 + b * 2
        sum_v = n1 + n2
        m1 = 72 + a
        m2 = 28 + b
        diff_v = m1 - m2
        return [
            _text_q(f"bi:{node_key}:calc:{s}", node_key, "basic", "calculation",
                    f"列竖式计算：{n1} + {n2} =",
                    str(sum_v), f"个位满十向十位进 1，{n1} + {n2} = {sum_v}。"),
            _choice_q(f"bi:{node_key}:sc:{s}", node_key, "basic",
                      "笔算两位数加减两位数时，相同数位要对齐，从（ ）位算起。",
                      "个", ["十", "百", "高"],
                      "笔算加减法都要相同数位对齐，从个位算起。", s),
            _tf_q(f"bi:{node_key}:tf:{s}", node_key, "basic",
                  "判断：笔算两位数减法时，如果个位不够减，要从十位退 1 当 10 再减。",
                  True, "退位减法法则：个位不够减，从十位退 1 作 10。"),
            _text_q(f"bi:{node_key}:fb:{s}", node_key, "medium", "fill_blank",
                    f"填空：比 {n1} 多 {n2} 的数是（ ）。",
                    str(sum_v), f"{n1} + {n2} = {sum_v}。"),
            _text_q(f"bi:{node_key}:calc2:{s}", node_key, "medium", "calculation",
                    f"退位减法计算：{m1} - {m2} =",
                    str(diff_v), f"{m1} - {m2} = {diff_v}。"),
            _text_q(f"bi:{node_key}:sa:{s}", node_key, "hard", "short_answer",
                    f"解决问题：手工课上小红折了 {m1} 颗幸运星，小刚比小红少折 {m2} 颗，小刚折了多少颗幸运星？（只填数字）",
                    str(diff_v), f"{m1} - {m2} = {diff_v}（颗）。", [f"{diff_v}颗"]),
        ]

    if node_key == "G2-M1-2":
        x = 20 + a
        y = 15 + b
        z = 10 + c
        res_add = x + y + z
        res_paren = 80 - (y + z)
        return [
            _text_q(f"bi:{node_key}:calc:{s}", node_key, "basic", "calculation",
                    f"连加计算：{x} + {y} + {z} =",
                    str(res_add), f"{x} + {y} + {z} = {res_add}。"),
            _choice_q(f"bi:{node_key}:sc:{s}", node_key, "basic",
                      f"计算带有小括号的算式 80 - ({y} + {z}) 时，应该先算（ ）。",
                      f"{y} + {z}", [f"80 - {y}", f"80 - {z}", "从左往右算"],
                      "算式里有小括号的，要先算小括号里面的。", s),
            _tf_q(f"bi:{node_key}:tf:{s}", node_key, "basic",
                  "判断：计算 72 - 18 - 22 时，可以先算 18 + 22 = 40，再算 72 - 40 = 32。",
                  True, "连续减去两个数，等于减去这两个数的和。"),
            _text_q(f"bi:{node_key}:fb:{s}", node_key, "medium", "fill_blank",
                    f"填空：80 - ({y} + {z}) =（ ）。",
                    str(res_paren), f"先算括号内 {y + z}，再算 80 - {y + z} = {res_paren}。"),
            _text_q(f"bi:{node_key}:calc2:{s}", node_key, "medium", "calculation",
                    f"加减混合计算：60 - {x} + {z} =",
                    str(60 - x + z), f"60 - {x} = {60 - x}，再加 {z} 得 {60 - x + z}。"),
            _text_q(f"bi:{node_key}:sa:{s}", node_key, "hard", "short_answer",
                    f"解决问题：公交车上原来有 50 人，到站后下车 {x} 人，又上车 {y} 人，现在车上有多少人？（只填数字）",
                    str(50 - x + y), f"50 - {x} + {y} = {50 - x + y}（人）。", [f"{50 - x + y}人"]),
        ]

    if node_key == "G2-M1-3":
        m = 3 + (s % 4)
        n = 4 + ((s * 2) % 3)
        prod = m * n
        return [
            _text_q(f"bi:{node_key}:calc:{s}", node_key, "basic", "calculation",
                    f"用乘法口诀直接写出得数：{m} × {n} =",
                    str(prod), f"{m} × {n} = {prod}。"),
            _choice_q(f"bi:{node_key}:sc:{s}", node_key, "basic",
                      f"把相同加数连加算式 {m} + {m} + {m} + {m} 改写成乘法算式是（ ）。",
                      f"{m} × 4", [f"{m} + 4", f"{m} × 3", "4 + 4"],
                      f"4 个 {m} 相加可以写成 {m} × 4 或 4 × {m}。", s),
            _tf_q(f"bi:{node_key}:tf:{s}", node_key, "basic",
                  "判断：求几个相同加数的和，用乘法计算比较简便。",
                  True, "乘法是求几个相同加数和的简便运算。"),
            _text_q(f"bi:{node_key}:fb:{s}", node_key, "medium", "fill_blank",
                    "填空：根据乘法口诀“四六二十四”，4 × 6 =（ ）。",
                    "24", "四六二十四，4 × 6 = 24。"),
            _choice_q(f"bi:{node_key}:sc2:{s}", node_key, "medium",
                      "乘法口诀“五五二十五”可以写出（ ）道乘法算式。",
                      "1", ["2", "3", "4"],
                      "两个乘数相同（都是 5），只能写出 5 × 5 = 25 这 1 道乘法算式。", s + 1),
            _text_q(f"bi:{node_key}:sa:{s}", node_key, "hard", "short_answer",
                    f"解决问题：游乐园每艘小船坐 {m} 人，{n} 艘这样的小船一共可以坐多少人？（只填数字）",
                    str(prod), f"{m} × {n} = {prod}（人）。", [f"{prod}人"]),
        ]

    if node_key == "G2-M1-4":
        m = 7 + (s % 3)
        n = 3 + (s % 6)
        prod = m * n
        return [
            _text_q(f"bi:{node_key}:calc:{s}", node_key, "basic", "calculation",
                    f"直接写出得数：{m} × {n} =",
                    str(prod), f"根据乘法口诀，{m} × {n} = {prod}。"),
            _choice_q(f"bi:{node_key}:sc:{s}", node_key, "basic",
                      "计算 8 × 9 和 9 × 8 时，用到的乘法口诀是（ ）。",
                      "八九七十二", ["七九六十三", "八八六十四", "九九八十一"],
                      "8 × 9 = 72 和 9 × 8 = 72 都用“八九七十二”。", s),
            _tf_q(f"bi:{node_key}:tf:{s}", node_key, "basic",
                  f"判断：求 {n} 的 {m} 倍是多少，就是求 {m} 个 {n} 是多少，列式为 {n} × {m} = {prod}。",
                  True, "求一个数的几倍是多少用乘法。"),
            _text_q(f"bi:{node_key}:fb:{s}", node_key, "medium", "fill_blank",
                    f"填空：{n} 的 {m} 倍是（ ）。",
                    str(prod), f"{n} × {m} = {prod}。"),
            _text_q(f"bi:{node_key}:calc2:{s}", node_key, "medium", "calculation",
                    f"口算：9 × {a} =",
                    str(9 * a), f"9 × {a} = {9 * a}。"),
            _text_q(f"bi:{node_key}:sa:{s}", node_key, "hard", "short_answer",
                    f"解决问题：一盒彩笔有 {m} 支，买 {n} 盒这样的彩笔一共有多少支？（只填数字）",
                    str(prod), f"{m} × {n} = {prod}（支）。", [f"{prod}支"]),
        ]

    if node_key == "G2-M2-1":
        parts = 3 + (s % 4)
        each = 2 + (s % 5)
        tot = parts * each
        return [
            _text_q(f"bi:{node_key}:calc:{s}", node_key, "basic", "calculation",
                    f"平均分计算：{tot} ÷ {parts} =",
                    str(each), f"把 {tot} 平均分成 {parts} 份，每份是 {each}。"),
            _choice_q(f"bi:{node_key}:sc:{s}", node_key, "basic",
                      f"在除法算式 {tot} ÷ {parts} = {each} 中，被除数是（ ）。",
                      str(tot), [str(parts), str(each), "÷"],
                      f"除号前面的数叫被除数（{tot}），除号后面的数叫除数（{parts}），得数叫商（{each}）。", s),
            _tf_q(f"bi:{node_key}:tf:{s}", node_key, "basic",
                  "判断：把 12 颗糖分给 3 个小朋友，每人一定分到 4 颗。",
                  False, "题目没有说“平均分”，只有平均分时每人才一定分得 4 颗。"),
            _text_q(f"bi:{node_key}:fb:{s}", node_key, "medium", "fill_blank",
                    f"填空：把 {tot} 个苹果平均放在 {parts} 个盘子里，每个盘子放（ ）个。",
                    str(each), f"{tot} ÷ {parts} = {each}（个）。"),
            _choice_q(f"bi:{node_key}:sc2:{s}", node_key, "medium",
                      "在数学上，每份分得（ ），叫做平均分。",
                      "同样多", ["不一样多", "越多越好", "至少1个"],
                      "每份分得同样多叫平均分。", s + 1),
            _text_q(f"bi:{node_key}:sa:{s}", node_key, "hard", "short_answer",
                    f"解决问题：有 {tot} 根竹笋，每只大熊猫分 {each} 根，正好可以分给几只大熊猫？（只填数字）",
                    str(parts), f"{tot} ÷ {each} = {parts}（只）。", [f"{parts}只"]),
        ]

    if node_key == "G2-M2-2":
        div = 4 + (s % 6)
        quot = 3 + ((s * 3) % 6)
        dvd = div * quot
        return [
            _text_q(f"bi:{node_key}:calc:{s}", node_key, "basic", "calculation",
                    f"用乘法口诀求商：{dvd} ÷ {div} =",
                    str(quot), f"想：{div} 乘几等于 {dvd}，因为 {div} × {quot} = {dvd}，所以商是 {quot}。"),
            _choice_q(f"bi:{node_key}:sc:{s}", node_key, "basic",
                      "计算 56 ÷ 7 = 8 时，运用的乘法口诀是（ ）。",
                      "七八五十六", ["六八四十八", "七七四十九", "八八六十四"],
                      "七八五十六对应 56 ÷ 7 = 8 和 56 ÷ 8 = 7。", s),
            _tf_q(f"bi:{node_key}:tf:{s}", node_key, "basic",
                  "判断：根据乘法口诀“六八四十八”，可以写出 48 ÷ 6 = 8 和 48 ÷ 8 = 6 两道除法算式。",
                  True, "两个乘数不同的乘法口诀可以写出两道乘法算式和两道除法算式。"),
            _text_q(f"bi:{node_key}:fb:{s}", node_key, "medium", "fill_blank",
                    f"填空：{dvd} 里面有（ ）个 {div}。",
                    str(quot), f"求 {dvd} 里面有几个 {div}，用除法 {dvd} ÷ {div} = {quot}。"),
            _text_q(f"bi:{node_key}:calc2:{s}", node_key, "medium", "calculation",
                    f"直接写出得数：{dvd} ÷ {quot} =",
                    str(div), f"{dvd} ÷ {quot} = {div}。"),
            _text_q(f"bi:{node_key}:sa:{s}", node_key, "hard", "short_answer",
                    f"解决问题：王老师用 {dvd} 元买同一种钢笔作奖品，每支钢笔 {div} 元，一共可以买多少支？（只填数字）",
                    str(quot), f"{dvd} ÷ {div} = {quot}（支）。", [f"{quot}支"]),
        ]

    if node_key == "G2-M2-3":
        div = 4 + (s % 5)
        quot = 3 + (s % 5)
        rem = 1 + (s % (div - 1))
        dvd = div * quot + rem
        return [
            _text_q(f"bi:{node_key}:calc:{s}", node_key, "basic", "calculation",
                    f"有余数除法计算：{dvd} ÷ {div} = {quot} ……（ ）。括号里的余数是几？（只填数字）",
                    str(rem), f"{div} × {quot} = {div * quot}，{dvd} - {div * quot} = {rem}。"),
            _choice_q(f"bi:{node_key}:sc:{s}", node_key, "basic",
                      f"在有余数的除法算式 □ ÷ {div} = {quot} …… △ 中，余数 △ 最大是（ ）。",
                      str(div - 1), [str(div), str(div + 1), "1"],
                      f"余数必须比除数小，除数是 {div}，余数最大是 {div - 1}。", s),
            _tf_q(f"bi:{node_key}:tf:{s}", node_key, "basic",
                  "判断：在有余数的除法里，余数一定要比除数小。",
                  True, "如果余数大于或等于除数，说明还可以继续分，商小了。"),
            _text_q(f"bi:{node_key}:fb:{s}", node_key, "medium", "fill_blank",
                    f"填空：一个数除以 {div}，商是 {quot}，余数是 {rem}，这个被除数是（ ）。",
                    str(dvd), f"被除数 = 商 × 除数 + 余数 = {quot} × {div} + {rem} = {dvd}。"),
            _choice_q(f"bi:{node_key}:sc2:{s}", node_key, "medium",
                      f"在算式 ○ ÷ △ = 6 …… {div - 1} 中，除数 △ 最小是（ ）。",
                      str(div), [str(div - 1), str(div - 2), str(div + 1)],
                      f"除数要比余数 {div - 1} 大，所以除数最小是 {div}。", s + 1),
            _text_q(f"bi:{node_key}:sa:{s}", node_key, "hard", "short_answer",
                    f"解决问题：有 {dvd} 颗山楂，每 {div} 颗穿成一串糖葫芦，穿成 {quot} 串后还剩几颗山楂？（只填数字）",
                    str(rem), f"{dvd} ÷ {div} = {quot}（串）…… {rem}（颗），还剩 {rem} 颗。", [f"{rem}颗"]),
        ]

    if node_key == "G2-M2-4":
        th = 2 + (s % 7)
        hu = 3 + ((s * 3) % 6)
        ones = 4 + (s % 5)
        num_zero = th * 1000 + ones
        return [
            _text_q(f"bi:{node_key}:calc:{s}", node_key, "basic", "calculation",
                    f"整千数口算：{th * 1000} + 1000 =",
                    str((th + 1) * 1000), f"{th} 个千加 1 个千是 {th + 1} 个千，即 {(th + 1) * 1000}。"),
            _choice_q(f"bi:{node_key}:sc:{s}", node_key, "basic",
                      "10 个一百是（ ），10 个一千是一万。",
                      "1000", ["100", "10000", "10"],
                      "相邻计数单位进率是十，10 个一百是一千（1000）。", s),
            _tf_q(f"bi:{node_key}:tf:{s}", node_key, "basic",
                  "判断：读万以内的数时，中间有一个 0 或连续两个 0，都只读一个“零”；末尾不管有几个 0，都不读。",
                  True, "这是万以内数的读数法则。"),
            _text_q(f"bi:{node_key}:fb:{s}", node_key, "medium", "fill_blank",
                    f"填空：由 {th} 个千和 {ones} 个一组成的四位数写作（ ）。",
                    str(num_zero), f"千位写 {th}，百位和十位用 0 占位，个位写 {ones}，即 {num_zero}。"),
            _choice_q(f"bi:{node_key}:sc2:{s}", node_key, "medium",
                      "一台洗衣机售价 2998 元，它的价格最接近的整千近似数是（ ）元。",
                      "3000", ["2000", "2900", "4000"],
                      "2998 离 3000 只差 2，近似数是 3000。", s + 1),
            _text_q(f"bi:{node_key}:sa:{s}", node_key, "hard", "short_answer",
                    f"解决问题：学校图书馆有科技书 {th * 100} 本，故事书 {hu * 100} 本，这两种书一共有多少本？（只填数字）",
                    str((th + hu) * 100), f"{th * 100} + {hu * 100} = {(th + hu) * 100}（本）。", [f"{(th + hu) * 100}本"]),
        ]

    if node_key == "G2-M3-1":
        m_val = 2 + (s % 6)
        cm_val = m_val * 100
        start_k = 2 + (s % 3)
        end_k = start_k + a + 3
        return [
            _text_q(f"bi:{node_key}:fb:{s}", node_key, "basic", "fill_blank",
                    f"填空：{m_val} 米 =（ ）厘米。",
                    str(cm_val), f"1 米 = 100 厘米，{m_val} 米 = {cm_val} 厘米。"),
            _choice_q(f"bi:{node_key}:sc:{s}", node_key, "basic",
                      "测量教室黑板的长度或操场跑道的长度，通常用（ ）作单位。",
                      "米", ["厘米", "克", "千克"],
                      "测量较长的物体或距离通常用“米”作单位。", s),
            _tf_q(f"bi:{node_key}:tf:{s}", node_key, "basic",
                  "判断：1 米长的木棍和 100 厘米长的铁丝一样长。",
                  True, "1 米 = 100 厘米，长度完全相等。"),
            _text_q(f"bi:{node_key}:calc:{s}", node_key, "medium", "calculation",
                    f"尺子测量计算：一支铅笔左端对齐尺子的刻度 {start_k} 厘米，右端对齐刻度 {end_k} 厘米，这支铅笔长多少厘米？（只填数字）",
                    str(end_k - start_k), f"物体长度 = 终点刻度 - 起点刻度 = {end_k} - {start_k} = {end_k - start_k}（厘米）。"),
            _choice_q(f"bi:{node_key}:sc2:{s}", node_key, "medium",
                      "小学生食指的宽度大约是 1（ ）。",
                      "厘米", ["米", "千克", "千米"],
                      "食指宽、图钉长都大约是 1 厘米。", s + 1),
            _text_q(f"bi:{node_key}:sa:{s}", node_key, "hard", "short_answer",
                    f"解决问题：一根彩带长 1 米，捆扎礼盒用去了 {a * 10} 厘米，还剩多少厘米？（只填数字）",
                    str(100 - a * 10), f"1 米 = 100 厘米，100 - {a * 10} = {100 - a * 10}（厘米）。", [f"{100 - a * 10}厘米"]),
        ]

    if node_key == "G2-M3-2":
        n_sq = b
        fig = _rect_grid_figure(4, 3, "方格纸上的长方形（4个角都是直角）")
        return [
            _text_q(f"bi:{node_key}:fb:{s}", node_key, "basic", "fill_blank",
                    "看图填空：一个角有 1 个顶点和（ ）条直直的边，图中长方形有 4 个直角。（只填数字）",
                    "2", "每个角都由 1 个顶点和 2 条直直的边组成。", figure=fig),
            _choice_q(f"bi:{node_key}:sc:{s}", node_key, "basic",
                      "用三角尺上的直角比一比，比直角小的角是（ ）。",
                      "锐角", ["钝角", "直角", "平角"],
                      "比直角小的角叫锐角，比直角大的角（平角内）叫钝角。", s),
            _tf_q(f"bi:{node_key}:tf:{s}", node_key, "basic",
                  "判断：角的两条边画得越长，这个角就越大。",
                  False, "角的大小只与两条边张开的大小有关，与边的长短无关。"),
            _choice_q(f"bi:{node_key}:sc2:{s}", node_key, "medium",
                      "红领巾上有 3 个角，其中最大的一个角是（ ）。",
                      "钝角", ["直角", "锐角", "不能确定"],
                      "红领巾有 1 个钝角和 2 个锐角。", s + 1),
            _text_q(f"bi:{node_key}:calc:{s}", node_key, "medium", "calculation",
                    f"数直角计算：1 个正方形有 4 个直角，{n_sq} 个独立的正方形一共有多少个直角？（只填数字）",
                    str(n_sq * 4), f"4 × {n_sq} = {n_sq * 4}（个）。"),
            _text_q(f"bi:{node_key}:sa:{s}", node_key, "hard", "short_answer",
                    "解决问题：一副三角尺共有 2 块，每块三角尺上有 1 个直角和 2 个锐角，这副三角尺上一共有多少个锐角？（只填数字）",
                    "4", "2 + 2 = 4（个）。"),
        ]

    if node_key == "G2-M3-3":
        w_len = a + 1
        h_len = b
        fig = _rect_grid_figure(w_len, h_len, "方格纸上的轴对称长方形")
        return [
            _choice_q(f"bi:{node_key}:sc:{s}", node_key, "basic",
                      "推拉抽屉、观光电梯上下直行、升国旗，这些运动都属于（ ）现象。",
                      "平移", ["旋转", "对折", "放大"],
                      "沿直线运动且方向、形状、大小不变的现象是平移。", s),
            _tf_q(f"bi:{node_key}:tf:{s}", node_key, "basic",
                  "判断：大风车转动、直升机螺旋桨转动、钟表指针走动都属于旋转现象。",
                  True, "绕着一个中心点或轴转动的现象叫旋转。"),
            _choice_q(f"bi:{node_key}:sc2:{s}", node_key, "medium",
                      "对折后两边能够完全重合的图形叫做（ ），折痕所在的直线叫对称轴。",
                      "轴对称图形", ["平移图形", "旋转图形", "立体图形"],
                      "沿一条直线对折后两侧完全重合的图形是轴对称图形。", s + 1),
            _text_q(f"bi:{node_key}:fb:{s}", node_key, "medium", "fill_blank",
                    "看图填空：一般长方形（长和宽不相等）是轴对称图形，它有（ ）条对称轴。（只填数字）",
                    "2", "长方形有横、竖 2 条对称轴。", figure=fig),
            _text_q(f"bi:{node_key}:calc:{s}", node_key, "basic", "calculation",
                    f"观察物体计算：1 个正方体有 6 个面，{a} 个独立的正方体一共有多少个面？（只填数字）",
                    str(a * 6), f"6 × {a} = {a * 6}（个）。"),
            _text_q(f"bi:{node_key}:sa:{s}", node_key, "hard", "short_answer",
                    f"解决问题：方格纸上的一枚棋子先向右平移 {a} 格，再继续向右平移 {b} 格，它一共向右平移了多少格？（只填数字）",
                    str(a + b), f"{a} + {b} = {a + b}（格）。", [f"{a + b}格"]),
        ]

    if node_key == "G2-M3-4":
        kg_val = 2 + (s % 6)
        g_val = kg_val * 1000
        big_grids = 3 + (s % 8)
        mins = big_grids * 5
        return [
            _text_q(f"bi:{node_key}:fb:{s}", node_key, "basic", "fill_blank",
                    f"填空：{kg_val} 千克 =（ ）克。",
                    str(g_val), f"1 千克 = 1000 克，{kg_val} 千克 = {g_val} 克。"),
            _choice_q(f"bi:{node_key}:sc:{s}", node_key, "basic",
                      "钟面上有 12 个大格、60 个小格，分针走 1 个大格是（ ）分钟。",
                      "5", ["1", "10", "60"],
                      "分针走 1 小格是 1 分，走 1 大格（5小格）是 5 分。", s),
            _tf_q(f"bi:{node_key}:tf:{s}", node_key, "basic",
                  "判断：1 千克铁和 1000 克棉花一样重。",
                  True, "1 千克 = 1000 克，质量完全相同。"),
            _text_q(f"bi:{node_key}:calc:{s}", node_key, "medium", "calculation",
                    f"钟面时间计算：分针从 12 走到 {big_grids}，走了 {big_grids} 个大格，一共是多少分钟？（只填数字）",
                    str(mins), f"5 × {big_grids} = {mins}（分钟）。"),
            _choice_q(f"bi:{node_key}:sc2:{s}", node_key, "medium",
                      "计量一枚 2 分硬币或一粒花生米的质量，通常用（ ）作单位。",
                      "克", ["千克", "米", "厘米"],
                      "计量比较轻的物品，常用“克”（g）作单位。", s + 1),
            _text_q(f"bi:{node_key}:sa:{s}", node_key, "hard", "short_answer",
                    f"解决问题：妈妈买了 {a * 100} 克蓝莓和 {b * 100} 克草莓，这两样水果一共重多少克？（只填数字）",
                    str((a + b) * 100), f"{a * 100} + {b * 100} = {(a + b) * 100}（克）。", [f"{(a + b) * 100}克"]),
        ]

    if node_key == "G2-M4-1":
        m = 3 + (s % 5)
        n = 4 + (s % 4)
        k = 5 + (s % 6)
        res1 = k + m * n
        res2 = (m + 2) * n
        return [
            _text_q(f"bi:{node_key}:calc:{s}", node_key, "basic", "calculation",
                    f"混合运算：{k} + {m} × {n} =",
                    str(res1), f"先算乘法 {m} × {n} = {m * n}，再加 {k} 得 {res1}。"),
            _choice_q(f"bi:{node_key}:sc:{s}", node_key, "basic",
                      "在没有括号的算式里，如果有乘、除法，又有加、减法，要先算（ ）。",
                      "乘、除法", ["加、减法", "从左往右按顺序", "随便哪一步"],
                      "两级混合运算顺序：先乘除，后加减。", s),
            _tf_q(f"bi:{node_key}:tf:{s}", node_key, "basic",
                  f"判断：算式 ({m} + 2) × {n} 和 {m} + 2 × {n} 的计算结果相同。",
                  False, "带小括号的先算加法，不带括号的先算乘法，结果不同。"),
            _text_q(f"bi:{node_key}:fb:{s}", node_key, "medium", "fill_blank",
                    f"填空：({m} + 2) × {n} =（ ）。",
                    str(res2), f"先算括号内 {m} + 2 = {m + 2}，再乘 {n} 得 {res2}。"),
            _text_q(f"bi:{node_key}:calc2:{s}", node_key, "medium", "calculation",
                    f"计算：{m * n} ÷ {m} + {k} =",
                    str(n + k), f"先算除法 {m * n} ÷ {m} = {n}，再加 {k} 得 {n + k}。"),
            _text_q(f"bi:{node_key}:sa:{s}", node_key, "hard", "short_answer",
                    f"解决问题：烘焙社烤了 50 块饼干，分给 {m} 个小队，每小队分 {n} 块，还剩多少块饼干？（只填数字）",
                    str(50 - m * n), f"50 - {m} × {n} = {50 - m * n}（块）。", [f"{50 - m * n}块"]),
        ]

    if node_key == "G2-M4-2":
        cap = 4 + (s % 3)
        full_boats = 4 + (s % 4)
        rem = 1 + (s % (cap - 1))
        stu = cap * full_boats + rem
        need_boats = full_boats + 1
        return [
            _text_q(f"bi:{node_key}:calc:{s}", node_key, "basic", "calculation",
                    f"租船问题计算：{stu} 名同学去划船，每条船最多坐 {cap} 人，至少要租几条船？（只填数字）",
                    str(need_boats), f"{stu} ÷ {cap} = {full_boats}（条）…… {rem}（人），余下的 {rem} 人也要租 1 条船，共 {need_boats} 条。"),
            _choice_q(f"bi:{node_key}:sc:{s}", node_key, "basic",
                      "解决租船、租车、装油桶这类“至少需要几个”的问题时，余下的人或物不够装满 1 份也要再加 1，这种方法叫（ ）。",
                      "进一法", ["去尾法", "四舍五入", "退位法"],
                      "余数无论多小都要多加 1 个单位，叫进一法。", s),
            _tf_q(f"bi:{node_key}:tf:{s}", node_key, "basic",
                  "判断：小亮有 22 元钱，每本笔记本 5 元，因为 22 ÷ 5 = 4（本）…… 2（元），剩下的 2 元不够买 1 本，所以最多能买 4 本。",
                  True, "买东西钱不够买最后 1 件时要舍去余数（去尾法）。"),
            _text_q(f"bi:{node_key}:fb:{s}", node_key, "medium", "fill_blank",
                    f"填空：有 {stu} 朵玫瑰花，每 {cap} 朵扎成一束，最多可以扎成（ ）束。",
                    str(full_boats), f"{stu} ÷ {cap} = {full_boats}（束）…… {rem}（朵），余下的不够扎 1 束，最多扎 {full_boats} 束。"),
            _choice_q(f"bi:{node_key}:sc2:{s}", node_key, "medium",
                      "彩灯按“红、黄、蓝”每 3 盏一组循环排列，第 14 盏彩灯是（ ）色。",
                      "黄", ["红", "蓝", "紫"],
                      "14 ÷ 3 = 4（组）…… 2（盏），余数是 2，对应每组的第 2 盏黄色。", s + 1),
            _text_q(f"bi:{node_key}:sa:{s}", node_key, "hard", "short_answer",
                    f"解决问题：珠子按“1颗黑、2颗白”每 3 颗一组重复穿成手链，穿了完整的 {full_boats} 组，一共有多少颗白珠子？（只填数字）",
                    str(full_boats * 2), f"每组有 2 颗白珠子，{full_boats} × 2 = {full_boats * 2}（颗）。", [f"{full_boats * 2}颗"]),
        ]

    if node_key == "G2-M4-3":
        d1 = 1 + (s % 3)
        d2 = 4 + (s % 3)
        d3 = 7 + (s % 3)
        tops = 2 + (s % 3)
        pants = 3 + (s % 3)
        ways = tops * pants
        return [
            _text_q(f"bi:{node_key}:calc:{s}", node_key, "basic", "calculation",
                    f"搭配计算：衣柜里有 {tops} 件不同的上衣和 {pants} 条不同的裤子，1 件上衣配 1 条裤子，一共有多少种不同的穿法？（只填数字）",
                    str(ways), f"{tops} × {pants} = {ways}（种）。"),
            _choice_q(f"bi:{node_key}:sc:{s}", node_key, "basic",
                      f"用数字卡片 {d1} 和 {d2} 摆出十位和个位不相同的两位数，一共能摆出（ ）个。",
                      "2", ["1", "3", "4"],
                      f"可以摆出 {d1}{d2} 和 {d2}{d1}，共 2 个。", s),
            _tf_q(f"bi:{node_key}:tf:{s}", node_key, "basic",
                  "判断：用 0、3、6 三张卡片组成没有重复数字的两位数，因为 0 不能放在十位，所以只能组成 4 个两位数。",
                  True, "十位只能放 3 或 6（2种），每种对应个位 2 种，共 2 × 2 = 4 个（30、36、60、63）。"),
            _text_q(f"bi:{node_key}:fb:{s}", node_key, "medium", "fill_blank",
                    f"填空：用 {d1}、{d2}、{d3} 这三张非零数字卡片组成十位和个位不同的两位数，一共能组成（ ）个。",
                    "6", "固定十位有 3 种选法，个位有 2 种选法，3 × 2 = 6（个）。"),
            _choice_q(f"bi:{node_key}:sc2:{s}", node_key, "medium",
                      "3 个好朋友见面，每两个人握一次手，一共要握（ ）次手。",
                      "3", ["2", "6", "4"],
                      "握手的顺序无关，甲-乙、甲-丙、乙-丙共 3 次。", s + 1),
            _text_q(f"bi:{node_key}:sa:{s}", node_key, "hard", "short_answer",
                    f"解决问题：用 {d1}、{d2}、{d3} 三张卡片组成没有重复数字的两位数，其中最大的两位数是多少？（只填数字）",
                    str(d3 * 10 + d2), f"十位选最大的 {d3}，个位选次大的 {d2}，最大两位数是 {d3 * 10 + d2}。"),
        ]

    # G2-M4-4 简单逻辑推理（排除法与方格填数）
    missing = 1 + (s % 4)
    present = [x for x in (1, 2, 3, 4) if x != missing]
    return [
        _text_q(f"bi:{node_key}:fb:{s}", node_key, "basic", "fill_blank",
                f"方格填数：在 4×4 的四宫格中，每行、每列都有 1～4 这四个数且不重复。某一行已经出现了 {present[0]}、{present[1]}、{present[2]}，这一行剩下的空格应填（ ）。",
                str(missing), f"1、2、3、4 中只缺 {missing}，所以填 {missing}。"),
        _choice_q(f"bi:{node_key}:sc:{s}", node_key, "basic",
                  "小狗、小猫、小兔比赛拍球，分别拍了 30 下、25 下、20 下。小狗说：“我拍得最多。”小猫说：“我拍的不是最少的。”那么小兔拍了（ ）下。",
                  "20", ["25", "30", "35"],
                  "小狗最多是 30 下，小猫不是最少则是 25 下，剩下的小兔拍了 20 下。", s),
        _tf_q(f"bi:{node_key}:tf:{s}", node_key, "basic",
              "判断：在解决四宫格填数问题时，应该先看哪一个空格所在的行和列已经出现了 3 个不同的数，就能直接确定这个空格填几。",
              True, "所在行列已有 3 个不同数字时，排除这 3 个数即可唯一确定第 4 个数。"),
        _text_q(f"bi:{node_key}:calc:{s}", node_key, "medium", "calculation",
                f"推理计算：1 + 2 + 3 + 4 = 10。如果四宫格某一列前三个数分别是 {present[0]}、{present[1]}、{present[2]}，用 10 减去前三个数的和，第四个数是几？（只填数字）",
                str(missing), f"10 - ({present[0]} + {present[1]} + {present[2]}) = {missing}。"),
        _choice_q(f"bi:{node_key}:sc2:{s}", node_key, "medium",
                  "欢欢、乐乐和奇奇三人分别拿着语文、数学、音乐三本书。欢欢拿的不是语文书，乐乐拿的是数学书，那么欢欢拿的是（ ）书。",
                  "音乐", ["语文", "数学", "美术"],
                  "乐乐拿数学书，欢欢拿的不是语文也不是数学，所以欢欢拿的是音乐书。", s + 1),
        _text_q(f"bi:{node_key}:sa:{s}", node_key, "hard", "short_answer",
                f"解决问题：红、黄、蓝三个盒子里分别放着 {a} 个、{a + 2} 个、{a + 5} 个玻璃球。已知红盒比蓝盒多，黄盒里的玻璃球既不是最多的也不是最少的，请问黄盒里放了几个玻璃球？（只填数字）",
                str(a + 2), f"黄盒不是最多也不是最少，所以是中间数 {a + 2} 个。"),
    ]


def build_grade_node_pool(node_key: str, seed: int) -> list[dict[str, Any]]:
    """根据 G1 / G2 / G3 / G4 / G6 节点编码分发生成 6 道确定性参数化题目."""
    s = abs(int(seed))
    k = str(node_key or "").strip().upper()
    if k.startswith("G1-"):
        return _build_g1_node_pool(k, s)
    if k.startswith("G2-"):
        return _build_g2_node_pool(k, s)
    if k.startswith("G3-"):
        return _build_g3_node_pool(k, s)
    if k.startswith("G4-"):
        return _build_g4_node_pool(k, s)
    if k.startswith("G6-"):
        return _build_g6_node_pool(k, s)
    return []


__all__ = [
    "GRADE_MATH_MAPS",
    "GRADE_VISUAL_NODE_MAP",
    "MATH_G1_CORE_MAP",
    "MATH_G1_SPRINTS",
    "MATH_G2_CORE_MAP",
    "MATH_G2_SPRINTS",
    "MATH_G3_CORE_MAP",
    "MATH_G3_SPRINTS",
    "MATH_G4_CORE_MAP",
    "MATH_G4_SPRINTS",
    "MATH_G6_CORE_MAP",
    "MATH_G6_SPRINTS",
    "build_grade_node_pool",
    "get_grade_math_map",
]
