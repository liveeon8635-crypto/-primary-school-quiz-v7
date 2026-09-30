"""回归测试：反馈 #304 五年级知识模块练习需使用最新人教版教材目录。

反馈原文：“知识模块练习”五年级里面的“简易方程”和“位置”在最新的人教版
教材里面已经改版了，你们还没有更新，不是最新版本。

本测试锁定：
1. 当前教材版本为 2024 版；
2. 五年级“简易方程”和“位置”在 2024 版下均归属五年级上册；
3. 五年级知识模块目录包含这两个模块，且不再使用 2013 版的过时归属；
4. 未知版本回退到当前版本，避免展示过时目录。
"""

from changying.services.classroom_execution import (
    CURRENT_TEXTBOOK_EDITION,
    knowledge_module_placement,
    knowledge_modules_for_grade,
    normalize_textbook_edition,
)


def test_current_edition_is_latest():
    assert CURRENT_TEXTBOOK_EDITION == "2024"


def test_unknown_edition_falls_back_to_current():
    assert normalize_textbook_edition(None) == CURRENT_TEXTBOOK_EDITION
    assert normalize_textbook_edition("") == CURRENT_TEXTBOOK_EDITION
    assert normalize_textbook_edition("1999") == CURRENT_TEXTBOOK_EDITION
    assert normalize_textbook_edition("2024") == "2024"


def test_jianyi_fangcheng_updated_to_grade5_term1_in_2024():
    old = knowledge_module_placement("简易方程", "2013")
    new = knowledge_module_placement("简易方程", "2024")
    assert old is not None and new is not None
    assert old["grade"] == 5 and old["term"] == "下"
    assert new["grade"] == 5 and new["term"] == "上"
    assert new["edition"] == "2024"


def test_weizhi_updated_unit_in_2024():
    new = knowledge_module_placement("位置", "2024")
    assert new is not None
    assert new["grade"] == 5 and new["term"] == "上"
    assert "数对" in new["unit"]


def test_grade5_modules_use_latest_edition():
    modules = knowledge_modules_for_grade(5)
    names = {m["module"] for m in modules}
    assert {"简易方程", "位置"} <= names
    for m in modules:
        assert m["edition"] == CURRENT_TEXTBOOK_EDITION
        assert m["grade"] == 5
    jianyi = next(m for m in modules if m["module"] == "简易方程")
    assert jianyi["term"] == "上"


def test_unknown_module_returns_none():
    assert knowledge_module_placement("不存在的模块") is None
