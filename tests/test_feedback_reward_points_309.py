"""Regression test for feedback #309: adopted feedback earns reward points.

Feedback #309: each submitted feedback that gets adopted earns one feedback
reward point, redeemable for account time. The point-to-time exchange rate
is intentionally undefined until real data is sufficient, and redemption
stays behind the protected production boundary.
"""

from changying.web import v1_unified_tools_session_bridge as bridge


def test_adopted_feedback_earns_one_point():
    records = [
        {"id": 1, "status": "adopted"},
        {"id": 2, "status": "pending"},
        {"id": 3, "adopted": True},
    ]
    summary = bridge.compute_feedback_reward_points(records)
    assert summary["earnedPoints"] == 2
    assert summary["adoptedIds"] == [1, 3]
    assert summary["exchangeRateDefined"] is False


def test_unadopted_feedback_earns_nothing():
    records = [{"id": 10, "status": "pending"}, {"id": 11, "status": "rejected"}]
    summary = bridge.compute_feedback_reward_points(records)
    assert summary["earnedPoints"] == 0
    assert summary["adoptedIds"] == []


def test_single_record_summary_never_grants_account_time():
    result = bridge.summarize_feedback_reward_for_record({"id": 5, "status": "adopted"})
    assert result["adopted"] is True
    assert result["earnedPoints"] == 1
    assert result["accountTimeGranted"] == 0
    assert result["exchangeRateDefined"] is False


def test_redemption_preview_is_reversible_and_non_destructive():
    records = [{"id": 7, "status": "adopted"}]
    preview = bridge.build_feedback_reward_redemption_preview(records)
    assert preview["redeemablePoints"] == 1
    assert preview["accountTimeGranted"] == 0
    assert preview["reversible"] is True


def test_handler_claim_reports_points_without_mutating_time():
    records = [{"id": 9, "status": "adopted"}]
    result = bridge.handle_feedback_reward_request(
        {"action": "claim_feedback_reward"}, records
    )
    assert result["ok"] is True
    assert result["claimed"] is True
    assert result["earnedPoints"] == 1
    assert result["accountTimeGranted"] == 0
    assert result["destructive"] is False
