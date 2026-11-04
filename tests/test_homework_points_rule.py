"""晚托作业积分规则：按时 +3；正确率 60 中点上下一档 ±3；扣分扣到 0 为止。"""
from __future__ import annotations

from changying.services import homework_points_rule as rule


def test_on_time_gives_three_points():
    assert rule.pending_on_time(True)["points"] == 3


def test_late_gives_no_on_time_points_but_is_not_a_penalty():
    late = rule.pending_on_time(False)
    assert late["points"] == 0
    assert "仍可做完" in late["note"]


def test_accuracy_ladder_is_centred_on_sixty_with_three_point_swing():
    assert rule.accuracy_points(100) == 3
    assert rule.accuracy_points(90) == 3
    assert rule.accuracy_points(85) == 2
    assert rule.accuracy_points(75) == 1
    assert rule.accuracy_points(65) == 0
    assert rule.accuracy_points(60) == 0
    assert rule.accuracy_points(55) == -1
    assert rule.accuracy_points(45) == -2
    assert rule.accuracy_points(30) == -3
    assert rule.accuracy_points(0) == -3


def test_accuracy_is_clamped_into_range():
    assert rule.accuracy_points(-20) == -3
    assert rule.accuracy_points(140) == 3


def test_accuracy_settles_only_after_grading():
    pending = rule.settle_accuracy(None, graded=False)
    assert pending["settled"] is False and pending["points"] == 0


def test_unsettled_stays_open_without_an_expiry():
    # 没批改就一直挂着：过期会让迟批的作业永久失去结算机会，需求里没有这条
    expired = rule.settle_accuracy(None, graded=False)
    assert expired["settled"] is False and expired["points"] == 0


def test_deduction_never_takes_the_balance_below_zero():
    """业务方选 B：扣分扣到 0 为止。"""
    broke = rule.settle_accuracy(20, balance=1)
    assert broke["rawPoints"] == -3
    assert broke["points"] == -1          # 只能扣掉剩下的 1 分
    assert broke["clamped"] is True


def test_zero_balance_cannot_be_deducted_at_all():
    zero = rule.settle_accuracy(20, balance=0)
    assert zero["points"] == 0 and zero["clamped"] is True


def test_positive_adjustment_is_never_clamped():
    up = rule.settle_accuracy(95, balance=0)
    assert up["points"] == 3 and up["clamped"] is False


def test_total_combines_on_time_and_accuracy():
    total = rule.total_for_assignment(True, 55, balance=10)
    assert total["total"] == 2            # +3 按时，-1 正确率
    assert total["fullySettled"] is True

def test_unknown_balance_never_deducts():
    """不知道余额就不扣：宁可不结算，也不能扣成负数。"""
    unknown = rule.settle_accuracy(20, balance=None)
    assert unknown["points"] == 0 and unknown["clamped"] is True


def test_total_counts_the_on_time_points_before_deducting():
    # 余额 0 + 按时 3 分 = 3，正确率 −3 可以全扣，最终 0 而不是把余额扣成 −3
    total = rule.total_for_assignment(True, 20, balance=0)
    assert total["total"] == 0
    assert [e["points"] for e in total["entries"]] == [3, -3]