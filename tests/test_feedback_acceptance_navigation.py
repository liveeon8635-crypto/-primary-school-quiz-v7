"""反馈 #348 回归测试：手机端反馈验收底部操作区与返回反馈记录。"""

from changying.services.classroom_execution import (
    FEEDBACK_ACCEPTANCE_ACTIONS,
    feedback_acceptance_actions,
    feedback_acceptance_can_return,
    feedback_acceptance_mobile_layout,
    feedback_acceptance_return_target,
)


def test_return_to_records_action_present():
    actions = feedback_acceptance_actions()
    keys = [a["key"] for a in actions]
    assert "return_to_records" in keys
    assert set(keys) == set(FEEDBACK_ACCEPTANCE_ACTIONS)


def test_return_target_points_to_feedback_records():
    assert feedback_acceptance_return_target() == "/v1/workspace?view=feedback_records"
    assert feedback_acceptance_can_return() is True


def test_mobile_layout_prevents_crowding():
    layout = feedback_acceptance_mobile_layout()
    assert layout["stack"] == "vertical"
    assert layout["fullWidthButtons"] is True
    assert layout["gapPx"] >= 8
    assert layout["minTouchTargetPx"] >= 44
    assert layout["safeAreaInsetBottom"] is True
