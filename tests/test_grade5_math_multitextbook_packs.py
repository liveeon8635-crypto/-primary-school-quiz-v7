from collections import Counter

from changying.services.builtin_question_bank import (
    built_in_question_specs,
    built_in_textbooks,
)


def test_grade5_math_exposes_five_supported_textbook_editions():
    assert built_in_textbooks(5, "数学") == [
        "人教版",
        "北师大版",
        "苏教版",
        "冀教版",
        "青岛版",
    ]


def test_each_supplemental_edition_has_substantial_valid_inventory():
    minimums = {
        "北师大版": 120,
        "苏教版": 140,
        "冀教版": 140,
        "青岛版": 140,
    }
    for textbook, minimum in minimums.items():
        specs = built_in_question_specs(5, "数学", textbook)
        assert len(specs) >= minimum, (textbook, len(specs))
        keys = set()
        for row in specs:
            assert row["grade"] == 5
            assert row["subject"] == "数学"
            assert row["semester"] == "上册"
            assert row["textbook"] == textbook
            assert row["unit"]
            assert row["knowledge"]
            assert row["text"]
            assert len(row["options"]) == 4
            assert len(set(row["options"])) == 4
            assert 0 <= row["correct_index"] < 4
            key = (row["unit"], row["knowledge"], row["text"])
            assert key not in keys
            keys.add(key)


def test_beishida_pack_tracks_its_grade5_upper_term_structure():
    rows = built_in_question_specs(5, "数学", "北师大版")
    units = {row["unit"] for row in rows}
    assert {
        "第一单元 · 小数除法",
        "第二单元 · 轴对称和平移",
        "第三单元 · 倍数与因数",
        "第四单元 · 多边形的面积",
        "第五单元 · 分数的意义",
        "第六单元 · 组合图形的面积",
        "第七单元 · 可能性",
    } <= units


def test_sujiao_pack_tracks_its_grade5_upper_term_structure():
    rows = built_in_question_specs(5, "数学", "苏教版")
    units = {row["unit"] for row in rows}
    assert {
        "第一单元 · 负数的初步认识",
        "第二单元 · 多边形的面积",
        "第三单元 · 小数的意义和性质",
        "第四单元 · 小数加法和减法",
        "第五单元 · 小数乘法和除法",
        "第六单元 · 统计表和条形统计图（二）",
        "第七单元 · 解决问题的策略",
        "第八单元 · 用字母表示数",
    } <= units


def test_jijiao_pack_tracks_its_grade5_upper_term_structure():
    rows = built_in_question_specs(5, "数学", "冀教版")
    units = {row["unit"] for row in rows}
    assert {
        "第一单元 · 方向与路线",
        "第二单元 · 小数乘法",
        "第三单元 · 小数除法",
        "第四单元 · 可能性",
        "第五单元 · 四则混合运算（二）",
        "第六单元 · 多边形的面积",
        "第七单元 · 土地的面积",
        "第八单元 · 方程",
    } <= units


def test_qingdao_pack_tracks_its_grade5_upper_term_structure():
    rows = built_in_question_specs(5, "数学", "青岛版")
    units = {row["unit"] for row in rows}
    assert {
        "第一单元 · 今天我当家——小数乘法",
        "第二单元 · 图案美——对称、平移与旋转",
        "第三单元 · 游三峡——小数除法",
        "第四单元 · 走进动物园——简易方程",
        "第五单元 · 生活中的多边形——多边形的面积",
        "第六单元 · 团体操表演——因数与倍数",
        "第七单元 · 绿色家园——折线统计图",
    } <= units


def test_supplemental_editions_have_many_knowledge_modules():
    for textbook in ("北师大版", "苏教版", "冀教版", "青岛版"):
        rows = built_in_question_specs(5, "数学", textbook)
        counts = Counter(row["knowledge"] for row in rows)
        assert len(counts) >= 7
        assert max(counts.values()) >= 8
