"""反馈 #325 回归测试：组卷作业布置作业的难度选择与提交就绪。

反馈原文：组卷作业里面布置作业里有两个问题：1是所有选项已经选择好了，但是提交不了。
2是没有难度选择（简单，中等，偏难）。
"""

from changying.web import v1_product_assistant as mod


def test_difficulty_options_present():
    options = mod.paper_assign_difficulty_options()
    assert options == ["简单", "中等", "偏难"]


def test_submit_not_ready_without_difficulty():
    result = mod.paper_assign_submit_readiness(
        selected_questions=[1, 2, 3],
        difficulty="",
        target_class="五年级一班",
    )
    assert result["ready"] is False
    assert "difficulty" in result["missing"]


def test_submit_ready_when_all_selected():
    result = mod.paper_assign_submit_readiness(
        selected_questions=[1, 2, 3],
        difficulty="中等",
        target_class="五年级一班",
    )
    assert result["ready"] is True
    assert result["missing"] == []
    assert result["marker"] == mod.PAPER_ASSIGN_SUBMIT_READY_MARKER


def test_submit_not_ready_without_questions():
    result = mod.paper_assign_submit_readiness(
        selected_questions=[],
        difficulty="简单",
        target_class="五年级一班",
    )
    assert result["ready"] is False
    assert "questions" in result["missing"]
