from types import SimpleNamespace
import json

from changying.services.question_type_fit import (
    question_type_fit_score,
    question_type_is_acceptable,
)
from changying.services.reinforcement_subject_policy import augment_reinforcement_prompt
from changying.web.student_quiz_navigation import MARKER
from changying.web.v1_student_practice import select_student_practice_questions


def _row(
    qid,
    *,
    subject="语文",
    knowledge="句子衔接",
    qtype="single_choice",
    options=None,
    answer="",
):
    if options is None:
        options = ["A", "B", "C", "D"] if qtype == "single_choice" else ["正确", "错误"]
    return SimpleNamespace(
        id=qid,
        subject=subject,
        knowledge=knowledge,
        unit="全册基础",
        textbook="统编版（人民教育出版社）",
        text=f"题目 {qid}",
        question_type=qtype,
        options_json=json.dumps(options, ensure_ascii=False),
        correct_index=0 if options else -1,
        answer_json=json.dumps({"answer": answer}, ensure_ascii=False),
    )


def test_chinese_sentence_cohesion_rejects_true_false_but_keeps_natural_forms():
    assert question_type_fit_score("语文", "句子衔接", "single_choice") == 0
    assert question_type_fit_score("语文", "句子衔接", "fill_blank") == 0
    assert question_type_is_acceptable("语文", "句子衔接", "true_false") is False


def test_math_calculation_does_not_get_forced_into_true_false():
    assert question_type_is_acceptable("数学", "小数乘法计算", "calculation") is True
    assert question_type_is_acceptable("数学", "小数乘法计算", "true_false") is False


def test_comprehensive_selector_excludes_mechanical_sentence_cohesion_judgement():
    rows = [
        _row(1, qtype="true_false"),
        _row(2, qtype="single_choice"),
        _row(3, knowledge="关联词运用", qtype="true_false"),
    ]
    chosen = select_student_practice_questions(
        rows,
        kind="comprehensive",
        count=3,
        textbook="统编版（人民教育出版社）",
    )
    ids = {row.id for row in chosen}
    assert 1 not in ids
    assert 2 in ids
    assert 3 in ids


def test_reinforcement_prompt_explains_knowledge_type_fit_without_template_leak():
    base = '最近测试/练习反馈：{"primary":{"grade":5,"subject":"语文","textbook":"统编版（人民教育出版社）"}}'
    prompt = augment_reinforcement_prompt("reinforcement_generate", base)
    assert "知识点—题型匹配约束" in prompt
    assert "句子衔接/排序/连贯优先单选或填空，不使用判断题" in prompt
    assert "{fit_guidance}" not in prompt


def test_runtime_student_quiz_supports_back_forward_and_answer_revision():
    from app import app  # noqa: F401
    import app_v924 as legacy

    html = legacy.INDEX_HTML
    assert MARKER in html
    assert "answersById=new Map()" in html
    assert 'id="quizPrev"' in html
    assert 'id="quizForward"' in html
    assert 'id="quizSubmit"' in html
    assert "可前后切换" in html
    assert "已答 '+count+'/'+qs.length" in html
    assert "orderedAnswers=()=>qs.map(q=>responseFor(q)).filter(Boolean)" in html

    quiz = html.split("function startQuiz(qs,title,aid){", 1)[1].split("async function progress(){", 1)[0]
    assert "answers.push(item)" not in quiz
