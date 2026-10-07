"""反馈 #370 回归测试：导入试卷后保存位置的导航提示。

钟老师在组卷作业导入试卷后不清楚保存到哪里，问助手也没有导航提示。
本测试验证产品助手对相关提问返回明确的「试卷库」导航步骤，
且对无关提问不误触发。
"""

from changying.web.v1_product_assistant import (
    PAPER_IMPORT_NAVIGATION_MARKER,
    PAPER_IMPORT_SAVED_LOCATION,
    paper_import_navigation_hint,
)


def test_marker_registered():
    assert PAPER_IMPORT_NAVIGATION_MARKER == "changying_v1_paper_import_navigation_v1"


def test_hint_for_save_location_question():
    hint = paper_import_navigation_hint("组卷作业导入试卷后保存到哪里了")
    assert hint
    assert PAPER_IMPORT_SAVED_LOCATION in hint
    assert "试卷库" in hint
    assert "1." in hint


def test_hint_for_cannot_find_paper():
    hint = paper_import_navigation_hint("导入的试卷找不到，也没有导航页")
    assert hint
    assert "试卷库" in hint


def test_hint_empty_for_unrelated_question():
    assert paper_import_navigation_hint("今天天气怎么样") == ""
    assert paper_import_navigation_hint("") == ""
