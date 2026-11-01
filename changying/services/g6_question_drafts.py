"""六年级上册题目草稿（可程序验算）。

每个知识点 6 题：基础 2、中等 2、提高 2。分数一律用假分数表示（如 5/4），
圆的计算统一取 π=3.14，面积/周长保留两位小数。需要画图的节点（确定位置、圆的设计）
与纯情境节点（体育中的数学、水是生命之源）不自动出题。
"""
from __future__ import annotations

from fractions import Fraction
from typing import Any

PI = Fraction(314, 100)


def _f(v: Fraction) -> str:
    return str(v)


def _q(text: str, answer: str, level: str, check: dict[str, Any]) -> dict[str, Any]:
    return {"text": text, "answer": answer, "level": level, "verify": check}


def _mul_int(a: Fraction, n: int, level: str) -> dict[str, Any]:
    return _q(f"{a} × {n} = ____", _f(a * n), level, {"op": "mul_int", "a": str(a), "n": n})


def _mul_frac(a: Fraction, b: Fraction, level: str) -> dict[str, Any]:
    return _q(f"{a} × {b} = ____", _f(a * b), level, {"op": "mul_frac", "a": str(a), "b": str(b)})


def _div_int(a: Fraction, n: int, level: str) -> dict[str, Any]:
    return _q(f"{a} ÷ {n} = ____", _f(a / n), level, {"op": "div_int", "a": str(a), "n": n})


def _div_frac(a: Fraction, b: Fraction, level: str) -> dict[str, Any]:
    return _q(f"{a} ÷ {b} = ____", _f(a / b), level, {"op": "div_frac", "a": str(a), "b": str(b)})


def _recip(a: Fraction, level: str) -> dict[str, Any]:
    return _q(f"{a} 的倒数是 ____", _f(1 / a), level, {"op": "recip", "a": str(a)})


def _circle_c(r: int, level: str) -> dict[str, Any]:
    value = 2 * PI * r
    return _q(f"半径 {r} 厘米的圆，周长是多少厘米？（π 取 3.14）", f"{float(value):.2f}", level,
              {"op": "circle_c", "r": r})


def _circle_s(r: int, level: str) -> dict[str, Any]:
    value = PI * r * r
    return _q(f"半径 {r} 厘米的圆，面积是多少平方厘米？（π 取 3.14）", f"{float(value):.2f}", level,
              {"op": "circle_s", "r": r})


def _ring_s(big: int, small: int, level: str) -> dict[str, Any]:
    value = PI * (big * big - small * small)
    return _q(f"外圆半径 {big} 厘米、内圆半径 {small} 厘米的圆环，面积是多少平方厘米？（π 取 3.14）",
              f"{float(value):.2f}", level, {"op": "ring_s", "big": big, "small": small})


def _percent_of(x: Fraction, p: int, level: str) -> dict[str, Any]:
    return _q(f"{x} 的 {p}% 是多少？", _f(x * Fraction(p, 100)), level, {"op": "percent_of", "x": str(x), "p": p})


def _discount(price: int, zhe: int, level: str) -> dict[str, Any]:
    value = Fraction(price * zhe, 10)
    return _q(f"一件商品原价 {price} 元，打 {zhe} 折后多少元？", _f(value), level,
              {"op": "discount", "price": price, "zhe": zhe})


def _interest(principal: int, rate: int, years: int, level: str) -> dict[str, Any]:
    value = Fraction(principal * rate * years, 100)
    return _q(f"存入 {principal} 元，年利率 {rate}%，{years} 年的利息是多少元？", _f(value), level,
              {"op": "interest", "principal": principal, "rate": rate, "years": years})


def _expr(text: str, value: Fraction, level: str, check: dict[str, Any]) -> dict[str, Any]:
    return _q(f"{text} = ____", _f(value), level, check)


