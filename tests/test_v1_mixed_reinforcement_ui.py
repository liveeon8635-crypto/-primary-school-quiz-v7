from changying.web.v1 import v1_html
from changying.web.v1_student_practice import patch_v1_student_practice_html


def test_v1_student_quiz_supports_mixed_answer_types_and_figures():
    html = v1_html()
    assert "function v1QuestionTypeLabel(q)" in html
    assert "function v1ChoiceLike(q)" in html
    assert "function v1RenderQuestionFigure(fig)" in html
    assert 'id="v1QuizTextAnswer"' in html
    assert "text_answer" in html
    assert "应用简答题" in html
    assert "题目图示" in html


def test_v1_teacher_ai_preview_renders_question_types_answers_and_figures():
    html = patch_v1_student_practice_html(v1_html())
    assert "function cyQuestionTypeLabel(type)" in html
    assert "function cyRenderQuestionFigure(fig)" in html
    assert "参考答案：" in html
    assert "accepted_answers" in html
    assert "q.figure" in html
    assert "5题以上至少使用3种题型" in html


def test_v1_teacher_ai_preview_retries_transient_generation_fetch():
    html = patch_v1_student_practice_html(v1_html())
    assert "retrySafe=method==='GET'||url.includes('/reinforcement/generate')" in html
    assert "attempt<(retrySafe?2:1)" in html
    assert "网络连接刚刚中断，请稍后再试" in html
