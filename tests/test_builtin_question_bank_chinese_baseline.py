"""Regression test for feedback #310: Chinese knowledge-module practice must
never be empty when a student has no matched textbook.

Two students (淦云凡, 翁舒言) had no available textbook and no knowledge-module
practice detail. The baseline fallback must always return a non-empty,
well-formed spec list.
"""

from __future__ import annotations

from changying.services.builtin_question_bank_chinese import (
    baseline_chinese_specs,
    grade5_chinese_specs,
)


def test_baseline_chinese_specs_is_non_empty() -> None:
    rows = baseline_chinese_specs()
    assert isinstance(rows, list)
    assert len(rows) > 0, "baseline Chinese practice must not be empty"


def test_baseline_chinese_specs_matches_grade5_pack() -> None:
    assert baseline_chinese_specs() == grade5_chinese_specs()


def test_baseline_chinese_specs_have_required_fields() -> None:
    required = {
        "grade",
        "subject",
        "textbook",
        "semester",
        "unit",
        "knowledge",
        "text",
        "options",
        "correct_index",
        "explanation",
    }
    for row in baseline_chinese_specs():
        assert required.issubset(row.keys())
        assert row["subject"] == "语文"
        assert isinstance(row["options"], list)
        assert len(row["options"]) == 4
        assert 0 <= row["correct_index"] < 4
        assert row["options"][row["correct_index"]]
