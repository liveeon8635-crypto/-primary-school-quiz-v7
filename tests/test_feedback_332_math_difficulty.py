"""反馈 #332 回归测试：AI 生成的数学题每个等级难度都应提高。"""

from changying.web.v1_product_assistant import (
    MATH_DIFFICULTY_LEVELS,
    MATH_DIFFICULTY_MIN_OPERANDS,
    MATH_DIFFICULTY_MIN_STEPS,
    MATH_DIFFICULTY_RAISED_MARKER,
    math_difficulty_contract,
)


def test_all_levels_raise_difficulty():
    contract = math_difficulty_contract()
    assert contract["marker"] == MATH_DIFFICULTY_RAISED_MARKER
    assert contract["raised"] is True
    assert set(contract["levels"]) == set(MATH_DIFFICULTY_LEVELS)
    for level in MATH_DIFFICULTY_LEVELS:
        assert contract["minOperands"][level] >= 2
        assert contract["minSteps"][level] >= 2


def test_higher_level_requires_more():
    assert MATH_DIFFICULTY_MIN_OPERANDS["提高"] > MATH_DIFFICULTY_MIN_OPERANDS["基础"]
    assert MATH_DIFFICULTY_MIN_OPERANDS["挑战"] > MATH_DIFFICULTY_MIN_OPERANDS["提高"]
    assert MATH_DIFFICULTY_MIN_STEPS["提高"] > MATH_DIFFICULTY_MIN_STEPS["基础"]
    assert MATH_DIFFICULTY_MIN_STEPS["挑战"] > MATH_DIFFICULTY_MIN_STEPS["提高"]


def test_single_level_contract():
    contract = math_difficulty_contract("挑战")
    assert contract["levels"] == ["挑战"]
    assert contract["minOperands"]["挑战"] == MATH_DIFFICULTY_MIN_OPERANDS["挑战"]
