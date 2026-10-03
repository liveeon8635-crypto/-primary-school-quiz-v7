"""反馈 #323 回归测试：/v1/workspace 新手指引只弹一次，点击卡片不再重复弹出。"""

from changying.web import v1_product_assistant as assistant


def test_workspace_tutorial_contract_marker():
    contract = assistant.workspace_tutorial_contract()
    assert contract["marker"] == "changying_v1_workspace_tutorial_shown_once_v1"


def test_workspace_tutorial_shows_once():
    contract = assistant.workspace_tutorial_contract()
    assert contract["showOnce"] is True
    assert contract["page"] == "/v1/workspace"


def test_workspace_tutorial_suppressed_on_card_click():
    contract = assistant.workspace_tutorial_contract()
    assert contract["suppressOnCardClick"] is True
    assert contract["storageKey"] == "changying_v1_workspace_tutorial_seen"
