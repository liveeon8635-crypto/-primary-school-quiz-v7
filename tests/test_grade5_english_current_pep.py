from changying.services.builtin_question_bank import (
    built_in_question_specs,
    built_in_subjects,
    built_in_textbooks,
    potential_question_catalog,
)
from changying.services.builtin_question_bank_english import ENGLISH_G5_TEXTBOOK


CURRENT_UNITS = {
    "Unit 1 · Different friends",
    "Unit 2 · My feelings",
    "Unit 3 · Work and play",
    "Unit 4 · Healthy habits",
    "Unit 5 · Food we eat",
    "Unit 6 · Nature and us",
}


def test_grade5_english_current_pep_is_available():
    assert "英语" in built_in_subjects(5)
    assert built_in_textbooks(5, "英语") == [ENGLISH_G5_TEXTBOOK]
    assert ENGLISH_G5_TEXTBOOK == "人教版（PEP·当前最新版）"


def test_current_pep_english_pack_has_128_original_online_items():
    rows = built_in_question_specs(5, "英语", ENGLISH_G5_TEXTBOOK)
    assert len(rows) == 128
    assert {row["unit"] for row in rows} == CURRENT_UNITS
    assert {row["subject"] for row in rows} == {"英语"}
    assert {row["textbook"] for row in rows} == {ENGLISH_G5_TEXTBOOK}
    assert all(len(row["options"]) == 4 for row in rows)
    assert all(0 <= int(row["correct_index"]) < 4 for row in rows)
    assert all((row["text"] or "").strip() for row in rows)


def test_english_pack_does_not_fall_back_to_legacy_unit_line():
    rows = built_in_question_specs(5, "英语", ENGLISH_G5_TEXTBOOK)
    units = " | ".join(sorted({row["unit"] for row in rows}))
    for legacy in (
        "What's he like?",
        "My week",
        "What would you like?",
        "What can you do?",
        "There is a big bed",
        "In a nature park",
    ):
        assert legacy not in units


def test_english_practice_catalog_exposes_balanced_modules():
    modules, total = potential_question_catalog(
        [],
        grade=5,
        subject="英语",
        textbook=ENGLISH_G5_TEXTBOOK,
    )
    counts = {row["knowledge"]: row["count"] for row in modules}
    assert total == 128
    assert len(counts) == 16
    assert set(counts.values()) == {8}
    assert counts["人物信息理解"] == 8
    assert counts["情绪原因与建议"] == 8
    assert counts["一般现在时"] == 8
    assert counts["should与shouldn't"] == 8
    assert counts["饮食选择与表达"] == 8
    assert counts["保护自然与行为判断"] == 8


def test_practice_ui_names_current_pep_english_line():
    import app  # noqa: F401
    from changying.web import v1 as v1_module

    html = v1_module.v1_html()
    assert "英语使用人教版（PEP·当前最新版）" in html
    assert "旧教材单元" in html
