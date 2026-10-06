"""Regression test for feedback #335: 组卷作业提交不了作业.

Teacher 钟老师 reported that on /classic?legacy=1&unified=1&page=papers the
组卷作业 could not be submitted. The product assistant must expose a guidance
card that routes the teacher to the paper tool and explains the submit path.
"""

from changying.web import v1_product_assistant as assistant


def test_paper_submit_guidance_card_exists():
    cards = {card["key"]: card for card in assistant._GUIDANCE_CARDS}
    assert "paper_submit" in cards, "组卷作业提交 guidance card must exist for feedback #335"
    card = cards["paper_submit"]
    assert card["path"] == "/v1/tool?page=papers"
    keywords = card["keywords"]
    assert "提交不了作业" in keywords
    assert "组卷作业提交" in keywords


def test_homework_create_card_still_present():
    cards = {card["key"]: card for card in assistant._GUIDANCE_CARDS}
    assert "homework_create" in cards
    assert cards["homework_create"]["path"] == "/v1/tool?page=papers"