def build_drafts() -> dict[str, list[dict[str, Any]]]:
    """返回 {知识点名称: [6 道题]}，名称与六年级地图节点的 name 一致。"""
    return {
        "分数乘整数": [
            _mul_int(Fraction(3, 4), 2, "basic"),
            _mul_int(Fraction(2, 5), 3, "basic"),
            _mul_int(Fraction(5, 6), 4, "medium"),
            _mul_int(Fraction(7, 9), 3, "medium"),
            _q("每米重 3/8 千克，4 米重多少千克？", "3/2", "hard",
               {"op": "mul_int", "a": "3/8", "n": 4}),
            _q("一袋糖重 5/7 千克，3 袋共重多少千克？", "15/7", "hard",
               {"op": "mul_int", "a": "5/7", "n": 3}),
        ],
        "一个数乘分数": [
            _mul_frac(Fraction(1, 2), Fraction(2, 3), "basic"),
            _mul_frac(Fraction(3, 5), Fraction(5, 6), "basic"),
            _q("12 的 3/4 是多少？", "9", "medium", {"op": "mul_int", "a": "12", "n": 3, "div": 4}),
            _mul_frac(Fraction(4, 9), Fraction(3, 8), "medium"),
            _q("一根绳子长 5/6 米，用去它的 3/5，用去多少米？", "1/2", "hard",
               {"op": "mul_frac", "a": "5/6", "b": "3/5"}),
            _q("一本书 60 页，已经看了全书的 2/5，看了多少页？", "24", "hard",
               {"op": "mul_int", "a": "60", "n": 2, "div": 5}),
        ],
        "分数、小数混合运算及运算律": [
            _expr("1/2 × 0.4", Fraction(1, 5), "basic", {"op": "expr", "text": "1/2 × 0.4"}),
            _expr("0.25 + 3/4", Fraction(1), "basic", {"op": "expr", "text": "0.25 + 3/4"}),
            _expr("(1/3 + 1/6) × 6", Fraction(3), "medium", {"op": "expr", "text": "(1/3 + 1/6) × 6"}),
            _expr("5/8 × 4 + 3/8 × 4", Fraction(4), "medium", {"op": "expr", "text": "5/8 × 4 + 3/8 × 4"}),
            _expr("7/9 × 0.6 + 2/9 × 0.6", Fraction(3, 5), "hard", {"op": "expr", "text": "7/9 × 0.6 + 2/9 × 0.6"}),
            _expr("(1 - 2/5) × 0.5", Fraction(3, 10), "hard", {"op": "expr", "text": "(1 - 2/5) × 0.5"}),
        ],
        "倒数的认识": [
            _recip(Fraction(3, 4), "basic"),
            _recip(Fraction(5), "basic"),
            _recip(Fraction(1, 7), "medium"),
            _recip(Fraction(9, 2), "medium"),
            _q("一个数与它的倒数相乘，积是多少？", "1", "hard", {"op": "recip_product"}),
            _q("最小的质数的倒数是多少？", "1/2", "hard", {"op": "recip", "a": "2"}),
        ],
        "一个数除以整数": [
            _div_int(Fraction(4, 5), 2, "basic"),
            _div_int(Fraction(6, 7), 3, "basic"),
            _div_int(Fraction(9, 10), 3, "medium"),
            _div_int(Fraction(8, 15), 4, "medium"),
            _q("3/4 千米平均分成 3 段，每段多少千米？", "1/4", "hard", {"op": "div_int", "a": "3/4", "n": 3}),
            _q("把 5/6 升水平均倒进 5 个杯子，每杯多少升？", "1/6", "hard", {"op": "div_int", "a": "5/6", "n": 5}),
        ],
        "一个数除以分数": [
            _div_frac(Fraction(3, 4), Fraction(1, 2), "basic"),
            _div_frac(Fraction(5, 6), Fraction(5, 12), "basic"),
            _div_frac(Fraction(7, 8), Fraction(7, 16), "medium"),
            _div_frac(Fraction(2), Fraction(4, 5), "medium"),
            _q("有多少个 2/3 相加等于 2？", "3", "hard", {"op": "div_frac", "a": "2", "b": "2/3"}),
            _q("一根木料长 9/10 米，每 3/20 米锯一段，可以锯几段？", "6", "hard",
               {"op": "div_frac", "a": "9/10", "b": "3/20"}),
        ],
        "解决问题（分数除法）": [
            _q("一个数的 2/3 是 8，这个数是多少？", "12", "basic", {"op": "div_frac", "a": "8", "b": "2/3"}),
            _q("一个数的 3/5 是 9，这个数是多少？", "15", "basic", {"op": "div_frac", "a": "9", "b": "3/5"}),
            _q("一本书看了 2/5，正好 40 页，全书多少页？", "100", "medium",
               {"op": "div_frac", "a": "40", "b": "2/5"}),
            _q("一桶油用去 3/8，正好 12 千克，这桶油原有多少千克？", "32", "medium",
               {"op": "div_frac", "a": "12", "b": "3/8"}),
            _q("男生人数是女生的 4/5，男生 20 人，女生多少人？", "25", "hard",
               {"op": "div_frac", "a": "20", "b": "4/5"}),
            _q("一件商品打八折后 200 元，原价多少元？", "250", "hard",
               {"op": "discount_reverse", "price": 200, "zhe": 8}),
        ],
        "圆的周长": [
            _circle_c(2, "basic"),
            _circle_c(5, "basic"),
            _circle_c(10, "medium"),
            _q("直径 8 厘米的圆，周长是多少厘米？（π 取 3.14）", "25.12", "medium",
               {"op": "circle_c_d", "d": 8}),
            _q("一个圆的周长是 31.4 厘米，它的直径是多少厘米？（π 取 3.14）", "10.00", "hard",
               {"op": "circle_d_from_c", "c": 31.4}),
            _q("一棵树树干周长 1.57 米，它的直径是多少米？（π 取 3.14）", "0.50", "hard",
               {"op": "circle_d_from_c", "c": 1.57}),
        ],
        "圆的面积（1）": [
            _circle_s(2, "basic"),
            _circle_s(3, "basic"),
            _circle_s(10, "medium"),
            _q("直径 6 厘米的圆，面积是多少平方厘米？（π 取 3.14）", "28.26", "medium",
               {"op": "circle_s_d", "d": 6}),
            _q("一个圆的半径扩大 2 倍，面积扩大几倍？", "4", "hard", {"op": "circle_scale", "k": 2}),
            _q("周长 12.56 厘米的圆，面积是多少平方厘米？（π 取 3.14）", "12.56", "hard",
               {"op": "circle_s_from_c", "c": 12.56}),
        ],
        "圆的面积（2）": [
            _ring_s(4, 2, "basic"),
            _ring_s(5, 3, "basic"),
            _ring_s(10, 6, "medium"),
            _q("半径 4 厘米的半圆，面积是多少平方厘米？（π 取 3.14）", "25.12", "medium",
               {"op": "semicircle_s", "r": 4}),
            _q("外圆直径 10 厘米、内圆直径 6 厘米的圆环，面积是多少平方厘米？（π 取 3.14）", "50.24", "hard",
               {"op": "ring_s", "big": 5, "small": 3}),
            _q("边长 6 厘米的正方形里剪一个最大的圆，剩下多少平方厘米？（π 取 3.14）", "7.74", "hard",
               {"op": "square_minus_circle", "side": 6}),
        ],
        "百分数的意义（2）": [
            _q("把 0.45 化成百分数。", "45%", "basic", {"op": "to_percent", "value": "0.45"}),
            _q("把 3/4 化成百分数。", "75%", "basic", {"op": "to_percent", "value": "3/4"}),
            _q("把 60% 化成小数。", "0.6", "medium", {"op": "to_decimal", "value": 60}),
            _q("把 12% 化成最简分数。", "3/25", "medium", {"op": "to_fraction", "value": 12}),
            _percent_of(Fraction(80), 25, "hard"),
            _percent_of(Fraction(120), 15, "hard"),
        ],
        "折扣": [
            _discount(100, 8, "basic"),
            _discount(200, 9, "basic"),
            _discount(350, 7, "medium"),
            _discount(480, 6, "medium"),
            _q("一台电视原价 2400 元，打八五折后多少元？", "2040", "hard",
               {"op": "discount_rate", "price": 2400, "rate": 85}),
            _q("一本书打七折后 21 元，原价多少元？", "30", "hard",
               {"op": "discount_reverse", "price": 21, "zhe": 7}),
        ],
        "利率": [
            _interest(1000, 3, 1, "basic"),
            _interest(2000, 2, 3, "basic"),
            _interest(5000, 4, 2, "medium"),
            _interest(8000, 3, 5, "medium"),
            _q("存入 10000 元，年利率 2.75%，2 年后一共可取回多少元（不含税）？", "10550", "hard",
               {"op": "interest_total", "principal": 10000, "rate": "2.75", "years": 2}),
            _q("存入 3000 元，一年后取回本息 3060 元，年利率是多少？", "2%", "hard",
               {"op": "rate_from", "principal": 3000, "interest": 60}),
        ],
        "生活中的负数": [
            _q("零上 5 摄氏度记作 +5℃，零下 3 摄氏度记作多少？", "-3", "basic", {"op": "int", "value": -3}),
            _q("比 0 小 2 的数是 ____", "-2", "basic", {"op": "int", "value": -2}),
            _q("某天最高 6℃、最低 -4℃，温差是多少？", "10", "medium", {"op": "temp_diff", "high": 6, "low": -4}),
            _q("海拔 -30 米表示低于海平面多少米？", "30", "medium", {"op": "int", "value": 30}),
            _q("从海拔 120 米下降到 -80 米，下降了多少米？", "200", "hard",
               {"op": "temp_diff", "high": 120, "low": -80}),
            _q("存入 500 元记作 +500，取出 200 元应记作多少？", "-200", "hard", {"op": "int", "value": -200}),
        ],
        "体育中的数学": [
            _q("标准跑道一圈 400 米，跑 3 圈是多少米？", "1200", "basic", {"op": "int", "value": 3 * 400}),
            _q("跑 800 米要跑几圈 400 米跑道？", "2", "basic", {"op": "int", "value": 800 // 400}),
            _q("直径 20 米的圆形场地，周长多少米？（π 取 3.14）", "62.80", "medium",
               {"op": "circle_c_d", "d": 20}),
            _q("半径 10 米的圆形场地，面积多少平方米？（π 取 3.14）", "314.00", "medium",
               {"op": "circle_s", "r": 10}),
            _q("400 米跑道跑 1 圈用 80 秒，平均每秒多少米？", "5", "hard", {"op": "int", "value": 400 // 80}),
            _q("甲用 75 秒、乙用 82 秒跑完一圈，甲比乙快多少秒？", "7", "hard", {"op": "int", "value": 82 - 75}),
        ],
        "水是生命之源": [
            _q("一个班 40 人，每人每天节约 2 升水，全班每天节约多少升？", "80", "basic", {"op": "int", "value": 40 * 2}),
            _q("上题的结果合多少立方米？（1000 升 = 1 立方米）", "0.08", "basic", {"op": "litre_to_m3", "litres": 80}),
            _q("某户上月用水 20 立方米，本月用水 16 立方米，节约了百分之几？", "20%", "medium",
               {"op": "save_percent", "上": 20, "今": 16}),
            _q("全校 500 人，平均每人每天用水 30 升，一天共用水多少升？", "15000", "medium",
               {"op": "int", "value": 500 * 30}),
            _q("一天用水 15000 升，合多少立方米？", "15", "hard", {"op": "litre_to_m3", "litres": 15000}),
            _q("若每人每天少用 5 升，全校 500 人一个月（30 天）少用多少立方米？", "75", "hard",
               {"op": "save_m3", "people": 500, "litres": 5, "days": 30}),
        ],        "分数乘法·解决问题（1）": [
            _q("35 的 2/7 是多少？", "10", "basic", {"op": "mul_int", "a": "35", "n": 2, "div": 7}),
            _q("48 的 3/4 是多少？", "36", "basic", {"op": "mul_int", "a": "48", "n": 3, "div": 4}),
            _q("一条路长 120 米，已经修了 5/8，修了多少米？", "75", "medium",
               {"op": "mul_int", "a": "120", "n": 5, "div": 8}),
            _q("果园有 90 棵树，其中 2/5 是苹果树，苹果树多少棵？", "36", "medium",
               {"op": "mul_int", "a": "90", "n": 2, "div": 5}),
            _q("先取 40 的 3/8，再取出的 2/3，第二次取出多少？", "10", "hard",
               {"op": "mul_int", "a": "40", "n": 3, "div": 8, "then_num": 2, "then_den": 3}),
            _q("一班 45 人，男生占 3/5；男生中有 1/3 参加合唱队，合唱队男生多少人？", "9", "hard",
               {"op": "mul_int", "a": "45", "n": 3, "div": 5, "then_num": 1, "then_den": 3}),
        ],
    }
