import pytest
from types import SimpleNamespace

from changying.services.builtin_question_bank import (
    built_in_question_specs,
    built_in_subjects,
    built_in_textbooks,
)
from changying.services.textbook_registry import (
    CHINESE_G5_TEXTBOOK,
    ENGLISH_G5_TEXTBOOK,
    MATH_G5_TEXTBOOK,
    TextbookRegistryError,
    normalize_question_batch,
    normalize_textbook,
    registered_subjects,
    registered_textbooks,
    require_textbook,
)


def test_grade5_registry_is_single_source_for_supported_subjects_and_textbooks():
    assert registered_subjects(5) == ["数学", "语文", "英语"]
    assert built_in_subjects(5) == registered_subjects(5)
    assert registered_textbooks(5, "数学") == [MATH_G5_TEXTBOOK]
    assert registered_textbooks(5, "语文") == [CHINESE_G5_TEXTBOOK]
    assert registered_textbooks(5, "英语") == [ENGLISH_G5_TEXTBOOK]
    assert built_in_textbooks(5, "英语") == [ENGLISH_G5_TEXTBOOK]


def test_only_safe_textbook_aliases_are_normalized():
    assert normalize_textbook(5, "数学", "人教版（当前最新版）") == MATH_G5_TEXTBOOK
    assert normalize_textbook(5, "语文", "统编版") == CHINESE_G5_TEXTBOOK
    assert normalize_textbook(5, "英语", "PEP·当前最新版") == ENGLISH_G5_TEXTBOOK

    with pytest.raises(TextbookRegistryError):
        normalize_textbook(5, "英语", "人教版")
    with pytest.raises(TextbookRegistryError):
        normalize_textbook(5, "英语", "人教版（PEP·旧版）")
    with pytest.raises(TextbookRegistryError):
        normalize_textbook(5, "数学", ENGLISH_G5_TEXTBOOK)
    with pytest.raises(TextbookRegistryError):
        normalize_textbook(5, "语文", MATH_G5_TEXTBOOK)


def test_registered_scope_requires_explicit_textbook_for_write_workflows():
    with pytest.raises(TextbookRegistryError):
        require_textbook(5, "数学", "")
    assert require_textbook(4, "数学", "") == ""


def test_assignment_batch_normalizes_safe_alias_but_rejects_cross_subject_mix():
    rows = [
        SimpleNamespace(grade=5, subject="数学", textbook="人教版（当前最新版）"),
        SimpleNamespace(grade=5, subject="数学", textbook="人教版"),
    ]
    assert normalize_question_batch(rows) == (5, "数学", MATH_G5_TEXTBOOK)
    assert [row.textbook for row in rows] == [MATH_G5_TEXTBOOK, MATH_G5_TEXTBOOK]

    mixed = [
        SimpleNamespace(grade=5, subject="数学", textbook=MATH_G5_TEXTBOOK),
        SimpleNamespace(grade=5, subject="英语", textbook=ENGLISH_G5_TEXTBOOK),
    ]
    with pytest.raises(TextbookRegistryError):
        normalize_question_batch(mixed)


def test_builtin_packs_accept_safe_aliases_but_never_cross_map_textbooks():
    assert len(built_in_question_specs(5, "数学", "人教版（当前最新版）")) >= 180
    assert len(built_in_question_specs(5, "语文", "统编版")) >= 120
    assert len(built_in_question_specs(5, "英语", "PEP·当前最新版")) == 160

    assert built_in_question_specs(5, "英语", MATH_G5_TEXTBOOK) == []
    assert built_in_question_specs(5, "数学", ENGLISH_G5_TEXTBOOK) == []
    assert built_in_question_specs(5, "语文", ENGLISH_G5_TEXTBOOK) == []


def test_runtime_installs_textbook_registry_guard_on_write_routes():
    import app  # noqa: F401
    import app_v924 as legacy

    assert legacy.app.state.textbook_registry_guard_installed is True

    targets = {
        ("/ai/questions/generate", "POST"),
        ("/ai/questions/save", "POST"),
        ("/ai/questions/assign", "POST"),
        ("/teacher/students/{sid}/reinforcement/assign", "POST"),
        ("/teacher/papers", "POST"),
    }
    found = set()
    for route in legacy.app.routes:
        key = (getattr(route, "path", None), "POST")
        if key in targets and "POST" in getattr(route, "methods", set()):
            found.add(key)
            assert hasattr(route.dependant.call, "__wrapped__")
    assert found == targets
