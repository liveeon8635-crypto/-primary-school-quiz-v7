from pathlib import Path


def test_teacher_grading_ui_shows_structured_rubric_review():
    source = Path("app_v924.py").read_text(encoding="utf-8")

    assert "function aiRubricRows(result)" in source
    assert "r.rubric_results||[]" in source
    assert "主观题评分点核对" in source
    assert "已达到：" in source
    assert "未达到：" in source
    assert "需教师确认：" in source
    assert "最终分数仍以教师确认为准" in source


def test_rubric_ui_does_not_auto_confirm_teacher_score():
    source = Path("app_v924.py").read_text(encoding="utf-8")

    rubric_start = source.index("function aiRubricRows(result)")
    rubric_end = source.index("async function openAIGradingLoop", rubric_start)
    rubric_source = source[rubric_start:rubric_end]

    assert "/grading-confirm" not in rubric_source
    assert "confirmAIGrade" not in rubric_source
