from scripts.weekend_course_simulation import (
    class_post_rate, progress_points, scenarios, team_points, tutor_points,
)


def test_all_wrong_gets_no_progress_or_team_points():
    students, prev = scenarios()["全错"]
    assert [progress_points(s)["points"] for s in students] == [0, 0, 0]
    assert team_points(prev, class_post_rate(students)) == 0


def test_absent_student_gets_nothing_and_is_excluded_from_rate():
    students, _ = scenarios()["一人缺课"]
    assert progress_points(students[1])["points"] == 0
    assert round(class_post_rate(students), 1) == 75.0


def test_first_lesson_has_no_progress_or_team_points():
    students, prev = scenarios()["首次课无基线"]
    assert all(progress_points(s)["points"] == 0 for s in students)
    assert team_points(prev, class_post_rate(students)) == 0


def test_progress_cap_and_tutor_points_follow_tutee_result():
    students, prev = scenarios()["常规课(弱生进步,强带弱成功)"]
    assert progress_points(students[2])["points"] == 6
    assert tutor_points(students[2]) == 2
    assert 0 < team_points(prev, class_post_rate(students)) <= 4
