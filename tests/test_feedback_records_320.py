"""Regression test for feedback #320: feedback records with 取用/回执/奖励分 status,
follow-up append, image upload, and 查收（满意）acknowledgement."""

from changying.web import v1_product_assistant as mod


def test_feedback_records_markers_present():
    assert mod.FEEDBACK_RECORDS_PATH == "/v1/product-feedback/records"
    assert mod.FEEDBACK_RECORDS_FOLLOWUP_PATH.endswith("/follow-up")
    assert mod.FEEDBACK_RECORDS_ACK_PATH.endswith("/acknowledge")
    assert mod.FEEDBACK_RECORDS_FOLLOWUP_ATTACHMENT is True
    assert mod.FEEDBACK_RECORDS_ACKNOWLEDGE_SATISFIED is True
    assert "acknowledge_satisfied" in mod.FEEDBACK_RECORDS_FULL_FEATURES
    assert set(mod.FEEDBACK_RECORDS_STATUS_FIELDS) == {"taken", "receipt", "reward_points"}


def test_feedback_record_status_derivation():
    status = mod._feedback_record_status({
        "takenAt": "2026-10-01T00:00:00Z",
        "receipt": "received",
        "rewardPoints": 5,
        "followUps": [{"message": "追加"}],
        "acknowledgedSatisfied": True,
    })
    assert status["taken"] is True
    assert status["receipt"] == "received"
    assert status["reward_points"] == 5
    assert status["follow_up_count"] == 1
    assert status["acknowledged_satisfied"] is True


def test_feedback_record_status_defaults():
    status = mod._feedback_record_status({})
    assert status["taken"] is False
    assert status["receipt"] == "pending"
    assert status["reward_points"] == 0
    assert status["follow_up_count"] == 0
    assert status["acknowledged_satisfied"] is False
