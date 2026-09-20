import inspect

from changying.services.builtin_question_bank import (
    built_in_question_specs,
    built_in_subjects,
    built_in_textbooks,
)


def test_science_is_not_exposed_as_a_built_in_textbook_pack_before_local_version_is_registered():
    assert "科学" not in built_in_subjects(5)
    assert built_in_textbooks(5, "科学") == []
    assert built_in_question_specs(5, "科学") == []
    assert built_in_question_specs(5, "科学", "人教版") == []


def test_science_ai_generation_requires_explicit_school_textbook_and_has_subject_rules():
    import app_v924 as legacy

    source = inspect.getsource(legacy.ai_generate_questions)
    assert "科学教材必须明确填写学校实际使用的出版社/版本" in source
    assert 'science_textbook=="人教版"' in source
    assert "【科学命题规则】" in source
    assert "不得自行猜测、替换" in source
    assert "明火、强电、危险化学品" in source
    assert "基于证据解释" in source
