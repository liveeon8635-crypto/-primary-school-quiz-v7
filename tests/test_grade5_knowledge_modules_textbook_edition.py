"""回归测试：五年级知识模块练习需与最新人教版教材一致（反馈 #304）。

反馈：机构老师钟老师指出“知识模块练习”五年级里的“简易方程”和“位置”
在最新人教版教材里已经改版，产品未更新。
本测试锁定教材版本标记与五年级模块清单，防止回退到旧版模块。
"""

from changying.web import v1_product_assistant as assistant


def test_grade5_modules_include_renjiao_current_modules():
    modules = set(assistant.GRADE5_KNOWLEDGE_MODULES)
    assert "简易方程" in modules
    assert "位置" in modules


def test_grade5_modules_do_not_use_retired_old_edition_modules():
    modules = set(assistant.GRADE5_KNOWLEDGE_MODULES)
    retired = set(assistant.GRADE5_RETIRED_MODULES)
    assert retired, "必须显式记录已停用的旧版模块，避免误用"
    assert not (modules & retired), "五年级模块清单不得包含旧版已改版模块"


def test_textbook_edition_marker_is_current():
    assert assistant.RENJIAO_TEXTBOOK_EDITION.startswith("人教版")
    assert "2024" in assistant.RENJIAO_TEXTBOOK_EDITION
