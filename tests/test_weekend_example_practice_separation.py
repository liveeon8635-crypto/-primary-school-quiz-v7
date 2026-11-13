from changying.services.weekend_presentation import presentation_pages
from changying.services.weekend_answers import display_stem


def test_example_mode_never_replays_student_practice_paper():
    raw = [
        "例题讲解", "例题一：观察图形", "第一步：找出已知条件",
        "第二步：列出关系", "第三步：计算", "第四步：检查",
        "例题二：继续分析", "观察数量关系", "列式并说明理由",
        "学生随堂试卷", "第1题：随堂练习甲", "第2题：随堂练习乙",
    ]
    pages = presentation_pages(raw, example_mode=True)
    joined = "\\n".join(pages)
    assert "例题一" in joined
    assert "例题二" in joined
    assert "学生随堂试卷" not in joined
    assert "随堂练习甲" not in joined
    assert "随堂练习乙" not in joined


def test_example_mode_fails_closed_when_import_contains_only_practice_paper():
    raw = [
        "学生随堂试卷", "第1题：练习甲", "第2题：练习乙",
        "第3题：练习丙", "第4题：练习丁", "第5题：练习戊",
        "第6题：练习己", "第7题：练习庚", "第8题：练习辛",
        "第9题：练习壬", "第10题：练习癸",
    ]
    assert presentation_pages(raw, example_mode=True) == []


def test_local_practice_number_replaces_imported_original_number():
    assert display_stem("第4题 2分｜哪项面积最接近1公顷？") == "哪项面积最接近1公顷？"
    assert display_stem("第 12 题（进阶） 3分：计算下面图形面积。") == "计算下面图形面积。"
    assert display_stem("（1）先观察图形，再填写。") == "（1）先观察图形，再填写。"
    assert display_stem("阅读材料\\n\\n第4题 2分｜回答问题。") == "阅读材料\\n\\n第4题 2分｜回答问题。"


def test_local_number_prefix_is_removed_without_mutating_source():
    imported = "第4题 2分｜题目原文"
    rendered = "选择题 1：" + display_stem(imported)
    assert rendered == "选择题 1：题目原文"
    assert imported == "第4题 2分｜题目原文"
