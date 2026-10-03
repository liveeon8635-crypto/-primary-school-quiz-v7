"""反馈 #309 回归测试：被取用的反馈对应增加反馈奖励分，可用于兑换帐号时长。"""

from changying.web.v1_product_assistant import (
    FEEDBACK_REWARD_POINTS_PER_ADOPTED,
    FEEDBACK_REWARD_REDEEM_TARGET,
    feedback_reward_points,
)


def test_adopted_feedback_earns_reward_points():
    records = [
        {"feedbackId": 1, "status": "已取用"},
        {"feedbackId": 2, "status": "已提交"},
        {"feedbackId": 3, "status": "已采纳"},
    ]
    result = feedback_reward_points(records)
    assert result["adoptedCount"] == 2
    assert result["totalRewardPoints"] == 2 * FEEDBACK_REWARD_POINTS_PER_ADOPTED
    assert result["redeemTarget"] == FEEDBACK_REWARD_REDEEM_TARGET
    assert result["redeemRate"] is None


def test_unadopted_feedback_earns_no_points():
    result = feedback_reward_points([{"feedbackId": 9, "status": "已提交"}])
    assert result["adoptedCount"] == 0
    assert result["totalRewardPoints"] == 0
    assert result["items"][0]["rewardPoints"] == 0


def test_empty_records_are_safe():
    result = feedback_reward_points(None)
    assert result["totalRewardPoints"] == 0
    assert result["items"] == []
