import pytest

from changying.web.science_teacher_ai import (
    SCIENCE_TEACHER_AI_MARKER,
    augment_science_teacher_prompt,
    patch_science_teacher_ai_html,
    require_explicit_science_textbook,
)


def test_science_textbook_requires_school_specific_label():
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

    assert (
        require_explicit_science_textbook("科学", "人教/鄂教版·学校现用版")
        == "人教/鄂教版·学校现用版"
    )
    assert require_explicit_science_textbook("数学", "人教版") == "人教版"


def test_science_lesson_prompt_adds_evidence_practice_and_safety_contract():
    base = (
        "你是中国小学教师的备课助手。"
        "课程：5年级 科学；教材：学校实际科学教材 上册；单元：第一单元。"
    )
    out = augment_science_teacher_prompt("lesson_plan", base)
    assert "科学教师工作流附加约束" in out
    assert "观察事实/实验数据" in out
    assert "变量控制" in out
    assert "明火、强电、危险化学品" in out
    assert "不得猜测或替换" in out

    practice = augment_science_teacher_prompt("lesson_practice", base)
    assert "开放探究题不能伪装成唯一自动判分答案" in practice
    math = base.replace("科学", "数学")
    assert augment_science_teacher_prompt("lesson_plan", math) == math
    assert augment_science_teacher_prompt("grading", base) == base


def test_science_teacher_ui_patch_adds_lesson_subject_hint_and_dynamic_default_clear():
    html = """
    <html><body>
      <select id="aqSubject"><option>数学</option><option>语文</option><option>英语</option><option>科学</option></select>
      <input id="aqTextbook" value="人教版">
      <select id="alSubject"><option>数学</option><option>语文</option><option>英语</option></select>
      <input id="alTextbook" value="人教版">
    </body></html>
    """
    once = patch_science_teacher_ai_html(html)
    twice = patch_science_teacher_ai_html(once)

    assert once == twice
    assert SCIENCE_TEACHER_AI_MARKER in once
    assert '<option>英语</option><option>科学</option></select>' in once
    assert "aqScienceTextbookHint" in once
    assert "alScienceTextbookHint" in once
    assert "学校实际使用的出版社/版本" in once
    assert "ambiguous.has" in once
    assert "textbook.value=''" in once
    assert "aria-required" in once


def test_runtime_installs_science_teacher_ai_workflow_on_classic_ai_routes():
    import app  # noqa: F401
    import app_v924 as legacy

    assert legacy.app.state.science_teacher_ai_workflow_installed is True
    assert SCIENCE_TEACHER_AI_MARKER in legacy.INDEX_HTML
    assert '<select id="alSubject"><option>数学</option><option>语文</option><option>英语</option><option>科学</option></select>' in legacy.INDEX_HTML
    assert "科学：请填写学校实际使用的出版社/版本" in legacy.INDEX_HTML

    targets = {
        ("/ai/questions/generate", "POST"),
        ("/ai/lesson-plan/generate", "POST"),
        ("/ai/lesson-plan/practice", "POST"),
    }
    found = set()
    for route in legacy.app.routes:
        key = (getattr(route, "path", None), "POST")
        if key in targets and "POST" in getattr(route, "methods", set()):
            found.add(key)
            assert hasattr(route.dependant.call, "__wrapped__")
    assert found == targets
