"""Regression tests for Feedback #309: feedback reward points.

Each submitted feedback that gets adopted earns one reward point,
redeemable for account time. The exchange rate is intentionally
undefined until real data is sufficient, and redemption stays behind
the protected boundary.
"""

from changying.web.v1_unified_tools_session_bridge import (
    V1_FEEDBACK_REWARD_MARKER,
    compute_feedback_reward_points,
    handle_feedback_reward_request,
    is_adopted_feedback,
)


def test_adopted_feedback_detected_by_status():
    assert is_adopted_feedback({"id": 1, "status": "adopted"}) is True
    assert is_adopted_feedback({"id": 2, "status": "accepted"}) is True
    assert is_adopted_feedback({"id": 3, "status": "used"}) is True


def test_adopted_feedback_detected_by_flag():
    assert is_adopted_feedback({"id": 1, "adopted": True}) is True
    assert is_adopted_feedback({"id": 2, "isAdopted": True}) is True


def test_pending_feedback_earns_no_point():
    assert is_adopted_feedback({"id": 1, "status": "pending"}) is False
    assert is_adopted_feedback({"id": 2, "status": "rejected"}) is False
    assert is_adopted_feedback({}) is False
    assert is_adopted_feedback(None) is False


def test_each_adopted_feedback_earns_one_point():
    records = [
        {"id": 1, "status": "adopted"},
        {"id": 2, "status": "pending"},
        {"id": 3, "status": "adopted"},
        {"id": 4, "status": "rejected"},
    ]
    summary = compute_feedback_reward_points(records)
    assert summary["marker"] == V1_FEEDBACK_REWARD_MARKER
    assert summary["earnedPoints"] == 2
    assert summary["adoptedIds"] == [1, 3]
    assert summary["exchangeRateDefined"] is False
    assert summary["redeemable"] is False


def test_empty_feedback_earns_zero_points():
    summary = compute_feedback_reward_points([])
    assert summary["earnedPoints"] == 0
    assert summary["adoptedIds"] == []


def test_handler_reports_points_without_mutating_account_time():
    records = [{"id": 10, "status": "adopted"}]
    result = handle_feedback_reward_request(
        {"action": "preview_feedback_reward"}, records
    )
    assert result["ok"] is True
    assert result["marker"] == V1_FEEDBACK_REWARD_MARKER
    assert result["summary"]["earnedPoints"] == 1
    assert result["destructive"] is False
    assert result["requiresConfirmation"] is True


def test_handler_rejects_unsupported_action():
    result = handle_feedback_reward_request({"action": "redeem"}, [])
    assert result["ok"] is False
    assert result["error"] == "unsupported_action"


def test_handler_rejects_invalid_payload():
    result = handle_feedback_reward_request(None, [])
    assert result["ok"] is False
    assert result["error"] == "invalid_payload"
