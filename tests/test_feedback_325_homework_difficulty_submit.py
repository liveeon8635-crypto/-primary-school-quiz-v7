"""反馈 #325 回归测试：组卷作业布置作业的难度选择与提交可用性。"""

from changying.web.v1_product_assistant import (
    HOMEWORK_DIFFICULTY_OPTIONS,
    homework_difficulty_contract,
    homework_submit_contract,
)


def test_difficulty_options_present():
    contract = homework_difficulty_contract()
    assert contract["options"] == ["简单", "中等", "偏难"]
    assert contract["required"] is True
    assert HOMEWORK_DIFFICULTY_OPTIONS == ("简单", "中等", "偏难")


def test_submit_enabled_when_all_fields_selected():
    result = homework_submit_contract({"title": "第一单元练习", "questions": "1,2,3", "difficulty": "中等"})
    assert result["submitEnabled"] is True
    assert result["missingFields"] == []


def test_submit_disabled_when_difficulty_missing():
    result = homework_submit_contract({"title": "第一单元练习", "questions": "1,2,3"})
    assert result["submitEnabled"] is False
    assert "difficulty" in result["missingFields"]
