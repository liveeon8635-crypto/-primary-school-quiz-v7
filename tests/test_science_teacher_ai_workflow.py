import pytest

from changying.web.science_teacher_ai import (
    SCIENCE_TEACHER_AI_MARKER,
    augment_science_teacher_prompt,
    patch_science_teacher_ai_html,
    require_explicit_science_textbook,
)


def test_science_textbook_must_be_explicit_and_science_specific():
    for value in (
        "",
        "人教版",
        "人教版（当前最新版）",
        "人教版（PEP·当前最新版）",
        "统编版",
        "统编版（人民教育出版社）",
    ):
        with pytest.raises(ValueError):
            require_explicit_science_textbook("科学", value)

    assert require_explicit_science_textbook("科学", "学校实际使用的科学教材A版") == "学校实际使用的科学教材A版"
    assert require_explicit_science_textbook("数学", "人教版") == "人教版"


def test_science_lesson_prompts_gain_science_practice_and_safety_constraints():
    base = "课程：5年级 科学；教材：学校实际科学教材 上册；单元：第一单元；课题：观察；总时长：90分钟。"
    for feature in ("lesson_plan", "lesson_practice"):
        prompt = augment_science_teacher_prompt(feature, base)
        assert "科学教师工作流附加约束" in prompt
        assert "观察事实/实验数据" in prompt
        assert "变量" in prompt
        assert "明火、强电、危险化学品" in prompt
        assert "不得虚构教材章节" in prompt

    assert augment_science_teacher_prompt("lesson_plan", "课程：5年级 数学；教材：人教版") == "课程：5年级 数学；教材：人教版"


def test_teacher_ai_html_exposes_science_lesson_and_clears_ambiguous_defaults():
    import app_v924 as legacy

    html = patch_science_teacher_ai_html(legacy.INDEX_HTML)
    twice = patch_science_teacher_ai_html(html)

    assert html == twice
    assert SCIENCE_TEACHER_AI_MARKER in html
    assert '<select id="alSubject"><option>数学</option><option>语文</option><option>英语</option><option>科学</option></select>' in html
    assert "aqScienceTextbookHint" in html
    assert "alScienceTextbookHint" in html
    assert "科学：请填写学校实际使用的出版社/版本" in html
    assert "if(science&&ambiguous.has(String(textbook.value||'').trim())) textbook.value=''" in html
    assert "textbook.placeholder=science?'必填：学校实际科学教材出版社/版本':'请输入教材版本'" in html


def test_runtime_installs_science_teacher_ai_guard_on_all_teacher_ai_generation_routes():
    import app  # noqa: F401
    import app_v924 as legacy

    assert legacy.app.state.science_teacher_ai_workflow_installed is True
    assert SCIENCE_TEACHER_AI_MARKER in legacy.INDEX_HTML

    expected = {
        ("/ai/questions/generate", "POST"),
        ("/ai/lesson-plan/generate", "POST"),
        ("/ai/lesson-plan/practice", "POST"),
    }
    found = set()
    for route in legacy.app.routes:
        key = (getattr(route, "path", None), "POST")
        if key in expected and "POST" in getattr(route, "methods", set()):
            found.add(key)
            assert hasattr(route.dependant.call, "__wrapped__")
    assert found == expected
