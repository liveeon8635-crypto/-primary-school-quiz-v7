import inspect

from app_v924 import half_up_percent, teaching_grade_answers


def test_half_up_percent_uses_school_style_rounding():
    assert half_up_percent(1, 8) == 13
    assert half_up_percent(7, 8) == 88
    assert half_up_percent(4, 8) == 50
    assert half_up_percent(0, 8) == 0
    assert half_up_percent(8, 8) == 100
    assert half_up_percent(0, 0) == 0


def test_teaching_sessions_share_the_same_rounding_contract():
    source = inspect.getsource(teaching_grade_answers)
    assert "score=half_up_percent(correct,total)" in source
    assert "round(correct/total*100)" not in source
