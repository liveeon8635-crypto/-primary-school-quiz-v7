"""反馈 #316 回归测试：产品助手必须能把用户导航到明确的反馈记录功能界面。

验证两点：
1. 用户询问“反馈记录”时，助手导航卡片返回 feedback_records 卡片，指向可打开的反馈记录页面路径；
2. 未命中关键词时，feedback_records 也参与默认引导卡片集合，反馈记录入口始终可被发现。
"""
from changying.web.v1_product_assistant import _guidance_cards


def test_feedback_records_card_returned_for_records_query():
    cards = _guidance_cards("我在哪里可以看到我提交过的反馈记录和回执？", "/v1/workspace")
    assert any(
        card["key"] == "feedback_records"
        and card["path"] == "/v1/feedback"
        and "反馈记录" in card["title"]
        for card in cards
    ), cards


def test_feedback_records_card_title_and_description_not_placeholder():
    cards = _guidance_cards("反馈记录", "")
    card = next((c for c in cards if c["key"] == "feedback_records"), None)
    assert card is not None
    assert card["title"].strip()
    assert card["description"].strip()
    assert card["path"].startswith("/v1")
