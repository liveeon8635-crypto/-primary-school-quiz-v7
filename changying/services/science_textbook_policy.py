"""Shared science textbook integrity policy.

Science has multiple valid textbook lines.  Changying must never guess a
publisher/version from generic defaults used by other subjects.
"""

from __future__ import annotations


AMBIGUOUS_SCIENCE_TEXTBOOKS = frozenset(
    {
        "",
        "人教版",
        "人教版（当前最新版）",
        "人教版（PEP·当前最新版）",
        "PEP·当前最新版",
        "统编版",
        "统编版（人民教育出版社）",
    }
)


def require_explicit_science_textbook(subject: str, textbook: str) -> str:
    """Return a science textbook label only when it is explicit and safe."""
    raw_subject = str(subject or "").strip()
    raw_textbook = str(textbook or "").strip()
    if "科学" not in raw_subject:
        return raw_textbook
    if raw_textbook in AMBIGUOUS_SCIENCE_TEXTBOOKS:
        raise ValueError(
            "科学教材必须明确填写学校实际使用的出版社/版本；"
            "不要使用数学、语文或英语界面的通用默认教材名"
        )
    return raw_textbook


def explicit_science_textbook(subject: str, textbook: str) -> str:
    """Return the explicit science label, or an empty string when unresolved."""
    try:
        return require_explicit_science_textbook(subject, textbook)
    except ValueError:
        return ""


__all__ = [
    "AMBIGUOUS_SCIENCE_TEXTBOOKS",
    "explicit_science_textbook",
    "require_explicit_science_textbook",
]
