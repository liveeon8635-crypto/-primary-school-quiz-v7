from changying.services.reinforcement_subject_policy import (
    augment_reinforcement_prompt,
    reinforcement_subject_from_prompt,
)
from changying.web.reinforcement_quality import infer_reinforcement_figure


def test_chinese_reinforcement_prompt_adds_subject_specific_contract():
    base = '''最近测试/练习反馈：{"primary":{"grade":5,"subject":"语文","textbook":"人教版"}}
要求：生成针对性练习。'''
    assert reinforcement_subject_from_prompt(base) == "语文"
    prompt = augment_reinforcement_prompt("reinforcement_generate", base)
    assert "当前科目是语文" in prompt
    assert "不要使用 calculation" in prompt
    assert "开放性阅读感受、习作、长篇表达不得自动判分" in prompt
    assert "figure 必须返回 {}" in prompt


def test_math_reinforcement_prompt_is_not_rewritten_by_chinese_policy():
    base = '''最近测试/练习反馈：{"primary":{"grade":5,"subject":"数学","textbook":"人教版"}}'''
    assert reinforcement_subject_from_prompt(base) == "数学"
    assert augment_reinforcement_prompt("reinforcement_generate", base) == base


def test_unrelated_ai_features_are_untouched():
    base = '''{"primary":{"subject":"语文"}}'''
    assert augment_reinforcement_prompt("grading", base) == base


def test_chinese_item_drops_accidental_math_figure():
    item = {
        "subject": "语文",
        "knowledge": "提取关键信息",
        "text": "阅读材料后选择正确答案。",
        "figure": {
            "type": "coordinate_grid",
            "points": [{"label": "A", "x": 2, "y": 3}],
        },
    }
    assert infer_reinforcement_figure(item) == {}


def test_math_item_still_preserves_valid_figure():
    item = {
        "subject": "数学",
        "knowledge": "位置",
        "text": "点A在(2,3)。",
        "figure": {
            "type": "coordinate_grid",
            "points": [{"label": "A", "x": 2, "y": 3}],
        },
    }
    figure = infer_reinforcement_figure(item)
    assert figure["type"] == "coordinate_grid"
    assert figure["points"][0]["x"] == 2
