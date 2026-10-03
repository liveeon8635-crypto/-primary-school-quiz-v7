"""Regression test for feedback #304: Grade 5 module practice must expose the
latest PEP textbook revision marker instead of a stale one.
"""

from changying.services.builtin_question_bank_chinese import (
    PEP_G5_TEXTBOOK_REVISION,
    textbook_revision,
)


def test_textbook_revision_marker_present():
    assert PEP_G5_TEXTBOOK_REVISION == "2024-pep-latest"


def test_textbook_revision_callable_returns_latest():
    assert textbook_revision() == "2024-pep-latest"
