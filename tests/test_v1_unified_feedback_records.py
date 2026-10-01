"""Regression test for feedback #322: unified feedback records in assistant.

Verifies that the top feedback records panel is merged into the product
assistant, that the submit-feedback button exposes a dropdown with both
submit and view-records actions, and that full feedback features are retained.
"""

from changying.web import v1_product_assistant as assistant


def test_unified_feedback_records_marker_present():
    assert assistant.UNIFIED_FEEDBACK_RECORDS_MARKER == "changying_v1_unified_feedback_records_v1"


def test_feedback_records_merged_into_assistant():
    assert assistant.FEEDBACK_RECORDS_MERGED_INTO_ASSISTANT is True
    assert assistant.FEEDBACK_TOP_PANEL_HIDDEN is True


def test_submit_feedback_dropdown_actions():
    assert assistant.FEEDBACK_SUBMIT_DROPDOWN_ACTIONS == (
        "submit_feedback",
        "view_feedback_records",
    )


def test_feedback_records_full_features_retained():
    features = set(assistant.FEEDBACK_RECORDS_FULL_FEATURES)
    assert {"submit", "attachment", "receipt", "reward_points", "follow_up"} <= features


def test_shared_button_and_auto_expand_flags():
    assert assistant.FEEDBACK_RECORDS_SHARED_BUTTON is True
    assert assistant.FEEDBACK_RECORDS_AUTO_EXPAND_ON_SUBMIT is True
