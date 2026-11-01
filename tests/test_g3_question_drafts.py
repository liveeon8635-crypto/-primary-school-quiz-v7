"""三年级题目草稿：每个知识点 6 题、三档各 2，答案必须能程序验算。"""
from __future__ import annotations

from collections import Counter

from changying.services import knowledge_maps as km
from changying.services.g3_question_drafts import build_drafts, _LEN


def _map():
    return km.TEMPLATES["rj2026-g3-math-up"]["map"]


def _recompute(item: dict) -> str:
    v = item["verify"]
    op = v["op"]
    if op == "mul":
        return str(v["a"] * v["b"])
    if op == "expr":
        text = v["text"].replace("×", "*").replace("÷", "/")
        value = eval(text, {"__builtins__": {}}, {})
        return str(int(value)) if float(value).is_integer() else str(value)
    if op == "conv":
        table = v.get("table") or _LEN
        return str(v["value"] * table[v["src"]] // table[v["dst"]])
    if op == "int":
        return str(v["value"])
    raise AssertionError(f"未知的验算类型：{op}")


def test_every_node_has_six_questions_two_per_level():
    drafts = build_drafts()
    assert drafts, "没有生成任何草稿"
    for name, items in drafts.items():
        assert len(items) == 6, f"{name} 有 {len(items)} 题"
        levels = Counter(x["level"] for x in items)
        assert levels == {"basic": 2, "medium": 2, "hard": 2}, f"{name} 分档 {levels}"


def test_question_names_match_map_nodes():
    names = {n["name"] for n in _map()["nodes"]}
    unknown = set(build_drafts()) - names
    assert not unknown, f"这些名称在地图里找不到：{sorted(unknown)}"


def test_every_answer_is_recomputable():
    bad = []
    for name, items in build_drafts().items():
        for item in items:
            expected = _recompute(item)
            if item["answer"] != expected:
                bad.append(f"{name}: {item['text']} 标答 {item['answer']} 实算 {expected}")
    assert not bad, "\n".join(bad)


def test_answers_are_plain_integers_or_reasonable_strings():
    for name, items in build_drafts().items():
        for item in items:
            assert item["answer"].strip(), f"{name} 有空答案"
            assert item["text"].strip(), f"{name} 有空题干"
            assert "____" in item["text"] or "（　）" in item["text"] or "？" in item["text"], \
                f"{name} 的题干没有作答位：{item['text']}"


def test_pilot_covers_arithmetic_units_only():
    """U1 观察物体、UC 曹冲称象需要配图或情境，暂不自动出题。"""
    names = set(build_drafts())
    assert "从不同方向观察物体" not in names
    assert "认识曹冲称象与质量单位" not in names
    assert len(names) == 17
