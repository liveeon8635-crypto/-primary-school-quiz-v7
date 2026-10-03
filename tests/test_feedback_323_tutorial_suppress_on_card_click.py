"""反馈 #323 回归测试：点击卡片不再重复弹出新手指引。

机构老师钟老师在 /v1/workspace 反馈“每次点击卡片这个新手指引都弹出来”。
本测试锁定：卡片点击触发时新手指引不自动弹出；同一会话已展示过也不重复弹出；
仅首次进入工作台且未展示过时才自动弹出一次。
"""

from changying.web.v1_product_assistant import (
    TUTORIAL_SUPPRESS_ON_CARD_CLICK_MARKER,
    TUTORIAL_SUPPRESSED_TRIGGERS,
    tutorial_should_auto_open,
    tutorial_suppression_contract,
)


def test_card_click_does_not_auto_open_tutorial():
    for trigger in TUTORIAL_SUPPRESSED_TRIGGERS:
        assert tutorial_should_auto_open(trigger=trigger, already_shown=False) is False


def test_tutorial_does_not_reopen_when_already_shown():
    assert tutorial_should_auto_open(trigger="workspace_enter", already_shown=True) is False


def test_tutorial_auto_opens_once_on_first_workspace_enter():
    assert tutorial_should_auto_open(trigger="workspace_enter", already_shown=False) is True


def test_suppression_contract_marker_and_flags():
    contract = tutorial_suppression_contract()
    assert contract["marker"] == TUTORIAL_SUPPRESS_ON_CARD_CLICK_MARKER
    assert contract["cardClickSuppressesTutorial"] is True
    assert contract["reopenOnCardClick"] is False
    assert "card_click" in contract["suppressedTriggers"]
