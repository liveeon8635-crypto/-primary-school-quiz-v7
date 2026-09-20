from app_v924 import half_up_percent


def test_half_up_percent_uses_school_style_rounding():
    assert half_up_percent(1, 8) == 13
    assert half_up_percent(7, 8) == 88
    assert half_up_percent(4, 8) == 50
    assert half_up_percent(0, 8) == 0
    assert half_up_percent(8, 8) == 100
    assert half_up_percent(0, 0) == 0
