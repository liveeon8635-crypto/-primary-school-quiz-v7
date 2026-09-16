from changying.web.v1 import v1_html
from changying.web import v1_teaching_actions
from changying.web.v1_teaching_actions import (
    V1_TEACHING_ACTIONS_MARKER,
    patch_v1_teaching_actions_html,
)


def test_teaching_action_patch_reuses_existing_homework_and_lesson_routes():
    html = patch_v1_teaching_actions_html(v1_html())

    assert V1_TEACHING_ACTIONS_MARKER in html
    assert "/teacher/assignments" in html
    assert "/teacher/papers" in html
    assert "/teacher/assignments/${aid}/submissions" in html
    assert "/teaching/lessons" in html
    assert "method:'POST'" in html
    assert "method:'PUT'" in html
    assert "原教学系统" in html


def test_teaching_action_patch_is_idempotent_and_stays_inside_v1():
    once = patch_v1_teaching_actions_html(v1_html())
    twice = patch_v1_teaching_actions_html(once)

    assert twice == once
    assert once.count(V1_TEACHING_ACTIONS_MARKER) >= 2
    assert "/classic" not in v1_teaching_actions._TEACHING_ACTIONS_SNIPPET
    assert "stopImmediatePropagation" in v1_teaching_actions._TEACHING_ACTIONS_SNIPPET
    assert "作业与错题" in v1_teaching_actions._TEACHING_ACTIONS_SNIPPET
    assert "批改/订正" in v1_teaching_actions._TEACHING_ACTIONS_SNIPPET
    assert "备课" in v1_teaching_actions._TEACHING_ACTIONS_SNIPPET


def test_timetable_card_does_not_fake_a_calendar_schedule():
    html = patch_v1_teaching_actions_html(v1_html())

    assert "不等同于带日期/教室的日历排课" in html
    assert "当前生产库没有标准化“日期 / 时段 / 教室 / 教师 / 班级”的课表表" in html
    assert "正式排课应作为 V1.1 数据迁移单独推进" in html


def test_assignment_bridge_keeps_write_scope_on_existing_apis():
    snippet = v1_teaching_actions._TEACHING_ACTIONS_SNIPPET

    assert "CREATE TABLE" not in snippet
    assert "ALTER TABLE" not in snippet
    assert "DATABASE_URL" not in snippet
    assert "paper_id:paperID" in snippet
    assert "submission_mode:mode" in snippet
    assert "teacherConfirmed" in snippet
    assert "wrongCount" in snippet
