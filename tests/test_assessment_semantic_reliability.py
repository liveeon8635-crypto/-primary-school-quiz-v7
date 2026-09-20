import inspect
from types import SimpleNamespace

from changying.services.answer_semantics import (
    answer_matches,
    enrich_generated_item,
    infer_unit_semantics,
)
from changying.services.assessment_reliability import mastery_transition


def q(text, *, subject="数学", question_type="short_answer"):
    return SimpleNamespace(text=text, subject=subject, question_type=question_type)


def test_unit_already_printed_after_blank_accepts_numeric_answer():
    question = q("一个梯形的面积是____平方厘米。", question_type="fill_blank")
    assert answer_matches(question, "45", "45", []) is True
    assert answer_matches(question, "45平方厘米", "45", []) is True
    assert answer_matches(question, "45平方米", "45", []) is False
    assert infer_unit_semantics(
        question_text=question.text,
        answer="45",
        subject="数学",
        question_type="fill_blank",
    ) == {"policy": "provided_in_stem", "unit": "平方厘米"}


def test_open_area_answer_requires_correct_unit():
    question = q("一个梯形的上底是5.6厘米，下底是9.4厘米，高是6厘米，它的面积是多少？")
    assert answer_matches(question, "45", "45", []) is False
    assert answer_matches(question, "45平方厘米", "45", []) is True
    assert answer_matches(question, "45cm2", "45", []) is True
    assert answer_matches(question, "45平方米", "45", []) is False


def test_numeric_equivalence_handles_fraction_decimal_and_percent():
    question = q("计算结果是多少？", question_type="calculation")
    assert answer_matches(question, "1/2", "0.5", []) is True
    assert answer_matches(question, "50%", "0.5", []) is True
    assert answer_matches(question, "0.50", "0.5", []) is True


def test_generated_open_area_answer_is_enriched_with_required_unit():
    item = {
        "subject": "数学",
        "question_type": "short_answer",
        "text": "一个长方形长8厘米、宽5厘米，它的面积是多少？",
        "answer": "40",
        "accepted_answers": ["40"],
    }
    enriched = enrich_generated_item(item)
    assert enriched["answer"] == "40平方厘米"
    assert enriched["accepted_answers"] == []
    assert enriched["answer_unit"] == "平方厘米"
    assert enriched["answer_unit_policy"] == "required"


def test_generated_blank_with_printed_unit_keeps_numeric_reference():
    item = {
        "subject": "数学",
        "question_type": "fill_blank",
        "text": "一个长方形长8厘米、宽5厘米，面积是____平方厘米。",
        "answer": "40",
        "accepted_answers": [],
    }
    enriched = enrich_generated_item(item)
    assert enriched["answer"] == "40"
    assert enriched["answer_unit_policy"] == "provided_in_stem"


def test_mastery_requires_two_successful_reinforcement_cycles():
    count, status, mastered = mastery_transition(previous_count=0, demonstrated=True)
    assert (count, status, mastered) == (1, "active", False)

    count, status, mastered = mastery_transition(previous_count=count, demonstrated=True)
    assert (count, status, mastered) == (2, "mastered", True)


def test_failed_reinforcement_resets_mastery_confirmation_count():
    assert mastery_transition(previous_count=1, demonstrated=False) == (0, "active", False)


def test_uncovered_knowledge_keeps_previous_confirmation_count():
    assert mastery_transition(previous_count=1, demonstrated=None) == (1, "active", False)


def test_runtime_installs_semantic_grading_and_evidence_mastery():
    import app  # noqa: F401
    import app_v924 as legacy

    assert legacy.grade_answers.__name__ == "semantic_grade_answers"
    assert legacy.normalized_answer_stats.__name__ == "semantic_normalized_answer_stats"
    assert legacy._reinforcement_mastery_update.__name__ == "evidence_based_mastery_update"


def test_runtime_semantic_grading_uses_half_up_rounding_contract():
    from changying.services.assessment_reliability import install_assessment_reliability

    source = inspect.getsource(install_assessment_reliability)
    assert "implementation.half_up_percent(correct, total)" in source
    assert "round(correct / total * 100)" not in source


def test_runtime_grade_answers_is_semantic_wrapper_after_production_install():
    import app  # noqa: F401
    import app_v924 as legacy

    assert legacy.grade_answers.__name__ == "grade_answers"
    wrapped_source = inspect.getsource(legacy.grade_answers.__wrapped__)
    assert "semantic_grade_answers" in wrapped_source or "implementation.half_up_percent" in wrapped_source
