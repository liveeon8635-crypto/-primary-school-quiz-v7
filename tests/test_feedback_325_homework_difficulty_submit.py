"""反馈 #325 回归测试：组卷作业布置作业的难度选择与提交就绪。

覆盖钟老师反馈的两个问题：
1) 所有选项已选择但提交不了 —— 提交就绪判定必须明确缺失项；
2) 缺少难度选择（简单/中等/偏难）—— 必须提供三个难度选项。
"""

from changying.web.v1_product_assistant import (
    HOMEWORK_DIFFICULTY_OPTIONS,
    HOMEWORK_DIFFICULTY_DEFAULT,
    HOMEWORK_SUBMIT_READY_MARKER,
    homework_assignment_contract,
    homework_submit_ready,
)


def test_difficulty_options_present():
    assert HOMEWORK_DIFFICULTY_OPTIONS == ("简单", "中等", "偏难")
    assert HOMEWORK_DIFFICULTY_DEFAULT in HOMEWORK_DIFFICULTY_OPTIONS


def test_assignment_contract_exposes_difficulty_and_submit_requirements():
    contract = homework_assignment_contract()
    assert contract["marker"] == HOMEWORK_SUBMIT_READY_MARKER
    assert contract["difficultyOptions"] == ["简单", "中等", "偏难"]
    assert contract["difficultyRequired"] is True
    assert "difficulty" in contract["submitRequires"]
    assert contract["submitEnabledWhenAllRequired"] is True


def test_submit_ready_when_all_required_present():
    result = homework_submit_ready({"questions": [1, 2], "recipients": [10], "difficulty": "中等"})
    assert result["ready"] is True
    assert result["missing"] == []


def test_submit_not_ready_reports_missing_difficulty():
    result = homework_submit_ready({"questions": [1], "recipients": [10]})
    assert result["ready"] is False
    assert "difficulty" in result["missing"]


def test_submit_not_ready_reports_missing_questions_and_recipients():
    result = homework_submit_ready({"difficulty": "偏难"})
    assert result["ready"] is False
    assert set(result["missing"]) == {"questions", "recipients"}


def test_invalid_difficulty_rejected():
    result = homework_submit_ready({"questions": [1], "recipients": [10], "difficulty": "超难"})
    assert result["ready"] is False
    assert "difficulty" in result["missing"]
