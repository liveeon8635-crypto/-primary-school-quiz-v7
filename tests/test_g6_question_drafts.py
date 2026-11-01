"""六年级题目草稿：6 题/节点、三档各 2，答案必须能程序验算。"""
from __future__ import annotations

from collections import Counter
from fractions import Fraction

from changying.services import knowledge_maps as km
from changying.services.g6_question_drafts import build_drafts

PI = Fraction(314, 100)


def _frac(s) -> Fraction:
    return Fraction(str(s))


def _recompute(item) -> str:
    v = item["verify"]
    op = v["op"]

    if op == "mul_int":
        a = _frac(v["a"])
        value = a * v["n"]
        if v.get("div"):
            value /= v["div"]
        if v.get("then_num"):
            value *= Fraction(v["then_num"], v["then_den"])
        return str(value)
    if op == "mul_frac":
        return str(_frac(v["a"]) * _frac(v["b"]))
    if op == "div_int":
        return str(_frac(v["a"]) / v["n"])
    if op == "div_frac":
        return str(_frac(v["a"]) / _frac(v["b"]))
    if op == "recip":
        return str(1 / _frac(v["a"]))
    if op == "recip_product":
        return "1"
    if op == "circle_c":
        return f"{float(2 * PI * v['r']):.2f}"
    if op == "circle_c_d":
        return f"{float(PI * v['d']):.2f}"
    if op == "circle_d_from_c":
        return f"{float(Fraction(str(v['c'])) / PI):.2f}"
    if op == "circle_s":
        return f"{float(PI * v['r'] * v['r']):.2f}"
    if op == "circle_s_d":
        return f"{float(PI * Fraction(v['d'], 2) ** 2):.2f}"
    if op == "circle_scale":
        return str(v["k"] * v["k"])
    if op == "circle_s_from_c":
        r = Fraction(str(v["c"])) / (2 * PI)
        return f"{float(PI * r * r):.2f}"
    if op == "ring_s":
        return f"{float(PI * (v['big'] ** 2 - v['small'] ** 2)):.2f}"
    if op == "semicircle_s":
        return f"{float(PI * v['r'] * v['r'] / 2):.2f}"
    if op == "square_minus_circle":
        side = v["side"]
        return f"{float(Fraction(side ** 2) - PI * Fraction(side, 2) ** 2):.2f}"
    if op == "to_percent":
        value = _frac(v["value"])
        pct = value * 100
        text = f"{float(pct):g}"
        return f"{text}%"
    if op == "to_decimal":
        return f"{v['value'] / 100:g}"
    if op == "to_fraction":
        return str(Fraction(v["value"], 100))
    if op == "percent_of":
        return str(_frac(v["x"]) * Fraction(v["p"], 100))
    if op == "discount":
        return str(Fraction(v["price"] * v["zhe"], 10))
    if op == "discount_rate":
        return str(Fraction(v["price"] * v["rate"], 100))
    if op == "discount_reverse":
        return str(Fraction(v["price"] * 10, v["zhe"]))
    if op == "interest":
        return str(Fraction(v["principal"] * v["rate"] * v["years"], 100))
    if op == "interest_total":
        interest = Fraction(v["principal"]) * _frac(v["rate"]) / 100 * v["years"]
        total = Fraction(v["principal"]) + interest
        return f"{float(total):g}"
    if op == "rate_from":
        return f"{float(Fraction(v['interest']) / v['principal'] * 100):g}%"
    if op == "expr":
        text = (v["text"].replace("×", "*").replace("÷", "/"))
        # 分数用 Fraction 精确算：把 a/b 包成 Fraction
        import re
        def repl(m):
            return f"Fraction({m.group(1)},{m.group(2)})"
        text = re.sub(r"(\d+)/(\d+)", repl, text)
        value = eval(text, {"__builtins__": {}}, {"Fraction": Fraction})
        return str(Fraction(value).limit_denominator())
    if op == "int":
        return str(v["value"])
    if op == "temp_diff":
        return str(v["high"] - v["low"])
    if op == "litre_to_m3":
        return f"{v['litres'] / 1000:g}"
    if op == "save_percent":
        return f"{(v['上'] - v['今']) / v['上'] * 100:g}%"
    if op == "save_m3":
        return f"{v['people'] * v['litres'] * v['days'] / 1000:g}"
    raise AssertionError(f"未知的验算类型：{op}")


def test_each_node_has_six_questions_two_per_level():
    for name, items in build_drafts().items():
        assert len(items) == 6, f"{name} 有 {len(items)} 题"
        assert Counter(x["level"] for x in items) == {"basic": 2, "medium": 2, "hard": 2}, name


def test_names_match_the_grade6_map():
    names = {n["name"] for n in km.TEMPLATES["rj2026-g6-math-up"]["map"]["nodes"]}
    unknown = set(build_drafts()) - names
    assert not unknown, f"这些名称在地图里找不到：{sorted(unknown)}"


def test_every_answer_recomputes():
    bad = []
    for name, items in build_drafts().items():
        for item in items:
            expected = _recompute(item)
            if item["answer"] != expected:
                bad.append(f"{name}: {item['text']} 标答={item['answer']} 实算={expected}")
    assert not bad, "\n".join(bad)


def test_pilot_skips_nodes_that_need_figures_or_context():
    names = set(build_drafts())
    for skipped in ("用有序数对确定位置",):
        assert skipped not in names
    assert len(names) == 17
