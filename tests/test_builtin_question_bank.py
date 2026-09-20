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


def test_generated_math_questions_include_valid_mixed_auto_gradable_payloads():
    specs = built_in_question_specs(5, "数学")
    keys = set()
    types = Counter()
    knowledge_types = {}
    for row in specs:
        assert row["grade"] == 5
        assert row["subject"] == "数学"
        question_type = row.get("question_type") or "single_choice"
        types[question_type] += 1
        knowledge_types.setdefault(row["knowledge"], set()).add(question_type)

        if question_type in {"single_choice", "true_false"}:
            assert len(row["options"]) >= 2
            assert len(set(row["options"])) == len(row["options"])
            assert 0 <= row["correct_index"] < len(row["options"])
            assert row["options"][row["correct_index"]]
        else:
            assert question_type in {"fill_blank", "calculation"}
            assert row["options"] == []
            assert row["correct_index"] == -1
            assert row["answer_json"]["answer"]

        key = (row["text"], row["knowledge"])
        assert key not in keys
        keys.add(key)

    assert {"single_choice", "true_false", "fill_blank", "calculation"} <= set(types)
    assert all(
        {"single_choice", "true_false", "fill_blank"} <= type_set
        for type_set in knowledge_types.values()
    )


def test_unsupported_pack_does_not_invent_other_grades_or_subjects():
    assert built_in_question_specs(4, "数学") == []
    assert built_in_question_specs(4, "语文") == []
    assert built_in_question_specs(4, "英语") == []
    assert built_in_question_specs(5, "科学") == []
    assert built_in_subjects(4) == []


def test_grade5_chinese_pack_is_large_and_covers_core_language_modules():
    specs = built_in_question_specs(5, "语文")
    assert "语文" in built_in_subjects(5)
    assert len(specs) >= 120

    counts = Counter(row["knowledge"] for row in specs)
    expected = {
        "字音辨析",
        "字形辨析",
        "词语理解",
        "成语运用",
        "关联词运用",
        "病句辨析",
        "标点符号",
        "修辞手法",
        "句子衔接",
        "提取关键信息",
        "概括主要内容",
        "阅读推断",
        "体会思想感情",
        "说明方法",
        "资料整合",
        "习作修改",
    }
    assert expected <= set(counts)
    assert min(counts[name] for name in expected) >= 8
    for row in specs:
        assert row["grade"] == 5
        assert row["subject"] == "语文"
        assert row["textbook"] == "统编版（人民教育出版社）"
        assert len(row["options"]) == 4
        assert len(set(row["options"])) == 4
        assert 0 <= row["correct_index"] < 4


def test_grade5_chinese_pack_has_mixed_auto_gradable_question_shapes():
    specs = built_in_question_specs(5, "语文", "统编版（人民教育出版社）")
    types = Counter((row.get("question_type") or "single_choice") for row in specs)
    assert len(specs) == 160
    assert types["single_choice"] == 128
    assert types["true_false"] == 16
    assert types["fill_blank"] == 16
    assert types["short_answer"] == 16
    for row in specs:
        question_type = row.get("question_type") or "single_choice"
        if question_type in {"single_choice", "true_false"}:
            assert len(row["options"]) >= 2
            assert 0 <= int(row["correct_index"]) < len(row["options"])
        else:
            assert question_type in {"fill_blank", "short_answer"}
            assert row["options"] == []
            assert row["correct_index"] == -1
            assert row["answer_json"]["answer"]


def test_grade5_english_pack_has_mixed_auto_gradable_question_shapes():
    specs = built_in_question_specs(5, "英语", "人教版（PEP·当前最新版）")
    types = Counter((row.get("question_type") or "single_choice") for row in specs)
    assert len(specs) == 160
    assert types["single_choice"] == 128
    assert types["true_false"] == 16
    assert types["fill_blank"] == 16
    assert types["short_answer"] == 16


def test_grade5_math_pack_uses_current_pep_textbook_only():
    assert built_in_textbooks(5, "数学") == ["人教版"]
    assert len(built_in_question_specs(5, "数学", "人教版")) >= 180
    for other_publisher in ("北师大版", "苏教版", "冀教版", "青岛版", "西师大版"):
        assert built_in_question_specs(5, "数学", other_publisher) == []
    assert built_in_textbooks(5, "语文") == ["统编版（人民教育出版社）"]
    assert len(built_in_question_specs(5, "语文", "统编版（人民教育出版社）")) >= 120
    for other_publisher in ("北师大版", "苏教版"):
        assert built_in_question_specs(5, "语文", other_publisher) == []



def test_grade5_english_pack_uses_current_pep_textbook_only():
    textbook = "人教版（PEP·当前最新版）"
    assert built_in_textbooks(5, "英语") == [textbook]
    assert len(built_in_question_specs(5, "英语", textbook)) == 160
    for legacy_or_other in (
        "人教PEP",
        "人教版",
        "外研版",
        "译林版",
        "人教版（PEP·旧版）",
    ):
        assert built_in_question_specs(5, "英语", legacy_or_other) == []
