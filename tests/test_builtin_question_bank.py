from collections import Counter

from changying.services.builtin_question_bank import (
    built_in_question_specs,
    built_in_subjects,
    built_in_textbooks,
)


def test_grade5_math_pack_is_large_and_covers_core_modules():
    specs = built_in_question_specs(5, "数学")
    assert "数学" in built_in_subjects(5)
    assert len(specs) >= 180

    counts = Counter(row["knowledge"] for row in specs)
    expected = {
        "小数乘整数",
        "小数乘小数",
        "积的近似数",
        "小数乘法简便运算",
        "用数对确定位置",
        "除数是整数的小数除法",
        "一个数除以小数",
        "商的近似数",
        "循环小数",
        "可能性大小",
        "用字母表示数",
        "解方程",
        "实际问题与方程",
        "平行四边形的面积",
        "三角形的面积",
        "梯形的面积",
        "组合图形的面积",
        "植树问题",
    }
    assert expected <= set(counts)
    assert min(counts[name] for name in expected) >= 10


def test_generated_questions_have_valid_unique_multiple_choice_payloads():
    specs = built_in_question_specs(5, "数学")
    keys = set()
    for row in specs:
        assert row["grade"] == 5
        assert row["subject"] == "数学"
        assert len(row["options"]) == 4
        assert len(set(row["options"])) == 4
        assert 0 <= row["correct_index"] < 4
        assert row["options"][row["correct_index"]]
        key = (row["text"], row["knowledge"])
        assert key not in keys
        keys.add(key)


def test_unsupported_pack_does_not_invent_other_grades():
    assert built_in_question_specs(4, "数学") == []
    assert built_in_question_specs(4, "语文") == []
    assert built_in_subjects(4) == []


def test_grade5_math_pack_uses_current_pep_textbook_only():
    assert built_in_textbooks(5, "数学") == ["人教版"]
    assert len(built_in_question_specs(5, "数学", "人教版")) >= 180
    for other_publisher in ("北师大版", "苏教版", "冀教版", "青岛版", "西师大版"):
        assert built_in_question_specs(5, "数学", other_publisher) == []
    assert built_in_textbooks(5, "语文") == ["统编版（人民教育出版社）"]


def test_grade5_chinese_pack_covers_all_eight_units_with_original_objective_items():
    specs = built_in_question_specs(5, "语文", "统编版（人民教育出版社）")
    assert "语文" in built_in_subjects(5)
    assert len(specs) >= 64
    assert {row["subject"] for row in specs} == {"语文"}
    assert {row["textbook"] for row in specs} == {"统编版（人民教育出版社）"}
    units = {row["unit"].split(" · ", 1)[0] for row in specs}
    assert units == {"第一单元", "第二单元", "第三单元", "第四单元", "第五单元", "第六单元", "第七单元", "第八单元"}
    knowledge = {row["knowledge"] for row in specs}
    assert "提高阅读速度" in knowledge
    assert "创造性复述民间故事" in knowledge
    assert "说明方法与说明性文章" in knowledge
    assert "静态描写与动态描写" in knowledge
    for row in specs:
        assert len(row["options"]) == 4
        assert len(set(row["options"])) == 4
        assert 0 <= row["correct_index"] < 4


def test_grade5_chinese_pack_rejects_other_publishers():
    assert built_in_question_specs(5, "语文", "北师大版") == []
