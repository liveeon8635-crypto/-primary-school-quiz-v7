import inspect

from changying.services.builtin_question_bank import (
    built_in_question_specs,
    built_in_subjects,
    built_in_textbooks,
)


def test_grade5_auto_assessment_exposes_math_and_chinese_only():
    assert built_in_subjects(5) == ["数学", "语文"]
    assert built_in_textbooks(5, "数学") == ["人教版"]
    assert built_in_textbooks(5, "语文") == ["统编版（人民教育出版社）"]
    assert built_in_subjects(4) == []


def test_chinese_modules_are_large_enough_for_comprehensive_and_module_practice():
    specs = built_in_question_specs(5, "语文", "统编版（人民教育出版社）")
    assert len(specs) >= 64
    counts = {}
    for row in specs:
        counts[row["knowledge"]] = counts.get(row["knowledge"], 0) + 1
    assert len(counts) >= 8
    assert min(counts.values()) >= 8


def test_runtime_reinforcement_context_is_subject_aware():
    import app  # noqa: F401
    import app_v924 as legacy

    assert legacy.student_assessment_context.__name__ == "subject_aware_context"
    source = inspect.getsource(legacy.teacher_reinforcement_generate)
    assert "context_subject" in source
    assert 'forced_subject!="数学"' in source
    assert "非数学学科" in source
