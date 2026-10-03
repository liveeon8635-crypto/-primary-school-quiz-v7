"""Regression test: onboarding guide must not re-appear on every card click.

Feedback #323 (/v1/workspace): clicking a card re-triggers the new-user guide
every time. The guide must be shown at most once per user, gated by a persisted
seen flag exposed via window.ChangyingFeedbackCenter.shouldShowGuide().
"""
import pathlib
import re


FEEDBACK_CENTER = pathlib.Path(__file__).resolve().parents[1] / "changying" / "web" / "feedback_center.js"


def _source():
    return FEEDBACK_CENTER.read_text(encoding="utf-8")


def test_guide_seen_flag_is_persisted():
    src = _source()
    assert "v717OnboardingGuideSeen" in src, "guide seen flag key must be defined"
    assert "localStorage.setItem(GUIDE_SEEN_KEY" in src, "guide seen flag must be persisted"


def test_should_show_guide_helper_exposed():
    src = _source()
    assert "shouldShowGuide" in src, "shouldShowGuide helper must be exposed"
    assert "markGuideSeen" in src, "markGuideSeen helper must be exposed"
    assert re.search(r"window\.ChangyingFeedbackCenter\s*=\s*Object\.freeze\(\{[^}]*shouldShowGuide", src, re.S), (
        "shouldShowGuide must be part of the frozen ChangyingFeedbackCenter API"
    )


def test_should_show_guide_returns_false_after_seen():
    src = _source()
    # shouldShowGuide must be the negation of guideSeen so a persisted flag suppresses it.
    assert re.search(r"const\s+shouldShowGuide\s*=\s*\(\)\s*=>\s*!guideSeen\(\)", src), (
        "shouldShowGuide must return false once the guide has been seen"
    )
