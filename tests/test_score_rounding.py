import inspect

from app_v924 import (
    half_up_percent,
    progress_for,
    student_growth_profile_data,
    teacher_analytics_data,
    teaching_grade_answers,
)


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


def test_learning_accuracy_views_share_the_same_half_up_contract():
    progress_source = inspect.getsource(progress_for)
    assert '"accuracy":half_up_percent(hit,total)' in progress_source
    assert '"accuracy":half_up_percent(v[0],v[1])' in progress_source
    assert "round(hit/total*100)" not in progress_source
    assert "round(v[0]/v[1]*100)" not in progress_source

    growth_source = inspect.getsource(inspect.unwrap(student_growth_profile_data))
    assert "accuracy=half_up_percent(total_correct,total_questions)" in growth_source

    teacher_source = inspect.getsource(inspect.unwrap(teacher_analytics_data))
    assert '"accuracy":half_up_percent(v[0],v[1])' in teacher_source
    assert "avg_accuracy=half_up_percent(correct_sum,total_sum)" in teacher_source
