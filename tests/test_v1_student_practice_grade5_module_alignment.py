"""Regression test for feedback #304: 人教版（2024 修订）五年级数学知识模块对齐。

反馈原文：“知识模块练习”五年级里面的“简易方程”和“位置”在最新的人教版教材里面
已经改版了，你们还没有更新，不是最新版本。

本测试锁定：
1. 旧版单元名“简易方程”必须映射到最新人教版模块名“用字母表示数”。
2. 旧版单元名“位置”必须映射到最新人教版模块名“用数对确定位置”。
3. 非五年级/非数学的模块名必须原样返回，避免影响其他题库。
"""

from changying.web.v1_student_practice import normalize_knowledge_module


def test_grade5_math_old_equation_module_maps_to_latest_textbook_name():
    assert normalize_knowledge_module(5, "数学", "简易方程") == "用字母表示数"
    assert normalize_knowledge_module(5, "数学", "方程") == "用字母表示数"
    assert normalize_knowledge_module(5, "数学", "解简易方程") == "用字母表示数"


def test_grade5_math_old_position_module_maps_to_latest_textbook_name():
    assert normalize_knowledge_module(5, "数学", "位置") == "用数对确定位置"
    assert normalize_knowledge_module(5, "数学", "确定位置") == "用数对确定位置"
    assert normalize_knowledge_module(5, "数学", "数对") == "用数对确定位置"


def test_latest_textbook_module_names_are_stable():
    assert normalize_knowledge_module(5, "数学", "用字母表示数") == "用字母表示数"
    assert normalize_knowledge_module(5, "数学", "用数对确定位置") == "用数对确定位置"


def test_other_grade_or_subject_is_unchanged():
    assert normalize_knowledge_module(4, "数学", "简易方程") == "简易方程"
    assert normalize_knowledge_module(5, "语文", "位置") == "位置"
    assert normalize_knowledge_module(5, "数学", "") == ""
